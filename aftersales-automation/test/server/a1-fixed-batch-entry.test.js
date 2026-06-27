'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildA1FixedBatchOp,
  createA1FixedBatchRouteHandler,
  parseAccountNum,
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
  assert.equal(op.label, 'A1固定清单 账号14「茗瑞-KGOS」');
  assert.deepEqual(op.params, {
    accountNum: '14',
    accountNote: '茗瑞-KGOS',
    thresholdHours: 48,
    disableAutoExecute: true,
  });
});

test('route handler validates account and enqueues single-account fixed batch op', () => {
  const enqueued = [];
  const handler = createA1FixedBatchRouteHandler({
    readAccounts: () => ({
      14: { file: 'account14.json', name: '账号14', note: '茗瑞-KGOS' },
    }),
    sessionExists: file => file === 'account14.json',
    opQueue: {
      enqueue: (type, label, params) => {
        enqueued.push({ type, label, params });
        return { id: 'op-a1-14' };
      },
    },
  });
  const res = fakeResponse();

  handler({ params: { num: '14' }, body: {} }, res);

  assert.equal(res.statusCode, 202);
  assert.deepEqual(res.body, { ok: true, opId: 'op-a1-14', message: '账号14固定清单批次已入队' });
  assert.deepEqual(enqueued, [{
    type: 'a1-fixed-batch',
    label: 'A1固定清单 账号14「茗瑞-KGOS」',
    params: {
      accountNum: '14',
      accountNote: '茗瑞-KGOS',
      thresholdHours: 48,
      disableAutoExecute: true,
    },
  }]);
});

test('route handler rejects invalid, missing, or unsaved accounts before enqueue', () => {
  const opQueue = { enqueue: () => assert.fail('invalid account must not enqueue') };

  let res = fakeResponse();
  createA1FixedBatchRouteHandler({ readAccounts: () => ({}), sessionExists: () => true, opQueue })(
    { params: { num: 'abc' }, body: {} },
    res
  );
  assert.equal(res.statusCode, 400);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({ readAccounts: () => ({}), sessionExists: () => true, opQueue })(
    { params: { num: '14' }, body: {} },
    res
  );
  assert.equal(res.statusCode, 404);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { file: 'account14.json', note: '茗瑞-KGOS' } }),
    sessionExists: () => false,
    opQueue,
  })({ params: { num: '14' }, body: {} }, res);
  assert.equal(res.statusCode, 404);

  res = fakeResponse();
  createA1FixedBatchRouteHandler({
    readAccounts: () => ({ 14: { note: '茗瑞-KGOS' } }),
    sessionExists: () => assert.fail('missing session file must not call sessionExists'),
    opQueue,
  })({ params: { num: '14' }, body: {} }, res);
  assert.equal(res.statusCode, 404);
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
