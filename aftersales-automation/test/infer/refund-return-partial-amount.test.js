'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { inferDecision } = require('../../lib/infer');
const { isBatchExecutable } = require('../../lib/constants');
const { saveConfirmedSkuPricing, setConfigPathForTests } = require('../../lib/sku-pricing');

function makeData({
  attr1 = '咖啡5盒',
  archiveItems = [{ name: '咖啡', specCode: 'COFFEE', qty: 5 }],
  productSpecCode = 'SKU-COFFEE-5',
  amount = 119,
  receivedItems = [{ name: '咖啡', specCode: 'COFFEE', qtyGood: 4, qtyBad: 0 }],
  returnQty = 4,
  gifts = [],
} = {}) {
  return {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '七天无理由退货',
      returnTracking: 'RETURN-PARTIAL',
      amount,
      subOrders: [{ id: 'SUB-1', sku: 'SKU-1', attr1, afterSaleNum: 1 }],
      gifts,
    },
    productArchives: [{ subOrderId: 'SUB-1', subItems: archiveItems }],
    productMatches: [{ subOrderId: 'SUB-1', matched: true, specCode: productSpecCode }],
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-PARTIAL',
        tracking: 'RETURN-PARTIAL',
        goodsStatus: '卖家已收到退货',
        returnQty,
        items: receivedItems,
      }],
    },
    collectErrors: [],
  };
}

function infer(collectedData) {
  return inferDecision(
    { mode: 'live', collectedData, workOrderNum: 'WORK-PARTIAL', queueItemId: 'Q-PARTIAL' },
    { id: 'Q-PARTIAL', type: '退货退款', source: 'scan' },
  );
}

function withTempPricing(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aftersales-partial-amount-'));
  const file = path.join(dir, 'sku-pricing.json');
  setConfigPathForTests(file);
  try {
    return fn();
  } finally {
    setConfigPathForTests(null);
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('单子订单单商品少退时给出人工修改退款金额，且禁止无人自动执行', () => withTempPricing(() => {
  const decision = infer(makeData());

  assert.equal(decision.action, 'reject');
  assert.equal(decision.reasonCode, 'PARTIAL_RETURN_AMOUNT_MANUAL');
  assert.equal(decision.refundAmountRecommendation.recommendedAmount, 95.2);
  assert.equal(decision.refundAmountRecommendation.formula, '119/5*4=95.2');
  assert.equal(decision.rejectDetail, '退回少1件咖啡，修改金额119/5*4=95.2');
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(isBatchExecutable(decision, 'simulated'), false);
  assert.match(decision.recommendedActionLabel, /95\.20/);
}));

test('15送3首次遇到时只生成SKU确认标记，确认后基于同一采集数据计算13份计价商品', () => withTempPricing(() => {
  const data = makeData({
    attr1: '美式风味咖啡15盒送3盒',
    archiveItems: [{ name: '美式风味咖啡', specCode: 'COFFEE', qty: 18 }],
    productSpecCode: 'KGOS-15-3',
    amount: 1199.57,
    receivedItems: [{ name: '美式风味咖啡', specCode: 'COFFEE', qtyGood: 16, qtyBad: 0 }],
    returnQty: 16,
  });

  const before = infer(data);
  assert.equal(before.action, 'escalate');
  assert.equal(before.humanTriggeredExecutionAllowed, false);
  assert.deepEqual(before.skuPricingPending, {
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡15盒送3盒',
    physicalQty: 18,
    suggestedPricedQty: 15,
    suggestedBundledGiftQty: 3,
    compositionMismatch: false,
  });

  saveConfirmedSkuPricing([{
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡15盒送3盒',
    physicalQty: 18,
    pricedQty: 15,
    bundledGiftQty: 3,
  }]);

  const after = infer(data);
  assert.equal(after.action, 'reject');
  assert.equal(after.reasonCode, 'PARTIAL_RETURN_AMOUNT_MANUAL');
  assert.equal(after.refundAmountRecommendation.refundablePricedQty, 13);
  assert.equal(after.refundAmountRecommendation.recommendedAmount, 1039.63);
  assert.equal(after.refundAmountRecommendation.formula, '1199.57/15*13=1039.63');
  assert.equal(after.rejectDetail, '退回少2件美式风味咖啡，修改金额1199.57/15*13=1039.63');
}));

test('同一SKU档案含两个不同商品时不会进入部分退款金额辅助分支', () => withTempPricing(() => {
  const data = makeData({
    attr1: '咖啡3+杯子1',
    archiveItems: [
      { name: '咖啡', specCode: 'COFFEE', qty: 3 },
      { name: '杯子', specCode: 'CUP', qty: 1 },
    ],
    productSpecCode: 'MIXED-3-1',
    amount: 100,
    receivedItems: [{ name: '咖啡', specCode: 'COFFEE', qtyGood: 2, qtyBad: 0 }],
    returnQty: 2,
  });

  const decision = infer(data);
  assert.equal(decision.action, 'escalate');
  assert.equal(decision.refundAmountRecommendation, undefined);
  assert.equal(decision.skuPricingPending, undefined);
}));
