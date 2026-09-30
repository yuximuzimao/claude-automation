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

test('同一规格分散在多个已入库行时合计数量，未入库行不计数', () => {
  const data = makeCollectedData();
  data.ticket.subOrders = [
    { id: 'SUB-OIL-3', afterSaleNum: 1 },
    { id: 'SUB-OIL-1', afterSaleNum: 1 },
  ];
  data.productArchives = [
    {
      subOrderId: 'SUB-OIL-3',
      subItems: [{ name: '慕斯油150ml', specCode: 'SPEC-OIL', qty: 3 }],
    },
    {
      subOrderId: 'SUB-OIL-1',
      subItems: [{ name: '慕斯油150ml', specCode: 'SPEC-OIL', qty: 1 }],
    },
  ];
  data.productMatches = [
    { subOrderId: 'SUB-OIL-3', matched: true },
    { subOrderId: 'SUB-OIL-1', matched: true },
  ];
  data.erpAftersale.rows = [
    {
      erpOrderId: 'ERP-OIL-A',
      tracking: 'RETURN-MULTI',
      goodsStatus: '卖家已收到退货\n多收货',
      returnQty: 2,
      items: [{ name: '慕斯油150ml', specCode: 'SPEC-OIL', qtyGood: 2, qtyBad: 0 }],
    },
    {
      erpOrderId: 'ERP-OIL-B',
      tracking: 'RETURN-MULTI',
      goodsStatus: '卖家已收到退货\n商品无误',
      returnQty: 3,
      items: [{ name: '慕斯油150ml', specCode: 'SPEC-OIL', qtyGood: 3, qtyBad: 0 }],
    },
    {
      erpOrderId: 'ERP-OIL-NOT-RECEIVED',
      tracking: 'RETURN-MULTI',
      goodsStatus: '待收货',
      returnQty: 100,
      items: [{ name: '慕斯油150ml', specCode: 'SPEC-OIL', qtyGood: 100, qtyBad: 0 }],
    },
  ];

  const decision = infer(data);

  assert.equal(decision.action, 'approve');
  const oilStep = decision.steps.find(step => step.condition === '慕斯油150ml');
  assert.ok(oilStep);
  assert.match(String(oilStep.result), /期望4件，入库5件/);
  assert.match(decision.reason, /实退5件/);
  assert.doesNotMatch(decision.reason, /105/);
});

test('多主子订单的商品档案缺少子订单归属时禁止猜测倍数', () => {
  const data = makeCollectedData();
  delete data.productArchives[1].subOrderId;

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /主商品数量归属不完整/);
  assert.match(decision.reason, /afterSaleNum/);
});
