'use strict';

// ── SSE ───────────────────────────────────────────────────────────
let es;
function connectSSE() {
  es = new EventSource('/api/events');
  es.addEventListener('connected', () => {
    setConnected(true);
    loadAllLiveTabs();
    loadNextScanTime();
    // 重连后恢复队列面板状态（先同步 lastCompletedOpId，避免弹出历史完成通知）
    api('/op-queue').then(state => {
      if (state.lastCompleted) lastCompletedOpId = state.lastCompleted.id;
      renderQueuePanel(state);
    }).catch(() => {});
  });
  es.onerror = () => setConnected(false);
  es.addEventListener('queue-update', () => { loadLive(); loadSim(); if (currentTab === 'action') loadActionList(); else loadActionBadge(); });
  es.addEventListener('simulation-update', () => { loadLive(); loadSim(); if (currentTab === 'action') loadActionList(); else loadActionBadge(); });
  es.addEventListener('feedback-new', () => { if (currentTab === 'stats') loadStats(); });
  es.addEventListener('cases-update', () => { if (currentTab === 'history') loadHistory(); });
  es.addEventListener('insight-ready', () => { if (currentTab === 'stats') loadStats(); showToast('洞察已生成，已刷新统计页'); });
  es.addEventListener('pipeline-update', (e) => {
    loadLive();
    try {
      const data = JSON.parse(e.data || '{}');
      if (data.workOrderNum && (data.stage === 'collecting' || data.stage === 'inferring')) {
        pipelineProgress = { workOrderNum: data.workOrderNum, stage: data.stage };
      } else if (data.stage === 'auto_executing') {
        pipelineProgress = { workOrderNum: data.workOrderNum, stage: 'auto_executing' };
      } else if (data.stage === 'auto_executed') {
        pipelineProgress = null;
        showToast(`⚡ 自动同意退款：${data.workOrderNum}`);
      } else if (data.stage === 'done' || data.stage === 'start' || data.stage === 'error') {
        pipelineProgress = null;
      }
    } catch(e) {}
    renderQueuePanel(lastQueueState);
  });
  es.addEventListener('scan-progress', (e) => {
    try {
      const data = JSON.parse(e.data || '{}');
      if (data.type === 'init') {
        scanProgress = { accounts: data.accounts };
      } else if (scanProgress && data.type === 'start') {
        const acc = scanProgress.accounts.find(a => a.num === data.num);
        if (acc) acc.status = 'scanning';
      } else if (scanProgress && (data.type === 'done' || data.type === 'error')) {
        const acc = scanProgress.accounts.find(a => a.num === data.num);
        if (acc) {
          acc.status = data.type === 'done' ? 'done' : 'error';
          if (data.count !== undefined) acc.count = data.count;
        }
      }
    } catch(e) {}
    renderQueuePanel(lastQueueState);
  });
  es.addEventListener('op-queue-update', (e) => {
    const state = JSON.parse(e.data || '{}');
    // 清除已不适用的进度状态
    if (!state.running || state.running.type !== 'scan') scanProgress = null;
    if (!state.running || (state.running.type !== 'pipeline' && state.running.type !== 'reinfer')) pipelineProgress = null;
    renderQueuePanel(state);
  });
  es.addEventListener('accounts-update', () => {
    if (currentTab === 'accounts') loadAccounts();
  });
}

// ── 队列面板 ─────────────────────────────────────────────────────
let lastCompletedOpId = null;
let queuedSimIds = new Set(); // 当前在队列中（running+queued）的 simId 集合
let lastQueueState = {};      // 缓存最新 queue state，供进度事件触发重绘
let scanProgress = null;      // {accounts: [{num, note, status, count?}]}
let pipelineProgress = null;  // {workOrderNum, stage}

function renderScanProgress(progress) {
  if (!progress || !progress.accounts || !progress.accounts.length) return '';
  const items = progress.accounts.map(a => {
    const icon = a.status === 'done' ? '✓' : a.status === 'scanning' ? '⟳' : a.status === 'error' ? '✕' : '○';
    const cls = 'oq-acc oq-acc-' + a.status;
    return `<span class="${cls}">${icon} ${h(a.note)}${a.count !== undefined ? ` (${a.count})` : ''}</span>`;
  }).join('');
  return `<div class="oq-scan-accounts">${items}</div>`;
}

function renderQueuePanel(state) {
  lastQueueState = state || {};
  const { running, queued = [], lastCompleted, paused } = state || {};
  setPausedState(!!paused);
  const badge = document.getElementById('op-queue-badge');
  const dropdown = document.getElementById('op-queue-dropdown');
  if (!badge || !dropdown) return;

  // 更新 queuedSimIds（供卡片渲染判断按钮状态）
  queuedSimIds = new Set();
  if (running && running.params && running.params.simId) queuedSimIds.add(running.params.simId);
  queued.forEach(op => { if (op.params && op.params.simId) queuedSimIds.add(op.params.simId); });

  // 刷新已在队列中的卡片按钮文字
  queuedSimIds.forEach(simId => {
    const btn = document.querySelector(`button[onclick="executeSim('${simId}', this)"]`);
    if (btn && !btn.disabled) { btn.disabled = true; btn.textContent = '排队中…'; }
  });
  const queuedCount = queued.length;
  if (running) {
    badge.textContent = `● 处理中${queuedCount > 0 ? ` +${queuedCount}` : ''}`;
    badge.className = 'running';
  } else {
    badge.textContent = '○ 空闲';
    badge.className = '';
  }

  // 完成通知
  if (lastCompleted && lastCompleted.id !== lastCompletedOpId) {
    lastCompletedOpId = lastCompleted.id;
    if (lastCompleted.status === 'done') {
      const r = lastCompleted.result || {};
      if (lastCompleted.type === 'execute' && !r.skipped) {
        const actionCN = DECISION_LABELS[r.action] || '';
        showToast(`✅ 执行完成：${r.workOrderNum || ''} ${actionCN}`);
        loadLive();
      } else if (lastCompleted.type === 'scan') {
        loadLive();
      } else if (lastCompleted.type === 'pipeline' || lastCompleted.type === 'reinfer') {
        loadLive();
      }
    } else if (lastCompleted.status === 'error') {
      const errMsg = (lastCompleted.result && lastCompleted.result.error) || '未知错误';
      showToast(`❌ ${lastCompleted.label}失败：${errMsg.slice(0, 60)}`, 'error');
      loadLive();
    }
  }

  // 渲染下拉内容
  const rows = [];
  if (running) {
    let progressHtml = '';
    if (running.type === 'scan' && scanProgress) {
      progressHtml = renderScanProgress(scanProgress);
    } else if ((running.type === 'pipeline' || running.type === 'reinfer') && pipelineProgress) {
      const stageMap = { collecting: '采集中', inferring: '推理中', auto_executing: '自动执行中' };
      const stageCN = stageMap[pipelineProgress.stage] || pipelineProgress.stage;
      progressHtml = `<div class="oq-pipeline-status"><span class="oq-pipeline-stage">${stageCN}</span><span class="oq-pipeline-num">${h(pipelineProgress.workOrderNum)}</span></div>`;
    }
    rows.push(`<div class="op-queue-item op-queue-running">
      <span class="oq-dot">●</span>
      <div class="oq-running-body">
        <span class="oq-label">${h(running.label)}</span>
        ${progressHtml}
      </div>
      <span class="oq-status">运行中</span>
    </div>`);
  }
  queued.forEach(op => {
    rows.push(`<div class="op-queue-item">
      <span class="oq-dot">○</span>
      <span class="oq-label">${h(op.label)}</span>
      <button class="oq-cancel" onclick="cancelOp('${op.id}')">✕</button>
    </div>`);
  });
  if (!rows.length) {
    rows.push('<div class="oq-empty">队列为空</div>');
  }
  dropdown.innerHTML = rows.join('');
}

function toggleQueuePanel() {
  const dropdown = document.getElementById('op-queue-dropdown');
  if (dropdown) dropdown.classList.toggle('hidden');
}

async function cancelOp(id) {
  try { await fetch('/api/op-queue/' + id, { method: 'DELETE' }); } catch(e) {}
}

// ── 紧急停止 / 恢复 ───────────────────────────────────────────────
async function emergencyStop() {
  try {
    await fetch('/api/emergency-stop', { method: 'POST' });
  } catch(e) {}
}

async function resumeSystem() {
  try {
    await fetch('/api/resume', { method: 'POST' });
  } catch(e) {}
}

function setPausedState(paused) {
  const stopBtn = document.getElementById('emergency-stop-btn');
  const resumeBtn = document.getElementById('resume-btn');
  const banner = document.getElementById('paused-banner');
  if (stopBtn) stopBtn.classList.toggle('hidden', paused);
  if (resumeBtn) resumeBtn.classList.toggle('hidden', !paused);
  if (banner) banner.classList.toggle('hidden', !paused);
}

document.addEventListener('click', (e) => {
  const panel = document.getElementById('op-queue-panel');
  if (panel && !panel.contains(e.target)) {
    const dropdown = document.getElementById('op-queue-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
  }
});

function setConnected(ok) {
  document.getElementById('connection-status').className = 'conn-dot ' + (ok ? 'connected' : 'disconnected');
}

// ── Tab ──────────────────────────────────────────────────────────
let currentTab = 'pending';
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentTab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    const tabEl = document.getElementById('tab-' + currentTab);
    if (tabEl) tabEl.classList.add('active');
    if (['pending', 'auto', 'waiting-tab'].includes(currentTab)) loadAllLiveTabs();
    if (currentTab === 'action') loadActionList();
    if (currentTab === 'history') { historyPage = 1; loadHistory(); }
    if (currentTab === 'stats') loadStats();
    if (currentTab === 'accounts') loadAccounts();
  });
});

