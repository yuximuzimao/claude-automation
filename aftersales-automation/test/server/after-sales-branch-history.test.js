'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  REGISTERED_RULE_SUMMARIES,
  classifySimulation,
  summarizeHistory,
} = require('../../lib/server/after-sales-branch-history');

test('infer.js 中每个带 summary 的最终规则都必须登记', () => {
  const source = fs.readFileSync(path.join(__dirname, '../../lib/infer.js'), 'utf8');
  const summaries = [...source.matchAll(/summary: '([^']+)'/g)].map(match => match[1]);
  const missing = [...new Set(summaries)].filter(summary => !REGISTERED_RULE_SUMMARIES.has(summary));

  assert.deepEqual(missing, []);
});

function makeSimulation(overrides = {}) {
  const ruleSummary = overrides.ruleSummary || '逐商品对比通过→同意退款';
  return {
    id: overrides.id || 'sim-1',
    workOrderNum: overrides.workOrderNum || 'wo-1',
    queueItemId: overrides.queueItemId || 'queue-1',
    createdAt: overrides.createdAt || '2026-07-10T00:00:00.000Z',
    autoExecutedAt: overrides.autoExecutedAt,
    executedAt: overrides.executedAt,
    collectedData: {
      ticket: {
        afterSaleReason: overrides.afterSaleReason || '七天无理由退货（不喜欢/不合适）',
        returnTracking: 'RETURN-1',
        buyerRemark: Object.prototype.hasOwnProperty.call(overrides, 'buyerRemark')
          ? overrides.buyerRemark
          : '无',
        subOrders: [{ id: 'main-1', afterSaleNum: 1 }],
        gifts: [],
      },
      productArchives: [{
        subOrderId: 'main-1',
        subItems: [{ name: '商品A', specCode: 'SPEC-A', qty: 1 }],
      }],
      erpAftersale: {
        rows: [{
          erpOrderId: 'ERP-1',
          tracking: 'RETURN-1',
          goodsStatus: '卖家已收到退货',
          returnQty: overrides.receivedGood ?? 1,
          items: [{ name: '商品A', specCode: 'SPEC-A', qtyGood: overrides.receivedGood ?? 1, qtyBad: 0 }],
        }],
      },
    },
    decision: {
      action: overrides.action || 'approve',
      reason: overrides.reason || '核对通过',
      warnings: overrides.warnings || [],
      rulesApplied: overrides.noRule ? [] : [{
        doc: overrides.ruleDoc || 'flow-5.1',
        section: overrides.ruleSection || 'Step4',
        summary: ruleSummary,
      }],
    },
  };
}

test('同一退货核对规则必须拆开精确退回和真实多退', () => {
  const exact = classifySimulation(makeSimulation(), { type: '退货退款' });
  const excess = classifySimulation(makeSimulation({
    receivedGood: 2,
    warnings: ['入库3件，比期望多1件（可能少申请了退货份数）'],
    reason: '核对通过：商品A×2，实退3件（多1件）',
  }), { type: '退货退款' });

  assert.equal(exact.branchId, 'refund_return.received.exact.approve');
  assert.equal(exact.automationStatus, 'enabled');
  assert.equal(excess.branchId, 'refund_return.received.excess.approve');
  assert.equal(excess.automationStatus, 'candidate');
  assert.notEqual(exact.caseId, excess.caseId);
});

test('部分签收且部分可拦截的新拒绝结果登记为候选分支', () => {
  const result = classifySimulation(makeSimulation({
    action: 'reject',
    ruleDoc: 'flow-5.3',
    ruleSummary: '部分签收+部分可拦截→拒绝退款+拦截未签收件',
    reason: '一个包裹已签收，另一个包裹仍需拦截',
  }), { type: '仅退款' });

  assert.equal(result.branchId, 'refund_only.mixed_signed_and_interceptable.reject');
  assert.equal(result.automationStatus, 'candidate');
  assert.match(result.branchLabel, /拒绝退款/);
});

test('旧决定虽然写着核对通过，严格规格证明不完整时仍必须转人工分支', () => {
  const simulation = makeSimulation();
  simulation.collectedData.productArchives = [];

  const result = classifySimulation(simulation, { type: '退货退款' });
  assert.equal(result.branchId, 'refund_return.received.incomplete.manual');
  assert.equal(result.automationStatus, 'manual_only');
  assert.match(result.missingFacts.join('；'), /商品档案/);
});

