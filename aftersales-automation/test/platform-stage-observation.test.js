'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  EXCHANGE_WAITING_MERCHANT_RESHIP_CASE_ID,
  createPlatformStageObservation,
  classifyPlatformStage,
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

test('观察期分支保留原综合推理作对照并转为无需处理人工归档', () => {
  const baselineDecision = { action: 'approve', reason: '原综合推理建议同意换货', confidence: 'high' };
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
