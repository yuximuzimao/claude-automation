'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  createScanReminderState,
  updateScanReminderState,
  sendScanSummaryReminders,
  buildDeadlineSummaryReminder,
  buildAccountAbnormalReminder,
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

test('同一扫描批次的快超时工单只生成最早截止时间的汇总提醒', () => {
  const now = new Date(2026, 8, 20, 14, 5, 0);
  const title = buildDeadlineSummaryReminder([
    { workOrderNum: '1002', deadlineAt: new Date(2026, 8, 20, 18, 35, 0).toISOString() },
    { workOrderNum: '1001', deadlineAt: new Date(2026, 8, 20, 16, 20, 0).toISOString() },
    { workOrderNum: '1003', deadlineAt: new Date(2026, 8, 21, 8, 0, 0).toISOString() },
  ], now);

  assert.equal(
    title,
    '【售后待办】有工单即将超时，最早剩余2小时15分，截止2026-09-20 16:20，请打开售后系统查看'
  );
  assert.doesNotMatch(title, /1001|1002|1003/);
});

test('没有尚未到期且进入提醒阈值的工单时不创建汇总文案', () => {
  const now = new Date(2026, 8, 20, 14, 5, 0);
  assert.equal(buildDeadlineSummaryReminder([
    { deadlineAt: new Date(2026, 8, 20, 13, 0, 0).toISOString() },
    { deadlineAt: new Date(2026, 8, 21, 8, 0, 0).toISOString() },
  ], now), null);
});

test('店铺新出现或变更异常时提醒，相同异常持续存在时不重复提醒', () => {
  const first = buildAccountAbnormalReminder(14, { status: 'ok' }, {
    status: 'error',
    note: '茗瑞-KGOS',
    error: '打开工单失败: 未识别到新标签页',
  });
  assert.equal(
    first,
    '【售后异常】茗瑞-KGOS：打开工单失败: 未识别到新标签页，请打开售后系统处理'
  );

  assert.equal(buildAccountAbnormalReminder(14, {
    status: 'error',
    error: '打开工单失败: 未识别到新标签页',
  }, {
    status: 'error',
    note: '茗瑞-KGOS',
    error: '打开工单失败: 未识别到新标签页',
  }), null);

  assert.match(buildAccountAbnormalReminder(14, {
    status: 'error',
    error: '打开工单失败: 未识别到新标签页',
  }, {
    status: 'expired',
    note: '茗瑞-KGOS',
    error: '登录已失效',
  }), /登录已失效/);
});

test('历史驿站直接拒绝结果不再允许批量执行', () => {
  assert.equal(BATCH_SAFE_REJECT_CODES.includes('AT_STATION'), false);
});
