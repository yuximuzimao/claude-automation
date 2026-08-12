'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../lib/cdp');
const { _test } = require('../lib/workflow');

const { TIMING, waitForAssociationOrderLoad } = _test;

test('关联订单慢加载时持续等待，不会在前几次未就绪时提前失败', async () => {
  const originalEval = cdp.eval;
  let checks = 0;
  let inspectedExpression = '';

  cdp.eval = async (_targetId, expression) => {
    checks += 1;
    inspectedExpression = expression;
    return checks >= 4;
  };

  try {
    const loaded = await waitForAssociationOrderLoad('test-target', {
      timeoutMs: 100,
      intervalMs: 1,
    });

    assert.equal(loaded, true);
    assert.equal(checks, 4);
    assert.match(inspectedExpression, /继续关联/);
    assert.match(inspectedExpression, /新建售后工单/);
  } finally {
    cdp.eval = originalEval;
  }
});

test('关联订单等待使用保守的生产节奏', () => {
  assert.ok(TIMING.slowPollIntervalMs >= 1000);
  assert.ok(TIMING.networkSettleMs >= 1500);
  assert.ok(TIMING.associationLoadTimeoutMs >= 45000);
});

test('关联订单始终未加载时仍保留明确的超时错误', async () => {
  const originalEval = cdp.eval;
  cdp.eval = async () => false;

  try {
    await assert.rejects(
      waitForAssociationOrderLoad('test-target', { timeoutMs: 8, intervalMs: 1 }),
      /waitFor 超时: 等关联弹窗消失\+订单加载/
    );
  } finally {
    cdp.eval = originalEval;
  }
});
