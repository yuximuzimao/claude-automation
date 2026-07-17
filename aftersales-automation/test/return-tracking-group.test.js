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
