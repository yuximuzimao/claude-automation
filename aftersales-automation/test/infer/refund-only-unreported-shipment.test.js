'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { inferDecision } = require('../../lib/infer');
const { isBatchExecutable } = require('../../lib/constants');
const { shouldAutoExecute } = require('../../lib/server/after-sales-auto-gate');
const { classifySimulation } = require('../../lib/server/after-sales-branch-history');
const { supplementBaiduLogisticsIfNeeded } = require('../../lib/external-logistics-baidu');

const TRACKING = 'TEST-ERP-TRACKING';

function fixture() {
  const search = { subOrderId: '1234', rows: { rows: [{ status: '卖家已发货', tracking: TRACKING }] } };
  const collectedData = {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '多拍/拍错/不想要',
      subOrders: [{ id: 1234, logistics: '准备发货' }],
    },
    erpSearch: search,
    erpSearches: [search],
    erpLogistics: { results: [{ tracking: TRACKING, logisticsText: '揽收 2026-11-17 09:00:00\n您的包裹已揽收' }] },
    logistics: { packages: [{ text: '查看物流\n暂无信息\n关闭' }] },
  };
  return {
    sim: { id: 'sim', mode: 'live', collectedData },
    item: { id: 'queue', workOrderNum: 'test', type: '仅退款', status: 'simulated', urgency: '1天', hoursUntilNextScan: 1 },
  };
}

test('鲸灵准备发货且无物流、ERP 对应运单已揽收，待确认页仅提供人工建议', async () => {
  const { sim, item } = fixture();
  sim.decision = inferDecision(sim, item);
  assert.equal(sim.decision.reasonCode, 'UNREPORTED_SHIPMENT_MANUAL');
  assert.equal(sim.decision.action, 'escalate');
  assert.equal(sim.decision.requiresHumanReview, true);
  assert.equal(sim.decision.humanTriggeredExecutionAllowed, false);
  assert.equal(sim.decision.waitingRescan, undefined);
  assert.deepEqual(sim.decision.courierActions, []);
  assert.equal(isBatchExecutable(sim.decision, item.status), false);
  assert.equal(shouldAutoExecute(sim.decision, sim.collectedData, item), false);
  assert.equal(classifySimulation(sim, item).branchId, 'refund_only.unreported_shipment.manual');

  const supplement = await supplementBaiduLogisticsIfNeeded(sim.collectedData, sim.decision, {
    type: item.type,
    queryBaiduLogistics: () => assert.fail('已确认 ERP 凭证来源，无需补查'),
  });
  assert.equal(supplement.attempted, false);

  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const page = { queuedSimIds: new Set(), renderSteps: () => '' };
  vm.runInNewContext([
    source.slice(source.indexOf('function h('), source.indexOf('function timeAgo(')),
    source.slice(source.indexOf('const DECISION_LABELS'), source.indexOf('function decisionDisplayLabel')),
    source.slice(source.indexOf('function decisionDisplayLabel'), source.indexOf('}', source.indexOf('function decisionDisplayLabel')) + 1),
    source.slice(source.indexOf('function renderBody('), source.indexOf('async function openTicket(')),
  ].join('\n'), page);
  const body = page.renderBody(item, sim, 'live');
  assert.match(body, /人工处理/);
  assert.match(body, /ERP 运单 TEST-ERP-TRACKING/);
  assert.match(body, /ERP 打开对应运单的物流弹窗/);
  assert.match(body, /商品发货中.*可在派件时拒收/);
  assert.match(body, /拒绝成功后，须向鲸灵补传发货物流/);
  assert.doesNotMatch(page.renderActions(item, sim, 'live'), /executeSim/);
});

test('明确发出节点也命中人工分支，评价指令无法开放执行', () => {
  const { sim, item } = fixture();
  sim.collectedData.erpLogistics.results[0].logisticsText = '快件已发出';
  for (const hint of ['同意', '拒绝']) {
    const decision = inferDecision(sim, { ...item, hint });
    assert.equal(decision.reasonCode, 'UNREPORTED_SHIPMENT_MANUAL');
    assert.equal(decision.action, 'escalate');
    assert.equal(decision.humanTriggeredExecutionAllowed, false);
  }
});

test('未揽收、已退回或仍需核实物流时沿用原分支', () => {
  const cases = [
    ['鲸灵已显示运单', cd => { cd.logistics.packages[0].text = `物流单号：${TRACKING}\n已揽收`; }, 'INTERCEPT_WAITING'],
    ['鲸灵读取失败', cd => { cd.logistics.packages = [{ error: '物流弹窗未打开' }]; }, 'INTERCEPT_WAITING'],
    ['鲸灵子订单不是准备发货', cd => { cd.ticket.subOrders[0].logistics = '已发货'; }, 'INTERCEPT_WAITING'],
    ['ERP 运单不属于对应主子订单', cd => { cd.erpSearch.subOrderId = '4567'; }, 'INTERCEPT_WAITING'],
    ['ERP 没有同号物流', cd => { cd.erpLogistics.results[0].tracking = 'OTHER-TRACKING'; }, undefined],
    ['ERP 只有未揽收', cd => { cd.erpLogistics.results[0].logisticsText = '快件尚未揽收'; }, undefined, 'approve'],
    ['ERP 已退回', cd => { cd.erpLogistics.results[0].logisticsText += '\n快件已安排退回'; }, undefined, 'approve'],
    ['ERP 已拦截成功', cd => { cd.erpLogistics.results[0].logisticsText += '\n拦截成功'; }, 'INTERCEPT_WAITING'],
    ['ERP 已签收', cd => { cd.erpLogistics.results[0].logisticsText += '\n买家已签收'; }, 'INTERCEPT_WAITING'],
    ['ERP 另有未知运单', cd => { cd.erpSearch.rows.rows.push({ status: '卖家已发货', tracking: 'UNKNOWN' }); }, 'INTERCEPT_WAITING'],
  ];
  for (const [label, change, expectedCode, expectedAction] of cases) {
    const { sim, item } = fixture();
    change(sim.collectedData);
    const decision = inferDecision(sim, item);
    assert.equal(decision.reasonCode, expectedCode, label);
    if (expectedAction) assert.equal(decision.action, expectedAction, label);
  }
});
