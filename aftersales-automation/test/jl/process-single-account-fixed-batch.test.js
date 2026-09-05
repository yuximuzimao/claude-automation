'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  clickPageOneLikeHuman,
  createWaitForPage,
  createCircuitReader,
  createAutoExecutionGate,
  buildMissingWaitingRescanProcessed,
  createReconcileWaitingRescanAbsences,
  loadDefaultDependencies,
  resolveSharedReturnGroupForBatch,
  locateWorkOrderOnFreshList,
  processOpenedDetail,
  processOpenedDetailAndPersist,
  processSingleAccountFixedBatch,
  closeAndVerifyDetailTarget,
  cleanupCurrentAccountJlTargets,
  statusForProcessed,
  buildSimulationPayload,
  createEnsureQueueItem,
  runCli,
} = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
const {
  createAutoExecutionJournal,
  STATUS,
  UNFINISHED_INTENT_BLOCK_REASON,
  EXECUTED_BLOCK_REASON,
} = require('../../lib/server/auto-execution-journal');
const { resolveSharedReturnGroup } = require('../../lib/return-tracking-group');

const ORDER_1 = '100001781188621717210';
const ORDER_2 = '100001781188621717211';

test('完整48小时清单缺失的自动等待重查项转待确认，不按扫描间隔判逾期', async () => {
  const missingOrder = '100001781188621717212';
  const otherAccountOrder = '100001781188621717213';
  const manuallyWaitingOrder = '100001781188621717214';
  const queue = {
    items: [
      { id: 'q-present', workOrderNum: ORDER_1, accountNum: '3', mode: 'live', status: 'waiting', waitingRescan: true },
      { id: 'q-missing', workOrderNum: missingOrder, accountNum: 3, mode: 'live', status: 'waiting', waitingRescan: true, type: '退货退款' },
      { id: 'q-other', workOrderNum: otherAccountOrder, accountNum: '4', mode: 'live', status: 'waiting', waitingRescan: true },
      { id: 'q-manual', workOrderNum: manuallyWaitingOrder, accountNum: '3', mode: 'live', status: 'waiting', waitingRescan: false },
    ],
  };
  const previousSimulation = {
    id: 'sim-previous',
    queueItemId: 'q-missing',
    collectedData: {
      ticket: { workOrderNum: missingOrder, type: '退货退款', returnTracking: 'YT1234567890123' },
      erpAftersale: { rows: [] },
    },
    decision: { action: 'reject', waitingRescan: true },
  };
  const simulations = [previousSimulation];
  const db = {
    readQueue: () => queue,
    readSimulations: () => simulations,
    appendSimulation: simulation => simulations.push(simulation),
    updateQueueItem: (id, patch) => {
      const item = queue.items.find(candidate => candidate.id === id);
      if (!item) return null;
      Object.assign(item, patch);
      return item;
    },
  };
  const reconcile = createReconcileWaitingRescanAbsences(db);
  const observedAt = '2026-08-15T00:00:00.000Z';
  const result = await reconcile({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    snapshot: [{ workOrderNum: ORDER_1 }],
    observedAt,
  });

  assert.equal(result.length, 1);
  assert.equal(result[0].workOrderNum, missingOrder);
  assert.equal(queue.items.find(item => item.id === 'q-missing').status, 'simulated');
  assert.equal(queue.items.find(item => item.id === 'q-missing').waitingRescan, false);
  assert.equal(queue.items.find(item => item.id === 'q-present').status, 'waiting');
  assert.equal(queue.items.find(item => item.id === 'q-other').status, 'waiting');
  assert.equal(queue.items.find(item => item.id === 'q-manual').status, 'waiting');

  const anomaly = simulations.at(-1);
  assert.equal(anomaly.source, 'waiting_rescan_missing');
  assert.equal(anomaly.decision.action, 'escalate');
  assert.equal(anomaly.decision.reasonCode, 'WAITING_RESCAN_MISSING_FROM_48H_LIST');
  assert.equal(anomaly.decision.humanTriggeredExecutionAllowed, false);
  assert.equal(anomaly.collectedData.ticket.returnTracking, 'YT1234567890123');
  assert.deepEqual(anomaly.collectedData.erpAftersale, { rows: [] });
  assert.deepEqual(anomaly.collectedData.waitingRescanAbsence, {
    observedAt,
    source: 'fixed_batch_48h_reconciliation',
    previousSimulationId: 'sim-previous',
  });

  const second = await reconcile({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    snapshot: [{ workOrderNum: ORDER_1 }],
    observedAt: '2026-08-15T08:00:00.000Z',
  });
  assert.deepEqual(second, []);
  assert.equal(simulations.length, 2);
});

test('等待重查缺失结果明确表示无法确认平台终态', () => {
  const processed = buildMissingWaitingRescanProcessed(
    { id: 'q-1', workOrderNum: ORDER_1 },
    null,
    '2026-08-15T00:00:00.000Z'
  );
  assert.equal(processed.status, 'simulated');
  assert.match(processed.decision.reason, /未出现于本次完整48小时清单/);
  assert.match(processed.decision.warnings.join('；'), /不能据此推断工单已关闭/);
  assert.equal(processed.decision.requiresHumanReview, true);
  assert.equal(processed.decision.autoExecutionBlocked, true);
});

function page(currentPage, tickets, options = {}) {
  return {
    tickets,
    pagination: {
      totalCount: options.totalCount == null ? tickets.length : options.totalCount,
      currentPage,
      pages: options.pages || [
        { text: '1', active: currentPage === 1 },
      ],
      hasNext: Boolean(options.hasNext),
      reason: options.reason || (options.hasNext ? null : '下一页按钮已禁用'),
      nextButton: { visible: true, disabled: !options.hasNext },
    },
  };
}

function batchDependencies(overrides = {}) {
  const calls = [];
  let targets = ['list-tab'];
  const urgent = [
    { workOrderNum: ORDER_1, type: '仅退款', meta: { value: 1 } },
    { workOrderNum: ORDER_2, type: '退货退款', meta: { value: 2 } },
  ];
  const dependencies = {
    openAccountFlow: async accountNum => ({ success: true, accountNum, targetId: 'list-tab', matchedNote: '测试店铺' }),
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: { urgent, totalCount: 21, complete: true },
    }),
    locateWorkOrder: async (_targetId, workOrderNum) => ({ found: true, workOrderNum }),
    clickWorkOrderAction: async workOrderNum => {
      const detailTargetId = `detail-${workOrderNum}`;
      targets.push(detailTargetId);
      calls.push(['open', workOrderNum, detailTargetId]);
      return { success: true, newTargetId: detailTargetId };
    },
    collectDetail: async ({ detailTargetId, ticket }) => ({
      ticket: { workOrderNum: ticket.workOrderNum },
      detailTargetId,
    }),
    inferDecision: (collectedData, ticket) => ({
      action: ticket.workOrderNum === ORDER_1 ? 'approve' : 'manual',
      collectedData,
    }),
    shouldAutoExecute: decision => decision.action === 'approve',
    assertBatchAllowed: async () => ({ allowed: true }),
    reserveAutoExecution: async () => ({ reserved: true }),
    markAutoExecuted: async () => ({ executed: true }),
    ensureQueueItem: async ({ ticket }) => {
      const queueItem = { id: `q-${ticket.workOrderNum}`, workOrderNum: ticket.workOrderNum, status: 'pending' };
      calls.push(['ensureQueueItem', ticket.workOrderNum, queueItem.id]);
      return queueItem;
    },
    persistOutcome: async ({ ticket, processed }) => {
      calls.push(['persistOutcome', ticket.workOrderNum, processed.status, processed.decision && processed.decision.action]);
      return { id: `sim-${ticket.workOrderNum}` };
    },
    executeDecision: async ({ detailTargetId, ticket }) => {
      calls.push(['execute', ticket.workOrderNum, detailTargetId]);
      return { success: true, action: 'approve' };
    },
    sleep: async () => {},
    closeTarget: async targetId => {
      calls.push(['close', targetId]);
      targets = targets.filter(id => id !== targetId);
      return { closed: true, targetId };
    },
    getTargets: async () => targets.map(id => ({
      id,
      type: 'page',
      url: id === 'list-tab'
        ? 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list'
        : `https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=${id.replace(/^detail-/, '')}`,
    })),
    readShopName: async () => ({ success: true, state: 'logged-in', shopName: '测试店铺' }),
    onProgress: async progress => calls.push(['progress', progress.workOrderNum, progress.status]),
    ...overrides,
  };
  return { dependencies, calls, urgent, getTargets: () => targets.slice() };
}

