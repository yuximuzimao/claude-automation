const test = require('node:test');
const assert = require('node:assert/strict');

const {
  renderA1FixedBatchButton,
  renderCancellingReloginControl,
  renderConfirmReloginControls,
  registerCreatedAccountConfirmation,
  runReloginCancellation,
  shouldShowA1FixedBatchButton,
  shouldShowReloginButton,
  shouldKeepConfirmAfterError,
} = require('../../public/account-relogin-state');

test('new account response enters the existing confirm-save state', () => {
  const confirm = new Set();

  const num = registerCreatedAccountConfirmation({ ok: true, num: 15 }, confirm);

  assert.equal(num, 15);
  assert.equal(confirm.has(15), true);
});

test('new account response without an account number does not change confirm state', () => {
  const confirm = new Set([3]);

  const num = registerCreatedAccountConfirmation({ ok: true }, confirm);

  assert.equal(num, null);
  assert.deepEqual([...confirm], [3]);
});

function makeCancelButton() {
  const controls = [{ disabled: false }, { disabled: false }];
  const button = {
    textContent: '取消',
    closest: () => ({ querySelectorAll: () => controls }),
  };
  return { button, controls };
}

test('pending cancellation immediately disables controls and keeps relogin blocked', async () => {
  const cancelling = new Set();
  const confirm = new Set([3]);
  const { button, controls } = makeCancelButton();
  let finishRequest;
  const request = new Promise(resolve => { finishRequest = resolve; });

  const resultPromise = runReloginCancellation({
    num: 3,
    button,
    cancelling,
    confirm,
    requestCancel: () => request,
  });

  assert.equal(cancelling.has(3), true);
  assert.equal(confirm.has(3), true);
  assert.equal(button.textContent, '取消中...');
  assert.deepEqual(controls.map(control => control.disabled), [true, true]);

  finishRequest({ ok: true });
  assert.deepEqual(await resultPromise, { ok: true });
  assert.equal(cancelling.has(3), false);
  assert.equal(confirm.has(3), false);
});

test('failed cancellation restores controls by preserving confirm state', async () => {
  const cancelling = new Set();
  const confirm = new Set([3]);
  const { button } = makeCancelButton();

  const result = await runReloginCancellation({
    num: 3,
    button,
    cancelling,
    confirm,
    requestCancel: async () => ({ ok: false, error: '取消失败' }),
  });

  assert.deepEqual(result, { ok: false, error: '取消失败' });
  assert.equal(cancelling.has(3), false);
  assert.equal(confirm.has(3), true);
});

test('thrown cancellation request does not leave account stuck cancelling', async () => {
  const cancelling = new Set();
  const confirm = new Set([3]);
  const { button } = makeCancelButton();

  const result = await runReloginCancellation({
    num: 3,
    button,
    cancelling,
    confirm,
    requestCancel: async () => { throw new Error('server disconnected'); },
  });

  assert.equal(result.ok, false);
  assert.match(result.error, /server disconnected/);
  assert.equal(cancelling.has(3), false);
  assert.equal(confirm.has(3), true);
});

test('cancelling state blocks relogin until backend confirms cancellation', () => {
  const html = renderCancellingReloginControl();

  assert.match(html, /disabled/);
  assert.match(html, />取消中\.\.\.</);
  assert.doesNotMatch(html, /reloginAccount|confirmRelogin|cancelRelogin/);
});

test('confirm state renders both save and cancel actions', () => {
  const html = renderConfirmReloginControls(5);

  assert.match(html, /confirmRelogin\(5\)/);
  assert.match(html, /cancelRelogin\(5, this\)/);
});

test('missing pending relogin session returns to relogin button', () => {
  const keepConfirm = shouldKeepConfirmAfterError({
    ok: false,
    error: '没有待确认的登录会话，请重新点击"重新登录"',
  });

  assert.equal(keepConfirm, false);
});

test('transient confirm failure keeps confirm action available', () => {
  const keepConfirm = shouldKeepConfirmAfterError({
    ok: false,
    error: '确认失败: socket hang up',
  });

  assert.equal(keepConfirm, true);
});

test('saved but unscanned account does not show relogin action', () => {
  assert.equal(shouldShowReloginButton({ hasFile: true, status: 'unknown' }), false);
});

test('expired account still shows relogin action', () => {
  assert.equal(shouldShowReloginButton({ hasFile: true, status: 'expired' }), true);
});

test('normal (ok) account also keeps relogin action', () => {
  assert.equal(shouldShowReloginButton({ hasFile: true, status: 'ok' }), true);
});

test('error account still shows relogin action', () => {
  assert.equal(shouldShowReloginButton({ hasFile: true, status: 'error' }), true);
});

test('A1 fixed-batch button only shows for ok saved accounts', () => {
  assert.equal(shouldShowA1FixedBatchButton({ hasFile: true, status: 'ok' }), true);
  assert.equal(shouldShowA1FixedBatchButton({ hasFile: true, status: 'expired' }), false);
  assert.equal(shouldShowA1FixedBatchButton({ hasFile: true, status: 'error' }), false);
  assert.equal(shouldShowA1FixedBatchButton({ hasFile: true, status: 'unknown' }), false);
  assert.equal(shouldShowA1FixedBatchButton({ hasFile: false, status: 'ok' }), false);
});

test('A1 fixed-batch button renders a single-account no-auto action', () => {
  const html = renderA1FixedBatchButton(14);

  assert.match(html, /runA1FixedBatch\(14, this\)/);
  assert.match(html, />处理工单</);
});
