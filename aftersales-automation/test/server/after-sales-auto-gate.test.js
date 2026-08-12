'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  proveRefundOnlySafeTracking,
  proveRefundOnlyUnshipped,
  shouldAutoExecute,
} = require('../../lib/server/after-sales-auto-gate');

function exactCollectedData(reason = '七天无理由退货（不喜欢/不合适）') {
  return {
    ticket: {
      afterSaleReason: reason,
      returnTracking: 'RETURN-1',
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
        returnQty: 1,
        items: [{ name: '商品A', specCode: 'SPEC-A', qtyGood: 1, qtyBad: 0 }],
      }],
    },
  };
}

function approveDecision(overrides = {}) {
  return {
    action: 'approve',
    reason: '核对通过',
    warnings: [],
    rulesApplied: [{ doc: 'flow-5.1', section: 'Step4', summary: '逐商品对比通过→同意退款' }],
    ...overrides,
  };
}

function refundOnlyUnshippedData(reason = '多拍/拍错/不想要') {
  return {
    ticket: {
      afterSaleReason: reason,
      returnTracking: '',
      subOrders: [{ id: 'MAIN-1' }, { id: 'MAIN-2' }],
      gifts: [{ id: 'GIFT-1' }],
    },
    erpSearches: [
      {
        subOrderId: 'MAIN-1',
        rows: { rows: [{ status: '待审核', tracking: null, trackings: [], platformOrderIds: ['MAIN-1'] }] },
      },
      {
        subOrderId: 'MAIN-2',
        rows: { rows: [{ status: '待发货', tracking: null, trackings: [], platformOrderIds: ['MAIN-2'] }] },
      },
    ],
    giftErpSearches: [{
      subOrderId: 'GIFT-1',
      rows: { rows: [{ status: '待打印快递单', tracking: null, trackings: [], platformOrderIds: ['GIFT-1'] }] },
    }],
    logistics: { packages: [{ text: '查看物流\n暂无信息\n关闭' }] },
    erpLogistics: { results: [{ tracking: '', logisticsText: '暂无物流信息' }] },
    collectErrors: [
      'product-detail: 跳过（工单类型=仅退款，无需核对商品明细）',
      'erp-aftersale: 无退货快递单号，跳过',
    ],
  };
}

function refundOnlyDecision(overrides = {}) {
  return approveDecision({
    reason: '主商品+赠品均未发货（无快递单号）',
    rulesApplied: [{ doc: 'flow-5.2', section: 'Step4', summary: '主商品+赠品未发货→同意退款' }],
    ...overrides,
  });
}

function refundOnlySafeTrackingData(reason = '多拍/拍错/不想要') {
  const data = refundOnlyUnshippedData(reason);
  data.erpSearches[0].rows.rows[0] = {
    status: '卖家已发货',
    tracking: 'RETURNED-1',
    trackings: ['RETURNED-1'],
    platformOrderIds: ['MAIN-1'],
  };
  data.erpSearches[1].rows.rows[0] = {
    status: '待打印快递单',
    tracking: 'NOT-PICKED-1',
    trackings: ['NOT-PICKED-1'],
    platformOrderIds: ['MAIN-2'],
  };
  data.erpLogistics = { results: [
    { tracking: 'RETURNED-1', logisticsText: '客户要求，快件已安排退回' },
    { tracking: 'NOT-PICKED-1', logisticsText: '暂无物流信息，等待揽收' },
  ] };
  data.logistics = { packages: [
    { text: '物流单号：RETURNED-1\n客户要求，快件已安排退回' },
    { text: '物流单号：NOT-PICKED-1\n暂无物流信息，等待揽收' },
  ] };
  return data;
}

function refundOnlySafeTrackingDecision(overrides = {}) {
  return approveDecision({
    reason: '主商品和赠品全部ERP行均未发货或物流已退回',
    rulesApplied: [{ doc: 'flow-5.2', section: 'Step4', summary: '全部ERP行逐行核验通过→同意退款' }],
    ...overrides,
  });
}

test('只允许七天无理由退货的严格精确退回分支自动执行', () => {
  assert.equal(shouldAutoExecute(
    approveDecision(),
    exactCollectedData(),
    { type: '退货退款' },
  ), true);
});

