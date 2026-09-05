'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  extractBaiduLogisticsCard,
  findUnconfirmedShippedTrackings,
  queryBaiduLogistics,
  supplementBaiduLogisticsIfNeeded,
} = require('../lib/external-logistics-baidu');

const TRACKING = 'YT7641388739489';
const RETURN_CARD = `
圆通速递
查询
物流追踪
2026年09月05日 下午08:38:32 最新
您的快件离开【自贡转运中心】，已发往【广州转运中心】。
2026年09月05日 下午03:32:11
您的快件已被【四川省宜宾市三江新区城区】安排退回，退回原因：客户要求退回
2026年09月05日 下午03:29:11
您的快件暂时未投递成功
圆通速递
官方电话： 95554
我要寄件
`;

function collectedData() {
  return {
    erpSearches: [{
      rows: {
        rows: [{ status: '卖家已发货', tracking: 'YT7641388201852', trackings: ['YT7641388201852'] }],
      },
    }],
    giftErpSearches: [{
      rows: {
        rows: [{ status: '卖家已发货', tracking: TRACKING, trackings: [TRACKING] }],
      },
    }],
    erpLogistics: {
      results: [
        { tracking: 'YT7641388201852', logisticsText: '退回 2026-09-05\n您的快件已被安排退回' },
        { tracking: TRACKING, logisticsText: '2026-09-05 20:38:32\n您的快件离开【自贡转运中心】，已发往【广州转运中心】' },
      ],
    },
    logistics: {
      packages: [{ text: '物流单号：\nYT7641388201852\n退回 2026-09-05\n客户要求退回' }],
    },
  };
}

test('只截取百度物流追踪卡片，不把后续普通搜索结果混入物流证据', () => {
  const pageText = `百度一下\n相关搜索\n${RETURN_CARD}\n物流编号百科里提到退回商品`;
  const card = extractBaiduLogisticsCard(pageText);
  assert.match(card, /安排退回/);
  assert.doesNotMatch(card, /物流编号百科/);
});

test('真实浏览器查询契约：命中目标搜索词后读取物流卡，并且无论成功与否都关闭临时百度页', async () => {
  const calls = [];
  const result = await queryBaiduLogistics(TRACKING, {
    createTarget: async url => {
      calls.push(['create', url]);
      return { id: 'BAIDU-TAB' };
    },
    eval: async id => {
      calls.push(['eval', id]);
      return {
        title: `${TRACKING}_百度搜索`,
        query: TRACKING,
        text: RETURN_CARD,
      };
    },
    closeTarget: async id => calls.push(['close', id]),
    sleep: async ms => calls.push(['sleep', ms]),
  });

  assert.equal(result.success, true);
  assert.equal(result.tracking, TRACKING);
  assert.equal(result.status, 'returned');
  assert.equal(result.confirmedReturn, true);
  assert.match(result.logisticsText, /安排退回/);
  assert.deepEqual(calls, [
    ['create', `https://www.baidu.com/s?wd=${TRACKING}`],
    ['sleep', 3000],
    ['eval', 'BAIDU-TAB'],
    ['sleep', 2000],
    ['close', 'BAIDU-TAB'],
  ]);
});

test('异常补证只查询现有平台/ERP没有确认退回的已发货运单', async () => {
  const cd = collectedData();
  assert.deepEqual(findUnconfirmedShippedTrackings(cd), [TRACKING]);

  const queried = [];
  const result = await supplementBaiduLogisticsIfNeeded(cd, {
    action: 'escalate',
    rulesApplied: [{ doc: 'flow-5.3', section: 'Step3-gift' }],
  }, {
    type: '仅退款',
    queryBaiduLogistics: async tracking => {
      queried.push(tracking);
      return {
        success: true,
        tracking,
        source: 'baidu',
        status: 'returned',
        confirmedReturn: true,
        logisticsText: RETURN_CARD,
      };
    },
  });

  assert.equal(result.attempted, true);
  assert.deepEqual(queried, [TRACKING]);
  assert.equal(cd.externalLogistics.results[0].confirmedReturn, true);
});

test('ERP行仍是待发货但物流已有真实揽收节点时仍可进入异常补证，等待揽收则不可', () => {
  const shipped = collectedData();
  shipped.giftErpSearches[0].rows.rows[0].status = '待发货';
  shipped.erpLogistics.results[1].logisticsText = '2026-09-05 10:00\n您的快件已揽收并离开网点';
  assert.deepEqual(findUnconfirmedShippedTrackings(shipped), [TRACKING]);

  const notPicked = collectedData();
  notPicked.giftErpSearches[0].rows.rows[0].status = '待发货';
  notPicked.erpLogistics.results[1].logisticsText = '暂无物流信息，等待揽收';
  assert.deepEqual(findUnconfirmedShippedTrackings(notPicked), []);
});

test('普通已通过决定不打开百度，保持正常路径零额外查询', async () => {
  const cd = collectedData();
  let called = false;
  const result = await supplementBaiduLogisticsIfNeeded(cd, { action: 'approve', rulesApplied: [] }, {
    type: '仅退款',
    queryBaiduLogistics: async () => {
      called = true;
      return { success: false };
    },
  });
  assert.equal(result.attempted, false);
  assert.equal(called, false);
  assert.equal(cd.externalLogistics, undefined);
});
