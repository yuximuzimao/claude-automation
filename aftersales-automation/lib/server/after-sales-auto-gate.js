'use strict';

const { classifySimulation } = require('./after-sales-branch-history');
const { evaluateRefundOnlyTrackings } = require('../infer');

const AUTO_EXECUTABLE_BRANCHES = new Set([
  'refund_return.received.exact.approve',
  'refund_only.unshipped.approve',
  'refund_only.safe_tracking.approve',
]);

const UNSHIPPED_STATUSES = new Set(['待审核', '待打印快递单', '待发货']);

function rowTrackings(row) {
  return [...new Set([
    ...(Array.isArray(row?.trackings) ? row.trackings : []),
    row?.tracking,
  ].filter(Boolean).map(String))];
}

function validateOrderSearches(orders, searches, validateRow = () => true) {
  const orderIds = (orders || []).map(order => String(order?.id || '')).filter(Boolean);
  if (orderIds.length !== (orders || []).length) return false;
  if (new Set(orderIds).size !== orderIds.length) return false;
  if (!Array.isArray(searches) || searches.length !== orderIds.length) return false;

  return orderIds.every(orderId => {
    const matches = searches.filter(search => String(search?.subOrderId || '') === orderId);
    if (matches.length !== 1) return false;
    const rows = matches[0]?.rows?.rows;
    if (!Array.isArray(rows) || rows.length === 0) return false;
    return rows.every(row => {
      const platformOrderIds = Array.isArray(row?.platformOrderIds)
        ? row.platformOrderIds.map(String)
        : [];
      return platformOrderIds.includes(orderId) && validateRow(row);
    });
  });
}

function packageHasTracking(pkg) {
  return /物流单号[：:]\s*\n?([A-Za-z0-9-]+)/.test(String(pkg?.text || ''));
}

function proveRefundOnlyUnshipped(collectedData) {
  const ticket = collectedData?.ticket;
  if (!ticket || String(ticket.returnTracking || '').trim()) return false;

  const allowedCollectErrors = [
    /^product-detail: 跳过（工单类型=仅退款，/,
    /^erp-aftersale: 无退货快递单号，跳过$/,
  ];
  const collectErrors = Array.isArray(collectedData.collectErrors) ? collectedData.collectErrors : [];
  if (collectErrors.some(error => !allowedCollectErrors.some(pattern => pattern.test(String(error))))) {
    return false;
  }

  const unshippedRow = row => UNSHIPPED_STATUSES.has(row?.status) && rowTrackings(row).length === 0;
  if (!validateOrderSearches(ticket.subOrders, collectedData.erpSearches, unshippedRow)) return false;
  if (!validateOrderSearches(ticket.gifts || [], collectedData.giftErpSearches || [], unshippedRow)) return false;
  if ((collectedData.logistics?.packages || []).some(packageHasTracking)) return false;
  if ((collectedData.erpLogistics?.results || []).some(result => rowTrackings(result).length > 0)) return false;
  return true;
}

function proveRefundOnlySafeTracking(collectedData) {
  const ticket = collectedData?.ticket;
  if (!ticket || String(ticket.returnTracking || '').trim()) return false;

  const allowedCollectErrors = [
    /^product-detail: 跳过（工单类型=仅退款，/,
    /^erp-aftersale: 无退货快递单号，跳过$/,
  ];
  const collectErrors = Array.isArray(collectedData.collectErrors) ? collectedData.collectErrors : [];
  if (collectErrors.some(error => !allowedCollectErrors.some(pattern => pattern.test(String(error))))) {
    return false;
  }

  if (!validateOrderSearches(ticket.subOrders, collectedData.erpSearches)) return false;
  if (!validateOrderSearches(ticket.gifts || [], collectedData.giftErpSearches || [])) return false;

  const searches = [
    ...(collectedData.erpSearches || []),
    ...(collectedData.giftErpSearches || []),
  ];
  const rows = searches.flatMap(search => search?.rows?.rows || []);
  if (!rows.length) return false;
  if (rows.some(row => rowTrackings(row).length === 0 && !UNSHIPPED_STATUSES.has(row?.status))) {
    return false;
  }

  const evaluation = evaluateRefundOnlyTrackings(collectedData, rows);
  if (!evaluation.trackings.length || evaluation.missingFromErpRows.length) return false;
  const knownTrackings = new Set(evaluation.trackings.map(String));
  const erpResults = Array.isArray(collectedData.erpLogistics?.results)
    ? collectedData.erpLogistics.results
    : [];
  if (erpResults.some(result => result?.tracking && !knownTrackings.has(String(result.tracking)))) {
    return false;
  }
  return evaluation.outcomes.length === evaluation.trackings.length
    && evaluation.outcomes.every(item => ['returned', 'not_picked_up'].includes(item.outcome));
}

function shouldAutoExecute(decision, collectedData, queueItem) {
  if (!decision || decision.action !== 'approve') return false;
  // manualOnly 兼容修改前已落库的模拟记录；新决策使用语义更准确的两个字段。
  if (decision.manualOnly || decision.requiresHumanReview || decision.autoExecutionBlocked) return false;
  if (!collectedData || !queueItem || !['退货退款', '仅退款'].includes(queueItem.type)) return false;
  if (decision.hinted || queueItem.hint) return false;

  const classification = classifySimulation({ collectedData, decision }, queueItem);
  if (!classification.registered
    || !AUTO_EXECUTABLE_BRANCHES.has(classification.branchId)
    || classification.automationStatus !== 'enabled'
    || classification.missingFacts.length !== 0) {
    return false;
  }

  if (classification.branchId.startsWith('refund_return.') && queueItem.type !== '退货退款') {
    return false;
  }
  if (classification.branchId.startsWith('refund_only.') && queueItem.type !== '仅退款') {
    return false;
  }
  if (classification.branchId === 'refund_only.unshipped.approve') {
    return proveRefundOnlyUnshipped(collectedData);
  }
  if (classification.branchId === 'refund_only.safe_tracking.approve') {
    return proveRefundOnlySafeTracking(collectedData);
  }
  return true;
}

module.exports = { proveRefundOnlySafeTracking, proveRefundOnlyUnshipped, shouldAutoExecute };
