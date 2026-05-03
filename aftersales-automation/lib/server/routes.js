'use strict';
/**
 * WHAT: Express API 路由（43 个端点）
 * WHERE: server.js → 注册为 /api 前缀
 * WHY: HTTP 接口层，所有业务逻辑在 lib/ 下，此处只做参数解析和调用转发
 * ENTRY: server.js: app.use('/api', routes)
 */
const express = require('express');
const { execFileSync, spawnSync } = require('child_process');
const path = require('path');
const db = require('./data');
const sse = require('./sse');
const opQueue = require('./op-queue');

const router = express.Router();
const CLI = path.join(__dirname, '../../cli.js');
const BASE = path.join(__dirname, '../..');
const SESSIONS_DIR = path.join(BASE, '../sessions');
const ACCOUNTS_FILE = path.join(SESSIONS_DIR, 'accounts.json');
const ACCOUNT_STATUS_FILE = path.join(BASE, 'data/account-status.json');

// ── 紧急停止 / 恢复 ───────────────────────────────────────────────

router.post('/emergency-stop', (req, res) => {
  opQueue.emergencyStop();
  if (req.app.locals.stopScan) req.app.locals.stopScan();
  res.json({ ok: true, paused: true });
});

router.post('/resume', (req, res) => {
  opQueue.resume();
  if (req.app.locals.resumeScan) req.app.locals.resumeScan();
  res.json({ ok: true, paused: false });
});

// ── Open Ticket（注入账号 + 打开工单详情）────────────────────────
router.post('/open-ticket', (req, res) => {
  const { workOrderNum, accountNum } = req.body;
  if (!workOrderNum) return res.status(400).json({ error: 'workOrderNum required' });
  const label = `查看工单 ${workOrderNum}`;
  const op = opQueue.enqueue('open-ticket', label, { workOrderNum, accountNum });
  res.status(202).json({ ok: true, opId: op.id });
});

// ── Queue ─────────────────────────────────────────────────────────

router.get('/queue', (req, res) => {
  const queue = db.readQueue();
  if (req.query.mode) {
    queue.items = queue.items.filter(i => i.mode === req.query.mode);
  }
  res.json(queue);
});

router.post('/queue', (req, res) => {
  const { workOrderNum, accountNum, accountNote, mode, source, type, urgency, groundTruth } = req.body;
  if (!workOrderNum) return res.status(400).json({ error: 'workOrderNum required' });

  // 校验 accountNum 与 accountNote 匹配，防止跨店铺注入
  if (accountNum) {
    try {
      const accounts = JSON.parse(require('fs').readFileSync(ACCOUNTS_FILE, 'utf8'));
      const expectedNote = accounts[String(accountNum)] && accounts[String(accountNum)].note;
      if (expectedNote && accountNote && expectedNote !== accountNote) {
        return res.status(400).json({ error: `账号${accountNum}对应店铺为「${expectedNote}」，与提交的「${accountNote}」不一致` });
      }
    } catch(e) { /* accounts 文件不存在，跳过校验 */ }
  }

  const item = db.addQueueItem({ workOrderNum, accountNum, accountNote, mode: mode || 'sim', source: source || 'web', type, urgency, groundTruth });
  if (!item) return res.status(409).json({ error: '工单号已存在且未完成' });
  res.json(item);
});

router.delete('/queue/:id', (req, res) => {
  const ok = db.deleteQueueItem(req.params.id);
  if (!ok) return res.status(404).json({ error: '未找到' });
  res.json({ ok: true });
});

// ── Simulations ───────────────────────────────────────────────────

router.get('/simulations', (req, res) => {
  const filter = {};
  if (req.query.mode) filter.mode = req.query.mode;
  if (req.query.status) filter.status = req.query.status;
  if (req.query.limit) filter.limit = parseInt(req.query.limit);
  res.json(db.readSimulations(filter));
});

router.get('/simulations/:id', (req, res) => {
  const sim = db.getSimulation(req.params.id);
  if (!sim) return res.status(404).json({ error: '未找到' });
  res.json(sim);
});

// 重新采集+推理（含评价内容 hint）
router.post('/simulations/:id/reinfer', (req, res) => {
  const sim = db.getSimulation(req.params.id);
  if (!sim) return res.status(404).json({ error: '未找到' });
  const hint = (req.body.hint || '').trim();
  const label = hint ? `AI改进 ${sim.workOrderNum}` : `重新采集推理 ${sim.workOrderNum}`;
  const op = opQueue.enqueue('reinfer', label, { simId: sim.id, hint });
  res.status(202).json({ ok: true, opId: op.id, hint: !!hint });
});

