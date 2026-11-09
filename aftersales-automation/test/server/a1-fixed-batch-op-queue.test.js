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
  const blocked = Object.assign(new Error('风控熔断中'), { jinglingCircuitBlocked: true });
  assert.equal(buildA1FixedBatchFailureStatus({ type: 'a1-fixed-batch', params: { accountNum: '3' } }, blocked), null);
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

test('账号状态不可信隔离只关闭当前鲸灵tab，并在5秒静默后再次确认无鲸灵tab', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { isolateUntrustedJlTarget } = require('../../lib/server/op-queue');
  const calls = [];
  let targets = [
    { id: 'jl-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-supplier/business/home' },
    { id: 'erp-tab', type: 'page', url: 'https://viperp.superboss.cc/' },
  ];
  const cdp = {
    getTargets: async () => targets.map(item => ({ ...item })),
    closeTarget: async targetId => {
      calls.push(['close', targetId]);
    },
  };

  const result = await isolateUntrustedJlTarget('jl-tab', {}, {
    cdp,
    wait: async ms => {
      calls.push(['wait', ms]);
      if (ms === 300) targets = targets.filter(item => item.id !== 'jl-tab');
    },
  });

  assert.deepEqual(result, { isolated: true, quietMs: 5000 });
  assert.deepEqual(calls, [['close', 'jl-tab'], ['wait', 300], ['wait', 5000]]);
  assert.deepEqual(targets.map(item => item.id), ['erp-tab']);
});

test('账号状态不可信隔离会关闭已知异常target，即使它暂时还是about:blank', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { isolateUntrustedJlTarget } = require('../../lib/server/op-queue');
  const calls = [];
  let targets = [
    { id: 'jl-tab', type: 'page', url: 'about:blank' },
    { id: 'erp-tab', type: 'page', url: 'https://viperp.superboss.cc/' },
  ];
  const cdp = {
    getTargets: async () => targets.map(item => ({ ...item })),
    closeTarget: async targetId => {
      calls.push(['close', targetId]);
      targets = targets.filter(item => item.id !== targetId);
    },
  };

  await isolateUntrustedJlTarget('jl-tab', {}, {
    cdp,
    wait: async ms => calls.push(['wait', ms]),
  });

  assert.deepEqual(calls, [['close', 'jl-tab'], ['wait', 300], ['wait', 5000]]);
  assert.deepEqual(targets.map(item => item.id), ['erp-tab']);
});

test('about:blank异常target关闭请求返回后仍存在时必须判隔离失败', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { isolateUntrustedJlTarget } = require('../../lib/server/op-queue');
  const calls = [];
  const targets = [
    { id: 'jl-tab', type: 'page', url: 'about:blank' },
    { id: 'erp-tab', type: 'page', url: 'https://viperp.superboss.cc/' },
  ];
  const cdp = {
    getTargets: async () => targets.map(item => ({ ...item })),
    closeTarget: async targetId => calls.push(['close', targetId]),
  };

  await assert.rejects(
    isolateUntrustedJlTarget('jl-tab', {}, {
      cdp,
      wait: async ms => calls.push(['wait', ms]),
    }),
    /目标 tab 关闭后仍存在/
  );

  assert.deepEqual(calls, [['close', 'jl-tab'], ['wait', 300]]);
});

test('隔离开始前已经收到停止时不读取也不关闭任何tab', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { isolateUntrustedJlTarget } = require('../../lib/server/op-queue');
  const controller = new AbortController();
  controller.abort();
  const calls = [];
  const cdp = {
    getTargets: async () => {
      calls.push(['getTargets']);
      return [];
    },
    closeTarget: async targetId => calls.push(['close', targetId]),
  };

  await assert.rejects(
    isolateUntrustedJlTarget('jl-tab', { _abortSignal: controller.signal }, {
      cdp,
      wait: async ms => calls.push(['wait', ms]),
    }),
    error => error && error.name === 'AbortError'
  );

  assert.deepEqual(calls, []);
});

