'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_STATE_FILE = path.join(__dirname, '../data/wanwu-scan-state.json');

function defaultState() {
  return {
    status: 'never',
    message: '等待扫描',
    counts: {},
    total: 0,
    summary: '',
    shortSummary: '',
    lastAttemptAt: null,
    lastSuccessAt: null,
    error: null,
  };
}

function normalizeState(input) {
  const source = input && typeof input === 'object' ? input : {};
  return {
    ...defaultState(),
    ...source,
    counts: source.counts && typeof source.counts === 'object' ? source.counts : {},
  };
}

function readState(options = {}) {
  const filePath = options.filePath || DEFAULT_STATE_FILE;
  try {
    return normalizeState(JSON.parse(fs.readFileSync(filePath, 'utf8')));
  } catch (error) {
    if (error && error.code === 'ENOENT') return defaultState();
    return normalizeState({
      status: 'error',
      message: '状态读取失败',
      error: String(error && error.message || error).slice(0, 200),
    });
  }
}

function writeState(nextState, options = {}) {
  const filePath = options.filePath || DEFAULT_STATE_FILE;
  const normalized = normalizeState(nextState);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(tmpPath, JSON.stringify(normalized, null, 2));
  fs.renameSync(tmpPath, filePath);
  const readBack = readState({ filePath });
  if (readBack.status !== normalized.status || readBack.lastAttemptAt !== normalized.lastAttemptAt) {
    throw new Error('万物扫描状态写入后校验失败');
  }
  return readBack;
}

module.exports = {
  DEFAULT_STATE_FILE,
  defaultState,
  normalizeState,
  readState,
  writeState,
};
