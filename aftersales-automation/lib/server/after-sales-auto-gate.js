'use strict';

const { classifySimulation } = require('./after-sales-branch-history');

function shouldAutoExecute(decision, collectedData, queueItem) {
  if (!decision || decision.action !== 'approve') return false;
  // manualOnly 兼容修改前已落库的模拟记录；新决策使用语义更准确的两个字段。
  if (decision.manualOnly || decision.requiresHumanReview || decision.autoExecutionBlocked) return false;
  if (!collectedData || !queueItem || queueItem.type !== '退货退款') return false;
  if (decision.hinted || queueItem.hint) return false;

  const classification = classifySimulation({ collectedData, decision }, queueItem);
  return classification.registered
    && classification.branchId === 'refund_return.received.exact.approve'
    && classification.automationStatus === 'enabled'
    && classification.missingFacts.length === 0;
}

module.exports = { shouldAutoExecute };
