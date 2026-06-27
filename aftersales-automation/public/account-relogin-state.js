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
    // 正常(ok)/失效(expired)/异常(error) 都保留重新登录入口；
    // 仅「已保存未扫描」(unknown) 不显示，避免误导为已失效（沿用旧决策）。
    return account.status === 'ok'
      || account.status === 'expired'
      || account.status === 'error';
  }

  function shouldShowA1FixedBatchButton(account) {
    return !!account && account.hasFile === true && account.status === 'ok';
  }

  function renderA1FixedBatchButton(num) {
    return `<button class="btn-ghost btn-sm btn-a1-fixed-batch" onclick="runA1FixedBatch(${num}, this)">A1固定清单</button>`;
  }

  const api = {
    isMissingPendingSession,
    renderA1FixedBatchButton,
    shouldKeepConfirmAfterError,
    shouldShowA1FixedBatchButton,
    renderConfirmReloginControls,
    shouldShowReloginButton,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  root.AccountReloginState = api;
})(typeof window !== 'undefined' ? window : globalThis);
