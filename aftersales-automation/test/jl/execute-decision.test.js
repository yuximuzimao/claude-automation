'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { getExecutionLabels, resolveRejectCopy } = require('../../lib/jl/execute-decision');

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

test('拦截件执行时使用独立拒绝文案，不把含单号的推理结果写入平台', () => {
  const copy = resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'INTERCEPT_WAITING',
      reason: 'YT123456789在途未退回，剩余20小时，当前等待重查',
      rejectReason: '包裹未退回',
      rejectDetail: '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
    },
    rejectReason: '其他',
    rejectDetail: 'YT123456789仍在途',
  });

  assert.deepEqual(copy, {
    reason: '包裹未退回',
    detail: '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
  });
  assert.doesNotMatch(copy.detail, /YT123456789/);
});

test('拦截件缺少独立拒绝文案时禁止用推理结果兜底', () => {
  assert.throws(() => resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'INTERCEPT_TIMEOUT',
      reason: 'YT123456789在途未退回，时效不足',
    },
  }), /禁止使用推理结果兜底/);
});
