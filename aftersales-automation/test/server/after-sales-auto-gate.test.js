'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { shouldAutoExecute } = require('../../lib/server/after-sales-auto-gate');

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

test('旧置信文件的 auto 状态不参与新门禁', () => {
  const refundOnlyDecision = {
    action: 'approve',
    reason: '全部未发货',
    rulesApplied: [{ doc: 'flow-5.2', section: 'Step4', summary: '主商品+赠品未发货→同意退款' }],
    warnings: [],
  };
  const refundOnlyData = {
    ticket: { afterSaleReason: '多拍/拍错/不想要' },
  };

  assert.equal(shouldAutoExecute(refundOnlyDecision, refundOnlyData, { type: '仅退款' }), false);
});

test('所有生产自动执行入口都使用新分支门禁，不再读取旧置信模块', () => {
  const files = [
    '../../lib/server/pipeline.js',
    '../../lib/server/op-queue.js',
    '../../scripts/jl-steps/14-process-single-account-fixed-batch.js',
  ];

  for (const relative of files) {
    const source = fs.readFileSync(path.join(__dirname, relative), 'utf8');
    assert.doesNotMatch(source, /auto-exec-confidence/);
    assert.match(source, /after-sales-auto-gate/);
  }
});

test('反馈和重算接口不再更新旧置信文件', () => {
  const source = fs.readFileSync(path.join(__dirname, '../../lib/server/routes.js'), 'utf8');

  assert.doesNotMatch(source, /require\(['"]\.\/auto-exec-confidence['"]\)/);
  assert.doesNotMatch(source, /confidence\.(onFeedback|recalculate|getAllScenes)/);
  assert.match(source, /summarizeHistory/);

  const serverSource = fs.readFileSync(path.join(__dirname, '../../server.js'), 'utf8');
  assert.doesNotMatch(serverSource, /初始化 auto-exec-confidence\.json/);
});
