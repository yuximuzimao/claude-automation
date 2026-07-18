'use strict';
/**
 * pipeline.js - 单工单顺序流水线（严格串行，无并行）
 *
 * 关键：collect.js 用 spawn（async）+ Promise 运行，不阻塞事件循环，
 * SSE 能在采集期间实时推送状态变更。
 */

const { spawn, execFileSync, spawnSync } = require('child_process');
const path = require('path');
const confidence = require('./auto-exec-confidence');
const db = require('./data');
const sse = require('./sse');
const { getSkipCompletionStatus } = require('./pipeline-status');
const { inferDecision } = require('../infer');
const { resolveSharedReturnGroup } = require('../return-tracking-group');
const { inferWithAI } = require('../ai-infer');
const { hasConfirmedReturn, getHoursUntilNextScan } = require('../constants');
const { extractShippedTrackings } = require('../helpers');

const BASE = path.join(__dirname, '../..');
const SESSIONS_DIR = path.join(BASE, '../sessions');
const SESSION_STATE_FILE = path.join(BASE, 'data/current-session.json');
const CIRCUIT_BREAKER_FILE = path.join(BASE, 'data/circuit-breaker.json');
const SESSION_TTL_MS = 10 * 60 * 1000;

// ── 风控熔断器（持久化到磁盘，重启不丢失）───────────────────
let circuitBreakerTripped = false;
let circuitBreakerReason = '';

function readCircuitBreaker() {
  try {
    const raw = require('fs').readFileSync(CIRCUIT_BREAKER_FILE, 'utf8');
    const data = JSON.parse(raw);
    if (data && data.tripped) {
      circuitBreakerTripped = true;
      circuitBreakerReason = data.reason || '未知';
      log(`[熔断] 启动时检测到持久化熔断状态: ${circuitBreakerReason}`);
    }
  } catch { /* 文件不存在则视为未熔断 */ }
}

function writeCircuitBreaker(error, label) {
  const data = {
    tripped: true,
    reason: (error && error.message) || '未知风控错误',
    trippedAt: new Date().toISOString(),
    trippedBy: label || 'unknown',
  };
  try { require('fs').writeFileSync(CIRCUIT_BREAKER_FILE, JSON.stringify(data, null, 2)); } catch {}
}

function clearCircuitBreaker() {
  circuitBreakerTripped = false;
  circuitBreakerReason = '';
  try { require('fs').unlinkSync(CIRCUIT_BREAKER_FILE); } catch {}
}

// 启动时读取持久化熔断状态
readCircuitBreaker();

// 注册全局熔断函数（供 wait.js 就地调用）
globalThis.__tripCircuitBreaker = function (error, label) {
  if (circuitBreakerTripped) return;  // 已熔断，不重复写入
  writeCircuitBreaker(error, label);
  circuitBreakerTripped = true;
  circuitBreakerReason = (error && error.message) || '未知风控错误';
  log(`[熔断] 触发！${circuitBreakerReason} (${label})`);
  sse.broadcast('circuit-breaker-tripped', {
    reason: circuitBreakerReason,
    trippedBy: label,
    trippedAt: new Date().toISOString(),
  });
};
function isSameSession(accountNum) {
  try {
    const s = JSON.parse(require('fs').readFileSync(SESSION_STATE_FILE, 'utf8'));
    return s && s.accountNum === accountNum && (Date.now() - s.at) < SESSION_TTL_MS;
  } catch { return false; }
}
function saveSessionState(num) {
  try { require('fs').writeFileSync(SESSION_STATE_FILE, JSON.stringify({ accountNum: num, at: Date.now() })); } catch {}
}

function log(msg) { process.stdout.write(`[pipeline] ${msg}\n`); }

// ── 自动执行条件判断 ──────────────────────────────────────────────
// 基于"沉默=正确"模型：场景指纹在 15 天内执行 ≥10 次且零差评 → 自动执行
function shouldAutoExecute(decision, collectedData, queueItem) {
  return confidence.shouldAutoExecute(decision, collectedData, queueItem);
}

