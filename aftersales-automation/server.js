'use strict';
const path = require('path');
const fs = require('fs');

// ── 单实例锁（防止多个 server.js 进程同时运行导致重复扫描）─────────
const LOCK_FILE = path.join(__dirname, 'data/.server.lock');

function cleanupLock() { try { fs.unlinkSync(LOCK_FILE); } catch(e) {} }

try {
  const existingPid = fs.readFileSync(LOCK_FILE, 'utf8').trim();
  // 检查旧进程是否仍在运行
  try {
    process.kill(Number(existingPid), 0); // signal 0 = 只检查不发送
    console.error(`[server] 已有实例运行中 (PID ${existingPid})，退出`);
    process.exit(1);
  } catch(e) { /* 旧进程不存在，继续 */ }
} catch(e) { /* lock 文件不存在，继续 */ }
fs.writeFileSync(LOCK_FILE, String(process.pid));

// 确保 lock 文件在所有退出路径上被清理
process.on('exit', cleanupLock);
process.on('SIGINT', () => { cleanupLock(); process.exit(0); });
process.on('SIGTERM', () => { cleanupLock(); process.exit(0); });
process.on('SIGHUP', () => { cleanupLock(); process.exit(0); });

// ── 全局崩溃防护（防止 uncaughtException/unhandledRejection 杀死进程）────
const CRASH_LOG = path.join(__dirname, 'data/crash.log');
function logCrash(type, err) {
  const ts = new Date().toISOString();
  const msg = `[${ts}] ${type}: ${err && err.stack ? err.stack : err}\n`;
  try { fs.appendFileSync(CRASH_LOG, msg); } catch(e) {}
  console.error(msg);
}

process.on('uncaughtException', (err) => {
  logCrash('uncaughtException', err);
  // 致命异常：清理锁后退出，由外部进程管理器重启
  cleanupLock();
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logCrash('unhandledRejection', reason);
  // unhandledRejection 通常不是致命的，记录但不退出
  // Node.js 默认行为在 v15+ 会杀死进程，覆盖为仅记录
  console.error('未处理的Promise拒绝（已捕获，进程继续运行）:', reason);
});

// 自动从 Claude Code 设置注入 API 配置（若 env 未手动设置）
(function injectClaudeEnv() {
  const needsKey = !process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN;
  const needsUrl = !process.env.ANTHROPIC_BASE_URL;
  if (!needsKey && !needsUrl) return;
  try {
    const os = require('os'), fs = require('fs'), path = require('path');
    const settingsPath = path.join(os.homedir(), '.claude', 'settings.json');
    const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    const env = settings.env || {};
    if (needsKey && env.ANTHROPIC_AUTH_TOKEN) {
      process.env.ANTHROPIC_AUTH_TOKEN = env.ANTHROPIC_AUTH_TOKEN;
      console.log('[server] 已从 Claude 设置注入 ANTHROPIC_AUTH_TOKEN');
    }
    if (needsUrl && env.ANTHROPIC_BASE_URL) {
      process.env.ANTHROPIC_BASE_URL = env.ANTHROPIC_BASE_URL;
      console.log('[server] 已从 Claude 设置注入 ANTHROPIC_BASE_URL');
    }
  } catch(e) { /* settings 不存在或格式错误，跳过 */ }
})();

const express = require('express');
const routes = require('./lib/server/routes');
const opQueue = require('./lib/server/op-queue');
const { SCAN_HOURS } = require('./lib/constants');

const PORT = process.env.PORT || 3457;
const SESSIONS_DIR = path.join(__dirname, '../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/api', routes);
app.get('/health', (req, res) => res.json({ ok: true, ts: new Date().toISOString() }));

// ── 自动扫描 ──────────────────────────────────────────────────────

let skipNextScan = false;

app.post('/api/skip-next-scan', (req, res) => {
  skipNextScan = true;
  console.log('[auto-scan] 下次扫描已标记跳过');
  res.json({ ok: true, message: '下次扫描将被跳过' });
});

function runAutoScan() {
  if (skipNextScan) {
    skipNextScan = false;
    console.log('[auto-scan] 本次扫描已跳过（手动标记）');
    return;
  }
  try {
    const accounts = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));
    const numsToScan = Object.keys(accounts)
      .map(Number)
      .filter(n => {
        const a = accounts[String(n)];
        return a && fs.existsSync(path.join(SESSIONS_DIR, a.file));
      })
      .sort((a, b) => a - b);

    for (const num of numsToScan) {
      const account = accounts[String(num)];
      const note = (account && (account.note || account.name)) || `账号${num}`;
      opQueue.enqueue('scan-account', `扫描 ${note}`, { accountNum: num, accountNote: note });
    }
    opQueue.enqueue('scan-finalize', '巡检收尾', {});
  } catch (e) {
    console.error(`[auto-scan] 读取账号失败: ${e.message}`);
  }
}

// 精确到点的定时调度（8/12/16/20）
let scanTimer = null;

