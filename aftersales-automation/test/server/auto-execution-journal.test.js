'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
  createAutoExecutionJournal,
  isUnfinishedIntent,
  STATUS,
  PHASE,
  RESOLUTION,
  UNFINISHED_INTENT_BLOCK_REASON,
  EXECUTED_BLOCK_REASON,
  MANUAL_RESOLUTION_BLOCK_REASON,
} = require('../../lib/server/auto-execution-journal');

function tmpJournal(prefix = 'auto-journal-') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  const filePath = path.join(dir, 'journal.json');
  return { filePath, journal: createAutoExecutionJournal({ filePath }) };
}

test('auto_executing intent持久化后重复reserve被阻断，成功后更新executed', () => {
  const { journal } = tmpJournal();
  const rec = journal.reserve('100001781188621717210', { accountNote: '顺链' });
  assert.equal(rec.status, STATUS.AUTO_EXECUTING);
  assert.equal(rec.phase, PHASE.RESERVED);
  assert.equal(rec.allowAutoRetry, false);
  assert.equal(rec.allowBatchExecute, false);
  assert.equal(rec.history[0].event, 'reserved');

  assert.throws(() => journal.reserve('100001781188621717210', {}), /已有自动执行记录/);
  journal.markPageActionStarted('100001781188621717210');
  journal.markExecuted('100001781188621717210');
  const executed = journal.read()['100001781188621717210'];
  assert.equal(executed.status, STATUS.AUTO_EXECUTED);
  assert.equal(executed.phase, PHASE.PAGE_ACTION_SUCCEEDED);
  assert.equal(Boolean(executed.executedAt), true);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /已有自动执行记录/);
});

test('未完成intent可被只读识别，markExecuted后不再视为残留', () => {
  const { journal } = tmpJournal('auto-journal-unfinished-');
  journal.reserve('100001781188621717210', { accountNote: '顺链' });

  const unfinished = journal.getUnfinishedIntent('100001781188621717210');
  assert.equal(unfinished.status, STATUS.AUTO_EXECUTING);
  assert.equal(isUnfinishedIntent(unfinished), true);

  journal.markPageActionStarted('100001781188621717210');
  journal.markExecuted('100001781188621717210');
  assert.equal(journal.getUnfinishedIntent('100001781188621717210'), null);
  assert.equal(isUnfinishedIntent(journal.read()['100001781188621717210']), false);
});

test('blocking record 覆盖 unfinished、executed、manual resolved 和 failed', () => {
  const { journal } = tmpJournal('auto-journal-blocking-');
  journal.reserve('wo-unfinished', {});
  assert.equal(journal.getBlockingRecord('wo-unfinished').blockReason, UNFINISHED_INTENT_BLOCK_REASON);

  journal.reserve('wo-executed', {});
  journal.markPageActionStarted('wo-executed');
  journal.markExecuted('wo-executed');
  assert.equal(journal.getBlockingRecord('wo-executed').blockReason, EXECUTED_BLOCK_REASON);

  journal.reserve('wo-failed', {});
  journal.markFailed('wo-failed', { message: '依赖缺失' });
  assert.equal(journal.getBlockingRecord('wo-failed').blockReason, MANUAL_RESOLUTION_BLOCK_REASON);

  journal.reserve('wo-manual', {});
  journal.resolveManual('wo-manual', {
    resolution: RESOLUTION.CONFIRMED_NOT_EXECUTED,
    operatorNote: '人工确认未执行',
  });
  assert.equal(journal.getBlockingRecord('wo-manual').blockReason, MANUAL_RESOLUTION_BLOCK_REASON);
});

test('page action phase 流转后失败保持 unresolved 并要求人工复核', () => {
  const { journal } = tmpJournal('auto-journal-phase-');
  journal.reserve('100001781188621717210', {});
  const started = journal.markPageActionStarted('100001781188621717210');
  assert.equal(started.phase, PHASE.PAGE_ACTION_STARTED);
  assert.equal(Boolean(started.pageActionStartedAt), true);

  const failed = journal.markFailed('100001781188621717210', { message: 'CDP timeout' });
  assert.equal(failed.status, STATUS.AUTO_EXECUTING);
  assert.equal(failed.phase, PHASE.WRITEBACK_FAILED);
  assert.equal(failed.requiresManualReview, true);
  assert.equal(failed.failureType, 'page_action_uncertain');
  assert.equal(journal.getBlockingRecord('100001781188621717210').blockReason, UNFINISHED_INTENT_BLOCK_REASON);
});

