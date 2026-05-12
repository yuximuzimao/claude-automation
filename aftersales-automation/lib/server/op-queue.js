'use strict';
/**
 * op-queue.js - 全局操作队列（串行化所有浏览器操作，防止 CDP 冲突）
 *
 * 所有涉及 Chrome 控制的操作（scan/collect/pipeline/reinfer/execute/open-ticket）
 * 必须通过 enqueue() 入队，由内部调度器严格串行执行。
 */

const { execFileSync, spawnSync, spawn } = require('child_process');
const http = require('http');
const path = require('path');
const db = require('./data');
const sse = require('./sse');
const { RETURN_KEYWORDS, REMIND_HOURS, RESCAN_INTERVAL_HOURS } = require('../constants');

const fs = require('fs');
const BASE = path.join(__dirname, '../..');
const CLI = path.join(BASE, 'cli.js');
const SESSIONS_DIR = path.join(BASE, '../sessions');
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

// 创建 Mac 提醒：优先 Reminders.app，失败时（后台无 TTY）降级为系统通知
function createReminder(title) {
  const remind = spawnSync('osascript', ['-e',
    `tell application "Reminders" to make new reminder at end of list "待办" of default account with properties {name:"${title.replace(/"/g, '\\"')}"}`
  ], { timeout: 10000, encoding: 'utf8' });
  if (remind.status === 0) {
    log(`[预警] ${title}`);
    return true;
  }
  const errMsg = (remind.stderr || '').slice(0, 80);
  log(`[预警] Reminders 创建失败（${errMsg}），降级为系统通知`);
  spawnSync('osascript', ['-e',
    `display notification "${title.replace(/"/g, '\\"')}" with title "鲸灵售后预警" sound name "default"`
  ], { timeout: 5000 });
  return false;
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
    case 'check-session':  return execCheckSession(op);
    case 'pipeline':       return execPipeline(op);
    case 'reinfer':        return execReinfer(op);
    case 'reprocess-one':  return execReprocessOne(op);
    case 'execute':        return execExecute(op);
    case 'open-ticket':    return execOpenTicket(op);
    case 'collect':        return execCollect(op);
    default: throw new Error(`未知操作类型: ${op.type}`);
  }
}

// ── 各类操作实现 ──────────────────────────────────────────────────

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

// ── 轻量 session 检测（inject + CDP URL 校验，不拉工单） ────────────

async function execCheckSession(op) {
  const { accountNum, accountNote } = op.params;

  // Step 1: 注入 session（失败则直接标 expired/error）
  const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
    timeout: 30000, encoding: 'utf8',
  });
  if (inj.status !== 0) {
    const msg = (inj.stderr || inj.stdout || '').slice(0, 150);
    const isExpired = /登录已失效|login|sso|鲸灵标签页未找到/.test(msg);
    updateAccountStatus(accountNum, {
      status: isExpired ? 'expired' : 'error',
      lastScan: new Date().toISOString(),
      error: msg, note: accountNote,
    });
    return { accountNum, status: isExpired ? 'expired' : 'error' };
  }

  // Step 2: 额外等 3s，让页面完成跳转（inject 内已等 2s）
  await new Promise(r => setTimeout(r, 3000));

  // Step 3: 用 CDP /json 查 SCRM tab 当前 URL
  const tabUrl = await new Promise(resolve => {
    http.get('http://localhost:9222/json', res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => {
        try {
          const t = JSON.parse(d).find(t => t.url && t.url.includes('scrm.jlsupp.com'));
          resolve(t ? t.url : null);
        } catch(e) { resolve(null); }
      });
    }).on('error', () => resolve(null));
  });

  let status, error;
  if (tabUrl === null) {
    status = 'error'; error = '鲸灵标签页未找到';
  } else if (tabUrl.includes('/login')) {
    status = 'expired'; error = `登录已失效，当前URL: ${tabUrl.slice(0, 100)}`;
  } else {
    status = 'ok'; error = null;
  }

  updateAccountStatus(accountNum, {
    status, lastScan: new Date().toISOString(), note: accountNote,
    ...(error ? { error } : { error: null }),
  });
  return { accountNum, status };
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
  await new Promise(r => setTimeout(r, 5000));

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
    createReminder(title);
  }

  log(`账号${accountNum} ${accountNote}: 采集 ${urgent.length} 条，新增 ${added}，更新 ${updated}，重置等待 ${waitingReset}`);
  updateAccountStatus(accountNum, { status: 'ok', lastScan: new Date().toISOString(), count: urgent.length, note: accountNote });
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
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    enqueue('reprocess-one', label, { queueItemId: item.id });
  }
  log(`巡检收尾：入队 ${pending.length} 条工单推理`);
  return { done: true, pipelineCount: pending.length };
}

