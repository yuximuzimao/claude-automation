'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function waitFor(predicate) {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const tick = () => {
      try {
        const value = predicate();
        if (value) return resolve(value);
      } catch (error) {
        return reject(error);
      }
      if (Date.now() - started > 1000) return reject(new Error('timed out waiting for op'));
      setTimeout(tick, 10);
    };
    tick();
  });
}

test('op-queue executes a1-fixed-batch through Step14 with no-auto defaults', async () => {
  const step14Path = path.join(__dirname, '../../scripts/jl-steps/14-process-single-account-fixed-batch.js');
  const resolvedStep14 = require.resolve(step14Path);
  const calls = [];
  require.cache[resolvedStep14] = {
    id: resolvedStep14,
    filename: resolvedStep14,
    loaded: true,
    exports: {
      processSingleAccountFixedBatch: async (accountNum, options) => {
        calls.push([accountNum, options]);
        return { success: true, accountNum, items: [] };
      },
    },
  };

  delete require.cache[require.resolve('../../lib/server/op-queue')];
  const opQueue = require('../../lib/server/op-queue');
  const op = opQueue.enqueue('a1-fixed-batch', 'A1固定清单 账号14「茗瑞-KGOS」', {
    accountNum: '14',
    accountNote: '茗瑞-KGOS',
    thresholdHours: 1,
    disableAutoExecute: false,
  });

  const completed = await waitFor(() => opQueue.getState().lastCompleted);

  assert.equal(completed.id, op.id);
  assert.equal(completed.status, 'done');
  assert.deepEqual(calls, [[
    '14',
      {
        thresholdHours: 48,
      },
  ]]);
  assert.deepEqual(completed.result, { success: true, accountNum: '14', items: [] });
});