// 批量执行（拆成多条 execute 入队，逐一串行）
router.post('/simulations/batch-execute', (req, res) => {
  const sims = db.readSimulations({ mode: 'live' });
  const toExec = sims.filter(s => s.decision && !s.executedAt && s.mode === 'live');
  for (const sim of toExec) {
    const actionLabel = { approve: '同意退款', reject: '拒绝退款', escalate: '上报人工' }[sim.decision.action] || sim.decision.action;
    opQueue.enqueue('execute', `执行 ${sim.workOrderNum} ${actionLabel}`, { simId: sim.id });
  }
  res.status(202).json({ ok: true, count: toExec.length });
});

// 批量重来（每条工单单独入队，前端可见每条进度）
router.post('/queue/batch-reprocess', (req, res) => {
  const queue = db.readQueue();
  const items = (queue.items || []).filter(i => i.mode === 'live' && i.status !== 'done');
  for (const item of items) {
    db.updateQueueItem(item.id, { status: 'pending', hint: null });
    opQueue.enqueue('reprocess-one', `${item.workOrderNum} 采集推理`, { queueItemId: item.id });
  }
  res.status(202).json({ ok: true, count: items.length });
});

// 单条工单重新采集+推理（reset → pending → reprocess-one 入队）
router.post('/queue/:id/reprocess', (req, res) => {
  const queue = db.readQueue();
  const queueItem = (queue.items || []).find(i => i.id === req.params.id);
  if (!queueItem) return res.status(404).json({ error: '未找到队列项' });
  if (queueItem.status === 'done') return res.status(400).json({ error: '已完成工单不能重新处理' });
  db.updateQueueItem(req.params.id, { status: 'pending', hint: null });
  const label = `${queueItem.accountNote || '账号' + queueItem.accountNum} | ${queueItem.workOrderNum}`;
  const op = opQueue.enqueue('reprocess-one', label, { queueItemId: req.params.id });
  res.status(202).json({ ok: true, opId: op.id });
});

// 手动标记「等待重查」（客服主观决策，下次扫描时重新采集推理）
router.post('/queue/:id/mark-waiting', (req, res) => {
  const queue = db.readQueue();
  const queueItem = (queue.items || []).find(i => i.id === req.params.id);
  if (!queueItem) return res.status(404).json({ error: '未找到队列项' });
  if (queueItem.status === 'done') return res.status(400).json({ error: '已完成工单不能标记等待' });
  db.updateQueueItem(req.params.id, { status: 'waiting' });
  res.json({ ok: true });
});

// 已手动处理归档（escalate 或用户已手动处理的工单）
router.post('/queue/:id/archive-manual', (req, res) => {
  const queue = db.readQueue();
  const queueItem = (queue.items || []).find(i => i.id === req.params.id);
  if (!queueItem) return res.status(404).json({ error: '未找到队列项' });

  const simId = req.body.simId;
  const sim = simId ? db.getSimulation(simId) : null;
  const decision = sim && sim.decision;

  const archiveSource = req.body.source || (queueItem.status === 'auto_executed' ? 'auto_executed' : 'manual_handled');
  const defaultReason = archiveSource === 'auto_executed' ? '自动处理归档' : '手动处理归档';

  db.appendCase({
    id: `case-${Date.now()}`,
    workOrderNum: queueItem.workOrderNum,
    accountNote: queueItem.accountNote,
    type: queueItem.type || (sim && sim.collectedData && sim.collectedData.ticket && sim.collectedData.ticket.type),
    groundTruth: {
      action: (decision && decision.action) || 'escalate',
      reason: (decision && decision.reason) || defaultReason,
      source: archiveSource,
    },
    collectedData: sim && sim.collectedData,
    addedAt: new Date().toISOString(),
  });

  db.updateQueueItem(queueItem.id, { status: 'done' });
  if (sim) db.updateSimulation(sim.id, { archivedAt: new Date().toISOString() });

  sse.broadcast('cases-update', {});
  res.json({ ok: true });
});

