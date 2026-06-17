'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');
const { closeExtraJlTabs } = require('../../scripts/jl-steps/06-close-extra-jl-tabs');

const originalGetTargets = cdp.getTargets;
const originalCloseTarget = cdp.closeTarget;

test.afterEach(() => {
  cdp.getTargets = originalGetTargets;
  cdp.closeTarget = originalCloseTarget;
});

test('closeExtraJlTabs leaves zero tabs unchanged', async () => {
  const closedIds = [];
  cdp.getTargets = async () => [];
  cdp.closeTarget = async (id) => closedIds.push(id);

  const result = await closeExtraJlTabs({ sleepMs: 0 });

  assert.deepEqual(result, { success: true, count: 0, closed: [], keptTargetId: null });
  assert.deepEqual(closedIds, []);
});

test('closeExtraJlTabs leaves one tab unchanged and returns kept target id', async () => {
  const closedIds = [];
  cdp.getTargets = async () => [
    { id: 'jl-1', type: 'page', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
  ];
  cdp.closeTarget = async (id) => closedIds.push(id);

  const result = await closeExtraJlTabs({ sleepMs: 0 });

  assert.deepEqual(result, { success: true, count: 1, closed: [], keptTargetId: 'jl-1' });
  assert.deepEqual(closedIds, []);
});

test('closeExtraJlTabs keeps first scrm tab and closes only extras in order', async () => {
  const closedIds = [];
  cdp.getTargets = async () => [
    { id: 'jl-1', type: 'page', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
    { id: 'erp-1', type: 'page', url: 'https://viperp.superboss.cc/', title: 'ERP' },
    { id: 'jl-2', type: 'page', url: 'https://scrm.jlsupp.com/micro-businessPlatform/login', title: '登录' },
    { id: 'jl-3', type: 'page', url: 'https://scrm.jlsupp.com/other', title: '其他' },
  ];
  cdp.closeTarget = async (id) => {
    closedIds.push(id);
    return { closed: true };
  };

  const result = await closeExtraJlTabs({ sleepMs: 0 });

  assert.equal(result.success, true);
  assert.equal(result.count, 3);
  assert.equal(result.keptTargetId, 'jl-1');
  assert.deepEqual(result.closed, ['jl-2', 'jl-3']);
  assert.deepEqual(closedIds, ['jl-2', 'jl-3']);
});

test('closeExtraJlTabs stops on first closeTarget error without retrying remaining tabs', async () => {
  const closedAttempts = [];
  cdp.getTargets = async () => [
    { id: 'jl-1', type: 'page', url: 'https://scrm.jlsupp.com/workbench', title: '后台' },
    { id: 'jl-2', type: 'page', url: 'https://scrm.jlsupp.com/login', title: '登录' },
    { id: 'jl-3', type: 'page', url: 'https://scrm.jlsupp.com/other', title: '其他' },
  ];
  cdp.closeTarget = async (id) => {
    closedAttempts.push(id);
    if (id === 'jl-2') throw new Error('close failed');
  };

  const result = await closeExtraJlTabs({ sleepMs: 0 });

  assert.equal(result.success, false);
  assert.equal(result.count, 3);
  assert.equal(result.keptTargetId, 'jl-1');
  assert.deepEqual(result.closed, []);
  assert.deepEqual(closedAttempts, ['jl-2']);
  assert.match(result.error, /close failed/);
});
