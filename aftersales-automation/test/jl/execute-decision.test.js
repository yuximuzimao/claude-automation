'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { getExecutionLabels } = require('../../lib/jl/execute-decision');

test('换货同意使用换货专属按钮，不复用退款按钮', () => {
  assert.deepEqual(getExecutionLabels('换货', 'approve'), {
    actionLabel: '同意换货',
    confirmActionLabel: '确认同意换货',
  });
});

test('换货拒绝只允许精确点击拒绝换货按钮', () => {
  assert.deepEqual(getExecutionLabels('换货', 'reject'), {
    actionLabels: ['拒绝换货'],
    confirmActionLabels: ['确认拒绝换货'],
  });
});

test('退货退款保持原退款执行按钮', () => {
  assert.deepEqual(getExecutionLabels('退货退款', 'approve'), {
    actionLabel: '同意退款',
    confirmActionLabel: '确认同意退款',
  });
  assert.deepEqual(getExecutionLabels('退货退款', 'reject'), {
    actionLabels: ['拒绝退款', '拒绝退货'],
    confirmActionLabels: ['确认拒绝退款', '确认拒绝退货'],
  });
});
