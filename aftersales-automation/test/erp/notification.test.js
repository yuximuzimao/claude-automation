'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  buildErpDownReminder,
  alertErpDown,
} = require('../../lib/erp/navigate');

test('ERP 登录异常使用提醒事项文案', () => {
  assert.equal(
    buildErpDownReminder('连续3次认证失败，已熔断'),
    '【ERP异常】连续3次认证失败，已熔断，请打开售后系统检查 ERP 登录状态',
  );
});

test('ERP 登录异常通过创建提醒依赖发送，不触发系统通知', () => {
  const reminders = [];
  const result = alertErpDown('启动校验失败', title => {
    reminders.push(title);
    return true;
  });

  assert.equal(result, true);
  assert.deepEqual(reminders, [
    '【ERP异常】启动校验失败，请打开售后系统检查 ERP 登录状态',
  ]);
});
