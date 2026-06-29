'use strict';
/**
 * op-queue.js - 全局操作队列（串行化所有浏览器操作，防止 CDP 冲突）
 *
 * 所有涉及 Chrome 控制的操作（scan/collect/pipeline/reinfer/execute/open-ticket）
 * 必须通过 enqueue() 入队，由内部调度器严格串行执行。
 */

const { execFileSync, spawnSync, spawn } = require('child_process');
const path = require('path');
const db = require('./data');
const sse = require('./sse');
const { classifySessionFailure } = require('./account-session-status');
const { RETURN_KEYWORDS, REMIND_HOURS, RESCAN_INTERVAL_HOURS } = require('../constants');
const { extractShippedTrackings, createReminder } = require('../helpers');

const fs = require('fs');
const BASE = path.join(__dirname, '../..');
const CLI = path.join(BASE, 'cli.js');
const SESSIONS_DIR = path.join(BASE, '../sessions');

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
let activeProc = null;

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
  const idx = queue.findIndex(op => op.id === id && op.status === 'queued');
  if (idx === -1) return false;
  queue.splice(idx, 1);
  log(`取消 [${id}]`);
  broadcast();
  return true;
}

function getState() {
  return { running, queued: queue.filter(op => op.status === 'queued'), lastCompleted, paused };
}

function emergencyStop() {
  paused = true;
  for (let i = queue.length - 1; i >= 0; i--) {
    if (queue[i].status === 'queued') queue.splice(i, 1);
  }
  if (activeProc) { try { activeProc.kill('SIGTERM'); } catch(e) {} activeProc = null; }
  log('紧急停止');
  broadcast();
}

function resume() { paused = false; log('恢复'); broadcast(); processNext(); }
function isPaused() { return paused; }
function isRunning() { return !!running; }

// ── 内部调度 ──────────────────────────────────────────────────────

function broadcast() { sse.broadcast('op-queue-update', getState()); }

function processNext() {
  if (running || paused) return;
  const next = queue.find(op => op.status === 'queued');
  if (!next) return;
  next.status = 'running'; next.startedAt = new Date().toISOString(); running = next;
  log(`开始 [${next.id}] ${next.label}`); broadcast();
  executeOp(next).then(result => {
    next.status = 'done'; next.result = result; next.doneAt = new Date().toISOString();
    log(`完成 [${next.id}] ${next.label}`);
  }).catch(e => {
    next.status = 'error'; next.result = { error: e.message }; next.doneAt = new Date().toISOString();
    if (next.type === 'execute' && next.params && next.params.simId) {
      try { db.updateSimulation(next.params.simId, { executeError: e.message }); } catch {}
    }
    log(`失败 [${next.id}] ${next.label}: ${e.message}`);
  }).finally(() => {
    running = null; lastCompleted = next;
    const idx = queue.indexOf(next); if (idx !== -1) queue.splice(idx, 1);
    broadcast(); processNext();
  });
}

// ── 执行分派 ──────────────────────────────────────────────────────

async function executeOp(op) {
  switch (op.type) {
    case 'scan':           return execScan(op);
    case 'scan-account':   return execScanAccount(op);
    case 'scan-finalize':  return execScanFinalize(op);
    case 'open-account':   return execOpenAccount(op);
    case 'pipeline':       return execPipeline(op);
    case 'reinfer':        return execReinfer(op);
    case 'reprocess-one':  return execReprocessOne(op);
    case 'execute':        return execExecute(op);
    case 'open-ticket':    return execOpenTicket(op);
    case 'collect':        return execCollect(op);
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
    activeProc = proc;
    proc.stdout.on('data', d => { stdout += d; });
    proc.on('close', code => { if (activeProc === proc) activeProc = null; resolve({ code, stdout }); });
    proc.on('error', err => { if (activeProc === proc) activeProc = null; reject(err); });
  });
}

// [removed-2026-06-16] 删除 execCheckSession：刷新状态全链路的一环（多账号连续注入检测=风控红线）。
// 配套删除 routes.js POST /accounts/refresh-status 与前端"刷新状态"按钮。

