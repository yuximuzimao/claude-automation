'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { inferDecision } = require('../../lib/infer');
const { shouldAutoExecute } = require('../../lib/server/after-sales-auto-gate');
const { isBatchExecutable } = require('../../lib/constants');
const { classifySimulation } = require('../../lib/server/after-sales-branch-history');

function exactCollectedData(afterSaleReason = '无理由售后（不喜欢不合适）') {
  return {
    ticket: {
      afterSaleReason,
      returnTracking: 'RETURN-EXCHANGE-1',
      subOrders: [{ id: 'main-1', afterSaleNum: 1 }],
      gifts: [],
    },
    erpSearch: { rows: { rows: [{ status: '卖家已发货' }] } },
    productArchives: [{
      subOrderId: 'main-1',
      subItems: [{ name: '悦颜精粹水', specCode: 'SPEC-A', qty: 1 }],
    }],
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-AFTERSALE-1',
        tracking: 'RETURN-EXCHANGE-1',
        goodsStatus: '卖家已收到退货',
        returnQty: 1,
        items: [{ name: '悦颜精粹水', specCode: 'SPEC-A', qtyGood: 1, qtyBad: 0 }],
      }],
    },
    collectErrors: [],
  };
}

function infer(type, collectedData) {
  return inferDecision(
    { mode: 'live', collectedData },
    { type, source: 'scan' },
  );
}

test('普通换货严格核对一致时禁止无人自动，但允许人工确认后单笔或批量同意换货', () => {
  const data = exactCollectedData();
  const decision = infer('换货', data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.recommendedActionLabel, '同意换货');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.match(decision.reason, /换货.*推荐人工同意换货/);
  assert.match(decision.reason, /悦颜精粹水/);
  assert.match(decision.warnings.join('；'), /提前补发/);
  assert.equal(shouldAutoExecute(decision, data, { type: '换货' }), false);
  assert.equal(isBatchExecutable(decision, 'simulated'), true);
});

test('商责换货保留双重醒目标记，核对一致后仍只推荐人工同意换货', () => {
  const data = exactCollectedData('卖家发错货');
  const decision = infer('换货', data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.deepEqual(decision.manualReviewReasons, ['商责', '换货']);
  assert.equal(decision.manualReviewKind, 'merchant_exchange_return_exact');
  assert.match(decision.reason, /商责换货/);
  assert.match(decision.warnings.join('；'), /生成新的发货单/);

  const classification = classifySimulation({ collectedData: data, decision }, { type: '换货' });
  assert.equal(classification.registered, true);
  assert.equal(classification.branchId, 'merchant_fault.exchange.exact.manual_approve');
  assert.equal(classification.automationStatus, 'manual_only');
});

test('商责退货退款有退货单号且核对一致时，推荐人工同意退款但不得借用正常精确退回自动门禁', () => {
  const data = exactCollectedData('卖家发错货');
  const decision = infer('退货退款', data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.recommendedActionLabel, '同意退款');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(decision.manualReviewKind, 'merchant_refund_return_exact');
  assert.match(decision.reason, /商责退货退款/);
  assert.equal(shouldAutoExecute(decision, data, { type: '退货退款' }), false);
  assert.equal(isBatchExecutable(decision, 'simulated'), true);
});

test('换货退回规格不符时列出实际退回商品并转人工，不推荐同意', () => {
  const data = exactCollectedData();
  data.erpAftersale.rows[0].items[0] = {
    name: '其他商品',
    specCode: 'SPEC-OTHER',
    qtyGood: 1,
    qtyBad: 0,
  };
  const decision = infer('换货', data);

  assert.equal(decision.action, 'escalate');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, false);
  assert.equal(decision.manualReviewKind, 'exchange_return_review');
  assert.match(decision.reason, /规格与订单不符/);
  assert.match(decision.reason, /其他商品/);
});

test('换货无退货单号时保持人工，不伪造退回核验结论', () => {
  const data = exactCollectedData();
  delete data.ticket.returnTracking;
  data.erpAftersale = null;
  const decision = infer('换货', data);

  assert.equal(decision.action, 'escalate');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, false);
  assert.equal(decision.manualReviewKind, 'exchange_no_tracking');
  assert.match(decision.reason, /无退货单号/);
});

test('商责换货无退货单号时描述为申请阶段，不误称退回核验缺失', () => {
  const data = exactCollectedData('卖家发错货');
  delete data.ticket.returnTracking;
  data.erpAftersale = null;
  const decision = infer('换货', data);

  assert.equal(decision.action, 'escalate');
  assert.equal(decision.manualReviewKind, 'merchant_exchange_no_tracking');
  assert.equal(decision.humanTriggeredExecutionAllowed, false);
  assert.match(decision.reason, /客户申请「卖家发错货」退货/);
  assert.match(decision.reason, /确认商责情况是否属实/);
  assert.doesNotMatch(decision.reason, /无法核验客户实际退回商品/);
});

test('人工评价指令不能进入无人自动，但可作为人工确认后的系统执行动作', () => {
  const data = exactCollectedData();
  const decision = inferDecision(
    { mode: 'live', collectedData: data },
    { type: '换货', source: 'scan', hint: '同意换货' },
  );

  assert.equal(decision.action, 'approve');
  assert.equal(decision.hinted, true);
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(decision.recommendedActionLabel, '同意换货');
  assert.equal(isBatchExecutable(decision, 'simulated'), true);
});
