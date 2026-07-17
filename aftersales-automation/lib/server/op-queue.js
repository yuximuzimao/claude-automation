'use strict';
/**
 * op-queue.js - 全局操作队列（串行化所有浏览器操作，防止 CDP 冲突）
 *
 * 所有涉及 Chrome 控制的操作（scan/collect/pipeline/reinfer/execute/open-ticket）
 * 必须通过 enqueue() 入队，由内部调度器严格串行执行。
 */

const { spawn } = require('child_process');
const path = require('path');
const db = require('./data');
const sse = require('./sse');
const { classifySessionFailure } = require('./account-session-status');
const { hasConfirmedReturn, REMIND_HOURS, RESCAN_INTERVAL_HOURS } = require('../constants');
const { extractShippedTrackings, createReminder } = require('../helpers');
const { expireStaleAlerts } = require('../jl/alerts');

const fs = require('fs');
const BASE = path.join(__dirname, '../..');
const SESSIONS_DIR = path.join(BASE, '../sessions');
const { assertAccountNum } = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');

// ── 当前注入账号状态（跨子进程共享，10分钟TTL）─────────────────────
const SESSION_STATE_FILE = path.join(BASE, 'data/current-session.json');
const SESSION_TTL_MS = 10 * 60 * 1000;
function readSessionState() {
  try { return JSON.parse(fs.readFileSync(SESSION_STATE_FILE, 'utf8')); } catch { return null; }
}
function saveSessionState(num) {
  try { fs.writeFileSync(SESSION_STATE_FILE, JSON.stringify({ accountNum: num, at: Date.now() })); } catch {}
}
function isSameSession(accountNum) {
  const s = readSessionState();
  return s && s.accountNum === accountNum && (Date.now() - s.at) < SESSION_TTL_MS;
}
const ACCOUNT_STATUS_FILE = path.join(BASE, 'data/account-status.json');

function readAccountStatus() {
  try { return JSON.parse(fs.readFileSync(ACCOUNT_STATUS_FILE, 'utf8')); } catch(e) { return {}; }
}
function writeAccountStatus(status) {
  fs.writeFileSync(ACCOUNT_STATUS_FILE, JSON.stringify(status, null, 2));
}
function updateAccountStatus(num, patch) {
  const s = readAccountStatus();
  const prev = s[String(num)] || {};
  const merged = Object.assign({}, prev, patch);
  if ((patch.status === 'ok' && !patch.error) || patch.error === null) {
    delete merged.error;
  }
  s[String(num)] = merged;
  writeAccountStatus(s);
  sse.broadcast('accounts-update', readAccountStatus());
}

let counter = 0;
const queue = [];
let running = null;
let lastCompleted = null;
let paused = false;
const trackedProcs = new Set();
let abortController = new AbortController();

const STOP_EVENT_FILE = path.join(BASE, 'data/emergency-stop.json');

function log(msg) { process.stdout.write(`[op-queue] ${msg}\n`); }

// ── 公共 API ──────────────────────────────────────────────────────

function enqueue(type, label, params) {
  const op = {
    id: `op-${Date.now()}-${++counter}`,
    type, label,
    params: params || {},
    status: 'queued', result: null,
    createdAt: new Date().toISOString(),
    startedAt: null, doneAt: null,
  };
  queue.push(op);
  log(`入队 [${op.id}] ${label}`);
  broadcast();
  processNext();
  return op;
}

function cancel(id) {
  // 取消排队中的操作
  const idx = queue.findIndex(op => op.id === id && op.status === 'queued');
  if (idx !== -1) {
    queue.splice(idx, 1);
    log(`取消 [${id}]`);
    broadcast();
    return true;
  }
  // 取消正在运行的操作
  if (running && running.id === id) {
    abortController.abort();
    abortController = new AbortController();
    killAllTrackedProcs();
    log(`强制停止运行中操作 [${id}]`);
    broadcast();
    return true;
  }
  return false;
}

function getState() {
  return { running, queued: queue.filter(op => op.status === 'queued'), lastCompleted, paused };
}

// ── 子进程跟踪与清理 ──────────────────────────────────────────────

function killAllTrackedProcs() {
  if (trackedProcs.size === 0) return;
  const procs = [...trackedProcs];
  log(`正在终止 ${procs.length} 个子进程...`);

  // 第一轮：SIGTERM
  for (const proc of procs) {
    try { proc.kill('SIGTERM'); } catch(e) { /* 已退出 */ }
  }

  // 等待 2 秒让进程优雅退出
  const deadline = Date.now() + 2000;
  while (Date.now() < deadline) {
    const alive = procs.filter(p => { try { p.kill(0); return true; } catch(e) { return false; } });
    if (alive.length === 0) { log('所有子进程已退出'); trackedProcs.clear(); return; }
    // busy-wait 太浪费，用同步 sleep 在 Node 不现实，这里依赖短超时
    break;
  }

  // 第二轮到点：SIGKILL 强制
  let forceKilled = 0;
  for (const proc of procs) {
    try { proc.kill('SIGKILL'); forceKilled++; } catch(e) { /* 已退出 */ }
  }
  if (forceKilled > 0) log(`强制终止 ${forceKilled} 个未响应子进程`);
  trackedProcs.clear();
}

