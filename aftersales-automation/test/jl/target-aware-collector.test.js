'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { inferDecision } = require('../../lib/infer');

const {
  collectTicketTargetAware,
  resolveUniqueErpTargetId,
} = require('../../lib/jl/target-aware-collector');

const WORK_ORDER = '100001781188621717210';

function ok(data) {
  return { success: true, data };
}

test('采集全程显式绑定详情tab和ERP tab，不选择任意鲸灵tab', async () => {
  const calls = [];
  const dependencies = {
    readTicket: async (targetId, workOrderNum) => {
      calls.push(['readTicket', targetId, workOrderNum]);
      return ok({
        subOrders: [{ id: 'sub-1', sku: 'sku-1', attr1: '红', afterSaleNum: 1 }],
        gifts: [],
        subBizType: '仅退款',
      });
    },
    getLogistics: async (targetId, workOrderNum) => {
      calls.push(['getLogistics', targetId, workOrderNum]);
      return ok({ packages: [] });
    },
    erpSearch: async (targetId, subOrderId) => {
      calls.push(['erpSearch', targetId, subOrderId]);
      return ok({ subOrderId, rows: [] });
    },
    readAllErpLogistics: async targetId => {
      calls.push(['readAllErpLogistics', targetId]);
      return ok({ results: [] });
    },
    erpAftersale: async () => assert.fail('无退货单号不应查ERP售后'),
    productMatch: async () => assert.fail('仅退款不应查商品对应表'),
    productArchive: async () => assert.fail('仅退款不应查商品档案'),
    getErpShop: () => assert.fail('仅退款不需要ERP店铺映射'),
  };

  const result = await collectTicketTargetAware({
    detailTargetId: 'detail-tab',
    erpTargetId: 'erp-tab',
    workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS',
    type: '仅退款',
  }, dependencies);

  assert.deepEqual(calls, [
    ['readTicket', 'detail-tab', WORK_ORDER],
    ['erpSearch', 'erp-tab', 'sub-1'],
    ['readAllErpLogistics', 'erp-tab'],
    ['getLogistics', 'detail-tab', WORK_ORDER],
  ]);
  assert.equal(result.ticket.subOrders[0].id, 'sub-1');
  assert.deepEqual(result.collectErrors, ['product-detail: 跳过（工单类型=仅退款，无需核对商品明细）', 'erp-aftersale: 无退货快递单号，跳过']);
});

test('仅退款依次采集全部赠品子订单及其ERP物流', async () => {
  const calls = [];
  const dependencies = {
    readTicket: async () => ok({
      subOrders: [{ id: 'main-1' }],
      gifts: [{ id: 'gift-1' }, { id: 'gift-2' }],
      subBizType: '仅退款',
    }),
    erpSearch: async (_targetId, subOrderId) => {
      calls.push(['erpSearch', subOrderId]);
      return ok({ rows: { rows: [{ status: '待审核' }] } });
    },
    readAllErpLogistics: async () => {
      calls.push(['erpLogistics']);
      return ok({ results: [] });
    },
    getLogistics: async () => ok({ packages: [] }),
    erpAftersale: async () => assert.fail('无退货单号不应查ERP售后'),
    productMatch: async () => assert.fail('仅退款不应查商品对应表'),
    productArchive: async () => assert.fail('仅退款不应查商品档案'),
    getErpShop: () => assert.fail('仅退款不需要ERP店铺映射'),
  };

  const result = await collectTicketTargetAware({
    detailTargetId: 'detail-tab',
    erpTargetId: 'erp-tab',
    workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS',
    type: '仅退款',
  }, dependencies);

  assert.deepEqual(
    calls.filter(call => call[0] === 'erpSearch').map(call => call[1]),
    ['main-1', 'gift-1', 'gift-2']
  );
  assert.equal(calls.filter(call => call[0] === 'erpLogistics').length, 3);
  assert.deepEqual(result.giftErpSearches.map(item => item.subOrderId), ['gift-1', 'gift-2']);
  assert.equal(result.giftErpSearch.subOrderId, 'gift-1');
});

test('退货退款遍历全部主子订单和赠品，并复用同一ERP targetId', async () => {
  const calls = [];
  const dependencies = {
    readTicket: async () => ok({
      subOrders: [
        { id: 'sub-1', sku: 'sku-1', attr1: '红', afterSaleNum: 1 },
        { id: 'sub-2', sku: 'sku-2', attr1: '蓝', afterSaleNum: 1 },
      ],
      gifts: [{ id: 'gift-real-id', sku: 'gift-sku', attr1: '默认' }],
      returnTracking: 'SF1234567890',
      subBizType: '退货退款',
    }),
    getLogistics: async targetId => {
      calls.push(['getLogistics', targetId]);
      return ok({ packages: [] });
    },
    erpSearch: async (targetId, id) => {
      calls.push(['erpSearch', targetId, id]);
      return ok({ subOrderId: id, rows: [] });
    },
    readAllErpLogistics: async targetId => {
      calls.push(['erpLogistics', targetId]);
      return ok({ results: [{ tracking: 'x' }] });
    },
    erpAftersale: async (targetId, tracking) => {
      calls.push(['erpAftersale', targetId, tracking]);
      return ok({ rows: [] });
    },
    productMatch: async (targetId, sku, attr1, shop) => {
      calls.push(['productMatch', targetId, sku, attr1, shop]);
      return ok({ matched: true, specCode: `code-${sku}` });
    },
    productArchive: async (targetId, code) => {
      calls.push(['productArchive', targetId, code]);
      return ok({ title: code, subItems: [] });
    },
    getErpShop: note => {
      assert.equal(note, '顺链-KGOS');
      return '顺链';
    },
  };

  const result = await collectTicketTargetAware({
    detailTargetId: 'detail-tab',
    erpTargetId: 'erp-tab',
    workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS',
    type: '退货退款',
  }, dependencies);

  assert.deepEqual(
    calls.filter(call => call[0] === 'erpSearch').map(call => call[2]),
    ['sub-1', 'sub-2', 'gift-real-id']
  );
  assert.equal(calls.every(call => !['erpSearch', 'erpLogistics', 'erpAftersale', 'productMatch', 'productArchive'].includes(call[0]) || call[1] === 'erp-tab'), true);
  assert.equal(result.productMatches.length, 2);
  assert.equal(result.giftProductMatch.specCode, 'code-gift-sku');
  assert.equal(result.erpLogistics.results.length, 3);
});

