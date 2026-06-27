'use strict';
/**
 * WHAT: live 三标签批量操作的显式作用域解析与候选筛选
 * WHERE: routes.js 的 batch-execute / batch-reprocess 路由调用
 * WHY: 防止前端店铺筛选后，后端批量操作仍误作用于隐藏店铺
 * ENTRY: lib/server/routes.js: selectExecutableSimulations / selectReprocessQueueItems
 */

const { isBatchExecutable } = require('../constants');

const AUTO_STATUSES = ['auto_executed', 'auto_executing'];
const FINISHED_STATUSES = ['done', ...AUTO_STATUSES];

function hasOwn(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj || {}, key);
}

function isBlank(value) {
  return value === undefined || value === null || String(value).trim() === '';
}

function parsePositiveAccountNum(value) {
  if (isBlank(value)) return null;
  const text = String(value).trim();
  if (!/^[1-9]\d*$/.test(text)) throw new Error('invalid accountNum');
  return Number(text);
}

function parseBatchExecuteRequest(body = {}) {
  const hasAccount = hasOwn(body, 'accountNum') && !isBlank(body.accountNum);
  const accountNum = parsePositiveAccountNum(body.accountNum);
  const hasScope = hasOwn(body, 'statusScope') && !isBlank(body.statusScope);

  // Backward compatibility: an empty legacy caller keeps the old broad behavior.
  if (!hasScope && !hasAccount) {
    return { statusScope: 'all', accountNum: null, explicitScope: false };
  }
  if (!hasScope) throw new Error('statusScope required');

  const statusScope = String(body.statusScope).trim();
  if (statusScope !== 'pending') throw new Error('invalid statusScope');
  return { statusScope, accountNum, explicitScope: true };
}

function parseBatchReprocessRequest(body = {}) {
  const hasAccount = hasOwn(body, 'accountNum') && !isBlank(body.accountNum);
  const accountNum = parsePositiveAccountNum(body.accountNum);
  const hasScope = hasOwn(body, 'statusScope') && !isBlank(body.statusScope);

  // Backward compatibility: an empty legacy caller keeps the old broad behavior.
  if (!hasScope && !hasAccount) {
    return { statusScope: 'all', accountNum: null, explicitScope: false };
  }
  if (!hasScope) throw new Error('statusScope required');

  const statusScope = String(body.statusScope).trim();
  if (!['pending', 'waiting', 'all'].includes(statusScope)) throw new Error('invalid statusScope');
  return { statusScope, accountNum, explicitScope: true };
}

function matchesAccount(item, accountNum) {
  if (accountNum == null) return true;
  return Number(item && item.accountNum) === accountNum;
}

function isPendingTabItem(item) {
  return !!(item && item.mode === 'live' && item.status !== 'waiting' && !FINISHED_STATUSES.includes(item.status));
}

function isWaitingTabItem(item) {
  return !!(item && item.mode === 'live' && item.status === 'waiting');
}

function isLegacyReprocessable(item) {
  return !!(item && item.mode === 'live' && !FINISHED_STATUSES.includes(item.status));
}

function parseUrgencyMinutes(urgency) {
  if (!urgency) return Infinity;
  let total = 0;
  const dm = String(urgency).match(/(\d+)天/); if (dm) total += parseInt(dm[1], 10) * 1440;
  const hm = String(urgency).match(/(\d+)小时/); if (hm) total += parseInt(hm[1], 10) * 60;
  const mm = String(urgency).match(/(\d+)分/); if (mm) total += parseInt(mm[1], 10);
  return total || Infinity;
}

function deadlineSortValue(item, now = Date.now()) {
  const deadlineMs = item && item.deadlineAt ? Date.parse(item.deadlineAt) : NaN;
  if (Number.isFinite(deadlineMs)) return deadlineMs;
  const urgencyMinutes = parseUrgencyMinutes(item && item.urgency);
  return Number.isFinite(urgencyMinutes) ? now + urgencyMinutes * 60000 : Infinity;
}

function sortLikeLivePage(a, b) {
  const diff = deadlineSortValue(a) - deadlineSortValue(b);
  if (diff !== 0) return diff;
  const accountDiff = (Number(a.accountNum) || 0) - (Number(b.accountNum) || 0);
  if (accountDiff !== 0) return accountDiff;
  return String(a.workOrderNum || '').localeCompare(String(b.workOrderNum || ''));
}

function latestSimulationsByQueue(simulations = []) {
  const latest = new Map();
  const sorted = [...simulations]
    .filter(s => s && s.mode === 'live' && s.decision)
    .sort((a, b) => new Date(a.createdAt || 0) - new Date(b.createdAt || 0));
  for (const sim of sorted) latest.set(sim.queueItemId, sim);
  return latest;
}

function selectExecutableSimulations({ simulations = [], queueItems = [], scope }) {
  const effectiveScope = scope || { statusScope: 'all', accountNum: null, explicitScope: false };
  const queueMap = new Map((queueItems || []).map(item => [item.id, item]));
  const latestByQueue = latestSimulationsByQueue(simulations);

  if (effectiveScope.explicitScope) {
    return [...queueMap.values()]
      .filter(item => effectiveScope.statusScope === 'pending' ? isPendingTabItem(item) : isLegacyReprocessable(item))
      .filter(item => matchesAccount(item, effectiveScope.accountNum))
      .sort(sortLikeLivePage)
      .map(item => latestByQueue.get(item.id))
      .filter(sim => {
        if (!sim || sim.executedAt) return false;
        const item = queueMap.get(sim.queueItemId);
        return item && isBatchExecutable(sim.decision, item.status);
      });
  }

  return [...latestByQueue.values()].filter(sim => {
    if (!sim || sim.executedAt) return false;
    const item = queueMap.get(sim.queueItemId);
    return item && matchesAccount(item, effectiveScope.accountNum) && isBatchExecutable(sim.decision, item.status);
  });
}

function selectReprocessQueueItems(queueItems = [], scope) {
  const effectiveScope = scope || { statusScope: 'all', accountNum: null, explicitScope: false };
  return (queueItems || [])
    .filter(item => {
      if (effectiveScope.statusScope === 'pending') return isPendingTabItem(item);
      if (effectiveScope.statusScope === 'waiting') return isWaitingTabItem(item);
      return isLegacyReprocessable(item);
    })
    .filter(item => matchesAccount(item, effectiveScope.accountNum))
    .sort(sortLikeLivePage);
}

module.exports = {
  parsePositiveAccountNum,
  parseBatchExecuteRequest,
  parseBatchReprocessRequest,
  selectExecutableSimulations,
  selectReprocessQueueItems,
  isPendingTabItem,
  isWaitingTabItem,
  sortLikeLivePage,
};
