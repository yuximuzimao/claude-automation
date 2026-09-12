'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { reconcileCacheAccounts, validateAlertAccount } = require('../../lib/jl/alerts');

test('平台提醒缓存丢弃不存在的账号和显示名不匹配的测试数据', () => {
  const source = {
    byAccount: {
      '3': { num: '3', note: '测试店铺', items: [{ title: '售后工单待处理' }] },
      '13': { num: '13', note: '澜泽-KGOS', items: [{ title: '待开票' }] },
      '999': { num: '999', note: '不存在店铺', items: [{ title: '逾期待处理' }] },
    },
    updatedAt: '2026-09-12T00:00:00.000Z',
  };

  const result = reconcileCacheAccounts(source, {
    '3': '百浩-RITEKOKO',
    '13': '澜泽-KGOS',
  });

  assert.equal(result.changed, true);
  assert.deepEqual(Object.keys(result.cache.byAccount), ['13']);
  assert.equal(source.byAccount['3'].note, '测试店铺');
});

test('平台提醒缓存与当前账号配置一致时保持原样', () => {
  const source = {
    byAccount: {
      '3': { num: '3', note: '百浩-RITEKOKO', items: [] },
    },
  };
  const result = reconcileCacheAccounts(source, { '3': '百浩-RITEKOKO' });
  assert.equal(result.changed, false);
  assert.deepEqual(result.cache, source);
});

test('读取真实页面前拒绝不存在账号和测试店铺显示名', () => {
  const notes = { '3': '百浩-RITEKOKO' };
  assert.deepEqual(validateAlertAccount('3', '测试店铺', notes), {
    ok: false,
    key: '3',
    reason: '店铺显示名不匹配',
  });
  assert.deepEqual(validateAlertAccount('999', '测试店铺', notes), {
    ok: false,
    key: '999',
    reason: '账号不存在',
  });
  assert.deepEqual(validateAlertAccount(3, '百浩-RITEKOKO', notes), {
    ok: true,
    key: '3',
    note: '百浩-RITEKOKO',
  });
});