test('冻结首次48小时清单，并严格按快照顺序逐单处理', async () => {
  const fixture = batchDependencies();
  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  fixture.urgent.reverse();
  fixture.urgent[0].meta.value = 99;

  assert.deepEqual(result.snapshot.map(item => item.workOrderNum), [ORDER_1, ORDER_2]);
  assert.deepEqual(result.snapshot.map(item => item.meta.value), [1, 2]);
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'open').map(call => call[1]),
    [ORDER_1, ORDER_2]
  );
  assert.deepEqual(result.items.map(item => item.status), ['auto_executed', 'simulated']);
  assert.deepEqual(fixture.getTargets(), ['list-tab']);
});

test('平台提示重复退货单时，先解析关联工单再进行推理', async () => {
  const calls = [];
  const collectedData = {
    ticket: {
      workOrderNum: ORDER_1,
      returnTrackingMultiUse: true,
      returnTrackingUsedBy: [ORDER_2],
    },
  };
  const result = await processOpenedDetail({
    ticket: { workOrderNum: ORDER_1 },
    queueItem: { workOrderNum: ORDER_1 },
    disableAutoExecute: true,
  }, {
    collectDetail: async () => collectedData,
    resolveSharedReturnGroup: async data => {
      calls.push(['resolve', data.ticket.workOrderNum]);
      return { mode: 'combined_applications', workOrderNums: [ORDER_1, ORDER_2], expectedItems: [] };
    },
    inferDecision: async data => {
      calls.push(['infer', data.sharedReturnGroup.mode]);
      return { action: 'approve' };
    },
  });

  assert.equal(result.status, 'simulated');
  assert.deepEqual(calls, [
    ['resolve', ORDER_1],
    ['infer', 'combined_applications'],
  ]);
});

test('仅退款物流异常时先做百度补证，再用补证后的采集数据重新推理', async () => {
  const calls = [];
  const collectedData = {
    ticket: { workOrderNum: ORDER_1 },
  };
  const result = await processOpenedDetail({
    ticket: { workOrderNum: ORDER_1, type: '仅退款' },
    queueItem: { workOrderNum: ORDER_1, type: '仅退款' },
    disableAutoExecute: true,
  }, {
    collectDetail: async () => collectedData,
    inferDecision: async data => {
      calls.push(['infer', Boolean(data.externalLogistics)]);
      return data.externalLogistics
        ? { action: 'approve', reason: '百度补证后已退回' }
        : { action: 'escalate', reason: '赠品未退回', rulesApplied: [{ doc: 'flow-5.3', section: 'Step3-gift' }] };
    },
    supplementExternalLogistics: async (data, decision) => {
      calls.push(['baidu', decision.action]);
      data.externalLogistics = {
        source: 'baidu',
        attemptedTrackings: ['YT7641388739489'],
        results: [{ tracking: 'YT7641388739489', status: 'returned', confirmedReturn: true }],
        errors: [],
      };
      return { attempted: true, changed: true };
    },
  });

  assert.equal(result.status, 'simulated');
  assert.equal(result.decision.action, 'approve');
  assert.deepEqual(calls, [
    ['infer', false],
    ['baidu', 'escalate'],
    ['infer', true],
  ]);
});

test('关联工单在当前批次尚未重采时屏蔽旧 simulation，避免第一张使用过期数据', () => {
  const current = {
    ticket: {
      workOrderNum: ORDER_1,
      returnTracking: 'TRACK-SHARED',
      returnTrackingMultiUse: true,
      returnTrackingUsedBy: [ORDER_2],
      subOrders: [{ id: 'SUB-1', afterSaleNum: 1 }],
      gifts: [],
    },
    productArchives: [{
      subOrderId: 'SUB-1',
      subItems: [{ name: '商品1', specCode: 'SPEC-1', qty: 1 }],
    }],
  };
  const staleRelated = {
    workOrderNum: ORDER_2,
    collectedData: {
      ticket: {
        workOrderNum: ORDER_2,
        returnTracking: 'TRACK-SHARED',
        subOrders: [{ id: 'STALE-SUB', afterSaleNum: 1 }],
        gifts: [],
      },
      productArchives: [{
        subOrderId: 'STALE-SUB',
        subItems: [{ name: '旧商品', specCode: 'STALE-SPEC', qty: 9 }],
      }],
    },
  };
  const context = {
    batchWorkOrderNums: new Set([ORDER_1, ORDER_2]),
    collectedDataByWorkOrder: new Map([[ORDER_1, current]]),
  };

  assert.deepEqual(
    resolveSharedReturnGroupForBatch(current, [staleRelated], ORDER_1, context),
    {
      mode: 'incomplete',
      reason: `平台提示关联工单 ${ORDER_2} 仍在当前48小时批次，但本轮尚未采集完整`,
      missingWorkOrderNums: [ORDER_2],
    }
  );
});

test('同批次关联工单第一张先到时延迟到组齐后回算，不受处理顺序影响', async () => {
  const fixture = batchDependencies();
  const inferGroups = [];
  const subOrders = {
    [ORDER_1]: 'SUB-1',
    [ORDER_2]: 'SUB-2',
  };

  fixture.dependencies.collectDetail = async ({ ticket }) => {
    const other = ticket.workOrderNum === ORDER_1 ? ORDER_2 : ORDER_1;
    const subOrderId = subOrders[ticket.workOrderNum];
    return {
      ticket: {
        workOrderNum: ticket.workOrderNum,
        returnTracking: 'TRACK-SHARED',
        returnTrackingMultiUse: true,
        returnTrackingUsedBy: [other],
        subOrders: [{ id: subOrderId, afterSaleNum: 1 }],
        gifts: [],
      },
      productArchives: [{
        subOrderId,
        outerId: 'SPEC-SHARED',
        subItems: [{ name: '共享商品', specCode: 'SPEC-SHARED', qty: 1 }],
      }],
      collectErrors: [],
    };
  };
  fixture.dependencies.resolveSharedReturnGroup = (data, workOrderNum, context) => {
    const batchRecords = [...context.collectedDataByWorkOrder.entries()].map(([num, collectedData]) => ({
      workOrderNum: num,
      collectedData,
    }));
    return resolveSharedReturnGroup(data, batchRecords, workOrderNum);
  };
  fixture.dependencies.inferDecision = async data => {
    inferGroups.push(data.sharedReturnGroup);
    return {
      action: data.sharedReturnGroup.mode === 'combined_applications' ? 'approve' : 'escalate',
      reason: data.sharedReturnGroup.reason || '关联组核对通过',
    };
  };
  fixture.dependencies.shouldAutoExecute = () => false;

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(inferGroups.length, 2);
  assert.ok(inferGroups.every(group => group.mode === 'combined_applications'));
  assert.ok(inferGroups.every(group =>
    group.expectedItems.length === 1 &&
    group.expectedItems[0].specCode === 'SPEC-SHARED' &&
    group.expectedItems[0].qty === 2
  ));
  assert.deepEqual(result.items.map(item => item.decision.action), ['approve', 'approve']);
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'persistOutcome').map(call => [call[1], call[3]]),
    [[ORDER_1, 'escalate'], [ORDER_2, 'escalate'], [ORDER_2, 'approve'], [ORDER_1, 'approve']]
  );
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'open').map(call => call[1]),
    [ORDER_1, ORDER_2]
  );
  assert.equal(fixture.calls.some(call => call[0] === 'execute'), false);
});

