'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function waitFor(predicate) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const tick = () => {
      try {
        const value = predicate();
        if (value) return resolve(value);
      } catch (error) {
        return reject(error);
      }
      if (Date.now() - started > 1000) return reject(new Error('timed out waiting for op'));
      setTimeout(tick, 10);
    };
    tick();
  });
}

test('a1-fixed-batch失败会生成账号级持久异常状态', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildA1FixedBatchFailureStatus } = require('../../lib/server/op-queue');
  const failure = buildA1FixedBatchFailureStatus({
    type: 'a1-fixed-batch',
    params: { accountNum: '3', accountNote: '百浩-RITEKOKO' },
  }, new Error('售后工单 100001784549334112734 倒计时解析失败，停止冻结48小时清单'),
  () => '2026-07-23T10:00:00.000Z');

  assert.deepEqual(failure, {
    accountNum: '3',
    patch: {
      status: 'error',
      error: '售后工单 100001784549334112734 倒计时解析失败，停止冻结48小时清单',
      lastScan: '2026-07-23T10:00:00.000Z',
      note: '百浩-RITEKOKO',
    },
  });
});

test('a1-fixed-batch登录异常仍归类为登录失效', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildA1FixedBatchFailureStatus } = require('../../lib/server/op-queue');
  const failure = buildA1FixedBatchFailureStatus({
    type: 'a1-fixed-batch',
    params: { accountNum: '3', accountNote: '百浩-RITEKOKO' },
  }, new Error('注入后仍跳转到登录页'));

  assert.equal(failure.patch.status, 'expired');
});

test('等待重查仅拦截件允许人工提前拒绝', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { canManuallyExecuteWaitingIntercept } = require('../../lib/server/op-queue');
  const queueItem = { status: 'waiting' };

  assert.equal(canManuallyExecuteWaitingIntercept(queueItem, {
    action: 'reject',
    waitingRescan: true,
    manualExecutionAllowedWhileWaiting: true,
    reasonCode: 'INTERCEPT_WAITING',
  }), true);

  assert.equal(canManuallyExecuteWaitingIntercept(queueItem, {
    action: 'reject',
    waitingRescan: true,
    reasonCode: 'WAREHOUSE_NOT_RECEIVED',
  }), false);
  assert.equal(canManuallyExecuteWaitingIntercept({ status: 'simulated' }, {
    action: 'reject',
    waitingRescan: true,
    manualExecutionAllowedWhileWaiting: true,
    reasonCode: 'INTERCEPT_WAITING',
  }), false);
});

test('重新采集使用本次列表定位到的新阶段，不沿用 queue 旧阶段', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildFreshReprocessTicket } = require('../../lib/server/op-queue');
  const ticket = buildFreshReprocessTicket({
    workOrderNum: '100001785233662360131',
    type: '换货',
    accountNote: '测试店铺',
    platformStage: {
      raw: '商家-待商家处理',
      observedAt: '2026-08-10T03:00:00.000Z',
      source: 'after-sale-list',
      readState: 'read',
    },
  }, {
    workOrderNum: '100001785233662360131',
    type: '换货',
    status: '商家-待商家二次发货',
  });

  assert.equal(ticket.platformStage.raw, '商家-待商家二次发货');
  assert.equal(ticket.platformStage.readState, 'read');
  assert.notEqual(ticket.platformStage.observedAt, '2026-08-10T03:00:00.000Z');
});

test('等待重查完整复用扫描处理链路，七天无理由命中后可自动执行并统一写回', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { processRecheckedOpenedDetail } = require('../../lib/server/op-queue');
  const calls = [];
  const queueItem = {
    id: 'q-recheck-1',
    workOrderNum: '100001785233662360132',
    type: '退货退款',
    status: 'waiting',
  };

  const result = await processRecheckedOpenedDetail({
    account: { accountNum: '3', matchedNote: '测试店铺' },
    listTargetId: 'list-tab',
    detailTargetId: 'detail-tab',
    erpTargetId: 'erp-tab',
    ticket: { workOrderNum: queueItem.workOrderNum, type: '退货退款' },
    queueItem,
  }, {
    dependencies: {
      collectDetail: async () => ({ ticket: { afterSaleReason: '七天无理由退货（不喜欢/不合适）' } }),
      inferDecision: async (_collectedData, freshQueueItem) => {
        calls.push(['infer', freshQueueItem.type]);
        return { action: 'approve', caseId: 'refund_return_exact_match' };
      },
      shouldAutoExecute: async (_decision, _collectedData, freshQueueItem) => {
        calls.push(['auto-gate', freshQueueItem.type]);
        return freshQueueItem.type === '退货退款';
      },
      assertAutoExecutionAllowed: async () => ({ allowed: true }),
      reserveAutoExecution: async () => calls.push(['reserve']),
      markPageActionStarted: async () => calls.push(['page-started']),
      executeDecision: async () => ({ success: true, action: 'approve' }),
      markPageActionSucceeded: async () => calls.push(['page-succeeded']),
      markAutoExecuted: async () => calls.push(['executed']),
      persistOutcome: async ({ processed, source, queueItem: persistedQueueItem }) => {
        calls.push(['persist', source, persistedQueueItem.id, processed.status]);
        return { id: 'reprocess-sim-1', queueStatus: 'auto_executed' };
      },
    },
  });

  assert.equal(result.processed.status, 'auto_executed');
  assert.equal(result.persisted.queueStatus, 'auto_executed');
  assert.deepEqual(calls, [
    ['infer', '退货退款'],
    ['auto-gate', '退货退款'],
    ['reserve'],
    ['page-started'],
    ['page-succeeded'],
    ['executed'],
    ['persist', 'reprocess', 'q-recheck-1', 'auto_executed'],
  ]);
});

test('op-queue executes a1-fixed-batch through Step14 with fixed 48h defaults', async () => {
  const step14Path = path.join(__dirname, '../../scripts/jl-steps/14-process-single-account-fixed-batch.js');
  const resolvedStep14 = require.resolve(step14Path);
  const calls = [];
  require.cache[resolvedStep14] = {
    id: resolvedStep14,
    filename: resolvedStep14,
    loaded: true,
    exports: {
      processSingleAccountFixedBatch: async (accountNum, options) => {
        calls.push([accountNum, options]);
        return { success: true, accountNum, items: [] };
      },
    },
  };

  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const opQueue = require('../../lib/server/op-queue');
  const op = opQueue.enqueue('a1-fixed-batch', 'A1固定清单 账号14「茗瑞-KGOS」', {
    accountNum: '14',
    accountNote: '茗瑞-KGOS',
    thresholdHours: 1,
    disableAutoExecute: false,
  });

  const completed = await waitFor(() => opQueue.getState().lastCompleted);

  assert.equal(completed.id, op.id);
  assert.equal(completed.status, 'done');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '14');
  assert.equal(calls[0][1].thresholdHours, 48);
  assert.equal(typeof calls[0][1].onTicketProgress, 'function');
  assert.deepEqual(completed.result, { success: true, accountNum: '14', items: [] });
});
