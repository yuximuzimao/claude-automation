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
const { RETURN_KEYWORDS } = require('../constants');

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
  // 扫描成功时清除残留的 error 字段，避免前端显示过期错误
  if (patch.status === 'ok' && !patch.error) {
    delete merged.error;
  }
  s[String(num)] = merged;
  writeAccountStatus(s);
  sse.broadcast('accounts-update', readAccountStatus());
}

let counter = 0;
const queue = [];        // OpItem[]，包含 queued + running + done/error（done 保留最近20条）
let running = null;      // 当前正在执行的 OpItem | null
let lastCompleted = null; // 最近一次完成的 OpItem（供前端闪烁提示）
let paused = false;      // 紧急停止标志
let activeProc = null;   // 当前子进程引用（用于 kill）

function log(msg) { process.stdout.write(`[op-queue] ${msg}\n`); }

// ── 公共 API ──────────────────────────────────────────────────────

function enqueue(type, label, params) {
  const op = {
    id: `op-${Date.now()}-${++counter}`,
    type,
    label,
    params: params || {},
    status: 'queued',
    result: null,
    createdAt: new Date().toISOString(),
    startedAt: null,
    doneAt: null,
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
  return {
    running,
    queued: queue.filter(op => op.status === 'queued'),
    lastCompleted,
    paused,
  };
}

function emergencyStop() {
  paused = true;
  // 清空所有排队中的任务（直接从 queue 移除）
  for (let i = queue.length - 1; i >= 0; i--) {
    if (queue[i].status === 'queued') queue.splice(i, 1);
  }
  // 终止当前子进程
  if (activeProc) {
    try { activeProc.kill('SIGTERM'); } catch(e) {}
    activeProc = null;
  }
  log('紧急停止：队列已清空，子进程已终止');
  broadcast();
}

function resume() {
  paused = false;
  log('系统恢复运行');
  broadcast();
  processNext();
}

function isPaused() { return paused; }

function isRunning() { return !!running; }

// ── 内部调度 ──────────────────────────────────────────────────────

function broadcast() {
  sse.broadcast('op-queue-update', getState());
}

function processNext() {
  if (running) return; // 已有任务在跑
  if (paused) return;  // 已紧急停止
  const next = queue.find(op => op.status === 'queued');
  if (!next) return;

  next.status = 'running';
  next.startedAt = new Date().toISOString();
  running = next;
  log(`开始 [${next.id}] ${next.label}`);
  broadcast();

  executeOp(next).then(result => {
    next.status = 'done';
    next.result = result;
    next.doneAt = new Date().toISOString();
    log(`完成 [${next.id}] ${next.label}`);
  }).catch(e => {
    next.status = 'error';
    next.result = { error: e.message };
    next.doneAt = new Date().toISOString();
    // execute 失败时把错误写回 sim，卡片可以展示
    if (next.type === 'execute' && next.params && next.params.simId) {
      try { db.updateSimulation(next.params.simId, { executeError: e.message }); } catch {}
    }
    log(`失败 [${next.id}] ${next.label}: ${e.message}`);
  }).finally(() => {
    running = null;
    lastCompleted = next;
    // 完成后直接从 queue 中移除，不保留历史
    const idx = queue.indexOf(next);
    if (idx !== -1) queue.splice(idx, 1);
    broadcast();
    processNext(); // 继续下一条
  });
}

// ── 执行分派 ──────────────────────────────────────────────────────

async function executeOp(op) {
  switch (op.type) {
    case 'scan':           return execScan(op);
    case 'scan-account':   return execScanAccount(op);
    case 'scan-finalize':  return execScanFinalize(op);
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

// ── 单账号扫描（自动巡检拆分为每账号一条任务）─────────────────────
async function execScanAccount(op) {
  const { accountNum, accountNote } = op.params;
  try {
    return await _execScanAccountInner(accountNum, accountNote);
  } catch(e) {
    const msg = e.message || '';
    const isExpired = /登录已失效|login|sso|鲸灵标签页未找到/.test(msg);
    updateAccountStatus(accountNum, {
      status: isExpired ? 'expired' : 'error',
      lastScan: new Date().toISOString(),
      error: msg.slice(0, 200),
      note: accountNote,
    });
    throw e;
  }
}

async function _execScanAccountInner(accountNum, accountNote) {
  // 注入账号
  const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
    timeout: 30000, encoding: 'utf8',
  });
  if (inj.status !== 0) throw new Error(`账号 ${accountNum} 注入失败: ${(inj.stderr || inj.stdout || '').slice(0, 100)}`);

  // 等待浏览器稳定
  await new Promise(r => setTimeout(r, 5000));

  // 读工单列表
  const r = spawnSync('node', [path.join(BASE, 'cli.js'), 'list'], {
    timeout: 120000, encoding: 'utf8', cwd: BASE,
  });
  let out;
  try { out = JSON.parse(r.stdout || '{}'); } catch(e) { throw new Error(`list 输出解析失败: ${(r.stdout || '').slice(0, 100)}`); }
  if (!out.success) throw new Error(out.error || 'list 失败');

  const urgent = (out.data && out.data.urgent) || [];

  // 写入 queue.json（去重）
  let added = 0, updated = 0, waitingReset = 0;
  const queue = db.readQueue();
  for (const t of urgent) {
    const urgency = t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`;
    const deadlineAt = t.deadlineAt || new Date(Date.now() + (t.totalHours || 0) * 3600000).toISOString();
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
        workOrderNum: t.workOrderNum,
        accountNum,
        accountNote,
        mode: 'live',
        source: 'scan',
        type: t.type || null,
        urgency,
        deadlineAt,
      });
      if (item) added++;
    }
  }

  // 6小时预警
  const warnTickets = urgent.filter(t => t.totalHours !== undefined && t.totalHours <= 6);
  for (const t of warnTickets) {
    const timeStr = t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`;
    const dl = t.deadlineAt ? new Date(t.deadlineAt) : new Date(Date.now() + (t.totalHours || 0) * 3600000);
    const dlStr = `截止${(dl.getMonth()+1).toString().padStart(2,'0')}/${dl.getDate().toString().padStart(2,'0')} ${dl.getHours().toString().padStart(2,'0')}:${dl.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${accountNote} 工单${t.workOrderNum} ${t.type || ''} 剩余${timeStr} ${dlStr}`;
    const script = `tell application "Reminders" to make new reminder at end of list "待办" of default account with properties {name:"${title.replace(/"/g, '\\"')}"}`;
    const remind = spawnSync('osascript', ['-e', script], { timeout: 10000, encoding: 'utf8' });
    if (remind.status === 0) log(`[预警] ${title}`);
    else log(`[预警] 创建失败（非致命）: ${(remind.stderr || '').slice(0, 80)}`);
  }

  log(`账号${accountNum} ${accountNote}: 采集 ${urgent.length} 条，新增 ${added}，更新 ${updated}，重置等待 ${waitingReset}`);
  updateAccountStatus(accountNum, { status: 'ok', lastScan: new Date().toISOString(), count: urgent.length, note: accountNote });
  return { accountNum, accountNote, count: urgent.length, added, updated, waitingReset };
}

// ── 巡检收尾（全部账号扫完后：清理拦截 + 逐工单入队推理）─────────
async function execScanFinalize(op) {
  const fs = require('fs');
  const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');
  try {
    fs.writeFileSync(SCAN_STATUS_FILE, JSON.stringify({
      scanning: false, lastScanAt: new Date().toISOString(), lastResult: null,
    }));
  } catch(e) {}

  // 清理已退回的拦截记录
  await cleanReturnedIntercepts();

  // 每张 pending live 工单单独入队推理（可逐条取消）
  const pending = (db.readQueue().items || []).filter(i => i.status === 'pending' && i.mode === 'live');
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
    let stdout = '';
    let stderrBuf = '';
    const proc = spawn('node', [path.join(BASE, 'scan-all.js'), ...args], {
      cwd: BASE, stdio: ['ignore', 'pipe', 'pipe'],
    });
    activeProc = proc;
    proc.stdout.on('data', d => { stdout += d; });
    proc.stderr.on('data', d => {
      stderrBuf += d;
      const lines = stderrBuf.split('\n');
      stderrBuf = lines.pop(); // 不完整的末行暂存
      for (const line of lines) {
        if (line.startsWith('SCAN_PROGRESS:')) {
          try { sse.broadcast('scan-progress', JSON.parse(line.slice(14))); } catch(e) {}
        } else if (line.trim()) {
          process.stderr.write(line + '\n');
        }
      }
    });
    proc.on('close', code => {
      if (activeProc === proc) activeProc = null;
      // 处理 stderr 剩余内容
      if (stderrBuf.trim()) {
        if (stderrBuf.startsWith('SCAN_PROGRESS:')) {
          try { sse.broadcast('scan-progress', JSON.parse(stderrBuf.slice(14))); } catch(e) {}
        } else {
          process.stderr.write(stderrBuf + '\n');
        }
      }
      resolve({ code, stdout });
    });
    proc.on('error', reject);
  });
  let result = null;
  try { result = JSON.parse(stdout); } catch(e) {}
  // 写扫描状态文件（兼容旧的 scan-status 接口）
  const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');
  try { fs.writeFileSync(SCAN_STATUS_FILE, JSON.stringify({ scanning: false, lastScanAt: new Date().toISOString(), lastResult: result })); } catch(e) {}
  // scan-all.js 已直接写 account-status.json，这里只需 SSE 广播让前端实时刷新
  if (result) sse.broadcast('accounts-update', readAccountStatus());
  if (code !== 0 && !result) throw new Error('scan-all 执行失败');

  // 6小时预警：为即将过期的工单创建 Mac 提醒
  const warnTickets = (result && result.urgent || []).filter(t => t.totalHours !== undefined && t.totalHours <= 6);
  for (const t of warnTickets) {
    const timeStr = t.days > 0 ? `${t.days}天${t.hours}小时` : `${t.hours}小时`;
    const deadlineDate = t.deadlineAt ? new Date(t.deadlineAt) : new Date(Date.now() + (t.totalHours || 0) * 3600000);
    const deadlineStr = `截止${(deadlineDate.getMonth()+1).toString().padStart(2,'0')}/${deadlineDate.getDate().toString().padStart(2,'0')} ${deadlineDate.getHours().toString().padStart(2,'0')}:${deadlineDate.getMinutes().toString().padStart(2,'0')}`;
    const title = `【⚠️即将过期】${t.note || '账号' + t.num} 工单${t.workOrderNum} ${t.type || ''} 剩余${timeStr} ${deadlineStr}`;
    const appleScript = `tell application "Reminders" to make new reminder at end of list "待办" of default account with properties {name:"${title.replace(/"/g, '\\"')}"}`;
    const r = spawnSync('osascript', ['-e', appleScript], { timeout: 10000, encoding: 'utf8' });
    if (r.status === 0) {
      log(`[预警] 提醒已创建：${title}`);
    } else {
      log(`[预警] 提醒创建失败（非致命）: ${(r.stderr || '').slice(0, 80)}`);
    }
  }

  // 扫描完成后逐工单入队推理（每张单独一条，可逐条取消）
  const pending = (db.readQueue().items || []).filter(i => i.status === 'pending' && i.mode === 'live');
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    enqueue('reprocess-one', label, { queueItemId: item.id });
  }

  // 扫描后专项清理：用实时 ERP 查询检测已退回的拦截记录（后台执行，不阻塞推理入队）
  cleanReturnedIntercepts().catch(e => log(`[intercept-clean] 清理失败（非致命）: ${e.message}`));

  return result;
}

