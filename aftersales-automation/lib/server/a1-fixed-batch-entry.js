'use strict';

const fs = require('fs');
const path = require('path');
const { filterAuthCookies, filterIdentityLocalStorage } = require('../jl/session-filter');
const { getAccountOpenGuard } = require('./account-session-status');

function parseAccountNum(value) {
  const accountNum = String(value == null ? '' : value).trim();
  if (!/^[1-9]\d*$/.test(accountNum)) throw new Error('invalid accountNum');
  return accountNum;
}

function buildA1FixedBatchOp({ accountNum, accountNote }) {
  const num = parseAccountNum(accountNum);
  const note = String(accountNote || `账号${num}`).trim() || `账号${num}`;
  return {
    type: 'a1-fixed-batch',
    label: `A1固定清单 账号${num}「${note}」`,
    params: {
      accountNum: num,
      accountNote: note,
      thresholdHours: 48,
      disableAutoExecute: true,
    },
  };
}

function validateSessionFile({ accountNum, file, sessionsDir, fsImpl = fs }) {
  const num = parseAccountNum(accountNum);
  const expectedFile = `account${num}.json`;
  const sessionFile = String(file || '').trim();
  if (!sessionFile || path.basename(sessionFile) !== sessionFile || sessionFile !== expectedFile) {
    return { ok: false, error: `账号${num} session 文件名非法或不匹配` };
  }
  if (!sessionsDir) return { ok: false, error: 'sessionsDir required' };

  let sessionPath;
  try {
    const baseRealPath = fsImpl.realpathSync(sessionsDir);
    const realPath = fsImpl.realpathSync(path.join(sessionsDir, sessionFile));
    const relativePath = path.relative(baseRealPath, realPath);
    if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
      return { ok: false, error: `账号${num} session 文件路径非法` };
    }
    sessionPath = realPath;
  } catch (error) {
    return { ok: false, error: `账号${num} session 文件不存在或不可读: ${error.message}` };
  }

  let session;
  try {
    session = JSON.parse(fsImpl.readFileSync(sessionPath, 'utf8'));
  } catch (error) {
    return { ok: false, error: `账号${num} session 文件损坏: ${error.message}` };
  }

  const authCookies = filterAuthCookies(session.cookies || []).filter(cookie => {
    return cookie && cookie.value && String(cookie.domain || '').includes('jlsupp.com');
  });
  if (authCookies.length === 0) {
    return { ok: false, error: `账号${num} session 缺少鲸灵认证 Cookie` };
  }

  const origin = (session.origins || []).find(item => String(item && item.origin || '').includes('scrm.jlsupp.com'));
  const identityEntries = filterIdentityLocalStorage(origin && origin.localStorage || []).filter(item => item && item.value);
  if (identityEntries.length === 0) {
    return { ok: false, error: `账号${num} session 缺少鲸灵账号身份 localStorage` };
  }

  return { ok: true };
}

function createA1FixedBatchRouteHandler({
  readAccounts,
  readAccountStatus,
  sessionExists,
  validateSessionFile: validateSession,
  opQueue,
}) {
  if (typeof readAccounts !== 'function') throw new Error('readAccounts required');
  if (typeof readAccountStatus !== 'function') throw new Error('readAccountStatus required');
  if (typeof validateSession !== 'function' && typeof sessionExists !== 'function') {
    throw new Error('validateSessionFile required');
  }
  if (!opQueue || typeof opQueue.enqueue !== 'function') throw new Error('opQueue.enqueue required');

  return (req, res) => {
    let accountNum;
    try {
      accountNum = parseAccountNum(req && req.params && req.params.num);
    } catch {
      return res.status(400).json({ error: 'invalid accountNum' });
    }

    let accounts;
    try {
      accounts = readAccounts();
    } catch (error) {
      return res.status(500).json({ ok: false, error: `读取账号配置失败: ${error.message}` });
    }
    const account = accounts && accounts[accountNum];
    if (!account) return res.status(404).json({ ok: false, error: `账号${accountNum}不存在` });

    let statusMap;
    try {
      statusMap = readAccountStatus();
    } catch (error) {
      return res.status(423).json({ ok: false, error: `读取账号状态失败: ${error.message}` });
    }
    const guard = getAccountOpenGuard(statusMap && statusMap[accountNum] || {});
    if (!guard.ok) {
      return res.status(409).json({ ok: false, error: guard.error });
    }

    if (!account.file) {
      return res.status(404).json({ ok: false, error: `账号${accountNum} session 文件不存在，请重新登录` });
    }
    const sessionValidation = validateSession
      ? validateSession({ accountNum, file: account.file })
      : { ok: sessionExists(account.file) };
    if (!sessionValidation || sessionValidation.ok !== true) {
      return res.status(404).json({
        ok: false,
        error: sessionValidation && sessionValidation.error
          ? sessionValidation.error
          : `账号${accountNum} session 文件不存在，请重新登录`,
      });
    }

    const spec = buildA1FixedBatchOp({
      accountNum,
      accountNote: account.note || account.name || `账号${accountNum}`,
    });
    const op = opQueue.enqueue(spec.type, spec.label, spec.params);
    return res.status(202).json({ ok: true, opId: op.id, message: `账号${accountNum}固定清单批次已入队` });
  };
}

module.exports = {
  buildA1FixedBatchOp,
  createA1FixedBatchRouteHandler,
  parseAccountNum,
  validateSessionFile,
};
