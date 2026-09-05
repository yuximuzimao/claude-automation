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
    reason: '平台提示关联工单 WO-MISSING 仍在当前48小时批次，但本轮尚未采集完整',
    missingWorkOrderNums: ['WO-MISSING'],
  });
});

test('相同主子订单的两个当前有效工单都累计申请数量', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const related = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: related }]), {
    mode: 'combined_applications',
    workOrderNums: ['WO-1', 'WO-2'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 2 },
    ],
  });
});

test('历史关联工单未执行同意退款时不占用当前退货数量', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const historical = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  delete historical.ticket.returnTracking;
  historical.productArchives = [];

  assert.deepEqual(resolveSharedReturnGroup(
    current,
    [{ workOrderNum: 'WO-2', collectedData: historical, decision: { action: 'escalate' } }],
    'WO-1',
    { activeWorkOrderNums: new Set(['WO-1']), freshWorkOrderNums: new Set(['WO-1']) }
  ), {
    mode: 'combined_applications',
    workOrderNums: ['WO-1'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
    ],
    historicalConsumedItems: [],
    historicalWorkOrders: [{
      workOrderNum: 'WO-2',
      action: 'escalate',
      executedAt: null,
      consumesReturnQty: false,
    }],
  });
});

test('历史关联工单已执行同意退款时按该历史工单自己的数量占用退货实物', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const historical = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });

  const result = resolveSharedReturnGroup(
    current,
    [{
      workOrderNum: 'WO-2',
      collectedData: historical,
      decision: { action: 'approve' },
      executedAt: '2026-09-01T00:00:00.000Z',
    }],
    'WO-1',
    { activeWorkOrderNums: new Set(['WO-1']), freshWorkOrderNums: new Set(['WO-1']) }
  );

  assert.deepEqual(result.expectedItems, [
    { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
  ]);
  assert.deepEqual(result.historicalConsumedItems, [
    { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
  ]);
  assert.deepEqual(result.historicalWorkOrders, [{
    workOrderNum: 'WO-2',
    action: 'approve',
    executedAt: '2026-09-01T00:00:00.000Z',
    consumesReturnQty: true,
  }]);
});

test('历史工单后续出现未执行快照时仍优先保留曾经真实执行同意退款的占用证据', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const historical = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  const laterSnapshot = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });

  const result = resolveSharedReturnGroup(
    current,
    [
      {
        workOrderNum: 'WO-2',
        collectedData: historical,
        decision: { action: 'approve' },
        executedAt: '2026-09-01T00:00:00.000Z',
      },
      {
        workOrderNum: 'WO-2',
        collectedData: laterSnapshot,
        decision: { action: 'escalate' },
        createdAt: '2026-09-02T00:00:00.000Z',
      },
    ],
    'WO-1',
    { activeWorkOrderNums: new Set(['WO-1']), freshWorkOrderNums: new Set(['WO-1']) }
  );

  assert.deepEqual(result.historicalConsumedItems, [
    { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
  ]);
  assert.equal(result.historicalWorkOrders[0].consumesReturnQty, true);
});

test('平台点名的关联工单既不在当前48小时批次、历史也找不到时转人工并显示缺失工单号', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-MISSING'] });

  assert.deepEqual(resolveSharedReturnGroup(
    current,
    [],
    'WO-1',
    { activeWorkOrderNums: new Set(['WO-1']), freshWorkOrderNums: new Set(['WO-1']) }
  ), {
    mode: 'incomplete',
    reason: '平台提示关联工单 WO-MISSING，但本轮48小时采集与历史记录均未找到；可能为历史记录缺失或特殊重复申请，需人工判断',
    missingWorkOrderNums: ['WO-MISSING'],
    missingHistoricalWorkOrderNums: ['WO-MISSING'],
  });
});

test('关联工单同时包含相同和新增主子订单时全部按工单申请量累计', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const related = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  related.ticket.subOrders.push({ id: 'SUB-2', afterSaleNum: 1 });
  related.productArchives.push(archive('SUB-2', 'SPEC-SUB-2', 1));

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: related }]), {
    mode: 'combined_applications',
    workOrderNums: ['WO-1', 'WO-2'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 2 },
      { specCode: 'SPEC-SUB-2', name: '商品SPEC-SUB-2', qty: 1 },
    ],
  });
});

test('平台关联工单使用不同子订单时合并逐规格应退数量', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'], qty: 1 });
  const previous = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2', qty: 2 });

  assert.deepEqual(resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: previous }]), {
    mode: 'combined_applications',
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
  assert.equal(result.mode, 'combined_applications');
  assert.deepEqual(result.expectedItems.find(item => item.specCode === 'SPEC-GIFT'), {
    specCode: 'SPEC-GIFT',
    name: '商品SPEC-GIFT',
    qty: 1,
  });
});

test('多个当前有效工单重复显示同一赠品子订单时只累计一套赠品', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const related = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-1' });
  current.ticket.gifts = [{ id: 'GIFT-SHARED' }];
  current.giftProductArchive = archive('GIFT-SHARED', 'SPEC-GIFT', 12);
  related.ticket.gifts = [{ id: 'GIFT-SHARED' }];
  related.giftProductArchive = archive('GIFT-SHARED', 'SPEC-GIFT', 12);

  const result = resolveSharedReturnGroup(current, [{ workOrderNum: 'WO-2', collectedData: related }]);
  assert.equal(result.mode, 'combined_applications');
  assert.deepEqual(result.expectedItems, [
    { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 2 },
    { specCode: 'SPEC-GIFT', name: '商品SPEC-GIFT', qty: 12 },
  ]);
});

test('链式关联 A→B→C 时遍历完整关联组，不得只汇总直接关联的 A+B', () => {
  const current = collected({ workOrderNum: 'WO-1', subOrderId: 'SUB-1', usedBy: ['WO-2'] });
  const second = collected({ workOrderNum: 'WO-2', subOrderId: 'SUB-2', usedBy: ['WO-1', 'WO-3'] });
  const third = collected({ workOrderNum: 'WO-3', subOrderId: 'SUB-3', usedBy: ['WO-2'] });

  assert.deepEqual(resolveSharedReturnGroup(current, [
    { workOrderNum: 'WO-2', collectedData: second },
    { workOrderNum: 'WO-3', collectedData: third },
  ]), {
    mode: 'combined_applications',
    workOrderNums: ['WO-1', 'WO-2', 'WO-3'],
    expectedItems: [
      { specCode: 'SPEC-SUB-1', name: '商品SPEC-SUB-1', qty: 1 },
      { specCode: 'SPEC-SUB-2', name: '商品SPEC-SUB-2', qty: 1 },
      { specCode: 'SPEC-SUB-3', name: '商品SPEC-SUB-3', qty: 1 },
    ],
  });
});