test('同批次单向关联即使被关联工单先处理，也先延迟自动执行并在批次末改走共享人工分支', async () => {
  const fixture = batchDependencies();
  fixture.urgent.forEach(ticket => { ticket.type = '退货退款'; });
  const subOrders = { [ORDER_1]: 'SUB-1', [ORDER_2]: 'SUB-2' };

  fixture.dependencies.collectDetail = async ({ ticket }) => {
    const isAssociationSource = ticket.workOrderNum === ORDER_2;
    const subOrderId = subOrders[ticket.workOrderNum];
    return {
      ticket: {
        workOrderNum: ticket.workOrderNum,
        returnTracking: 'TRACK-ONE-WAY',
        returnTrackingMultiUse: isAssociationSource || undefined,
        returnTrackingUsedBy: isAssociationSource ? [ORDER_1] : undefined,
        subOrders: [{ id: subOrderId, afterSaleNum: 1 }],
        gifts: [],
      },
      productArchives: [{
        subOrderId,
        subItems: [{ name: '共享商品', specCode: 'SPEC-SHARED', qty: 1 }],
      }],
      collectErrors: [],
    };
  };
  fixture.dependencies.resolveSharedReturnGroup = (data, workOrderNum, context) =>
    resolveSharedReturnGroupForBatch(data, [], workOrderNum, context);
  fixture.dependencies.inferDecision = async data => ({
    action: data.sharedReturnGroup && data.sharedReturnGroup.mode === 'incomplete' ? 'escalate' : 'approve',
    reason: data.sharedReturnGroup ? `共享分支：${data.sharedReturnGroup.mode}` : '普通精确退回',
  });
  fixture.dependencies.shouldAutoExecute = (_decision, data) => !data.sharedReturnGroup;

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.ok(result.items.every(item => item.collectedData.sharedReturnGroup.mode === 'combined_applications'));
  assert.ok(result.items.every(item => item.status === 'simulated'));
  assert.equal(fixture.calls.some(call => call[0] === 'execute'), false);
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'persistOutcome').map(call => [call[1], call[3]]),
    [[ORDER_1, 'escalate'], [ORDER_2, 'approve'], [ORDER_1, 'approve']]
  );
});

test('批次采集完成后仍无关联的普通退货退款会重新打开详情并保留原自动执行能力', async () => {
  const fixture = batchDependencies();
  fixture.urgent[0].type = '退货退款';

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.items[0].status, 'auto_executed');
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'open').map(call => call[1]),
    [ORDER_1, ORDER_2, ORDER_1]
  );
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'execute').map(call => call[1]),
    [ORDER_1]
  );
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'persistOutcome').map(call => [call[1], call[3]]),
    [[ORDER_1, 'escalate'], [ORDER_2, 'manual'], [ORDER_1, 'approve']]
  );
});

test('延迟关联组时立即写入不可执行占位结果，不能让旧 approve 留在最新状态', async () => {
  const persisted = [];
  const relatedItem = {
    queueItem: { id: `q-${ORDER_2}`, workOrderNum: ORDER_2 },
    ticket: { workOrderNum: ORDER_2, type: '退货退款' },
  };
  const result = await processOpenedDetailAndPersist({
    account: { accountNum: '3' },
    ticket: { workOrderNum: ORDER_1, type: '退货退款' },
    queueItem: { id: `q-${ORDER_1}`, workOrderNum: ORDER_1 },
    sharedReturnContext: {
      batchWorkOrderNums: new Set([ORDER_1, ORDER_2]),
      collectedDataByWorkOrder: new Map(),
      batchItemsByWorkOrder: new Map([[ORDER_2, relatedItem]]),
    },
    allowSharedReturnDefer: true,
  }, {
    collectDetail: async () => ({
      ticket: {
        workOrderNum: ORDER_1,
        returnTrackingMultiUse: true,
        returnTrackingUsedBy: [ORDER_2],
      },
    }),
    resolveSharedReturnGroup: async () => ({
      mode: 'incomplete',
      reason: '缺少关联工单',
      missingWorkOrderNums: [ORDER_2],
    }),
    persistOutcome: async ({ queueItem, processed }) => {
      persisted.push({ queueItem, processed });
      return { id: `sim-safe-placeholder-${queueItem.workOrderNum}`, queueStatus: 'simulated' };
    },
  });

  assert.equal(result.processed.status, 'deferred_shared_return');
  assert.equal(result.persistedSafetyPlaceholder, true);
  assert.equal(persisted.length, 2);
  assert.equal(persisted[0].processed.decision.action, 'escalate');
  assert.equal(persisted[0].processed.decision.humanTriggeredExecutionAllowed, false);
  assert.match(persisted[0].processed.decision.reason, /尚未采齐/);
  assert.equal(persisted[1].queueItem.workOrderNum, ORDER_2);
  assert.equal(persisted[1].processed.decision.humanTriggeredExecutionAllowed, false);
  assert.match(persisted[1].processed.decision.reason, new RegExp(ORDER_1));
  assert.deepEqual(result.relatedSafetyPlaceholders.map(item => item.workOrderNum), [ORDER_2]);
  assert.equal(relatedItem.persistedSimulationId, `sim-safe-placeholder-${ORDER_2}`);
});

test('同批次关联工单包含相同主子订单时不再触发旧去重守卫', async () => {
  let executed = false;
  const result = await processOpenedDetail({
    ticket: { workOrderNum: ORDER_1, type: '退货退款' },
    queueItem: { workOrderNum: ORDER_1, type: '退货退款' },
    sharedReturnContext: {
      batchWorkOrderNums: new Set([ORDER_1, ORDER_2]),
      collectedDataByWorkOrder: new Map(),
    },
  }, {
    collectDetail: async () => ({
      ticket: { workOrderNum: ORDER_1, returnTrackingMultiUse: true },
    }),
    resolveSharedReturnGroup: async () => ({
      mode: 'combined_applications',
      workOrderNums: [ORDER_1, ORDER_2],
      expectedItems: [{ specCode: 'SPEC-1', qty: 2 }],
    }),
    inferDecision: async data => {
      assert.equal(data.sharedReturnGroup.mode, 'combined_applications');
      return { action: 'approve', reason: '两张当前有效申请合并核对通过' };
    },
    shouldAutoExecute: async () => false,
    executeDecision: async () => { executed = true; return { success: true }; },
  });

  assert.equal(result.decision.action, 'approve');
  assert.equal(executed, false);
});

test('关联工单不在当前批次且没有完整记录时不延迟，直接保留人工核验原因', async () => {
  const outsideOrder = '100001781188621717299';
  let inferredGroup = null;
  const result = await processOpenedDetail({
    ticket: { workOrderNum: ORDER_1 },
    queueItem: { workOrderNum: ORDER_1 },
    sharedReturnContext: {
      batchWorkOrderNums: new Set([ORDER_1]),
      collectedDataByWorkOrder: new Map(),
    },
    allowSharedReturnDefer: true,
    disableAutoExecute: true,
  }, {
    collectDetail: async () => ({
      ticket: {
        workOrderNum: ORDER_1,
        returnTrackingMultiUse: true,
        returnTrackingUsedBy: [outsideOrder],
      },
    }),
    resolveSharedReturnGroup: async () => ({
      mode: 'incomplete',
      reason: `平台提示关联工单 ${outsideOrder}，但本轮48小时采集与历史记录均未找到；可能为历史记录缺失或特殊重复申请，需人工判断`,
      missingWorkOrderNums: [outsideOrder],
    }),
    inferDecision: async data => {
      inferredGroup = data.sharedReturnGroup;
      return { action: 'escalate', reason: data.sharedReturnGroup.reason };
    },
  });

  assert.equal(result.status, 'simulated');
  assert.equal(result.decision.action, 'escalate');
  assert.equal(inferredGroup.missingWorkOrderNums[0], outsideOrder);
});