test('账号状态不可信隔离发现额外鲸灵tab时立即失败，不重复关闭或等待', async () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { isolateUntrustedJlTarget } = require('../../lib/server/op-queue');
  const calls = [];
  let targets = [
    { id: 'jl-tab', type: 'page', url: 'https://scrm.jlsupp.com/micro-supplier/business/home' },
    { id: 'unexpected-jl', type: 'page', url: 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list' },
  ];
  const cdp = {
    getTargets: async () => targets.map(item => ({ ...item })),
    closeTarget: async targetId => {
      calls.push(['close', targetId]);
      targets = targets.filter(item => item.id !== targetId);
    },
  };

  await assert.rejects(
    isolateUntrustedJlTarget('jl-tab', {}, {
      cdp,
      wait: async ms => calls.push(['wait', ms]),
    }),
    /关闭后仍有鲸灵 tab/
  );
  assert.deepEqual(calls, [['close', 'jl-tab'], ['wait', 300]]);
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
    remaining: '1 天 5 小时 30 分 后自动换货',
    totalHours: 29.5,
  });

  assert.equal(ticket.platformStage.raw, '商家-待商家二次发货');
  assert.equal(ticket.platformStage.readState, 'read');
  assert.notEqual(ticket.platformStage.observedAt, '2026-08-10T03:00:00.000Z');
  assert.equal(ticket.remaining, '1 天 5 小时 30 分 后自动换货');
  assert.equal(ticket.totalHours, 29.5);
});

test('重新采集用当前列表倒计时覆盖旧截止时间，超过48小时则停止处理', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildFreshReprocessState } = require('../../lib/server/op-queue');
  const nowMs = Date.parse('2026-08-20T08:00:00.000Z');
  const state = buildFreshReprocessState({
    workOrderNum: '100001786710544972432',
    type: '退货退款',
    accountNote: '测试店铺',
    urgency: '1 天 14 小时 9 分 后自动退货退款',
    deadlineAt: '2026-08-21T02:09:47.537Z',
  }, {
    workOrderNum: '100001786710544972432',
    type: '退货退款',
    status: '商家-待收货',
    remaining: '12 天 23 小时 45 分 后自动退货退款',
    totalHours: 311.75,
  }, '测试店铺', nowMs);

  assert.equal(state.outside48Hours, true);
  assert.equal(state.queuePatch.urgency, '12 天 23 小时 45 分 后自动退货退款');
  assert.equal(state.queuePatch.deadlineAt, '2026-09-02T07:45:00.000Z');
  assert.notEqual(state.queuePatch.deadlineAt, '2026-08-21T02:09:47.537Z');
});

test('超过48小时的重新采集写入明确暂缓结果，不继续展示旧缺失告警', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildFreshReprocessState, buildOutside48ReprocessProcessed } = require('../../lib/server/op-queue');
  const state = buildFreshReprocessState({
    workOrderNum: '100001786710544972432',
    type: '退货退款',
    accountNote: '测试店铺',
  }, {
    workOrderNum: '100001786710544972432',
    type: '退货退款',
    status: '商家-待收货',
    remaining: '12 天 23 小时 45 分 后自动退货退款',
    totalHours: 311.75,
  });
  const processed = buildOutside48ReprocessProcessed(state, {
    id: 'waiting-missing-old',
    collectedData: {
      ticket: { workOrderNum: '100001786710544972432', returnTracking: 'YT1234567890' },
    },
    decision: { reasonCode: 'WAITING_RESCAN_MISSING_FROM_48H_LIST' },
  }, '2026-08-20T08:00:00.000Z');

  assert.equal(processed.status, 'simulated');
  assert.equal(processed.decision.reasonCode, 'OUTSIDE_48H_DEFERRED');
  assert.equal(processed.decision.recommendedActionLabel, '已移出48小时范围');
  assert.match(processed.decision.reason, /12 天 23 小时 45 分/);
  assert.equal(processed.decision.humanTriggeredExecutionAllowed, false);
  assert.equal(processed.collectedData.ticket.returnTracking, 'YT1234567890');
  assert.deepEqual(processed.collectedData.outside48h, {
    observedAt: '2026-08-20T08:00:00.000Z',
    totalHours: 311.75,
    source: 'manual_reprocess_list',
  });
});

