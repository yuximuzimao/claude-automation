'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const BASE = path.join(__dirname, '../..');
const HUD_SCRIPT = path.join(BASE, 'scripts/scan-status-hud.js');
const STATUS_DIR = path.join(os.tmpdir(), 'aftersales-scan-hud');
const DEFAULT_COUNTDOWN_SECONDS = 10;
const DEFAULT_CLOSE_AFTER_MS = 5000;

function ensureStatusDir() {
  fs.mkdirSync(STATUS_DIR, { recursive: true });
}

function getStatusPath(sessionId) {
  return path.join(STATUS_DIR, `${sessionId}.json`);
}

function readStatus(sessionId) {
  if (!sessionId) return null;
  try {
    return JSON.parse(fs.readFileSync(getStatusPath(sessionId), 'utf8'));
  } catch {
    return null;
  }
}

function writeStatusFile(filePath, status) {
  ensureStatusDir();
  const tmpPath = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(tmpPath, JSON.stringify(status, null, 2));
  fs.renameSync(tmpPath, filePath);
}

function launchHud(filePath, spawnImpl = spawn) {
  if (process.platform !== 'darwin') return { launched: false, reason: 'unsupported-platform' };
  try {
    const child = spawnImpl('/usr/bin/osascript', ['-l', 'JavaScript', HUD_SCRIPT, filePath], {
      detached: true,
      stdio: 'ignore',
    });
    if (child && typeof child.once === 'function') {
      child.once('error', err => {
        console.error(`[scan-hud] 状态窗启动失败: ${err.message}`);
      });
    }
    if (child && typeof child.unref === 'function') child.unref();
    return { launched: true, pid: child && child.pid };
  } catch (err) {
    console.error(`[scan-hud] 状态窗启动失败: ${err.message}`);
    return { launched: false, reason: err.message };
  }
}

function createSession(options = {}) {
  const countdownSeconds = Number.isFinite(Number(options.countdownSeconds))
    ? Math.max(0, Math.round(Number(options.countdownSeconds)))
    : DEFAULT_COUNTDOWN_SECONDS;
  const sessionId = options.sessionId || `scan-${Date.now()}-${process.pid}`;
  const filePath = getStatusPath(sessionId);
  const now = Date.now();
  const status = {
    sessionId,
    phase: 'countdown',
    title: '售后自动扫描',
    status: `${countdownSeconds} 秒后开始工单自动扫描`,
    detail: '请暂存当前工作，并暂时停止鼠标键盘操作。',
    countdownUntil: now + countdownSeconds * 1000,
    shopIndex: 0,
    shopTotal: 0,
    remainingShops: 0,
    shopName: null,
    ticketIndex: 0,
    ticketTotal: 0,
    workOrderNum: null,
    processedTickets: 0,
    accountErrors: 0,
    heartbeatAt: now,
  };
  writeStatusFile(filePath, status);
  const launch = launchHud(filePath, options.spawnImpl);
  return { sessionId, filePath, countdownSeconds, ...launch };
}

function updateSession(sessionId, patch = {}) {
  if (!sessionId) return false;
  const current = readStatus(sessionId);
  if (!current) return false;
  const next = {
    ...current,
    ...patch,
    sessionId,
    heartbeatAt: Date.now(),
  };
  writeStatusFile(getStatusPath(sessionId), next);
  return true;
}

function finishSession(sessionId, options = {}) {
  if (!sessionId) return false;
  const phase = options.phase || 'done';
  return updateSession(sessionId, {
    ...options,
    phase,
    finishedAt: Date.now(),
    closeAfterMs: options.closeAfterMs == null ? DEFAULT_CLOSE_AFTER_MS : options.closeAfterMs,
  });
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = {
  DEFAULT_COUNTDOWN_SECONDS,
  DEFAULT_CLOSE_AFTER_MS,
  createSession,
  updateSession,
  finishSession,
  readStatus,
  getStatusPath,
  wait,
  _private: {
    launchHud,
    writeStatusFile,
    STATUS_DIR,
    HUD_SCRIPT,
  },
};