// 执行实际工单操作（live 专用）→ 入队串行执行
router.post('/simulations/:id/execute', (req, res) => {
  const sim = db.getSimulation(req.params.id);
  if (!sim) return res.status(404).json({ error: '未找到' });
  if (sim.mode !== 'live') return res.status(400).json({ error: '仅 live 工单支持 execute' });
  if (!sim.decision) return res.status(400).json({ error: '尚未有决策结果' });
  if (sim.executedAt) return res.status(409).json({ error: '已执行' });

  // 防重复入队：同 simId 已在队列（running 或 queued）则直接返回
  const qstate = opQueue.getState();
  const alreadyQueued = (
    (qstate.running && qstate.running.params && qstate.running.params.simId === sim.id) ||
    qstate.queued.some(op => op.params && op.params.simId === sim.id)
  );
  if (alreadyQueued) return res.status(409).json({ error: '已在队列中', alreadyQueued: true });

  const actionLabel = { approve: '同意退款', reject: '拒绝退款', escalate: '上报人工' }[sim.decision.action] || sim.decision.action;
  const { rejectReason, rejectDetail, rejectImageUrl } = req.body;
  const op = opQueue.enqueue('execute', `执行 ${sim.workOrderNum} ${actionLabel}`, {
    simId: sim.id, rejectReason, rejectDetail, rejectImageUrl,
  });
  res.status(202).json({ ok: true, opId: op.id });
});

// ── Feedback ──────────────────────────────────────────────────────

router.get('/feedback', (req, res) => {
  const filter = {};
  if (req.query.verdict) filter.verdict = req.query.verdict;
  if (req.query.limit) filter.limit = parseInt(req.query.limit);
  if (req.query.withReason === '1') filter.withReason = true;
  if (req.query.uninsighted === '1') filter.uninsighted = true;
  res.json(db.readFeedback(filter));
});

router.post('/feedback', (req, res) => {
  const { simulationId, workOrderNum, verdict, reason, suggestedAction, ruleImpact } = req.body;
  if (!simulationId || !verdict) return res.status(400).json({ error: 'simulationId + verdict required' });
  const fb = db.appendFeedback({ simulationId, workOrderNum, verdict, reason, suggestedAction, ruleImpact });
  res.json(fb);
});

router.delete('/feedback/:simId', (req, res) => {
  db.revokeFeedback(req.params.simId);
  res.json({ ok: true });
});

// ── Action Dismiss ────────────────────────────────────────────────

router.post('/action-dismiss', (req, res) => {
  const { entries } = req.body; // [{ tracking, type, workOrderNum }]
  if (!Array.isArray(entries) || !entries.length) return res.status(400).json({ error: 'entries required' });
  db.addDismissed(entries);
  res.json({ ok: true, count: entries.length });
});

router.get('/action-dismissed', (req, res) => {
  res.json(db.readDismissed());
});

router.delete('/action-dismiss/:tracking', (req, res) => {
  db.removeDismissed(decodeURIComponent(req.params.tracking));
  res.json({ ok: true });
});

// ── Cases ─────────────────────────────────────────────────────────

router.get('/cases', (req, res) => {
  const filter = {};
  if (req.query.limit) filter.limit = parseInt(req.query.limit);
  if (req.query.offset) filter.offset = parseInt(req.query.offset);
  res.json(db.readCases(filter));
});

// ── Stats ─────────────────────────────────────────────────────────

router.get('/stats', (req, res) => {
  res.json(db.computeStats());
});

// ── Scan（触发 scan-all.js）────────────────────────────────────────

const SCAN_STATUS_FILE = path.join(BASE, 'data/scan-status.json');

router.get('/pipeline-status', (req, res) => {
  res.json({ running: opQueue.isRunning() });
});

router.get('/scan-status', (req, res) => {
  try {
    const data = fs.existsSync(SCAN_STATUS_FILE)
      ? JSON.parse(fs.readFileSync(SCAN_STATUS_FILE, 'utf8'))
      : { scanning: false, lastScanAt: null, lastResult: null };
    // scanning 状态从队列动态读取（比文件更可靠）
    data.scanning = !!(opQueue.getState().running && opQueue.getState().running.type === 'scan') ||
                    !!(opQueue.getState().queued.some(op => op.type === 'scan'));
    data.nextScanAt = req.app.locals.nextScanAt || null;
    res.json(data);
  } catch(e) {
    res.json({ scanning: false, lastScanAt: null, lastResult: null });
  }
});

