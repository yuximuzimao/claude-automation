'use strict';

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
const path = require('path');
const fs = require('fs');
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

app.listen(PORT, () => {
  console.log(`黑总专属售后系统已启动: http://localhost:${PORT}`);
  scheduleNextScan();
  // 启动时处理队列里已有的 pending 工单（每张单独入队，可逐条取消）
  const db = require('./lib/server/data');
  const pending = (db.readQueue().items || []).filter(i => i.status === 'pending' && i.mode === 'live');
  for (const item of pending) {
    const label = `${item.accountNote || '账号' + item.accountNum} | ${item.workOrderNum}`;
    opQueue.enqueue('reprocess-one', label, { queueItemId: item.id });
  }
  if (pending.length > 0) console.log(`[startup] 入队 ${pending.length} 条 pending 工单`);
});
