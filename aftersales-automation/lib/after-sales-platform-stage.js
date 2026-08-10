'use strict';

const PLATFORM_STAGE_SOURCE = 'after-sale-list';
const EXCHANGE_WAITING_MERCHANT_RESHIP = '商家-待商家二次发货';
const EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID = 'exchange_waiting_merchant_reship';

function cleanRawStage(value) {
  const text = String(value == null ? '' : value).trim();
  return text || null;
}

function normalizeStageText(value) {
  return String(value == null ? '' : value).replace(/\s+/g, '');
}

function createPlatformStageObservation(raw, observedAt = new Date().toISOString()) {
  const cleaned = cleanRawStage(raw);
  return {
    raw: cleaned,
    observedAt,
    source: PLATFORM_STAGE_SOURCE,
    readState: cleaned ? 'read' : 'missing',
  };
}

function getTicketPlatformStage(ticket, observedAt) {
  const existing = ticket && ticket.platformStage;
  if (existing && existing.source === PLATFORM_STAGE_SOURCE && existing.readState) {
    return {
      raw: cleanRawStage(existing.raw),
      observedAt: existing.observedAt || observedAt || new Date().toISOString(),
      source: PLATFORM_STAGE_SOURCE,
      readState: cleanRawStage(existing.raw) ? 'read' : 'missing',
    };
  }
  return createPlatformStageObservation(ticket && ticket.status, observedAt);
}

function classifyPlatformStage({ type, platformStage }) {
  if (type !== '换货') return null;
  if (normalizeStageText(platformStage && platformStage.raw) !== normalizeStageText(EXCHANGE_WAITING_MERCHANT_RESHIP)) {
    return null;
  }
  return {
    caseId: EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
    stage: EXCHANGE_WAITING_MERCHANT_RESHIP,
    meaning: '换货判断已完成，等待发货端二次发货',
    rollout: 'manual_observation',
  };
}

function summarizeBaselineDecision(decision) {
  if (!decision) return null;
  return {
    action: decision.action || null,
    reason: decision.reason || '',
    confidence: decision.confidence || null,
    manualReviewKind: decision.manualReviewKind || null,
  };
}

function applyPlatformStageObservation({ type, platformStage, baselineDecision }) {
  const classification = classifyPlatformStage({ type, platformStage });
  if (!classification) {
    return { decision: baselineDecision, assessment: null };
  }

  const reason = `【换货｜无需处理】平台当前为「${classification.stage}」，本工单已完成售后判断，正在等待发货端处理。试运行期间请人工确认后手动归档。`;
  return {
    decision: {
      action: 'skip',
      recommendedActionLabel: '无需处理',
      reason,
      confidence: 'high',
      requiresHumanReview: true,
      autoExecutionBlocked: true,
      humanTriggeredExecutionAllowed: false,
      manualArchiveOnly: true,
      platformStageCaseId: classification.caseId,
      rulesApplied: [{
        doc: 'flow-5.4',
        section: 'Step 7',
        summary: '待商家二次发货（观察期）→无需平台操作，人工确认后归档',
      }],
      warnings: ['观察期内不自动归档、不执行平台按钮，请人工确认后手动归档'],
      steps: [
        { type: 'read', label: '平台阶段', value: classification.stage },
        { type: 'branch', text: '换货判断已完成，等待发货端二次发货 → 无需平台操作' },
        { type: 'check', condition: '观察期人工确认', result: '确认后手动归档' },
      ],
    },
    assessment: {
      caseId: classification.caseId,
      rollout: classification.rollout,
      meaning: classification.meaning,
      baselineDecision: summarizeBaselineDecision(baselineDecision),
    },
  };
}

module.exports = {
  PLATFORM_STAGE_SOURCE,
  EXCHANGE_WAITING_MERCHANT_RESHIP,
  EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
  createPlatformStageObservation,
  getTicketPlatformStage,
  classifyPlatformStage,
  applyPlatformStageObservation,
};
