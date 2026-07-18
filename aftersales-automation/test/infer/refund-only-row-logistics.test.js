'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { inferDecision } = require('../../lib/infer');

function makeDecision({ mainRows, giftRows = [], erpLogs = [], packages = [], intercepted, queueItemOverrides = {} }) {
  const gifts = giftRows.length ? [{ id: 'gift-1' }] : [];
  const collectedData = {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '七天无理由退货',
      subBizType: '仅退款',
      subOrders: [{ id: 'main-1' }],
      gifts,
    },
    erpSearches: [{ subOrderId: 'main-1', rows: { rows: mainRows } }],
    erpSearch: { subOrderId: 'main-1', rows: { rows: mainRows } },
    giftErpSearches: giftRows.length
      ? [{ subOrderId: 'gift-1', rows: { rows: giftRows } }]
      : [],
    giftErpSearch: giftRows.length
      ? { subOrderId: 'gift-1', rows: { rows: giftRows } }
      : null,
    erpLogistics: { results: erpLogs },
    logistics: { packages },
    collectErrors: [],
    intercepted,
  };
  const queueItem = {
    id: 'refund-only-row-test',
    type: '仅退款',
    workOrderNum: 'work-order-test',
    urgency: '1天',
    hoursUntilNextScan: 1,
    ...queueItemOverrides,
  };
  return inferDecision({ mode: 'live', collectedData }, queueItem);
}

function trackedRow(status, tracking) {
  return { status, tracking, trackings: [tracking] };
}

function packageText(tracking, logisticsText) {
  return { text: `物流单号：\n${tracking}\n${logisticsText}` };
}

function checkedLogistics(decision) {
  return decision.steps.some(step => step.label === '逐行物流核验');
}

test('待审核、待打印、待发货全部无单号时逐行通过并退款', () => {
  const decision = makeDecision({
    mainRows: [
      { status: '待审核' },
      { status: '待打印快递单' },
      { status: '待发货' },
    ],
    giftRows: [{ status: '待发货' }],
  });

  assert.equal(decision.action, 'approve');
});

