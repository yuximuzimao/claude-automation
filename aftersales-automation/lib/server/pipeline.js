'use strict';
/**
 * pipeline.js - 单工单顺序流水线（严格串行，无并行）
 *
 * 关键：collect.js 用 spawn（async）+ Promise 运行，不阻塞事件循环，
 * SSE 能在采集期间实时推送状态变更。
 */

const { spawn, execFileSync, spawnSync } = require('child_process');
const path = require('path');
const db = require('./data');
const sse = require('./sse');
const { inferDecision } = require('../infer');
const { inferWithAI } = require('../ai-infer');
const { RETURN_KEYWORDS, getHoursUntilNextScan } = require('../constants');

const BASE = path.join(__dirname, '../..');
const SESSIONS_DIR = path.join(BASE, '../sessions');

function log(msg) { process.stdout.write(`[pipeline] ${msg}\n`); }

// ── 自动执行条件判断 ──────────────────────────────────────────────
function shouldAutoExecute(decision, collectedData, queueItem) {
  // 2026-04-26：关闭自动执行，切回人工确认模式（待规则稳定后重新开启）
  return false;
}

async function autoExecuteApprove(workOrderNum, accountNum) {
  const EXEC_OPTS = { cwd: BASE, timeout: 90000, encoding: 'utf8' };
  if (accountNum) {
    const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
      timeout: 30000, encoding: 'utf8',
    });
    if (inj.status !== 0) throw new Error(`账号 ${accountNum} 注入失败：${(inj.stderr || '').slice(0, 100)}`);
  }
  const raw = execFileSync('node', [path.join(BASE, 'cli.js'), 'approve', workOrderNum], EXEC_OPTS);
  const result = JSON.parse(raw);
  if (!result.success) throw new Error(result.error || '执行失败');
  return result;
}

// async 包装 spawn，不阻塞事件循环
function spawnAsync(cmd, args, opts) {
  return new Promise((resolve) => {
    const proc = spawn(cmd, args, { ...opts, stdio: ['ignore', 'ignore', 'inherit'] });
    proc.on('close', resolve);
    proc.on('error', () => resolve(1));
  });
}

function getPendingItems(mode) {
  const queue = db.readQueue();
  return (queue.items || []).filter(i =>
    i.status === 'pending' && (mode === 'all' || i.mode === mode)
  );
}

