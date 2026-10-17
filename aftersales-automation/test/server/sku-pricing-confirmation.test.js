'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { confirmSkuPricingAndReinfer } = require('../../lib/server/sku-pricing-confirmation');

function makeSim(id, queueItemId, workOrderNum, specCode = 'KGOS-15-3', physicalQty = 18) {
  return {
    id,
    mode: 'live',
    queueItemId,
    workOrderNum,
    createdAt: '2026-10-12T00:00:00.000Z',
    collectedData: { ticket: { marker: workOrderNum } },
    decision: {
      action: 'escalate',
      skuPricingPending: {
        specCode,
        specName: '美式风味咖啡15盒送3盒',
        physicalQty,
        suggestedPricedQty: 15,
        suggestedBundledGiftQty: 3,
      },
    },
  };
}

test('确认一个SKU后只用已有collectedData重推理其关联工单', () => {
  const sims = [
    makeSim('S1', 'Q1', 'W1'),
    makeSim('S2', 'Q2', 'W2'),
    makeSim('S3', 'Q3', 'W3', 'OTHER', 12),
  ];
  const updates = [];
  const savedEntries = [];
  const fakeDb = {
    readSimulations: () => sims,
    readQueue: () => ({ items: [
      { id: 'Q1', status: 'simulated', type: '退货退款' },
      { id: 'Q2', status: 'simulated', type: '退货退款' },
      { id: 'Q3', status: 'simulated', type: '退货退款' },
    ] }),
    updateSimulation: (id, patch) => updates.push({ id, patch }),
  };

  const result = confirmSkuPricingAndReinfer([{
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡15盒送3盒',
    physicalQty: 18,
    pricedQty: 15,
    bundledGiftQty: 3,
  }], {
    db: fakeDb,
    saveConfirmedSkuPricing: entries => {
      savedEntries.push(...entries);
      return entries;
    },
    inferDecision: (sim, queueItem) => ({
      action: 'reject',
      reasonCode: 'PARTIAL_RETURN_AMOUNT_MANUAL',
      fromCollectedMarker: sim.collectedData.ticket.marker,
      queueItemId: queueItem.id,
    }),
    now: () => '2026-10-12T01:00:00.000Z',
  });

  assert.equal(savedEntries.length, 1);
  assert.deepEqual(updates.map(item => item.id), ['S1', 'S2']);
  assert.deepEqual(result.reinferred.map(item => item.workOrderNum), ['W1', 'W2']);
  assert.equal(updates[0].patch.decision.fromCollectedMarker, 'W1');
  assert.equal(updates[1].patch.decision.fromCollectedMarker, 'W2');
});

test('提交的ERP实际组成与当前关联工单不一致时拒绝保存', () => {
  const fakeDb = {
    readSimulations: () => [makeSim('S1', 'Q1', 'W1', 'KGOS-15-3', 18)],
    readQueue: () => ({ items: [{ id: 'Q1', status: 'simulated', type: '退货退款' }] }),
    updateSimulation: () => { throw new Error('不应更新'); },
  };
  let saved = false;

  assert.throws(() => confirmSkuPricingAndReinfer([{
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡15盒送3盒',
    physicalQty: 20,
    pricedQty: 18,
    bundledGiftQty: 2,
  }], {
    db: fakeDb,
    saveConfirmedSkuPricing: () => { saved = true; return []; },
  }), /ERP实际组成与提交值不一致/);
  assert.equal(saved, false);
});
