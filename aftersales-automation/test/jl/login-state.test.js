'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { judgeLoginState, matchShopName, shopKeyword } = require('../../lib/jl/login-state');
const { readShopName } = require('../../scripts/jl-steps/02-read-shop-name');
const { openLogin } = require('../../scripts/jl-steps/01-open-login');

const JL_HOME = 'https://scrm.jlsupp.com/micro-supplier/business/home';
const JL_LOGIN = 'https://scrm.jlsupp.com/micro-businessPlatform/login';

test('已登录：店铺名有值 → state=logged-in', () => {
  const r = judgeLoginState({ url: JL_HOME, title: '鲸灵商家后台', shopName: '杭州共途贸易有限公司', 'has商家登录': false, 'has自动注册': false });
  assert.equal(r.success, true);
  assert.equal(r.state, 'logged-in');
  assert.equal(r.loggedIn, true);
  assert.equal(r.shopName, '杭州共途贸易有限公司');
});

test('未登录确证：无店铺名 + 两句文案同时存在 → state=logged-out', () => {
  const r = judgeLoginState({ url: JL_LOGIN, title: '鲸灵商家后台', shopName: '', 'has商家登录': true, 'has自动注册': true });
  assert.equal(r.success, true);
  assert.equal(r.state, 'logged-out');
  assert.equal(r.loggedIn, false);
});

test('未知状态：无店铺名 但 只有"商家登录"缺"自动注册" → 报异常', () => {
  const r = judgeLoginState({ url: JL_LOGIN, title: 't', shopName: '', 'has商家登录': true, 'has自动注册': false });
  assert.equal(r.success, false);
  assert.match(r.error, /未知页面状态/);
});

test('未知状态：无店铺名 但 两句都缺 → 报异常（不误判为未登录）', () => {
  const r = judgeLoginState({ url: JL_LOGIN, title: 't', shopName: '', 'has商家登录': false, 'has自动注册': false });
  assert.equal(r.success, false);
  assert.match(r.error, /未知页面状态/);
});

test('未知状态：无店铺名 但 只有"自动注册"缺"商家登录" → 报异常', () => {
  const r = judgeLoginState({ url: JL_LOGIN, title: 't', shopName: '', 'has商家登录': false, 'has自动注册': true });
  assert.equal(r.success, false);
  assert.match(r.error, /未知页面状态/);
});

test('切号过渡态：店铺名=新用户时不判已登录', () => {
  const r = judgeLoginState({ url: JL_HOME, title: 't', shopName: '新用户', 'has商家登录': false, 'has自动注册': false });
  assert.equal(r.success, true);
  assert.equal(r.state, 'transitional');
  assert.equal(r.loggedIn, false);
});

test('稳定读取：新用户过渡态只在读取层等待，不暴露给业务层', async () => {
  const states = [
    { url: JL_HOME, title: 't', shopName: '新用户', 'has商家登录': false, 'has自动注册': false },
    { url: JL_HOME, title: 't', shopName: '杭州共途贸易有限公司', 'has商家登录': false, 'has自动注册': false },
  ];
  const sleeps = [];
  const result = await readShopName('tab-1', 0, {
    cdp: {
      eval: async () => JSON.stringify(states.shift()),
    },
    sleep: async ms => sleeps.push(ms),
    settleRetryMs: 10,
    settleMaxRetries: 3,
  });

  assert.equal(result.success, true);
  assert.equal(result.state, 'logged-in');
  assert.equal(result.shopName, '杭州共途贸易有限公司');
  assert.deepEqual(sleeps, [0, 10]);
  assert.equal(states.length, 0);
});

test('稳定读取：鲸灵微应用暂时空白时只读等待，随后真实店铺出现才判已登录', async () => {
  const states = [
    { url: JL_HOME, title: 't', shopName: '', 'has商家登录': false, 'has自动注册': false },
    { url: JL_HOME, title: 't', shopName: '合肥百浩创展贸易有限公司', 'has商家登录': false, 'has自动注册': false },
  ];
  const result = await readShopName('tab-2', 0, {
    cdp: {
      eval: async () => JSON.stringify(states.shift()),
    },
    sleep: async () => {},
    settleRetryMs: 10,
    settleMaxRetries: 3,
  });

  assert.equal(result.success, true);
  assert.equal(result.state, 'logged-in');
  assert.equal(result.shopName, '合肥百浩创展贸易有限公司');
});

test('稳定读取：等待期间收到停止时立即抛出AbortError，不再读取页面', async () => {
  const controller = new AbortController();
  let reads = 0;

  await assert.rejects(
    readShopName('tab-abort-wait', 8000, {
      abortSignal: controller.signal,
      cdp: {
        eval: async () => {
          reads += 1;
          return JSON.stringify({ url: JL_HOME, title: 't', shopName: '测试店铺', 'has商家登录': false, 'has自动注册': false });
        },
      },
      sleep: async () => {
        controller.abort();
      },
    }),
    error => error && error.name === 'AbortError'
  );

  assert.equal(reads, 0);
});