function emergencyStop() {
  paused = true;
  const interrupted = running ? { id: running.id, type: running.type, label: running.label, startedAt: running.startedAt } : null;
  const clearedCount = queue.filter(op => op.status === 'queued').length;

  // 清空排队中的操作
  for (let i = queue.length - 1; i >= 0; i--) {
    if (queue[i].status === 'queued') queue.splice(i, 1);
  }

  // 中断当前正在运行的异步操作
  abortController.abort();
  abortController = new AbortController();

  // 终止所有子进程并验证
  killAllTrackedProcs();

  // 写 stop 事件到磁盘，供 server 重启时识别
  writeStopEvent(interrupted, clearedCount);

  log(`紧急停止${interrupted ? '（中断: ' + interrupted.label + '）' : ''}，清除 ${clearedCount} 个排队操作`);
  broadcast();
}

function resume() {
  // 清除 stop 事件标记
  clearStopEvent();
  paused = false; abortController = new AbortController(); log('恢复'); broadcast(); processNext();
}

// ── Stop 事件持久化 ──────────────────────────────────────────────

function writeStopEvent(interrupted, clearedCount) {
  try {
    fs.writeFileSync(STOP_EVENT_FILE, JSON.stringify({
      stoppedAt: new Date().toISOString(),
      interrupted: interrupted || null,
      clearedCount,
      queueEmpty: queue.length === 0,
      runningCleared: running === null || running.status === 'cancelled',
    }, null, 2));
  } catch(e) { log(`写入 stop 事件失败: ${e.message}`); }
}

function clearStopEvent() {
  try { if (fs.existsSync(STOP_EVENT_FILE)) fs.unlinkSync(STOP_EVENT_FILE); } catch(e) {}
}

function readStopEvent() {
  try { return JSON.parse(fs.readFileSync(STOP_EVENT_FILE, 'utf8')); } catch { return null; }
}

// ── Stop 后验证（供 routes 调用，返回验证结果给前端）──────────────

function verifyStopState() {
  const aliveProcs = [];
  // 检查是否有未退出的子进程（通过 pid 检测）
  for (const proc of trackedProcs) {
    try { proc.kill(0); aliveProcs.push(proc.pid); } catch(e) { /* 已退出 */ }
  }
  return {
    queueEmpty: queue.length === 0,
    runningCleared: !running || running.status === 'cancelled',
    aliveProcs: aliveProcs.length > 0 ? aliveProcs : null,
    paused,
    allClean: queue.length === 0 && (!running || running.status === 'cancelled') && aliveProcs.length === 0,
  };
}
function isPaused() { return paused; }
function isRunning() { return !!running; }

// ── 内部调度 ──────────────────────────────────────────────────────

function broadcast() { sse.broadcast('op-queue-update', getState()); }

function processNext() {
  if (running || paused) return;
  const next = queue.find(op => op.status === 'queued');
  if (!next) return;
  next.status = 'running'; next.startedAt = new Date().toISOString(); running = next;
  next._abortSignal = abortController.signal;
  log(`开始 [${next.id}] ${next.label}`); broadcast();
  executeOp(next).then(result => {
    next.status = 'done'; next.result = result; next.doneAt = new Date().toISOString();
    log(`完成 [${next.id}] ${next.label}`);
  }).catch(e => {
    if (e.name === 'AbortError' || (e.message || '').includes('操作已被用户停止')) {
      next.status = 'cancelled'; next.result = { error: '操作已被用户停止' }; next.doneAt = new Date().toISOString();
      log(`已停止 [${next.id}] ${next.label}`);
    } else {
      next.status = 'error'; next.result = { error: e.message }; next.doneAt = new Date().toISOString();
      if (next.type === 'execute' && next.params && next.params.simId) {
        try { db.updateSimulation(next.params.simId, { executeError: e.message }); } catch {}
      }
      log(`失败 [${next.id}] ${next.label}: ${e.message}`);
    }
  }).finally(() => {
    running = null; lastCompleted = next;
    const idx = queue.indexOf(next); if (idx !== -1) queue.splice(idx, 1);
    broadcast(); processNext();
  });
}

// ── 中断检查 ──────────────────────────────────────────────────────

function assertNotAborted(op) {
  if (op._abortSignal && op._abortSignal.aborted) {
    const err = new Error('操作已被用户停止');
    err.name = 'AbortError';
    throw err;
  }
}

// ── 执行分派 ──────────────────────────────────────────────────────

async function executeOp(op) {
  switch (op.type) {
    case 'scan':           return execScan(op);
    case 'scan-finalize':  return execScanFinalize(op);
    case 'open-account':   return execOpenAccount(op);
    case 'reinfer':        return execReinfer(op);
    case 'reprocess-one':  return execReprocessOne(op);
    case 'execute':        return execExecute(op);
    case 'open-ticket':    return execOpenTicket(op);
    case 'return-inbound': return execReturnInbound(op);
    case 'a1-fixed-batch': return execA1FixedBatch(op);
  }
}

// ── 各类操作实现 ──────────────────────────────────────────────────

// ── 退货入库 ──────────────────────────────────────────────────────

