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
      `<button class="btn-relogin cancel" onclick="cancelRelogin(${num}, this)">取消</button>`,
    ].join('');
  }

  function renderCancellingReloginControl() {
    return '<button class="btn-relogin pending" disabled>取消中...</button>';
  }

  async function runReloginCancellation({ num, button, cancelling, confirm, requestCancel }) {
    if (cancelling.has(num)) return { ok: false, ignored: true };

    cancelling.add(num);
    const actions = button && typeof button.closest === 'function'
      ? button.closest('.account-actions')
      : null;
    const controls = actions && typeof actions.querySelectorAll === 'function'
      ? actions.querySelectorAll('.btn-relogin')
      : [];
    Array.from(controls).forEach(control => { control.disabled = true; });
    if (button) button.textContent = '取消中...';

    try {
      const result = await requestCancel();
      if (result && result.ok) confirm.delete(num);
      return result || { ok: false, error: '取消登录失败：后端未返回结果' };
    } catch (error) {
      return { ok: false, error: `取消登录失败：${error.message}` };
    } finally {
      cancelling.delete(num);
    }
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
    return `<button class="btn-ghost btn-sm btn-a1-fixed-batch" onclick="runA1FixedBatch(${num}, this)">处理工单</button>`;
  }

  const api = {
    isMissingPendingSession,
    renderA1FixedBatchButton,
    renderCancellingReloginControl,
    runReloginCancellation,
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
