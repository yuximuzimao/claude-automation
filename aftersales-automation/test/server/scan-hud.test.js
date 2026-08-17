'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const scanHud = require('../../lib/server/scan-hud');

function fakeSpawn() {
  return {
    pid: 4242,
    once() {},
    unref() {},
  };
}

function cleanup(sessionId) {
  try { fs.unlinkSync(scanHud.getStatusPath(sessionId)); } catch {}
}

test('scan HUD session persists countdown, live progress, and terminal state', () => {
  const sessionId = `test-${process.pid}-${Date.now()}`;
  try {
    const created = scanHud.createSession({
      sessionId,
      countdownSeconds: 10,
      spawnImpl: fakeSpawn,
    });
    assert.equal(created.sessionId, sessionId);

    const countdown = scanHud.readStatus(sessionId);
    assert.equal(countdown.phase, 'countdown');
    assert.equal(countdown.shopIndex, 0);
    assert.equal(countdown.accountErrors, 0);
    assert.ok(countdown.countdownUntil > Date.now());

    assert.equal(scanHud.updateSession(sessionId, {
      phase: 'running',
      shopIndex: 3,
      shopTotal: 8,
      remainingShops: 5,
      shopName: '澜泽',
      ticketIndex: 3,
      ticketTotal: 10,
      workOrderNum: '100001',
      processedTickets: 7,
    }), true);

    const running = scanHud.readStatus(sessionId);
    assert.equal(running.phase, 'running');
    assert.equal(running.shopName, '澜泽');
    assert.equal(running.ticketIndex, 3);
    assert.equal(running.ticketTotal, 10);
    assert.equal(running.remainingShops, 5);

    assert.equal(scanHud.finishSession(sessionId, {
      phase: 'completed_with_errors',
      status: '扫描完成，1 个店铺出现异常',
      accountErrors: 1,
      processedTickets: 9,
      closeAfterMs: 500,
    }), true);

    const finished = scanHud.readStatus(sessionId);
    assert.equal(finished.phase, 'completed_with_errors');
    assert.equal(finished.accountErrors, 1);
    assert.equal(finished.processedTickets, 9);
    assert.equal(finished.closeAfterMs, 500);
    assert.ok(finished.finishedAt > 0);
  } finally {
    cleanup(sessionId);
  }
});

test('terminal updates preserve the latest live progress when counts are omitted', () => {
  const sessionId = `test-error-${process.pid}-${Date.now()}`;
  try {
    scanHud.createSession({ sessionId, countdownSeconds: 10, spawnImpl: fakeSpawn });
    scanHud.updateSession(sessionId, {
      phase: 'running',
      shopIndex: 4,
      shopTotal: 8,
      remainingShops: 4,
      processedTickets: 12,
      accountErrors: 1,
    });
    scanHud.finishSession(sessionId, {
      phase: 'error',
      status: '本轮自动扫描因异常结束',
      error: 'ERP异常',
      closeAfterMs: 500,
    });

    const finished = scanHud.readStatus(sessionId);
    assert.equal(finished.shopIndex, 4);
    assert.equal(finished.shopTotal, 8);
    assert.equal(finished.processedTickets, 12);
    assert.equal(finished.accountErrors, 1);
  } finally {
    cleanup(sessionId);
  }
});

test('scan HUD update is a no-op for an unknown session', () => {
  assert.equal(scanHud.updateSession('missing-scan-hud-session', { phase: 'running' }), false);
  assert.equal(scanHud.finishSession('missing-scan-hud-session', { phase: 'done' }), false);
});
