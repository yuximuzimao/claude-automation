'use strict';

const crypto = require('crypto');
const { proveReturnItems } = require('../return-item-proof');

const ENABLED_AUTOMATION_CASES = new Set([
  'refund_return.received.exact.approve\u0000七天无理由退货（不喜欢/不合适）',
  'refund_only.unshipped.approve\u0000多拍/拍错/不想要',
]);

const BRANCHES = Object.freeze({
  'refund_return.received.exact.approve': {
    label: '退货退款 / 已入库 / 精确退回 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_return.received.excess.approve': {
    label: '退货退款 / 已入库 / 真实多退 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_return.received.short.manual': {
    label: '退货退款 / 已入库 / 少退或缺失 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.received.damaged.manual': {
    label: '退货退款 / 已入库 / 含次品 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.received.damaged_and_short.manual': {
    label: '退货退款 / 已入库 / 次品且少退 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.received.incomplete.manual': {
    label: '退货退款 / 已入库 / 严格规格证明不完整 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.received.unmatched.manual': {
    label: '退货退款 / 已入库 / 未匹配商品 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.archive_missing.manual': {
    label: '退货退款 / 商品档案缺失 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.not_received.wait': {
    label: '退货退款 / 仓库未确认收货 / 时效充足 / 等待重查',
    automationStatus: 'manual_only',
  },
  'refund_return.not_received.timeout_reject': {
    label: '退货退款 / 仓库未确认收货 / 时效不足 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.shared.exact.approve': {
    label: '退货退款 / 不同子订单共用退货单 / 精确退回 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_return.shared.excess.approve': {
    label: '退货退款 / 不同子订单共用退货单 / 真实多退 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_return.shared.damaged.manual': {
    label: '退货退款 / 共用退货单 / 含次品 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.shared.short.manual': {
    label: '退货退款 / 共用退货单 / 少退 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.product_match_missing.manual': {
    label: '退货退款 / 商品对应表无法精确匹配 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_return.no_tracking.overdue.reject': {
    label: '退货退款 / 无退货单号 / 超售后期 / 拒绝',
    automationStatus: 'manual_only',
  },
  'refund_return.no_tracking.special.manual': {
    label: '退货退款 / 七天无理由无退货单号 / 特殊退货人工查询',
    automationStatus: 'manual_only',
  },
  'refund_only.unshipped.approve': {
    label: '仅退款 / 主品与赠品均未发货 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_only.safe_tracking.approve': {
    label: '仅退款 / 所有运单均未揽收或已退回 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_only.returned.approve': {
    label: '仅退款 / 所有包裹已退回 / 同意退款',
    automationStatus: 'candidate',
  },
  'refund_only.transit_or_station.wait': {
    label: '仅退款 / 在途或驿站 / 时效充足 / 拦截并等待重查',
    automationStatus: 'manual_only',
  },
  'refund_only.transit_or_station.timeout_reject': {
    label: '仅退款 / 在途或驿站 / 时效不足 / 拒绝并拦截',
    automationStatus: 'manual_only',
  },
  'refund_only.station_legacy_reject': {
    label: '仅退款 / 驿站 / 历史旧规则直接拒绝',
    automationStatus: 'manual_only',
  },
  'refund_only.signed.reject': {
    label: '仅退款 / 已签收且无在途件 / 拒绝并提示退货退款',
    automationStatus: 'manual_only',
  },
  'refund_only.main_returned_gift_not_returned.manual': {
    label: '仅退款 / 主品已退回但赠品未退回 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_only.erp_transit.wait': {
    label: '仅退款 / 鲸灵无物流且 ERP 在途 / 等待重查',
    automationStatus: 'manual_only',
  },
  'refund_only.gift_transit.wait': {
    label: '仅退款 / 主品未发货且赠品在途 / 等待重查',
    automationStatus: 'manual_only',
  },
  'refund_only.gift_shipped_no_tracking.manual': {
    label: '仅退款 / 赠品已发货但无运单 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_only.gift_signed_or_station.manual': {
    label: '仅退款 / 赠品已签收或在驿站 / 人工处理',
    automationStatus: 'manual_only',
  },
  'refund_only.mixed_signed_and_interceptable.manual': {
    label: '仅退款 / 部分签收且部分可拦截 / 人工处理',
    automationStatus: 'manual_only',
  },
  'global.merchant_fault.manual': {
    label: '商责售后原因 / 人工处理',
    automationStatus: 'manual_only',
  },
  'global.cancelled.wait_archive': {
    label: '客户取消或取消中 / 等待归档',
    automationStatus: 'manual_only',
  },
  'global.terminal.skip': {
    label: '平台已退款或已关闭 / 无操作归档',
    automationStatus: 'manual_only',
  },
  'global.gone.skip': {
    label: '非扫描来源工单不可访问 / 无操作归档',
    automationStatus: 'manual_only',
  },
  'global.gone_scan.manual': {
    label: '扫描来源详情不可确认 / 保留复查',
    automationStatus: 'manual_only',
  },
  'global.exchange.manual': {
    label: '换货 / 人工处理',
    automationStatus: 'manual_only',
  },
  'exchange.return.exact.manual_approve': {
    label: '换货 / 有退货单号 / 精确退回 / 推荐人工同意换货',
    automationStatus: 'manual_only',
  },
  'exchange.return.review.manual': {
    label: '换货 / 有退货单号 / 退回核验异常 / 人工确认',
    automationStatus: 'manual_only',
  },
  'exchange.no_tracking.manual': {
    label: '换货 / 无退货单号 / 人工处理',
    automationStatus: 'manual_only',
  },
  'merchant_fault.refund_return.exact.manual_approve': {
    label: '商责退货退款 / 有退货单号 / 精确退回 / 推荐人工同意退款',
    automationStatus: 'manual_only',
  },
  'merchant_fault.refund_return.review.manual': {
    label: '商责退货退款 / 退回核验异常或无单号 / 人工确认',
    automationStatus: 'manual_only',
  },
  'merchant_fault.exchange.exact.manual_approve': {
    label: '商责换货 / 有退货单号 / 精确退回 / 推荐人工同意换货',
    automationStatus: 'manual_only',
  },
  'merchant_fault.exchange.review.manual': {
    label: '商责换货 / 退回核验异常或无单号 / 人工确认',
    automationStatus: 'manual_only',
  },
  'global.order_type_missing.manual': {
    label: '历史数据缺少工单类型 / 人工处理',
    automationStatus: 'manual_only',
  },
});

const RULE_BRANCHES = Object.freeze({
  '主商品+赠品未发货→同意退款': 'refund_only.unshipped.approve',
  '全部ERP行逐行核验通过→同意退款': 'refund_only.safe_tracking.approve',
  '所有包裹已退回→同意退款': 'refund_only.returned.approve',
  'ERP双源核查→已退回→同意退款': 'refund_only.returned.approve',
  '商责原因→上报人工': 'global.merchant_fault.manual',
  '取消状态→等待归档+提醒取消拦截': 'global.cancelled.wait_archive',
  '工单不可访问→自动归档': 'global.gone.skip',
  '扫描工单详情页未确认→保留待复查': 'global.gone_scan.manual',
  '换货→上报人工': 'global.exchange.manual',
  '换货退回核验通过→推荐人工同意换货': 'exchange.return.exact.manual_approve',
  '换货退回核验异常→人工确认': 'exchange.return.review.manual',
  '换货无退货单号→人工处理': 'exchange.no_tracking.manual',
  '商责退货退款核验通过→推荐人工同意退款': 'merchant_fault.refund_return.exact.manual_approve',
  '商责退货退款退回核验异常→人工确认': 'merchant_fault.refund_return.review.manual',
  '商责退货退款无退货单号→人工处理': 'merchant_fault.refund_return.review.manual',
  '商责换货退回核验通过→推荐人工同意换货': 'merchant_fault.exchange.exact.manual_approve',
  '商责换货退回核验异常→人工确认': 'merchant_fault.exchange.review.manual',
  '商责换货无退货单号→人工处理': 'merchant_fault.exchange.review.manual',
  '有记录未入库+剩余>12h→等待重查': 'refund_return.not_received.wait',
  '未入库+剩余>12h→等待重查': 'refund_return.not_received.wait',
  '有记录未入库+剩余≤12h→拒绝': 'refund_return.not_received.timeout_reject',
  '未入库+剩余≤12h→拒绝': 'refund_return.not_received.timeout_reject',
  '在途/驿站拦截件+剩余-扫描>8h→自动等待重查': 'refund_only.transit_or_station.wait',
  '在途拦截件+剩余-扫描>8h→自动等待重查': 'refund_only.transit_or_station.wait',
  '在途/驿站拦截件+剩余-扫描≤8h→拒绝+创建拦截提醒': 'refund_only.transit_or_station.timeout_reject',
  '在途拦截件+剩余-扫描≤8h→拒绝+创建拦截提醒': 'refund_only.transit_or_station.timeout_reject',
  '驿站待取件→拒绝+创建拦截提醒': 'refund_only.station_legacy_reject',
  '已签收→拒绝，让改退货退款': 'refund_only.signed.reject',
  '主品退回但赠品未退回→上报人工': 'refund_only.main_returned_gift_not_returned.manual',
  'ERP在途→等待重查': 'refund_only.erp_transit.wait',
  '赠品在途→等待重查': 'refund_only.gift_transit.wait',
  '赠品已发货无单号→上报人工': 'refund_only.gift_shipped_no_tracking.manual',
  '赠品已签收/驿站→上报人工': 'refund_only.gift_signed_or_station.manual',
  '部分签收+部分可拦截→拦截未签收件+签收件走退货退款': 'refund_only.mixed_signed_and_interceptable.manual',
  '对应表缺规格→上报': 'refund_return.received.unmatched.manual',
  '无档案→上报人工（安全优先）': 'refund_return.archive_missing.manual',
  '全部子订单 attr1 mismatch → 上报': 'refund_return.product_match_missing.manual',
  '共用退货单含次品→上报人工': 'refund_return.shared.damaged.manual',
  '共用退货单逐规格不足→上报人工': 'refund_return.shared.short.manual',
  '超售后期无理由退货→拒绝': 'refund_return.no_tracking.overdue.reject',
});

const REGISTERED_RULE_SUMMARIES = new Set([
  ...Object.keys(RULE_BRANCHES),
  '逐商品对比通过→同意退款',
  '不同子订单共用退货单，合并逐规格核对通过→同意退款',
  '退货异常→上报人工',
]);

function stableToken(value) {
  return crypto.createHash('sha1').update(String(value || '')).digest('hex').slice(0, 10);
}

function hasExcess(decision) {
  const text = [decision.reason, ...(decision.warnings || [])].filter(Boolean).join('；');
  return /多退|多\d+件|比期望多/.test(text);
}

function classifyRule(decision, collectedData) {
  const summaries = (decision.rulesApplied || []).map(rule => rule && rule.summary).filter(Boolean);

  if (summaries.includes('逐商品对比通过→同意退款')) {
    const proof = proveReturnItems(collectedData);
    const proofBranches = {
      exact: 'refund_return.received.exact.approve',
      excess: 'refund_return.received.excess.approve',
      short: 'refund_return.received.short.manual',
      damaged: 'refund_return.received.damaged.manual',
      unmatched: 'refund_return.received.unmatched.manual',
      incomplete: 'refund_return.received.incomplete.manual',
    };
    return { branchId: proofBranches[proof.outcome] || 'refund_return.received.incomplete.manual', proof };
  }

  if (summaries.includes('不同子订单共用退货单，合并逐规格核对通过→同意退款')) {
    return { branchId: hasExcess(decision)
      ? 'refund_return.shared.excess.approve'
      : 'refund_return.shared.exact.approve' };
  }

  if (summaries.includes('退货异常→上报人工')) {
    const reason = String(decision.reason || '');
    const damaged = reason.includes('次品');
    const short = /不足|退货里没有|缺失/.test(reason);
    if (damaged && short) return { branchId: 'refund_return.received.damaged_and_short.manual' };
    if (damaged) return { branchId: 'refund_return.received.damaged.manual' };
    if (short) return { branchId: 'refund_return.received.short.manual' };
    return null;
  }

  for (const summary of summaries) {
    if (RULE_BRANCHES[summary]) return { branchId: RULE_BRANCHES[summary] };
  }
  return null;
}

function classifySimulation(simulation, queueItem = {}) {
  const decision = simulation && simulation.decision;
  const ticket = simulation?.collectedData?.ticket || {};
  const reason = ticket.afterSaleReason;
  const orderType = queueItem.type || simulation?.collectedData?.ticket?.type || simulation?.orderType;
  const specialNoTracking = decision?.action === 'escalate'
    && orderType === '退货退款'
    && !String(ticket.returnTracking || '').trim()
    && String(reason || '').includes('七天无理由退货')
    && String(decision.reason || '').includes('可能为超期特殊退货或次品特殊处理');
  const terminalSkip = decision?.action === 'skip'
    && /^工单状态：/.test(String(decision.reason || ''));
  const manualReviewBranches = {
    exchange_return_exact: 'exchange.return.exact.manual_approve',
    exchange_return_review: 'exchange.return.review.manual',
    exchange_no_tracking: 'exchange.no_tracking.manual',
    merchant_refund_return_exact: 'merchant_fault.refund_return.exact.manual_approve',
    merchant_refund_return_review: 'merchant_fault.refund_return.review.manual',
    merchant_refund_return_no_tracking: 'merchant_fault.refund_return.review.manual',
    merchant_exchange_return_exact: 'merchant_fault.exchange.exact.manual_approve',
    merchant_exchange_return_review: 'merchant_fault.exchange.review.manual',
    merchant_exchange_no_tracking: 'merchant_fault.exchange.review.manual',
  };
  const manualReviewBranchId = (decision?.requiresHumanReview || decision?.manualOnly)
    ? manualReviewBranches[decision.manualReviewKind]
    : null;
  let ruleClassification = null;
  if (manualReviewBranchId) {
    ruleClassification = { branchId: manualReviewBranchId };
  } else if (specialNoTracking) {
    ruleClassification = { branchId: 'refund_return.no_tracking.special.manual' };
  } else if (terminalSkip) {
    ruleClassification = { branchId: 'global.terminal.skip' };
  } else if (decision) {
    ruleClassification = classifyRule(decision, simulation?.collectedData);
  }
  const branchId = ruleClassification && ruleClassification.branchId;
  const missingFacts = [];
  if (!reason) missingFacts.push('售后原因');
  if (!orderType) missingFacts.push('工单类型');
  if (!decision) missingFacts.push('最终决定');
  if (decision && !branchId) missingFacts.push('已登记的最终规则结果');

  if (reason && !orderType && decision && branchId) {
    const incompleteBranch = BRANCHES['global.order_type_missing.manual'];
    return {
      registered: true,
      caseId: `global.order_type_missing.manual.${stableToken(reason)}`,
      branchId: 'global.order_type_missing.manual',
      branchLabel: incompleteBranch.label,
      afterSaleReason: reason,
      orderType: '类型缺失',
      expectedAction: decision.action,
      automationStatus: incompleteBranch.automationStatus,
      missingFacts: ['工单类型'],
    };
  }

  if (!branchId || !BRANCHES[branchId] || missingFacts.length > 0) {
    const signature = [reason, orderType, decision?.action, ...(decision?.rulesApplied || []).map(rule => rule?.summary)].join('|');
    return {
      registered: false,
      caseId: `unregistered.${stableToken(signature)}`,
      branchId: 'unregistered',
      branchLabel: '未登记分支',
      afterSaleReason: reason || '原因缺失',
      orderType: orderType || '类型缺失',
      expectedAction: decision?.action || 'unknown',
      automationStatus: 'manual_only',
      missingFacts,
    };
  }

  const branch = BRANCHES[branchId];
  const enabled = ENABLED_AUTOMATION_CASES.has(`${branchId}\u0000${String(reason)}`);
  return {
    registered: true,
    caseId: `${branchId}.${stableToken(reason)}`,
    branchId,
    branchLabel: branch.label,
    afterSaleReason: reason,
    orderType,
    expectedAction: decision.action,
    automationStatus: enabled ? 'enabled' : branch.automationStatus,
    missingFacts: ruleClassification?.proof?.missingFacts || [],
  };
}

function redactNote(value) {
  const text = String(value == null ? '' : value).trim();
  if (!text) return '真正空值';
  if (text === '无') return '字面“无”';
  if (/病|过敏|怀孕|孕妇|住院|手术|药物|健康/.test(text)) return '含个人健康信息，已脱敏';
  return text
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, '[手机号]')
    .replace(/\d{8,}/g, '[编号]');
}

function latestByWorkOrder(simulations) {
  const latest = new Map();
  for (const simulation of simulations) {
    const key = String(simulation.workOrderNum || simulation.queueItemId || simulation.id || '');
    const previous = latest.get(key);
    if (!previous || String(previous.createdAt || '') <= String(simulation.createdAt || '')) {
      latest.set(key, simulation);
    }
  }
  return [...latest.values()];
}

function summarizeHistory({
  simulations = [],
  feedbacks = [],
  queueItems = [],
  archivedCases = [],
  journal = {},
  now = new Date(),
  days = 30,
} = {}) {
  const nowMs = new Date(now).getTime();
  const cutoffMs = nowMs - days * 24 * 60 * 60 * 1000;
  const recent = simulations.filter(simulation => {
    const createdAt = Date.parse(simulation.createdAt || '');
    return Number.isFinite(createdAt) && createdAt >= cutoffMs && createdAt <= nowMs;
  });
  const queueById = new Map(queueItems.map(item => [item.id, item]));
  const queueByWorkOrder = new Map(queueItems
    .filter(item => item.workOrderNum)
    .map(item => [String(item.workOrderNum), item]));
  const caseByWorkOrder = new Map();
  for (const item of archivedCases) {
    if (!item.workOrderNum) continue;
    const key = String(item.workOrderNum);
    const previous = caseByWorkOrder.get(key);
    if (!previous || String(previous.addedAt || '') <= String(item.addedAt || '')) {
      caseByWorkOrder.set(key, item);
    }
  }
  const resolveQueueItem = simulation => queueById.get(simulation.queueItemId)
    || queueByWorkOrder.get(String(simulation.workOrderNum || ''))
    || caseByWorkOrder.get(String(simulation.workOrderNum || ''))
    || {};
  const isHinted = simulation => Boolean(simulation?.decision?.hinted || resolveQueueItem(simulation).hint);
  const latest = latestByWorkOrder(recent).filter(simulation => !isHinted(simulation));
  const recentById = new Map(recent.map(simulation => [simulation.id, simulation]));
  const recentByWorkOrder = new Map();
  for (const simulation of recent) {
    const key = String(simulation.workOrderNum || simulation.queueItemId || simulation.id || '');
    if (!recentByWorkOrder.has(key)) recentByWorkOrder.set(key, []);
    recentByWorkOrder.get(key).push(simulation);
  }
  for (const items of recentByWorkOrder.values()) {
    items.sort((a, b) => String(a.createdAt || '').localeCompare(String(b.createdAt || '')));
  }
  const journalCaseByWorkOrder = new Map();
  for (const [workOrderKey, record] of Object.entries(journal || {})) {
    const succeededAt = Date.parse(record?.pageActionSucceededAt || '');
    if (!Number.isFinite(succeededAt)) continue;
    const sourceSimulation = (recentByWorkOrder.get(String(workOrderKey)) || [])
      .map(simulation => ({
        simulation,
        distanceMs: Math.abs(Date.parse(simulation.createdAt || '') - succeededAt),
      }))
      .filter(item => Number.isFinite(item.distanceMs) && item.distanceMs <= 5 * 60 * 1000)
      .sort((a, b) => a.distanceMs - b.distanceMs)[0]?.simulation;
    if (!sourceSimulation || sourceSimulation.decision?.hinted) continue;
    journalCaseByWorkOrder.set(
      String(workOrderKey),
      classifySimulation(sourceSimulation, resolveQueueItem(sourceSimulation)).caseId,
    );
  }
  const feedbackByWorkOrderAndCase = new Map();
  for (const feedback of feedbacks) {
    const simulation = recentById.get(feedback.simulationId);
    if (!simulation || isHinted(simulation)) continue;
    const classification = classifySimulation(simulation, resolveQueueItem(simulation));
    const workOrderKey = String(simulation.workOrderNum || simulation.queueItemId || simulation.id || '');
    const key = `${workOrderKey}\u0000${classification.caseId}`;
    const previous = feedbackByWorkOrderAndCase.get(key);
    if (!previous || String(previous.createdAt || '') <= String(feedback.createdAt || '')) {
      feedbackByWorkOrderAndCase.set(key, feedback);
    }
  }
  const groups = new Map();

  for (const simulation of latest) {
    const queueItem = resolveQueueItem(simulation);
    const classification = classifySimulation(simulation, queueItem);
    if (!groups.has(classification.caseId)) {
      groups.set(classification.caseId, {
        ...classification,
        occurrenceCount: 0,
        positiveCount: 0,
        negativeCount: 0,
        autoSuccessCount: 0,
        manualHandledCount: 0,
        noteCounts: new Map(),
      });
    }
    const group = groups.get(classification.caseId);
    group.occurrenceCount += 1;

    const workOrderKey = String(simulation.workOrderNum || simulation.queueItemId || simulation.id || '');
    const feedback = feedbackByWorkOrderAndCase.get(`${workOrderKey}\u0000${classification.caseId}`);
    if (feedback?.verdict === 'positive') group.positiveCount += 1;
    if (feedback?.verdict === 'negative') group.negativeCount += 1;

    if (journalCaseByWorkOrder.get(String(simulation.workOrderNum || '')) === classification.caseId) {
      group.autoSuccessCount += 1;
    }
    const archivedSource = caseByWorkOrder.get(String(simulation.workOrderNum || ''))?.groundTruth?.source;
    const archivedAsManual = ['manual_handled', 'executed', 'batch_executed'].includes(archivedSource);
    if ((simulation.executedAt && !simulation.autoExecutedAt) || archivedAsManual) group.manualHandledCount += 1;

    const note = redactNote(simulation.collectedData?.ticket?.buyerRemark);
    group.noteCounts.set(note, (group.noteCounts.get(note) || 0) + 1);
  }

  const cases = [...groups.values()].map(group => {
    const notes = [...group.noteCounts.entries()]
      .map(([value, count]) => ({ value, count }))
      .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'zh-CN'));
    const { noteCounts, ...result } = group;
    return { ...result, notes };
  }).sort((a, b) => b.occurrenceCount - a.occurrenceCount || a.caseId.localeCompare(b.caseId));

  return {
    generatedAt: new Date(nowMs).toISOString(),
    cutoffAt: new Date(cutoffMs).toISOString(),
    totalSimulations: recent.length,
    uniqueWorkOrders: latest.length,
    unregisteredCount: cases.filter(item => !item.registered).reduce((sum, item) => sum + item.occurrenceCount, 0),
    cases,
  };
}

module.exports = {
  BRANCHES,
  ENABLED_AUTOMATION_CASES,
  REGISTERED_RULE_SUMMARIES,
  classifySimulation,
  redactNote,
  summarizeHistory,
};
