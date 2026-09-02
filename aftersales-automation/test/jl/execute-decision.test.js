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

test('拦截件执行使用分支对应原因，拒绝外部参数覆盖', () => {
  const copy = resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'INTERCEPT_WAITING',
      reason: 'YT123456789在途未退回，剩余20小时，当前等待重查',
      rejectReason: '已通知快递拦截暂未退回',
      rejectDetail: '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
    },
    rejectReason: '其他',
    rejectDetail: 'YT123456789仍在途',
  });

  assert.deepEqual(copy, {
    reason: '已通知快递拦截暂未退回',
    detail: '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
  });
  assert.doesNotMatch(copy.detail, /YT123456789/);
});

test('驿站拦截件保留驿站专属拒绝原因', () => {
  const copy = resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'INTERCEPT_TIMEOUT',
      reason: '驿站待取件，时效不足',
      rejectReason: '已到驿站待取件',
      rejectDetail: '订单已发出，已通知快递拦截暂未退回，等快递退返回我司后再退款',
    },
  });

  assert.equal(copy.reason, '已到驿站待取件');
});

test('混合签收分支使用独立拒绝原因和含单号详细文案', () => {
  const copy = resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'MIXED_SIGNED_INTERCEPTABLE',
      reason: '一个包裹已签收，另一个仍在途',
      rejectReason: '商品已签收，无法拦截，请自行申请退货退款',
      rejectDetail: '快递单号SIGNED1已签收，无法拦截。快递单号TRANSIT1已反馈快递拦截。',
    },
    rejectReason: '其他',
    rejectDetail: '外部覆盖文案',
  });

  assert.deepEqual(copy, {
    reason: '商品已签收，无法拦截，请自行申请退货退款',
    detail: '快递单号SIGNED1已签收，无法拦截。快递单号TRANSIT1已反馈快递拦截。',
  });
});

test('拦截件缺少分支拒绝原因或独立文案时禁止兜底', () => {
  assert.throws(() => resolveRejectCopy({
    decision: {
      action: 'reject',
      reasonCode: 'INTERCEPT_TIMEOUT',
      reason: 'YT123456789在途未退回，时效不足',
    },
  }), /禁止使用推理结果兜底/);
});