test('平台点名的关联工单不在当前批次时，从历史成功退款记录计算已占用数量', () => {
  const current = {
    ticket: {
      workOrderNum: ORDER_1,
      returnTracking: 'TRACK-SHARED',
      returnTrackingMultiUse: true,
      returnTrackingUsedBy: [ORDER_2],
      subOrders: [{ id: 'SUB-SHARED', afterSaleNum: 1 }],
      gifts: [],
    },
    productArchives: [{
      subOrderId: 'SUB-SHARED',
      subItems: [{ name: '共享商品', specCode: 'SPEC-SHARED', qty: 1 }],
    }],
  };
  const historical = {
    workOrderNum: ORDER_2,
    collectedData: {
      ticket: {
        workOrderNum: ORDER_2,
        returnTracking: 'TRACK-SHARED',
        subOrders: [{ id: 'SUB-SHARED', afterSaleNum: 1 }],
        gifts: [],
      },
      productArchives: [{
        subOrderId: 'SUB-SHARED',
        subItems: [{ name: '共享商品', specCode: 'SPEC-SHARED', qty: 1 }],
      }],
    },
    decision: { action: 'approve' },
    executedAt: '2026-09-01T00:00:00.000Z',
  };
  const context = {
    batchWorkOrderNums: new Set([ORDER_1]),
    collectedDataByWorkOrder: new Map([[ORDER_1, current]]),
  };

  const result = resolveSharedReturnGroupForBatch(current, [historical], ORDER_1, context);
  assert.equal(result.mode, 'combined_applications');
  assert.deepEqual(result.workOrderNums, [ORDER_1]);
  assert.deepEqual(result.expectedItems, [
    { specCode: 'SPEC-SHARED', name: '共享商品', qty: 1 },
  ]);
  assert.deepEqual(result.historicalConsumedItems, [
    { specCode: 'SPEC-SHARED', name: '共享商品', qty: 1 },
  ]);
  assert.equal(result.historicalWorkOrders[0].consumesReturnQty, true);
});

test('换货待商家二次发货保留原推理作对照，最终进入无需处理人工归档', async () => {
  let executed = false;
  const result = await processOpenedDetail({
    ticket: {
      workOrderNum: ORDER_1,
      type: '换货',
      status: '商家-待商家二次发货',
    },
    queueItem: { workOrderNum: ORDER_1, type: '换货' },
  }, {
    collectDetail: async () => ({ ticket: { workOrderNum: ORDER_1 }, collectErrors: [] }),
    inferDecision: async () => ({ action: 'approve', reason: '原综合推理建议同意换货', confidence: 'high' }),
    shouldAutoExecute: async decision => {
      assert.equal(decision.action, 'skip');
      return false;
    },
    executeDecision: async () => { executed = true; return { success: true }; },
  });

  assert.equal(result.status, 'simulated');
  assert.equal(result.decision.action, 'skip');
  assert.equal(result.decision.manualArchiveOnly, true);
  assert.equal(result.collectedData.platformStage.raw, '商家-待商家二次发货');
  assert.equal(result.collectedData.platformStageAssessment.baselineDecision.action, 'approve');
  assert.equal(executed, false);
});

test('自动执行只发生在 shouldAutoExecute 命中时，其他工单进入原待确认状态', async () => {
  const fixture = batchDependencies();
  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.items[0].status, 'auto_executed');
  assert.equal(result.items[1].status, 'simulated');
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'execute').map(call => call[1]),
    [ORDER_1]
  );
});

test('逐单结果写回原系统 queue/simulation 适配层', async () => {
  const fixture = batchDependencies();
  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.deepEqual(result.items.map(item => item.queueItemId), [`q-${ORDER_1}`, `q-${ORDER_2}`]);
  assert.deepEqual(result.items.map(item => item.persistedSimulationId), [`sim-${ORDER_1}`, `sim-${ORDER_2}`]);
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'persistOutcome').map(call => call.slice(1)),
    [
      [ORDER_1, 'auto_executed', 'approve'],
      [ORDER_2, 'simulated', 'manual'],
    ]
  );
});

test('复用旧queue item时强制修正mode和source为live/fixed_batch', async () => {
  const updates = [];
  const ensureQueueItem = createEnsureQueueItem({
    readQueue: () => ({
      items: [{ id: 'q-existing', workOrderNum: ORDER_1, status: 'simulated', mode: 'test', source: 'manual' }],
    }),
    updateQueueItem: (id, patch) => {
      updates.push([id, patch]);
      return { id, workOrderNum: ORDER_1, ...patch };
    },
    addQueueItem: () => assert.fail('已有未完成queue item时不应新增'),
  });

  const item = await ensureQueueItem({
    account: { accountNum: '14', matchedNote: '测试店铺' },
    ticket: { workOrderNum: ORDER_1, type: '仅退款', totalHours: 6 },
  });

  assert.equal(item.mode, 'live');
  assert.equal(item.source, 'fixed_batch');
  assert.equal(updates.length, 1);
  assert.equal(updates[0][0], 'q-existing');
  assert.equal(updates[0][1].mode, 'live');
  assert.equal(updates[0][1].source, 'fixed_batch');
  assert.equal(updates[0][1].platformStage.readState, 'missing');
});

test('queue item 保存列表读取到的平台阶段', async () => {
  let added = null;
  const ensureQueueItem = createEnsureQueueItem({
    readQueue: () => ({ items: [] }),
    updateQueueItem: () => assert.fail('没有旧 queue item 时不应更新'),
    addQueueItem: item => { added = { id: 'q-new', ...item }; return added; },
  });

  const item = await ensureQueueItem({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    ticket: {
      workOrderNum: ORDER_1,
      type: '换货',
      status: '商家-待商家二次发货',
      totalHours: 8,
    },
  });

  assert.equal(item.platformStage.raw, '商家-待商家二次发货');
  assert.equal(item.platformStage.readState, 'read');
  assert.equal(added.platformStage.source, 'after-sale-list');
});

test('同一工单同一阶段已确认后只刷新观察时间，不重复进入待确认', async () => {
  const updates = [];
  let added = false;
  const ensureQueueItem = createEnsureQueueItem({
    readQueue: () => ({
      items: [{
        id: 'q-confirmed',
        workOrderNum: ORDER_1,
        status: 'done',
        type: '换货',
        confirmedNoAction: {
          caseId: 'exchange_waiting_merchant_reship',
          stage: '商家-待商家二次发货',
          confirmedAt: '2026-08-10T04:00:00.000Z',
        },
      }],
    }),
    updateQueueItem: (id, patch) => {
      updates.push([id, patch]);
      return { id, workOrderNum: ORDER_1, status: 'done', ...patch };
    },
    addQueueItem: () => { added = true; return null; },
  });

  const item = await ensureQueueItem({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    ticket: { workOrderNum: ORDER_1, type: '换货', status: '商家-待商家二次发货', totalHours: 8 },
  });

  assert.equal(item.suppressConfirmedNoAction, true);
  assert.equal(item.platformStage.raw, '商家-待商家二次发货');
  assert.equal(updates.length, 1);
  assert.equal(updates[0][0], 'q-confirmed');
  assert.equal(added, false);
});

