const test = require('node:test');
const assert = require('node:assert/strict');

const {
  renderA1FixedBatchButton,
  renderCancellingReloginControl,
  renderConfirmReloginControls,
  shouldShowA1FixedBatchButton,
  shouldShowReloginButton,
  shouldKeepConfirmAfterError,
} = require('../../public/account-relogin-state');

test('cancelling state blocks relogin until backend confirms cancellation', () => {
  const html = renderCancellingReloginControl();

  assert.match(html, /disabled/);
  assert.match(html, />取消中\.\.\.</);
  assert.doesNotMatch(html, /reloginAccount|confirmRelogin|cancelRelogin/);
});

test('confirm state renders both save and cancel actions', () => {
  const html = renderConfirmReloginControls(5);

  assert.match(html, /confirmRelogin\(5\)/);
  assert.match(html, /cancelRelogin\(5\)/);
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