// 扫描后专项清理：查 ERP 实时物流状态，检测拦截记录是否已退回
async function cleanReturnedIntercepts() {
  const map = db.readIntercepts();
  const trackings = Object.keys(map);
  if (!trackings.length) return;

  // TTL 过期清理（不需要 ERP）
  let cleaned = 0;
  for (const tracking of trackings) {
    const rec = map[tracking];
    const age = Date.now() - new Date(rec.executedAt).getTime();
    if (age > db.INTERCEPT_TTL_MS) {
      db.removeIntercept(tracking);
      log(`[intercept-clean] ${tracking} 超7天过期，已清除`);
      cleaned++;
    }
  }

  // ERP 实时查询（获取失败则跳过，不影响 TTL 清理结果）
  const { getTargetIds } = require('../targets');
  const { erpSearch } = require('../erp/search');
  let erpId;
  try {
    const ids = await getTargetIds();
    erpId = ids.erpId;
  } catch(e) {
    log(`[intercept-clean] 无法获取 ERP target，跳过实时查询: ${e.message}`);
    if (cleaned > 0) log(`[intercept-clean] 共清除 ${cleaned} 条过期记录`);
    return;
  }

  // 查询剩余（未过期）的记录
  const remaining = Object.keys(db.readIntercepts());
  for (const tracking of remaining) {
    try {
      const res = await erpSearch(erpId, tracking);
      if (!res.success) { log(`[intercept-clean] ERP 查 ${tracking} 失败: ${res.error}`); continue; }
      const rows = res.data && res.data.rows && res.data.rows.rows || [];
      const hasReturned = rows.some(r => RETURN_KEYWORDS.some(kw => (r.textSnippet || '').includes(kw)));
      if (hasReturned) {
        db.removeIntercept(tracking);
        log(`[intercept-clean] ${tracking} ERP显示已退回，已清除`);
        cleaned++;
      } else {
        log(`[intercept-clean] ${tracking} 未退回，保留`);
      }
    } catch(e) {
      log(`[intercept-clean] 查询 ${tracking} 异常: ${e.message}`);
    }
  }
  if (cleaned > 0) log(`[intercept-clean] 共清除 ${cleaned} 条拦截记录`);
  else log(`[intercept-clean] 检查完毕，无需清除`);
}

