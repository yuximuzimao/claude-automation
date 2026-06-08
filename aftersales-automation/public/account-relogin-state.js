(function(root) {
  function isMissingPendingSession(res) {
    const error = String((res && res.error) || '');
    return error.includes('没有待确认的登录会话');
  }

  function shouldKeepConfirmAfterError(res) {
    return !isMissingPendingSession(res);
  }

  function renderConfirmReloginControls(num) {
    return [
      `<button class="btn-relogin confirm" onclick="confirmRelogin(${num})">确认保存</button>`,
      `<button class="btn-relogin cancel" onclick="cancelRelogin(${num})">取消</button>`,
    ].join('');
  }

  function shouldShowReloginButton(account) {
    if (!account || !account.hasFile) return true;
    return account.status === 'expired' || account.status === 'error';
  }

  const api = {
    isMissingPendingSession,
    shouldKeepConfirmAfterError,
    renderConfirmReloginControls,
    shouldShowReloginButton,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  root.AccountReloginState = api;
})(typeof window !== 'undefined' ? window : globalThis);
