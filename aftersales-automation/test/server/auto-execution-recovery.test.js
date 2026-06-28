'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
  createAutoExecutionJournal,
  STATUS,
  RESOLUTION,
} = require('../../lib/server/auto-execution-journal');
const {
  createAutoExecutionRecovery,
} = require('../../lib/server/auto-execution-recovery');

const ORDER = '100001781188621717210';
const NOW = new Date('2026-06-27T01:02:03.000Z');

function makeFixture() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-recovery-'));
  const journal = createAutoExecutionJournal({ filePath: path.join(dir, 'journal.json'), now: () => NOW });
  journal.reserve(ORDER, { accountNum: 14, accountNote: '茗瑞-KGOS', decisionAction: 'approve' });
  journal.markPageActionStarted(ORDER);

  const queue = {
    updatedAt: null,
    items: [{
      id: 'q-1',
      workOrderNum: ORDER,
      accountNum: 14,
      accountNote: '茗瑞-KGOS',
      mode: 'live',
      source: 'fixed_batch',
      status: 'auto_executing',
    }],
  };
  const simulations = [{
    id: 'sim-1',
    workOrderNum: ORDER,
    queueItemId: 'q-1',
    accountNum: 14,
    accountNote: '茗瑞-KGOS',
    mode: 'live',
    source: 'fixed_batch',
    decision: { action: 'approve', reason: '原本可自动同意' },
    createdAt: '2026-06-27T00:00:00.000Z',
  }];
  const recovery = createAutoExecutionRecovery({
    journal,
    readQueue: () => queue,
    updateQueueItem: (id, patch) => {
      const idx = queue.items.findIndex(item => item.id === id);
      if (idx === -1) return null;
      queue.items[idx] = { ...queue.items[idx], ...patch };
      return queue.items[idx];
    },
    readSimulations: () => simulations,
    appendSimulation: sim => simulations.push(sim),
    now: () => NOW,
  });
  return { journal, queue, simulations, recovery };
}

test('confirmed_executed 人工归档同步关闭 journal、queue 和 audit simulation', () => {
  const { journal, queue, simulations, recovery } = makeFixture();
  const result = recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_EXECUTED,
    operatorNote: '已在鲸灵后台确认退款成功',
  });

  assert.equal(result.ok, true);
  assert.equal(result.journal.status, STATUS.MANUALLY_RESOLVED);
  assert.equal(result.journal.resolution, RESOLUTION.CONFIRMED_EXECUTED);
  assert.equal(result.journal.allowAutoRetry, false);
  assert.equal(result.journal.allowBatchExecute, false);
  assert.equal(result.journal.queueItemId, 'q-1');
  assert.equal(result.journal.recoverySimulationId, result.simulation.id);

  assert.equal(result.simulation.id, `auto-recovery-${ORDER}-${RESOLUTION.CONFIRMED_EXECUTED}`);
  assert.equal(queue.items[0].status, 'auto_executed');
  assert.equal(queue.items[0].manualResolution, RESOLUTION.CONFIRMED_EXECUTED);
  assert.equal(queue.items[0].batchExecuteBlocked, true);
  assert.equal(Boolean(queue.items[0].executedAt), true);

  const audit = simulations.at(-1);
  assert.equal(audit.id, `auto-recovery-${ORDER}-${RESOLUTION.CONFIRMED_EXECUTED}`);
  assert.equal(audit.source, 'auto_execution_recovery');
  assert.equal(audit.manualResolution, RESOLUTION.CONFIRMED_EXECUTED);
  assert.equal(audit.executedAt, NOW.toISOString());
  assert.equal(audit.autoExecutedAt, NOW.toISOString());
  assert.equal(journal.getBlockingRecord(ORDER).blockReason, '自动执行异常已人工归档，禁止自动重试');
});

test('confirmed_not_executed 回待确认但默认禁止自动/批量重试，并清理旧执行终态字段', () => {
  const { queue, simulations, recovery } = makeFixture();
  queue.items[0].executedAt = '2026-06-27T00:10:00.000Z';
  queue.items[0].autoExecutedAt = '2026-06-27T00:10:00.000Z';
  queue.items[0].execution = { success: true };
  simulations[0].executedAt = '2026-06-27T00:10:00.000Z';
  simulations[0].autoExecutedAt = '2026-06-27T00:10:00.000Z';
  simulations[0].execution = { success: true };
  recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_NOT_EXECUTED,
    operatorNote: '后台确认未提交',
  });

  assert.equal(queue.items[0].status, 'simulated');
  assert.equal(queue.items[0].manualExecuteBlocked, false);
  assert.equal(queue.items[0].autoExecuteBlocked, true);
  assert.equal(queue.items[0].batchExecuteBlocked, true);
  assert.equal(queue.items[0].executedAt, null);
  assert.equal(queue.items[0].autoExecutedAt, null);
  assert.equal(queue.items[0].execution, null);
  assert.match(queue.items[0].autoBlockedReason, /确认平台未执行/);

  const audit = simulations.at(-1);
  assert.equal(audit.manualResolution, RESOLUTION.CONFIRMED_NOT_EXECUTED);
  assert.equal(audit.manualExecuteBlocked, false);
  assert.equal(audit.batchExecuteBlocked, true);
  assert.equal(audit.executedAt, null);
  assert.equal(audit.autoExecutedAt, null);
  assert.equal(audit.execution, null);
  assert.match(audit.autoExecuteError, /确认平台未执行/);
});