test('退货异常必须区分少退、次品和两者同时存在', () => {
  const short = classifySimulation(makeSimulation({
    action: 'escalate',
    ruleSummary: '退货异常→上报人工',
    reason: '退货数量不足：商品A（退了0件，应退1件）',
  }), { type: '退货退款' });
  const damaged = classifySimulation(makeSimulation({
    action: 'escalate',
    ruleSummary: '退货异常→上报人工',
    reason: '退货含次品：商品A（次品1件）',
  }), { type: '退货退款' });
  const both = classifySimulation(makeSimulation({
    action: 'escalate',
    ruleSummary: '退货异常→上报人工',
    reason: '退货含次品：商品A（次品1件）；退货数量不足：商品B',
  }), { type: '退货退款' });

  assert.equal(short.branchId, 'refund_return.received.short.manual');
  assert.equal(damaged.branchId, 'refund_return.received.damaged.manual');
  assert.equal(both.branchId, 'refund_return.received.damaged_and_short.manual');
  assert.equal(short.automationStatus, 'manual_only');
});

test('相同最终分支但售后原因不同，必须使用不同 caseId', () => {
  const sevenDay = classifySimulation(makeSimulation(), { type: '退货退款' });
  const trial = classifySimulation(makeSimulation({ afterSaleReason: '试用退货' }), { type: '退货退款' });

  assert.equal(sevenDay.branchId, trial.branchId);
  assert.notEqual(sevenDay.caseId, trial.caseId);
  assert.equal(trial.automationStatus, 'candidate');
});

test('仅开放多拍拍错的主品赠品均未发货分支，其他原因保持候选', () => {
  const makeRefundOnlySimulation = afterSaleReason => ({
    collectedData: { ticket: { afterSaleReason } },
    decision: {
      action: 'approve',
      reason: '主商品+赠品均未发货（无快递单号）',
      warnings: [],
      rulesApplied: [{
        doc: 'flow-5.2',
        section: 'Step4',
        summary: '主商品+赠品未发货→同意退款',
      }],
    },
  });

  const enabled = classifySimulation(
    makeRefundOnlySimulation('多拍/拍错/不想要'),
    { type: '仅退款' },
  );
  const candidate = classifySimulation(
    makeRefundOnlySimulation('拒收'),
    { type: '仅退款' },
  );

  assert.equal(enabled.branchId, 'refund_only.unshipped.approve');
  assert.equal(enabled.automationStatus, 'enabled');
  assert.equal(candidate.branchId, 'refund_only.unshipped.approve');
  assert.equal(candidate.automationStatus, 'candidate');
  assert.notEqual(enabled.caseId, candidate.caseId);
});

test('多拍拍错的安全物流分支已授权，其他售后原因仍保持候选', () => {
  const makeSafeTrackingSimulation = afterSaleReason => ({
    collectedData: { ticket: { afterSaleReason } },
    decision: {
      action: 'approve',
      reason: '主商品和赠品全部ERP行均未发货或物流已退回',
      warnings: [],
      rulesApplied: [{
        doc: 'flow-5.2',
        section: 'Step4',
        summary: '全部ERP行逐行核验通过→同意退款',
      }],
    },
  });

  const enabled = classifySimulation(
    makeSafeTrackingSimulation('多拍/拍错/不想要'),
    { type: '仅退款' },
  );
  const candidate = classifySimulation(
    makeSafeTrackingSimulation('拒收'),
    { type: '仅退款' },
  );

  assert.equal(enabled.branchId, 'refund_only.safe_tracking.approve');
  assert.equal(enabled.automationStatus, 'enabled');
  assert.equal(candidate.branchId, 'refund_only.safe_tracking.approve');
  assert.equal(candidate.automationStatus, 'candidate');
});

test('无法识别的旧结果明确列为未登记，不得猜测或允许自动处理', () => {
  const result = classifySimulation(makeSimulation({ noRule: true }), { type: '退货退款' });

  assert.equal(result.registered, false);
  assert.equal(result.branchId, 'unregistered');
  assert.equal(result.automationStatus, 'manual_only');
  assert.match(result.missingFacts.join('；'), /规则结果/);
});

