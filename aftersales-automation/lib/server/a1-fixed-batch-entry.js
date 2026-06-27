'use strict';

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

function createA1FixedBatchRouteHandler({ readAccounts, sessionExists, opQueue }) {
  if (typeof readAccounts !== 'function') throw new Error('readAccounts required');
  if (typeof sessionExists !== 'function') throw new Error('sessionExists required');
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
    if (!account.file || !sessionExists(account.file)) {
      return res.status(404).json({ ok: false, error: `账号${accountNum} session 文件不存在，请重新登录` });
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
};
