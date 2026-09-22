'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { retry } = require('../lib/wait');

test('AbortError 立即停止重试，不继续等待或执行下一次', async () => {
  let attempts = 0;
  const error = new Error('操作已被用户停止');
  error.name = 'AbortError';

  await assert.rejects(
    retry(async () => {
      attempts++;
      throw error;
    }, { maxRetries: 8, delayMs: 1000 }),
    candidate => candidate === error
  );

  assert.equal(attempts, 1);
});
