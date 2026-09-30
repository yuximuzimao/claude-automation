'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { inferDecision } = require('../../lib/infer');

function makeCollectedData() {
  return {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '七天无理由退货',
      returnTracking: 'RETURN-MULTI',
      subOrders: [
        { id: 'SUB-SPRAY', afterSaleNum: 4 },
        { id: 'SUB-SET', afterSaleNum: 1 },
      ],
      gifts: [],
    },
    productArchives: [
      {
        subOrderId: 'SUB-SPRAY',
        subItems: [{ name: '保湿喷雾2.0', specCode: 'SPEC-SPRAY', qty: 1 }],
      },
      {
        subOrderId: 'SUB-SET',
        subItems: [{ name: '悦希修颜礼盒', specCode: 'SPEC-BOX', qty: 2 }],
      },
    ],
    productMatches: [
      { subOrderId: 'SUB-SPRAY', matched: true },
      { subOrderId: 'SUB-SET', matched: true },
    ],
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-AFTER-MULTI',
        tracking: 'RETURN-MULTI',
        goodsStatus: '卖家已收到退货',
        returnQty: 6,
        items: [
          { name: '保湿喷雾2.0', specCode: 'SPEC-SPRAY', qtyGood: 4, qtyBad: 0 },
          { name: '悦希修颜礼盒', specCode: 'SPEC-BOX', qtyGood: 2, qtyBad: 0 },
        ],
      }],
    },
    collectErrors: [],
  };
}

function infer(collectedData) {
  return inferDecision(
    { mode: 'live', collectedData, workOrderNum: '100001790500355965114' },
    { type: '退货退款', source: 'scan' },
  );
}

test('多个主子订单分别使用自己的 afterSaleNum 计算应退数量', () => {
  const decision = infer(makeCollectedData());

  assert.equal(decision.action, 'approve');

  const sprayStep = decision.steps.find(step => step.condition === '保湿喷雾2.0');
  const setStep = decision.steps.find(step => step.condition === '悦希修颜礼盒');

  assert.ok(sprayStep);
  assert.ok(setStep);
  assert.match(String(sprayStep.result), /期望4件，入库4件/);
  assert.match(String(setStep.result), /期望2件，入库2件/);
});

test('多主子订单的商品档案缺少子订单归属时禁止猜测倍数', () => {
  const data = makeCollectedData();
  delete data.productArchives[1].subOrderId;

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /主商品数量归属不完整/);
  assert.match(decision.reason, /afterSaleNum/);
});