// ── API ──────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json();
}

function h(str) {
  return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60) return `${diff}秒前`;
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return `${Math.floor(diff / 86400)}天前`;
}


// ── 重新采集推理 ─────────────────────────────────────────────────
async function reinferSim(simId, btn) {
  const hint = (document.getElementById('fi-' + simId) || {}).value || '';
  if (btn) { btn.disabled = true; btn.textContent = '已加入队列'; }
  try {
    await fetch('/api/simulations/' + simId + '/reinfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hint }),
    });
    showToast(hint ? '已加入队列：根据评价重新推理' : '已加入队列：重新采集推理');
  } catch (e) {
    showToast('操作失败：' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '重新采集推理'; }
  }
}

// ── 批量执行 ─────────────────────────────────────────────────────
async function batchExecute() {
  if (!confirm('确认批量执行所有推理完成的实际工单？')) return;
  try {
    const res = await api('/simulations/batch-execute', { method: 'POST', body: JSON.stringify({}) });
    const count = res.count || 0;
    showToast(count > 0 ? `已将 ${count} 张工单加入执行队列` : '没有待执行的工单');
  } catch (e) {
    showToast('批量执行失败：' + e.message, 'error');
  }
}

// ── 批量重来 ─────────────────────────────────────────────────────
async function batchReprocess() {
  if (!confirm('确认重新采集推理所有未执行的实际工单？')) return;
  try {
    await api('/queue/batch-reprocess', { method: 'POST', body: JSON.stringify({}) });
    showToast('批量重来已加入队列，稍后自动处理');
  } catch (e) {
    showToast('操作失败：' + e.message, 'error');
  }
}

// ── 下次扫描时间 ──────────────────────────────────────────────────
async function loadNextScanTime() {
  try {
    const data = await api('/scan-status');
    const el = document.getElementById('next-scan-label');
    if (!el) return;
    if (data.nextScanAt) {
      const d = new Date(data.nextScanAt);
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      el.textContent = `下次扫描 ${hh}:${mm}`;
    }
  } catch(e) {}
}

// ── 扫描工单 ─────────────────────────────────────────────────────
async function scanTickets() {
  const btn = document.getElementById('scan-btn');
  btn.disabled = true;
  btn.textContent = '已提交';
  try {
    await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    showToast('扫描已加入队列，完成后自动处理');
  } catch (e) {
    showToast('提交失败：' + e.message, 'error');
  }
  setTimeout(() => { btn.textContent = '扫描工单'; btn.disabled = false; }, 2000);
}

function showToast(msg, type = 'info') {
  const el = document.createElement('div');
  el.style.cssText = `position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
    background:${type==='error'?'#dc2626':'#1f2937'};color:#fff;
    padding:10px 18px;border-radius:8px;font-size:13px;
    box-shadow:0 4px 12px rgba(0,0,0,.2);z-index:999;`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ── 常量 ─────────────────────────────────────────────────────────
const DECISION_LABELS = { approve: '同意退款', reject: '拒绝退款', escalate: '上报人工', pending: '待推理', skip: '已退款归档' };
const DECISION_ICONS  = { approve: '✅', reject: '❌', escalate: '⚠️', pending: '○', skip: '🔄' };
const STATUS_CN = {
  pending: '待采集', collecting: '采集中', collected: '已采集',
  inferring: '推理中', simulated: '已推理', confirmed: '已确认', executed: '已执行', done: '已完成',
  waiting: '等待重查', auto_executing: '自动执行中', auto_executed: '已自动执行',
};

// 解析紧急度为分钟数（用于排序，无法解析则 Infinity）
function parseUrgencyMinutes(urgency) {
  if (!urgency) return Infinity;
  let total = 0;
  const dm = urgency.match(/(\d+)天/); if (dm) total += parseInt(dm[1]) * 1440;
  const hm = urgency.match(/(\d+)小时/); if (hm) total += parseInt(hm[1]) * 60;
  const mm = urgency.match(/(\d+)分/); if (mm) total += parseInt(mm[1]);
  return total || Infinity;
}

// 实时倒计时格式化（从 deadlineAt ISO 时间戳计算）
function formatCountdown(deadlineAt) {
  if (!deadlineAt) return null;
  const diff = new Date(deadlineAt).getTime() - Date.now();
  if (diff <= 0) return { text: '已过期', className: 'urgency-expired' };
  const hours = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  const days = Math.floor(hours / 24);
  const remHours = hours % 24;

  let text;
  if (days > 0) text = days + '天' + remHours + '小时';
  else if (hours > 0) text = hours + '小时' + mins + '分';
  else text = mins + '分钟';

  let className = 'urgency-safe';
  if (hours < 6) className = 'urgency-critical';
  else if (hours < 12) className = 'urgency-warning';
  else if (hours < 24) className = 'urgency-caution';

  return { text: text, className: className };
}

// ── 实际工单 ─────────────────────────────────────────────────────
// ── 实际工单（三标签页共享数据源）────────────────────────────────
async function loadAllLiveTabs() {
  const [queue, sims] = await Promise.all([
    api('/queue?mode=live'),
    api('/simulations?mode=live'),
  ]);

  const items = (queue.items || []).filter(i => i.status !== 'done');

  items.sort((a, b) => {
    const aMs = a.deadlineAt ? new Date(a.deadlineAt).getTime() : Date.now() + parseUrgencyMinutes(a.urgency) * 60000;
    const bMs = b.deadlineAt ? new Date(b.deadlineAt).getTime() : Date.now() + parseUrgencyMinutes(b.urgency) * 60000;
    return aMs - bMs;
  });

  const simsByQueueItem = {};
  (sims || []).forEach(s => {
    if (!simsByQueueItem[s.queueItemId]) simsByQueueItem[s.queueItemId] = [];
    simsByQueueItem[s.queueItemId].push(s);
  });
  Object.values(simsByQueueItem).forEach(arr =>
    arr.sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))
  );

  function renderItem(item, idx) {
    const allSims = simsByQueueItem[item.id] || [];
    const latestSim = allSims[allSims.length - 1] || null;
    const prevSims = allSims.slice(0, -1);
    return renderCard(item, latestSim, 'live', prevSims, idx + 1);
  }

  const AUTO_STATUSES = ['auto_executed', 'auto_executing'];

  // Tab 1: 待确认
  const pendingItems = items.filter(i => i.status !== 'waiting' && !AUTO_STATUSES.includes(i.status));
  const simCount = pendingItems.filter(i => i.status === 'simulated').length;
  const pendingTabBadge = document.getElementById('pending-tab-count');
  if (pendingTabBadge) pendingTabBadge.textContent = simCount || '';
  const pendingCountEl = document.getElementById('pending-count');
  if (pendingCountEl) pendingCountEl.textContent = pendingItems.length;
  const pendingEl = document.getElementById('pending-list');
  if (pendingEl) pendingEl.innerHTML = pendingItems.length
    ? pendingItems.map(renderItem).join('')
    : '<div class="empty-state">暂无待确认工单。点击「扫描工单」检测新工单。</div>';

  // Tab 2: 已自动执行
  const autoItems = items.filter(i => AUTO_STATUSES.includes(i.status));
  const autoTabBadge = document.getElementById('auto-tab-count');
  if (autoTabBadge) autoTabBadge.textContent = autoItems.length || '';
  const autoCountEl = document.getElementById('auto-count');
  if (autoCountEl) autoCountEl.textContent = autoItems.length;
  const autoEl = document.getElementById('auto-list');
  if (autoEl) autoEl.innerHTML = autoItems.length
    ? autoItems.map(renderItem).join('')
    : '<div class="empty-state">暂无自动执行工单。</div>';

  // Tab 3: 等待重查
  const waitingItems = items.filter(i => i.status === 'waiting');
  const waitingTabBadge = document.getElementById('waiting-tab-count');
  if (waitingTabBadge) waitingTabBadge.textContent = waitingItems.length || '';
  const waitingCountEl = document.getElementById('waiting-count');
  if (waitingCountEl) waitingCountEl.textContent = waitingItems.length;
  const waitingEl = document.getElementById('waiting-list');
  if (waitingEl) waitingEl.innerHTML = waitingItems.length
    ? waitingItems.map(renderItem).join('')
    : '<div class="empty-state">暂无等待重查工单。</div>';
}

// 兼容旧调用（SSE handlers 里仍然叫 loadLive）
function loadLive() { return loadAllLiveTabs(); }

// ── 模拟训练 ─────────────────────────────────────────────────────
async function loadSim() {
  const [queue, sims] = await Promise.all([
    api('/queue?mode=sim'),
    api('/simulations?mode=sim'),
  ]);
  const items = queue.items || [];
  document.getElementById('sim-count').textContent = items.length;

  const simMap = {};
  (sims || []).forEach(s => { simMap[s.queueItemId] = s; });

  const el = document.getElementById('sim-list');
  if (!items.length) {
    el.innerHTML = '<div class="empty-state">暂无训练案例。点击「添加案例」投入新工单，或运行 <code>node simulate.js add</code>。</div>';
    return;
  }
  el.innerHTML = items.map(item => renderCard(item, simMap[item.id], 'sim')).join('');
}

function toggleAddForm() {
  document.getElementById('add-form').classList.toggle('hidden');
}