async function execScan(op) {
  const { accounts = [] } = op.params;
  const args = accounts.length ? accounts.map(String) : [];
  const { code, stdout } = await new Promise((resolve, reject) => {
    let stdout = '', stderrBuf = '';
    const proc = spawn('node', [path.join(BASE, 'scan-all.js'), ...args], {
      cwd: BASE, stdio: ['ignore', 'pipe', 'pipe'],
    });
    activeProc = proc;
    proc.stdout.on('data', d => { stdout += d; });
    proc.stderr.on('data', d => {
      stderrBuf += d;
      const lines = stderrBuf.split('\n');
      stderrBuf = lines.pop();
      for (const line of lines) {
        if (line.startsWith('SCAN_PROGRESS:')) {
          try { sse.broadcast('scan-progress', JSON.parse(line.slice(14))); } catch(e) {}
        } else if (line.trim()) process.stderr.write(line + '\n');
      }
    });
    proc.on('close', code => {
      if (activeProc === proc) activeProc = null;
      if (stderrBuf.trim()) {
        if (stderrBuf.startsWith('SCAN_PROGRESS:')) {
          try { sse.broadcast('scan-progress', JSON.parse(stderrBuf.slice(14))); } catch(e) {}
        } else process.stderr.write(stderrBuf + '\n');
      }
      resolve({ code, stdout });
    });
    proc.on('error', reject);
  });
  let result = null;
  try { result = JSON.parse(stdout); } catch(e) {}
  const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');
  try { fs.writeFileSync(SCAN_STATUS_FILE, JSON.stringify({ scanning: false, lastScanAt: new Date().toISOString(), lastResult: result })); } catch(e) {}
  if (result) sse.broadcast('accounts-update', readAccountStatus());
  if (code !== 0 && !result) throw new Error('scan-all 执行失败');

  // 到期预警：从本次扫描结果
  const warnTickets = (result && result.urgent || []).filter(t => t.totalHours != null && t.totalHours <= REMIND_HOURS);
  for (const t of warnTickets) {
    const timeStr = t.days !== undefined ? (t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`) : '未知';
    const deadlineDate = t.deadlineAt ? new Date(t.deadlineAt) : new Date(Date.now() + (t.totalHours || 0) * 3600000);
    const deadlineStr = `截止${(deadlineDate.getMonth()+1).toString().padStart(2,'0')}/${deadlineDate.getDate().toString().padStart(2,'0')} ${deadlineDate.getHours().toString().padStart(2,'0')}:${deadlineDate.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${t.note || '账号' + t.num} 工单${t.workOrderNum} ${t.type || ''} 剩余${timeStr} ${deadlineStr}`;
    createReminder(title);
  }

  // 补充：检查队列中扫描未命中的到期工单（waiting/simulated）
  const scanWarnedNums = new Set(warnTickets.map(t => t.workOrderNum));
  const queueItems = (db.readQueue().items || []).filter(i =>
    i.mode === 'live' && !['done', 'auto_executed'].includes(i.status)
  );
  for (const qi of queueItems) {
    if (scanWarnedNums.has(qi.workOrderNum)) continue;
    if (!qi.deadlineAt) continue;
    const remainingHours = (new Date(qi.deadlineAt).getTime() - Date.now()) / 3600000;
    if (remainingHours > REMIND_HOURS || remainingHours <= 0) continue;
    const timeStr = remainingHours < 1 ? '<1小时' : `${remainingHours.toFixed(0)}小时`;
    const dl = new Date(qi.deadlineAt);
    const dlStr = `截止${(dl.getMonth()+1).toString().padStart(2,'0')}/${dl.getDate().toString().padStart(2,'0')} ${dl.getHours().toString().padStart(2,'0')}:${dl.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${qi.accountNote || ''} 工单${qi.workOrderNum} ${qi.type || ''} 剩余${timeStr} ${dlStr}`;
    createReminder(title);
  }

  // 入队推理
  const pending = (db.readQueue().items || []).filter(i =>
    (i.status === 'pending' || i.status === 'collected') && i.mode === 'live'
  );
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    enqueue('reprocess-one', label, { queueItemId: item.id });
  }

  cleanReturnedIntercepts().catch(e => log(`[intercept-clean] 清理失败（非致命）: ${e.message}`));
  return result;
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
  const pipeline = require('./pipeline');
  const sim = db.getSimulation(simId);
  if (!sim) throw new Error('simulation 未找到: ' + simId);
  await pipeline.reprocessOne(sim.queueItemId, hint);
  return { done: true };
}

async function execReprocessOne(op) {
  const { queueItemId } = op.params;
  const pipeline = require('./pipeline');
  await pipeline.reprocessOne(queueItemId, '');
  return { done: true };
}

async function execExecute(op) {
  const { simId, rejectReason, rejectDetail, rejectImageUrl } = op.params;
  const sim = db.getSimulation(simId);
  if (!sim) throw new Error('simulation 未找到: ' + simId);
  if (sim.executedAt) return { skipped: true, reason: '已执行过' };

  const queueItem = (db.readQueue().items || []).find(i => i.id === sim.queueItemId);
  if (!queueItem) return { skipped: true, reason: '队列项不存在' };
  if (queueItem.status === 'waiting') return { skipped: true, reason: '工单处于等待重查状态，跳过执行' };
  const accountNum = queueItem.accountNum;
  if (accountNum) {
    const injResult = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
      timeout: 30000, encoding: 'utf8',
    });
    if (injResult.status !== 0) throw new Error(`账号 ${accountNum} 注入失败：${(injResult.stderr || injResult.stdout || '').slice(0, 200)}`);
  }

  const { action } = sim.decision;
  const EXEC_OPTS = { cwd: BASE, timeout: 90000, encoding: 'utf8' };
  let result;

  if (action === 'approve') {
    result = JSON.parse(execFileSync('node', [CLI, 'approve', sim.workOrderNum], EXEC_OPTS));
  } else if (action === 'reject') {
    const args = ['reject', sim.workOrderNum,
      rejectReason || sim.decision.rejectReason || sim.decision.reason,
      rejectDetail || sim.decision.rejectDetail || sim.decision.reason,
    ];
    if (rejectImageUrl) args.push(rejectImageUrl);
    result = JSON.parse(execFileSync('node', [CLI, ...args], EXEC_OPTS));
    // 拦截提醒
    const needsReminder = (sim.decision.warnings || []).some(w => w.includes('拦截提醒') || w.includes('退回提醒'));
    if (needsReminder) {
      try {
        const cd = sim.collectedData || {};
        const accountNote = queueItem && queueItem.accountNote || '未知账号';
        const allShipTrackings = (function() {
          const result = [], seen = new Set();
          function addFrom(erpData) {
            const rows = (erpData && erpData.rows && erpData.rows.rows) || [];
            rows.forEach(row => {
              if (row.status !== '卖家已发货') return;
              const ts = (row.trackings && row.trackings.length) ? row.trackings : (row.tracking ? [row.tracking] : []);
              ts.forEach(t => { if (t && !seen.has(t)) { seen.add(t); result.push(t); } });
            });
          }
          addFrom(cd.erpSearch); addFrom(cd.giftErpSearch);
          return result;
        })();
        const erpRows = cd.erpSearch && cd.erpSearch.rows && cd.erpSearch.rows.rows || [];
        const internalId = erpRows[0] && erpRows[0].internalId || '';
        const archiveTitle = cd.productArchive && cd.productArchive.title || '';
        const subOrderAttr = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].attr1 || '';
        const goodsName = (archiveTitle || subOrderAttr).slice(0, 30);
        const qty = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].afterSaleNum || '';
        const shipTracking = allShipTrackings.join(',');
        const remindArgs = [CLI, 'remind', sim.workOrderNum, accountNote,
          shipTracking, internalId, goodsName, qty ? String(qty) : ''];
        execFileSync('node', remindArgs, EXEC_OPTS);
        allShipTrackings.forEach(t => {
          db.addIntercept({ shipTracking: t, workOrderNum: sim.workOrderNum, accountNote });
          log(`已记录拦截: ${t}`);
        });
      } catch(e) { log(`remind 失败（非致命）: ${e.message}`); }
    }
  } else if (action === 'escalate') {
    result = JSON.parse(execFileSync('node', [CLI, 'add-note', sim.workOrderNum, `【待人工】${sim.decision.reason}`], EXEC_OPTS));
  } else {
    throw new Error(`未知 action: ${action}`);
  }

  if (!result.success) throw new Error(result.error || '执行失败');

  db.appendCase({
    id: `case-${Date.now()}`, workOrderNum: sim.workOrderNum, accountNote: sim.accountNote,
    type: sim.collectedData && sim.collectedData.ticket && sim.collectedData.ticket.type,
    groundTruth: { action, reason: sim.decision.reason, source: 'executed' },
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
