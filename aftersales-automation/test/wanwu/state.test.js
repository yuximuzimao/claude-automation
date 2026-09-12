'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { readState, writeState } = require('../../wanwu/state');

test('万物状态原子写入并读回验证', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wanwu-state-test-'));
  const filePath = path.join(dir, 'state.json');
  try {
    assert.equal(readState({ filePath }).status, 'never');
    const written = writeState({
      status: 'attention',
      message: '待发货 1',
      counts: { pendingShip: 1 },
      total: 1,
      lastAttemptAt: '2026-09-12T07:00:00.000Z',
    }, { filePath });
    assert.equal(written.status, 'attention');
    assert.equal(readState({ filePath }).counts.pendingShip, 1);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
