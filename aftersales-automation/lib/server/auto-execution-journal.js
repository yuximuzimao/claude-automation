'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_PATH = path.join(__dirname, '../../data/auto-execution-journal.json');
const UNFINISHED_INTENT_BLOCK_REASON = '存在未完成自动执行 intent，需人工复核';
const EXECUTED_BLOCK_REASON = '已有自动执行成功记录，禁止重复执行';
const MANUAL_RESOLUTION_BLOCK_REASON = '自动执行异常已人工归档，禁止自动重试';

const STATUS = Object.freeze({
  AUTO_EXECUTING: 'auto_executing',
  AUTO_EXECUTED: 'auto_executed',
  FAILED: 'failed',
  MANUALLY_RESOLVED: 'manually_resolved',
});

const PHASE = Object.freeze({
  RESERVED: 'reserved',
  PAGE_ACTION_STARTED: 'page_action_started',
  PAGE_ACTION_SUCCEEDED: 'page_action_succeeded',
  WRITEBACK_FAILED: 'writeback_failed',
});

const RESOLUTION = Object.freeze({
  CONFIRMED_EXECUTED: 'confirmed_executed',
  CONFIRMED_NOT_EXECUTED: 'confirmed_not_executed',
  UNKNOWN: 'unknown',
});

function nowIso(now = new Date()) {
  return now instanceof Date ? now.toISOString() : new Date(now).toISOString();
}

function historyEvent(event, extra = {}, now = new Date()) {
  return { at: nowIso(now), event, ...extra };
}

function appendHistory(record, event, extra = {}, now = new Date()) {
  return [
    ...((record && Array.isArray(record.history)) ? record.history : []),
    historyEvent(event, extra, now),
  ];
}

function isUnfinishedIntent(record) {
  return Boolean(record && record.status === STATUS.AUTO_EXECUTING);
}

function isAutoExecutedRecord(record) {
  return Boolean(record && record.status === STATUS.AUTO_EXECUTED);
}

function isManualResolutionBlocked(record) {
  if (!record || record.status !== STATUS.MANUALLY_RESOLVED) return false;
  return record.allowAutoRetry !== true;
}

function isFailedBlocked(record) {
  if (!record || record.status !== STATUS.FAILED) return false;
  return record.allowAutoRetry !== true;
}

function isExecutionBlocked(record) {
  return isUnfinishedIntent(record)
    || isAutoExecutedRecord(record)
    || isManualResolutionBlocked(record)
    || isFailedBlocked(record);
}

function getExecutionBlockReason(record) {
  if (isUnfinishedIntent(record)) return UNFINISHED_INTENT_BLOCK_REASON;
  if (isAutoExecutedRecord(record)) return EXECUTED_BLOCK_REASON;
  if (isManualResolutionBlocked(record)) return MANUAL_RESOLUTION_BLOCK_REASON;
  if (isFailedBlocked(record)) return MANUAL_RESOLUTION_BLOCK_REASON;
  return null;
}

function assertWorkOrderNum(workOrderNum) {
  const value = String(workOrderNum || '').trim();
  if (!value) throw new Error('缺少工单号');
  return value;
}

function assertResolution(resolution) {
  const value = String(resolution || '').trim();
  if (!Object.values(RESOLUTION).includes(value)) {
    throw new Error(`非法人工归档结论: ${resolution}`);
  }
  return value;
}

function assertOperatorNote(note) {
  const value = String(note || '').trim();
  if (!value) throw new Error('人工归档必须填写 operatorNote');
  return value;
}

function assertPhase(record, allowed, action, workOrderNum) {
  const phase = record && record.phase;
  if (!allowed.includes(phase)) {
    const actual = phase || 'legacy_missing_phase';
    throw new Error(`工单 ${workOrderNum} 当前 phase=${actual}，禁止执行 ${action}`);
  }
}