async function processOne(queueItem, options = {}) {
  const { hint } = options;
  const { workOrderNum, accountNum, id: queueItemId } = queueItem;

  // ── 采集 ─────────────────────────────────────────────────────────
  // 注意：不在这里改状态，让 collect.js 自己把 pending→collecting→collected
  // pipeline 只广播 SSE 通知前端刷新
  log(`[${workOrderNum}] 采集`);
  sse.broadcast('pipeline-update', { stage: 'collecting', workOrderNum });

  const collectArgs = ['--live', '--workOrderNum', workOrderNum];
  if (accountNum) collectArgs.push('--account', String(accountNum));
  const collectExitCode = await spawnAsync('node', [path.join(BASE, 'collect.js'), ...collectArgs], { cwd: BASE, timeout: 120000 });

  // collect.js 失败时：状态可能停在 collecting 或 collected，重置为 pending 待下次重试
  if (collectExitCode !== 0) {
    log(`[${workOrderNum}] collect.js 退出码 ${collectExitCode}，重置为 pending`);
    db.updateQueueItem(queueItemId, { status: 'pending' });
    sse.broadcast('pipeline-update', { stage: 'error', workOrderNum });
    return;
  }

  // ── 推理 ─────────────────────────────────────────────────────────
  log(`[${workOrderNum}] 推理`);
  // collect.js 已把状态设为 'collected'，这里改为 'inferring'
  db.updateQueueItem(queueItemId, { status: 'inferring' });
  sse.broadcast('pipeline-update', { stage: 'inferring', workOrderNum });

  // 一次读取，供 getLatestSim 和多次使用检测共用
  const allSims = db.readSimulations();
  const sim = [...allSims].reverse().find(s => s.queueItemId === queueItemId) || null;
  if (!sim || !sim.collectedData) {
    log(`[${workOrderNum}] 采集失败`);
    db.updateQueueItem(queueItemId, { status: 'pending' });
    sse.broadcast('pipeline-update', { stage: 'error', workOrderNum });
    return;
  }

  const freshItem = (db.readQueue().items || []).find(i => i.id === queueItemId) || queueItem;
  const hoursUntilNextScan = getHoursUntilNextScan();
  const itemWithHint = { ...freshItem, hoursUntilNextScan, ...(hint ? { hint } : {}) };

  // ── 退货快递单号多次使用检测（双来源：页面可见文本 + DB交叉比对）──
  const returnTracking = sim.collectedData.ticket && sim.collectedData.ticket.returnTracking;
  if (returnTracking) {
    // 来源1：采集时页面已标注「多次使用」（主来源，含平台已知关联工单号）
    const pageMultiUse = sim.collectedData.ticket.returnTrackingMultiUse || false;
    const pageUsedBy = sim.collectedData.ticket.returnTrackingUsedBy || [];

    // 来源2：DB交叉比对（补充：找本系统内其他工单使用同一快递单号）
    const dbConflictNums = [];
    const currentSubOrderIds = new Set(
      ((sim.collectedData.ticket && sim.collectedData.ticket.subOrders) || []).map(o => String(o.id || o))
    );
    allSims.forEach(s => {
      if (s.id === sim.id) return;
      if (s.workOrderNum === workOrderNum) return;  // 同一工单的历史sim不算冲突
      const rt = s.collectedData && s.collectedData.ticket && s.collectedData.ticket.returnTracking;
      if (!rt || rt !== returnTracking) return;
      // 同一子订单（同一笔订单的多个售后工单）不算冲突
      const otherSubOrderIds = ((s.collectedData.ticket.subOrders) || []).map(o => String(o.id || o));
      if (otherSubOrderIds.some(id => currentSubOrderIds.has(id))) return;
      dbConflictNums.push(s.workOrderNum);
    });

    // 合并两个来源（去重）
    const allUsedBy = [...new Set([...pageUsedBy, ...dbConflictNums])];
    if (pageMultiUse || allUsedBy.length > 0) {
      log(`[${workOrderNum}] 退货快递单 ${returnTracking} 多次使用（页面标注:${pageMultiUse}，关联工单:${allUsedBy.join('、') || '无'}）`);
      sim.collectedData.ticket.returnTrackingMultiUse = true;
      sim.collectedData.ticket.returnTrackingUsedBy = allUsedBy;
    }
  }

  // ── 已拦截检测：同快递单号已经创建过拦截提醒 → 注入标记 ──────────
  // 检查主订单+赠品的所有分包快递单号（不只是第一行）
  const allShipTrackings = (function(cd) {
    const result = [];
    const seen = new Set();
    function addFrom(erpData) {
      const rows = (erpData && erpData.rows && erpData.rows.rows) || [];
      rows.forEach(row => {
        if (!['卖家已发货', '交易成功', '交易关闭'].includes(row.status)) return;
        const ts = (row.trackings && row.trackings.length) ? row.trackings : (row.tracking ? [row.tracking] : []);
        ts.forEach(t => { if (t && !seen.has(t)) { seen.add(t); result.push(t); } });
      });
    }
    addFrom(cd.erpSearch);
    addFrom(cd.giftErpSearch);
    return result;
  })(sim.collectedData);

  for (const shipTracking of allShipTrackings) {
    const interceptRecord = db.hasIntercept(shipTracking);
    if (interceptRecord) {
      // 检查物流是否已有退回节点——若已退回则清除拦截记录，不再上报人工
      const packages = sim.collectedData.logistics && sim.collectedData.logistics.packages || [];
      const hasReturned = packages.some(p => RETURN_KEYWORDS.some(kw => (p.text || '').includes(kw)));
      if (hasReturned) {
        log(`[${workOrderNum}] 快递 ${shipTracking} 已退回，清除拦截记录`);
        db.removeIntercept(shipTracking);
        // 不注入 intercepted，让推理走正常「已退回→同意退款」分支
      } else {
        log(`[${workOrderNum}] 快递 ${shipTracking} 已拦截待退回（来自 ${interceptRecord.workOrderNum}）`);
        // 注入第一个找到的拦截记录（任一快递被拦截均触发上报）
        if (!sim.collectedData.intercepted) {
          sim.collectedData.intercepted = { tracking: shipTracking, ...interceptRecord };
        }
      }
    }
  }

  let decision;
  try {
    if (hint) {  // claude CLI 无需 API key，hint 存在即启用 AI
      log(`[${workOrderNum}] AI推理 hint="${hint.slice(0, 40)}"`);
      decision = await inferWithAI(sim, itemWithHint);
      log(`[${workOrderNum}] AI推理完成 → ${decision.action}`);
    } else {
      decision = inferDecision(sim, itemWithHint);
    }
  } catch (e) {
    log(`[${workOrderNum}] 推理失败 (${e.message})，降级为规则推理`);
    try {
      decision = inferDecision(sim, itemWithHint);
      if (!decision.warnings) decision.warnings = [];
      if (hint) decision.warnings.push(`AI推理失败，已降级为规则推理：${e.message.slice(0, 60)}`);
    } catch (e2) {
      decision = { action: 'escalate', reason: `推理异常: ${e2.message}`, confidence: 'low', rulesApplied: [], warnings: [] };
    }
  }
  decision.inferredAt = new Date().toISOString();
  decision.auto = true;
  if (hint) decision.hinted = true;

  // 已退款等终结状态 → 自动归档，无需用户操作
  if (decision.action === 'skip') {
    const autoClosedAt = new Date().toISOString();
    db.updateSimulation(sim.id, { decision, executedAt: autoClosedAt, hint: hint || null });
    db.updateQueueItem(queueItemId, { status: 'done', hint: hint || null });
    sse.broadcast('pipeline-update', { stage: 'done', workOrderNum });
    log(`[${workOrderNum}] 自动归档 → ${decision.reason}`);
    return;
  }

  if (decision.waitingRescan) {
    db.updateSimulation(sim.id, { decision, hint: hint || null });
    db.updateQueueItem(queueItemId, { status: 'waiting', hint: hint || null });
    sse.broadcast('pipeline-update', { stage: 'waiting', workOrderNum });
    log(`[${workOrderNum}] 标记等待重查 → ${decision.reason.slice(0, 60)}`);
    return;
  }

  // ── 自动执行：七天无理由退货 approve → 直接同意，无需人工确认 ────
  // 执行前再检查：历史是否已有该工单的执行记录（防止同一工单被第二次采集推理触发重复自动执行）
  if (!hint && shouldAutoExecute(decision, sim.collectedData, freshItem)) {
    const prevExecuted = allSims.some(
      s => s.workOrderNum === workOrderNum && s.mode === 'live' && s.id !== sim.id && !!s.executedAt
    );
    if (prevExecuted) {
      log(`[${workOrderNum}] 跳过自动执行 → 已有执行记录，直接归档`);
      db.updateSimulation(sim.id, { decision, skippedReason: '已有执行记录' });
      db.updateQueueItem(queueItemId, { status: 'done' });
      sse.broadcast('pipeline-update', { stage: 'done', workOrderNum });
      return;
    }
    db.updateSimulation(sim.id, { decision });
    db.updateQueueItem(queueItemId, { status: 'auto_executing' });
    sse.broadcast('pipeline-update', { stage: 'auto_executing', workOrderNum });
    log(`[${workOrderNum}] 触发自动执行 approve`);
    try {
      await autoExecuteApprove(workOrderNum, freshItem.accountNum);
      const autoExecutedAt = new Date().toISOString();
      db.appendCase({
        id: `case-${Date.now()}`,
        workOrderNum,
        accountNote: freshItem.accountNote,
        type: (sim.collectedData.ticket && sim.collectedData.ticket.type) || '',
        groundTruth: { action: 'approve', reason: decision.reason, source: 'auto_executed' },
        collectedData: sim.collectedData,
        addedAt: autoExecutedAt,
      });
      db.updateSimulation(sim.id, { decision, autoExecutedAt, executedAt: autoExecutedAt });
      db.updateQueueItem(queueItemId, { status: 'auto_executed' });
      sse.broadcast('pipeline-update', { stage: 'auto_executed', workOrderNum });
      log(`[${workOrderNum}] 自动执行完成`);
    } catch (e) {
      log(`[${workOrderNum}] 自动执行失败 (${e.message})，降级为 simulated`);
      db.updateSimulation(sim.id, { decision, autoExecuteError: e.message });
      db.updateQueueItem(queueItemId, { status: 'simulated' });
      sse.broadcast('pipeline-update', { stage: 'simulated', workOrderNum });
    }
    return;
  }

  db.updateSimulation(sim.id, { decision, hint: hint || null });
  db.updateQueueItem(queueItemId, { status: 'simulated', hint: hint || null });
  sse.broadcast('pipeline-update', { stage: 'simulated', workOrderNum });
  log(`[${workOrderNum}] 完成 → ${decision.action}`);
}