function scheduleNextScan() {
  // 先清除可能残留的旧 timer，防止多次调用叠加（resumeScan 连续触发时重复入队根因）
  if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }
  const now = new Date();
  const h = now.getHours(), m = now.getMinutes(), s = now.getSeconds();
  // 只找严格大于当前小时的下一个整点（当前整点不重复触发）
  let nextHour = SCAN_HOURS.find(hour => hour > h);
  let daysAhead = 0;
  if (nextHour === undefined) { nextHour = SCAN_HOURS[0]; daysAhead = 1; }

  const next = new Date(now);
  next.setDate(next.getDate() + daysAhead);
  next.setHours(nextHour, 0, 0, 0);

  const ms = next.getTime() - now.getTime();
  console.log(`[auto-scan] 下次: ${next.toLocaleString('zh-CN')}（${Math.round(ms / 60000)} 分钟后）`);
  app.locals.nextScanAt = next.toISOString();

  scanTimer = setTimeout(() => {
    scanTimer = null;
    if (!opQueue.isPaused()) runAutoScan();
    scheduleNextScan();
  }, ms);
}

// 供 routes.js 调用的扫描控制（通过 app.locals 传递）
app.locals.stopScan = () => {
  if (scanTimer) { clearTimeout(scanTimer); scanTimer = null; }
  app.locals.nextScanAt = null;
  console.log('[auto-scan] 定时扫描已暂停');
};
app.locals.resumeScan = () => {
  scheduleNextScan();
  console.log('[auto-scan] 定时扫描已恢复');
};

app.listen(PORT, async () => {
  console.log(`黑总专属售后系统已启动: http://localhost:${PORT}`);

  // ===== ERP 启动闸门：先校验登录，再开放工单队列 =====
  const { checkLogin, recoverLogin, updateErpHealth, loadErpHealth, alertErpDown } = require('./lib/erp/navigate');
  const { getTargetIds } = require('./lib/targets');
  let startupErpId = null;
  try {
    // 确保 CDP 就绪（Chrome 可能尚未完全启动）
    for (let i = 0; i < 3; i++) {
      try { ({ erpId: startupErpId } = await getTargetIds()); break; }
      catch { await new Promise(r => setTimeout(r, 1000)); }
    }
    if (!startupErpId) throw new Error('CDP target 未就绪（Chrome 可能未启动）');

    const status = await checkLogin(startupErpId);
    if (!status.loggedIn) {
      console.log('[startup] ERP 未登录，尝试恢复...');
      await recoverLogin(startupErpId);
    }
    updateErpHealth({ status: 'up', lastOkTime: new Date().toISOString(), consecutiveAuthFail: 0 });
    console.log('[startup] ERP 登录校验通过');
  } catch (e) {
    console.error('[startup] ERP 登录校验失败:', e.message);
    updateErpHealth({ status: 'down', failReason: e.message, lastFailTime: new Date().toISOString() });
    alertErpDown(e.message); // 告警但不阻止启动（鲸灵扫描仍可运行）
  }
  // ===== 闸门结束，以下正常启动 =====

  // ── 启动时数据清理 ────────────────────────────────────────────────
  startupDataCleanup();

  scheduleNextScan();
  startErpHeartbeat(getTargetIds, checkLogin, recoverLogin, updateErpHealth, loadErpHealth, alertErpDown);

  // 启动时清理残留状态：collecting/collected（上次进程崩溃留下的）重置为 pending
  // 然后把所有 pending 工单入队推理
  const db = require('./lib/server/data');
  const stale = (db.readQueue().items || []).filter(i =>
    ['collecting', 'collected', 'inferring'].includes(i.status) && i.mode === 'live'
  );
  for (const item of stale) {
    db.updateQueueItem(item.id, { status: 'pending' });
  }
  if (stale.length > 0) console.log(`[startup] 重置 ${stale.length} 条残留状态工单为 pending`);

  const pending = (db.readQueue().items || []).filter(i => i.status === 'pending' && i.mode === 'live');
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    opQueue.enqueue('reprocess-one', label, { queueItemId: item.id });
  }
  if (pending.length > 0) console.log(`[startup] 入队 ${pending.length} 条 pending 工单`);
});

