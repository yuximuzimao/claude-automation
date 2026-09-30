'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { inferDecision } = require('../../lib/infer');

function collectedGiftReturn(rowOverrides = {}) {
  return {
    ticket: {
      workOrderStatus: '待处理',
      afterSaleReason: '七天无理由退货',
      returnTracking: 'RETURN-1',
      subOrders: [{ id: 'MAIN-1', afterSaleNum: 1 }],
      gifts: [{ id: 'GIFT-1' }],
    },
    productArchives: [{
      subOrderId: 'MAIN-1',
      subItems: [{ name: '主商品', specCode: 'SPEC-MAIN', qty: 1 }],
    }],
    productMatches: [{ subOrderId: 'MAIN-1', matched: true }],
    giftProductArchive: {
      subItems: [{ name: '赠品', specCode: 'SPEC-GIFT', qty: 1 }],
    },
    giftErpSearches: [{
      subOrderId: 'GIFT-1',
      rows: {
        rows: [{
          status: '待打印快递单',
          tracking: null,
          trackings: [],
          ...rowOverrides,
        }],
      },
    }],
    erpAftersale: {
      rows: [{
        erpOrderId: 'ERP-AFTER-1',
        tracking: 'RETURN-1',
        goodsStatus: '卖家已收到退货',
        returnQty: 1,
        items: [{ name: '主商品', specCode: 'SPEC-MAIN', qtyGood: 1, qtyBad: 0 }],
      }],
    },
    collectErrors: [],
  };
}

function infer(collectedData) {
  return inferDecision(
    { mode: 'live', collectedData },
    { type: '退货退款', source: 'scan' },
  );
}

test('赠品待打印快递单且无单号时视为未发货，不要求客户退回赠品', () => {
  const decision = infer(collectedGiftReturn());

  assert.equal(decision.action, 'approve');
  assert.doesNotMatch(decision.reason, /赠品|SPEC-GIFT|退货数量不足/);
  assert.ok(decision.steps.some(step =>
    step.condition === '赠品是否实际发出' && String(step.result).includes('否（待打印快递单，无快递单号）')
  ));
});

test('赠品待打印但已有快递单号时不能按未发货排除，缺少赠品仍上报', () => {
  const decision = infer(collectedGiftReturn({
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  }));

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /主品已完整退回/);
  assert.match(decision.reason, /整套赠品未随本次退货入库/);
  assert.match(decision.reason, /赠品1个包裹暂无可核验物流状态/);
  assert.doesNotMatch(decision.reason, /退货数量不足/);
});

test('赠品已发货状态即使无单号也不能按明确未发货排除', () => {
  const decision = infer(collectedGiftReturn({ status: '卖家已发货' }));

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /主品已完整退回/);
  assert.match(decision.reason, /整套赠品未随本次退货入库/);
  assert.match(decision.reason, /赠品未取得可核验运单号/);
  assert.doesNotMatch(decision.reason, /退货数量不足/);
});

test('整套赠品未入库且赠品已签收未退回时，最终原因直接展示赠品物流状态', () => {
  const data = collectedGiftReturn({
    status: '交易成功',
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  });
  data.giftProductArchive.subItems = [
    { name: '赠品A', specCode: 'SPEC-GIFT-A', qty: 1 },
    { name: '赠品B', specCode: 'SPEC-GIFT-B', qty: 1 },
  ];
  data.erpLogistics = {
    results: [{
      tracking: 'GIFT-TRACK-1',
      logisticsText: '2026-09-30 13:13:02 您的快件已投递，收件人:档口',
    }],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /主品已完整退回/);
  assert.match(decision.reason, /整套赠品未随本次退货入库/);
  assert.match(decision.reason, /赠品1个包裹已签收，暂无退回证据/);
  assert.doesNotMatch(decision.reason, /赠品A|赠品B|退货数量不足/);
  assert.ok(decision.steps.some(step =>
    step.condition === '[赠品物流]GIFT-TRACK-1'
    && /已签收/.test(String(step.result))
    && /未识别到明确退回证据/.test(String(step.result))
  ));
});