async function submitAdd() {
  const workOrderNum = document.getElementById('f-workOrderNum').value.trim();
  const accountNum = parseInt(document.getElementById('f-accountNum').value) || null;
  const accountNote = document.getElementById('f-accountNote').value.trim();
  const gtVal = document.getElementById('f-groundTruth').value;
  if (!workOrderNum) { showToast('工单号不能为空', 'error'); return; }
  const res = await api('/queue', {
    method: 'POST',
    body: JSON.stringify({
      workOrderNum, accountNum, accountNote: accountNote || `账号${accountNum}`,
      mode: 'sim', source: 'web',
      groundTruth: gtVal ? { action: gtVal, reason: '', source: 'manual' } : null,
    }),
  });
  if (res.error) { showToast('添加失败：' + res.error, 'error'); return; }
  toggleAddForm();
  loadSim();
  showToast('已添加到训练队列');
}

// ── 历史记录（cases.jsonl）────────────────────────────────────────
const HISTORY_PAGE_SIZE = 30;
let historyPage = 1;

async function loadHistory(page) {
  if (page !== undefined) historyPage = page;
  const offset = (historyPage - 1) * HISTORY_PAGE_SIZE;

  const [result, feedbacks] = await Promise.all([
    api(`/cases?limit=${HISTORY_PAGE_SIZE}&offset=${offset}`),
    api('/feedback?limit=500'),
  ]);

  const cases = result.items || [];
  const total = result.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));

  document.getElementById('history-count').textContent = total;

  // 按工单号建立反馈索引（每个工单只取最新一条）
  const fbByNum = {};
  (feedbacks || []).forEach(f => {
    const existing = fbByNum[f.workOrderNum];
    if (!existing || f.createdAt > existing.createdAt) {
      fbByNum[f.workOrderNum] = f;
    }
  });

  const el = document.getElementById('history-list');
  if (!total) {
    el.innerHTML = '<div class="empty-state">暂无历史记录。执行实际工单后自动归档，或运行 <code>node simulate.js import</code> 导入案例。</div>';
    return;
  }

  const cardsHtml = cases.map(c => renderHistoryCard(c, fbByNum[c.workOrderNum] || null)).join('');
  el.innerHTML = renderPagination(historyPage, totalPages, total) + cardsHtml + renderPagination(historyPage, totalPages, total);
}

function renderPagination(page, totalPages, total) {
  const start = (page - 1) * HISTORY_PAGE_SIZE + 1;
  const end = Math.min(page * HISTORY_PAGE_SIZE, total);
  const canPrev = page > 1;
  const canNext = page < totalPages;

  const pageNums = [];
  for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) {
    pageNums.push(i);
  }

  return `
<div class="pagination">
  <span class="pagination-info">第 ${start}–${end} 条，共 ${total} 条</span>
  <div class="pagination-btns">
    <button class="pg-btn" onclick="loadHistory(1)" ${!canPrev ? 'disabled' : ''}>«</button>
    <button class="pg-btn" onclick="loadHistory(${page - 1})" ${!canPrev ? 'disabled' : ''}>‹</button>
    ${pageNums.map(n => `<button class="pg-btn${n === page ? ' pg-active' : ''}" onclick="loadHistory(${n})">${n}</button>`).join('')}
    <button class="pg-btn" onclick="loadHistory(${page + 1})" ${!canNext ? 'disabled' : ''}>›</button>
    <button class="pg-btn" onclick="loadHistory(${totalPages})" ${!canNext ? 'disabled' : ''}>»</button>
  </div>
</div>`;
}

function renderHistoryCard(c, latestFb) {
  const gt = c.groundTruth;
  const gtAction = gt && gt.action;
  const gtSource = gt && gt.source;

  const gtBadge = gtAction ? `<span class="decision-tag ${gtAction}">${DECISION_ICONS[gtAction]} ${DECISION_LABELS[gtAction]}</span>` : '';
  const sourceBadge = `<span class="tag tag-type">${gtSource === 'auto_executed' ? '自动处理' : gtSource === 'executed' ? '已执行' : gtSource === 'manual_handled' ? '手动归档' : gtSource === 'manual' ? '手动录入' : '导入'}</span>`;

  // 反馈（只取最新一条）
  const fbHtml = latestFb ? `
<div class="hist-fb ${latestFb.verdict}">
  <span>${latestFb.verdict === 'positive' ? '✅ 好评' : '❌ 差评'}</span>
  ${latestFb.reason ? `<span style="margin-left:6px">${h(latestFb.reason)}</span>` : ''}
</div>` : '';

  // 买家申请信息（同 renderBody）
  const ticket = (c.collectedData && c.collectedData.ticket) || {};
  const applyItems = [
    ['售后原因', ticket.afterSaleReason],
    ['申请金额', ticket.amount ? `¥${ticket.amount}` : null],
    ['买家说明', ticket.buyerRemark && ticket.buyerRemark !== '无' ? ticket.buyerRemark : null],
  ].filter(([, v]) => v);

  const applyHtml = applyItems.length ? `
<div class="ticket-summary" style="margin:6px 0">
  ${applyItems.map(([l, v]) => `<div class="summary-item"><span class="summary-label">${l}</span><span class="summary-value apply-value">${h(String(v))}</span></div>`).join('')}
</div>` : '';

  // 推理理由
  const reasonHtml = gt && gt.reason && gt.reason !== '待确认'
    ? `<p style="font-size:13px;color:var(--gray-600);margin:4px 0">${h(gt.reason)}</p>` : '';

  return `
<div class="ticket-card">
  <div class="ticket-header">
    <div class="ticket-main-info">
      <div class="ticket-num">${c.workOrderNum}</div>
      <div class="ticket-account">${h(c.accountNote || '—')}</div>
    </div>
    <div class="ticket-meta">
      ${c.type ? `<span class="tag tag-type">${c.type}</span>` : ''}
      ${sourceBadge}
      ${gtBadge}
    </div>
  </div>
  <div class="ticket-body">
    ${applyHtml}
    ${reasonHtml}
    ${fbHtml}
  </div>
</div>`;
}

