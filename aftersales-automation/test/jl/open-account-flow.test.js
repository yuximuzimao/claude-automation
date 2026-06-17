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
    logout: async (targetId) => {
      calls.push(`logout:${targetId}`);
      return { success: true, loggedOut: true };
    },
    inject: async (accountNum) => {
      calls.push(`inject:${accountNum}`);
      return { success: true, loggedIn: true, shopName: '合肥百浩创展贸易有限公司', accountNum: String(accountNum) };
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
  assert.deepEqual(calls, ['openLogin', 'readShopName:tab-1']);
});

test('openAccountFlow：已登录但错号时先退出，再注入目标账号', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: true, state: 'logged-in', shopName: '杭州共途贸易有限公司' }, calls),
  });

  assert.equal(result.success, true);
  assert.equal(result.action, 'logout-inject');
  assert.deepEqual(calls, ['openLogin', 'readShopName:tab-1', 'logout:tab-1', 'inject:3']);
});

test('openAccountFlow：确证未登录时直接注入目标账号', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: true, state: 'logged-out', loggedIn: false }, calls),
  });

  assert.equal(result.success, true);
  assert.equal(result.action, 'inject');
  assert.deepEqual(calls, ['openLogin', 'readShopName:tab-1', 'inject:3']);
});

test('openAccountFlow：未知登录态报错即停，不退出也不注入', async () => {
  const calls = [];
  const result = await openAccountFlow(3, {
    note: '百浩-RITEKOKO',
    steps: makeSteps({ success: false, error: '未知页面状态' }, calls),
  });

  assert.equal(result.success, false);
  assert.match(result.error, /未知页面状态/);
  assert.deepEqual(calls, ['openLogin', 'readShopName:tab-1']);
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
