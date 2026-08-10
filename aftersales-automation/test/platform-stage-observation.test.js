'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
  createPlatformStageObservation,
  classifyPlatformStage,
  createConfirmedNoAction,
  resolveManualArchiveOutcome,
  matchesConfirmedNoAction,
  applyPlatformStageObservation,
} = require('../lib/after-sales-platform-stage');

test('平台阶段观察保留原始文案、时间、来源和缺失状态', () => {
  const read = createPlatformStageObservation(' 商家-待商家二次发货 ', '2026-08-10T00:00:00.000Z');
  assert.deepEqual(read, {
    raw: '商家-待商家二次发货',
    observedAt: '2026-08-10T00:00:00.000Z',
    source: 'after-sale-list',
    readState: 'read',
  });

  const missing = createPlatformStageObservation('', '2026-08-10T00:00:00.000Z');
  assert.equal(missing.raw, null);
  assert.equal(missing.readState, 'missing');
});

test('只有换货的待商家二次发货进入观察期状态分支', () => {
  const platformStage = createPlatformStageObservation('商家- 待商家二次发货');
  const matched = classifyPlatformStage({ type: '换货', platformStage });
  assert.equal(matched.caseId, EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID);
  assert.equal(matched.rollout, 'manual_observation');

  assert.equal(classifyPlatformStage({ type: '退货退款', platformStage }), null);
  assert.equal(classifyPlatformStage({
    type: '换货',
    platformStage: createPlatformStageObservation('商家-待商家处理'),
  }), null);
});

test('观察期分支完整复制原综合推理作对照并转为无需处理人工归档', () => {
  const baselineDecision = {
    action: 'approve',
    reason: '原综合推理建议同意换货',
    confidence: 'high',
    warnings: ['需要核对提前补发'],
    steps: [{ type: 'check', result: '通过' }],
    rulesApplied: [{ doc: 'flow-5.4', section: 'Step 6', summary: '完整原规则' }],
    autoExecutionBlocked: true,
  };
  const result = applyPlatformStageObservation({
    type: '换货',
    platformStage: createPlatformStageObservation('商家-待商家二次发货'),
    baselineDecision,
  });

  assert.equal(result.decision.action, 'skip');
  assert.equal(result.decision.recommendedActionLabel, '无需处理');
  assert.equal(result.decision.manualArchiveOnly, true);
  assert.equal(result.decision.humanTriggeredExecutionAllowed, false);
  assert.match(result.decision.reason, /无需处理/);
  assert.match(result.decision.reason, /手动归档/);
  assert.equal(result.assessment.baselineDecision.action, 'approve');
  assert.equal(result.assessment.baselineDecision.reason, baselineDecision.reason);
  assert.deepEqual(result.assessment.baselineDecision.warnings, baselineDecision.warnings);
  assert.deepEqual(result.assessment.baselineDecision.steps, baselineDecision.steps);
  assert.deepEqual(result.assessment.baselineDecision.rulesApplied, baselineDecision.rulesApplied);
  assert.equal(result.assessment.baselineDecision.autoExecutionBlocked, true);
  assert.notEqual(result.assessment.baselineDecision, baselineDecision);
});

test('只有唯一已登记阶段能生成确认无需处理记录和专用归档来源', () => {
  const platformStage = createPlatformStageObservation('商家-待商家二次发货');
  const { decision } = applyPlatformStageObservation({
    type: '换货',
    platformStage,
    baselineDecision: { action: 'approve' },
  });
  const archivedAt = '2026-08-10T04:00:00.000Z';
  const outcome = resolveManualArchiveOutcome({
    queueStatus: 'simulated',
    decision,
    platformStage,
    archivedAt,
  });

  assert.equal(outcome.source, 'confirmed_no_action');
  assert.deepEqual(outcome.confirmedNoAction, {
    caseId: EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
    stage: '商家-待商家二次发货',
    confirmedAt: archivedAt,
  });
  assert.equal(matchesConfirmedNoAction({
    type: '换货',
    platformStage: createPlatformStageObservation('商家- 待商家二次发货'),
    confirmedNoAction: outcome.confirmedNoAction,
  }), true);

  assert.equal(createConfirmedNoAction(decision, createPlatformStageObservation('商家-待商家处理')), null);
  assert.equal(resolveManualArchiveOutcome({
    queueStatus: 'simulated',
    decision: { ...decision, platformStageCaseId: 'unknown_case' },
    platformStage,
    archivedAt,
  }).source, 'manual_handled');
  assert.deepEqual(resolveManualArchiveOutcome({
    queueStatus: 'auto_executed',
    decision,
    platformStage,
    archivedAt,
  }), { confirmedNoAction: null, source: 'auto_executed' });
});

test('阶段或工单类型变化后确认记录失效，工单必须重新进入正常判断', () => {
  const confirmedNoAction = {
    caseId: EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
    stage: '商家-待商家二次发货',
    confirmedAt: '2026-08-10T04:00:00.000Z',
  };
  assert.equal(matchesConfirmedNoAction({
    type: '换货',
    platformStage: createPlatformStageObservation('商家-待商家处理'),
    confirmedNoAction,
  }), false);
  assert.equal(matchesConfirmedNoAction({
    type: '退货退款',
    platformStage: createPlatformStageObservation('商家-待商家二次发货'),
    confirmedNoAction,
  }), false);
});

test('其他平台阶段只观察，不覆盖原综合推理', () => {
  const baselineDecision = { action: 'reject', reason: '原综合推理' };
  const result = applyPlatformStageObservation({
    type: '换货',
    platformStage: createPlatformStageObservation('商家-待商家处理'),
    baselineDecision,
  });
  assert.equal(result.decision, baselineDecision);
  assert.equal(result.assessment, null);
});

test('来源或读取状态不可信时即使文案相同也不得命中', () => {
  const raw = '商家-待商家二次发货';
  assert.equal(classifyPlatformStage({
    type: '换货',
    platformStage: { raw, source: 'unknown', readState: 'read' },
  }), null);
  assert.equal(classifyPlatformStage({
    type: '换货',
    platformStage: { raw, source: 'after-sale-list', readState: 'missing' },
  }), null);
});