test('已确认工单的平台阶段变化后创建新 queue item 重新判断', async () => {
  let added = null;
  const ensureQueueItem = createEnsureQueueItem({
    readQueue: () => ({
      items: [{
        id: 'q-confirmed',
        workOrderNum: ORDER_1,
        status: 'done',
        type: '换货',
        confirmedNoAction: {
          caseId: 'exchange_waiting_merchant_reship',
          stage: '商家-待商家二次发货',
          confirmedAt: '2026-08-10T04:00:00.000Z',
        },
      }],
    }),
    updateQueueItem: () => assert.fail('阶段变化后不应更新旧确认记录'),
    addQueueItem: item => { added = { id: 'q-new', status: 'pending', ...item }; return added; },
  });

  const item = await ensureQueueItem({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    ticket: { workOrderNum: ORDER_1, type: '换货', status: '商家-待商家处理', totalHours: 8 },
  });

  assert.equal(item.id, 'q-new');
  assert.equal(item.suppressConfirmedNoAction, undefined);
  assert.equal(added.platformStage.raw, '商家-待商家处理');
});

test('固定批次遇到同阶段已确认项时不打开详情、不解析ERP，仍返回扫描留痕', async () => {
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: {
        urgent: [{ workOrderNum: ORDER_1, type: '换货', status: '商家-待商家二次发货', totalHours: 8 }],
        totalCount: 1,
        complete: true,
      },
    }),
    ensureQueueItem: async () => ({
      id: 'q-confirmed',
      workOrderNum: ORDER_1,
      status: 'done',
      suppressConfirmedNoAction: true,
    }),
    resolveErpTargetId: async () => assert.fail('全部为已确认同阶段时不应解析 ERP target'),
    locateWorkOrder: async () => assert.fail('已确认同阶段时不应再次定位工单'),
    clickWorkOrderAction: async () => assert.fail('已确认同阶段时不应打开详情'),
    collectDetail: async () => assert.fail('已确认同阶段时不应重新采集'),
  });

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].status, 'done');
  assert.equal(result.items[0].suppressConfirmedNoAction, true);
  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'progress').map(call => call.slice(1)),
    [[ORDER_1, 'done']]
  );
});

test('disableAutoExecute=true时命中approve也只写待确认，不调用自动执行链路', async () => {
  const fixture = batchDependencies({
    shouldAutoExecute: async () => assert.fail('disableAutoExecute=true 时不应调用 shouldAutoExecute'),
    executeDecision: async () => assert.fail('disableAutoExecute=true 时不应执行退款'),
  });

  const result = await processSingleAccountFixedBatch('3', {
    dependencies: fixture.dependencies,
    disableAutoExecute: true,
  });

  assert.equal(result.items[0].status, 'simulated');
  assert.equal(result.items[0].autoBlockedReason, 'fixed_batch 已显式关闭自动执行');
  assert.equal(fixture.calls.some(call => call[0] === 'execute'), false);
});

test('runCli支持依赖注入、JSON输出和disable-auto-execute参数', async () => {
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({ success: true, targetId: 'list-tab', list: { urgent: [], totalCount: 0, complete: true } }),
  });
  const lines = [];
  const code = await runCli(['node', '14-process', '3', '--disable-auto-execute'], {
    dependencies: fixture.dependencies,
    writeLine: line => lines.push(line),
  });

  assert.equal(code, 0);
  const output = JSON.parse(lines[0]);
  assert.equal(output.success, true);
  assert.equal(output.snapshot.length, 0);
});

test('runCli遇到非法accountNum返回1且不打开账号', async () => {
  let opened = false;
  const lines = [];
  const fixture = batchDependencies({
    openAccountFlow: async () => { opened = true; return { success: true, targetId: 'list-tab' }; },
  });

  const code = await runCli(['node', '14-process', 'abc'], {
    dependencies: fixture.dependencies,
    writeLine: line => lines.push(line),
  });

  assert.equal(code, 1);
  assert.equal(opened, false);
  assert.match(JSON.parse(lines[0]).error, /accountNum|合法/);
});

test('fixed_batch 来源的终态 skip 沿用原系统语义进入已自动执行列表', () => {
  const processed = {
    status: 'simulated',
    collectedData: { ticket: { workOrderNum: ORDER_1 } },
    decision: { action: 'skip', reason: '工单已退款' },
  };
  const queueItem = { id: `q-${ORDER_1}`, source: 'fixed_batch', workOrderNum: ORDER_1 };

  assert.equal(statusForProcessed(processed, queueItem), 'auto_executed');
  const sim = buildSimulationPayload({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    queueItem,
    ticket: { workOrderNum: ORDER_1 },
    processed,
  });
  assert.equal(Boolean(sim.executedAt), true);
  assert.equal(Boolean(sim.autoExecutedAt), true);
});

test('观察期无需处理 skip 保持待确认，不提前进入已自动执行', () => {
  const processed = {
    status: 'simulated',
    collectedData: { ticket: { workOrderNum: ORDER_1 } },
    decision: { action: 'skip', manualArchiveOnly: true, reason: '待商家二次发货，无需处理' },
  };
  const queueItem = { id: `q-${ORDER_1}`, source: 'fixed_batch', workOrderNum: ORDER_1 };

  assert.equal(statusForProcessed(processed, queueItem), 'simulated');
  const sim = buildSimulationPayload({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    queueItem,
    ticket: { workOrderNum: ORDER_1 },
    processed,
  });
  assert.equal(Boolean(sim.executedAt), false);
  assert.equal(Boolean(sim.autoExecutedAt), false);
});

test('非扫描来源的终态 skip 仍直接 done，不误进已自动执行', () => {
  const processed = {
    status: 'simulated',
    collectedData: { ticket: { workOrderNum: ORDER_1 } },
    decision: { action: 'skip', reason: '工单已退款' },
  };
  const queueItem = { id: `q-${ORDER_1}`, source: 'web', workOrderNum: ORDER_1 };

  assert.equal(statusForProcessed(processed, queueItem), 'done');
  const sim = buildSimulationPayload({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    queueItem,
    ticket: { workOrderNum: ORDER_1 },
    processed,
    source: 'web',
  });
  assert.equal(Boolean(sim.executedAt), true);
  assert.equal(Boolean(sim.autoExecutedAt), false);
});

test('自动执行安全门发现reserve残留intent时阻断approve并转人工', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-gate-residual-'));
  const journal = createAutoExecutionJournal({ filePath: path.join(dir, 'journal.json') });
  journal.reserve(ORDER_1, { accountNote: '测试店铺' });
  const gate = createAutoExecutionGate({
    readCircuit: () => null,
    executionJournal: journal,
    readSimulations: () => { throw new Error('残留intent命中后不应继续读历史执行记录'); },
  });

  assert.deepEqual(await gate({ ticket: { workOrderNum: ORDER_1 } }), {
    allowed: false,
    reason: UNFINISHED_INTENT_BLOCK_REASON,
  });
});

test('approve成功但markExecuted失败留下的intent会阻断下次自动执行', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-gate-mark-fail-'));
  const journal = createAutoExecutionJournal({ filePath: path.join(dir, 'journal.json') });
  journal.reserve(ORDER_1, { accountNote: '测试店铺' });
  const gate = createAutoExecutionGate({
    readCircuit: () => null,
    executionJournal: journal,
    readSimulations: () => [],
  });

  assert.deepEqual(await gate({ ticket: { workOrderNum: ORDER_1 } }), {
    allowed: false,
    reason: UNFINISHED_INTENT_BLOCK_REASON,
  });
});

test('journal已有auto_executed即使simulation缺失也阻断自动执行', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-gate-journal-executed-'));
  const journal = createAutoExecutionJournal({ filePath: path.join(dir, 'journal.json') });
  journal.reserve(ORDER_1, { accountNote: '测试店铺' });
  journal.markPageActionStarted(ORDER_1);
  journal.markExecuted(ORDER_1);
  const gate = createAutoExecutionGate({
    readCircuit: () => null,
    executionJournal: journal,
    readSimulations: () => assert.fail('journal executed 命中后不应继续读 simulation 历史'),
  });

  assert.deepEqual(await gate({ ticket: { workOrderNum: ORDER_1 } }), {
    allowed: false,
    reason: EXECUTED_BLOCK_REASON,
  });
});

