'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');
const { countJlTabs } = require('../../scripts/jl-steps/05-count-jl-tabs');

const originalGetTargets = cdp.getTargets;

test.afterEach(() => {
  cdp.getTargets = originalGetTargets;
});

test('countJlTabs filters only scrm page targets', async () => {
  cdp.getTargets = async () => [
    { id: 'jl-1', type: 'page', url: 'https://scrm.jlsupp.com/micro-businessPlatform/login', title: '鲸灵' },
    { id: 'worker-1', type: 'service_worker', url: 'https://scrm.jlsupp.com/sw.js', title: '' },
    { id: 'erp-1', type: 'page', url: 'https://viperp.superboss.cc/', title: 'ERP' },
    { id: 'jl-2', type: 'page', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
  ];

  const result = await countJlTabs();

  assert.equal(result.success, true);
  assert.equal(result.count, 2);
  assert.deepEqual(result.tabs, [
    { id: 'jl-1', url: 'https://scrm.jlsupp.com/micro-businessPlatform/login', title: '鲸灵' },
    { id: 'jl-2', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
  ]);
});

test('countJlTabs returns zero when there are no scrm page targets', async () => {
  cdp.getTargets = async () => [
    { id: 'erp-1', type: 'page', url: 'https://viperp.superboss.cc/', title: 'ERP' },
    { id: 'blank-1', type: 'page', url: 'about:blank', title: '' },
  ];

  const result = await countJlTabs();

  assert.deepEqual(result, { success: true, count: 0, tabs: [] });
});

test('countJlTabs reports getTargets errors without retrying', async () => {
  let calls = 0;
  cdp.getTargets = async () => {
    calls += 1;
    throw new Error('chrome unavailable');
  };

  const result = await countJlTabs();

  assert.equal(calls, 1);
  assert.equal(result.success, false);
  assert.match(result.error, /chrome unavailable/);
});
