'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const PROJECT_ROOT = path.join(__dirname, '../..');
const AFTER_SALE_LIST_URL = 'https://scrm.jlsupp.com/micro-customer/business/after-sale-list';

test('04 注入后固定导航售后列表，不原地 reload 旧 URL', () => {
  const source = fs.readFileSync(
    path.join(PROJECT_ROOT, 'scripts/jl-steps/04-inject.js'),
    'utf8'
  );
  const start = source.indexOf('async function inject(');
  const end = source.indexOf('if (require.main === module)');
  assert.notEqual(start, -1, '找不到 inject 函数');
  assert.notEqual(end, -1, '找不到 inject 函数结束边界');
  const injectSource = source.slice(start, end);

  assert.match(source, /const AFTER_SALE_LIST_URL = ['"]https:\/\/scrm\.jlsupp\.com\/micro-customer\/business\/after-sale-list['"];/);
  assert.match(injectSource, /await cdp\.navigate\(targetId, AFTER_SALE_LIST_URL\)/);
  assert.doesNotMatch(injectSource, /cdp\.reload\(/);
  assert.match(injectSource, /matchShopName\(judged\.shopName, note\)/);
});

test('04 使用显式 targetId 时只选择已清理的目标 tab', () => {
  const injectModule = require('../../scripts/jl-steps/04-inject');

  assert.equal(typeof injectModule.resolveInjectionTargetId, 'function');
  assert.equal(
    injectModule.resolveInjectionTargetId('cleaned-tab', [
      { id: 'other-tab', type: 'page', url: 'https://scrm.jlsupp.com/other' },
      { id: 'cleaned-tab', type: 'page', url: 'https://scrm.jlsupp.com/login' },
    ]),
    'cleaned-tab'
  );
});

test('04 独立调用未传 targetId 时只接受唯一鲸灵 tab', () => {
  const injectModule = require('../../scripts/jl-steps/04-inject');
  const oneTab = [
    { id: 'only-tab', type: 'page', url: 'https://scrm.jlsupp.com/login' },
  ];
  const multipleTabs = [
    ...oneTab,
    { id: 'second-tab', type: 'page', url: 'https://scrm.jlsupp.com/work-order/2' },
  ];

  assert.equal(typeof injectModule.resolveInjectionTargetId, 'function');
  assert.equal(injectModule.resolveInjectionTargetId(null, oneTab), 'only-tab');
  assert.throws(
    () => injectModule.resolveInjectionTargetId(null, multipleTabs),
    /多个鲸灵 tab.*targetId/
  );
});

test('11 对指定 targetId 直接导航售后列表，再校验、排序和读取', async () => {
  const cdp = require('../../lib/cdp');
  const preparePath = require.resolve('../../scripts/jl-steps/11-prepare-after-sale-list');
  const menuPath = require.resolve('../../scripts/jl-steps/08-click-after-sale-menu');
  const sortPath = require.resolve('../../scripts/jl-steps/09-select-overdue-sort');
  const readPath = require.resolve('../../scripts/jl-steps/10-read-urgent-after-sale-list');
  const original = {
    prepare: require.cache[preparePath],
    menu: require.cache[menuPath],
    sort: require.cache[sortPath],
    read: require.cache[readPath],
    navigate: cdp.navigate,
    eval: cdp.eval,
    setTimeout: global.setTimeout,
  };
  const calls = [];

  try {
    require.cache[menuPath] = {
      id: menuPath,
      filename: menuPath,
      loaded: true,
      exports: {
        clickAfterSaleMenu: async () => {
          throw new Error('扫描准备不应依赖步骤 08 首页菜单');
        },
      },
    };
    require.cache[sortPath] = {
      id: sortPath,
      filename: sortPath,
      loaded: true,
      exports: {
        TARGET_SORT: '按逾期时间最近排序',
        selectOverdueSort: async options => {
          calls.push(['sort', options]);
          return { success: true, targetId: options.targetId };
        },
      },
    };
    require.cache[readPath] = {
      id: readPath,
      filename: readPath,
      loaded: true,
      exports: {
        isAscendingByTotalHours: () => true,
        readUrgentAfterSaleList: async options => {
          calls.push(['read', options]);
          return { success: true, urgent: [] };
        },
      },
    };
    cdp.navigate = async (targetId, url) => {
      calls.push(['navigate', targetId, url]);
      return { success: true };
    };
    cdp.eval = async (_targetId, expression) => {
      if (expression.includes('hasPendingFilter')) {
        calls.push(['ready', _targetId]);
        return { success: true, hasTitle: true, hasPendingFilter: true };
      }
      calls.push(['sortCheck', _targetId]);
      return { sortValue: '按逾期时间最近排序', tickets: [] };
    };
    global.setTimeout = callback => {
      callback();
      return 0;
    };
    delete require.cache[preparePath];

    const { prepareAfterSaleList } = require(preparePath);
    const result = await prepareAfterSaleList({ targetId: 'account-tab', thresholdHours: 36 });

    assert.equal(result.success, true);
    assert.equal(result.targetId, 'account-tab');
    assert.deepEqual(calls, [
      ['navigate', 'account-tab', AFTER_SALE_LIST_URL],
      ['ready', 'account-tab'],
      ['sort', { targetId: 'account-tab' }],
      ['sortCheck', 'account-tab'],
      ['read', { targetId: 'account-tab', thresholdHours: 36 }],
    ]);
  } finally {
    cdp.navigate = original.navigate;
    cdp.eval = original.eval;
    global.setTimeout = original.setTimeout;
    for (const [modulePath, cached] of [
      [preparePath, original.prepare],
      [menuPath, original.menu],
      [sortPath, original.sort],
      [readPath, original.read],
    ]) {
      if (cached) require.cache[modulePath] = cached;
      else delete require.cache[modulePath];
    }
  }
});
