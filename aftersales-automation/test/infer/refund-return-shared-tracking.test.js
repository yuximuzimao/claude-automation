'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { inferDecision } = require('../../lib/infer');
const { shouldAutoExecute } = require('../../lib/server/after-sales-auto-gate');

function item(specCode, qtyGood, qtyBad = 0) {
  return { name: `商品${specCode}`, specCode, qty: qtyGood + qtyBad, qtyGood, qtyBad };
}

function makeCollectedData({ rows, sharedReturnGroup, multiUse = false }) {
  const normalizedRows = rows.map((row, index) => ({
    erpOrderId: `ERP-${index + 1}`,
    tracking: 'TRACK-SHARED',
    ...row,
  }));
  return {
    ticket: {
      subOrders: [{ id: 'SUB-A', afterSaleNum: 1 }],
      gifts: [],
      afterSaleReason: '七天无理由退货',
      returnTracking: 'TRACK-SHARED',
      returnTrackingMultiUse: multiUse || undefined,
      returnTrackingUsedBy: multiUse ? ['100001700000000000002'] : undefined,
    },
    erpAftersale: { tracking: 'TRACK-SHARED', rows: normalizedRows },
    productMatches: [{ subOrderId: 'SUB-A', specCode: 'A' }],
    productArchives: [{
      subOrderId: 'SUB-A',
      outerId: 'A',
      subItems: [{ name: '商品A', specCode: 'A', qty: 1 }],
    }],
    sharedReturnGroup,
    collectErrors: [],
  };
}

function infer(collectedData) {
  return inferDecision({
    id: 'sim-shared-return',
    workOrderNum: '100001700000000000001',
    collectedData,
  }, {
    type: '退货退款',
    workOrderNum: '100001700000000000001',
    hint: null,
  });
}

describe('退货退款共用退货单号', () => {
  it('非已收货行即使带商品明细也直接忽略', () => {
    const decision = infer(makeCollectedData({
      rows: [
        { goodsStatus: '空', returnQty: 0, items: [item('A', 9)] },
        { goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] },
      ],
    }));

    assert.equal(decision.action, 'approve');
    assert.doesNotMatch(decision.reason, /多8件|实退10件/);
  });

  it('相同主子订单的两个当前有效工单按两张申请数量合并核对', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 2, items: [item('A', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001', '100001700000000000002'],
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 2 }],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.match(decision.reason, /逐规格核对通过/);
  });

  it('历史关联工单已成功退款时先扣除历史占用，阻止同一批退货再次退款', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001'],
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 1 }],
        historicalConsumedItems: [{ specCode: 'A', name: '商品A', qty: 1 }],
        historicalWorkOrders: [{
          workOrderNum: '100001700000000000002',
          action: 'approve',
          executedAt: '2026-09-01T00:00:00.000Z',
          consumesReturnQty: true,
        }],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /本次可用0件/);
    assert.match(decision.reason, /历史已退款占用1件/);
  });

  it('历史关联工单未成功执行退款时不占用退货数量', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001'],
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 1 }],
        historicalConsumedItems: [],
        historicalWorkOrders: [{
          workOrderNum: '100001700000000000002',
          action: 'escalate',
          executedAt: null,
          consumesReturnQty: false,
        }],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.match(decision.reason, /逐规格核对通过/);
  });

  it('真实结构回归：18×2主品加同一套12件赠品，ERP实收48不得误报多18件', () => {
    const decision = infer(makeCollectedData({
      rows: [{
        goodsStatus: '卖家已收到退货',
        returnQty: 48,
        items: [item('MAIN', 36), item('GIFT', 12)],
      }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001', '100001700000000000002'],
        expectedItems: [
          { specCode: 'MAIN', name: '主品', qty: 36 },
          { specCode: 'GIFT', name: '赠品', qty: 12 },
        ],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.doesNotMatch(decision.reason, /多18件/);
    assert.match(decision.reason, /主品×36/);
    assert.match(decision.reason, /赠品×12/);
  });

  it('不同子订单共用单号时按合并后的逐规格数量核对', () => {
    const collectedData = makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 3, items: [item('A', 1), item('B', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001', '100001700000000000003'],
        expectedItems: [
          { specCode: 'A', name: '商品A', qty: 1 },
          { specCode: 'B', name: '商品B', qty: 2 },
        ],
      },
    });
    const decision = infer(collectedData);

    assert.equal(decision.action, 'approve');
    assert.match(decision.reason, /共用退货单/);
    assert.match(decision.reason, /逐规格核对通过/);
    assert.equal(decision.requiresHumanReview, true);
    assert.equal(decision.autoExecutionBlocked, true);
    assert.equal(decision.humanTriggeredExecutionAllowed, true);
    assert.equal(shouldAutoExecute(decision, collectedData, { type: '退货退款' }), false);
  });

  it('不同子订单合并核对后确认为多退时仍可同意，但明确提示多退', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 4, items: [item('A', 2), item('B', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001', '100001700000000000003'],
        expectedItems: [
          { specCode: 'A', name: '商品A', qty: 1 },
          { specCode: 'B', name: '商品B', qty: 2 },
        ],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.match(decision.reason, /确认多退/);
    assert.match(decision.warnings.join('；'), /商品A多1件/);
  });

  it('不同子订单合并后任一规格少退时转人工', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 2, items: [item('A', 1), item('B', 1)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        workOrderNums: ['100001700000000000001', '100001700000000000003'],
        expectedItems: [
          { specCode: 'A', name: '商品A', qty: 1 },
          { specCode: 'B', name: '商品B', qty: 2 },
        ],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /商品B.*本次可用1件，应退2件/);
  });

  it('不同子订单的关联数据不完整时转人工，但仍展示当前工单与ERP逐规格证据', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'incomplete',
        reason: '关联工单缺少商品档案',
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /关联工单缺少商品档案/);
    const evidence = (decision.steps || []).find(step => step.label === '当前工单 ↔ ERP逐规格对应');
    assert.ok(evidence);
    assert.match(evidence.value, /商品A\[A\]：当前工单应退1件、ERP良品1件/);
    const note = (decision.steps || []).find(step => step.label === '对应关系说明');
    assert.match(note && note.value, /不能据此单独判断多退、少退或是否应退款/);
  });

  it('共用退货单已收货行的 ERP 售后单号重复时转人工', () => {
    const decision = infer(makeCollectedData({
      rows: [
        { erpOrderId: 'ERP-DUP', goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] },
        { erpOrderId: 'ERP-DUP', goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] },
      ],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 2 }],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /ERP 售后单号ERP-DUP重复/);
  });

  it('共用退货单已收货行混入其他退货单号时转人工', () => {
    const decision = infer(makeCollectedData({
      rows: [
        { goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] },
        { tracking: 'OTHER-TRACKING', goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] },
      ],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 2 }],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /退货单号与工单不一致/);
  });

  it('共用退货单已收货行退回总数与商品明细不一致时转人工', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'combined_applications',
        expectedItems: [{ specCode: 'A', name: '商品A', qty: 2 }],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /退回总数与良品次品合计不一致/);
  });
});