test('unknown 人工归档保留强阻断，不允许普通手动/批量执行，并清理旧执行终态字段', () => {
  const { queue, simulations, recovery } = makeFixture();
  queue.items[0].executedAt = '2026-06-27T00:10:00.000Z';
  queue.items[0].autoExecutedAt = '2026-06-27T00:10:00.000Z';
  simulations[0].executedAt = '2026-06-27T00:10:00.000Z';
  simulations[0].autoExecutedAt = '2026-06-27T00:10:00.000Z';
  recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.UNKNOWN,
    operatorNote: '平台状态不明',
  });

  assert.equal(queue.items[0].status, 'simulated');
  assert.equal(queue.items[0].manualExecuteBlocked, true);
  assert.equal(queue.items[0].batchExecuteBlocked, true);
  assert.equal(queue.items[0].executedAt, null);
  assert.equal(queue.items[0].autoExecutedAt, null);
  assert.match(queue.items[0].autoBlockedReason, /状态不明/);

  const audit = simulations.at(-1);
  assert.equal(audit.manualResolution, RESOLUTION.UNKNOWN);
  assert.equal(audit.manualExecuteBlocked, true);
  assert.equal(audit.batchExecuteBlocked, true);
  assert.equal(audit.executedAt, null);
  assert.equal(audit.autoExecutedAt, null);
});

test('缺少 queue item 时拒绝 journal-only 归档', () => {
  const { journal } = makeFixture();
  const recovery = createAutoExecutionRecovery({
    journal,
    readQueue: () => ({ items: [] }),
    updateQueueItem: () => assert.fail('不应更新不存在的 queue'),
    readSimulations: () => [],
    appendSimulation: () => assert.fail('不应追加 simulation'),
    now: () => NOW,
  });

  assert.throws(() => recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_EXECUTED,
    operatorNote: '已确认',
  }), /缺少 queue item/);
  assert.equal(journal.read()[ORDER].status, STATUS.AUTO_EXECUTING);
});

test('simulation append 失败时不得把 journal 标成 manually_resolved', () => {
  const { journal, queue } = makeFixture();
  const recovery = createAutoExecutionRecovery({
    journal,
    readQueue: () => queue,
    updateQueueItem: (id, patch) => {
      const idx = queue.items.findIndex(item => item.id === id);
      queue.items[idx] = { ...queue.items[idx], ...patch };
      return queue.items[idx];
    },
    readSimulations: () => [],
    appendSimulation: () => { throw new Error('append failed'); },
    now: () => NOW,
  });

  assert.throws(() => recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_EXECUTED,
    operatorNote: '已确认',
  }), /append failed/);
  assert.equal(journal.read()[ORDER].status, STATUS.AUTO_EXECUTING);
});

test('journal resolve 失败不得宣称成功，重试不重复追加 audit simulation', () => {
  const { journal, queue, simulations } = makeFixture();
  let resolveCalls = 0;
  let appendCalls = 0;
  const guardedJournal = {
    read: () => journal.read(),
    resolveManual: (...args) => {
      resolveCalls += 1;
      if (resolveCalls === 1) throw new Error('journal write failed');
      return journal.resolveManual(...args);
    },
  };
  const recovery = createAutoExecutionRecovery({
    journal: guardedJournal,
    readQueue: () => queue,
    updateQueueItem: (id, patch) => {
      const idx = queue.items.findIndex(item => item.id === id);
      queue.items[idx] = { ...queue.items[idx], ...patch };
      return queue.items[idx];
    },
    readSimulations: () => simulations,
    appendSimulation: sim => {
      appendCalls += 1;
      simulations.push(sim);
    },
    now: () => NOW,
  });

  assert.throws(() => recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_NOT_EXECUTED,
    operatorNote: '第一次 journal 写失败',
  }), /journal write failed/);
  assert.equal(journal.read()[ORDER].status, STATUS.AUTO_EXECUTING);
  assert.equal(appendCalls, 1);

  const result = recovery.resolve({
    workOrderNum: ORDER,
    resolution: RESOLUTION.CONFIRMED_NOT_EXECUTED,
    operatorNote: '重试成功',
  });
  const audit = simulations.find(sim => sim.id === `auto-recovery-${ORDER}-${RESOLUTION.CONFIRMED_NOT_EXECUTED}`);
  assert.equal(result.journal.status, STATUS.MANUALLY_RESOLVED);
  assert.equal(result.journal.operatorNote, '第一次 journal 写失败');
  assert.equal(queue.items[0].manualResolutionNote, '第一次 journal 写失败');
  assert.equal(audit.manualResolutionNote, '第一次 journal 写失败');
  assert.equal(appendCalls, 1);
  assert.equal(simulations.filter(sim => sim.id === `auto-recovery-${ORDER}-${RESOLUTION.CONFIRMED_NOT_EXECUTED}`).length, 1);
});
