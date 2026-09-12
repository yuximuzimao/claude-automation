'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  totalCount,
  summarizeCounts,
  buildPendingReminder,
  buildFailureReminder,
  sendPendingReminder,
} = require('../../wanwu/reminder');

test('万物待办按业务优先级汇总且支持顶部短摘要', () => {
  const counts = { pendingShip: 2, pendingAudit: 1, pendingTicket: 3 };
  assert.equal(totalCount(counts), 6);
  assert.equal(summarizeCounts(counts), '待发货 2 · 待审核 1 · 工单 3');
  assert.equal(summarizeCounts(counts, { limit: 2 }), '待发货 2 · 待审核 1 · 另1项');
  assert.equal(buildPendingReminder(counts), '【万物待办】待发货 2 · 待审核 1 · 工单 3，请打开棒棒糖后台管理处理');
});

test('没有待办时不调用提醒快捷指令', () => {
  let calls = 0;
  assert.equal(sendPendingReminder({}, () => { calls++; return true; }), true);
  assert.equal(calls, 0);
});

test('扫描异常提醒包含具体原因', () => {
  assert.match(buildFailureReminder(new Error('登录后未进入首页')), /万物异常.*登录后未进入首页/);
});