function defaultWriteAtomic(filePath, value) {
  const tmp = `${filePath}.${process.pid}.tmp`;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const fd = fs.openSync(tmp, 'w');
  try {
    fs.writeFileSync(fd, JSON.stringify(value, null, 2));
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  fs.renameSync(tmp, filePath);
  const dirFd = fs.openSync(path.dirname(filePath), 'r');
  try { fs.fsyncSync(dirFd); } finally { fs.closeSync(dirFd); }
}

function createAutoExecutionJournal(options = {}) {
  const filePath = options.filePath || DEFAULT_PATH;
  const readFile = options.readFile || (target => fs.readFileSync(target, 'utf8'));
  const writeAtomic = options.writeAtomic || (value => defaultWriteAtomic(filePath, value));
  const now = options.now || (() => new Date());
  const read = () => {
    try { return JSON.parse(readFile(filePath)); } catch (error) {
      if (error && error.code === 'ENOENT') return {};
      throw error;
    }
  };
  const write = value => writeAtomic(value);
  const withLock = options.withLock || (operation => {
    const lockPath = `${filePath}.lock`;
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    let fd;
    try {
      fd = fs.openSync(lockPath, 'wx');
    } catch (error) {
      if (error.code === 'EEXIST') throw new Error('自动执行日志正被其他进程更新，拒绝并发执行');
      throw error;
    }
    try { return operation(); } finally {
      fs.closeSync(fd);
      try { fs.unlinkSync(lockPath); } catch {}
    }
  });

  const updateRecord = (workOrderNum, updater) => withLock(() => {
    const num = assertWorkOrderNum(workOrderNum);
    const current = read();
    const record = current[num];
    const nextRecord = updater(record, num);
    const next = { ...current, [num]: nextRecord };
    write(next);
    return nextRecord;
  });

  return {
    read,
    getUnfinishedIntent(workOrderNum) {
      const current = read();
      const record = current[workOrderNum];
      return isUnfinishedIntent(record) ? record : null;
    },
    getBlockingRecord(workOrderNum) {
      const current = read();
      const record = current[workOrderNum];
      return isExecutionBlocked(record) ? { ...record, blockReason: getExecutionBlockReason(record) } : null;
    },
    reserve(workOrderNum, metadata = {}) {
      return updateRecord(workOrderNum, (record, num) => {
        if (isExecutionBlocked(record)) {
          throw new Error(`工单 ${num} 已有自动执行记录: ${record.status}`);
        }
        const reservedAt = nowIso(now());
        return {
          ...metadata,
          workOrderNum: num,
          status: STATUS.AUTO_EXECUTING,
          phase: PHASE.RESERVED,
          attemptId: metadata.attemptId || `auto-${Date.now()}-${num}`,
          reservedAt,
          allowAutoRetry: false,
          allowBatchExecute: false,
          history: [historyEvent('reserved', { phase: PHASE.RESERVED }, reservedAt)],
        };
      });
    },
    markPageActionStarted(workOrderNum) {
      return updateRecord(workOrderNum, (record, num) => {
        if (!isUnfinishedIntent(record)) throw new Error(`工单 ${num} 缺少 auto_executing intent`);
        assertPhase(record, [PHASE.RESERVED], 'markPageActionStarted', num);
        const stamp = now();
        return {
          ...record,
          phase: PHASE.PAGE_ACTION_STARTED,
          pageActionStartedAt: nowIso(stamp),
          history: appendHistory(record, 'page_action_started', { phase: PHASE.PAGE_ACTION_STARTED }, stamp),
        };
      });
    },
    markPageActionSucceeded(workOrderNum) {
      return updateRecord(workOrderNum, (record, num) => {
        if (!isUnfinishedIntent(record)) throw new Error(`工单 ${num} 缺少 auto_executing intent`);
        assertPhase(record, [PHASE.PAGE_ACTION_STARTED], 'markPageActionSucceeded', num);
        const stamp = now();
        return {
          ...record,
          phase: PHASE.PAGE_ACTION_SUCCEEDED,
          pageActionSucceededAt: nowIso(stamp),
          history: appendHistory(record, 'page_action_succeeded', { phase: PHASE.PAGE_ACTION_SUCCEEDED }, stamp),
        };
      });
    },
    markFailed(workOrderNum, failure = {}) {
      return updateRecord(workOrderNum, (record, num) => {
        if (!isUnfinishedIntent(record)) throw new Error(`工单 ${num} 缺少 auto_executing intent`);
        const phase = record.phase || PHASE.PAGE_ACTION_STARTED;
        const stamp = now();
        const failureMessage = String(failure.message || failure.failureMessage || '自动执行失败');
        const failureType = failure.failureType || (phase === PHASE.RESERVED ? 'pre_page_action_failed' : 'page_action_uncertain');
        const afterPageAction = phase !== PHASE.RESERVED;
        return {
          ...record,
          status: afterPageAction ? STATUS.AUTO_EXECUTING : STATUS.FAILED,
          phase: afterPageAction ? (failure.phase || PHASE.WRITEBACK_FAILED) : phase,
          failureType,
          failureMessage,
          failedAt: nowIso(stamp),
          requiresManualReview: afterPageAction,
          allowAutoRetry: false,
          allowBatchExecute: false,
          history: appendHistory(record, afterPageAction ? 'recovery_required' : 'failed', {
            phase: afterPageAction ? (failure.phase || PHASE.WRITEBACK_FAILED) : phase,
            failureType,
            failureMessage,
          }, stamp),
        };
      });
    },
    markExecuted(workOrderNum) {
      return updateRecord(workOrderNum, (record, num) => {
        if (!isUnfinishedIntent(record)) {
          throw new Error(`工单 ${num} 缺少 auto_executing intent`);
        }
        assertPhase(record, [PHASE.PAGE_ACTION_STARTED, PHASE.PAGE_ACTION_SUCCEEDED], 'markExecuted', num);
        const stamp = now();
        return {
          ...record,
          status: STATUS.AUTO_EXECUTED,
          phase: PHASE.PAGE_ACTION_SUCCEEDED,
          executedAt: nowIso(stamp),
          allowAutoRetry: false,
          allowBatchExecute: false,
          history: appendHistory(record, 'auto_executed', { phase: PHASE.PAGE_ACTION_SUCCEEDED }, stamp),
        };
      });
    },
    resolveManual(workOrderNum, { resolution, operatorNote, resolvedBy = 'manual', metadata = {} } = {}) {
      const finalResolution = assertResolution(resolution);
      const finalNote = assertOperatorNote(operatorNote);
      return updateRecord(workOrderNum, (record, num) => {
        if (!record) throw new Error(`工单 ${num} 缺少自动执行 journal 记录`);
        const stamp = now();
        return {
          ...record,
          ...metadata,
          workOrderNum: num,
          status: STATUS.MANUALLY_RESOLVED,
          resolution: finalResolution,
          resolvedAt: nowIso(stamp),
          resolvedBy,
          operatorNote: finalNote,
          allowAutoRetry: false,
          allowBatchExecute: false,
          history: appendHistory(record, 'manually_resolved', {
            resolution: finalResolution,
            operatorNote: finalNote,
          }, stamp),
        };
      });
    },
  };
}

module.exports = {
  createAutoExecutionJournal,
  defaultWriteAtomic,
  isUnfinishedIntent,
  isExecutionBlocked,
  getExecutionBlockReason,
  UNFINISHED_INTENT_BLOCK_REASON,
  EXECUTED_BLOCK_REASON,
  MANUAL_RESOLUTION_BLOCK_REASON,
  STATUS,
  PHASE,
  RESOLUTION,
  DEFAULT_PATH,
};