test('重新采集无法读取当前倒计时时安全停止', () => {
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const { buildFreshReprocessState } = require('../../lib/server/op-queue');
  assert.throws(() => buildFreshReprocessState({
    workOrderNum: '100001786710544972432',
    type: '退货退款',
  }, {
    workOrderNum: '100001786710544972432',
    type: '退货退款',
    remaining: null,
    totalHours: null,
  }), /当前倒计时解析失败/);
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

test('已持久熔断时，查看、重采和执行在打开任何平台页面前被队列拦截', async t => {
  const { jinglingCircuit } = require('../../lib/wait');
  const readCircuit = t.mock.method(jinglingCircuit, 'read', () => ({ tripped: true, reason: '模拟风控' }));
  const open = t.mock.method(require('../../lib/jl/open-account-flow'), 'openAccountFlow', async () => {
    assert.fail('熔断中不能打开平台页面');
  });
  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const opQueue = require('../../lib/server/op-queue');
  for (const type of ['open-ticket', 'reprocess-one', 'execute', 'scan', 'open-account']) {
    const op = opQueue.enqueue(type, `模拟 ${type}`, {});
    const completed = await waitFor(() => {
      const last = opQueue.getState().lastCompleted;
      return last?.id === op.id && last;
    });
    assert.equal(completed.status, 'error');
    assert.match(completed.result.error, /风控熔断中: 模拟风控/);
  }
  assert.equal(readCircuit.mock.callCount(), 5);
  assert.equal(open.mock.callCount(), 0);
});

test('共享熔断使用现有文件和人工复位所需的状态格式', t => {
  const { jinglingCircuit } = require('../../lib/wait');
  const write = t.mock.method(require('node:fs'), 'writeFileSync', () => {});
  jinglingCircuit.trip(new Error('模拟 HTTP 426'), 'jl_work_order_detail');
  assert.equal(write.mock.callCount(), 1);
  const [file, content] = write.mock.calls[0].arguments;
  assert.match(file, /\/data\/circuit-breaker\.json$/);
  const record = JSON.parse(content);
  assert.equal(record.tripped, true);
  assert.equal(record.reason, '模拟 HTTP 426');
  assert.equal(record.trippedBy, 'jl_work_order_detail');
  assert.ok(Number.isFinite(Date.parse(record.trippedAt)));
});

test('熔断写盘失败后保持阻断，人工复位记录可恢复仍在运行的服务', t => {
  const { createJinglingCircuit } = require('../../lib/wait');
  const file = 'mock-circuit.json';
  let saved = JSON.stringify({ tripped: false, resetAt: '2026-11-09T01:00:00.000Z' });
  let canWrite = false;
  let canRead = true;
  const storage = {
    readFile: () => {
      if (!canRead) throw Object.assign(new Error('read failure'), { code: 'EACCES' });
      if (!saved) throw Object.assign(new Error('not found'), { code: 'ENOENT' });
      return saved;
    },
    writeFile: (_file, value) => {
      if (!canWrite) throw Object.assign(new Error('storage failure'), { code: 'EIO' });
      saved = value;
    },
  };
  const running = createJinglingCircuit(file, { ...storage, now: () => '2026-11-09T02:00:00.000Z' });
  const manual = createJinglingCircuit(file, { ...storage, now: () => '2026-11-09T03:00:00.000Z' });
  t.mock.method(console, 'error', () => {});
  running.trip(new Error('模拟风控'), 'fixture');
  assert.equal(running.read().tripped, true);
  saved = '{';
  assert.equal(running.read().reason, '模拟风控');
  assert.equal(manual.read().tripped, true);
  canRead = false;
  assert.equal(running.read().reason, '模拟风控');
  assert.equal(manual.read().tripped, true);
  canRead = true;
  saved = null;
  assert.equal(running.read().tripped, true);
  assert.throws(() => manual.reset(), /storage failure/);
  canWrite = true;
  manual.reset();
  assert.equal(running.read().tripped, false);
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
