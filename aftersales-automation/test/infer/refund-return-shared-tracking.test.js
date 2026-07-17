'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

const { inferDecision } = require('../../lib/infer');

function item(specCode, qtyGood, qtyBad = 0) {
  return { name: `商品${specCode}`, specCode, qty: qtyGood + qtyBad, qtyGood, qtyBad };
}

function makeCollectedData({ rows, sharedReturnGroup, multiUse = false }) {
  return {
    ticket: {
      subOrders: [{ id: 'SUB-A', afterSaleNum: 1 }],
      gifts: [],
      afterSaleReason: '七天无理由退货',
      returnTracking: 'TRACK-SHARED',
      returnTrackingMultiUse: multiUse || undefined,
      returnTrackingUsedBy: multiUse ? ['100001700000000000002'] : undefined,
    },
    erpAftersale: { tracking: 'TRACK-SHARED', rows },
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

  it('相同子订单重新申请时忽略历史工单，不因多次使用转人工', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 1, items: [item('A', 1)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'same_suborders_only',
        ignoredWorkOrderNums: ['100001700000000000002'],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.doesNotMatch(decision.reason, /多个工单共用/);
  });

  it('不同子订单共用单号时按合并后的逐规格数量核对', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 3, items: [item('A', 1), item('B', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'distinct_suborders',
        workOrderNums: ['100001700000000000001', '100001700000000000003'],
        expectedItems: [
          { specCode: 'A', name: '商品A', qty: 1 },
          { specCode: 'B', name: '商品B', qty: 2 },
        ],
      },
    }));

    assert.equal(decision.action, 'approve');
    assert.match(decision.reason, /共用退货单/);
    assert.match(decision.reason, /逐规格核对通过/);
  });

  it('不同子订单合并核对后确认为多退时仍可同意，但明确提示多退', () => {
    const decision = infer(makeCollectedData({
      rows: [{ goodsStatus: '卖家已收到退货', returnQty: 4, items: [item('A', 2), item('B', 2)] }],
      multiUse: true,
      sharedReturnGroup: {
        mode: 'distinct_suborders',
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
        mode: 'distinct_suborders',
        workOrderNums: ['100001700000000000001', '100001700000000000003'],
        expectedItems: [
          { specCode: 'A', name: '商品A', qty: 1 },
          { specCode: 'B', name: '商品B', qty: 2 },
        ],
      },
    }));

    assert.equal(decision.action, 'escalate');
    assert.match(decision.reason, /商品B.*退了1件，应退2件/);
  });

  it('不同子订单的关联数据不完整时转人工', () => {
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
  });
});
