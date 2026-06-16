'use strict';

function classifySessionFailure(message) {
  const msg = String(message || '');
  return /session\s*已失效|登录已失效|login|sso|跳转到登录页/.test(msg) ? 'expired' : 'error';
}

function normalizeAccountStatus(status) {
  return { ...(status || {}) };
}

function getAccountOpenGuard(status) {
  const st = normalizeAccountStatus(status);
  if (st.status === 'ok') return { ok: true, status: 'ok' };
  if (!st.status || st.status === 'unknown') return { ok: true, status: st.status || 'unknown' };
  return {
    ok: false,
    status: st.status || 'unknown',
    error: st.error
      ? `${st.error}，请先重新登录或刷新状态`
      : '账号状态异常，请先重新登录或刷新状态',
  };
}

module.exports = {
  classifySessionFailure,
  getAccountOpenGuard,
  normalizeAccountStatus,
};