router.post('/scan', (req, res) => {
  const nums = (req.body && req.body.accounts) || [];
  const op = opQueue.enqueue('scan', '扫描工单', { accounts: nums });
  res.status(202).json({ ok: true, opId: op.id });
});

// ── Collect（触发单条采集）────────────────────────────────────────

router.post('/collect/:queueItemId', (req, res) => {
  const item = (db.readQueue().items || []).find(i => i.id === req.params.queueItemId);
  if (!item) return res.status(404).json({ error: '未找到队列项' });
  if (item.status !== 'pending') return res.status(400).json({ error: `当前状态 ${item.status}，只有 pending 可采集` });
  const op = opQueue.enqueue('collect', `采集 ${item.workOrderNum}`, {
    queueItemId: item.id, mode: item.mode, accountNum: item.accountNum,
  });
  res.status(202).json({ ok: true, opId: op.id });
});

// ── Op Queue（操作队列状态 + 取消）───────────────────────────────

router.get('/op-queue', (req, res) => {
  res.json(opQueue.getState());
});

router.delete('/op-queue/:id', (req, res) => {
  const ok = opQueue.cancel(req.params.id);
  if (!ok) return res.status(409).json({ error: '操作不存在或已在执行中，无法取消' });
  res.json({ ok: true });
});

// ── Reviews（复盘笔记 CRUD）───────────────────────────────────────

const REVIEWS_PATH = path.join(BASE, 'data/reviews.jsonl');
const fs = require('fs');

// ── Insights（AI洞察）─────────────────────────────────────────────

const INSIGHTS_DIR = path.join(BASE, 'data/insights');
const MAX_INSIGHT_BATCH = 30;  // 单次最多分析30条，防止 token 溢出

// 洞察生成锁（防止并发重复生成）
let insightLock = false;

// 获取最近洞察列表
router.get('/insights', (req, res) => {
  if (!fs.existsSync(INSIGHTS_DIR)) return res.json([]);
  const files = fs.readdirSync(INSIGHTS_DIR)
    .filter(f => f.endsWith('.md'))
    .sort().reverse().slice(0, 10);
  const list = files.map(f => {
    const content = fs.readFileSync(path.join(INSIGHTS_DIR, f), 'utf8');
    const failed = content.includes('⚠️ 洞察生成失败') || content.includes('（无输出）');
    return { file: f, createdAt: f.replace('insight-', '').replace('.md', ''), preview: content.slice(0, 200), failed };
  });
  res.json(list);
});

// 获取单条洞察全文
router.get('/insights/:file', (req, res) => {
  const p = path.join(INSIGHTS_DIR, req.params.file);
  if (!fs.existsSync(p)) return res.status(404).json({ error: '未找到' });
  res.json({ content: fs.readFileSync(p, 'utf8') });
});

// 重置失败洞察
router.post('/insights/reset-failed', (req, res) => {
  const { ids } = req.body || {};
  if (ids && ids.length) {
    db.unmarkFeedbackInsighted(ids);
    return res.json({ ok: true, reset: ids.length });
  }
  const pending = db.readFeedback({ uninsighted: true });
  res.json({ ok: true, pending: pending.length });
});

