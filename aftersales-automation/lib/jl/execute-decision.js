'use strict';

const { approveTicket } = require('./approve');
const { rejectTicket } = require('./reject');

function getExecutionLabels(type, action) {
  const isExchange = type === '换货';
  if (action === 'approve') {
    return isExchange
      ? { actionLabel: '同意换货', confirmActionLabel: '确认同意换货' }
      : { actionLabel: '同意退款', confirmActionLabel: '确认同意退款' };
  }
  if (action === 'reject') {
    return isExchange
      ? { actionLabels: ['拒绝换货'], confirmActionLabels: ['确认拒绝换货'] }
      : {
          actionLabels: ['拒绝退款', '拒绝退货'],
          confirmActionLabels: ['确认拒绝退款', '确认拒绝退货'],
        };
  }
  throw new Error(`不支持的平台执行动作: ${action || '空'}`);
}

function resolveRejectCopy({ decision, rejectReason, rejectDetail }) {
  const requiresSeparatedCopy = ['INTERCEPT_WAITING', 'INTERCEPT_TIMEOUT', 'MIXED_SIGNED_INTERCEPTABLE'].includes(decision.reasonCode);

  if (requiresSeparatedCopy) {
    if (!decision.rejectReason || !decision.rejectDetail) {
      throw new Error('拦截件拒绝缺少分支对应的拒绝原因或独立详细文案，禁止使用推理结果兜底');
    }
    return {
      reason: decision.rejectReason,
      detail: decision.rejectDetail,
    };
  }

  const reason = rejectReason || decision.rejectReason || decision.reason;
  return {
    reason,
    detail: rejectDetail || decision.rejectDetail || reason,
  };
}

async function executeTicketDecision({
  targetId,
  workOrderNum,
  type,
  decision,
  rejectReason,
  rejectDetail,
  rejectImageUrl,
  packageTab,
}) {
  if (!decision) throw new Error('缺少工单决策');
  if (decision.action === 'approve') {
    return approveTicket(
      targetId,
      workOrderNum,
      getExecutionLabels(type, 'approve'),
    );
  }
  if (decision.action === 'reject') {
    const rejectCopy = resolveRejectCopy({ decision, rejectReason, rejectDetail });
    return rejectTicket(
      targetId,
      workOrderNum,
      rejectCopy.reason,
      rejectCopy.detail,
      rejectImageUrl || decision.imageUrl || null,
      packageTab,
      getExecutionLabels(type, 'reject'),
    );
  }
  throw new Error(`不支持的平台执行动作: ${decision.action || '空'}`);
}

module.exports = { getExecutionLabels, resolveRejectCopy, executeTicketDecision };
