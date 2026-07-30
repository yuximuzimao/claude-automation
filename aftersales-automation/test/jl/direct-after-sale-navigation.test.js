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

test('11 售后列表首次未渲染时持续只读等待，稍后就绪则继续', async () => {
  const cdp = require('../../lib/cdp');
  const preparePath = require.resolve('../../scripts/jl-steps/11-prepare-after-sale-list');
  const originalEval = cdp.eval;
  const statuses = [
    { success: false, hasTitle: false, hasPendingFilter: false },
    { success: false, hasTitle: true, hasPendingFilter: false },
    { success: true, hasTitle: true, hasPendingFilter: true },
  ];
  const sleepCalls = [];

  try {
    cdp.eval = async () => statuses.shift();
    delete require.cache[preparePath];
    const { assertAfterSaleListReady } = require(preparePath);

    const result = await assertAfterSaleListReady('slow-tab', {
      maxAttempts: 3,
      intervalMs: 750,
      sleep: async ms => sleepCalls.push(ms),
    });

    assert.equal(result.success, true);
    assert.deepEqual(sleepCalls, [750, 750]);
    assert.equal(statuses.length, 0);
  } finally {
    cdp.eval = originalEval;
    delete require.cache[preparePath];
  }
});

test('11 售后列表持续未渲染时到达上限仍安全失败', async () => {
  const cdp = require('../../lib/cdp');
  const preparePath = require.resolve('../../scripts/jl-steps/11-prepare-after-sale-list');
  const originalEval = cdp.eval;
  const sleepCalls = [];
  let evalCalls = 0;

  try {
    cdp.eval = async () => {
      evalCalls += 1;
      return {
        success: false,
        title: '鲸灵商家后台',
        url: AFTER_SALE_LIST_URL,
        hasTitle: false,
        hasPendingFilter: false,
      };
    };
    delete require.cache[preparePath];
    const { assertAfterSaleListReady } = require(preparePath);

    await assert.rejects(
      assertAfterSaleListReady('stuck-tab', {
        maxAttempts: 3,
        intervalMs: 500,
        sleep: async ms => sleepCalls.push(ms),
      }),
      /未到售后列表页:.*"hasTitle":false.*"hasPendingFilter":false/
    );

    assert.equal(evalCalls, 3);
    assert.deepEqual(sleepCalls, [500, 500]);
  } finally {
    cdp.eval = originalEval;
    delete require.cache[preparePath];
  }
});

test('11 将“排序值正确但列表乱序”标记为可刷新恢复的瞬时异常', async () => {
  const cdp = require('../../lib/cdp');
  const preparePath = require.resolve('../../scripts/jl-steps/11-prepare-after-sale-list');
  const originalEval = cdp.eval;

  try {
    cdp.eval = async () => ({
      sortValue: '按逾期时间最近排序',
      tickets: [
        { workOrderNum: '100001700000000000001', totalHours: 42 },
        { workOrderNum: '100001700000000000002', totalHours: 40 },
      ],
    });
    delete require.cache[preparePath];
    const {
      readCurrentPageSortCheck,
      SORT_ORDER_UNSTABLE_CODE,
    } = require(preparePath);

    await assert.rejects(
      readCurrentPageSortCheck('mixed-list-tab'),
      error => {
        assert.equal(error.code, SORT_ORDER_UNSTABLE_CODE);
        assert.equal(error.sortCheck.sortOk, true);
        assert.equal(error.sortCheck.ascending, false);
        return true;
      }
    );
  } finally {
    cdp.eval = originalEval;
    delete require.cache[preparePath];
  }
});

