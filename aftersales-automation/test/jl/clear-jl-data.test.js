'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');
const { clearJlData } = require('../../scripts/jl-steps/07-clear-jl-data');

test('clearJlData：缺 targetId 返回失败', async () => {
  const r = await clearJlData();
  assert.equal(r.success, false);
  assert.match(r.error, /targetId/);
});

test('clearJlData：成功返回 deletedCount', async () => {
  const orig = cdp.clearJlCookiesAndStorage;
  cdp.clearJlCookiesAndStorage = async (targetId) => ({ deletedCount: 5, deletedCookies: [] });
  try {
    const r = await clearJlData('tab-1');
    assert.equal(r.success, true);
    assert.equal(r.targetId, 'tab-1');
    assert.equal(r.deletedCount, 5);
  } finally {
    cdp.clearJlCookiesAndStorage = orig;
  }
});

test('clearJlData：底层抛错 → 返回失败（报错即停，不重试）', async () => {
  const orig = cdp.clearJlCookiesAndStorage;
  cdp.clearJlCookiesAndStorage = async () => { throw new Error('CDP timeout'); };
  try {
    const r = await clearJlData('tab-1');
    assert.equal(r.success, false);
    assert.match(r.error, /清理鲸灵数据失败.*CDP timeout/);
  } finally {
    cdp.clearJlCookiesAndStorage = orig;
  }
});
