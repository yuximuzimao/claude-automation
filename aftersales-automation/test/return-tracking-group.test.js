'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { resolveSharedReturnGroup } = require('../lib/return-tracking-group');

function archive(subOrderId, specCode, qty) {
  return {
    subOrderId,
    outerId: specCode,
    subItems: [{ name: `商品${specCode}`, specCode, qty }],
  };
}

function collected({ workOrderNum, subOrderId, tracking = 'TRACK-1', usedBy, qty = 1 }) {
  return {
    ticket: {
      workOrderNum,
      returnTracking: tracking,
      returnTrackingMultiUse: Boolean(usedBy),
      returnTrackingUsedBy: usedBy,
      subOrders: [{ id: subOrderId, afterSaleNum: 1 }],
      gifts: [],
    },
    productArchives: [archive(subOrderId, `SPEC-${subOrderId}`, qty)],
    collectErrors: [],
  };
}

test('平台没有重复使用提示时，不从历史退货单号主动建立关联', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1' });
  const simulations = [{
    workOrderNum: 'WO-2',
    collectedData: collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2' }),
  }];

  assert.equal(resolveSharedReturnGroup(current, simulations), null);
});

test('平台提示的关联工单没有完整记录时转人工', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-MISSING'] });

  assert.deepEqual(resolveSharedReturnGroup(current, []), {
    mode: 'incomplete',
    reason: '平台提示关联工单 WO-MISSING，但系统没有该工单的完整采集记录',
    missingWorkOrderNums: ['WO-MISSING'],
  });
});

test('平台关联工单使用相同子订单时只算当前申请', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]), {
    mode: 'same_suborders_only',
    ignoredWorkOrderNums: ['WO-2'],
  });
});

test('相同子订单的历史记录无需商品档案和退货单号也不参与累计', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  delete previous.ticket.returnTracking;
  previous.productArchives = [];

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]), {
    mode: 'same_suborders_only',
    ignoredWorkOrderNums: ['WO-2'],
  });
});

test('关联工单同时包含重复和新增子订单时不得整单忽略，必须转人工', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  previous.ticket.subOrders.push({ id: 'SUB-2', afterSaleNum: 1 });
  previous.productArchives.push(archive('SUB-2', 'SPEC-SUB-2', 1));

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]), {
    mode: 'incomplete',
    reason: '关联工单 WO-2 同时包含已计入和未计入的子订单，无法安全拆分应退数量',
  });
});

test('平台关联工单使用不同子订单时合并逐规格应退数量', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'], qty: 1 });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2', qty: 2 });

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]), {
    mode: 'distinct_suborders',
    workOrderNums: ['WO-1', 'WO-2'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
      { specCode: 'SPEC-SUB-2', name: '商品SPEC-SUB-2', qty: 2 },
    ],
  });
});

test('关联工单主品申请数量缺失、为零或非法时不得默认按一件汇总', () => {
  for (const invalidQty of [undefined, 0, '未知']) {
    const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
    const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2' });
    previous.ticket.subOrders[0].afterSaleNum = invalidQty;

    const result = resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]);
    assert.equal(result.mode, 'incomplete');
    assert.match(result.reason, /缺少有效退货数量/);
  }
});

test('赠品按商品档案的一份数量汇总，不读取赠品 afterSaleNum 放大数量', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2' });
  previous.ticket.gifts = [{ id: 'GIFT-2', afterSaleNum: 9 }];
  previous.giftProductArchive = archive('GIFT-2', 'SPEC-GIFT', 1);

  const result = resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]);
  assert.equal(result.mode, 'distinct_suborders');
  assert.deepEqual(result.expectedItems.find(item => item.specCode === 'SPEC-GIFT'), {
    specCode: 'SPEC-GIFT',
    name: '商品SPEC-GIFT',
    qty: 1,
  });
});

test('链式关联 A→B→C 时遍历完整关联组，不得只汇总直接关联的 A+B', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const second = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2', usedBy: ['WO-1', 'WO-3'] });
  const third = collected({ workOrderNum: 'WO-3', subOrderId: 'SUB-3', usedBy: ['WO-2'] });

  assert.deepEqual(resolveSharedReturnGroup(current, [
    { workOrderNum: 'WO-2', collectedData: second },
    { workOrderNum: 'WO-3', collectedData: third },
  ]), {
    mode: 'distinct_suborders',
    workOrderNums: ['WO-1', 'WO-2', 'WO-3'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
      { specCode: 'SPEC-SUB-2', name: '商品SPEC-SUB-2', qty: 1 },
      { specCode: 'SPEC-SUB-3', name: '商品SPEC-SUB-3', qty: 1 },
    ],
  });
});
