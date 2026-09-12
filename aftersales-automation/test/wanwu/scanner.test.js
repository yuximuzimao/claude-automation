'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  scanWanwu,
  STABLE_READ_INTERVAL_MS,
  OPEN_SETTLE_MS,
  LOGIN_SETTLE_MS,
  CLOSE_VERIFY_DELAY_MS,
} = require('../../wanwu/scanner');
const { COUNTER_DEFINITIONS, HOME_URL, LOGIN_BUTTON_SELECTOR } = require('../../wanwu/selectors');

function counts(overrides = {}) {
  return Object.fromEntries(COUNTER_DEFINITIONS.map(definition => [
    definition.key,
    overrides[definition.key] || 0,
  ]));
}

function home(snapshotCounts = counts()) {
  return {
    kind: 'home',
    ready: true,
    counts: snapshotCounts,
    issues: [],
    riskSignal: null,
  };
}

function login(extra = {}) {
  return {
    kind: 'login',
    ready: false,
    counts: {},
    issues: [],
    riskSignal: null,
    loginButtonVisible: true,
    loginError: null,
    ...extra,
  };
}

function fakeDependencies(states) {
  const calls = { created: [], activated: [], clicked: [], closed: [], sleeps: [], stages: [] };
  let index = 0;
  return {
    calls,
    deps: {
      createTarget: async url => { calls.created.push(url); return { id: 'wanwu-test-target' }; },
      activateTarget: async id => { calls.activated.push(id); },
      clickAt: async (id, selector) => { calls.clicked.push({ id, selector }); },
      closeTarget: async id => { calls.closed.push(id); },
      getTargets: async () => [],
      eval: async () => states[Math.min(index++, states.length - 1)],
      sleep: async ms => { calls.sleeps.push(ms); },
      assertNotAborted: () => {},
      onStage: stage => { calls.stages.push(stage); },
    },
  };
}

test('已登录时双读间隔3秒且关闭本次创建的标签页', async () => {
  const snapshot = home(counts({ pendingShip: 1 }));
  const fake = fakeDependencies([snapshot, snapshot, snapshot, snapshot]);

  const result = await scanWanwu(fake.deps);

  assert.equal(result.counts.pendingShip, 1);
  assert.equal(result.loggedInDuringScan, false);
  assert.deepEqual(fake.calls.created, [HOME_URL]);
  assert.deepEqual(fake.calls.clicked, []);
  assert.deepEqual(fake.calls.closed, ['wanwu-test-target']);
  assert.ok(fake.calls.sleeps.includes(OPEN_SETTLE_MS));
  assert.ok(fake.calls.sleeps.includes(STABLE_READ_INTERVAL_MS));
  assert.ok(fake.calls.sleeps.includes(CLOSE_VERIFY_DELAY_MS));
  assert.deepEqual(fake.calls.stages, ['opening', 'reading', 'closing']);
});

test('未登录时只真实点击一次登陆按钮再读取', async () => {
  const snapshot = home(counts());
  const fake = fakeDependencies([login(), snapshot, snapshot, snapshot]);

  const result = await scanWanwu(fake.deps);

  assert.equal(result.loggedInDuringScan, true);
  assert.deepEqual(fake.calls.clicked, [{ id: 'wanwu-test-target', selector: LOGIN_BUTTON_SELECTOR }]);
  assert.equal(fake.calls.sleeps.filter(ms => ms === LOGIN_SETTLE_MS).length, 2);
  assert.deepEqual(fake.calls.closed, ['wanwu-test-target']);
  assert.deepEqual(fake.calls.stages, ['opening', 'login', 'reading', 'closing']);
});

test('两次数字不一致时停止判断并仍然关闭标签页', async () => {
  const zero = home(counts());
  const changed = home(counts({ pendingAudit: 1 }));
  const fake = fakeDependencies([zero, zero, zero, changed]);

  await assert.rejects(() => scanWanwu(fake.deps), /两次读取不一致/);
  assert.deepEqual(fake.calls.closed, ['wanwu-test-target']);
  assert.equal(fake.calls.clicked.length, 0);
});

test('风控提示立即停止且仍然关闭标签页', async () => {
  const fake = fakeDependencies([{
    kind: 'unknown',
    ready: false,
    counts: {},
    issues: [],
    riskSignal: '访问过于频繁',
  }]);

  await assert.rejects(() => scanWanwu(fake.deps), /风控提示/);
  assert.deepEqual(fake.calls.closed, ['wanwu-test-target']);
  assert.equal(fake.calls.clicked.length, 0);
});

test('关闭后目标仍存在时整轮按异常处理', async () => {
  const snapshot = home(counts());
  const fake = fakeDependencies([snapshot, snapshot, snapshot, snapshot]);
  fake.deps.getTargets = async () => [{ id: 'wanwu-test-target' }];

  await assert.rejects(() => scanWanwu(fake.deps), /关闭后仍存在/);
  assert.deepEqual(fake.calls.closed, ['wanwu-test-target']);
});