test('没有退货单号时即使旧决定写着核对通过也禁止自动执行', () => {
  const data = exactCollectedData();
  delete data.ticket.returnTracking;

  assert.equal(shouldAutoExecute(approveDecision(), data, { type: '退货退款' }), false);
});

test('工单类型不是退货退款时不得借用退货核对规则自动执行', () => {
  assert.equal(shouldAutoExecute(
    approveDecision(),
    exactCollectedData(),
    { type: '仅退款' },
  ), false);
});

test('名称中碰巧包含七天无理由退货的其他原因不得自动执行', () => {
  assert.equal(shouldAutoExecute(
    approveDecision(),
    exactCollectedData('非七天无理由退货特殊处理'),
    { type: '退货退款' },
  ), false);
});

test('纯七天无理由退货原因尚未单独授权，保持人工', () => {
  assert.equal(shouldAutoExecute(
    approveDecision(),
    exactCollectedData('七天无理由退货'),
    { type: '退货退款' },
  ), false);
});

test('严格商品数量看似一致但存在采集错误时禁止自动执行', () => {
  const data = exactCollectedData();
  data.collectErrors = ['erp-aftersale: 读取不完整'];

  assert.equal(shouldAutoExecute(approveDecision(), data, { type: '退货退款' }), false);
});

test('旧决定写着核对通过，但规格编码不匹配时禁止自动执行', () => {
  const data = exactCollectedData();
  data.erpAftersale.rows[0].items[0].specCode = 'OTHER-SPEC';

  assert.equal(shouldAutoExecute(approveDecision(), data, { type: '退货退款' }), false);
});

test('其他售后原因即使严格精确退回也仍是候选，不自动执行', () => {
  assert.equal(shouldAutoExecute(
    approveDecision(),
    exactCollectedData('试用退货'),
    { type: '退货退款' },
  ), false);
});

test('人工 hint 覆盖的同意决定永远不能进入自动门禁', () => {
  assert.equal(shouldAutoExecute(
    approveDecision({ hinted: true }),
    exactCollectedData(),
    { type: '退货退款', hint: '同意退款' },
  ), false);
});

test('多拍拍错仅退款的主品和赠品均严格证明未发货时允许自动执行', () => {
  const data = refundOnlyUnshippedData();

  assert.equal(proveRefundOnlyUnshipped(data), true);
  assert.equal(shouldAutoExecute(refundOnlyDecision(), data, { type: '仅退款' }), true);
});

test('多拍拍错仅退款的所有运单均未揽收或已退回时允许自动执行', () => {
  const data = refundOnlySafeTrackingData();

  assert.equal(proveRefundOnlySafeTracking(data), true);
  assert.equal(shouldAutoExecute(refundOnlySafeTrackingDecision(), data, { type: '仅退款' }), true);
});

test('安全物流分支只授权多拍拍错，其他售后原因保持人工', () => {
  const data = refundOnlySafeTrackingData('拒收');

  assert.equal(proveRefundOnlySafeTracking(data), true);
  assert.equal(shouldAutoExecute(refundOnlySafeTrackingDecision(), data, { type: '仅退款' }), false);
});

test('安全物流分支出现任一在途、未知、额外运单或采集错误时禁止自动执行', () => {
  const inTransit = refundOnlySafeTrackingData();
  inTransit.erpLogistics.results[1].logisticsText = '快件已揽收，正在运输中';
  inTransit.logistics.packages[1].text = '物流单号：NOT-PICKED-1\n快件已揽收，正在运输中';
  assert.equal(proveRefundOnlySafeTracking(inTransit), false);

  const unknown = refundOnlySafeTrackingData();
  unknown.erpLogistics.results[1].logisticsText = '暂无物流信息';
  unknown.logistics.packages[1].text = '物流单号：NOT-PICKED-1\n暂无物流信息';
  assert.equal(proveRefundOnlySafeTracking(unknown), false);

  const extraTracking = refundOnlySafeTrackingData();
  extraTracking.logistics.packages.push({ text: '物流单号：EXTRA-1\n等待揽收' });
  assert.equal(proveRefundOnlySafeTracking(extraTracking), false);

  const extraErpTracking = refundOnlySafeTrackingData();
  extraErpTracking.erpLogistics.results.push({ tracking: 'EXTRA-ERP-1', logisticsText: '等待揽收' });
  assert.equal(proveRefundOnlySafeTracking(extraErpTracking), false);

  const abnormalUntracked = refundOnlySafeTrackingData();
  abnormalUntracked.giftErpSearches[0].rows.rows[0].status = '卖家已发货';
  assert.equal(proveRefundOnlySafeTracking(abnormalUntracked), false);

  const collectError = refundOnlySafeTrackingData();
  collectError.collectErrors.push('erp-search: 子订单 MAIN-2 读取失败');
  assert.equal(proveRefundOnlySafeTracking(collectError), false);
});