// 触发洞察生成
router.post('/insights/generate', (req, res) => {
  if (insightLock) return res.status(409).json({ error: '洞察生成进行中，请稍后再试' });

  const all = db.readFeedback({ uninsighted: true });
  if (!all.length) return res.status(400).json({ error: '没有待洞察的反馈' });

  // 分批：差评优先，最多 MAX_INSIGHT_BATCH 条
  const neg = all.filter(f => f.verdict === 'negative');
  const pos = all.filter(f => f.verdict === 'positive');
  const batch = [...neg, ...pos].slice(0, MAX_INSIGHT_BATCH);
  const remaining = all.length - batch.length;

  // 组装 prompt（跳过 sim 为 null 的反馈，不阻塞整批）
  const lines = [];
  const validIds = [];
  for (let i = 0; i < batch.length; i++) {
    const f = batch[i];
    const sim = db.getSimulation(f.simulationId);
    if (!sim || !sim.decision) continue;  // sim 已删除/无决策，跳过
    validIds.push(f.id);
    const cd = sim.collectedData || {};
    const ticket = cd.ticket || {};
    const action = sim.decision.action || '未知';
    const reason = sim.decision.reason || '';
    const confidence = sim.decision.confidence || '';
    const errs = (cd.collectErrors || []).filter(e => !e.includes('跳过（非退货退款类型正常）'));
    const errSummary = errs.length ? `采集异常(${errs.length}): ${errs.map(e => e.split(':')[0]).join(', ')}` : '采集正常';
    const steps = (sim.decision.steps || []).filter(s => s.type === 'branch').map(s => s.text).join(' → ');
    lines.push(`${i+1}. [${f.verdict === 'negative' ? '❌差评' : '✅好评'}] ${f.workOrderNum}
   类型: ${ticket.subOrders ? ticket.subOrders.length : '?'}子订单 | ${ticket.afterSaleReason || '未知'} | ${confidence}
   结论: ${action} — ${reason}
   ${steps ? '路径: ' + steps : ''}
   ${errSummary}
   人工: ${f.reason || '(无)'}`);
  }

  if (!lines.length) return res.status(400).json({ error: '所有待洞察反馈对应的 simulation 已失效' });

  const negCount = Math.min(neg.length, MAX_INSIGHT_BATCH);
  const posCount = batch.length - negCount;
  const batchNote = remaining > 0 ? `（剩余 ${remaining} 条下次分析）` : '';

  const prompt = `你是售后工单AI推理系统的规则优化助手。

## 数据
${batch.length} 条评价${batchNote}（${negCount} 条差评 + ${posCount} 条好评）：

${lines.join('\n\n')}

## 分析要求

1. **差评问题**：哪些推理逻辑错了？根因是什么？（具体场景×判断错误）
2. **好评隐性问题**：✅好评只代表结论正确，不代表过程没问题。找出：
   - 结论正确但有采集异常 → 过程脆但结果侥幸对
   - 置信度 high 但推理路径走了不可靠分支
   - 多个好评有共性采集异常 → 系统盲区
3. **规则建议**：针对发现的问题，具体怎么改规则/改代码？
4. **好评中值得保留的做法**：哪些规则/模式在多个好评工单中持续正确？

输出：
- 直接分析，不要标题行/元数据行/原始数据罗列
- 使用 ## 二级标题组织
- 每个发现标注涉及工单号`;

  insightLock = true;
  res.json({ ok: true, count: batch.length, remaining });

  (async () => {
    try {
      if (!fs.existsSync(INSIGHTS_DIR)) fs.mkdirSync(INSIGHTS_DIR, { recursive: true });
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const outFile = path.join(INSIGHTS_DIR, `insight-${ts}.md`);

      const claudeBin = path.join(path.dirname(process.execPath), 'claude');
      const result = spawnSync(claudeBin, ['-p', prompt], {
        timeout: 120000, encoding: 'utf8', cwd: BASE, env: { ...process.env },
      });
      const content = (result.stdout || '').trim();

      if (!content || result.status !== 0) {
        const errMsg = (result.stderr || '').trim() || `退出码 ${result.status}`;
        fs.writeFileSync(outFile, `# 洞察报告 ${ts}\n\n> ⚠️ 洞察生成失败：${errMsg}\n\n可点击"重新生成"重试。\n`);
        sse.broadcast('insight-error', { file: path.basename(outFile), error: errMsg });
        console.error('[insight] 生成失败:', errMsg);
        return;
      }

      // 先标记 feedback，再写洞察文件（标记成功但文件写入失败 → 安全：feedback
      // 已被标记，下次不会重复分析；可通过 reset-failed 回滚）
      db.markFeedbackInsighted(validIds);
      fs.writeFileSync(outFile, `# 洞察报告 ${ts}\n\n${content}\n`);

      // 清理历史失败记录文件
      try {
        const failedFiles = fs.readdirSync(INSIGHTS_DIR).filter(f => {
          if (!f.endsWith('.md')) return false;
          const c = fs.readFileSync(path.join(INSIGHTS_DIR, f), 'utf8');
          return c.includes('⚠️ 洞察生成失败') || c.includes('（无输出）');
        });
        failedFiles.forEach(f => fs.unlinkSync(path.join(INSIGHTS_DIR, f)));
        if (failedFiles.length) console.log('[insight] 已清除失败记录:', failedFiles.join(', '));
      } catch (e) { console.error('[insight] 清除失败记录出错:', e.message); }

      sse.broadcast('insight-ready', { file: path.basename(outFile) });
    } catch (e) {
      console.error('[insight]', e.message);
      sse.broadcast('insight-error', { error: e.message });
    } finally {
      insightLock = false;
    }
  })();
});