async function runPipeline(mode = 'live') {
  sse.broadcast('pipeline-update', { stage: 'start', mode });

  try {
    const items = getPendingItems(mode);
    log(`待处理 ${items.length} 张`);
    for (const item of items) {
      await processOne(item);
    }
    sse.broadcast('pipeline-update', { stage: 'done', mode, count: items.length });
    log(`全部完成`);
  } catch (e) {
    log(`异常: ${e.message}`);
    sse.broadcast('pipeline-update', { stage: 'error', error: e.message });
  }
}

async function reprocessOne(queueItemId, hint = '') {
  sse.broadcast('pipeline-update', { stage: hint ? 'optimizing' : 'collecting' });
  const queue = db.readQueue();
  const queueItem = (queue.items || []).find(i => i.id === queueItemId);
  if (!queueItem) throw new Error('未找到队列项');

  // 已执行完成的工单不再重处理（防止平台已退款后重复操作）
  if (['auto_executed', 'done'].includes(queueItem.status)) {
    log(`[${queueItem.workOrderNum}] 跳过重处理 → 已执行完成 (${queueItem.status})`);
    return;
  }
  // 没有 hint 时：检查历史 sim 是否已有执行记录（防止第二次 scan-finalize 重复处理）
  if (!hint) {
    const sims = db.readSimulations();
    const prevExec = sims.some(s => s.workOrderNum === queueItem.workOrderNum && s.mode === 'live' && !!s.executedAt);
    if (prevExec) {
      log(`[${queueItem.workOrderNum}] 跳过重处理 → 历史已有执行记录，归档`);
      db.updateQueueItem(queueItemId, { status: 'done' });
      sse.broadcast('pipeline-update', { stage: 'done', workOrderNum: queueItem.workOrderNum });
      return;
    }
  }

  // 重置为 pending，让 collect.js 重新采集
  db.updateQueueItem(queueItemId, { status: 'pending', hint: hint || null });
  await processOne(queueItem, { hint });
}

module.exports = { runPipeline, reprocessOne };