async function execPipeline(op) {
  const { mode = 'live' } = op.params;
  const pipeline = require('./pipeline');
  await pipeline.runPipeline(mode);
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

  // 注入账号
  const queueItem = (db.readQueue().items || []).find(i => i.id === sim.queueItemId);
  const accountNum = queueItem && queueItem.accountNum;
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
    const raw = execFileSync('node', [CLI, 'approve', sim.workOrderNum], EXEC_OPTS);
    result = JSON.parse(raw);
  } else if (action === 'reject') {
    const args = ['reject', sim.workOrderNum,
      rejectReason || sim.decision.rejectReason || sim.decision.reason,
      rejectDetail || sim.decision.rejectDetail || sim.decision.reason,
    ];
    if (rejectImageUrl) args.push(rejectImageUrl);
    const raw = execFileSync('node', [CLI, ...args], EXEC_OPTS);
    result = JSON.parse(raw);
    // 拦截提醒
    const needsReminder = (sim.decision.warnings || []).some(w => w.includes('拦截提醒') || w.includes('退回提醒'));
    if (needsReminder) {
      try {
        const cd = sim.collectedData || {};
        const accountNote = queueItem && queueItem.accountNote || '未知账号';

        // 收集所有发货快递单号（主订单所有分包 + 赠品子订单），去重
        const allShipTrackings = (function() {
          const result = [];
          const seen = new Set();
          function addFrom(erpData) {
            const rows = (erpData && erpData.rows && erpData.rows.rows) || [];
            rows.forEach(row => {
              if (row.status !== '卖家已发货') return;
              const ts = (row.trackings && row.trackings.length) ? row.trackings : (row.tracking ? [row.tracking] : []);
              ts.forEach(t => { if (t && !seen.has(t)) { seen.add(t); result.push(t); } });
            });
          }
          addFrom(cd.erpSearch);
          addFrom(cd.giftErpSearch);
          return result;
        })();

        const erpRows = cd.erpSearch && cd.erpSearch.rows && cd.erpSearch.rows.rows || [];
        const internalId = erpRows[0] && erpRows[0].internalId || '';

        // 商品名（取 productArchive.title 前30字，或 subOrders[0].attr1）
        const archiveTitle = cd.productArchive && cd.productArchive.title || '';
        const subOrderAttr = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].attr1 || '';
        const goodsName = (archiveTitle || subOrderAttr).slice(0, 30);
        const qty = cd.ticket && cd.ticket.subOrders && cd.ticket.subOrders[0] && cd.ticket.subOrders[0].afterSaleNum || '';

        // 发一条提醒，快递单号用逗号拼接（含所有分包+赠品）
        const shipTracking = allShipTrackings.join(',');
        const remindArgs = [CLI, 'remind', sim.workOrderNum, accountNote,
          shipTracking, internalId, goodsName, qty ? String(qty) : ''];
        execFileSync('node', remindArgs, EXEC_OPTS);

        // 记录已拦截（每个快递单号单独记录，防止二次工单重复拦截）
        allShipTrackings.forEach(t => {
          db.addIntercept({ shipTracking: t, workOrderNum: sim.workOrderNum, accountNote });
          log(`已记录拦截: ${t}`);
        });
      } catch(e) { log(`remind 失败（非致命）: ${e.message}`); }
    }
  } else if (action === 'escalate') {
    const raw = execFileSync('node', [CLI, 'add-note', sim.workOrderNum, `【待人工】${sim.decision.reason}`], EXEC_OPTS);
    result = JSON.parse(raw);
  } else {
    throw new Error(`未知 action: ${action}`);
  }

  if (!result.success) throw new Error(result.error || '执行失败');

  // 归档
  db.appendCase({
    id: `case-${Date.now()}`,
    workOrderNum: sim.workOrderNum,
    accountNote: sim.accountNote,
    type: sim.collectedData && sim.collectedData.ticket && sim.collectedData.ticket.type,
    groundTruth: { action, reason: sim.decision.reason, source: 'executed' },
    collectedData: sim.collectedData,
    addedAt: new Date().toISOString(),
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
  const raw = execFileSync('node', [CLI, 'open-ticket', workOrderNum], { cwd: BASE, timeout: 30000, encoding: 'utf8' });
  return JSON.parse(raw);
}

async function execCollect(op) {
  const { queueItemId, mode = 'live', accountNum } = op.params;
  const args = ['--limit', '1', mode === 'live' ? '--live' : '--sim'];
  if (accountNum) args.push('--account', String(accountNum));
  const { code } = await spawnAsync('node', [path.join(BASE, 'collect.js'), ...args], {
    cwd: BASE, timeout: 120000,
  });
  if (code !== 0) throw new Error('采集失败');
  return { done: true };
}

module.exports = { enqueue, cancel, getState, isRunning, emergencyStop, resume, isPaused };