test('真实journal自动执行链路写入page action phase后再markExecuted', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-phase-real-journal-'));
  const journal = createAutoExecutionJournal({ filePath: path.join(dir, 'journal.json') });
  const fixture = batchDependencies({
    reserveAutoExecution: async ({ ticket, decision }) => journal.reserve(ticket.workOrderNum, { decisionAction: decision.action }),
    markPageActionStarted: async ({ ticket }) => journal.markPageActionStarted(ticket.workOrderNum),
    markPageActionSucceeded: async ({ ticket }) => journal.markPageActionSucceeded(ticket.workOrderNum),
    markAutoExecuted: async ({ ticket }) => journal.markExecuted(ticket.workOrderNum),
  });

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });
  const record = journal.read()[ORDER_1];

  assert.equal(result.items[0].status, 'auto_executed');
  assert.equal(record.status, STATUS.AUTO_EXECUTED);
  assert.deepEqual(record.history.map(event => event.event), [
    'reserved',
    'page_action_started',
    'page_action_succeeded',
    'auto_executed',
  ]);
});

test('intent残留转人工时simulation保留autoBlockedReason', () => {
  const sim = buildSimulationPayload({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    queueItem: { id: `q-${ORDER_1}`, source: 'fixed_batch', workOrderNum: ORDER_1 },
    ticket: { workOrderNum: ORDER_1 },
    processed: {
      status: 'simulated',
      collectedData: { ticket: { workOrderNum: ORDER_1 } },
      decision: { action: 'approve', reason: '原本可自动同意' },
      autoBlockedReason: UNFINISHED_INTENT_BLOCK_REASON,
    },
  });

  assert.equal(sim.autoBlockedReason, UNFINISHED_INTENT_BLOCK_REASON);
  assert.equal(Boolean(sim.executedAt), false);
});

test('自动执行安全门读取journal损坏或EIO时停止，不当作无残留', async () => {
  for (const failure of [new SyntaxError('journal JSON损坏'), Object.assign(new Error('journal EIO'), { code: 'EIO' })]) {
    const gate = createAutoExecutionGate({
      readCircuit: () => null,
      executionJournal: { getUnfinishedIntent: () => { throw failure; } },
      readSimulations: () => [],
    });
    await assert.rejects(gate({ ticket: { workOrderNum: ORDER_1 } }), /损坏|EIO/);
  }
});

test('自动执行前安全门拒绝时不提交退款并转人工', async () => {
  const fixture = batchDependencies({
    assertAutoExecutionAllowed: async ({ ticket }) => ({
      allowed: ticket.workOrderNum !== ORDER_1,
      reason: '风控熔断中',
    }),
  });
  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.items[0].status, 'simulated');
  assert.equal(result.items[0].autoBlockedReason, '风控熔断中');
  assert.equal(fixture.calls.some(call => call[0] === 'execute' && call[1] === ORDER_1), false);
});

test('批次开始前已熔断时不打开账号', async () => {
  const fixture = batchDependencies({ assertBatchAllowed: async () => ({ allowed: false, reason: '风控熔断中' }) });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /风控熔断中/);
  assert.equal(fixture.calls.some(call => call[0] === 'open'), false);
});

test('熔断文件JSON损坏或读取EIO时批次在打开账号前停止', async () => {
  for (const failure of [new SyntaxError('熔断JSON损坏'), Object.assign(new Error('circuit EIO'), { code: 'EIO' })]) {
    const readCircuit = createCircuitReader(() => { throw failure; }, '/tmp/circuit.json');
    let opened = false;
    const fixture = batchDependencies({
      assertBatchAllowed: async () => { const state = readCircuit(); return state ? { allowed: false } : { allowed: true }; },
      openAccountFlow: async () => { opened = true; return { success: true, targetId: 'list-tab' }; },
    });
    await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /损坏|EIO/);
    assert.equal(opened, false);
  }
});

test('处理中触发熔断时下一张工单开始前停止', async () => {
  let checks = 0;
  const fixture = batchDependencies({
    assertBatchAllowed: async () => (++checks >= 3 ? { allowed: false, reason: '途中熔断' } : { allowed: true }),
  });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /途中熔断/);
  assert.deepEqual(fixture.calls.filter(call => call[0] === 'open').map(call => call[1]), [ORDER_1]);
});

test('自动执行intent写入失败时不得调用approve', async () => {
  const fixture = batchDependencies({ reserveAutoExecution: async () => { throw new Error('intent落盘失败'); } });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /intent落盘失败/);
  assert.equal(fixture.calls.some(call => call[0] === 'execute'), false);
});

test('approve失败后保留intent且停止，不自动重试', async () => {
  const calls = [];
  const fixture = batchDependencies({
    reserveAutoExecution: async () => { calls.push('reserved'); return { reserved: true }; },
    executeDecision: async () => { calls.push('approve'); throw new Error('approve失败'); },
    markAutoExecuted: async () => calls.push('marked'),
  });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /approve失败/);
  assert.deepEqual(calls, ['reserved', 'approve']);
});

test('approve成功但executed回写失败时intent仍阻断未来自动执行', async () => {
  const fixture = batchDependencies({ markAutoExecuted: async () => { throw new Error('executed回写失败'); } });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /executed回写失败/);
  assert.equal(fixture.calls.filter(call => call[0] === 'execute').length, 1);
});

test('进度回调记录 pending、processing 和最终状态的完整轨迹', async () => {
  const fixture = batchDependencies();
  await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  const orderOneStatuses = fixture.calls
    .filter(call => call[0] === 'progress' && call[1] === ORDER_1)
    .map(call => call[2]);
  assert.deepEqual(orderOneStatuses, ['pending', 'processing', 'auto_executed']);
});

test('动态分页收缩后从第二页回第一页找到目标工单', async () => {
  const reads = [
    page(2, [], { totalCount: 11, pages: [{ text: '1', active: false }, { text: '2', active: true }] }),
    page(1, [{ workOrderNum: ORDER_1 }], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true }, { text: '2', active: false }] }),
  ];
  const calls = [];

  const result = await locateWorkOrderOnFreshList('list-tab', ORDER_1, {
    readCurrentPage: async () => reads.shift(),
    clickPageOne: async () => calls.push('page1'),
    clickNextPage: async () => calls.push('next'),
  });

  assert.equal(result.found, true);
  assert.equal(result.page, 1);
  assert.equal(result.ticket.workOrderNum, ORDER_1);
  assert.deepEqual(calls, ['page1']);
});

test('切回第一页先滚动到底部再物理点击，不使用 Vue emit', async () => {
  const events = [];
  const p1rect = { centerX: 100, centerY: 500, left: 86, top: 486, width: 28, height: 28 };
  const p2rect = { centerX: 130, centerY: 500, left: 116, top: 486, width: 28, height: 28 };
  const states = [
    // 1. 初始读取（before）
    page(2, [], { totalCount: 11, pages: [{ text: '1', active: false, rect: p1rect }, { text: '2', active: true, rect: p2rect }] }),
    // 2. 滚动后重读（afterScroll）
    page(2, [], { totalCount: 11, pages: [{ text: '1', active: false, rect: p1rect }, { text: '2', active: true, rect: p2rect }] }),
    // 3. 点击后读取
    page(1, [], { totalCount: 11, pages: [{ text: '1', active: true, rect: p1rect }, { text: '2', active: false, rect: p2rect }] }),
  ];

  const result = await clickPageOneLikeHuman('list-tab', {
    readCurrentPage: async () => states.shift(),
    dispatchMouseEvent: async event => { events.push(event); },
    sleep: async () => {},
  });

  assert.equal(result.pagination.currentPage, 1);
  assert.ok(events.some(e => e.type === 'mouseWheel' && e.deltaY > 0), '应先向下滚动');
  assert.ok(events.some(e => e.type === 'mousePressed' && e.x === p1rect.centerX && e.y === p1rect.centerY), '应物理点击第1页 li');
});

