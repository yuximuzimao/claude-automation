'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { proveReturnItems } = require('../lib/return-item-proof');

function collected(overrides = {}) {
  return {
    ticket: {
      returnTracking: 'RETURN-1',
      subOrders: [{ id: 'main-1', afterSaleNum: 1 }],
      gifts: [{ id: 'gift-1' }],
      ...overrides.ticket,
    },
    productArchives: [{
      subOrderId: 'main-1',
      subItems: [{ name: '商品A', specCode: 'SPEC-A', qty: 1 }],
    }],
    giftProductArchive: {
      subItems: [{ name: '商品A', specCode: 'SPEC-A', qty: 1 }],
    },
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-1',
        tracking: 'RETURN-1',
        goodsStatus: '卖家已收到退货',
        returnQty: 2,
        items: [{ name: '商品A', specCode: 'SPEC-A', qtyGood: 2, qtyBad: 0 }],
      }],
    },
    ...overrides,
  };
}

test('主品和赠品为同规格时合并应退数量，数量相等才是精确退回', () => {
  const proof = proveReturnItems(collected());

  assert.equal(proof.outcome, 'exact');
  assert.equal(proof.mainOutcome, 'exact');
  assert.equal(proof.giftOutcome, 'exact');
  assert.deepEqual(proof.expectedBySpec, { 'SPEC-A': 2 });
  assert.deepEqual(proof.receivedGoodBySpec, { 'SPEC-A': 2 });
});

test('实退少于主品加赠品应退数量时是少退', () => {
  const data = collected();
  data.erpAftersale.rows[0].items[0].qtyGood = 1;
  data.erpAftersale.rows[0].returnQty = 1;

  assert.equal(proveReturnItems(data).outcome, 'short');
});

test('实退多于应退数量时是独立的真实多退结果', () => {
  const data = collected();
  data.erpAftersale.rows[0].items[0].qtyGood = 3;
  data.erpAftersale.rows[0].returnQty = 3;

  assert.equal(proveReturnItems(data).outcome, 'excess');
});

test('任一已收货规格存在次品时固定为次品结果', () => {
  const data = collected();
  data.erpAftersale.rows[0].items[0].qtyBad = 1;
  data.erpAftersale.rows[0].returnQty = 3;

  assert.equal(proveReturnItems(data).outcome, 'damaged');
});

test('ERP 已收货行出现应退清单外的规格时是未匹配商品', () => {
  const data = collected();
  data.erpAftersale.rows[0].items.push({ name: '未知商品', specCode: 'SPEC-X', qtyGood: 1, qtyBad: 0 });
  data.erpAftersale.rows[0].returnQty = 3;

  assert.equal(proveReturnItems(data).outcome, 'unmatched');
});

test('非“卖家已收到退货”行即使带商品明细也必须忽略', () => {
  const data = collected();
  data.erpAftersale.rows.push({
    goodsStatus: '待拆包',
    items: [{ name: '未知商品', specCode: 'SPEC-X', qtyGood: 99, qtyBad: 0 }],
  });

  assert.equal(proveReturnItems(data).outcome, 'exact');
});

test('现有免退包装耗材不计入应退规格', () => {
  const data = collected();
  data.productArchives[0].subItems.push(
    { name: 'HEE悦希印花礼袋-白', specCode: 'BAG', qty: 1 },
    { name: 'HEE悦希雪梨纸', specCode: 'PAPER', qty: 1 },
    { name: 'HEE悦希印花礼盒（天地盖）白色', specCode: 'BOX', qty: 1 },
  );

  assert.equal(proveReturnItems(data).outcome, 'exact');
});

test('多个赠品子订单但只有单个赠品档案时证据不完整', () => {
  const data = collected({
    ticket: {
      subOrders: [{ id: 'main-1', afterSaleNum: 1 }],
      gifts: [{ id: 'gift-1' }, { id: 'gift-2' }],
    },
  });

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /多个赠品子订单/);
});

test('缺少退货单号时严格证明不完整', () => {
  const data = collected();
  delete data.ticket.returnTracking;

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /退货单号/);
});

test('ERP 已收货行缺少商品明细时严格证明不完整', () => {
  const data = collected();
  data.erpAftersale.rows[0].items = [];

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /商品明细/);
});

test('ERP 行退回总数与良品次品合计不一致时严格证明不完整', () => {
  const data = collected();
  data.erpAftersale.rows[0].returnQty = 3;

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /退回总数/);
});

test('赠品明确申请退多件时使用自己的退货数量', () => {
  const data = collected();
  data.ticket.gifts[0].afterSaleNum = 2;

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'short');
  assert.deepEqual(proof.expectedBySpec, { 'SPEC-A': 3 });
});

test('ERP 已收货行单号冲突或售后单号重复时严格证明不完整', () => {
  const trackingConflict = collected();
  trackingConflict.erpAftersale.rows[0].tracking = 'OTHER-RETURN';
  assert.equal(proveReturnItems(trackingConflict).outcome, 'incomplete');

  const duplicate = collected();
  duplicate.erpAftersale.rows.push({ ...duplicate.erpAftersale.rows[0] });
  const proof = proveReturnItems(duplicate);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /重复/);
});

test('存在任何采集错误时严格证明不完整', () => {
  const data = collected({ collectErrors: ['product-match: 页面读取异常'] });

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /采集错误/);
});

test('应退档案或入库商品缺少规格编码时证据不完整', () => {
  const data = collected();
  data.erpAftersale.rows[0].items[0].specCode = '';

  const proof = proveReturnItems(data);
  assert.equal(proof.outcome, 'incomplete');
  assert.match(proof.missingFacts.join('；'), /规格编码/);
});
