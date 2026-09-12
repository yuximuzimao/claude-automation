'use strict';

const { createReminder } = require('../lib/helpers');
const { COUNTER_DEFINITIONS } = require('./selectors');

function activeCounters(counts = {}) {
  return COUNTER_DEFINITIONS
    .map(definition => ({
      ...definition,
      count: Number(counts[definition.key] || 0),
    }))
    .filter(item => Number.isFinite(item.count) && item.count > 0);
}

function totalCount(counts = {}) {
  return activeCounters(counts).reduce((sum, item) => sum + item.count, 0);
}

function summarizeCounts(counts = {}, options = {}) {
  const items = activeCounters(counts);
  const limit = options.limit == null ? items.length : Math.max(1, Number(options.limit));
  const visible = items.slice(0, limit).map(item => `${item.shortLabel} ${item.count}`);
  if (items.length > limit) visible.push(`另${items.length - limit}项`);
  return visible.join(' · ');
}

function buildPendingReminder(counts = {}) {
  const summary = summarizeCounts(counts);
  return summary ? `【万物待办】${summary}，请打开棒棒糖后台管理处理` : '';
}

function buildFailureReminder(error) {
  const reason = String(error && error.message || error || '扫描异常').slice(0, 100);
  return `【万物异常】${reason}，请检查棒棒糖后台管理`;
}

function sendPendingReminder(counts, send = createReminder) {
  const title = buildPendingReminder(counts);
  return title ? send(title) : true;
}

function sendFailureReminder(error, send = createReminder) {
  return send(buildFailureReminder(error));
}

module.exports = {
  activeCounters,
  totalCount,
  summarizeCounts,
  buildPendingReminder,
  buildFailureReminder,
  sendPendingReminder,
  sendFailureReminder,
};