test('切回第一页时拒绝沿用页码先变但cards仍是旧页的瞬时状态', async () => {
  const oldTicket = { workOrderNum: ORDER_2 };
  const newTicket = { workOrderNum: ORDER_1 };
  const p1rect = { centerX: 100, centerY: 500, left: 86, top: 486, width: 28, height: 28 };
  const p2rect = { centerX: 130, centerY: 500, left: 116, top: 486, width: 28, height: 28 };
  const states = [
    // 1. 初始读取（before）
    page(2, [oldTicket], { totalCount: 11, pages: [{ text: '1', active: false, rect: p1rect }, { text: '2', active: true, rect: p2rect }] }),
    // 2. 滚动后重读（afterScroll）—— 仍是第2页，但有 rect
    page(2, [oldTicket], { totalCount: 11, pages: [{ text: '1', active: false, rect: p1rect }, { text: '2', active: true, rect: p2rect }] }),
    // 3-5. waitForPage 内多次读取（页码变了但 cards 还是旧的，直到稳定）
    page(1, [oldTicket], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true, rect: p1rect }, { text: '2', active: false, rect: p2rect }] }),
    page(1, [newTicket], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true, rect: p1rect }, { text: '2', active: false, rect: p2rect }] }),
    page(1, [newTicket], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true, rect: p1rect }, { text: '2', active: false, rect: p2rect }] }),
  ];
  const result = await clickPageOneLikeHuman('list-tab', {
    readCurrentPage: async () => states.shift(),
    dispatchMouseEvent: async () => {},
    sleep: async () => {},
    waitForPage: async (_id, _page, read) => {
      let previous = null;
      while (true) {
        const state = await read();
        const fingerprint = state.tickets.map(ticket => ticket.workOrderNum).join('|');
        if (fingerprint === previous) return state;
        previous = fingerprint;
      }
    },
  });
  assert.deepEqual(result.tickets, [newTicket]);
});

test('生产waitForPage拒绝稳定两次的旧page2 cards，直到page1新cards稳定', async () => {
  const oldState = page(1, [{ workOrderNum: ORDER_2 }], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true }, { text: '2', active: false }] });
  const newState = page(1, [{ workOrderNum: ORDER_1 }], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true }, { text: '2', active: false }] });
  const states = [oldState, oldState, newState, newState];
  const waitForPage = createWaitForPage(async predicate => {
    while (true) { const value = await predicate(); if (value) return value; }
  });
  const result = await waitForPage('list-tab', 1, async () => states.shift(), {
    tickets: [{ workOrderNum: ORDER_2 }], pagination: { currentPage: 2, totalCount: 11 },
  });
  assert.deepEqual(result.tickets, newState.tickets);
  assert.equal(states.length, 0);
});

test('可信地遍历到末页仍找不到时才标记 gone_from_pending', async () => {
  const reads = [
    page(1, [], { totalCount: 11, hasNext: true, pages: [{ text: '1', active: true }, { text: '2', active: false }] }),
    page(2, [], { totalCount: 11, hasNext: false, pages: [{ text: '1', active: false }, { text: '2', active: true }] }),
  ];
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: { urgent: [{ workOrderNum: ORDER_1 }], totalCount: 11, complete: true },
    }),
    locateWorkOrder: (targetId, workOrderNum) => locateWorkOrderOnFreshList(targetId, workOrderNum, {
      readCurrentPage: async () => reads.shift(),
      clickPageOne: async () => assert.fail('已经在第一页，不应重复点击'),
      clickNextPage: async () => ({ clicked: true }),
    }),
  });

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.items[0].status, 'gone_from_pending');
  assert.equal(fixture.calls.some(call => call[0] === 'open'), false);
});

test('next禁用但尚未到totalCount推导末页时不得判gone', async () => {
  await assert.rejects(locateWorkOrderOnFreshList('list-tab', ORDER_1, {
    readCurrentPage: async () => page(2, [], {
      totalCount: 21, hasNext: false,
      pages: [{ text: '1', active: false }, { text: '2', active: true }, { text: '3', active: false }],
    }),
    clickPageOne: async () => page(1, [], { totalCount: 21, hasNext: false, pages: [{ text: '1', active: true }] }),
    clickNextPage: async () => ({ clicked: false }),
  }), /总页数|末页|分页/);
});

test('点击下一页后等待列表刷新到目标页再继续查找', async () => {
  const first = page(1, [], {
    totalCount: 11,
    hasNext: true,
    pages: [{ text: '1', active: true }, { text: '2', active: false }],
  });
  const second = page(2, [{ workOrderNum: ORDER_1 }], {
    totalCount: 11,
    hasNext: false,
    pages: [{ text: '1', active: false }, { text: '2', active: true }],
  });
  const reads = [first, first, second];

  const result = await locateWorkOrderOnFreshList('list-tab', ORDER_1, {
    readCurrentPage: async () => reads.shift(),
    clickPageOne: async () => assert.fail('已经在第一页'),
    clickNextPage: async () => ({ clicked: true }),
    waitForPage: async (_targetId, expectedPage, readCurrentPage) => {
      let state;
      do state = await readCurrentPage(); while (state.pagination.currentPage !== expectedPage);
      return state;
    },
  });

  assert.equal(result.found, true);
  assert.equal(result.page, 2);
  assert.equal(reads.length, 0);
});

test('单页总数不超过10且仅页1激活时，当前页找不到即可判定消失', async () => {
  const result = await locateWorkOrderOnFreshList('list-tab', ORDER_1, {
    readCurrentPage: async () => page(1, [], {
      totalCount: 5,
      hasNext: false,
      pages: [{ text: '1', active: true }],
    }),
    clickPageOne: async () => assert.fail('单页不应点击页1'),
    clickNextPage: async () => assert.fail('单页不应翻页'),
  });

  assert.deepEqual(result, {
    found: false,
    gone: true,
    reason: '单页待处理列表未找到目标工单',
    pagesChecked: [1],
  });
});

test('翻页失败不得误标消失，必须写回待确认并停止后续工单', async () => {
  const fixture = batchDependencies({
    locateWorkOrder: async () => { throw new Error('翻页后页码未变化'); },
  });

  await assert.rejects(
    processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }),
    /翻页后页码未变化/
  );

  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'progress').map(call => call.slice(1)),
    [
      [ORDER_1, 'pending'],
      [ORDER_2, 'pending'],
      [ORDER_1, 'processing'],
      [ORDER_1, 'simulated'],
    ]
  );
  assert.equal(fixture.calls.some(call => call[0] === 'open'), false);
});

test('详情处理异常仍关闭目标tab、写回人工复核simulation并停止下一单', async () => {
  const persistedFailures = [];
  const fixture = batchDependencies({
    collectDetail: async ({ detailTargetId }) => {
      assert.equal(detailTargetId, `detail-${ORDER_1}`);
      throw new Error('采集失败');
    },
    persistOutcome: async ({ ticket, processed }) => {
      persistedFailures.push({ ticket, processed });
      return { id: `sim-failure-${ticket.workOrderNum}`, queueStatus: 'simulated' };
    },
  });

  await assert.rejects(
    processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }),
    /采集失败/
  );

  assert.equal(persistedFailures.length, 1);
  assert.equal(persistedFailures[0].ticket.workOrderNum, ORDER_1);
  assert.equal(persistedFailures[0].processed.status, 'simulated');
  assert.equal(persistedFailures[0].processed.decision.action, 'escalate');
  assert.match(persistedFailures[0].processed.decision.reason, /fixed_batch处理失败: 采集失败/);
  assert.deepEqual(
    fixture.calls.filter(call => ['open', 'close'].includes(call[0])),
    [
      ['open', ORDER_1, `detail-${ORDER_1}`],
      ['close', `detail-${ORDER_1}`],
    ]
  );
  assert.deepEqual(fixture.getTargets(), ['list-tab']);
});

