'use strict';

const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '../../data');
const QUEUE_PATH = path.join(DATA_DIR, 'queue.json');
const SIM_PATH = path.join(DATA_DIR, 'simulations.jsonl');
const FB_PATH = path.join(DATA_DIR, 'feedback.jsonl');
const CASES_PATH = path.join(DATA_DIR, 'cases.jsonl');
const INTERCEPTS_PATH = path.join(DATA_DIR, 'intercepts.json');
const DISMISSED_PATH = path.join(DATA_DIR, 'action-dismissed.json');

// ── Intercepts（已拦截快递单号记录）──────────────────────────────────
// 结构：{ [shipTracking]: { workOrderNum, executedAt, accountNote } }

function readIntercepts() {
  try { return JSON.parse(fs.readFileSync(INTERCEPTS_PATH, 'utf8')); } catch { return {}; }
}

function addIntercept({ shipTracking, workOrderNum, accountNote }) {
  if (!shipTracking) return;
  const map = readIntercepts();
  map[shipTracking] = { workOrderNum, accountNote: accountNote || '', executedAt: new Date().toISOString() };
  fs.writeFileSync(INTERCEPTS_PATH, JSON.stringify(map, null, 2));
}

const INTERCEPT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7天

function hasIntercept(shipTracking) {
  if (!shipTracking) return null;
  const map = readIntercepts();
  const rec = map[shipTracking];
  if (!rec) return null;
  // 7天过期兜底
  if (rec.executedAt && Date.now() - new Date(rec.executedAt).getTime() > INTERCEPT_TTL_MS) {
    removeIntercept(shipTracking);
    return null;
  }
  return rec;
}

function removeIntercept(shipTracking) {
  if (!shipTracking) return;
  const map = readIntercepts();
  if (!map[shipTracking]) return;
  delete map[shipTracking];
  fs.writeFileSync(INTERCEPTS_PATH, JSON.stringify(map, null, 2));
}

// ── Queue ─────────────────────────────────────────────────────────

function readQueue() {
  try {
    return JSON.parse(fs.readFileSync(QUEUE_PATH, 'utf8'));
  } catch {
    return { updatedAt: null, items: [] };
  }
}

function writeQueue(data) {
  const tmp = QUEUE_PATH + '.tmp';
  data.updatedAt = new Date().toISOString();
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2));
  fs.renameSync(tmp, QUEUE_PATH);
}

function addQueueItem(item) {
  const queue = readQueue();
  const exists = queue.items.some(
    i => i.workOrderNum === item.workOrderNum && i.status !== 'done'
  );
  if (exists) return null;

  // live 模式：已有执行记录（executedAt）的工单不重复入队
  if ((item.mode || 'sim') === 'live') {
    const sims = readSimulations();
    const executed = sims.some(
      s => s.workOrderNum === item.workOrderNum && s.mode === 'live' && !!s.executedAt
    );
    if (executed) return null;
  }

  const id = `q-${Date.now()}-${queue.items.length}`;
  const newItem = {
    id,
    workOrderNum: item.workOrderNum,
    accountNum: item.accountNum || null,
    accountNote: item.accountNote || '',
    mode: item.mode || 'sim',
    source: item.source || 'web',
    addedAt: new Date().toISOString(),
    status: 'pending',
    type: item.type || null,
    urgency: item.urgency || null,
    deadlineAt: item.deadlineAt || null,
    groundTruth: item.groundTruth || null,
  };
  queue.items.push(newItem);
  writeQueue(queue);
  return newItem;
}

function updateQueueItem(id, patch) {
  const queue = readQueue();
  const idx = queue.items.findIndex(i => i.id === id);
  if (idx === -1) return null;
  queue.items[idx] = { ...queue.items[idx], ...patch };
  writeQueue(queue);
  return queue.items[idx];
}

function deleteQueueItem(id) {
  const queue = readQueue();
  const before = queue.items.length;
  queue.items = queue.items.filter(i => i.id !== id);
  if (queue.items.length === before) return false;
  writeQueue(queue);
  return true;
}

// ── Simulations ───────────────────────────────────────────────────