test('稳定读取：页面读取返回前收到停止时丢弃迟到结果，不进入账号判断', async () => {
  const controller = new AbortController();

  await assert.rejects(
    readShopName('tab-abort-read', 0, {
      abortSignal: controller.signal,
      cdp: {
        eval: async () => {
          controller.abort();
          return JSON.stringify({ url: JL_HOME, title: 't', shopName: '测试店铺', 'has商家登录': false, 'has自动注册': false });
        },
      },
      sleep: async () => {},
    }),
    error => error && error.name === 'AbortError'
  );
});

test('稳定读取：过渡态持续到上限时仍 fail-closed，不清理也不注入', async () => {
  let reads = 0;
  const result = await readShopName('tab-3', 0, {
    cdp: {
      eval: async () => {
        reads += 1;
        return JSON.stringify({ url: JL_HOME, title: 't', shopName: '新用户', 'has商家登录': false, 'has自动注册': false });
      },
    },
    sleep: async () => {},
    settleRetryMs: 10,
    settleMaxRetries: 2,
  });

  assert.equal(result.success, false);
  assert.match(result.error, /长时间停留在切号过渡态/);
  assert.equal(reads, 3);
});

test('打开登录页：about:blank 即使 complete 也继续等待真正进入鲸灵域', async () => {
  const pages = [
    { url: 'about:blank', title: '', readyState: 'complete' },
    { url: JL_LOGIN, title: '鲸灵商家后台', readyState: 'loading' },
    { url: JL_LOGIN, title: '鲸灵商家后台', readyState: 'complete' },
  ];
  let reads = 0;
  const result = await openLogin(JL_LOGIN, {
    cdp: {
      createTarget: async () => ({ id: 'new-tab' }),
      eval: async () => {
        reads += 1;
        return JSON.stringify(pages.shift());
      },
    },
    sleep: async () => {},
  });

  assert.equal(result.success, true);
  assert.equal(result.targetId, 'new-tab');
  assert.equal(result.url, JL_LOGIN);
  assert.equal(reads, 3);
});

test('打开登录页：停止发生在被动等待期间时立即中断，保留已创建tab且不再读取', async () => {
  const controller = new AbortController();
  let reads = 0;

  await assert.rejects(
    openLogin(JL_LOGIN, {
      abortSignal: controller.signal,
      cdp: {
        createTarget: async () => ({ id: 'new-tab-abort' }),
        eval: async () => {
          reads += 1;
          return JSON.stringify({ url: JL_LOGIN, title: '鲸灵商家后台', readyState: 'complete' });
        },
      },
      sleep: async () => { controller.abort(); },
    }),
    error => error && error.name === 'AbortError'
  );

  assert.equal(reads, 0);
});

test('已登录优先：真实店铺名有值时即使两句文案缺也判已登录', () => {
  const r = judgeLoginState({ url: JL_HOME, title: 't', shopName: '百浩创展', 'has商家登录': false, 'has自动注册': false });
  assert.equal(r.state, 'logged-in');
  assert.equal(r.shopName, '百浩创展');
});

test('非鲸灵域名 → success:false（防呆）', () => {
  const r = judgeLoginState({ url: 'https://viperp.superboss.cc/index.html', title: 'ERP', shopName: 'x', 'has商家登录': true, 'has自动注册': true });
  assert.equal(r.success, false);
  assert.match(r.error, /不在鲸灵域名/);
});

test('info 为空 → success:false', () => {
  const r = judgeLoginState(null);
  assert.equal(r.success, false);
});

// ── matchShopName / shopKeyword（关键字包含匹配）──

test('shopKeyword: 取 "-" 前核心词', () => {
  assert.equal(shopKeyword('百浩-RITEKOKO'), '百浩');
  assert.equal(shopKeyword('共途-KGOS'), '共途');
  assert.equal(shopKeyword('上海绰绰-悦希'), '上海绰绰');
  assert.equal(shopKeyword('汐澜-鲨鱼'), '汐澜');
});

test('matchShopName: 真机案例 百浩 → 合肥百浩创展贸易有限公司', () => {
  assert.equal(matchShopName('合肥百浩创展贸易有限公司', '百浩-RITEKOKO'), true);
});

test('matchShopName: 真机案例 共途 → 杭州共途贸易有限公司', () => {
  assert.equal(matchShopName('杭州共途贸易有限公司', '共途-KGOS'), true);
});

test('matchShopName: 不匹配 → false（防注入到错号）', () => {
  assert.equal(matchShopName('杭州共途贸易有限公司', '百浩-RITEKOKO'), false);
});

test('matchShopName: 空值安全', () => {
  assert.equal(matchShopName('', '百浩-RITEKOKO'), false);
  assert.equal(matchShopName('合肥百浩创展', ''), false);
});