// ── 启动时数据清理 ────────────────────────────────────────────────────
// simulations.jsonl: 保留最新 500 条（循环缓冲）
// queue.json: 清理 30 天前的 done 条目
function startupDataCleanup() {
  const SIM_FILE = path.join(__dirname, 'data/simulations.jsonl');
  const SIM_MAX = 500;
  const QUEUE_KEEP_DAYS = 30;

  // 1. Trim simulations.jsonl
  try {
    const lines = fs.readFileSync(SIM_FILE, 'utf8').split('\n').filter(l => l.trim());
    if (lines.length > SIM_MAX) {
      const kept = lines.slice(-SIM_MAX);
      fs.writeFileSync(SIM_FILE, kept.join('\n') + '\n');
      console.log(`[cleanup] simulations.jsonl: ${lines.length} → ${kept.length} 条（保留最新 ${SIM_MAX}）`);
    }
  } catch (e) {
    if (e.code !== 'ENOENT') console.error('[cleanup] simulations.jsonl 清理失败:', e.message);
  }

  // 2. Clean old done items from queue.json
  try {
    const db = require('./lib/server/data');
    const q = db.readQueue();
    const cutoff = Date.now() - QUEUE_KEEP_DAYS * 24 * 60 * 60 * 1000;
    const before = (q.items || []).length;
    q.items = (q.items || []).filter(i => {
      if (i.status !== 'done') return true;
      const ts = i.doneAt || i.executedAt || i.updatedAt || i.createdAt;
      return ts ? new Date(ts).getTime() > cutoff : true; // 无时间戳保留
    });
    if (q.items.length < before) {
      fs.writeFileSync(path.join(__dirname, 'data/queue.json'), JSON.stringify(q, null, 2));
      console.log(`[cleanup] queue.json: 清理 ${before - q.items.length} 条 30 天前的 done 记录，剩余 ${q.items.length} 条`);
    }
  } catch (e) {
    console.error('[cleanup] queue.json 清理失败:', e.message);
  }
}

// ── ERP 保活心跳（1小时）─────────────────────────────────────────────
// 防止 ERP 服务端 session 超时（实测约 4-8h），避免登录恢复失败的情况
function startErpHeartbeat(getTargetIds, checkLogin, recoverLogin, updateErpHealth, loadErpHealth, alertErpDown) {
  const HEARTBEAT_INTERVAL = 60 * 60 * 1000; // 1 小时
  const ALERT_REPEAT_MS = 30 * 60 * 1000;    // 30 分钟重复告警

  let heartbeatRunning = false;

  async function runHeartbeat() {
    if (heartbeatRunning) return; // 防止上次未完成时重入
    heartbeatRunning = true;
    try {
      let erpId;
      try { ({ erpId } = await getTargetIds()); }
      catch { console.log('[erp-heartbeat] 获取 ERP tab 失败，跳过本次心跳'); return; }

      const loginStatus = await checkLogin(erpId);
      if (loginStatus.loggedIn) {
        // 已登录：用 fetch + cache bust 续期（比 location.reload 副作用小）
        const fetchResult = await require('./lib/cdp').eval(erpId,
          `(async function(){
            try {
              var r = await fetch(location.href + (location.href.includes('?') ? '&' : '?') + '_t=' + Date.now(), {credentials:'include'});
              return JSON.stringify({ ok: r.ok, status: r.status });
            } catch(e) { return JSON.stringify({ ok: false, err: e.message }); }
          })()`
        ).catch(() => null);

        // 验证 fetch 后 session 仍有效
        const afterFetch = await checkLogin(erpId);
        if (afterFetch.loggedIn) {
          updateErpHealth({ status: 'up', lastOkTime: new Date().toISOString(), consecutiveAuthFail: 0 });
          console.log(`[erp-heartbeat] ERP 在线，fetch 续期完成 (${fetchResult && fetchResult.status || '?'})`);
        } else {
          // fetch 后 session 消失了（可能服务端确认失效），尝试恢复
          console.log('[erp-heartbeat] fetch 后检测到掉线，尝试 recoverLogin');
          await recoverLogin(erpId);
          updateErpHealth({ status: 'up', lastOkTime: new Date().toISOString(), consecutiveAuthFail: 0 });
          console.log('[erp-heartbeat] recoverLogin 成功');
        }
      } else {
        // 未登录：直接尝试恢复
        console.log('[erp-heartbeat] ERP 未登录，尝试 recoverLogin');
        try {
          await recoverLogin(erpId);
          updateErpHealth({ status: 'up', lastOkTime: new Date().toISOString(), consecutiveAuthFail: 0 });
          console.log('[erp-heartbeat] recoverLogin 成功');
        } catch (recoverErr) {
          console.error('[erp-heartbeat] recoverLogin 失败:', recoverErr.message);
          updateErpHealth({ status: 'down', lastFailTime: new Date().toISOString(), failReason: recoverErr.message });
          // 重复告警：若 health 记录的 lastAlertTime 距今超过 30 分钟则再次告警
          const health = loadErpHealth();
          const lastAlert = health.lastAlertTime ? new Date(health.lastAlertTime).getTime() : 0;
          if (Date.now() - lastAlert > ALERT_REPEAT_MS) {
            updateErpHealth({ lastAlertTime: new Date().toISOString() });
            alertErpDown(`心跳恢复失败 - ${recoverErr.message}`);
          }
        }
      }
    } catch (e) {
      console.error('[erp-heartbeat] 心跳异常:', e.message);
    } finally {
      heartbeatRunning = false;
    }
  }

  // 首次心跳在 1 小时后触发（避免启动校验刚完成就再做一次）
  setInterval(runHeartbeat, HEARTBEAT_INTERVAL);
  console.log(`[erp-heartbeat] 已启动，每 ${HEARTBEAT_INTERVAL / 60000} 分钟保活一次`);
}
