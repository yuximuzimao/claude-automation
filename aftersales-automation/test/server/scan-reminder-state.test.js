'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createScanReminderState,
  updateScanReminderState,
  sendScanSummaryReminders,
} = require('../../lib/server/op-queue');
const { BATCH_SAFE_REJECT_CODES } = require('../../lib/constants');

function collected(tracking) {
  return {
    erpSearch: { rows: { rows: [{ status: '卖家已发货', tracking }] } },
  };
}

test('同一扫描多个待拦截工单只设置一个汇总标记', () => {
  const state = createScanReminderState();
  updateScanReminderState(state, [
    { collectedData: collected('YT-1'), decision: { warnings: ['需创建快递拦截提醒'] } },
    { collectedData: collected('YT-2'), decision: { warnings: ['需创建快递拦截提醒'] } },
  ], () => null);

  assert.deepEqual(state, { needsIntercept: true, needsCancelIntercept: false });
});

test('快递行动已标记处理的不重复提醒，取消工单有拦截记录时汇总提醒取消拦截', () => {
  const state = createScanReminderState();
  updateScanReminderState(state, [
    { collectedData: collected('YT-OLD'), decision: { warnings: ['需创建快递拦截提醒'] } },
    { collectedData: collected('YT-CANCEL'), decision: { action: 'wait_archive', warnings: ['请取消快递拦截'] } },
  ], tracking => tracking === 'YT-OLD' || tracking === 'YT-CANCEL' ? { workOrderNum: 'old' } : null);

  assert.deepEqual(state, { needsIntercept: false, needsCancelIntercept: true });
});

test('扫描结束按类别最多发送两条汇总待办', () => {
  const reminders = [];
  sendScanSummaryReminders(
    { needsIntercept: true, needsCancelIntercept: true },
    title => { reminders.push(title); return true; }
  );

  assert.equal(reminders.length, 2);
  assert.match(reminders[0], /需要拦截/);
  assert.match(reminders[1], /取消.*拦截/);
});

test('历史驿站直接拒绝结果不再允许批量执行', () => {
  assert.equal(BATCH_SAFE_REJECT_CODES.includes('AT_STATION'), false);
});
