const test = require('node:test');
const assert = require('node:assert/strict');

const {
  renderConfirmReloginControls,
  shouldShowReloginButton,
  shouldKeepConfirmAfterError,
} = require('../../public/account-relogin-state');

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