test('历史记录缺少工单类型时进入明确的数据不完整分支', () => {
  const result = classifySimulation(makeSimulation(), {});

  assert.equal(result.registered, true);
  assert.equal(result.branchId, 'global.order_type_missing.manual');
  assert.equal(result.automationStatus, 'manual_only');
  assert.deepEqual(result.missingFacts, ['工单类型']);
});

test('七天无理由退货无退货单号是明确人工分支，不是未登记', () => {
  const simulation = makeSimulation({ action: 'escalate', noRule: true });
  delete simulation.collectedData.ticket.returnTracking;
  simulation.decision.reason = '无退货快递单号，可能为超期特殊退货或次品特殊处理，请人工查询并判断';

  const result = classifySimulation(simulation, { type: '退货退款' });
  assert.equal(result.registered, true);
  assert.equal(result.branchId, 'refund_return.no_tracking.special.manual');
  assert.equal(result.automationStatus, 'manual_only');
});

test('七天无理由无退货单号只有命中特殊退货理由时才进入该人工分支', () => {
  const simulation = makeSimulation({ action: 'escalate', noRule: true });
  delete simulation.collectedData.ticket.returnTracking;
  simulation.decision.reason = '采集数据不完整：缺少ERP售后数据';

  const result = classifySimulation(simulation, { type: '退货退款' });
  assert.notEqual(result.branchId, 'refund_return.no_tracking.special.manual');
  assert.equal(result.automationStatus, 'manual_only');
});

test('已退款等平台终态是明确无操作分支', () => {
  const simulation = makeSimulation({ action: 'skip', noRule: true });
  simulation.collectedData.ticket.workOrderStatus = '已退款';
  simulation.decision.reason = '工单状态：已退款，平台已自动处理，无需操作';

  const result = classifySimulation(simulation, { type: '退货退款' });
  assert.equal(result.registered, true);
  assert.equal(result.branchId, 'global.terminal.skip');
  assert.equal(result.automationStatus, 'manual_only');
});

