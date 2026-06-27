'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_PATH = path.join(__dirname, '../../data/auto-execution-journal.json');
const UNFINISHED_INTENT_BLOCK_REASON = '存在未完成自动执行 intent，需人工复核';

function isUnfinishedIntent(record) {
  return Boolean(record && record.status === 'auto_executing');
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

  return {
    read,
    getUnfinishedIntent(workOrderNum) {
      const current = read();
      const record = current[workOrderNum];
      return isUnfinishedIntent(record) ? record : null;
    },
    reserve(workOrderNum, metadata = {}) {
      return withLock(() => {
        const current = read();
        if (current[workOrderNum] && ['auto_executing', 'auto_executed'].includes(current[workOrderNum].status)) {
          throw new Error(`工单 ${workOrderNum} 已有自动执行记录: ${current[workOrderNum].status}`);
        }
        const next = {
          ...current,
          [workOrderNum]: { ...metadata, workOrderNum, status: 'auto_executing', reservedAt: new Date().toISOString() },
        };
        write(next);
        return next[workOrderNum];
      });
    },
    markExecuted(workOrderNum) {
      return withLock(() => {
        const current = read();
        if (!current[workOrderNum] || current[workOrderNum].status !== 'auto_executing') {
          throw new Error(`工单 ${workOrderNum} 缺少 auto_executing intent`);
        }
        const next = {
          ...current,
          [workOrderNum]: { ...current[workOrderNum], status: 'auto_executed', executedAt: new Date().toISOString() },
        };
        write(next);
        return next[workOrderNum];
      });
    },
  };
}

module.exports = {
  createAutoExecutionJournal,
  defaultWriteAtomic,
  isUnfinishedIntent,
  UNFINISHED_INTENT_BLOCK_REASON,
  DEFAULT_PATH,
};
