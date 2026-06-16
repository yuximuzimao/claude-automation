'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  classifySessionFailure,
  getAccountOpenGuard,
  normalizeAccountStatus,
} = require('../../lib/server/account-session-status');

test('ok account status remains ok even when last scan is old', () => {
  const now = Date.parse('2026-06-15T08:00:00.000Z');
  const status = normalizeAccountStatus({
    status: 'ok',
    lastScan: '2026-06-14T08:00:00.000Z',
  }, now);

  assert.equal(status.status, 'ok');
});

test('ok account status allows one checked open attempt', () => {
  const now = Date.parse('2026-06-15T08:00:00.000Z');
  const guard = getAccountOpenGuard({
    status: 'ok',
    lastScan: '2026-06-14T08:00:00.000Z',
  }, now);

  assert.equal(guard.ok, true);
  assert.equal(guard.status, 'ok');
});

test('expired account status blocks opening store backend before injecting', () => {
  const guard = getAccountOpenGuard({ status: 'expired', error: '登录已失效' });

  assert.equal(guard.ok, false);
  assert.equal(guard.status, 'expired');
  assert.match(guard.error, /重新登录/);
});

test('session expired message is classified as expired', () => {
  assert.equal(classifySessionFailure('账号 3 session 已失效（注入后仍跳转到登录页）'), 'expired');
});
