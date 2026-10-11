'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { inferDecision } = require('../../lib/infer');

function loadActionPage({ queueItems = [], simulations = [], dismissed = {} } = {}) {
  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const elements = new Map();
  const context = {
    SHIPPED_STATUSES: ['卖家已发货', '交易成功', '交易关闭'],
    h: value => String(value ?? ''),
    formatCountdown: () => null,
    document: { getElementById(id) {
      if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '' });
      return elements.get(id);
    } },
    api: async route => {
      if (route === '/queue?mode=live') return { items: queueItems };
      if (route === '/simulations?mode=live') return simulations;
      if (route === '/action-dismissed') return dismissed;
      throw new Error(`Unexpected API: ${route}`);
    },
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function extractBrand('), source.indexOf('function copyFromBtn(')), context);
  return { context, elements };
}

function returnFixture({ hasRows = true, urgent = false, field } = {}) {
  const summary = `${hasRows ? '有记录' : ''}未入库+剩余${urgent ? '≤12h→拒绝' : '>12h→等待重查'}`;
  const item = { id: 'q-return', workOrderNum: 'WO-RETURN', type: '退货退款', status: urgent ? 'simulated' : 'waiting', accountNum: 1, accountNote: '店铺-测试品牌', urgency: urgent ? '3小时' : '1天' };
  const sim = {
    id: 'sim-return', queueItemId: item.id, mode: 'live',
    collectedData: {
      ticket: { afterSaleReason: '七天无理由退货（不喜欢/不合适）', returnTracking: 'RETURN-001', gifts: [] },
      erpAftersale: { rows: hasRows ? [{ goodsStatus: '待商家收货' }] : [] },
      collectErrors: [],
    },
    decision: {
      action: 'reject', waitingRescan: !urgent,
      ...(urgent ? { reasonCode: 'WAREHOUSE_NOT_RECEIVED' } : {}),
      reason: '展示文案可任意修改', rulesApplied: [{ summary }],
      ...(field === undefined ? {} : { courierActions: field }),
    },
  };
  return { item, sim };
}

for (const hasRows of [false, true]) {
  for (const urgent of [false, true]) {
    test(`新推理：${hasRows ? '有ERP记录未收货' : '无入库记录'}，${urgent ? '时效不足' : '等待重查'}仍生成退货待入库`, () => {
      const { item, sim } = returnFixture({ hasRows, urgent });
      const decision = inferDecision(sim, item);
      assert.deepEqual(decision.courierActions.map(action => [action.type, action.tracking, action.status]), [
        ['return_wait', 'RETURN-001', 'waiting_receipt'],
      ]);
      assert.equal(decision.waitingRescan === true, !urgent);
    });
  }
}

for (const field of [undefined, []]) {
  test(`旧记录${field === undefined ? '无行动字段' : '行动为空'}：等待重查工单显示在面板并计入徽章`, async () => {
    const { item, sim } = returnFixture({ field });
    const { context, elements } = loadActionPage({ queueItems: [item], simulations: [sim] });
    await context.loadActionList();
    assert.match(elements.get('action-content').innerHTML, /退货待入库/);
    assert.match(elements.get('action-content').innerHTML, /RETURN-001/);
    assert.match(elements.get('action-content').innerHTML, /WO-RETURN/);
    assert.equal(elements.get('action-count').textContent, 1);
    await context.loadActionBadge();
    assert.equal(elements.get('action-tab-count').textContent, 1);
  });
}

test('人工标记只进入已处理区域，不虚构新的待办或修改旧 simulation', async () => {
  const { item, sim } = returnFixture();
  const original = JSON.stringify(sim);
  const { context, elements } = loadActionPage({ queueItems: [item], simulations: [sim], dismissed: { 'RETURN-001': { type: 'return' } } });
  await context.loadActionList();
  assert.equal(elements.get('action-count').textContent, 0);
  assert.match(elements.get('action-content').innerHTML, /已标记处理 \(1\)/);
  assert.equal(JSON.stringify(sim), original);
});

test('入库核验异常即使有退货单号，也不归入退货待入库', async () => {
  const { item, sim } = returnFixture();
  item.status = 'simulated';
  sim.decision = { action: 'escalate', waitingRescan: true, reason: '文案包含在途和拦截也不能生成行动', rulesApplied: [{ summary: '退货异常→上报人工' }], courierActions: [] };
  const { context, elements } = loadActionPage({ queueItems: [item], simulations: [sim] });
  await context.loadActionList();
  assert.equal(elements.get('action-count').textContent, 0);
});

test('自动退款的未揽收运单仍显示，有退回物流的候选被统一过滤', async () => {
  const item = { id: 'q-auto', status: 'auto_executed', type: '仅退款', workOrderNum: 'WO-AUTO' };
  const sim = { queueItemId: item.id, collectedData: { ticket: {} }, decision: { action: 'approve', courierActions: [
    { type: 'intercept', tracking: 'NOT-PICKED-001', status: 'not_picked_up' },
    { type: 'intercept', tracking: 'RETURNED-002', status: 'returned' },
  ] } };
  const { context, elements } = loadActionPage({ queueItems: [item], simulations: [sim] });
  await context.loadActionList();
  const html = elements.get('action-content').innerHTML;
  assert.match(html, /NOT-PICKED-001/);
  assert.match(html, /已自动处理/);
  assert.doesNotMatch(html, /RETURNED-002/);
  assert.equal(elements.get('action-count').textContent, 1);
});

test('行动里的待入库工单跳转到等待重查卡片，不触发平台操作', async () => {
  const { item, sim } = returnFixture();
  const { context, elements } = loadActionPage({ queueItems: [item], simulations: [sim] });
  const activated = [];
  let scrolled = false;
  const card = { style: { outline: '', outlineOffset: '' }, scrollIntoView: () => { scrolled = true; } };
  elements.set('card-' + item.id, card);
  context.activateTab = async tab => { activated.push(tab); };
  context.liveTabStoreFilters = { waiting: 'some-store' };
  context.setTimeout = fn => fn();
  context.showToast = message => assert.fail(message);
  await context.jumpToActionWorkOrder(item.id);
  assert.deepEqual(activated, ['waiting-tab']);
  assert.equal(context.liveTabStoreFilters.waiting, 'all');
  assert.equal(scrolled, true);
  assert.equal(card.style.outline, '');
});
