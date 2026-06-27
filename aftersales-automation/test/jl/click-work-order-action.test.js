'use strict';

const fs = require('fs');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');
const { waitForNewWorkOrderTarget } = require('../../scripts/jl-steps/12-click-work-order-action');

const WORK_ORDER_NUM = '100001781188621717210';

const scriptPath = path.join(__dirname, '../../scripts/jl-steps/12-click-work-order-action.js');

test('findUniqueWorkOrderContainerData fails when the work order has no unique container', () => {
const {
    findUniqueWorkOrderContainerData,
  } = require('../../scripts/jl-steps/12-click-work-order-action');

  assert.throws(
    () => findUniqueWorkOrderContainerData([], '100001781188621717210'),
    /工单号匹配数量异常: 0/
  );
});

test('findUniqueWorkOrderContainerData fails when multiple containers contain the work order', () => {
  const {
    findUniqueWorkOrderContainerData,
  } = require('../../scripts/jl-steps/12-click-work-order-action');

  const containers = [
    { text: '售后工单号：100001781188621717210\n处理', actionButtonCount: 1 },
    { text: '售后工单号：100001781188621717210\n查看', actionButtonCount: 1 },
  ];

  assert.throws(
    () => findUniqueWorkOrderContainerData(containers, '100001781188621717210'),
    /唯一工单容器匹配数量异常: 2/
  );
});

test('findUniqueWorkOrderContainerData fails when the container has multiple action buttons', () => {
  const {
    findUniqueWorkOrderContainerData,
  } = require('../../scripts/jl-steps/12-click-work-order-action');

  const containers = [
    { text: '售后工单号：100001781188621717210\n处理\n查看', actionButtonCount: 2 },
  ];

  assert.throws(
    () => findUniqueWorkOrderContainerData(containers, '100001781188621717210'),
    /处理按钮匹配数量异常: 2/
  );
});

test('findUniqueWorkOrderContainerData returns the only exact work order container', () => {
  const {
    findUniqueWorkOrderContainerData,
  } = require('../../scripts/jl-steps/12-click-work-order-action');

  const containers = [
    { text: '售后工单号：100001781188621717210\n处理', actionButtonCount: 1 },
    { text: '售后工单号：100001781188621717211\n处理', actionButtonCount: 1 },
  ];

  const result = findUniqueWorkOrderContainerData(containers, '100001781188621717210');

  assert.equal(result.text, containers[0].text);
});

test('buildFindActionButtonExpression embeds exact work order and avoids DOM click usage', () => {
  const {
    buildFindActionButtonExpression,
  } = require('../../scripts/jl-steps/12-click-work-order-action');

  const expression = buildFindActionButtonExpression('100001781188621717210');

  assert.match(expression, /100001781188621717210/);
  assert.match(expression, /售后处理/);
  assert.doesNotMatch(expression, /\.click\s*\(/);
});

test('source does not trigger action buttons with DOM click', () => {
  const source = fs.readFileSync(scriptPath, 'utf8');

  assert.doesNotMatch(source, /\.click\s*\(/);
  assert.match(source, /Input\.dispatchMouseEvent/);
  assert.match(source, /mouseMoved/);
  assert.match(source, /mousePressed/);
  assert.match(source, /mouseReleased/);
});

test('新tab识别失败时错误携带本次新增targetId供编排清理', async () => {
  const originalGetTargets = cdp.getTargets;
  cdp.getTargets = async () => [{ id: 'unexpected-tab', type: 'page', url: 'https://scrm.jlsupp.com/other' }];
  try {
    await assert.rejects(
      waitForNewWorkOrderTarget(new Set(['list-tab']), WORK_ORDER_NUM, { timeoutMs: 1, intervalMs: 1 }),
      error => {
        assert.deepEqual(error.newTargetIds, ['unexpected-tab']);
        return true;
      }
    );
  } finally {
    cdp.getTargets = originalGetTargets;
  }
});
