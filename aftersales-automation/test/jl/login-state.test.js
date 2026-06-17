'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { judgeLoginState, matchShopName, shopKeyword } = require('../../lib/jl/login-state');

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

test('已登录优先：店铺名有值时即使两句文案缺也判已登录', () => {
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