test('只缺赠品中的一部分时仍列具体缺失商品，不误写成整套赠品未退', () => {
  const data = collectedGiftReturn({
    status: '交易成功',
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  });
  data.giftProductArchive.subItems = [
    { name: '赠品A', specCode: 'SPEC-GIFT-A', qty: 1 },
    { name: '赠品B', specCode: 'SPEC-GIFT-B', qty: 1 },
  ];
  data.erpAftersale.rows[0].returnQty = 2;
  data.erpAftersale.rows[0].items.push({
    name: '赠品A',
    specCode: 'SPEC-GIFT-A',
    qtyGood: 1,
    qtyBad: 0,
  });
  data.erpLogistics = {
    results: [{
      tracking: 'GIFT-TRACK-1',
      logisticsText: '2026-09-30 13:13:02 您的快件已投递，收件人:档口',
    }],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.match(decision.reason, /赠品B/);
  assert.match(decision.reason, /退货数量不足/);
  assert.doesNotMatch(decision.reason, /整套赠品未随本次退货入库/);
});

test('赠品未入库但全部包裹已退回签收时允许人工确认后同意退款', () => {
  const data = collectedGiftReturn();
  data.giftErpSearches[0].rows.rows = [{
    status: '交易关闭',
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1', 'GIFT-TRACK-2'],
  }];
  data.erpLogistics = {
    results: [
      { tracking: 'GIFT-TRACK-1', logisticsText: '2026-09-29 15:41 已退回签收' },
      { tracking: 'GIFT-TRACK-2', logisticsText: '2026-09-29 16:10 已退回签收' },
    ],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(decision.recommendedActionLabel, '同意退款');
  assert.match(decision.reason, /主品已完整退回/);
  assert.match(decision.reason, /赠品2个包裹均已退回签收/);
  assert.match(decision.reason, /实际退回商品不存在少退/);
  assert.match(decision.reason, /人工确认后可同意退款/);
  assert.doesNotMatch(decision.reason, /退货数量不足/);
  assert.ok(decision.steps.some(step => step.label === '赠品发货包裹' && /共2个运单/.test(String(step.value))));
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-1' && /已退回签收/.test(String(step.result))));
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-2' && /已退回签收/.test(String(step.result))));
  assert.ok(decision.steps.some(step => step.label === '赠品发货物流观察' && /2\/2个包裹已退回签收/.test(String(step.value)) && /不改变自动放行条件/.test(String(step.value))));
});

test('赠品多包裹只有部分识别到退回时逐包裹保留差异', () => {
  const data = collectedGiftReturn();
  data.giftErpSearches[0].rows.rows = [{
    status: '交易关闭',
    trackings: ['GIFT-TRACK-1', 'GIFT-TRACK-2'],
  }];
  data.erpLogistics = {
    results: [
      { tracking: 'GIFT-TRACK-1', logisticsText: '2026-09-29 15:41 已退回签收' },
      { tracking: 'GIFT-TRACK-2', logisticsText: '2026-09-29 15:50 快件正在运输中' },
    ],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-1' && /已退回签收/.test(String(step.result))));
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-2' && /未识别到明确退回证据/.test(String(step.result))));
  assert.ok(decision.steps.some(step => step.label === '赠品发货物流观察' && /1\/2个包裹/.test(String(step.value))));
});

test('赠品全部包裹已进入退回途中或到达商家仓库时也允许人工确认后同意退款', () => {
  const data = collectedGiftReturn();
  data.giftErpSearches[0].rows.rows = [{
    status: '交易关闭',
    trackings: ['GIFT-TRACK-1', 'GIFT-TRACK-2'],
  }];
  data.erpLogistics = {
    results: [
      { tracking: 'GIFT-TRACK-1', logisticsText: '2026-09-29 17:56:59 您的快件已被转运中心安排退回，正在退回途中' },
      { tracking: 'GIFT-TRACK-2', logisticsText: '2026-09-30 11:44:35 到达商家仓库' },
    ],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(decision.recommendedActionLabel, '同意退款');
  assert.match(decision.reason, /全部.*明确退回链路|均已进入明确退回链路/);
  assert.match(decision.reason, /人工确认后可同意退款/);
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-1' && /退回节点/.test(String(step.result))));
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-2' && /退回节点/.test(String(step.result))));
});

test('仅有等待发件人确认的退回请求不算明确退回证据', () => {
  const data = collectedGiftReturn({
    status: '交易关闭',
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  });
  data.erpLogistics = {
    results: [{ tracking: 'GIFT-TRACK-1', logisticsText: '收件人要求退回，等待发件人确认' }],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.ok(decision.steps.some(step => step.condition === '[赠品物流]GIFT-TRACK-1' && /未识别到明确退回证据/.test(String(step.result))));
});

test('赠品已经随本次退货入库时不增加赠品发货物流观察', () => {
  const data = collectedGiftReturn({
    status: '交易关闭',
    tracking: 'GIFT-TRACK-1',
    trackings: ['GIFT-TRACK-1'],
  });
  data.erpLogistics = {
    results: [{ tracking: 'GIFT-TRACK-1', logisticsText: '2026-09-29 15:41 已退回签收' }],
  };
  data.erpAftersale.rows[0].returnQty = 2;
  data.erpAftersale.rows[0].items.push({ name: '赠品', specCode: 'SPEC-GIFT', qtyGood: 1, qtyBad: 0 });

  const decision = infer(data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.steps.some(step => step.label === '赠品发货物流观察'), false);
});

test('主品与赠品含同款商品时，赠品全部退回签收不得误写成主品少退', () => {
  const data = collectedGiftReturn();
  data.productArchives[0].subItems = [{ name: '悦颜霜', specCode: 'SPEC-SAME', qty: 1 }];
  data.giftProductArchive.subItems = [{ name: '悦颜霜', specCode: 'SPEC-SAME', qty: 1 }];
  data.erpAftersale.rows[0].items = [{ name: '悦颜霜', specCode: 'SPEC-SAME', qtyGood: 1, qtyBad: 0 }];
  data.giftErpSearches[0].rows.rows = [{
    status: '交易关闭',
    trackings: ['GIFT-TRACK-1', 'GIFT-TRACK-2'],
  }];
  data.erpLogistics = {
    results: [
      { tracking: 'GIFT-TRACK-1', logisticsText: '2026-09-30 14:40:57 您的快件已退回签收' },
      { tracking: 'GIFT-TRACK-2', logisticsText: '2026-09-30 15:18:14 您的快件已退回签收' },
    ],
  };

  const decision = infer(data);

  assert.equal(decision.action, 'approve');
  assert.equal(decision.requiresHumanReview, true);
  assert.equal(decision.autoExecutionBlocked, true);
  assert.equal(decision.humanTriggeredExecutionAllowed, true);
  assert.equal(decision.recommendedActionLabel, '同意退款');
  assert.doesNotMatch(decision.reason, /退货数量不足|主品.*不足/);
  assert.match(decision.reason, /实际退回商品不存在少退/);
  assert.ok(decision.steps.some(step =>
    step.condition === '[主+赠]悦颜霜'
    && /主品期望1件，入库1件（主品完整）/.test(String(step.result))
    && /赠品另1件未在本次退货入库/.test(String(step.result))
  ));
});

test('多个赠品子订单只查到其中一个时不得把全部赠品判成未发货', () => {
  const data = collectedGiftReturn();
  data.ticket.gifts.push({ id: 'GIFT-2' });
  const decision = infer(data);

  assert.equal(decision.action, 'escalate');
  assert.equal(decision.steps.some(step => step.condition === '赠品是否实际发出'), false);
  assert.match(decision.reason, /赠品|退货里没有|退货数量不足/);
});