router.get('/reviews', (req, res) => {
  if (!fs.existsSync(REVIEWS_PATH)) return res.json([]);
  const lines = fs.readFileSync(REVIEWS_PATH, 'utf8').split('\n').filter(Boolean);
  res.json(lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean).reverse());
});

router.post('/reviews', (req, res) => {
  const { title, content } = req.body;
  if (!content) return res.status(400).json({ error: 'content required' });
  const review = { id: `rv-${Date.now()}`, title: title || '复盘', content, createdAt: new Date().toISOString() };
  fs.appendFileSync(REVIEWS_PATH, JSON.stringify(review) + '\n');
  res.json(review);
});

router.delete('/reviews/:id', (req, res) => {
  if (!fs.existsSync(REVIEWS_PATH)) return res.status(404).json({ error: '未找到' });
  const lines = fs.readFileSync(REVIEWS_PATH, 'utf8').split('\n').filter(Boolean);
  const filtered = lines.filter(l => { try { return JSON.parse(l).id !== req.params.id; } catch { return true; } });
  fs.writeFileSync(REVIEWS_PATH, filtered.join('\n') + (filtered.length ? '\n' : ''));
  res.json({ ok: true });
});

// ── SSE ───────────────────────────────────────────────────────────

router.get('/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  res.write('event: connected\ndata: {}\n\n');
  sse.addClient(res);
});

// ── 账号管理 ──────────────────────────────────────────────────────

router.get('/accounts', (req, res) => {
  try {
    const accounts = JSON.parse(require('fs').readFileSync(ACCOUNTS_FILE, 'utf8'));
    let statusMap = {};
    try { statusMap = JSON.parse(require('fs').readFileSync(ACCOUNT_STATUS_FILE, 'utf8')); } catch(e) {}
    const list = Object.keys(accounts).sort((a, b) => Number(a) - Number(b)).map(num => {
      const a = accounts[num];
      const hasFile = require('fs').existsSync(path.join(SESSIONS_DIR, a.file));
      const st = statusMap[num] || {};
      return { num: Number(num), name: a.name, note: a.note, hasFile, ...st };
    });
    res.json({ ok: true, accounts: list });
  } catch(e) {
    res.status(500).json({ error: e.message });
  }
});

router.post('/accounts/add', (req, res) => {
  const note = (req.body && req.body.note || '').trim();
  if (!note) return res.status(400).json({ error: 'note is required' });
  try {
    const fs = require('fs');
    const accounts = JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));
    const nums = Object.keys(accounts).map(Number).sort((a, b) => a - b);
    const newNum = nums.length > 0 ? nums[nums.length - 1] + 1 : 1;
    accounts[String(newNum)] = {
      file: `account${newNum}.json`,
      name: `账号${newNum}`,
      note,
    };
    fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify(accounts, null, 2));
    const { spawn } = require('child_process');
    spawn('node', [path.join(SESSIONS_DIR, 'jl.js'), 'add', String(newNum), '--auto-save'], {
      detached: true, stdio: 'ignore',
    }).unref();
    res.json({ ok: true, message: `已创建账号${newNum}「${note}」，请在弹出的浏览器中完成登录` });
  } catch(e) {
    res.status(500).json({ error: e.message });
  }
});

router.post('/accounts/:num/relogin', (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (!num) return res.status(400).json({ error: 'invalid num' });
  const { spawn } = require('child_process');
  spawn('node', [path.join(SESSIONS_DIR, 'jl.js'), 'add', String(num), '--auto-save'], {
    detached: true, stdio: 'ignore',
  }).unref();
  res.json({ ok: true, message: `已为账号${num}启动登录窗口，请在弹出的浏览器中完成登录，登录成功后将自动保存` });
});

router.post('/accounts/:num/open', (req, res) => {
  const num = parseInt(req.params.num, 10);
  if (!num) return res.status(400).json({ error: 'invalid num' });
  const { spawn } = require('child_process');
  spawn('node', [path.join(SESSIONS_DIR, 'jl.js'), String(num)], {
    detached: true, stdio: 'ignore',
  }).unref();
  res.json({ ok: true, message: `已为账号${num}打开鲸灵店铺后台` });
});

module.exports = router;