test('11 排序校验从倒计时组件读取文本，不依赖“后自动”文案', () => {
  const source = fs.readFileSync(
    path.join(PROJECT_ROOT, 'scripts/jl-steps/11-prepare-after-sale-list.js'),
    'utf8'
  );
  const start = source.indexOf('async function readCurrentPageSortCheck');
  const end = source.indexOf('\nasync function verifySortWithRefreshRecovery', start);
  assert.notEqual(start, -1);
  assert.notEqual(end, -1);

  const body = source.slice(start, end);
  assert.match(body, /querySelectorAll\(['"]\.el-timer['"]\)/);
  assert.doesNotMatch(body, /后自动/);
});

test('11 瞬时乱序时等待2秒、只刷新一次并在页面就绪后复核', async () => {
  const {
    verifySortWithRefreshRecovery,
    SORT_ORDER_UNSTABLE_CODE,
    SORT_RECOVERY_WAIT_MS,
  } = require('../../scripts/jl-steps/11-prepare-after-sale-list');
  const calls = [];
  let checkCount = 0;

  const result = await verifySortWithRefreshRecovery('mixed-list-tab', {
    sleep: async ms => calls.push(['sleep', ms]),
    reload: async targetId => calls.push(['reload', targetId]),
    assertReady: async targetId => calls.push(['ready', targetId]),
    readSortCheck: async targetId => {
      calls.push(['check', targetId]);
      checkCount += 1;
      if (checkCount === 1) {
        const error = new Error('排序校验失败');
        error.code = SORT_ORDER_UNSTABLE_CODE;
        throw error;
      }
      return {
        sortValue: '按逾期时间最近排序',
        ascending: true,
        tickets: [],
      };
    },
  });

  assert.deepEqual(calls, [
    ['check', 'mixed-list-tab'],
    ['sleep', SORT_RECOVERY_WAIT_MS],
    ['reload', 'mixed-list-tab'],
    ['ready', 'mixed-list-tab'],
    ['sleep', SORT_RECOVERY_WAIT_MS],
    ['check', 'mixed-list-tab'],
  ]);
  assert.equal(result.recoveredByRefresh, true);
  assert.equal(result.ascending, true);
});

test('11 排序值错误时不刷新、不重试排序校验', async () => {
  const {
    verifySortWithRefreshRecovery,
  } = require('../../scripts/jl-steps/11-prepare-after-sale-list');
  const calls = [];
  const mismatch = new Error('排序校验失败');
  mismatch.code = 'SORT_VALUE_MISMATCH';

  await assert.rejects(
    verifySortWithRefreshRecovery('wrong-sort-tab', {
      sleep: async ms => calls.push(['sleep', ms]),
      reload: async targetId => calls.push(['reload', targetId]),
      assertReady: async targetId => calls.push(['ready', targetId]),
      readSortCheck: async targetId => {
        calls.push(['check', targetId]);
        throw mismatch;
      },
    }),
    error => error === mismatch
  );

  assert.deepEqual(calls, [['check', 'wrong-sort-tab']]);
});

test('11 刷新复核后仍乱序时安全停止，禁止循环刷新', async () => {
  const {
    verifySortWithRefreshRecovery,
    SORT_ORDER_UNSTABLE_CODE,
  } = require('../../scripts/jl-steps/11-prepare-after-sale-list');
  let checkCount = 0;
  let reloadCount = 0;

  await assert.rejects(
    verifySortWithRefreshRecovery('still-mixed-tab', {
      sleep: async () => {},
      reload: async () => {
        reloadCount += 1;
      },
      assertReady: async () => {},
      readSortCheck: async () => {
        checkCount += 1;
        const error = new Error('排序校验失败');
        error.code = SORT_ORDER_UNSTABLE_CODE;
        throw error;
      },
    }),
    /排序校验失败/
  );

  assert.equal(checkCount, 2);
  assert.equal(reloadCount, 1);
});

test('A1 单笔入口统一使用排序刷新恢复门禁', () => {
  const source = fs.readFileSync(
    path.join(PROJECT_ROOT, 'lib/server/op-queue.js'),
    'utf8'
  );
  const recoveryCalls = source.match(/step11\.verifySortWithRefreshRecovery\(listTargetId\)/g) || [];

  assert.equal(recoveryCalls.length, 3);
  assert.doesNotMatch(source, /step11\.readCurrentPageSortCheck\(listTargetId\)/);
});
