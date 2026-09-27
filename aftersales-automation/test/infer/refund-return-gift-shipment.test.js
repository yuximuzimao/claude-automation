'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { inferDecision } = require('../../lib/infer');

function collectedGiftReturn(rowOverrides = {}) {
  return {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '七天无理由退货',
      returnTracking: 'RETURN-1',
      subOrders: [{ id: 'MAIN-1', afterSaleNum: 1 }],
      gifts: [{ id: 'GIFT-1' }],
    },
    productArchives: [{
      subOrderId: 'MAIN-1',
      subItems: [{ name: '主商品', specCode: 'SPEC-MAIN', qty: 1 }],
    }],
    productMatches: [{ subOrderId: 'MAIN-1', matched: true }],
    giftProductArchive: {
      subItems: [{ name: '赠品', specCode: 'SPEC-GIFT', qty: 1 }],
    },
    giftErpSearches: [{
      subOrderId: 'GIFT-1',
      rows: {
        rows: [{
          status: '待打印快递单',
          tracking: null,
          trackings: [],
          ...rowOverrides,
        }],
      },
    }],
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-AFTER-1',
        tracking: 'RETURN-1',
        goodsStatus: '卖家已收到退货',
        returnQty: 1,
        items: [{ name: '主商品', specCode: 'SPEC-MAIN', qtyGood: 1, qtyBad: 0 }],
      }],
    },
    collectErrors: [],
  };
}

function infer(collectedData) {
  return inferDecision(
    { mode: 'live', collectedData },
    { type: '退货退款', source: 'scan' },
  );
}

test('赠品待打印快递单且无单号时视为未发货，不要求客户退回赠品', () => {
  const decision = infer(collectedGiftReturn());

  assert.equal(decision.action, 'approve');
  assert.doesNotMatch(decision.reason, /赠品|SPEC-GIFT|退货数量不足/);
  assert.ok(decision.steps.some(step =>
    step.condition === '赠品是否实际发出' && String(step.result).includes('否（待打印快递单，无快递单号）')
  ));
});

test('赠品待打印但已有快递单号时不能按未发货排除，缺少赠品仍上报', () => {
  const decision = infer(collectedGiftReturn({
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  }));

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /赠品|退货里没有|退货数量不足/);
});

test('赠品已发货状态即使无单号也不能按明确未发货排除', () => {
  const decision = infer(collectedGiftReturn({ status: '卖家已发货' }));

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /赠品|退货里没有|退货数量不足/);
});

test('多个赠品子订单只查到其中一个时不得把全部赠品判成未发货', () => {
  const data = collectedGiftReturn();
  data.ticket.gifts.push({ id: 'GIFT-2' });
  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.equal(decision.steps.some(step => step.condition === '赠品是否实际发出'), false);
  assert.match(decision.reason, /赠品|退货里没有|退货数量不足/);
});