// ── 卡片渲染（实际工单 + 模拟训练）──────────────────────────────
function renderCard(item, sim, mode, prevSims = [], seqNum = null) {
  const action = sim && sim.decision && sim.decision.action || 'pending';
  const fbStatus = sim && sim.feedbackStatus || 'pending';
  const statusClass = 'tag-status-' + item.status;

  const fbTagHtml = mode === 'sim' ? `<span class="fb-tag ${fbStatus}">${{positive:'✅ 正确', negative:'❌ 错误', pending:'待判定'}[fbStatus]}</span>` : '';

  return `
<div class="ticket-card" id="card-${item.id}">
  <div class="ticket-header">
    <div class="ticket-main-info">
      <div class="ticket-num">${seqNum != null ? `<span class="seq-num">#${seqNum}</span> ` : ''}<span class="work-order-id">${item.workOrderNum}</span></div>
      <div class="ticket-account">${h(item.accountNote || '—')}</div>
    </div>
    <div class="ticket-meta">
      ${item.type ? `<span class="tag tag-type">${item.type}</span>` : ''}
      <span class="tag tag-${item.mode}">${item.mode === 'live' ? '实际' : '训练'}</span>
      ${(function(){ if (['auto_executed','auto_executing'].includes(item.status)) return ''; var cd = item.deadlineAt ? formatCountdown(item.deadlineAt) : null; if (cd) return '<span class="tag tag-urgency ' + cd.className + '" data-deadline="' + item.deadlineAt + '">\u23f0 ' + cd.text + '</span>'; return item.urgency ? '<span class="tag tag-urgency">\u23f0 ' + item.urgency + '</span>' : ''; })()}
      <span class="tag ${statusClass}">${STATUS_CN[item.status] || item.status}</span>
      <span class="decision-tag ${action}">${DECISION_ICONS[action]} ${DECISION_LABELS[action] || action}</span>
      ${fbTagHtml}
    </div>
  </div>
  <div class="ticket-body">
    ${renderBody(item, sim, mode)}
    ${prevSims.length ? renderPrevSims(prevSims) : ''}
    <div class="ticket-actions">
      ${renderActions(item, sim, mode)}
    </div>
  </div>
</div>`;
}

function renderAutoExecCriteria(sim, item) {
  if (!sim || !sim.autoExecutedAt) return '';
  const ticket = (sim.collectedData && sim.collectedData.ticket) || {};
  const ts = new Date(sim.autoExecutedAt);
  const timeStr = `${(ts.getMonth()+1).toString().padStart(2,'0')}-${ts.getDate().toString().padStart(2,'0')} ${ts.getHours().toString().padStart(2,'0')}:${ts.getMinutes().toString().padStart(2,'0')}`;
  const autoErr = sim.autoExecuteError ? `<div class="auto-exec-err">⚠️ 降级原因：${h(sim.autoExecuteError)}</div>` : '';
  return `
<div class="auto-exec-criteria">
  <div class="auto-exec-criteria-title">⚡ 自动执行依据 <span class="auto-exec-time">${timeStr}</span></div>
  <div class="auto-exec-row">✅ 售后原因：${h(ticket.afterSaleReason || '七天无理由退货')}（非商责）</div>
  <div class="auto-exec-row">✅ ${h(sim.decision && sim.decision.reason || '')}</div>
  <div class="auto-exec-row">✅ 无次品 · 无快递冲突 · 无推理警告</div>
  ${autoErr}
</div>`;
}

function renderBody(item, sim, mode) {
  // 采集中/推理中：优先显示进行中状态，不渲染旧数据（刷新页面后状态仍正确）
  if (['collecting', 'inferring'].includes(item.status)) {
    return `<p style="font-size:13px;padding:4px 0;color:var(--gray-400)">${STATUS_CN[item.status]}…</p>`;
  }
  if (!sim || !sim.collectedData) {
    const liveMsg = item.status === 'pending'
      ? `<span style="color:var(--gray-400)">待采集…</span>`
      : `运行：<code>node collect.js --sim</code>`;
    return `<p style="font-size:13px;padding:4px 0">${liveMsg}</p>`;
  }

  const cd = sim.collectedData;
  const ticket = cd.ticket || {};
  const errors = (cd.collectErrors || []).filter(e => !e.includes('正常')).length;
  const subOrder = ticket.subOrders && ticket.subOrders[0];

  // ── 售后申请信息块 ────────────────────────────────────────────
  const applyItems = [
    ['售后原因', ticket.afterSaleReason],
    ['申请金额', ticket.amount ? `¥${ticket.amount}` : null],
    ['支付金额', ticket.payAmount ? `¥${ticket.payAmount}` : null],
    ['标签', ticket.tags && ticket.tags.length ? ticket.tags.join('、') : null],
    ['售后说明', ticket.buyerRemark && ticket.buyerRemark !== '无' ? ticket.buyerRemark : null],
    ['凭证图片', ticket.imageCount ? `${ticket.imageCount} 张（需人工查看）` : null],
  ].filter(([, v]) => v);

  const applyHtml = applyItems.length ? `
<div class="apply-info-section">
  <div class="apply-info-title">买家申请信息</div>
  <div class="ticket-summary">
    ${applyItems.map(([l, v]) => `<div class="summary-item"><span class="summary-label">${l}</span><span class="summary-value apply-value">${h(String(v))}</span></div>`).join('')}
  </div>
</div>` : '';

  // ── 工单数据摘要块 ─────────────────────────────────────────────
  const summaryItems = [
    ['子订单号', subOrder && subOrder.id],
    ['货号', subOrder && subOrder.sku],
    ['SKU属性', subOrder && subOrder.attr1],
    ['物流状态', subOrder && subOrder.logistics],
    ['退货快递', ticket.returnTracking],
    ['发货快递', cd.erpSearch && cd.erpSearch.rows && cd.erpSearch.rows.rows && cd.erpSearch.rows.rows[0] && cd.erpSearch.rows.rows[0].tracking],
    ['历史售后', ticket.afterSaleCount ? `${ticket.afterSaleCount} 次` : null],
    ['ERP状态', cd.erpSearch && cd.erpSearch.status],
    ['物流包裹', cd.logistics && cd.logistics.packages && `${cd.logistics.packages.length} 个`],
  ].filter(([, v]) => v);

  const summaryHtml = summaryItems.length ? `
<div class="ticket-summary">
  ${summaryItems.map(([l, v]) => `<div class="summary-item"><span class="summary-label">${l}</span><span class="summary-value">${h(String(v))}</span></div>`).join('')}
</div>` : '';

  const decisionHtml = sim.decision ? `
<div class="decision-box ${sim.decision.action}">
  <div class="decision-box-title">${DECISION_ICONS[sim.decision.action]} ${DECISION_LABELS[sim.decision.action]}
    ${sim.decision.confidence ? `<span class="confidence-indicator ${sim.decision.confidence}" style="margin-left:6px"></span>` : ''}
    ${sim.decision.aiPowered ? `<span class="ai-badge">🤖 AI</span>` : ''}
  </div>
  <div class="decision-box-reason">${h(sim.decision.reason || '')}</div>
  ${sim.decision.rulesApplied && sim.decision.rulesApplied.length ? `
  <div class="rules-list">
    ${sim.decision.rulesApplied.map(r => `<span class="rule-item">📖 ${h(r.doc)} §${h(r.section||'')}：${h(r.summary||'')}</span>`).join('')}
  </div>` : ''}
  ${sim.decision.warnings && sim.decision.warnings.length ? `<div class="warnings">⚠️ ${h(sim.decision.warnings.join('；'))}</div>` : ''}
</div>` : '';

  const errHtml = errors ? `<div class="collect-errors">⚠️ ${errors} 项采集异常</div>` : '';
  const judgmentHtml = mode === 'sim' ? renderJudgment(item, sim) : '';
  const stepsHtml = sim.decision && sim.decision.steps
    ? renderSteps(sim.decision.steps, !!sim.decision.aiPowered)
    : '';

  const autoExecHtml = (item.status === 'auto_executed' || item.status === 'auto_executing') ? renderAutoExecCriteria(sim, item) : '';
  return [autoExecHtml, decisionHtml, applyHtml, summaryHtml, errHtml, stepsHtml, judgmentHtml].filter(Boolean).join('');
}

function renderActions(item, sim, mode) {
  if (mode === 'sim') {
    const btns = [];
    if (item.status === 'pending') btns.push(`<button class="btn-ghost" onclick="collectItem('${item.id}')">采集数据</button>`);
    btns.push(`<button class="btn-ghost" style="margin-left:auto" onclick="deleteItem('${item.id}')">删除</button>`);
    return btns.join('');
  }

  // ── auto_executed：布局与「待确认」一致，操作按钮灰化禁用，好评/差评保留可用 ──
  if (item.status === 'auto_executed' || item.status === 'auto_executing') {
    if (sim && sim.decision) {
      const fbStatus = sim.feedbackStatus || 'pending';
      const fbDone = fbStatus !== 'pending';
      const posActive = fbStatus === 'positive';
      const negActive = fbStatus === 'negative';
      return `
<div class="live-actions">
  <div class="feedback-row">
    <button id="fb-pos-${sim.id}"
      class="btn-positive${posActive ? ' btn-fb-active' : ''}"
      onclick="${posActive ? `revokeFeedback('${sim.id}')` : `selectVerdict('${sim.id}','positive')`}"
      ${negActive ? `style="opacity:0.5"` : ''}>${posActive ? '已好评 ✅' : '好评'}</button>
    <button id="fb-neg-${sim.id}"
      class="btn-negative${negActive ? ' btn-fb-active' : ''}"
      onclick="${negActive ? `revokeFeedback('${sim.id}')` : `selectVerdict('${sim.id}','negative')`}"
      ${posActive ? `style="opacity:0.5"` : ''}>${negActive ? '已差评 ❌' : '差评'}</button>
    <button class="btn-ghost" disabled style="opacity:0.4;cursor:not-allowed">重新采集推理</button>
    <button class="btn-ghost" disabled style="opacity:0.4;cursor:not-allowed">标记等待中</button>
    <button class="btn-primary" disabled style="opacity:0.5;cursor:not-allowed">⚡ 已自动同意退款</button>
    <button class="btn-ghost" onclick="archiveManual('${item.id}','${sim.id}')">手动归档</button>
    <button class="btn-ghost" onclick="openTicket('${item.workOrderNum}',${item.accountNum || 'null'},this)">🔍 查看工单</button>
    <button class="btn-ghost" style="margin-left:auto" onclick="deleteItem('${item.id}')">删除</button>
  </div>
  ${!fbDone ? `<div style="margin-top:4px;display:flex;gap:6px;align-items:center">
    <textarea class="feedback-input" id="fi-${sim.id}" rows="2" placeholder="差评时请说明原因（供后续规则优化）"></textarea>
    <button class="btn-ghost" id="fb-submit-${sim.id}" onclick="submitPendingFeedback('${sim.id}','${item.workOrderNum}','${item.id}')" disabled>提交评价</button>
  </div>` : ''}
</div>`;
    }
    return `<div class="live-actions"><button class="btn-ghost" onclick="openTicket('${item.workOrderNum}',${item.accountNum || 'null'},this)">🔍 查看工单</button></div>`;
  }

  // ── live 模式：新操作区 ───────────────────────────────────────
  if (sim && sim.decision) {
    const fbStatus = sim.feedbackStatus || 'pending';
    const fbDone = fbStatus !== 'pending';   // 已评价过
    const posActive = fbStatus === 'positive';
    const negActive = fbStatus === 'negative';
    const executed = !!sim.executedAt;
    const inQueue = !executed && queuedSimIds.has(sim.id);
    const execErr = !executed && sim.executeError;

    const canReinfer = !executed;
    return `
<div class="live-actions">
  ${execErr ? `<div class="execute-error-bar">⚠️ 执行失败：${execErr}　<button class="btn-ghost btn-sm" onclick="archiveManual('${item.id}','${sim.id}')">手动归档</button></div>` : ''}
  <div class="feedback-row">
    <button id="fb-pos-${sim.id}"
      class="btn-positive${posActive ? ' btn-fb-active' : ''}"
      onclick="${posActive ? `revokeFeedback('${sim.id}')` : `selectVerdict('${sim.id}','positive')`}"
      ${negActive ? `style="opacity:0.5"` : ''}>${posActive ? '已好评 ✅' : '好评'}</button>
    <button id="fb-neg-${sim.id}"
      class="btn-negative${negActive ? ' btn-fb-active' : ''}"
      onclick="${negActive ? `revokeFeedback('${sim.id}')` : `selectVerdict('${sim.id}','negative')`}"
      ${posActive ? `style="opacity:0.5"` : ''}>${negActive ? '已差评 ❌' : '差评'}</button>
    ${canReinfer ? `<button class="btn-ghost" onclick="reinferSim('${sim.id}',this)">重新采集推理</button>` : ''}
    ${!executed && item.status !== 'waiting' ? `<button class="btn-ghost" onclick="markWaiting('${item.id}',this)" title="下次扫描时自动重新采集">标记等待中</button>` : ''}
    ${item.status === 'waiting' ? `<span style="font-size:12px;color:var(--gray-400);padding:0 6px">⏳ 等待下次扫描重查</span>` : ''}
    ${!executed ? `<button class="btn-primary" onclick="executeSim('${sim.id}', this)" ${inQueue ? 'disabled' : ''}>${inQueue ? '排队中…' : '▶ 执行操作'}</button>` : ''}
    ${!executed ? `<button class="btn-ghost" onclick="archiveManual('${item.id}','${sim.id}')">手动归档</button>` : ''}
    <button class="btn-ghost" onclick="openTicket('${item.workOrderNum}',${item.accountNum || 'null'},this)">🔍 查看工单</button>
    <button class="btn-ghost" style="margin-left:auto" onclick="deleteItem('${item.id}')">删除</button>
  </div>
  <textarea class="feedback-input" id="fi-${sim.id}" rows="3"
    placeholder="${executed ? '备注（仅记录）' : '评价内容或优化指令，点击「重新采集推理」后生效'}"
    ${fbDone && executed ? 'disabled' : ''}></textarea>
  ${!fbDone ? `<div style="margin-top:4px;text-align:right">
    <button class="btn-ghost" id="fb-submit-${sim.id}" onclick="submitPendingFeedback('${sim.id}','${item.workOrderNum}')" disabled>提交评价</button>
  </div>` : ''}
</div>`;
  }

  // 排队中/采集中/推理中：只显示查看+删除
  return `<div class="live-actions"><button class="btn-ghost" onclick="openTicket('${item.workOrderNum}',${item.accountNum || 'null'},this)">🔍 查看工单</button><button class="btn-ghost" style="margin-left:auto" onclick="deleteItem('${item.id}')">删除</button></div>`;
}

// ── 查看工单（注入账号 + 打开详情页）────────────────────────────
async function openTicket(workOrderNum, accountNum, btn) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = '已加入队列';
  try {
    await fetch('/api/open-ticket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workOrderNum, accountNum }),
    });
    showToast('已加入队列：打开工单详情');
  } catch (e) {
    showToast('提交失败: ' + e.message, 'error');
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = orig; }, 2000);
}

// ── 已手动处理归档 ───────────────────────────────────────────────
async function markWaiting(queueItemId, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = '标记中…';
  const res = await api('/queue/' + queueItemId + '/mark-waiting', { method: 'POST' });
  if (res.error) { showToast('标记失败：' + res.error, 'error'); btn.disabled = false; btn.textContent = orig; return; }
  showToast('已标记为等待重查，下次扫描时自动重新采集');
  loadLive();
}

async function archiveManual(queueItemId, simId) {
  if (!confirm('确认将该工单标记为「已手动处理」并归档到历史记录？\n归档后将从实际工单列表移除。')) return;
  try {
    const res = await api('/queue/' + queueItemId + '/archive-manual', {
      method: 'POST',
      body: JSON.stringify({ simId }),
    });
    if (res.error) { showToast('归档失败：' + res.error, 'error'); return; }
    showToast('已归档到历史记录');
    loadLive();
  } catch (e) {
    showToast('归档失败：' + e.message, 'error');
  }
}

// ── 推理过程展示 ─────────────────────────────────────────────────
function renderSteps(steps, isAI) {
  if (!steps || !steps.length) return '';
  const ICONS = { read: '📖', check: '🔍', branch: '➤' };
  const stepHtml = steps.map(step => {
    if (step.type === 'read') {
      return `<div class="trace-step trace-read"><span class="trace-icon">${ICONS.read}</span><span class="trace-label">${h(step.label)}</span><span class="trace-value">${step.label === '传入数据摘要' ? `<details><summary>展开查看</summary><pre class="trace-json">${h(step.value)}</pre></details>` : h(String(step.value))}</span></div>`;
    }
    if (step.type === 'check') {
      const ok = step.result === true;
      const no = step.result === false;
      return `<div class="trace-step trace-check ${ok ? 'trace-true' : no ? 'trace-false' : ''}"><span class="trace-icon">${ICONS.check}</span><span class="trace-condition">${h(step.condition)}</span><span class="trace-result">${h(String(step.result))}</span></div>`;
    }
    if (step.type === 'branch') {
      return `<div class="trace-step trace-branch"><span class="trace-icon">${ICONS.branch}</span><span class="trace-text">${h(step.text)}</span></div>`;
    }
    return '';
  }).join('');

  return `
<div class="inference-trace">
  <div class="inference-trace-toggle" onclick="this.parentElement.classList.toggle('open')">
    ${isAI ? '🤖 AI' : '📋 规则'}推理过程 (${steps.length} 步)
    <span class="prev-sim-arrow">▶</span>
  </div>
  <div class="inference-trace-list">${stepHtml}</div>
</div>`;
}

// ── 历史推理记录（实际工单重采集后展示前几次结果）─────────────────
function renderPrevSims(prevSims) {
  const ICONS = { approve: '✅', reject: '❌', escalate: '⚠️' };
  const items = [...prevSims].reverse(); // 最近的在前
  return `
<div class="prev-sim-history">
  <div class="prev-sim-toggle" onclick="this.parentElement.classList.toggle('open')">
    历史推理记录 (${items.length} 次)
    <span class="prev-sim-arrow">▶</span>
  </div>
  <div class="prev-sim-list">
    ${items.map(s => {
      const d = s.decision;
      if (!d) return '';
      const fb = s.feedbackStatus;
      const fbTag = fb === 'positive' ? '<span style="color:var(--green)">好评</span>'
                  : fb === 'negative' ? '<span style="color:var(--red)">差评</span>'
                  : '';
      const hint = s.hint || '';
      return `<div class="prev-sim-item">
        <span class="prev-sim-action ${d.action}">${ICONS[d.action]} ${DECISION_LABELS[d.action]}</span>
        ${d.aiPowered ? '<span class="ai-badge" style="font-size:10px">🤖</span>' : ''}
        <span class="prev-sim-reason">${h(d.reason || '')}</span>
        ${hint ? `<span class="prev-sim-hint">「${h(hint.slice(0, 40))}${hint.length > 40 ? '…' : ''}」</span>` : ''}
        ${fbTag}
      </div>`;
    }).join('')}
  </div>
</div>`;
}

// ── 内嵌判定（模拟训练专用）──────────────────────────────────────
function renderJudgment(item, sim) {
  if (!sim || !sim.decision) return '';
  const fbStatus = sim.feedbackStatus || 'pending';
  if (fbStatus !== 'pending') {
    return `<div class="judgment-done ${fbStatus}">
      <span class="jud-verdict">${fbStatus === 'positive' ? '✅ 已标记为正确' : '❌ 已标记为错误'}</span>
    </div>`;
  }
  const sid = sim.id.replace(/[^a-z0-9]/gi, '_');
  return `
<div class="judgment-inline">
  <div class="jud-fields">
    <textarea id="rem_${sid}" placeholder="备注（可选）：判定理由、改进建议…" rows="2"></textarea>
    <select id="act_${sid}">
      <option value="">正确答案（如有误）</option>
      <option value="approve">应同意退款</option>
      <option value="reject">应拒绝退款</option>
      <option value="escalate">应上报人工</option>
    </select>
    <input id="doc_${sid}" placeholder="规则文档（如 flow-5.1.md）" />
  </div>
  <div class="jud-btns">
    <button class="btn-green" onclick="judgeInline('${sim.id}','${h(item.workOrderNum)}','positive','${sid}')">✅ 判定正确</button>
    <button class="btn-red"   onclick="judgeInline('${sim.id}','${h(item.workOrderNum)}','negative','${sid}')">❌ 判定错误</button>
  </div>
</div>`;
}

async function judgeInline(simId, workOrderNum, verdict, sid) {
  const reason = (document.getElementById('rem_' + sid) || {}).value || '';
  const suggestedAction = (document.getElementById('act_' + sid) || {}).value || null;
  const doc = ((document.getElementById('doc_' + sid) || {}).value || '').trim() || null;
  if (verdict === 'negative' && !reason) { showToast('请填写备注说明错误原因', 'error'); return; }
  await submitFeedback(simId, workOrderNum, verdict, reason || null, suggestedAction, doc ? { doc } : null);
}

// ── 采集单条 ─────────────────────────────────────────────────────
async function collectItem(queueItemId) {
  const btn = event.target;
  btn.disabled = true; btn.textContent = '已加入队列';
  try {
    await api('/collect/' + queueItemId, { method: 'POST' });
    showToast('已加入采集队列');
  } catch (e) {
    showToast('异常：' + e.message, 'error');
    btn.disabled = false; btn.textContent = '采集数据';
  }
}

// ── 实际工单操作 ──────────────────────────────────────────────────
async function confirmSim(simId) {
  const res = await api('/simulations/' + simId + '/confirm', { method: 'POST' });
  if (res.error) { showToast('确认失败：' + res.error, 'error'); return; }
  showToast('已确认方案'); loadLive();
}

function showExecResult(btn, success, msg) {
  const container = btn && btn.closest('.live-actions');
  if (!container) { showToast(msg, success ? 'info' : 'error'); return; }
  // 移除之前的结果块
  const prev = container.querySelector('.exec-result');
  if (prev) prev.remove();
  const el = document.createElement('div');
  el.className = 'exec-result ' + (success ? 'exec-success' : 'exec-error');
  const text = document.createElement('span');
  text.textContent = (success ? '✅ ' : '❌ ') + msg;
  el.appendChild(text);
  if (!success) {
    const close = document.createElement('button');
    close.className = 'exec-result-close';
    close.textContent = '×';
    close.onclick = () => el.remove();
    el.appendChild(close);
  }
  container.appendChild(el);
}

async function executeSim(simId, btn) {
  if (!confirm('确认执行此操作？将真正同意/拒绝退款，不可撤销。')) return;
  if (btn) { btn.disabled = true; btn.textContent = '已加入队列'; }
  try {
    const res = await fetch('/api/simulations/' + simId + '/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (res.status === 202) {
      showToast('已加入执行队列，完成后自动刷新');
    } else {
      const data = await res.json().catch(() => ({}));
      if (res.status === 409 && data.alreadyQueued) {
        // 已在队列中，按钮保持禁用
        showToast('已在执行队列中，请稍候');
      } else {
        showToast(data.error || `服务器错误 ${res.status}`, 'error');
        if (btn) { btn.disabled = false; btn.textContent = '▶ 执行操作'; }
      }
    }
  } catch (e) {
    showToast('请求失败：' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = '▶ 执行操作'; }
  }
}

async function revokeFeedback(simId) {
  await api('/feedback/' + simId, { method: 'DELETE' });
  loadLive();
}

// 选择好/差评（不立即提交，激活提交按钮）
function selectVerdict(simId, verdict) {
  const posBtn = document.getElementById('fb-pos-' + simId);
  const negBtn = document.getElementById('fb-neg-' + simId);
  const submitBtn = document.getElementById('fb-submit-' + simId);
  if (!posBtn || !negBtn) return;

  // 记录选中状态到 DOM
  posBtn.dataset.selected = verdict === 'positive' ? '1' : '';
  negBtn.dataset.selected = verdict === 'negative' ? '1' : '';

  // 更新按钮样式
  posBtn.className = 'btn-positive' + (verdict === 'positive' ? ' btn-fb-active' : '');
  negBtn.className = 'btn-negative' + (verdict === 'negative' ? ' btn-fb-active' : '');
  posBtn.style.opacity = verdict === 'negative' ? '0.5' : '';
  negBtn.style.opacity = verdict === 'positive' ? '0.5' : '';
  posBtn.textContent = verdict === 'positive' ? '已好评 ✅' : '好评';
  negBtn.textContent = verdict === 'negative' ? '已差评 ❌' : '差评';

  // 更新点击事件为取消选择
  posBtn.onclick = verdict === 'positive'
    ? () => clearVerdict(simId)
    : () => selectVerdict(simId, 'positive');
  negBtn.onclick = verdict === 'negative'
    ? () => clearVerdict(simId)
    : () => selectVerdict(simId, 'negative');

  if (submitBtn) submitBtn.disabled = false;
}

function clearVerdict(simId) {
  const posBtn = document.getElementById('fb-pos-' + simId);
  const negBtn = document.getElementById('fb-neg-' + simId);
  const submitBtn = document.getElementById('fb-submit-' + simId);
  if (posBtn) { posBtn.className = 'btn-positive'; posBtn.style.opacity = ''; posBtn.textContent = '好评'; posBtn.onclick = () => selectVerdict(simId, 'positive'); }
  if (negBtn) { negBtn.className = 'btn-negative'; negBtn.style.opacity = ''; negBtn.textContent = '差评'; negBtn.onclick = () => selectVerdict(simId, 'negative'); }
  if (submitBtn) submitBtn.disabled = true;
}

async function submitPendingFeedback(simId, workOrderNum, queueItemId) {
  const posBtn = document.getElementById('fb-pos-' + simId);
  const verdict = posBtn && posBtn.dataset.selected === '1' ? 'positive' : 'negative';
  const submitBtn = document.getElementById('fb-submit-' + simId);
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '提交中…'; }
  const ok = await submitFeedback(simId, workOrderNum, verdict);
  if (ok && queueItemId) {
    // auto_executed 工单评价提交后自动归档，标注为自动处理
    await api('/queue/' + queueItemId + '/archive-manual', {
      method: 'POST',
      body: JSON.stringify({ simId, source: 'auto_executed' }),
    });
    loadLive();
  }
}

// ── 反馈（live 模式：好评/差评 读评价内容框；sim 模式由 judgeInline 直接传参）
async function submitFeedback(simId, workOrderNum, verdict, reason = '', suggestedAction = null, ruleImpact = null) {
  // 通过 ID 同时禁用两个按钮
  const posBtn = document.getElementById('fb-pos-' + simId);
  const negBtn = document.getElementById('fb-neg-' + simId);
  const inputEl = document.getElementById('fi-' + simId);
  if (posBtn) posBtn.disabled = true;
  if (negBtn) negBtn.disabled = true;
  // live 模式：若没有传 reason，则从输入框读取
  if (!reason && inputEl) reason = inputEl.value.trim();
  const res = await api('/feedback', {
    method: 'POST',
    body: JSON.stringify({ simulationId: simId, workOrderNum, verdict, reason, suggestedAction, ruleImpact }),
  });
  if (res.error) {
    showToast('提交失败：' + res.error, 'error');
    if (posBtn) posBtn.disabled = false;
    if (negBtn) negBtn.disabled = false;
    return;
  }
  showToast(verdict === 'positive' ? '已标记好评 ✅' : '已标记差评 ❌');
  return true;
}

async function deleteItem(itemId) {
  if (!confirm('确认删除？')) return;
  await api('/queue/' + itemId, { method: 'DELETE' });
  loadLive(); loadSim();
}

function closeModal() { document.getElementById('modal').classList.add('hidden'); }
document.getElementById('modal').addEventListener('click', e => {
  if (e.target === document.getElementById('modal')) closeModal();
});

// ── 统计复盘 ─────────────────────────────────────────────────────
async function loadStats() {
  const [stats, feedbacks, pendingInsight, recentInsights] = await Promise.all([
    api('/stats'),
    api('/feedback?limit=50'),
    api('/feedback?uninsighted=1'),
    api('/insights'),
  ]);
  const el = document.getElementById('stats-content');
  const accuracy = stats.accuracy !== null ? (stats.accuracy * 100).toFixed(1) + '%' : '—';

  const cardsHtml = `
<div class="stats-grid">
  <div class="stat-card"><div class="stat-number">${accuracy}</div><div class="stat-label">整体正确率</div></div>
  <div class="stat-card"><div class="stat-number">${stats.total||0}</div><div class="stat-label">累计推理</div></div>
  <div class="stat-card"><div class="stat-number green">${stats.positive||0}</div><div class="stat-label">✅ 正确</div></div>
  <div class="stat-card"><div class="stat-number red">${stats.negative||0}</div><div class="stat-label">❌ 错误</div></div>
</div>`;

  // 待洞察反馈区
  const pendingCount = (pendingInsight || []).length;
  const insightHtml = `
<div class="chart-section">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">
    <h3 style="margin:0">AI 洞察</h3>
    <button class="btn-primary" style="padding:4px 12px;font-size:13px"
      onclick="generateInsight(this)"
      ${pendingCount === 0 ? 'disabled title="暂无待洞察的有说明反馈"' : ''}>
      ${pendingCount > 0 ? `生成洞察（${pendingCount} 条待处理）` : '暂无待洞察内容'}
    </button>
  </div>
  ${pendingCount > 0 ? `
  <div style="font-size:13px;color:var(--gray-600);margin-bottom:8px">待洞察反馈：</div>
  ${(pendingInsight||[]).map(f => `
  <div class="feedback-item" style="margin-bottom:6px">
    <div class="fb-icon">${f.verdict==='positive'?'✅':'❌'}</div>
    <div class="fb-content">
      <div class="fb-num">${f.workOrderNum||'—'}</div>
      <div class="fb-reason">${h(f.reason)}</div>
    </div>
  </div>`).join('')}` : ''}
  ${(recentInsights||[]).length ? `
  <div style="font-size:13px;color:var(--gray-600);margin-top:12px;margin-bottom:6px">历史洞察：</div>
  ${(recentInsights||[]).map(ins => `
  <div style="border:1px solid var(--gray-200);border-radius:6px;padding:8px 12px;margin-bottom:6px;font-size:13px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="color:var(--gray-500)">${ins.createdAt}</span>
      <button class="btn-ghost" style="font-size:12px;padding:2px 8px" onclick="viewInsight('${ins.file}')">查看全文</button>
    </div>
    <div style="margin-top:4px;color:var(--gray-700);white-space:pre-wrap">${h(ins.preview)}…</div>
  </div>`).join('')}` : ''}
</div>`;

  // 最近有说明的反馈记录（已洞察的也展示，供回顾）
  const recentFb = (feedbacks || []).filter(f => (f.reason||'').trim()).reverse();
  const fbHtml = recentFb.length ? `
<div class="chart-section"><h3>反馈记录（有说明）</h3>
  ${recentFb.map(f => `
  <div class="feedback-item" style="margin-bottom:8px">
    <div class="fb-icon">${f.verdict==='positive'?'✅':'❌'}</div>
    <div class="fb-content">
      <div class="fb-num">${f.workOrderNum||'—'}${f.insightedAt ? ' <span style="font-size:11px;color:var(--gray-400)">已洞察</span>' : ''}</div>
      <div class="fb-reason">${h(f.reason)}</div>
      <div class="fb-time">${new Date(f.createdAt).toLocaleString('zh-CN')}</div>
    </div>
  </div>`).join('')}
</div>` : '';

  el.innerHTML = cardsHtml + insightHtml + fbHtml;
}

function generateInsights(stats) {
  const insights = [];
  if (!stats.feedbackCount) {
    insights.push({ type: '', title: '暂无足够数据', desc: '完成至少 5 次模拟训练判定后，将自动生成洞察分析。' });
    return insights;
  }
  const acc = stats.accuracy;
  if (acc !== null) {
    if (acc >= 0.9) insights.push({ type: 'ok', title: `正确率 ${(acc*100).toFixed(0)}%，表现良好`, desc: '继续积累案例，关注边缘场景。' });
    else if (acc >= 0.7) insights.push({ type: '', title: `正确率 ${(acc*100).toFixed(0)}%，仍有提升空间`, desc: '建议重点审查错误案例对应的规则文档。' });
    else insights.push({ type: 'warn', title: `正确率 ${(acc*100).toFixed(0)}%，需要重点优化`, desc: '运行 node simulate.js feedback-summary 获取规则修订建议。' });
  }
  const ruleEntries = Object.entries(stats.byRule || {});
  if (ruleEntries.length) {
    const worst = ruleEntries.sort((a,b) => b[1].negative/b[1].total - a[1].negative/a[1].total)[0];
    const err = Math.round(worst[1].negative/worst[1].total*100);
    if (err > 20) insights.push({ type: 'warn', title: `「${worst[0]}」错误率 ${err}%`, desc: `共 ${worst[1].total} 次命中，${worst[1].negative} 次判断错误，建议优先修订。` });
  }
  return insights;
}

// ── 洞察操作 ─────────────────────────────────────────────────────
async function generateInsight(btn) {
  btn.disabled = true;
  btn.textContent = '生成中…';
  try {
    const res = await api('/insights/generate', { method: 'POST' });
    if (res.error) { showToast('洞察失败：' + res.error, 'error'); btn.disabled = false; btn.textContent = '生成洞察'; return; }
    showToast(`已提交 ${res.count} 条反馈，洞察生成中，完成后自动刷新…`);
  } catch(e) {
    showToast('请求失败：' + e.message, 'error');
    btn.disabled = false;
  }
}

async function viewInsight(file) {
  const res = await api('/insights/' + encodeURIComponent(file));
  if (!res || res.error) return;
  const win = window.open('', '_blank');
  win.document.write(`<pre style="font-family:sans-serif;padding:20px;white-space:pre-wrap">${res.content.replace(/</g,'&lt;')}</pre>`);
}

// ── 到期预警横幅（header 常驻） ───────────────────────────────────
function formatAbsTime(iso) {
  var d = new Date(iso);
  var mm = String(d.getMonth() + 1).padStart(2, '0');
  var dd = String(d.getDate()).padStart(2, '0');
  var hh = String(d.getHours()).padStart(2, '0');
  var mi = String(d.getMinutes()).padStart(2, '0');
  return mm + '/' + dd + ' ' + hh + ':' + mi;
}

async function refreshDeadlineAlert() {
  var el = document.getElementById('deadline-alert');
  if (!el) return;
  try {
    var res = await fetch('/api/queue?mode=live');
    if (!res.ok) return;
    var data = await res.json();
    var now = Date.now();
    // 只关注活跃中的工单（pending/simulated/waiting/collecting/inferring）
    var active = (data.items || []).filter(function(i) {
      return ['pending', 'simulated', 'waiting', 'collecting', 'inferring'].includes(i.status) && i.deadlineAt;
    });
    // 只显示下次扫描前会超时的工单（≤6小时，与创建提醒逻辑相同）
    var urgent = active.filter(function(i) { return (new Date(i.deadlineAt) - now) <= 6 * 3600000; });

    if (urgent.length === 0) {
      el.className = 'deadline-alert hidden';
      return;
    }

    var lines = urgent.map(function(i) {
      var diff = new Date(i.deadlineAt) - now;
      var h = Math.floor(diff / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var remain = h > 0 ? h + '小时' + (m > 0 ? m + '分' : '') : m + '分钟';
      return (i.accountNote || '工单') + ' 剩余' + remain + '（截止 ' + formatAbsTime(i.deadlineAt) + '）';
    });

    el.className = 'deadline-alert urgent';
    el.innerHTML = '<span class="da-icon">🚨</span><div class="da-list">' +
      lines.map(function(l) { return '<div class="da-item">' + l + '</div>'; }).join('') +
      '</div>';
  } catch(e) {}
}

// ── 快递行动区 ────────────────────────────────────────────────────
function extractBrand(accountNote) {
  if (!accountNote) return '未知';
  const parts = accountNote.split('-');
  return parts.length > 1 ? parts[parts.length - 1] : accountNote;
}

function groupByBrand(items) {
  const map = {};
  items.forEach(item => {
    const brand = item.brand || '未知';
    if (!map[brand]) map[brand] = [];
    map[brand].push(item);
  });
  return map;
}

// 从 collectedData 中收集所有需拦截的发货快递单号（主订单+赠品，含分包）
function getShipRows(cd) {
  const result = [];
  const seen = new Set();
  function addFrom(erpData) {
    const rows = (erpData && erpData.rows && erpData.rows.rows) || [];
    rows.forEach(function(row) {
      if (row.status !== '卖家已发货') return;
      const ts = (row.trackings && row.trackings.length) ? row.trackings : (row.tracking ? [row.tracking] : []);
      ts.forEach(function(t) { if (t && !seen.has(t)) { seen.add(t); result.push(t); } });
    });
  }
  addFrom(cd.erpSearch);
  addFrom(cd.giftErpSearch);
  return result;
}

async function loadActionBadge() {
  try {
    const [queue, sims] = await Promise.all([api('/queue?mode=live'), api('/simulations?mode=live')]);
    const ACTIVE = ['waiting', 'simulated'];
    const items = (queue.items || []).filter(i => ACTIVE.includes(i.status));
    const simsByQueueId = {};
    (sims || []).forEach(s => { if (!simsByQueueId[s.queueItemId]) simsByQueueId[s.queueItemId] = []; simsByQueueId[s.queueItemId].push(s); });
    let count = 0;
    for (const item of items) {
      const allSims = simsByQueueId[item.id] || [];
      const sim = allSims[allSims.length - 1];
      if (!sim || !sim.collectedData || !sim.decision) continue;
      const ticket = sim.collectedData.ticket || {};
      const reason = sim.decision.reason || '';
      if (sim.decision.action === 'escalate') {
        if (!ticket.returnTracking && (reason.includes('拦截') || reason.includes('在途'))) {
          count += getShipRows(sim.collectedData).length;
        }
        if (ticket.returnTracking && (reason.includes('拆包') || reason.includes('尚未入库') || reason.includes('在途'))) count++;
      }
    }
    const badgeEl = document.getElementById('action-tab-count');
    if (badgeEl) badgeEl.textContent = count || '';
  } catch(e) {}
}

async function dismissSelected(panelType) {
  const panel = document.querySelector(`.action-panel[data-type="${panelType}"]`);
  if (!panel) return;
  const checked = panel.querySelectorAll('.action-cb:checked');
  if (!checked.length) { showToast('请先勾选要标记的快递单号', 'error'); return; }
  const entries = Array.from(checked).map(cb => ({
    tracking: cb.dataset.tracking,
    type: panelType,
    workOrderNum: cb.dataset.won || '',
  }));
  try {
    await api('/action-dismiss', { method: 'POST', body: JSON.stringify({ entries }) });
    showToast(`已标记 ${entries.length} 条为已处理`);
    loadActionList();
  } catch(e) {
    showToast('标记失败：' + e.message, 'error');
  }
}

async function undismiss(tracking, panelType) {
  try {
    await api('/action-dismiss/' + encodeURIComponent(tracking), { method: 'DELETE' });
    loadActionList();
  } catch(e) {
    showToast('取消标记失败：' + e.message, 'error');
  }
}

function toggleBrandSelect(brandKey) {
  const group = document.querySelector(`.action-brand-group[data-brand-key="${CSS.escape(brandKey)}"]`);
  if (!group) return;
  const cbs = group.querySelectorAll('.action-cb');
  const allChecked = Array.from(cbs).every(cb => cb.checked);
  cbs.forEach(cb => { cb.checked = !allChecked; });
}

async function loadActionList() {
  const [queue, sims, dismissed] = await Promise.all([
    api('/queue?mode=live'),
    api('/simulations?mode=live'),
    api('/action-dismissed').catch(() => ({})),
  ]);

  const ACTIVE = ['waiting', 'simulated', 'pending', 'collecting', 'inferring'];
  const items = (queue.items || []).filter(i => ACTIVE.includes(i.status));

  const simsByQueueId = {};
  (sims || []).forEach(s => {
    if (!simsByQueueId[s.queueItemId]) simsByQueueId[s.queueItemId] = [];
    simsByQueueId[s.queueItemId].push(s);
  });

  const intercepts = [];          // 待拦截（发出包裹在途）
  const returnsWaiting = [];      // 退货待入库（客户寄回但未入库）
  const dismissedIntercepts = []; // 已标记处理的待拦截
  const dismissedReturns = [];    // 已标记处理的退货

  for (const item of items) {
    const allSims = simsByQueueId[item.id] || [];
    const sim = allSims[allSims.length - 1];
    if (!sim || !sim.collectedData) continue;

    const cd = sim.collectedData;
    const ticket = cd.ticket || {};
    const decision = sim.decision;
    const reason = (decision && decision.reason) || '';
    const brand = extractBrand(item.accountNote);
    const base = {
      workOrderNum: item.workOrderNum,
      accountNote: item.accountNote,
      brand,
      deadlineAt: item.deadlineAt,
      accountNum: item.accountNum,
    };

    // 待拦截：决策含"拦截"或"在途"，且 returnTracking 为空（发出包裹拦截，非退货）
    // 包含主订单所有分包快递单号 + 赠品子订单对应的快递单号
    if (decision && decision.action === 'escalate' && !ticket.returnTracking &&
        (reason.includes('拦截') || reason.includes('在途'))) {
      getShipRows(cd).forEach(tracking => {
        if (dismissed && dismissed[tracking]) {
          dismissedIntercepts.push({ ...base, tracking });
        } else {
          intercepts.push({ ...base, tracking });
        }
      });
    }

    // 退货待入库：有 returnTracking，且决策含"拆包"/"尚未入库"/"在途"
    if (ticket.returnTracking && decision && decision.action === 'escalate' &&
        (reason.includes('拆包') || reason.includes('尚未入库') || reason.includes('在途'))) {
      if (dismissed && dismissed[ticket.returnTracking]) {
        dismissedReturns.push({ ...base, tracking: ticket.returnTracking });
      } else {
        returnsWaiting.push({ ...base, tracking: ticket.returnTracking });
      }
    }
  }

  const totalCount = intercepts.length + returnsWaiting.length;
  const badgeEl = document.getElementById('action-tab-count');
  if (badgeEl) badgeEl.textContent = totalCount || '';
  const countEl = document.getElementById('action-count');
  if (countEl) countEl.textContent = totalCount;

  const el = document.getElementById('action-content');
  if (!el) return;

  if (!intercepts.length && !returnsWaiting.length && !dismissedIntercepts.length && !dismissedReturns.length) {
    el.innerHTML = '<div class="empty-state">暂无需要操作的快递单号。</div>';
    return;
  }

  el.innerHTML = renderActionPanel('🚨 待拦截快递', '发出的包裹仍在途，需联系快递拦截', intercepts, 'intercept', dismissedIntercepts) +
                 renderActionPanel('📦 退货待入库', '客户已寄回，等待仓库拆包入库确认', returnsWaiting, 'return', dismissedReturns);
}

function renderActionPanel(title, subtitle, items, panelType, dismissedItems = []) {
  if (!items.length && !dismissedItems.length) return '';

  const byBrand = groupByBrand(items.length ? items : []);
  const allTrackings = items.map(i => i.tracking);

  const brandSections = Object.entries(byBrand).map(([brand, list]) => {
    const trackings = list.map(i => i.tracking);
    const brandKey = panelType + '-' + brand;
    const rows = list.map(item => {
      const cd = formatCountdown(item.deadlineAt);
      const urgencyHtml = cd ? `<span class="tag tag-urgency ${cd.className}" style="font-size:10px;padding:1px 6px">⏰ ${cd.text}</span>` : '';
      return `<div class="action-tracking-row">
        <input type="checkbox" class="action-cb" data-tracking="${h(item.tracking)}" data-won="${h(item.workOrderNum)}">
        <span class="action-tracking-num">${h(item.tracking)}</span>
        <span class="action-wono">${h(item.workOrderNum)}</span>
        ${urgencyHtml}
        <button class="btn-ghost btn-sm" onclick="openTicket('${item.workOrderNum}',${item.accountNum || 'null'},this)" style="margin-left:auto">查看</button>
      </div>`;
    }).join('');

    return `
<div class="action-brand-group" data-brand-key="${h(brandKey)}">
  <div class="action-brand-header">
    <input type="checkbox" class="action-brand-cb" onclick="toggleBrandSelect('${h(brandKey)}')" title="全选此品牌">
    <span class="action-brand-name">${h(brand)}</span>
    <span class="action-brand-count">${list.length} 单</span>
    <button class="btn-ghost btn-sm" data-trackings='${JSON.stringify(trackings)}' onclick="copyFromBtn(this)">复制 ${list.length} 条</button>
  </div>
  <div class="action-tracking-list">
    ${rows}
  </div>
</div>`;
  }).join('');

  const dismissedSection = dismissedItems.length ? `
<details class="action-dismissed-section">
  <summary class="action-dismissed-summary">已标记处理 (${dismissedItems.length}) — 点击展开</summary>
  <div class="action-dismissed-list">
    ${dismissedItems.map(item => `
    <div class="action-tracking-row action-tracking-dismissed">
      <span class="action-tracking-num">${h(item.tracking)}</span>
      <span class="action-wono">${h(item.workOrderNum)}</span>
      <span style="font-size:11px;color:var(--gray-400);margin-left:4px">${h(item.brand)}</span>
      <button class="btn-ghost btn-sm" style="margin-left:auto;color:var(--blue);font-size:11px" onclick="undismiss('${h(item.tracking)}','${panelType}')">取消标记</button>
    </div>`).join('')}
  </div>
</details>` : '';

  const headerButtons = items.length ? `
    <button class="btn-ghost" style="padding:5px 12px;font-size:12px" onclick="dismissSelected('${panelType}')">✓ 标记已处理</button>
    <button class="btn-primary" style="padding:5px 12px;font-size:12px" data-trackings='${JSON.stringify(allTrackings)}' onclick="copyFromBtn(this)">全部复制 (${items.length})</button>` : '';

  return `
<div class="action-panel" data-type="${panelType}">
  <div class="action-panel-header">
    <div>
      <span class="action-panel-title">${title}</span>
      <span class="action-panel-count">${items.length} 单</span>
    </div>
    <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <span style="font-size:12px;color:var(--gray-400)">${subtitle}</span>
      ${headerButtons}
    </div>
  </div>
  <div class="action-brand-sections">
    ${brandSections}
  </div>
  ${dismissedSection}
</div>`;
}

function copyFromBtn(btn) {
  try {
    const trackings = JSON.parse(btn.dataset.trackings || '[]');
    doCopy(trackings, btn);
  } catch(e) { showToast('复制失败：数据解析错误', 'error'); }
}

function doCopy(trackings, btn) {
  const text = trackings.join('\n');
  const orig = btn.textContent;
  function onSuccess() {
    btn.textContent = '已复制 ✓';
    setTimeout(() => { btn.textContent = orig; }, 2000);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(onSuccess).catch(() => fallbackCopy(text, onSuccess));
  } else {
    fallbackCopy(text, onSuccess);
  }
}

function fallbackCopy(text, cb) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
  document.body.appendChild(ta);
  ta.focus(); ta.select();
  try { document.execCommand('copy'); cb(); } catch(e) { showToast('复制失败，请手动复制', 'error'); }
  document.body.removeChild(ta);
}

// ── 初始化 ────────────────────────────────────────────────────────
connectSSE();
loadAllLiveTabs();
loadActionBadge();
refreshDeadlineAlert();
setInterval(refreshDeadlineAlert, 60000);

// 实时倒计时刷新（每 60 秒更新所有 deadline 元素）
setInterval(function() {
  document.querySelectorAll('[data-deadline]').forEach(function(el) {
    var cd = formatCountdown(el.dataset.deadline);
    if (cd) {
      el.textContent = '\u23f0 ' + cd.text;
      el.className = 'tag tag-urgency ' + cd.className;
    }
  });
}, 60000);

// ── 店铺管理 ─────────────────────────────────────────────────────
const reloginPending = new Set();

async function loadAccounts() {
  const el = document.getElementById('accounts-list');
  if (!el) return;
  const data = await api('/accounts');
  if (!data.ok) { el.innerHTML = `<p style="color:red">加载失败</p>`; return; }
  const accounts = data.accounts || [];
  const expiredCount = accounts.filter(a => a.status === 'expired').length;
  const badge = document.getElementById('accounts-tab-count');
  if (badge) badge.textContent = expiredCount > 0 ? expiredCount : '';

  el.innerHTML = accounts.map(a => {
    const statusKey = !a.hasFile ? 'unknown' : (a.status || 'unknown');
    const statusLabel = { ok: '正常', expired: '登录失效', error: '扫描异常', unknown: '未扫描' }[statusKey] || '未知';
    const isPending = reloginPending.has(a.num);
    const showReloginBtn = statusKey === 'expired' || statusKey === 'error' || statusKey === 'unknown' || !a.hasFile;
    const btnLabel = isPending ? '等待登录中...' : (!a.hasFile ? '添加登录' : '重新登录');
    const lastScan = a.lastScan ? new Date(a.lastScan).toLocaleString('zh-CN', { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '—';
    return `<div class="account-card status-${statusKey}">
      <div class="account-header">
        <span class="account-num">账号${a.num}</span>
        <span class="account-status-tag ${statusKey}">${statusLabel}</span>
      </div>
      <div class="account-note">${h(a.note || a.name)}</div>
      <div class="account-meta">上次扫描：${lastScan}${a.status === 'ok' && a.count !== undefined ? `　工单：${a.count}` : ''}</div>
      ${a.error ? `<div class="account-error">${h(a.error)}</div>` : ''}
      <div class="account-actions">
        ${a.hasFile ? `<button class="btn-ghost btn-sm" onclick="openAccountStore(${a.num})">打开店铺后台</button>` : ''}
        ${showReloginBtn ? `<button class="btn-relogin${isPending ? ' pending' : ''}" onclick="reloginAccount(${a.num})" ${isPending ? 'disabled' : ''}>${btnLabel}</button>` : ''}
      </div>
    </div>`;
  }).join('');
}

async function reloginAccount(num) {
  reloginPending.add(num);
  loadAccounts();
  const res = await api(`/accounts/${num}/relogin`, { method: 'POST' });
  showToast(res.message || `已启动账号${num}登录窗口`);
  // 30秒后自动刷新状态（登录成功会通过 SSE 推送）
  setTimeout(() => { reloginPending.delete(num); loadAccounts(); }, 30000);
}

async function openAccountStore(num) {
  const res = await api(`/accounts/${num}/open`, { method: 'POST' });
  showToast(res.message || `已打开账号${num}店铺后台`);
}

async function addNewAccount() {
  const note = prompt('请输入新店铺备注（如：店铺名-品牌）：');
  if (!note || !note.trim()) return;
  const res = await api('/accounts/add', { method: 'POST', body: JSON.stringify({ note: note.trim() }) });
  if (res.ok) {
    showToast(res.message || '新店铺已创建，正在启动登录窗口');
    setTimeout(loadAccounts, 2000);
  } else {
    showToast(res.error || '创建失败', 'error');
  }
}