async function execOpenAccount(op) {
  const { accountNum, accountNote } = op.params;
  const flow = spawnSync('node', [path.join(BASE, 'scripts/jl-steps/open-account.js'), String(accountNum)], {
    timeout: 90000, encoding: 'utf8', cwd: BASE,
  });
  let out = null;
  try { out = JSON.parse(flow.stdout || '{}'); } catch {}
  if (flow.status !== 0 || !out || !out.success) {
    const msg = ((out && out.error) || flow.stderr || flow.stdout || `退出码 ${flow.status}`).slice(0, 200);
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
  const { processSingleAccountFixedBatch } = require('../../scripts/jl-steps/14-process-single-account-fixed-batch');
  const { accountNum, accountNote } = op.params;
  const note = accountNote || `账号${accountNum}`;
  return processSingleAccountFixedBatch(String(accountNum), {
    thresholdHours: 48,
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

// ── 单账号扫描 ─────────────────────────────────────────────────────

async function execScanAccount(op) {
  const { accountNum, accountNote } = op.params;
  try { return await _execScanAccountInner(accountNum, accountNote); }
  catch(e) {
    const msg = e.message || '';
    const isExpired = /登录已失效|login|sso|鲸灵标签页未找到/.test(msg);
    updateAccountStatus(accountNum, {
      status: isExpired ? 'expired' : 'error',
      lastScan: new Date().toISOString(),
      error: msg.slice(0, 200), note: accountNote,
    });
    throw e;
  }
}

async function _execScanAccountInner(accountNum, accountNote) {
  const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
    timeout: 30000, encoding: 'utf8',
  });
  if (inj.status !== 0) throw new Error(`账号 ${accountNum} 注入失败: ${(inj.stderr || inj.stdout || '').slice(0, 100)}`);
  saveSessionState(accountNum);
  // 注入完成后等 10 秒，让页面和 session 完全稳定再读列表（防风控 + 防双刷）
  await new Promise(r => setTimeout(r, 10000));

  const r = spawnSync('node', [path.join(BASE, 'cli.js'), 'list'], {
    timeout: 120000, encoding: 'utf8', cwd: BASE,
  });
  let out;
  try { out = JSON.parse(r.stdout || '{}'); } catch(e) { throw new Error(`list 输出解析失败: ${(r.stdout || '').slice(0, 100)}`); }
  if (!out.success) throw new Error(out.error || 'list 失败');

  const urgent = (out.data && out.data.urgent) || [];

  let added = 0, updated = 0, waitingReset = 0;
  const queue = db.readQueue();
  for (const t of urgent) {
    const urgency = t.days !== undefined ? (t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`) : '时间解析失败';
    const deadlineAt = t.totalHours != null ? (t.deadlineAt || new Date(Date.now() + t.totalHours * 3600000).toISOString()) : null;
    const existing = queue.items.find(i => i.workOrderNum === t.workOrderNum && i.status !== 'done');
    if (existing) {
      if (existing.status === 'waiting') {
        db.updateQueueItem(existing.id, { status: 'pending', urgency, deadlineAt });
        waitingReset++;
      } else {
        db.updateQueueItem(existing.id, { urgency, deadlineAt });
        updated++;
      }
    } else {
      const item = db.addQueueItem({
        workOrderNum: t.workOrderNum, accountNum, accountNote,
        mode: 'live', source: 'scan', type: t.type || null, urgency, deadlineAt,
      });
      if (item) added++;
    }
  }

  // 到期预警
  const warnTickets = urgent.filter(t => t.totalHours != null && t.totalHours <= REMIND_HOURS);
  for (const t of warnTickets) {
    const timeStr = t.days !== undefined ? (t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`) : '未知';
    const dl = t.deadlineAt ? new Date(t.deadlineAt) : new Date(Date.now() + (t.totalHours || 0) * 3600000);
    const dlStr = `截止${(dl.getMonth()+1).toString().padStart(2,'0')}/${dl.getDate().toString().padStart(2,'0')} ${dl.getHours().toString().padStart(2,'0')}:${dl.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${accountNote} 工单${t.workOrderNum} ${t.type || ''} 剩余${timeStr} ${dlStr}`;
    if (!createReminder(title)) log(`[预警] Reminders 失败已降级通知: ${title}`);
  }

  log(`账号${accountNum} ${accountNote}: 采集 ${urgent.length} 条，新增 ${added}，更新 ${updated}，重置等待 ${waitingReset}`);
  updateAccountStatus(accountNum, { status: 'ok', lastScan: new Date().toISOString(), count: urgent.length, note: accountNote });

  // 读取结束后、切换下一账号前：导航到鲸灵首页读取提醒公告
  // 利用 10s 防风控间隔中的前 4s 完成导航+读取，不额外增加总耗时
  try {
    const { fetchAndCacheAlerts } = require('../jl/alerts');
    await fetchAndCacheAlerts(accountNum, accountNote); // alerts.js 内部会导航首页并等 3s
    log(`账号${accountNum} 首页提醒已更新`);
  } catch(e) {
    log(`账号${accountNum} 首页提醒读取失败（非阻塞）: ${e.message}`);
  }

  // 剩余等待时间（总 10s - alerts 约耗 4s = 6s），确保两次注入间隔
  await new Promise(r => setTimeout(r, 6000));
  return { accountNum, accountNote, count: urgent.length, added, updated, waitingReset };
}

// ── 巡检收尾 ─────────────────────────────────────────────────────

async function execScanFinalize(op) {
  const fs = require('fs');
  const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');
  try {
    fs.writeFileSync(SCAN_STATUS_FILE, JSON.stringify({
      scanning: false, lastScanAt: new Date().toISOString(), lastResult: null,
    }));
  } catch(e) {}

  await cleanReturnedIntercepts();

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
    .filter(n => (statusMap[String(n)] || {}).status === 'ok')
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
    const num = numsToScan[i];
    const cfg = accountsConfig[String(num)] || {};
    const note = cfg.note || cfg.name || `账号${num}`;

    sse.broadcast('scan-progress', { type: 'start', num, note, current: i + 1, total });
    try {
      const result = await processSingleAccountFixedBatch(String(num), {
        thresholdHours: 48,
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
      const res = await erpSearch(erpId, tracking);
      if (!res.success) { log(`[intercept-clean] ERP 查 ${tracking} 失败: ${res.error}`); continue; }
      const rows = res.data && res.data.rows && res.data.rows.rows || [];
      const hasReturned = rows.some(r => RETURN_KEYWORDS.some(kw => (r.textSnippet || '').includes(kw)));
      if (hasReturned) { db.removeIntercept(tracking); log(`[intercept-clean] ${tracking} ERP显示已退回，已清除`); cleaned++; }
      else log(`[intercept-clean] ${tracking} 未退回，保留`);
    } catch(e) { log(`[intercept-clean] 查询 ${tracking} 异常: ${e.message}`); }
  }
  if (cleaned > 0) log(`[intercept-clean] 共清除 ${cleaned} 条拦截记录`);
  else log(`[intercept-clean] 检查完毕，无需清除`);
}

async function execPipeline(op) {
  const pipeline = require('./pipeline');
  await pipeline.runPipeline(op.params.mode || 'live');
  return { done: true };
}

async function execReinfer(op) {
  const { simId, hint = '' } = op.params;
  const sim = db.getSimulation(simId);
  if (!sim) throw new Error('simulation 未找到: ' + simId);
  // 将用户输入的评价指令写入 queue item，同时清除旧 pipeline 残留的自动 hint
  db.updateQueueItem(sim.queueItemId, { hint: hint || null });
  // 复用 execReprocessOne 的完整 A1 安全链路（openAccountFlow → 定位 → 点击 → 采集 → 推理）
  return execReprocessOne({ params: { queueItemId: sim.queueItemId } });
}

async function execReprocessOne(op) {
  const { queueItemId } = op.params;

  const queueItem = (db.readQueue().items || []).find(i => i.id === queueItemId);
  if (!queueItem) throw new Error('未找到队列项');
  if (['auto_executed', 'done'].includes(queueItem.status)) {
    return { skipped: true, reason: '已执行完成，跳过重新采集' };
  }

  const accountNum = queueItem.accountNum;
  if (!accountNum) throw new Error('缺少账号编号');

  const cdp = require('../cdp');
  const { openAccountFlow } = require('../jl/open-account-flow');
  const { sleep, waitFor } = require('../wait');

  // ── Step 1: 安全打开账号 ──────────────────────────────────────────
  const accountResult = await openAccountFlow(String(accountNum));
  if (!accountResult || !accountResult.success) {
    throw new Error(`打开账号失败: ${(accountResult && accountResult.error) || '未知错误'}`);
  }
  saveSessionState(accountNum);
  const listTargetId = accountResult.targetId;

  // ── Step 2: 导航到售后列表页并排序（不读全量列表，只做页面准备）───
  const step11 = require('../../scripts/jl-steps/11-prepare-after-sale-list');

  await cdp.navigate(listTargetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
  await sleep(step11.AFTER_NAVIGATION_WAIT_MS);
  await step11.assertAfterSaleListReady(listTargetId);
  const { selectOverdueSort } = require('../../scripts/jl-steps/09-select-overdue-sort');
  await selectOverdueSort({ targetId: listTargetId });
  await sleep(step11.AFTER_SORT_WAIT_MS);
  await step11.readCurrentPageSortCheck(listTargetId);

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

  // Step 4: 点击处理按钮，打开详情 tab
  const opened = await clickWorkOrderAction(queueItem.workOrderNum, { targetId: listTargetId });
  if (!opened || !opened.success || !opened.newTargetId) {
    throw new Error(`打开工单失败: ${(opened && opened.error) || '未识别到新标签页'}`);
  }
  const detailTargetId = opened.newTargetId;

  // 等待详情页 Vue 组件完全渲染
  await sleep(2000);

  let detailClosed = false;
  try {
    // ── Step 5: 采集 + 推理（此处与执行操作不同）────────────────────
    const { inferDecision } = require('../infer');
    const { collectTicketTargetAware, resolveUniqueErpTargetId } = require('../jl/target-aware-collector');

    const erpTargetId = await resolveUniqueErpTargetId({ getTargets: cdp.getTargets }, null);
    const collectedData = await collectTicketTargetAware({
      detailTargetId,
      erpTargetId,
      workOrderNum: queueItem.workOrderNum,
      accountNote: queueItem.accountNote || accountResult.matchedNote || '',
      type: queueItem.type || null,
    });

    const decision = inferDecision({ collectedData }, queueItem);

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
      collectedData,
      decision,
      createdAt: now,
    };
    db.appendSimulation(sim);

    const queueStatus = decision && decision.action === 'skip'
      ? step14.statusForProcessed({ status: 'simulated', decision }, queueItem)
      : (decision && decision.waitingRescan ? 'waiting' : 'simulated');
    db.updateQueueItem(queueItem.id, { status: queueStatus, waitingRescan: !!(decision && decision.waitingRescan) });

    log(`[${queueItem.workOrderNum}] 重新采集推理完成 → ${decision.action}${decision.waitingRescan ? ' (等待重查)' : ''}`);
  } finally {
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

  const accountNum = queueItem.accountNum;
  if (!accountNum) throw new Error('缺少账号编号');

  const cdp = require('../cdp');
  const { openAccountFlow } = require('../jl/open-account-flow');
  const { sleep, waitFor } = require('../wait');

  // ── Step 1: 安全打开账号 ──────────────────────────────────────────
  const accountResult = await openAccountFlow(String(accountNum));
  if (!accountResult || !accountResult.success) {
    throw new Error(`打开账号失败: ${(accountResult && accountResult.error) || '未知错误'}`);
  }
  saveSessionState(accountNum);
  const listTargetId = accountResult.targetId;

  // ── Step 2: 导航到售后列表页并排序（不读全量列表，只做页面准备）───
  const step11 = require('../../scripts/jl-steps/11-prepare-after-sale-list');

  await cdp.navigate(listTargetId, 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list');
  await sleep(step11.AFTER_NAVIGATION_WAIT_MS);
  await step11.assertAfterSaleListReady(listTargetId);
  const { selectOverdueSort } = require('../../scripts/jl-steps/09-select-overdue-sort');
  await selectOverdueSort({ targetId: listTargetId });
  await sleep(step11.AFTER_SORT_WAIT_MS);
  await step11.readCurrentPageSortCheck(listTargetId);

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
  const { workOrderNum, accountNum } = op.params;
  if (accountNum) {
    const injResult = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
      timeout: 30000, encoding: 'utf8',
    });
    if (injResult.status !== 0) throw new Error(`账号 ${accountNum} 注入失败：${(injResult.stderr || injResult.stdout || '').slice(0, 200)}`);
  }
  return JSON.parse(execFileSync('node', [CLI, 'open-ticket', workOrderNum], { cwd: BASE, timeout: 30000, encoding: 'utf8' }));
}

async function execCollect(op) {
  const { queueItemId, mode = 'live', accountNum } = op.params;
  const args = ['--limit', '1', mode === 'live' ? '--live' : '--sim'];
  if (accountNum) args.push('--account', String(accountNum));
  const { code } = await spawnAsync('node', [path.join(BASE, 'collect.js'), ...args], { cwd: BASE, timeout: 180000 });
  if (code !== 0) throw new Error('采集失败');
  return { done: true };
}

module.exports = { enqueue, cancel, getState, isRunning, emergencyStop, resume, isPaused, updateAccountStatus };