function readSimulations(filter = {}) {
  if (!fs.existsSync(SIM_PATH)) return [];
  const lines = fs.readFileSync(SIM_PATH, 'utf8').split('\n').filter(Boolean);
  let sims = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

  if (filter.mode) sims = sims.filter(s => s.mode === filter.mode);
  if (filter.status) sims = sims.filter(s => (s.feedbackStatus || 'pending') === filter.status);
  if (filter.limit) sims = sims.slice(-filter.limit);
  return sims;
}

function getSimulation(id) {
  return readSimulations().find(s => s.id === id) || null;
}

function appendSimulation(sim) {
  fs.appendFileSync(SIM_PATH, JSON.stringify(sim) + '\n');
}

function updateSimulation(id, patch) {
  const lines = fs.readFileSync(SIM_PATH, 'utf8').split('\n').filter(Boolean);
  let found = false;
  const updated = lines.map(l => {
    try {
      const sim = JSON.parse(l);
      if (sim.id === id) {
        found = true;
        return JSON.stringify({ ...sim, ...patch });
      }
      return l;
    } catch { return l; }
  });
  if (!found) return null;
  fs.writeFileSync(SIM_PATH, updated.join('\n') + '\n');
  return getSimulation(id);
}

// ── Feedback ──────────────────────────────────────────────────────

function readFeedback(filter = {}) {
  if (!fs.existsSync(FB_PATH)) return [];
  const lines = fs.readFileSync(FB_PATH, 'utf8').split('\n').filter(Boolean);
  let items = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  if (filter.verdict) items = items.filter(f => f.verdict === filter.verdict);
  if (filter.withReason) items = items.filter(f => (f.reason || '').trim());
  if (filter.uninsighted) items = items.filter(f => !f.insightedAt && (f.reason || '').trim());
  if (filter.limit) items = items.slice(-filter.limit);
  return items;
}

function markFeedbackInsighted(ids) {
  if (!fs.existsSync(FB_PATH)) return;
  const now = new Date().toISOString();
  const idSet = new Set(ids);
  const lines = fs.readFileSync(FB_PATH, 'utf8').split('\n').filter(Boolean);
  const updated = lines.map(l => {
    try {
      const f = JSON.parse(l);
      if (idSet.has(f.id)) return JSON.stringify({ ...f, insightedAt: now });
      return l;
    } catch { return l; }
  });
  fs.writeFileSync(FB_PATH, updated.join('\n') + '\n');
}

function appendFeedback(fb) {
  const id = `fb-${Date.now()}`;
  const record = { id, ...fb, createdAt: new Date().toISOString() };
  fs.appendFileSync(FB_PATH, JSON.stringify(record) + '\n');
  // 同步更新 simulation 的 feedbackStatus
  updateSimulation(fb.simulationId, { feedbackStatus: fb.verdict });
  return record;
}

function revokeFeedback(simId) {
  if (!fs.existsSync(FB_PATH)) return;
  const lines = fs.readFileSync(FB_PATH, 'utf8').split('\n').filter(Boolean);
  const kept = lines.filter(l => {
    try { return JSON.parse(l).simulationId !== simId; } catch { return true; }
  });
  fs.writeFileSync(FB_PATH, kept.join('\n') + (kept.length ? '\n' : ''));
  updateSimulation(simId, { feedbackStatus: 'pending' });
}

// ── Cases ─────────────────────────────────────────────────────────

function readCases(filter = {}) {
  if (!fs.existsSync(CASES_PATH)) return { items: [], total: 0 };
  const lines = fs.readFileSync(CASES_PATH, 'utf8').split('\n').filter(Boolean);
  let cases = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

  // 过滤掉仍在 live queue 中处理中的工单（status !== 'done'）
  // 这些工单在"实际工单"页面展示，未完结不应出现在历史记录
  const queue = readQueue();
  const activeNums = new Set(
    queue.items.filter(i => i.status !== 'done' && i.mode === 'live').map(i => i.workOrderNum)
  );
  cases = cases.filter(c => !activeNums.has(c.workOrderNum));

  // 倒序（最新在前）
  cases = cases.reverse();
  const total = cases.length;

  const offset = filter.offset || 0;
  const limit = filter.limit || 50;
  cases = cases.slice(offset, offset + limit);

  return { items: cases, total };
}