async function execReturnInbound(op) {
  const { processOne, findErpTarget } = require('../../../return-inbound/lib/workflow');
  const { erpNav } = require('../../../return-inbound/lib/navigate');
  const trackingNumbers = op.params.trackingNumbers;
  const total = trackingNumbers.length;

  // targetId 一次获取，整批复用
  let targetId;
  try {
    targetId = await findErpTarget();
  } catch(e) {
    sse.broadcast('ri-error', { error: e.message });
    throw e;
  }

  // 导航到售后工单新版
  const navResult = await erpNav(targetId, '售后工单新版');
  if (!navResult.success) {
    const err = 'ERP导航失败: ' + navResult.error;
    sse.broadcast('ri-error', { error: err });
    throw new Error(err);
  }

  const results = []; // 严格保持输入顺序

  for (let i = 0; i < total; i++) {
    assertNotAborted(op);
    const tracking = trackingNumbers[i];

    // 阶段1: 广播"正在处理"
    sse.broadcast('ri-progress', { total, done: i, current: tracking, phase: 'processing' });

    let status;
    try {
      status = await processOne(targetId, tracking);
    } catch(e) {
      status = '错误:' + e.message;
    }
    results.push({ tracking, status });

    // 阶段2: 广播"已完成本条"（只传 lastResult，不传全量）
    sse.broadcast('ri-progress', {
      total,
      done: i + 1,
      current: tracking,
      phase: 'completed',
      lastResult: { tracking, status },
    });
  }

  // 最终一次性传全量（按输入顺序）
  sse.broadcast('ri-done', { results });
  return { results };
}

function spawnAsync(cmd, args, opts) {
  return new Promise((resolve, reject) => {
    let stdout = '';
    const proc = spawn(cmd, args, { ...opts, stdio: ['ignore', 'pipe', 'inherit'] });
    trackedProcs.add(proc);
    proc.stdout.on('data', d => { stdout += d; });
    proc.on('close', code => { trackedProcs.delete(proc); resolve({ code, stdout }); });
    proc.on('error', err => { trackedProcs.delete(proc); reject(err); });
  });
}

// [removed-2026-06-16] 删除 execCheckSession：刷新状态全链路的一环（多账号连续注入检测=风控红线）。
// 配套删除 routes.js POST /accounts/refresh-status 与前端"刷新状态"按钮。

async function execOpenAccount(op) {
  assertNotAborted(op);
  const { accountNum, accountNote } = op.params;
  // 直接调用 openAccountFlow，与 execExecute/execReprocessOne 共用同一安全链路（2026-07-01 模块化）
  const { openAccountFlow } = require('../jl/open-account-flow');
  const out = await Promise.race([
    openAccountFlow(String(accountNum)),
    new Promise((_, reject) => setTimeout(() => reject(new Error('打开账号超时（90s）')), 90000)),
  ]);
  if (!out || !out.success) {
    const msg = ((out && out.error) || '未知错误').slice(0, 200);
    const status = classifySessionFailure(msg);
    updateAccountStatus(accountNum, {
      status,
      lastScan: new Date().toISOString(),
      error: msg,
      note: accountNote,
    });
    throw new Error(msg);
  }
  saveSessionState(accountNum);
  updateAccountStatus(accountNum, {
    status: 'ok',
    lastScan: new Date().toISOString(),
    error: null,
    note: accountNote,
  });
  return { accountNum, status: 'ok', action: out.action };
}

async function execA1FixedBatch(op) {
  assertNotAborted(op);
  const { processSingleAccountFixedBatch } = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const { accountNum, accountNote } = op.params;
  const note = accountNote || `账号${accountNum}`;
  return processSingleAccountFixedBatch(String(accountNum), {
    thresholdHours: 48,
    abortSignal: op._abortSignal,
    onTicketProgress: (item) => {
      sse.broadcast('ticket-progress', {
        accountNum: String(accountNum),
        note,
        workOrderNum: item.workOrderNum,
        status: item.status,
      });
    },
  });
}


// ── 巡检收尾 ─────────────────────────────────────────────────────

async function execScanFinalize(op) {
  assertNotAborted(op);
  const fs = require('fs');
  const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');
  try {
    fs.writeFileSync(SCAN_STATUS_FILE, JSON.stringify({
      scanning: false, lastScanAt: new Date().toISOString(), lastResult: null,
    }));
  } catch(e) {}

  await cleanReturnedIntercepts();
  assertNotAborted(op);

  // pending/collected/simulated：无条件重置为 pending
  const allLive = (db.readQueue().items || []).filter(i =>
    ['pending', 'collected', 'simulated'].includes(i.status) && i.mode === 'live'
  );
  for (const item of allLive) {
    if (item.status !== 'pending') db.updateQueueItem(item.id, { status: 'pending' });
  }

  // waiting：节流重置——距上次推理 ≥ RESCAN_INTERVAL_HOURS 才允许
  const waitingItems = (db.readQueue().items || []).filter(i =>
    i.status === 'waiting' && i.mode === 'live'
  );
  let waitingResetCount = 0;
  for (const item of waitingItems) {
    const allSims = db.readSimulations();
    const latestSim = [...allSims].reverse().find(s => s.queueItemId === item.id);
    const lastInferAt = latestSim?.decision?.inferredAt;
    const anchor = lastInferAt || item.collectDoneAt;
    if (!anchor) {
      db.updateQueueItem(item.id, { status: 'pending' });
      waitingResetCount++;
      continue;
    }
    const hoursSince = (Date.now() - new Date(anchor).getTime()) / 3600000;
    if (hoursSince >= RESCAN_INTERVAL_HOURS) {
      db.updateQueueItem(item.id, { status: 'pending' });
      waitingResetCount++;
    }
  }
  if (waitingResetCount) log(`waiting 节流重置: ${waitingResetCount}/${waitingItems.length}`);
  if (allLive.length) sse.broadcast('queue-update', { resetCount: allLive.length });

  const pending = (db.readQueue().items || []).filter(i =>
    i.status === 'pending' && i.mode === 'live'
  );
  // 按账号排序，同账号工单连续处理，减少注入切换次数
  pending.sort((a, b) => (a.accountNum || 0) - (b.accountNum || 0));
  assertNotAborted(op);
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    enqueue('reprocess-one', label, { queueItemId: item.id });
  }
  log(`巡检收尾：入队 ${pending.length} 条工单推理（已按账号排序）`);
  return { done: true, pipelineCount: pending.length };
}

