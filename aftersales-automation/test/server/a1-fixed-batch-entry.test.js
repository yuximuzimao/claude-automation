'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildA1FixedBatchOp,
  createA1FixedBatchRouteHandler,
  parseAccountNum,
  validateSessionFile,
} = require('../../lib/server/a1-fixed-batch-entry');

test('parseAccountNum accepts positive numeric account ids only', () => {
  assert.equal(parseAccountNum('14'), '14');
  assert.equal(parseAccountNum(14), '14');
  assert.throws(() => parseAccountNum('abc'), /invalid accountNum/);
  assert.throws(() => parseAccountNum('0'), /invalid accountNum/);
});

test('buildA1FixedBatchOp always defaults to no-auto fixed 48h live batch', () => {
  const op = buildA1FixedBatchOp({
    accountNum: '14',
    accountNote: '茗瑞-KGOS',
  });

  assert.equal(op.type, 'a1-fixed-batch');
  assert.equal(op.label, '处理工单 账号14「茗瑞-KGOS」');
  assert.deepEqual(op.params, {
    accountNum: '14',
    accountNote: '茗瑞-KGOS',
    thresholdHours: 48,
  });
});

test('route handler validates account and enqueues single-account fixed batch op', () => {
  const enqueued = [];
  const handler = createA1FixedBatchRouteHandler({
    readAccounts: () => ({
      14: { file: 'account14.json', name: '账号14', note: '茗瑞-KGOS' },
    }),
    readAccountStatus: () => ({ 14: { status: 'ok' } }),
    validateSessionFile: ({ file }) => ({ ok: file === 'account14.json' }),
    opQueue: {
      enqueue: (type, label, params) => {
        enqueued.push({ type, label, params });
        return { id: 'op-a1-14' };
      },
    },
  });
  const res = fakeResponse();

  handler({
    params: { num: '14' },
    body: { disableAutoExecute: false, thresholdHours: 1, accounts: ['1', '14'] },
  }, res);

  assert.equal(res.statusCode, 202);
  assert.deepEqual(res.body, { ok: true, opId: 'op-a1-14', message: '账号14固定清单批次已入队' });
  assert.deepEqual(enqueued, [{
    type: 'a1-fixed-batch',
    label: '处理工单 账号14「茗瑞-KGOS」',
    params: {
      accountNum: '14',
      accountNote: '茗瑞-KGOS',
      thresholdHours: 48,
    },
  }]);
});

test('route handler rejects invalid, missing, or unsaved accounts before enqueue', () => {
  const opQueue = { enqueue: () => assert.fail('invalid account must not enqueue') };

  let res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({}),
    readAccountStatus: () => ({}),
    validateSessionFile: () => ({ ok: true }),
    opQueue,
  })(
    { params: { num: 'abc' }, body: {} },
    res
  );
  assert.equal(res.statusCode, 400);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({}),
    readAccountStatus: () => ({}),
    validateSessionFile: () => ({ ok: true }),
    opQueue,
  })(
    { params: { num: '14' }, body: {} },
    res
  );
  assert.equal(res.statusCode, 404);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { file: 'account14.json', note: '茗瑞-KGOS' } }),
    readAccountStatus: () => ({ 14: { status: 'ok' } }),
    validateSessionFile: () => ({ ok: false, error: 'session invalid' }),
    opQueue,
  })({ params: { num: '14' }, body: {} }, res);
  assert.equal(res.statusCode, 404);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { note: '茗瑞-KGOS' } }),
    readAccountStatus: () => ({ 14: { status: 'ok' } }),
    validateSessionFile: () => assert.fail('missing session file must not validate session'),
    opQueue,
  })({ params: { num: '14' }, body: {} }, res);
  assert.equal(res.statusCode, 404);
});

test('route handler fail-closes on account status errors and status read failures', () => {
  const opQueue = { enqueue: () => assert.fail('blocked account must not enqueue') };

  let res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { file: 'account14.json', note: '茗瑞-KGOS' } }),
    readAccountStatus: () => ({ 14: { status: 'expired', error: '登录已失效' } }),
    validateSessionFile: () => ({ ok: true }),
    opQueue,
  })({ params: { num: '14' }, body: { confirmed: true } }, res);
  assert.equal(res.statusCode, 409);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { file: 'account14.json', note: '茗瑞-KGOS' } }),
    readAccountStatus: () => { throw new Error('EIO'); },
    validateSessionFile: () => ({ ok: true }),
    opQueue,
  })({ params: { num: '14' }, body: {} }, res);
  assert.equal(res.statusCode, 423);
});

test('validateSessionFile rejects unsafe or unusable session files', () => {
  const sessionsDir = '/safe/sessions';
  const validPath = '/safe/sessions/account14.json';
  const files = {
    [validPath]: JSON.stringify({
      cookies: [{ name: 'JSESSIONID', value: 'token', domain: 'scrm.jlsupp.com' }],
      origins: [{
        origin: 'https://scrm.jlsupp.com',
        localStorage: [{ name: '__supplierId__', value: 'supplier-14' }],
      }],
    }),
    '/safe/sessions/bad.json': '{bad',
    '/safe/sessions/no-auth.json': JSON.stringify({
      cookies: [],
      origins: [{
        origin: 'https://scrm.jlsupp.com',
        localStorage: [{ name: '__supplierId__', value: 'supplier-14' }],
      }],
    }),
    '/safe/sessions/no-identity.json': JSON.stringify({
      cookies: [{ name: 'JSESSIONID', value: 'token', domain: 'scrm.jlsupp.com' }],
      origins: [{ origin: 'https://scrm.jlsupp.com', localStorage: [] }],
    }),
  };
  const fsImpl = {
    realpathSync: p => (p === sessionsDir || files[p] ? p : '/outside/account14.json'),
    readFileSync: p => files[p],
  };

  assert.deepEqual(validateSessionFile({ accountNum: '14', file: 'account14.json', sessionsDir, fsImpl }), { ok: true });
  assert.equal(validateSessionFile({ accountNum: '14', file: '../account14.json', sessionsDir, fsImpl }).ok, false);
  assert.equal(validateSessionFile({ accountNum: '14', file: 'account13.json', sessionsDir, fsImpl }).ok, false);
  assert.equal(validateSessionFile({ accountNum: '14', file: 'bad.json', sessionsDir, fsImpl }).ok, false);
  assert.equal(validateSessionFile({ accountNum: '14', file: 'no-auth.json', sessionsDir, fsImpl }).ok, false);
  assert.equal(validateSessionFile({ accountNum: '14', file: 'no-identity.json', sessionsDir, fsImpl }).ok, false);
});

function fakeResponse() {
  return {
    statusCode: 200,
    body: null,
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.body = payload;
      return this;
    },
  };
}
