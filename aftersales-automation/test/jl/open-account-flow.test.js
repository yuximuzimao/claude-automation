'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const { openAccountFlow, decideOpenAccountAction } = require('../../lib/jl/open-account-flow');

function makeSteps(loginState, calls) {
  return {
    openLogin: async () => {
      calls.push('openLogin');
      return { success: true, targetId: 'tab-1' };
    },
    readShopName: async (targetId) => {
      calls.push(`readShopName:${targetId}`);
      return loginState;
    },
    clearJlData: async (targetId) => {
      calls.push(`clearJlData:${targetId}`);
      return { success: true, verified: true, remainingAuthCookies: [], targetId, deletedCount: 3 };
    },
    inject: async (accountNum, options) => {
      calls.push(`inject:${accountNum}:${options && options.targetId}`);
      return { success: true, loggedIn: true, shopName: '合肥百浩创展贸易有限公司', accountNum: String(accountNum) };
    },
    countJlTabs: async () => {
      calls.push('countJlTabs');
      return { success: true, count: 0, tabs: [] };
    },
    closeExtraJlTabs: async () => {
      calls.push('closeExtraJlTabs');
      return { success: true, count: 1, closed: [], keptTargetId: 'tab-1' };
    },
  };
}

test('decideOpenAccountAction：已登录且店铺名匹配目标账号时复用，不注入', () => {
  const action = decideOpenAccountAction(
    { success: true, state: 'logged-in', shopName: '合肥百浩创展贸易有限公司' },
    '百浩-RITEKOKO'
  );

  assert.deepEqual(action, { action: 'reuse' });
});

test('openAccountFlow：匹配目标账号时只打开和读取，禁止注入', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: true, state: 'logged-in', shopName: '合肥百浩创展贸易有限公司' }, calls),
  });

  assert.equal(result.success, true);
  assert.equal(result.action, 'reuse');
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1']);
});

test('openAccountFlow：已登录但错号时先清 cookie 再注入目标账号（不再退出登录）', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: true, state: 'logged-in', shopName: '杭州共途贸易有限公司' }, calls),
  });

  assert.equal(result.success, true);
  assert.equal(result.action, 'inject');
  assert.equal(result.matchedNote, '百浩-RITEKOKO');
  // 错号现在走 clearJlData → inject，不含 logout
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1', 'clearJlData:tab-1', 'inject:3:tab-1']);
  assert.equal(calls.includes('logout:tab-1'), false);
});

test('openAccountFlow：确证未登录时先清 cookie 再注入目标账号', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: true, state: 'logged-out', loggedIn: false }, calls),
  });

  assert.equal(result.success, true);
  assert.equal(result.action, 'inject');
  assert.equal(result.matchedNote, '百浩-RITEKOKO');
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1', 'clearJlData:tab-1', 'inject:3:tab-1']);
});

test('openAccountFlow：清理失败则不注入，报错即停', async () => {
  const calls = [];
  const steps = makeSteps({ success: true, state: 'logged-out', loggedIn: false }, calls);
  steps.clearJlData = async (targetId) => {
    calls.push(`clearJlData:${targetId}`);
    return { success: false, error: '清理鲸灵数据失败: CDP timeout' };
  };

  const result = await openAccountFlow(3, { note: '百浩-RITEKOKO', steps });

  assert.equal(result.success, false);
  assert.match(result.error, /清理/);
  // clearJlData 失败后绝不调用 inject
  assert.equal(calls.includes('inject:3'), false);
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1', 'clearJlData:tab-1']);
});

test('openAccountFlow：清理返回 success:true 但 verified:false 时不得注入', async () => {
  const calls = [];
  const steps = makeSteps({ success: true, state: 'logged-out', loggedIn: false }, calls);
  steps.clearJlData = async (targetId) => {
    calls.push(`clearJlData:${targetId}`);
    return { success: true, verified: false, remainingAuthCookies: ['JSESSIONID'] };
  };

  const result = await openAccountFlow(3, { note: '百浩-RITEKOKO', steps });

  assert.equal(result.success, false);
  assert.match(result.error, /清理|验证/);
  assert.equal(calls.includes('inject:3'), false);
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1', 'clearJlData:tab-1']);
});

test('openAccountFlow：未知登录态报错即停，不清理也不注入', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: false, error: '未知页面状态' }, calls),
  });

  assert.equal(result.success, false);
  assert.match(result.error, /未知页面状态/);
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1']);
});

test('openAccountFlow：没有鲲灵 tab 时才调用 openLogin 新开', async () => {
  const calls = [];
  const steps = makeSteps({ success: true, state: 'logged-in', shopName: '合肥百浩创展贸易有限公司' }, calls);

  const result = await openAccountFlow(3, { note: '百浩-RITEKOKO', steps });

  assert.equal(result.success, true);
  assert.equal(result.targetId, 'tab-1');
  assert.deepEqual(calls, ['countJlTabs', 'openLogin', 'readShopName:tab-1']);
});

test('openAccountFlow：已有唯一鲲灵 tab 时复用且不调用 openLogin', async () => {
  const calls = [];
  const steps = makeSteps({ success: true, state: 'logged-in', shopName: '合肥百浩创展贸易有限公司' }, calls);
  steps.countJlTabs = async () => {
    calls.push('countJlTabs');
    return { success: true, count: 1, tabs: [{ id: 'existing-tab', url: 'https://scrm.jlsupp.com/workbench', title: '后台' }] };
  };

  const result = await openAccountFlow(3, { note: '百浩-RITEKOKO', steps });

  assert.equal(result.success, true);
  assert.equal(result.targetId, 'existing-tab');
  assert.deepEqual(calls, ['countJlTabs', 'readShopName:existing-tab']);
});

test('openAccountFlow：多个鲲灵 tab 时先关闭多余 tab，复用 keptTargetId 且不调用 openLogin', async () => {
  const calls = [];
  const steps = makeSteps({ success: true, state: 'logged-in', shopName: '合肥百浩创展贸易有限公司' }, calls);
  steps.countJlTabs = async () => {
    calls.push('countJlTabs');
    return {
      success: true,
      count: 3,
      tabs: [
        { id: 'kept-tab', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
        { id: 'extra-tab-1', url: 'https://scrm.jlsupp.com/login', title: '登录' },
        { id: 'extra-tab-2', url: 'https://scrm.jlsupp.com/other', title: '其他' },
      ],
    };
  };
  steps.closeExtraJlTabs = async () => {
    calls.push('closeExtraJlTabs');
    return { success: true, count: 3, closed: ['extra-tab-1', 'extra-tab-2'], keptTargetId: 'kept-tab' };
  };

  const result = await openAccountFlow(3, { note: '百浩-RITEKOKO', steps });

  assert.equal(result.success, true);
  assert.equal(result.targetId, 'kept-tab');
  assert.deepEqual(calls, ['countJlTabs', 'closeExtraJlTabs', 'readShopName:kept-tab']);
});

test('op-queue 打开店铺后台入口使用安全编排脚本，不再盲目 jl inject', () => {
  const source = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');
  const start = source.indexOf('async function execOpenAccount');
  const end = source.indexOf('// ── 单账号扫描');
  assert.notEqual(start, -1, '找不到 execOpenAccount');
  assert.notEqual(end, -1, '找不到 execOpenAccount 结束边界');
  const body = source.slice(start, end);

  assert.match(body, /scripts[\\/]+jl-steps[\\/]+open-account\.js/);
  assert.equal(body.includes("jl.js'), 'inject'"), false);
});