async function execScan(op) {
  const { accounts: specifiedAccounts = [] } = op.params;

  const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');
  let accountsConfig = {};
  try { accountsConfig = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8')); } catch(e) {}
  const statusMap = readAccountStatus();

  let numsToScan = Object.keys(accountsConfig)
    .map(Number)
    .filter(n => {
      const statusOk = (statusMap[String(n)] || {}).status === 'ok';
      const scanOn = accountsConfig[String(n)]?.scanEnabled !== false;
      return statusOk && scanOn;
    })
    .sort((a, b) => a - b);
  if (specifiedAccounts.length > 0) {
    const specified = new Set(specifiedAccounts.map(Number));
    numsToScan = numsToScan.filter(n => specified.has(n));
  }

  const { processSingleAccountFixedBatch } = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const total = numsToScan.length;

  // 发 init 事件，前端初始化进度面板
  sse.broadcast('scan-progress', {
    type: 'init',
    accounts: numsToScan.map(n => ({
      num: n,
      note: (accountsConfig[String(n)] || {}).note || (accountsConfig[String(n)] || {}).name || `账号${n}`,
      status: 'pending',
    })),
  });

  for (let i = 0; i < total; i++) {
    assertNotAborted(op);
    const num = numsToScan[i];
    const cfg = accountsConfig[String(num)] || {};
    const note = cfg.note || cfg.name || `账号${num}`;

    sse.broadcast('scan-progress', { type: 'start', num, note, current: i + 1, total });
    try {
      const result = await processSingleAccountFixedBatch(String(num), {
        thresholdHours: 48,
        abortSignal: op._abortSignal,
        onTicketProgress: (item) => {
          sse.broadcast('ticket-progress', {
            accountNum: String(num),
            note,
            workOrderNum: item.workOrderNum,
            status: item.status,
          });
        },
      });
      const count = (result && result.items ? result.items.length : null);
      updateAccountStatus(num, { status: 'ok', lastScan: new Date().toISOString(), note });
      sse.broadcast('scan-progress', { type: 'done', num, note, count });
    } catch(e) {
      const isExpired = /登录已失效|login|sso|鲸灵标签页未找到/.test(e.message || '');
      updateAccountStatus(num, {
        status: isExpired ? 'expired' : 'error',
        error: (e.message || '').slice(0, 200),
        lastScan: new Date().toISOString(),
        note,
      });
      sse.broadcast('scan-progress', { type: 'error', num, note, error: (e.message || '').slice(0, 100) });
      console.error(`[execScan] 账号${num} 失败:`, e.message);
    }

    // 风控红线：账号之间间隔 ≥10s
    if (i < total - 1) {
      await new Promise(r => setTimeout(r, 10000));
    }
  }

  // 到期预警：检查队列中 waiting/simulated 等待人工处理的工单
  const queueItems = (db.readQueue().items || []).filter(i =>
    i.mode === 'live' && !['done', 'auto_executed', 'auto_executing'].includes(i.status)
  );
  for (const qi of queueItems) {
    if (!qi.deadlineAt) continue;
    const remainingHours = (new Date(qi.deadlineAt).getTime() - Date.now()) / 3600000;
    if (remainingHours > REMIND_HOURS || remainingHours <= 0) continue;
    const timeStr = remainingHours < 1 ? '<1小时' : `${Math.round(remainingHours)}小时`;
    const dl = new Date(qi.deadlineAt);
    const dlStr = `截止${(dl.getMonth()+1).toString().padStart(2,'0')}/${dl.getDate().toString().padStart(2,'0')} ${dl.getHours().toString().padStart(2,'0')}:${dl.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${qi.accountNote || ''} 工单${qi.workOrderNum} ${qi.type || ''} 剩余${timeStr} ${dlStr}`;
    if (!createReminder(title)) log(`[预警] Reminders 失败已降级通知: ${title}`);
  }

  sse.broadcast('accounts-update', readAccountStatus());

  // 扫描完成后清过期的平台提醒（未扫描账号超过 24h → 清空）
  expireStaleAlerts(numsToScan);

  return { ok: true, scanned: total };
}

// ── 拦截记录清理 ─────────────────────────────────────────────────

async function cleanReturnedIntercepts() {
  const map = db.readIntercepts();
  const trackings = Object.keys(map);
  if (!trackings.length) return;

  let cleaned = 0;
  for (const tracking of trackings) {
    const rec = map[tracking];
    const age = Date.now() - new Date(rec.executedAt).getTime();
    if (age > db.INTERCEPT_TTL_MS) { db.removeIntercept(tracking); log(`[intercept-clean] ${tracking} 超7天过期，已清除`); cleaned++; }
  }

  const { getTargetIds } = require('../targets');
  const { erpSearch } = require('../erp/search');
  let erpId;
  try { const ids = await getTargetIds(); erpId = ids.erpId; }
  catch(e) { log(`[intercept-clean] 无法获取 ERP target: ${e.message}`); if (cleaned > 0) log(`[intercept-clean] 共清除 ${cleaned} 条过期记录`); return; }

  const remaining = Object.keys(db.readIntercepts());
  for (const tracking of remaining) {
    try {
      const res = await erpSearch(erpId, tracking, { validatePlatformOrderId: false });
      if (!res.success) { log(`[intercept-clean] ERP 查 ${tracking} 失败: ${res.error}`); continue; }
      const rows = res.data && res.data.rows && res.data.rows.rows || [];
      const hasReturned = rows.some(r => hasConfirmedReturn(r.textSnippet));
      if (hasReturned) { db.removeIntercept(tracking); log(`[intercept-clean] ${tracking} ERP显示已退回，已清除`); cleaned++; }
      else log(`[intercept-clean] ${tracking} 未退回，保留`);
    } catch(e) { log(`[intercept-clean] 查询 ${tracking} 异常: ${e.message}`); }
  }
  if (cleaned > 0) log(`[intercept-clean] 共清除 ${cleaned} 条拦截记录`);
  else log(`[intercept-clean] 检查完毕，无需清除`);
}

async function execReinfer(op) {
  assertNotAborted(op);
  const { simId, hint = '' } = op.params;
  const sim = db.getSimulation(simId);
  if (!sim) throw new Error('simulation 未找到: ' + simId);
  // 将用户输入的评价指令写入 queue item，同时清除旧 pipeline 残留的自动 hint
  db.updateQueueItem(sim.queueItemId, { hint: hint || null });
  // 复用 execReprocessOne 的完整 A1 安全链路（openAccountFlow → 定位 → 点击 → 采集 → 推理）
  return execReprocessOne({ params: { queueItemId: sim.queueItemId }, _abortSignal: op._abortSignal });
}

async function execReprocessOne(op) {
  const { queueItemId } = op.params;

  const queueItem = (db.readQueue().items || []).find(i => i.id === queueItemId);
  if (!queueItem) throw new Error('未找到队列项');
  if (['auto_executed', 'done'].includes(queueItem.status)) {
    return { skipped: true, reason: '已执行完成，跳过重新采集' };
  }

  const accountNum = assertAccountNum(queueItem.accountNum);

  const cdp = require('../cdp');
  const { openAccountFlow } = require('../jl/open-account-flow');
  const { sleep, waitFor } = require('../wait');

  // ── Step 1: 安全打开账号 ──────────────────────────────────────────
  const accountResult = await openAccountFlow(accountNum);
  if (!accountResult || !accountResult.success) {
    throw new Error(`打开账号失败: ${(accountResult && accountResult.error) || '未知错误'}`);
  }
  saveSessionState(accountNum);
  const listTargetId = accountResult.targetId;
  assertNotAborted(op);

  // ── Step 2: 导航到售后列表页并排序（不读全量列表，只做页面准备）───
  const step11 = require('../../scripts/jl-steps/11-prepare-after-sale-list');

  await cdp.navigate(listTargetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
  await sleep(step11.AFTER_NAVIGATION_WAIT_MS);
  await step11.assertAfterSaleListReady(listTargetId);
  const { selectOverdueSort } = require('../../scripts/jl-steps/09-select-overdue-sort');
  await selectOverdueSort({ targetId: listTargetId });
  await sleep(step11.AFTER_SORT_WAIT_MS);
  await step11.readCurrentPageSortCheck(listTargetId);
  assertNotAborted(op);

  // ── Step 3: 定位工单（与执行操作完全一致的寻址逻辑）───────────────
  const step10 = require('../../scripts/jl-steps/10-read-urgent-after-sale-list');
  const step14 = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const { clickWorkOrderAction } = require('../../scripts/jl-steps/12-click-work-order-action');

  const readCurrentPage = async (targetId) => {
    const raw = await cdp.eval(targetId, step10.READ_CURRENT_PAGE_TICKETS_JS);
    return {
      tickets: (raw && raw.tickets) || [],
      loading: Boolean(raw && raw.loading),
      pagination: step10.normalizePaginationState(raw && raw.pagination),
    };
  };
  const waitForPage = step14.createWaitForPage(waitFor);

  // prepareAfterSaleList 读完后分页可能停在最后一页，先回到第 1 页
  await step14.clickPageOneLikeHuman(listTargetId, {
    readCurrentPage, sleep, waitForPage,
    dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(listTargetId, event),
    eval: (id, js) => cdp.eval(id, js),
  });

  const located = await step14.locateWorkOrderOnFreshList(listTargetId, queueItem.workOrderNum, {
    readCurrentPage,
    clickPageOne: (id) => step14.clickPageOneLikeHuman(id, {
      readCurrentPage, sleep, waitForPage,
      dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(id, event),
      eval: (id, js) => cdp.eval(id, js),
    }),
    clickNextPage: step10.clickNextPage,
    waitForPage,
  });
  if (!located || !located.found) {
    throw new Error(`工单 ${queueItem.workOrderNum} 已不在待处理列表（可能已处理或已关闭）`);
  }
  assertNotAborted(op);

  // Step 4: 点击处理按钮，打开详情 tab
  const opened = await clickWorkOrderAction(queueItem.workOrderNum, { targetId: listTargetId });
  if (!opened || !opened.success || !opened.newTargetId) {
    throw new Error(`打开工单失败: ${(opened && opened.error) || '未识别到新标签页'}`);
  }
  const detailTargetId = opened.newTargetId;

  // 等待详情页 Vue 组件完全渲染
  await sleep(2000);
  assertNotAborted(op);

  // ── Step 5: 采集 + 推理 + 自动执行（step 14 processOpenedDetail 完整链路）──
  const { inferDecision } = require('../infer');
  const { collectTicketTargetAware, resolveUniqueErpTargetId } = require('../jl/target-aware-collector');
  const { shouldAutoExecute } = require('../server/auto-exec-confidence');
  const { createAutoExecutionJournal } = require('../server/auto-execution-journal');
  const { approveTicket } = require('../jl/approve');
  const { rejectTicket } = require('../jl/reject');
  const fs = require('fs');

  const erpTargetId = await resolveUniqueErpTargetId({ getTargets: cdp.getTargets }, null);
  const ticket = {
    workOrderNum: queueItem.workOrderNum,
    type: queueItem.type,
    accountNote: queueItem.accountNote || accountResult.matchedNote || '',
  };

  const circuitFile = path.join(BASE, 'data/circuit-breaker.json');
  const readCircuit = () => { try { return JSON.parse(fs.readFileSync(circuitFile, 'utf8')); } catch { return null; } };
  const executionJournal = createAutoExecutionJournal();

  const processed = await step14.processOpenedDetail({
    account: accountResult,
    listTargetId,
    detailTargetId,
    erpTargetId,
    ticket,
  }, {
    collectDetail: (ctx) => collectTicketTargetAware({
      detailTargetId: ctx.detailTargetId,
      erpTargetId: ctx.erpTargetId,
      workOrderNum: ctx.ticket.workOrderNum,
      accountNote: ctx.account.matchedNote || ctx.ticket.accountNote || '',
      type: ctx.ticket.type,
    }),
    inferDecision: (collectedData) => inferDecision({ collectedData }, queueItem),
    shouldAutoExecute,
    assertAutoExecutionAllowed: step14.createAutoExecutionGate({
      readCircuit,
      executionJournal,
      readSimulations: () => db.readSimulations(),
    }),
    executeDecision: async ({ detailTargetId: dtId, ticket: t, decision }) => {
      if (decision && decision.action === 'approve') return approveTicket(dtId, t.workOrderNum);
      if (decision && decision.action === 'reject') {
        return rejectTicket(dtId, t.workOrderNum,
          decision.rejectReason || decision.reason,
          decision.rejectDetail || decision.rejectReason || decision.reason,
          decision.imageUrl || null);
      }
      throw new Error(`不支持自动执行动作: ${decision && decision.action}`);
    },
    reserveAutoExecution: async ({ ticket: t, decision }) => executionJournal.reserve(t.workOrderNum, {
      accountNote: accountResult.matchedNote || '', decisionAction: decision.action,
    }),
    markPageActionStarted: async ({ ticket: t }) => executionJournal.markPageActionStarted(t.workOrderNum),
    markPageActionSucceeded: async ({ ticket: t }) => executionJournal.markPageActionSucceeded(t.workOrderNum),
    markAutoExecuted: async ({ ticket: t }) => executionJournal.markExecuted(t.workOrderNum),
  });

  // ── 写回结果 ──────────────────────────────────────────────────
  const now = new Date().toISOString();
  const sim = {
    id: `reprocess-${Date.now()}-${queueItem.workOrderNum}`,
    workOrderNum: queueItem.workOrderNum,
    queueItemId: queueItem.id,
    accountNum,
    accountNote: queueItem.accountNote || accountResult.matchedNote || '',
    mode: 'live',
    source: 'reprocess',
    collectedData: processed.collectedData,
    decision: processed.decision,
    createdAt: now,
  };
  if (processed.status === 'auto_executed') {
    sim.executedAt = now;
    sim.autoExecutedAt = now;
    sim.execution = processed.execution;
  }
  if (processed.autoBlockedReason) sim.autoBlockedReason = processed.autoBlockedReason;
  db.appendSimulation(sim);

  const queueStatus = step14.statusForProcessed(processed, queueItem);
  db.updateQueueItem(queueItem.id, {
    status: queueStatus,
    waitingRescan: !!(processed.decision && processed.decision.waitingRescan),
  });

  log(`[${queueItem.workOrderNum}] 重新采集推理完成 → ${processed.decision.action}${processed.status === 'auto_executed' ? ' (已自动执行)' : processed.decision.waitingRescan ? ' (等待重查)' : ''}`);

  let detailClosed = false;
  try { /* finally will close */ } finally {
    // Step 6: 关闭详情 tab（无论成功失败）
    try {
      const { readShopName } = require('../../scripts/jl-steps/02-read-shop-name');
      await step14.closeAndVerifyDetailTarget(detailTargetId, {
        getTargets: cdp.getTargets, closeTarget: cdp.closeTarget, sleep,
        readShopName: (id, waitMs) => readShopName(id, waitMs),
      }, { account: accountResult, listTargetId });
      detailClosed = true;
    } catch(e) { log(`[reprocess] 关闭详情 tab 失败（非致命）: ${e.message}`); }
  }

  return { done: true };
}

async function execExecute(op) {
  const { simId, rejectReason, rejectDetail, rejectImageUrl, fromBatch } = op.params;
  const sim = db.getSimulation(simId);
  if (!sim) throw new Error('simulation 未找到: ' + simId);
  if (sim.executedAt) return { skipped: true, reason: '已执行过' };

  const queueItem = (db.readQueue().items || []).find(i => i.id === sim.queueItemId);
  if (!queueItem) return { skipped: true, reason: '队列项不存在' };
  if (queueItem.status === 'waiting') return { skipped: true, reason: '工单处于等待重查状态，跳过执行' };

  const accountNum = assertAccountNum(queueItem.accountNum);

  const cdp = require('../cdp');
  const { openAccountFlow } = require('../jl/open-account-flow');
  const { sleep, waitFor } = require('../wait');

  // ── Step 1: 安全打开账号 ──────────────────────────────────────────
  const accountResult = await openAccountFlow(accountNum);
  if (!accountResult || !accountResult.success) {
    throw new Error(`打开账号失败: ${(accountResult && accountResult.error) || '未知错误'}`);
  }
  saveSessionState(accountNum);
  const listTargetId = accountResult.targetId;
  assertNotAborted(op);

  // ── Step 2: 导航到售后列表页并排序（不读全量列表，只做页面准备）───
  const step11 = require('../../scripts/jl-steps/11-prepare-after-sale-list');

  await cdp.navigate(listTargetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
  await sleep(step11.AFTER_NAVIGATION_WAIT_MS);
  await step11.assertAfterSaleListReady(listTargetId);
  const { selectOverdueSort } = require('../../scripts/jl-steps/09-select-overdue-sort');
  await selectOverdueSort({ targetId: listTargetId });
  await sleep(step11.AFTER_SORT_WAIT_MS);
  await step11.readCurrentPageSortCheck(listTargetId);
  assertNotAborted(op);

  const { action } = sim.decision;
  let result;

  if (action === 'escalate') {
    // ── escalate：直接在列表页添加备注，无需打开详情 ──────────────────
    const { addNote } = require('../jl/add-note');
    result = await addNote(listTargetId, sim.workOrderNum, `【待人工】${sim.decision.reason}`);
    if (!result.success) throw new Error(result.error || '备注失败');

    // 工单取消 → 清理关联的拦截记录
    if (sim.decision.reason && sim.decision.reason.includes('取消')) {
      try {
        const cd = sim.collectedData || {};
        const allShipTrackings = extractShippedTrackings(cd);
        allShipTrackings.forEach(t => {
          if (db.hasIntercept(t)) { db.removeIntercept(t); log(`[${sim.workOrderNum}] 工单取消，已清理拦截: ${t}`); }
        });
      } catch(e) { log(`cancel-intercept-cleanup 失败（非致命）: ${e.message}`); }
    }
  } else {
    // ── approve / reject：物理点击处理按钮，打开详情 tab ─────────────
    const step10 = require('../../scripts/jl-steps/10-read-urgent-after-sale-list');
    const step14 = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
    const { clickWorkOrderAction } = require('../../scripts/jl-steps/12-click-work-order-action');

    // Step 3: 定位工单（与扫描时寻找工单流程完全一致）
    const readCurrentPage = async (targetId) => {
      const raw = await cdp.eval(targetId, step10.READ_CURRENT_PAGE_TICKETS_JS);
      return {
        tickets: (raw && raw.tickets) || [],
        loading: Boolean(raw && raw.loading),
        pagination: step10.normalizePaginationState(raw && raw.pagination),
      };
    };
    const waitForPage = step14.createWaitForPage(waitFor);

    // prepareAfterSaleList 读完后分页可能停在最后一页，先回到第 1 页
    await step14.clickPageOneLikeHuman(listTargetId, {
      readCurrentPage, sleep, waitForPage,
      dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(listTargetId, event),
      eval: (id, js) => cdp.eval(id, js),
    });

    const located = await step14.locateWorkOrderOnFreshList(listTargetId, sim.workOrderNum, {
      readCurrentPage,
      clickPageOne: (id) => step14.clickPageOneLikeHuman(id, {
        readCurrentPage, sleep, waitForPage,
        dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(id, event),
        eval: (id, js) => cdp.eval(id, js),
      }),
      clickNextPage: step10.clickNextPage,
      waitForPage,
    });
    if (!located || !located.found) {
      throw new Error(`工单 ${sim.workOrderNum} 已不在待处理列表（可能已处理或已关闭）`);
    }

    // Step 4: 点击处理按钮，打开详情 tab
    const opened = await clickWorkOrderAction(sim.workOrderNum, { targetId: listTargetId });
    if (!opened || !opened.success || !opened.newTargetId) {
      throw new Error(`打开工单失败: ${(opened && opened.error) || '未识别到新标签页'}`);
    }
    const detailTargetId = opened.newTargetId;

    // 等待详情页 Vue 组件完全渲染（waitForNewWorkOrderTarget 只校验了 URL 含工单号，
    // body 可能尚未渲染完成，approveTicket navigate 会再等 3s，但这里多等 2s 更稳妥）
    await sleep(2000);
    assertNotAborted(op);

    let detailClosed = false;
    try {
      // Step 5: 在详情 tab 上执行决策
      if (action === 'approve') {
        const { approveTicket } = require('../jl/approve');
        result = await approveTicket(detailTargetId, sim.workOrderNum);
      } else if (action === 'reject') {
        const { rejectTicket } = require('../jl/reject');
        result = await rejectTicket(detailTargetId, sim.workOrderNum,
          rejectReason || sim.decision.rejectReason || sim.decision.reason,
          rejectDetail || sim.decision.rejectDetail || sim.decision.reason,
          rejectImageUrl || null);

        // 拦截提醒
        const needsReminder = (sim.decision.warnings || []).some(w => w.includes('拦截提醒') || w.includes('退回提醒'));
        if (needsReminder) {
          try {
            const cd = sim.collectedData || {};
            const accountNote = queueItem && queueItem.accountNote || '未知账号';
            const allShipTrackings = extractShippedTrackings(cd);
            const erpRows = cd.erpSearch && cd.erpSearch.rows && cd.erpSearch.rows.rows || [];
            const internalId = erpRows[0] && erpRows[0].internalId || '';
            const archiveTitle = cd.productArchive && cd.productArchive.title || '';
            const subOrderAttr = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].attr1 || '';
            const goodsName = (archiveTitle || subOrderAttr).slice(0, 30);
            const qty = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].afterSaleNum || '';
            const shipTracking = allShipTrackings.join(',');
            const remind = createReminder({
              workOrderNum: sim.workOrderNum, accountName: accountNote,
              shipTracking, internalId, goodsName, qty: qty ? String(qty) : '',
            });
            if (remind) {
              allShipTrackings.forEach(t => {
                db.addIntercept({ shipTracking: t, workOrderNum: sim.workOrderNum, accountNote });
                log(`已记录拦截: ${t}`);
              });
            }
          } catch(e) { log(`remind 失败（非致命）: ${e.message}`); }
        }
      } else {
        throw new Error(`未知 action: ${action}`);
      }
      if (!result.success) throw new Error(result.error || '执行失败');
    } finally {
      // Step 6: 关闭详情 tab（无论成功失败）
      try {
        const { readShopName } = require('../../scripts/jl-steps/02-read-shop-name');
        await step14.closeAndVerifyDetailTarget(detailTargetId, {
          getTargets: cdp.getTargets, closeTarget: cdp.closeTarget, sleep,
          readShopName: (id, waitMs) => readShopName(id, waitMs),
        }, { account: accountResult, listTargetId });
        detailClosed = true;
      } catch(e) { log(`[execute] 关闭详情 tab 失败（非致命）: ${e.message}`); }
    }
  }

  // ── 记录执行结果 ──────────────────────────────────────────────────
  db.appendCase({
    id: `case-${Date.now()}`, workOrderNum: sim.workOrderNum, accountNote: sim.accountNote,
    type: sim.collectedData && sim.collectedData.ticket && sim.collectedData.ticket.type,
    groundTruth: { action, reason: sim.decision.reason, source: fromBatch ? 'batch_executed' : 'executed' },
    collectedData: sim.collectedData, addedAt: new Date().toISOString(),
  });
  db.updateSimulation(simId, { executedAt: new Date().toISOString() });
  db.updateQueueItem(sim.queueItemId, { status: 'done' });
  return { action, workOrderNum: sim.workOrderNum };
}

async function execOpenTicket(op) {
  const { workOrderNum, accountNum: rawAccountNum } = op.params;
  const accountNum = assertAccountNum(rawAccountNum);

  // A2 安全链路 + 模拟点击（对齐 execExecute 步骤 1-5，2026-07-01）
  const cdp = require('../cdp');
  const { openAccountFlow } = require('../jl/open-account-flow');
  const { sleep, waitFor } = require('../wait');

  const accountResult = await openAccountFlow(accountNum);
  if (!accountResult || !accountResult.success) {
    throw new Error(`打开账号失败: ${(accountResult && accountResult.error) || '未知错误'}`);
  }
  saveSessionState(accountNum);
  const listTargetId = accountResult.targetId;
  assertNotAborted(op);

  // 导航到售后列表页并排序
  const step11 = require('../../scripts/jl-steps/11-prepare-after-sale-list');
  await cdp.navigate(listTargetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
  await sleep(step11.AFTER_NAVIGATION_WAIT_MS);
  await step11.assertAfterSaleListReady(listTargetId);
  const { selectOverdueSort } = require('../../scripts/jl-steps/09-select-overdue-sort');
  await selectOverdueSort({ targetId: listTargetId });
  await sleep(step11.AFTER_SORT_WAIT_MS);
  await step11.readCurrentPageSortCheck(listTargetId);
  assertNotAborted(op);

  // 定位工单
  const step10 = require('../../scripts/jl-steps/10-read-urgent-after-sale-list');
  const step14 = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const { clickWorkOrderAction } = require('../../scripts/jl-steps/12-click-work-order-action');

  const readCurrentPage = async (targetId) => {
    const raw = await cdp.eval(targetId, step10.READ_CURRENT_PAGE_TICKETS_JS);
    return {
      tickets: (raw && raw.tickets) || [],
      loading: Boolean(raw && raw.loading),
      pagination: step10.normalizePaginationState(raw && raw.pagination),
    };
  };
  const waitForPage = step14.createWaitForPage(waitFor);

  await step14.clickPageOneLikeHuman(listTargetId, {
    readCurrentPage, sleep, waitForPage,
    dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(listTargetId, event),
    eval: (id, js) => cdp.eval(id, js),
  });

  const located = await step14.locateWorkOrderOnFreshList(listTargetId, workOrderNum, {
    readCurrentPage,
    clickPageOne: (id) => step14.clickPageOneLikeHuman(id, {
      readCurrentPage, sleep, waitForPage,
      dispatchMouseEvent: (event) => cdp.dispatchMouseEvent(id, event),
      eval: (id, js) => cdp.eval(id, js),
    }),
    clickNextPage: step10.clickNextPage,
    waitForPage,
  });
  if (!located || !located.found) {
    throw new Error(`工单 ${workOrderNum} 未在待处理列表中找到（可能已处理或已关闭）`);
  }
  assertNotAborted(op);

  // 点击处理按钮打开详情 tab
  const opened = await clickWorkOrderAction(workOrderNum, { targetId: listTargetId });
  if (!opened || !opened.success || !opened.newTargetId) {
    throw new Error(`打开工单失败: ${(opened && opened.error) || '未识别到新标签页'}`);
  }
  await sleep(2000);

  return { opened: true, workOrderNum, accountNum, shopName: accountResult.shopName, detailTargetId: opened.newTargetId };
}

module.exports = { enqueue, cancel, getState, isRunning, emergencyStop, resume, isPaused, assertNotAborted, verifyStopState, readStopEvent, updateAccountStatus };