async function autoExecuteApprove(workOrderNum, accountNum) {
  const EXEC_OPTS = { cwd: BASE, timeout: 90000, encoding: 'utf8' };
  if (accountNum) {
    if (isSameSession(accountNum)) {
      log(`[auto-exec] 账号 ${accountNum} 已是当前账号，跳过注入`);
    } else {
      const inj = spawnSync('node', [path.join(SESSIONS_DIR, 'jl.js'), 'inject', String(accountNum)], {
        timeout: 30000, encoding: 'utf8',
      });
      if (inj.status !== 0) throw new Error(`账号 ${accountNum} 注入失败：${(inj.stderr || '').slice(0, 100)}`);
      saveSessionState(accountNum);
    }
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
    proc.on('close', (code) => resolve(code));
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

  // ── 风控熔断检查：已熔断则拒绝所有鲸灵任务 ─────────────────
  if (circuitBreakerTripped) {
    log(`[${workOrderNum}] 跳过 → 风控熔断中: ${circuitBreakerReason}`);
    sse.broadcast('pipeline-update', { stage: 'circuit_breaker', workOrderNum, reason: circuitBreakerReason });
    return;
  }

  // ── 采集 ─────────────────────────────────────────────────────────
  // 注意：不在这里改状态，让 collect.js 自己把 pending→collecting→collected
  // pipeline 只广播 SSE 通知前端刷新
  log(`[${workOrderNum}] 采集`);
  sse.broadcast('pipeline-update', { stage: 'collecting', workOrderNum });

  const collectArgs = ['--live', '--workOrderNum', workOrderNum];
  if (accountNum) collectArgs.push('--account', String(accountNum));
  const collectExitCode = await spawnAsync('node', [path.join(BASE, 'collect.js'), ...collectArgs], { cwd: BASE, timeout: 180000 });

  // collect.js 失败时：状态可能停在 collecting 或 collected，重置为 pending 待下次重试
  if (collectExitCode !== 0) {
    const retries = (queueItem.collectRetries || 0) + 1;
    log(`[${workOrderNum}] collect.js 退出码 ${collectExitCode}，第 ${retries} 次重试`);
    if (retries >= 3) {
      log(`[${workOrderNum}] collect.js 已重试 ${retries} 次，上报人工`);
      db.updateQueueItem(queueItemId, { status: 'simulated', hint: '采集连续失败，需人工核查', collectRetries: retries });
      sse.broadcast('pipeline-update', { stage: 'error', workOrderNum });
      return;
    }
    db.updateQueueItem(queueItemId, { status: 'pending', collectRetries: retries });
    sse.broadcast('pipeline-update', { stage: 'error', workOrderNum });
    return;
  }

  // ── 推理 ─────────────────────────────────────────────────────────
  log(`[${workOrderNum}] 推理`);
  // collect.js 已把状态设为 'collected'，这里改为 'inferring'
  db.updateQueueItem(queueItemId, { status: 'inferring', collectRetries: 0 });
  sse.broadcast('pipeline-update', { stage: 'inferring', workOrderNum });

  // 一次读取，供 getLatestSim、关联工单记录和重复执行检测共用
  const allSims = db.readSimulations();
  const sim = [...allSims].reverse().find(s => s.queueItemId === queueItemId) || null;
  if (!sim || !sim.collectedData) {
    const retries = (queueItem.collectRetries || 0) + 1;
    log(`[${workOrderNum}] 采集无数据（第 ${retries} 次），collect.js 退出码为 0 但未写入 simulation`);
    if (retries >= 3) {
      log(`[${workOrderNum}] 采集无数据已达 ${retries} 次，上报人工`);
      db.updateQueueItem(queueItemId, { status: 'simulated', hint: '采集无结果（collect.js 退出码0但无sim数据），需人工核查', collectRetries: retries });
    } else {
      db.updateQueueItem(queueItemId, { status: 'pending', collectRetries: retries });
    }
    sse.broadcast('pipeline-update', { stage: 'error', workOrderNum });
    return;
  }

  const freshItem = (db.readQueue().items || []).find(i => i.id === queueItemId) || queueItem;
  const hoursUntilNextScan = getHoursUntilNextScan();
  const itemWithHint = { ...freshItem, hoursUntilNextScan, ...(hint ? { hint } : {}) };

  // ── 重复退货单只认平台详情提示，不主动扫描历史单号建立关联 ──────
  const ticketData = sim.collectedData.ticket;
  if (ticketData && ticketData.returnTrackingMultiUse) {
    const pageUsedBy = (ticketData.returnTrackingUsedBy || []).filter(n => String(n) !== String(workOrderNum));
    ticketData.returnTrackingUsedBy = pageUsedBy;
    sim.collectedData.sharedReturnGroup = resolveSharedReturnGroup(sim.collectedData, allSims, workOrderNum);
    log(`[${workOrderNum}] 平台提示退货单 ${ticketData.returnTracking} 多次使用，关联工单:${pageUsedBy.join('、') || '无'}`);
  }

  // ── 已拦截检测：同快递单号已经创建过拦截提醒 → 注入标记 ──────────
  // 检查主订单+赠品的所有分包快递单号（不只是第一行）
  const allShipTrackings = extractShippedTrackings(sim.collectedData);

  for (const shipTracking of allShipTrackings) {
    const interceptRecord = db.hasIntercept(shipTracking);
    if (interceptRecord) {
      // 检查物流是否已有退回节点——若已退回则清除拦截记录，不再上报人工
      const packages = sim.collectedData.logistics && sim.collectedData.logistics.packages || [];
      const hasReturned = packages.some(p => hasConfirmedReturn(p.text));
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

  // 已退款等终结状态：扫描来源进入"已自动执行"列表，其他来源直接完成。
  if (decision.action === 'skip') {
    const autoClosedAt = new Date().toISOString();
    const status = getSkipCompletionStatus(queueItem);
    db.updateSimulation(sim.id, { decision, executedAt: autoClosedAt, hint: hint || null });
    db.updateQueueItem(queueItemId, { status, hint: hint || null });
    sse.broadcast('pipeline-update', { stage: status, workOrderNum });
    log(`[${workOrderNum}] ${status === 'auto_executed' ? '终态归入已自动执行' : '自动归档'} → ${decision.reason}`);
    return;
  }

  // 工单取消 → 等待人工归档；当前扫描主流程会在整轮结束后汇总提醒取消拦截
  if (decision.action === 'wait_archive') {
    db.updateSimulation(sim.id, { decision, hint: hint || null });
    db.updateQueueItem(queueItemId, { status: 'simulated', hint: hint || null });
    sse.broadcast('pipeline-update', { stage: 'simulated', workOrderNum });

    // 清理关联的拦截记录
    try {
      const cd = sim.collectedData || {};
      const allShipTrackings = extractShippedTrackings(cd);
      allShipTrackings.forEach(t => {
        if (db.hasIntercept(t)) {
          db.removeIntercept(t);
          log(`[${workOrderNum}] 工单取消，已清理拦截: ${t}`);
        }
      });
    } catch (e) { log(`[${workOrderNum}] cancel-intercept-cleanup 失败: ${e.message}`); }

    log(`[${workOrderNum}] 等待归档 → ${decision.reason}`);
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
  // skip 记录（工单暂时不可访问）不算真实执行，不阻断后续 approve
  if (!hint && shouldAutoExecute(decision, sim.collectedData, freshItem)) {
    const prevExecuted = allSims.some(
      s => s.workOrderNum === workOrderNum && s.mode === 'live' && s.id !== sim.id && !!s.executedAt && s.decision?.action !== 'skip'
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
      // 不在此处写 cases.jsonl——归档时才写入，保证历史记录只有一条
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
		// 熔断后停止接受新任务，已在途任务自然结束
		if (circuitBreakerTripped) {
			log(`熔断中，停止处理剩余 ${items.length - items.indexOf(item)} 张工单`);
			break;
		}
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

  // 风控熔断检查
  if (circuitBreakerTripped) {
    log(`[${queueItem.workOrderNum}] 跳过重处理 → 风控熔断中: ${circuitBreakerReason}`);
    sse.broadcast('pipeline-update', { stage: 'circuit_breaker', workOrderNum: queueItem.workOrderNum, reason: circuitBreakerReason });
    return;
  }

  // 已执行完成的工单不再重处理（防止平台已退款后重复操作）
  if (['auto_executed', 'done'].includes(queueItem.status)) {
    log(`[${queueItem.workOrderNum}] 跳过重处理 → 已执行完成 (${queueItem.status})`);
    return;
  }

  // 重置为 pending，让 collect.js 重新采集
  db.updateQueueItem(queueItemId, { status: 'pending', hint: hint || null });
  await processOne(queueItem, { hint });
}

module.exports = { runPipeline, reprocessOne, clearCircuitBreaker, isCircuitBreakerTripped: () => circuitBreakerTripped };
