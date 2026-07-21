const test = require('node:test');
const assert = require('node:assert/strict');

const {
  shouldInitializePhoneForAccount,
  startReloginSession,
} = require('../../lib/server/relogin-session');

test('an account without a saved session still needs first phone initialization on retry', () => {
  const account = { file: 'account15.json' };
  const fsImpl = { existsSync: () => false };

  assert.equal(shouldInitializePhoneForAccount({
    account,
    sessionsDir: '/sessions',
    fsImpl,
  }), true);
});

test('an account with a saved session uses ordinary relogin without phone initialization', () => {
  const account = { file: 'account15.json' };
  const fsImpl = { existsSync: file => file === '/sessions/account15.json' };

  assert.equal(shouldInitializePhoneForAccount({
    account,
    sessionsDir: '/sessions',
    fsImpl,
  }), false);
});

function makeHarness() {
  let portReady = false;
  const calls = [];
  const waits = [];
  let unrefCalled = false;

  return {
    calls,
    waits,
    get unrefCalled() { return unrefCalled; },
    fsImpl: {
      existsSync: () => portReady,
      unlinkSync: () => { portReady = false; },
    },
    spawnImpl(command, args, options) {
      calls.push({ command, args, options });
      return { unref() { unrefCalled = true; } };
    },
    async wait(ms) {
      waits.push(ms);
      portReady = true;
    },
  };
}

test('new account login waits for the confirm port and requests first phone initialization', async () => {
  const harness = makeHarness();

  await startReloginSession({
    num: 15,
    sessionsDir: '/sessions',
    initializePhone: true,
    fsImpl: harness.fsImpl,
    spawnImpl: harness.spawnImpl,
    wait: harness.wait,
  });

  assert.deepEqual(harness.calls, [{
    command: 'node',
    args: ['/sessions/jl.js', 'add', '15', '--auto-save', '--initialize-phone'],
    options: { detached: true, stdio: 'ignore' },
  }]);
  assert.deepEqual(harness.waits, [200]);
  assert.equal(harness.unrefCalled, true);
});

test('ordinary relogin keeps the existing command without first phone initialization', async () => {
  const harness = makeHarness();

  await startReloginSession({
    num: 5,
    sessionsDir: '/sessions',
    fsImpl: harness.fsImpl,
    spawnImpl: harness.spawnImpl,
    wait: harness.wait,
  });

  assert.deepEqual(harness.calls[0].args, [
    '/sessions/jl.js', 'add', '5', '--auto-save',
  ]);
});