function appendCase(c) {
  fs.appendFileSync(CASES_PATH, JSON.stringify(c) + '\n');
}

// ── Stats ─────────────────────────────────────────────────────────

function computeStats() {
  const sims = readSimulations();
  const feedbacks = readFeedback();
  const fbMap = {};
  feedbacks.forEach(f => { fbMap[f.simulationId] = f; });

  const judged = sims.filter(s => fbMap[s.id]);
  const positive = judged.filter(s => fbMap[s.id].verdict === 'positive').length;
  const negative = judged.filter(s => fbMap[s.id].verdict === 'negative').length;

  const byAction = {};
  const byRule = {};
  const byType = {};

  judged.forEach(s => {
    const action = s.decision && s.decision.action || 'unknown';
    const verdict = fbMap[s.id].verdict;

    if (!byAction[action]) byAction[action] = { total: 0, positive: 0, negative: 0 };
    byAction[action].total++;
    byAction[action][verdict]++;

    const type = s.collectedData && s.collectedData.ticket && s.collectedData.ticket.type || 'unknown';
    if (!byType[type]) byType[type] = { total: 0, positive: 0, negative: 0 };
    byType[type].total++;
    byType[type][verdict]++;

    const rules = s.decision && s.decision.rulesApplied || [];
    rules.forEach(r => {
      const doc = r.doc || 'unknown';
      if (!byRule[doc]) byRule[doc] = { total: 0, positive: 0, negative: 0 };
      byRule[doc].total++;
      byRule[doc][verdict]++;
    });
  });

  return {
    generatedAt: new Date().toISOString(),
    total: sims.length,
    feedbackCount: judged.length,
    positive,
    negative,
    accuracy: judged.length > 0 ? Math.round((positive / judged.length) * 1000) / 1000 : null,
    byAction,
    byRule,
    byType,
  };
}

// ── Action Dismissed（快递行动已标记处理，7天 TTL）────────────────────
// 结构：{ [tracking]: { type: 'intercept'|'return', dismissedAt, workOrderNum } }
const DISMISSED_TTL_MS = 7 * 24 * 60 * 60 * 1000;

function readDismissed() {
  try { return JSON.parse(fs.readFileSync(DISMISSED_PATH, 'utf8')); } catch { return {}; }
}

function addDismissed(entries) {
  // entries: [{ tracking, type, workOrderNum }]
  const map = readDismissed();
  const now = new Date().toISOString();
  // 清理过期条目
  Object.keys(map).forEach(k => {
    if (map[k].dismissedAt && Date.now() - new Date(map[k].dismissedAt).getTime() > DISMISSED_TTL_MS) {
      delete map[k];
    }
  });
  entries.forEach(({ tracking, type, workOrderNum }) => {
    if (tracking) map[tracking] = { type, workOrderNum: workOrderNum || '', dismissedAt: now };
  });
  fs.writeFileSync(DISMISSED_PATH, JSON.stringify(map, null, 2));
}

function isDismissed(tracking) {
  if (!tracking) return false;
  const map = readDismissed();
  const rec = map[tracking];
  if (!rec) return false;
  if (Date.now() - new Date(rec.dismissedAt).getTime() > DISMISSED_TTL_MS) return false;
  return true;
}

function removeDismissed(tracking) {
  if (!tracking) return;
  const map = readDismissed();
  delete map[tracking];
  fs.writeFileSync(DISMISSED_PATH, JSON.stringify(map, null, 2));
}

module.exports = {
  readQueue, writeQueue, addQueueItem, updateQueueItem, deleteQueueItem,
  readSimulations, getSimulation, appendSimulation, updateSimulation,
  readFeedback, appendFeedback, revokeFeedback, markFeedbackInsighted,
  readCases, appendCase,
  readDismissed, addDismissed, isDismissed, removeDismissed,
  computeStats,
  readIntercepts, addIntercept, hasIntercept, removeIntercept,
  INTERCEPT_TTL_MS,
};