test('历史汇总按工单去重，只采用30天内最新结果', () => {
  const simulations = [
    makeSimulation({ id: 'sim-old', createdAt: '2026-07-01T00:00:00.000Z' }),
    makeSimulation({ id: 'sim-new', createdAt: '2026-07-12T00:00:00.000Z' }),
  ];
  const report = summarizeHistory({
    simulations,
    feedbacks: [{ simulationId: 'sim-new', verdict: 'positive' }],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    journal: {
      'wo-1': { pageActionSucceededAt: '2026-07-12T00:01:00.000Z' },
    },
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.totalSimulations, 2);
  assert.equal(report.uniqueWorkOrders, 1);
  assert.equal(report.cases.length, 1);
  assert.equal(report.cases[0].occurrenceCount, 1);
  assert.equal(report.cases[0].positiveCount, 1);
  assert.equal(report.cases[0].autoSuccessCount, 1);
});

test('同一工单重扫但最终分支不变时，较早快照上的最新反馈仍计入一次', () => {
  const simulations = [
    makeSimulation({ id: 'sim-old', createdAt: '2026-07-01T00:00:00.000Z' }),
    makeSimulation({ id: 'sim-new', createdAt: '2026-07-12T00:00:00.000Z' }),
  ];
  const report = summarizeHistory({
    simulations,
    feedbacks: [
      { simulationId: 'sim-old', workOrderNum: 'wo-1', verdict: 'negative', createdAt: '2026-07-02T00:00:00.000Z' },
      { simulationId: 'sim-old', workOrderNum: 'wo-1', verdict: 'positive', createdAt: '2026-07-03T00:00:00.000Z' },
    ],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].positiveCount, 1);
  assert.equal(report.cases[0].negativeCount, 0);
});

test('同一工单重扫后最终分支改变时，旧分支反馈不得串入新分支', () => {
  const simulations = [
    makeSimulation({ id: 'sim-old', createdAt: '2026-07-01T00:00:00.000Z' }),
    makeSimulation({ id: 'sim-new', createdAt: '2026-07-12T00:00:00.000Z', receivedGood: 0 }),
  ];
  const report = summarizeHistory({
    simulations,
    feedbacks: [{ simulationId: 'sim-old', workOrderNum: 'wo-1', verdict: 'positive', createdAt: '2026-07-02T00:00:00.000Z' }],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    journal: { 'wo-1': { pageActionSucceededAt: '2026-07-01T00:01:00.000Z' } },
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].branchId, 'refund_return.received.short.manual');
  assert.equal(report.cases[0].positiveCount, 0);
  assert.equal(report.cases[0].negativeCount, 0);
  assert.equal(report.cases[0].autoSuccessCount, 0);
});

test('同一工单重扫后分支不变时，旧自动成功仍归入相同分支一次', () => {
  const report = summarizeHistory({
    simulations: [
      makeSimulation({ id: 'sim-old', createdAt: '2026-07-01T00:00:00.000Z' }),
      makeSimulation({ id: 'sim-new', createdAt: '2026-07-12T00:00:00.000Z' }),
    ],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    journal: { 'wo-1': { pageActionSucceededAt: '2026-07-01T00:01:00.000Z' } },
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].autoSuccessCount, 1);
});

test('人工 hint 覆盖的工单不进入任何分支累计', () => {
  const hinted = makeSimulation();
  hinted.decision.hinted = true;
  const report = summarizeHistory({
    simulations: [hinted],
    queueItems: [{ id: 'queue-1', type: '退货退款', hint: '同意退款' }],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.uniqueWorkOrders, 0);
  assert.deepEqual(report.cases, []);
});

test('已手动处理归档按工单计入人工处理次数', () => {
  const report = summarizeHistory({
    simulations: [makeSimulation()],
    feedbacks: [],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    archivedCases: [{ workOrderNum: 'wo-1', type: '退货退款', groundTruth: { source: 'manual_handled' } }],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].manualHandledCount, 1);
  assert.equal(report.cases[0].manualExecutedCount, 0);
  assert.equal(report.cases[0].manualArchivedCount, 1);
});

test('执行操作与手动归档分别计数，同时保留旧人工处理合计', () => {
  const simulations = [
    makeSimulation({ id: 'sim-executed', workOrderNum: 'wo-executed', queueItemId: 'queue-executed' }),
    makeSimulation({ id: 'sim-batch', workOrderNum: 'wo-batch', queueItemId: 'queue-batch' }),
    makeSimulation({ id: 'sim-archived', workOrderNum: 'wo-archived', queueItemId: 'queue-archived' }),
  ];
  const report = summarizeHistory({
    simulations,
    queueItems: [
      { id: 'queue-executed', workOrderNum: 'wo-executed', type: '退货退款' },
      { id: 'queue-batch', workOrderNum: 'wo-batch', type: '退货退款' },
      { id: 'queue-archived', workOrderNum: 'wo-archived', type: '退货退款' },
    ],
    archivedCases: [
      { workOrderNum: 'wo-executed', addedAt: '2026-07-10T01:00:00.000Z', groundTruth: { source: 'executed' } },
      { workOrderNum: 'wo-batch', addedAt: '2026-07-10T01:00:00.000Z', groundTruth: { source: 'batch_executed' } },
      { workOrderNum: 'wo-archived', addedAt: '2026-07-10T01:00:00.000Z', groundTruth: { source: 'manual_handled' } },
    ],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].manualExecutedCount, 2);
  assert.equal(report.cases[0].manualArchivedCount, 1);
  assert.equal(report.cases[0].manualHandledCount, 3);
});

test('自动处理归档即使带 executedAt 也不得误算为执行操作', () => {
  const report = summarizeHistory({
    simulations: [makeSimulation({ executedAt: '2026-07-10T00:01:00.000Z' })],
    queueItems: [{ id: 'queue-1', type: '退货退款' }],
    archivedCases: [{
      workOrderNum: 'wo-1',
      addedAt: '2026-07-10T01:00:00.000Z',
      groundTruth: { source: 'auto_executed' },
    }],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].manualExecutedCount, 0);
  assert.equal(report.cases[0].manualArchivedCount, 0);
  assert.equal(report.cases[0].manualHandledCount, 0);
});

test('待商家二次发货使用稳定独立分支，不归入未登记', () => {
  const simulation = {
    id: 'sim-stage',
    workOrderNum: 'wo-stage',
    queueItemId: 'queue-stage',
    createdAt: '2026-07-12T00:00:00.000Z',
    collectedData: {
      ticket: { buyerRemark: '' },
      platformStage: {
        raw: '商家-待商家二次发货',
        observedAt: '2026-07-12T00:00:00.000Z',
        source: 'after-sale-list',
        readState: 'read',
      },
    },
    decision: {
      action: 'skip',
      manualArchiveOnly: true,
      platformStageCaseId: 'exchange_waiting_merchant_reship',
    },
  };

  const result = classifySimulation(simulation, { type: '换货' });
  assert.equal(result.registered, true);
  assert.equal(result.caseId, 'platform_stage.exchange_waiting_merchant_reship');
  assert.equal(result.branchId, 'exchange.waiting_merchant_reship.confirm_no_action');
  assert.equal(result.afterSaleReason, '平台阶段观察');
});

test('只有无需处理人工归档决定能进入阶段观察分支', () => {
  const malformed = {
    id: 'sim-stage-malformed',
    workOrderNum: 'wo-stage-malformed',
    createdAt: '2026-07-12T00:00:00.000Z',
    collectedData: { ticket: {} },
    decision: {
      action: 'approve',
      manualArchiveOnly: false,
      platformStageCaseId: 'exchange_waiting_merchant_reship',
    },
  };
  const result = classifySimulation(malformed, { type: '换货' });
  assert.notEqual(result.branchId, 'exchange.waiting_merchant_reship.confirm_no_action');
  assert.equal(result.registered, false);
});

test('人工确认无需处理单独计数，不混入人工执行次数', () => {
  const simulation = {
    id: 'sim-stage',
    workOrderNum: 'wo-stage',
    queueItemId: 'queue-stage',
    createdAt: '2026-07-12T00:00:00.000Z',
    collectedData: { ticket: { buyerRemark: '' } },
    decision: {
      action: 'skip',
      manualArchiveOnly: true,
      platformStageCaseId: 'exchange_waiting_merchant_reship',
    },
  };
  const report = summarizeHistory({
    simulations: [simulation],
    queueItems: [{ id: 'queue-stage', workOrderNum: 'wo-stage', type: '换货' }],
    archivedCases: [{
      workOrderNum: 'wo-stage',
      type: '换货',
      addedAt: '2026-07-12T01:00:00.000Z',
      groundTruth: { source: 'confirmed_no_action' },
    }],
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.cases[0].confirmedNoActionCount, 1);
  assert.equal(report.cases[0].manualHandledCount, 0);
});

test('旧 simulation 的 queueItemId 失效时，按同一工单号恢复工单类型', () => {
  const simulation = makeSimulation({ queueItemId: 'missing-queue-id' });
  const report = summarizeHistory({
    simulations: [simulation],
    feedbacks: [],
    queueItems: [{ id: 'new-queue-id', workOrderNum: 'wo-1', type: '退货退款' }],
    journal: {},
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.unregisteredCount, 0);
  assert.equal(report.cases[0].orderType, '退货退款');
});

test('queue 也缺失时，只能按同一工单号的历史 case 恢复类型', () => {
  const simulation = makeSimulation({ queueItemId: 'missing-queue-id' });
  const report = summarizeHistory({
    simulations: [simulation],
    feedbacks: [],
    queueItems: [],
    archivedCases: [{ workOrderNum: 'wo-1', type: '退货退款' }],
    journal: {},
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  assert.equal(report.unregisteredCount, 0);
  assert.equal(report.cases[0].orderType, '退货退款');
});

test('备注区分字面“无”、真正空值和脱敏后的具体内容', () => {
  const simulations = [
    makeSimulation({ id: 'sim-1', workOrderNum: 'wo-1', queueItemId: 'queue-1', buyerRemark: '无' }),
    makeSimulation({ id: 'sim-2', workOrderNum: 'wo-2', queueItemId: 'queue-2', buyerRemark: '' }),
    makeSimulation({ id: 'sim-3', workOrderNum: 'wo-3', queueItemId: 'queue-3', buyerRemark: '电话13800138000，订单123456789012345' }),
  ];
  const report = summarizeHistory({
    simulations,
    feedbacks: [],
    queueItems: [
      { id: 'queue-1', type: '退货退款' },
      { id: 'queue-2', type: '退货退款' },
      { id: 'queue-3', type: '退货退款' },
    ],
    journal: {},
    now: new Date('2026-07-18T00:00:00.000Z'),
  });

  const notes = Object.fromEntries(report.cases[0].notes.map(item => [item.value, item.count]));
  assert.equal(notes['字面“无”'], 1);
  assert.equal(notes['真正空值'], 1);
  assert.equal(notes['电话[手机号]，订单[编号]'], 1);
});