test('点击后新tab识别失败时关闭错误携带的新增tab并停止', async () => {
  const closes = [];
  let targets = [
    { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
    { id: 'unexpected-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=' + ORDER_1 },
  ];
  const fixture = batchDependencies({
    clickWorkOrderAction: async () => {
      const error = new Error('新标签页校验失败');
      error.newTargetIds = ['unexpected-tab'];
      throw error;
    },
    closeTarget: async targetId => {
      closes.push(targetId);
      targets = targets.filter(target => target.id !== targetId);
    },
    getTargets: async () => targets,
  });

  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /新标签页校验失败/);
  assert.deepEqual(closes, ['unexpected-tab']);
});

test('详情tab关闭后仍存在时立即停止，且不得继续下一单', async () => {
  const fixture = batchDependencies({
    closeTarget: async targetId => ({ closed: true, targetId }),
  });

  await assert.rejects(
    processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }),
    /详情标签页关闭验证失败/
  );

  assert.deepEqual(
    fixture.calls.filter(call => call[0] === 'open').map(call => call[1]),
    [ORDER_1]
  );
});

test('空清单直接返回成功，不打开工单、不读取首页提醒', async () => {
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: { urgent: [], totalCount: 0, complete: true },
    }),
    fetchAndCacheAlerts: async () => assert.fail('本步骤不读取首页提醒'),
  });

  const result = await processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies });

  assert.equal(result.success, true);
  assert.deepEqual(result.snapshot, []);
  assert.deepEqual(result.items, []);
  assert.equal(fixture.calls.some(call => call[0] === 'open'), false);
});

test('首次48小时清单未完整读取时拒绝冻结和处理', async () => {
  let reconciled = false;
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({
      success: true,
      targetId: 'list-tab',
      list: { urgent: [{ workOrderNum: ORDER_1 }], totalCount: 21, complete: false, stopReason: '达到最大页数' },
    }),
    reconcileWaitingRescanAbsences: async () => {
      reconciled = true;
      return [];
    },
  });

  await assert.rejects(
    processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }),
    /48小时清单读取不完整/
  );
  assert.equal(fixture.calls.some(call => call[0] === 'open'), false);
  assert.equal(reconciled, false);
});

test('首次清单缺少有效totalCount时拒绝冻结', async () => {
  const fixture = batchDependencies({
    prepareAfterSaleList: async () => ({ success: true, targetId: 'list-tab', list: { urgent: [], complete: true, totalCount: null } }),
  });
  await assert.rejects(processSingleAccountFixedBatch('3', { dependencies: fixture.dependencies }), /totalCount/);
});

test('生产阈值固定48小时，拒绝其他thresholdHours', async () => {
  const fixture = batchDependencies();
  await assert.rejects(processSingleAccountFixedBatch('3', { thresholdHours: 24, dependencies: fixture.dependencies }), /固定为48小时/);
});

test('关闭详情tab前必须确认它是当前账号鲸灵详情页，且不是列表主tab', async () => {
  let closed = false;
  let targets = [
    { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
    { id: 'detail-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=' + ORDER_1 },
  ];
  const dependencies = {
    getTargets: async () => targets,
    readShopName: async targetId => ({ success: true, state: 'logged-in', shopName: targetId === 'detail-tab' ? '测试店铺旗舰店' : '测试店铺' }),
    sleep: async () => {},
    closeTarget: async targetId => {
      closed = true;
      targets = targets.filter(target => target.id !== targetId);
    },
  };

  await closeAndVerifyDetailTarget('detail-tab', dependencies, {
    account: { matchedNote: '测试店铺' },
    listTargetId: 'list-tab',
  });

  assert.equal(closed, true);
  assert.deepEqual(targets.map(target => target.id), ['list-tab']);
});

test('拒绝关闭非鲸灵tab、售后列表主tab或非当前账号鲸灵tab', async () => {
  const baseContext = { account: { matchedNote: '测试店铺' }, listTargetId: 'list-tab' };
  const makeDeps = (target, shopName = '测试店铺') => ({
    getTargets: async () => [
      { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
      target,
    ],
    readShopName: async () => ({ success: true, state: 'logged-in', shopName }),
    closeTarget: async () => assert.fail('不应关闭不可信 tab'),
  });

  await assert.rejects(closeAndVerifyDetailTarget('erp-tab', makeDeps({ id: 'erp-tab', url: 'https://viperp.superboss.cc/' }), baseContext), /非鲸灵/);
  await assert.rejects(closeAndVerifyDetailTarget('list-tab', makeDeps({ id: 'detail-tab', url: 'https://scrm.jlsupp.com/other' }), baseContext), /列表主 tab/);
  await assert.rejects(closeAndVerifyDetailTarget('detail-tab', makeDeps({ id: 'detail-tab', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail' }, '其他店铺'), baseContext), /非当前账号/);
});

test('账号收尾只关闭当前账号鲸灵非列表tab，并复核列表主tab仍匹配', async () => {
  const closed = [];
  let targets = [
    { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
    { id: 'detail-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=' + ORDER_1 },
    { id: 'other-shop-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=' + ORDER_2 },
    { id: 'erp-tab', type: 'page', url: 'https://viperp.superboss.cc/' },
  ];
  const dependencies = {
    getTargets: async () => targets,
    readShopName: async targetId => ({
      success: true,
      state: 'logged-in',
      shopName: targetId === 'other-shop-tab' ? '其他店铺' : '测试店铺',
    }),
    closeTarget: async targetId => {
      closed.push(targetId);
      targets = targets.filter(target => target.id !== targetId);
    },
  };

  const result = await cleanupCurrentAccountJlTargets({
    account: { matchedNote: '测试店铺' },
    listTargetId: 'list-tab',
  }, dependencies);

  assert.deepEqual(result.closedTargetIds, ['detail-tab']);
  assert.deepEqual(closed, ['detail-tab']);
  assert.deepEqual(targets.map(target => target.id), ['list-tab', 'other-shop-tab', 'erp-tab']);
});

test('有目标店铺名但缺readShopName时拒绝账号收尾清理', async () => {
  const dependencies = {
    getTargets: async () => [
      { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
      { id: 'detail-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-detail?workOrderNum=' + ORDER_1 },
    ],
    closeTarget: async () => assert.fail('缺少店铺校验依赖时不应关闭任何鲸灵 tab'),
  };

  await assert.rejects(
    cleanupCurrentAccountJlTargets({ account: { matchedNote: '测试店铺' }, listTargetId: 'list-tab' }, dependencies),
    /缺少 readShopName|店铺校验/
  );
});

test('默认依赖装配真实target-aware采集器，不走旧collect或pipeline注入路径', () => {
  const dependencies = loadDefaultDependencies();
  const source = fs.readFileSync(
    path.join(__dirname, '../../scripts/jl-steps/14-process-single-account-fixed-batch.js'),
    'utf8'
  );

  assert.equal(typeof dependencies.collectDetail, 'function');
  assert.equal(typeof dependencies.resolveErpTargetId, 'function');
  assert.equal(typeof dependencies.resolveSharedReturnGroup, 'function');
  assert.equal(typeof dependencies.reconcileWaitingRescanAbsences, 'function');
  assert.doesNotMatch(String(dependencies.collectDetail), /尚未接通/);
  assert.doesNotMatch(source, /require\(['"]\.\.\/\.\.\/collect\.js['"]\)/);
  assert.doesNotMatch(source, /require\(['"].*pipeline['"]\)/);
  assert.doesNotMatch(source, /sessions\/jl\.js/);
});