test('相同未发货分支的其他售后原因没有授权，仍保持人工', () => {
  const data = refundOnlyUnshippedData('拒收');

  assert.equal(shouldAutoExecute(refundOnlyDecision(), data, { type: '仅退款' }), false);
});

test('任一赠品搜索缺失、平台交易号不匹配或出现运单时禁止自动执行', () => {
  const missingGift = refundOnlyUnshippedData();
  missingGift.giftErpSearches = [];
  assert.equal(proveRefundOnlyUnshipped(missingGift), false);

  const wrongOrder = refundOnlyUnshippedData();
  wrongOrder.erpSearches[1].rows.rows[0].platformOrderIds = ['OTHER'];
  assert.equal(proveRefundOnlyUnshipped(wrongOrder), false);

  const tracked = refundOnlyUnshippedData();
  tracked.giftErpSearches[0].rows.rows[0].tracking = 'TRACK-1';
  assert.equal(proveRefundOnlyUnshipped(tracked), false);
});

test('出现额外采集错误或鲸灵侧存在ERP行外运单时禁止自动执行', () => {
  const collectError = refundOnlyUnshippedData();
  collectError.collectErrors.push('erp-search: 子订单 MAIN-2 读取失败');
  assert.equal(proveRefundOnlyUnshipped(collectError), false);

  const jlTracking = refundOnlyUnshippedData();
  jlTracking.logistics.packages[0].text = '物流单号：TRACK-OUTSIDE-ERP';
  assert.equal(proveRefundOnlyUnshipped(jlTracking), false);
});

test('旧决定只有分支文案但没有逐子订单证明时仍禁止自动执行', () => {
  const refundOnlyData = {
    ticket: { afterSaleReason: '多拍/拍错/不想要' },
  };

  assert.equal(shouldAutoExecute(refundOnlyDecision(), refundOnlyData, { type: '仅退款' }), false);
});

test('生产自动执行只由共享扫描链路持有新分支门禁，重查不得再复制一套', () => {
  const directGateFiles = [
    '../../lib/server/pipeline.js',
    '../../scripts/jl-steps/14-process-single-account-fixed-batch.js',
  ];

  for (const relative of directGateFiles) {
    const source = fs.readFileSync(path.join(__dirname, relative), 'utf8');
    assert.doesNotMatch(source, /auto-exec-confidence/);
    assert.match(source, /after-sales-auto-gate/);
  }

  const reprocessSource = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');
  assert.doesNotMatch(reprocessSource, /auto-exec-confidence/);
  assert.doesNotMatch(reprocessSource, /require\(['"]\.\.\/server\/after-sales-auto-gate['"]\)/);
  assert.match(reprocessSource, /step14\.loadDefaultDependencies\(\)/);
  assert.match(reprocessSource, /step14\.processOpenedDetailAndPersist/);
});

test('反馈和重算接口不再更新旧置信文件', () => {
  const source = fs.readFileSync(path.join(__dirname, '../../lib/server/routes.js'), 'utf8');

  assert.doesNotMatch(source, /require\(['"]\.\/auto-exec-confidence['"]\)/);
  assert.doesNotMatch(source, /confidence\.(onFeedback|recalculate|getAllScenes)/);
  assert.match(source, /summarizeHistory/);

  const serverSource = fs.readFileSync(path.join(__dirname, '../../server.js'), 'utf8');
  assert.doesNotMatch(serverSource, /初始化 auto-exec-confidence\.json/);
});