test('鲸灵详情读取失败立即抛错停止批次', async () => {
  const dependencies = {
    readTicket: async () => ({ success: false, error: '详情加载失败' }),
    getLogistics: async () => assert.fail('详情失败后不应继续'),
    erpSearch: async () => assert.fail('详情失败后不应继续'),
    readAllErpLogistics: async () => assert.fail('详情失败后不应继续'),
    erpAftersale: async () => assert.fail('详情失败后不应继续'),
    productMatch: async () => assert.fail('详情失败后不应继续'),
    productArchive: async () => assert.fail('详情失败后不应继续'),
    getErpShop: () => assert.fail('详情失败后不应继续'),
  };

  await assert.rejects(collectTicketTargetAware({
    detailTargetId: 'detail-tab', erpTargetId: 'erp-tab', workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS', type: '仅退款',
  }, dependencies), /read-ticket: 详情加载失败/);
});

test('鲸灵物流读取失败立即抛错停止批次', async () => {
  const dependencies = {
    readTicket: async () => ok({ subOrders: [], gifts: [], subBizType: '仅退款' }),
    getLogistics: async () => ({ success: false, error: '物流弹窗失败' }),
    erpSearch: async () => ok({}), readAllErpLogistics: async () => ok({ results: [] }),
    erpAftersale: async () => ok({}), productMatch: async () => ok({}),
    productArchive: async () => ok({}), getErpShop: () => '顺链',
  };
  await assert.rejects(collectTicketTargetAware({
    detailTargetId: 'detail-tab', erpTargetId: 'erp-tab', workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS', type: '仅退款',
  }, dependencies), /logistics: 物流弹窗失败/);
});

test('多子订单部分ERP搜索失败使用关键错误前缀，推理不得自动批准', async () => {
  const dependencies = {
    readTicket: async () => ok({
      subOrders: [{ id: 'sub-ok' }, { id: 'sub-fail' }],
      gifts: [],
      subBizType: '仅退款',
      afterSaleReason: '多拍/拍错/不想要',
    }),
    erpSearch: async (_targetId, id) => id === 'sub-ok'
      ? ok({ rows: { rows: [{ status: '待审核' }] } })
      : { success: false, error: '搜索失败' },
    readAllErpLogistics: async () => ok({ results: [] }),
    getLogistics: async () => ok({ packages: [] }),
    erpAftersale: async () => assert.fail('无退货单号'),
    productMatch: async () => assert.fail('仅退款不查商品'),
    productArchive: async () => assert.fail('仅退款不查商品'),
    getErpShop: () => assert.fail('仅退款不查店铺'),
  };
  const collected = await collectTicketTargetAware({
    detailTargetId: 'detail-tab', erpTargetId: 'erp-tab', workOrderNum: WORK_ORDER,
    accountNote: '顺链-KGOS', type: '仅退款',
  }, dependencies);
  const decision = inferDecision({ collectedData: collected }, { type: '仅退款' });

  assert.equal(collected.collectErrors.some(error => error.startsWith('erp-search:')), true);
  assert.equal(decision.action, 'escalate');
});

test('缺少显式详情或ERP targetId时拒绝采集', async () => {
  await assert.rejects(
    collectTicketTargetAware({ erpTargetId: 'erp-tab', workOrderNum: WORK_ORDER }, {}),
    /detailTargetId/
  );
  await assert.rejects(
    collectTicketTargetAware({ detailTargetId: 'detail-tab', workOrderNum: WORK_ORDER }, {}),
    /erpTargetId/
  );
});

test('ERP tab存在多个候选时选择其中一个并锁定，显式指定仍校验', async () => {
  const targets = [
    { id: 'jl-tab', type: 'page', url: 'https://scrm.jlsupp.com/a' },
    { id: 'erp-1', type: 'page', url: 'https://viperp.superboss.cc/a' },
    { id: 'erp-2', type: 'page', url: 'https://viperp.superboss.cc/b' },
  ];

  assert.equal(await resolveUniqueErpTargetId({ getTargets: async () => targets }), 'erp-1');
  assert.equal(await resolveUniqueErpTargetId({ getTargets: async () => targets }, 'erp-2'), 'erp-2');
  await assert.rejects(resolveUniqueErpTargetId({ getTargets: async () => targets }, 'missing'), /指定ERP标签页不存在/);
});

test('ERP tab缺失时自动创建并锁定新target', async () => {
  const calls = [];
  const targetId = await resolveUniqueErpTargetId({
    getTargets: async () => [],
    createTarget: async url => {
      calls.push(['createTarget', url]);
      return { id: 'erp-created', type: 'page', url };
    },
    activateTarget: async id => calls.push(['activateTarget', id]),
  });

  assert.equal(targetId, 'erp-created');
  assert.deepEqual(calls, [
    ['createTarget', 'https://viperp.superboss.cc'],
    ['activateTarget', 'erp-created'],
  ]);
});