test('第一行待审核但后续待打印行已揽收在途时不得退款', () => {
  const tracking = 'TEST-TRACK-IN-TRANSIT';
  const decision = makeDecision({
    mainRows: [{ status: '待审核' }, trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '揽收\n在途运输中' }],
    packages: [packageText(tracking, '揽收\n在途运输中')],
  });

  assert.notEqual(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('后续带单号行已有退回节点时允许退款', () => {
  const tracking = 'TEST-TRACK-RETURNED';
  const decision = makeDecision({
    mainRows: [{ status: '待审核' }, trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '揽收\n客户拒收，快件已安排退回' }],
    packages: [packageText(tracking, '客户拒收，快件已安排退回')],
  });

  assert.equal(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('只有“收件人要求退回，等待发件人确认”时不算已退回', () => {
  const tracking = 'TEST-TRACK-PENDING-RETURN';
  const pending = '包裹异常\n收件人要求退回，等待发件人确认！';
  const decision = makeDecision({
    mainRows: [trackedRow('卖家已发货', tracking)],
    erpLogs: [{ tracking, logisticsText: pending }],
    packages: [packageText(tracking, pending)],
  });

  assert.notEqual(decision.action, 'approve');
});

test('待发件人确认之后另有明确退回节点时仍算已退回', () => {
  const tracking = 'TEST-TRACK-CONFIRMED-RETURN';
  const confirmed = '包裹异常\n收件人要求退回，等待发件人确认！\n退回\n您的快件已被安排退回';
  const decision = makeDecision({
    mainRows: [trackedRow('卖家已发货', tracking)],
    erpLogs: [{ tracking, logisticsText: confirmed }],
    packages: [packageText(tracking, confirmed)],
  });

  assert.equal(decision.action, 'approve');
});

test('两边重复待确认文案加退回件标签仍不算第二个退回节点', () => {
  const tracking = 'TEST-TRACK-DUPLICATE-PENDING';
  const pending = '退回件\n包裹异常\n收件人要求退回，等待发件人确认！';
  const decision = makeDecision({
    mainRows: [trackedRow('卖家已发货', tracking)],
    erpLogs: [{ tracking, logisticsText: pending }],
    packages: [packageText(tracking, pending)],
  });

  assert.notEqual(decision.action, 'approve');
});

test('有单号但物流明确尚未揽收时仍按未发货退款', () => {
  const tracking = 'TEST-TRACK-NOT-PICKED';
  const decision = makeDecision({
    mainRows: [trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '暂无物流信息，等待揽收' }],
    packages: [packageText(tracking, '暂无物流信息，等待揽收')],
  });

  assert.equal(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('有单号但只有暂无物流信息时不得当作明确未揽收退款', () => {
  const tracking = 'TESTTRACKNOINFO001';
  const decision = makeDecision({
    mainRows: [trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '暂无物流信息' }],
    packages: [packageText(tracking, '暂无物流信息')],
  });

  assert.notEqual(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('ERP明确已发货但没有单号时作为数据异常转人工', () => {
  const decision = makeDecision({ mainRows: [{ status: '卖家已发货' }] });

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /无快递单号|数据异常/);
});

test('赠品带单号且仍在途时与主品使用相同规则并阻止退款', () => {
  const tracking = 'TEST-GIFT-IN-TRANSIT';
  const decision = makeDecision({
    mainRows: [{ status: '待审核' }],
    giftRows: [trackedRow('待发货', tracking)],
    erpLogs: [{ tracking, logisticsText: '揽收\n在途运输中' }],
    packages: [packageText(tracking, '揽收\n在途运输中')],
  });

  assert.notEqual(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('只有本地拦截记录但物流仍在途时不得视为拦截成功', () => {
  const tracking = 'TEST-TRACK-INTERCEPT-RECORD';
  const decision = makeDecision({
    mainRows: [{ status: '待审核' }, trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '揽收\n在途运输中' }],
    packages: [packageText(tracking, '揽收\n在途运输中')],
    intercepted: { tracking, workOrderNum: 'old-work-order' },
  });

  assert.notEqual(decision.action, 'approve');
});

test('有单号但物流结果不明时不得退款', () => {
  const tracking = 'TEST-TRACK-UNKNOWN';
  const decision = makeDecision({
    mainRows: [{ status: '待审核' }, trackedRow('待打印快递单', tracking)],
    erpLogs: [{ tracking, logisticsText: '' }],
    packages: [],
  });

  assert.notEqual(decision.action, 'approve');
  assert.equal(checkedLogistics(decision), true);
});

test('未揽收单号与在途单号混合时只要求拦截实际在途件', () => {
  const notPickedUp = 'TESTNOTPICKEDMIXED001';
  const inTransit = 'TESTINTRANSITMIXED002';
  const decision = makeDecision({
    mainRows: [
      trackedRow('待打印快递单', notPickedUp),
      trackedRow('卖家已发货', inTransit),
    ],
    erpLogs: [
      { tracking: notPickedUp, logisticsText: '暂无物流信息，等待揽收' },
      { tracking: inTransit, logisticsText: '揽收\n在途运输中' },
    ],
    packages: [
      packageText(notPickedUp, '暂无物流信息，等待揽收'),
      packageText(inTransit, '揽收\n在途运输中'),
    ],
  });

  assert.notEqual(decision.action, 'approve');
  assert.match(decision.reason, new RegExp(inTransit));
  assert.doesNotMatch(decision.reason, new RegExp(notPickedUp));
});

test('驿站待取件且时效充足时先拦截并等待重查', () => {
  const tracking = 'TEST-AT-STATION-WAIT';
  const station = '入站\n您的快件已到达菜鸟驿站，请及时取件';
  const decision = makeDecision({
    mainRows: [trackedRow('卖家已发货', tracking)],
    erpLogs: [{ tracking, logisticsText: station }],
    packages: [packageText(tracking, station)],
    queueItemOverrides: { urgency: '1天', hoursUntilNextScan: 1 },
  });

  assert.equal(decision.waitingRescan, true);
  assert.match(decision.reason, /驿站待取件.*需拦截/);
  assert.ok(decision.warnings.some(warning => warning.includes('拦截提醒')));
});

test('驿站待取件只有时效不足时才拒绝退款', () => {
  const tracking = 'TEST-AT-STATION-TIMEOUT';
  const station = '入站\n您的快件已到达菜鸟驿站，请及时取件';
  const decision = makeDecision({
    mainRows: [trackedRow('卖家已发货', tracking)],
    erpLogs: [{ tracking, logisticsText: station }],
    packages: [packageText(tracking, station)],
    queueItemOverrides: { urgency: '9小时', hoursUntilNextScan: 1 },
  });

  assert.equal(decision.action, 'reject');
  assert.equal(decision.waitingRescan, undefined);
  assert.equal(decision.reasonCode, 'INTERCEPT_TIMEOUT');
  assert.ok(decision.warnings.some(warning => warning.includes('拦截')));
});
