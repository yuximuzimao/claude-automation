const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  readSessionState,
  saveSessionState,
  isSameFreshSession,
} = require('../../lib/jl-session-state');

test('saveSessionState records the account that actually owns the current JL tab', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'jl-session-state-'));
  const file = path.join(dir, 'current-session.json');

  saveSessionState(file, 13, 123456);

  assert.deepEqual(readSessionState(file), { accountNum: 13, at: 123456 });
  assert.equal(isSameFreshSession(file, 13, 1000, 123999), true);
  assert.equal(isSameFreshSession(file, 3, 1000, 123999), false);
});