test('reserve阶段失败可进入 failed 但仍不允许自动重试', () => {
  const { journal } = tmpJournal('auto-journal-pre-action-fail-');
  journal.reserve('100001781188621717210', {});
  const failed = journal.markFailed('100001781188621717210', { message: '本地依赖缺失' });
  assert.equal(failed.status, STATUS.FAILED);
  assert.equal(failed.phase, PHASE.RESERVED);
  assert.equal(failed.requiresManualReview, false);
  assert.equal(failed.allowAutoRetry, false);
  assert.equal(journal.getBlockingRecord('100001781188621717210').blockReason, MANUAL_RESOLUTION_BLOCK_REASON);
});

test('phase 只能按 reserved -> page_action_started -> page_action_succeeded 推进', () => {
  const { journal } = tmpJournal('auto-journal-phase-order-');
  journal.reserve('100001781188621717210', {});
  assert.throws(() => journal.markPageActionSucceeded('100001781188621717210'), /phase=reserved/);
  assert.throws(() => journal.markExecuted('100001781188621717210'), /phase=reserved/);
  journal.markPageActionStarted('100001781188621717210');
  assert.throws(() => journal.markPageActionStarted('100001781188621717210'), /phase=page_action_started/);
  journal.markPageActionSucceeded('100001781188621717210');
  assert.throws(() => journal.markPageActionStarted('100001781188621717210'), /phase=page_action_succeeded/);
});

test('人工归档要求 resolution 和 operatorNote，且不重新放开自动执行', () => {
  const { journal } = tmpJournal('auto-journal-manual-');
  journal.reserve('100001781188621717210', {});
  assert.throws(() => journal.resolveManual('100001781188621717210', { resolution: RESOLUTION.UNKNOWN }), /operatorNote/);
  assert.throws(() => journal.resolveManual('100001781188621717210', { resolution: 'retry', operatorNote: 'x' }), /非法/);

  const resolved = journal.resolveManual('100001781188621717210', {
    resolution: RESOLUTION.UNKNOWN,
    operatorNote: '人工也无法确认平台状态',
  });
  assert.equal(resolved.status, STATUS.MANUALLY_RESOLVED);
  assert.equal(resolved.resolution, RESOLUTION.UNKNOWN);
  assert.equal(resolved.allowAutoRetry, false);
  assert.equal(resolved.allowBatchExecute, false);
  assert.equal(journal.getBlockingRecord('100001781188621717210').blockReason, MANUAL_RESOLUTION_BLOCK_REASON);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /已有自动执行记录/);
});

test('旧格式 auto_executing 无 phase 时按未完成高风险残留处理，且不允许继续推进页面动作', () => {
  const { filePath, journal } = tmpJournal('auto-journal-legacy-');
  fs.writeFileSync(filePath, JSON.stringify({ legacy: { status: STATUS.AUTO_EXECUTING, workOrderNum: 'legacy' } }));
  const blocked = journal.getBlockingRecord('legacy');
  assert.equal(blocked.blockReason, UNFINISHED_INTENT_BLOCK_REASON);
  assert.equal(blocked.phase, undefined);
  assert.throws(() => journal.markPageActionStarted('legacy'), /legacy_missing_phase/);
  assert.throws(() => journal.markPageActionSucceeded('legacy'), /legacy_missing_phase/);
  const resolved = journal.resolveManual('legacy', {
    resolution: RESOLUTION.UNKNOWN,
    operatorNote: '旧记录缺少 phase，只能人工归档',
  });
  assert.equal(resolved.status, STATUS.MANUALLY_RESOLVED);
});

test('原子写失败时reserve抛错且不得产生可见intent', () => {
  const journal = createAutoExecutionJournal({
    filePath: '/tmp/not-used.json',
    writeAtomic: () => { throw new Error('fsync失败'); },
  });
  assert.throws(() => journal.reserve('100001781188621717210', {}), /fsync失败/);
  assert.deepEqual(journal.read(), {});
});

test('日志JSON损坏时read和reserve均抛错，不得覆盖原文件', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'auto-journal-bad-'));
  const filePath = path.join(dir, 'journal.json');
  fs.writeFileSync(filePath, '{broken');
  const journal = createAutoExecutionJournal({ filePath });
  assert.throws(() => journal.read(), /JSON|Unexpected/);
  assert.throws(() => journal.getUnfinishedIntent('100001781188621717210'), /JSON|Unexpected/);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /JSON|Unexpected/);
  assert.equal(fs.readFileSync(filePath, 'utf8'), '{broken');
});

test('日志读取EIO时抛错，不得视为空日志', () => {
  const error = Object.assign(new Error('disk I/O error'), { code: 'EIO' });
  const journal = createAutoExecutionJournal({ filePath: '/tmp/not-used-journal.json', readFile: () => { throw error; } });
  assert.throws(() => journal.read(), /disk I\/O error/);
  assert.throws(() => journal.getUnfinishedIntent('100001781188621717210'), /disk I\/O error/);
  assert.throws(() => journal.reserve('100001781188621717210', {}), /disk I\/O error/);
});
