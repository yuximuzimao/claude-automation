'use strict';

const fs = require('fs');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');
const cdp = require('../../lib/cdp');
const { clickWorkOrderAction, scrollActionButtonIntoView, waitForNewWorkOrderTarget } = require('../../scripts/jl-steps/12-click-work-order-action');

const WORK_ORDER_NUM = '100001781188621717210';

const scriptPath = path.join(__dirname, '../../scripts/jl-steps/12-click-work-order-action.js');

function useFakeWebSocket(t, Socket) {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'WebSocket');
  Object.defineProperty(globalThis, 'WebSocket', { configurable: true, value: Socket });
  t.after(() => Object.defineProperty(globalThis, 'WebSocket', original));
}

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

test('新标签页识别失败时保留曾出现的标签，并只返回仍存在的目标供清理', async t => {
  let clock = 0;
  t.mock.method(Date, 'now', () => clock);
  t.mock.method(cdp, 'getTargets', async () => {
    clock++;
    return clock === 1
      ? [{ id: 'brief-tab', type: 'page', url: 'about:blank' }]
      : [{ id: 'unexpected-tab', type: 'page', url: 'https://scrm.jlsupp.com/login?secret=test' }];
  });
  t.mock.method(cdp, 'eval', async (id) => {
    if (id === 'brief-tab') throw Object.assign(new Error('read failed'), { cdpDiagnosticId: 'socket-1' });
    return { readyState: 'complete', urlContainsWorkOrderNum: false, bodyContainsWorkOrderNum: false };
  });

  await assert.rejects(
    waitForNewWorkOrderTarget(new Set(['list-tab']), WORK_ORDER_NUM, { timeoutMs: 1, intervalMs: 1 }),
    error => {
      assert.deepEqual(error.newTargetIds, ['unexpected-tab']);
      assert.equal(error.openEvidence.polls, 2);
      const [brief, unexpected] = error.openEvidence.candidates;
      assert.equal(brief.presentAtLastPoll, false);
      assert.equal(brief.lastCdpDiagnosticId, 'socket-1');
      assert.equal(unexpected.presentAtLastPoll, true);
      assert.equal(unexpected.lastPageKind, 'jl_login');
      assert.equal(error.workOrderBrowserFailure, undefined);
      assert.doesNotMatch(JSON.stringify(error.openEvidence), /secret/);
      return true;
    }
  );
});

test('滚动失败保留按钮位置和滚动证据，且不会发出点击', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const wheel = t.mock.method(cdp, 'dispatchMouseEvent', async () => {});
  const initial = { rect: { centerX: 200, centerY: 950 }, viewport: { width: 800, height: 600, scrollY: 0 } };
  const final = { ...initial, rect: { ...initial.rect, centerY: 700 }, scrollContainers: [{ top: 250, maxTop: 250 }] };
  let reads = 0;
  t.mock.method(cdp, 'eval', async () => ({ success: true, button: reads++ ? final : initial }));
  const assertion = assert.rejects(scrollActionButtonIntoView('list-tab', WORK_ORDER_NUM), error => {
    assert.match(error.message, /滚动后仍不在可视区/);
    assert.equal(error.workOrderBrowserFailure, 'button_outside_viewport');
    assert.equal(error.openEvidence.initial.rect.centerY, 950);
    assert.equal(error.openEvidence.final.rect.centerY, 700);
    assert.deepEqual(error.openEvidence.final.scrollContainers, final.scrollContainers);
    assert.equal(error.openEvidence.wheelDeltas.length, wheel.mock.callCount());
    assert.ok(wheel.mock.calls.every(call => call.arguments[1].type === 'mouseWheel'));
    return true;
  });
  for (let step = 0; step < 18; step++) {
    // 让每次模拟滚动后的 Promise 继续到下一次读取。
    await new Promise(resolve => setImmediate(resolve));
    t.mock.timers.tick(180);
  }
  await assertion;
});

test('候选标签标题或读取错误发现风控时立即失败，不等标签消失，也不按工单号兜底通过', async t => {
  let source;
  const getTargets = t.mock.method(cdp, 'getTargets', async () => [{
    id: 'risk-tab', type: 'page',
    url: `https://scrm.jlsupp.com/business/after-sale-detail?workOrderNum=${WORK_ORDER_NUM}`,
    title: source === 'targetTitle' ? 'captcha challenge' : '',
  }]);
  const evaluate = t.mock.method(cdp, 'eval', async () => {
    if (source === 'readError') throw Object.assign(new Error('HTTP 426'), { cdpDiagnosticId: 'cdp-426' });
    return { title: '访问过于频繁', containsWorkOrderNum: true };
  });
  for (source of ['targetTitle', 'pageTitle', 'readError']) {
    await assert.rejects(waitForNewWorkOrderTarget(new Set(['list-tab']), WORK_ORDER_NUM), error => {
      assert.equal(error.browserRiskSignal, true);
      assert.equal(error.workOrderBrowserFailure, undefined);
      assert.equal(error.openEvidence.riskTargetId, 'risk-tab');
      assert.equal(error.openEvidence.riskSource, source);
      if (source === 'readError') assert.equal(error.openEvidence.riskCdpDiagnosticId, 'cdp-426');
      return true;
    });
  }
  assert.equal(getTargets.mock.callCount(), 3);
  assert.equal(evaluate.mock.callCount(), 2);
});

test('共用打开详情步骤持久化风控，下一次调用在读取标签前被熔断拦截', async t => {
  const listTab = { id: 'list-tab', type: 'page', url: 'https://scrm.jlsupp.com/business/after-sale-list' };
  let reads = 0;
  t.mock.method(cdp, 'getTargets', async () => reads++ === 0
    ? [listTab]
    : [listTab, { id: 'risk-tab', type: 'page', url: 'about:blank', title: 'captcha' }]);
  t.mock.method(cdp, 'eval', async () => ({
    success: true, button: { rect: { centerX: 200, centerY: 300 }, viewport: { width: 800, height: 600 } },
  }));
  const mouse = t.mock.method(cdp, 'dispatchMouseEvent', async () => {});
  t.mock.method(cdp, 'logBrowserDiagnostic', () => {});
  let state;
  const circuit = {
    read: () => state,
    trip: (error, label) => { state = { tripped: true, reason: error.message, label }; },
  };
  const options = { targetId: 'list-tab', circuit };
  await assert.rejects(clickWorkOrderAction(WORK_ORDER_NUM, options), error => {
    assert.equal(error.browserRiskSignal, true);
    assert.equal(error.browserRiskHandled, true);
    return true;
  });
  assert.equal(state.label, 'jl_work_order_detail');
  await assert.rejects(clickWorkOrderAction(WORK_ORDER_NUM, options), /风控熔断中/);
  assert.equal(reads, 2);
  assert.equal(mouse.mock.callCount(), 3);
});

test('CDP 连接错误关联一次只读现场快照，保留错误并区分目标状态和发送阶段', async t => {
  const sockets = [];
  class Socket extends EventTarget {
    constructor() { super(); sockets.push(this); }
    send() {}
    close() {}
  }
  useFakeWebSocket(t, Socket);
  const lines = [];
  t.mock.method(console, 'error', line => lines.push(JSON.parse(line.slice(line.indexOf('{')))));
  const targets = t.mock.method(cdp, 'getTargets', async () => {
    if (sockets.length === 1) return [{ id: 'other', type: 'page' }];
    if (sockets.length === 2) return [{ id: 'detail', type: 'page', url: 'https://scrm.jlsupp.com/business/after-sale-detail?secret=test' }];
    throw Object.assign(new Error('local port down'), { code: 'ECONNREFUSED' });
  });

  for (const [opened, result] of [[false, 'target_absent'], [true, 'target_present'], [false, 'target_list_unavailable']]) {
    const operation = cdp.cdpCall('detail', 'Input.dispatchMouseEvent', { type: 'mousePressed', sensitive: 'omit-test' });
    const socket = sockets.at(-1);
    if (opened) socket.dispatchEvent(new Event('open'));
    socket.dispatchEvent(Object.assign(new Event('error'), {
      message: 'original failure',
      error: Object.assign(new Error(), { cause: { statusCode: 404 } }),
    }));
    await assert.rejects(operation, error => {
      assert.equal(error.message, 'WebSocket error: original failure');
      const event = lines.find(line => line.diagnosticId === error.cdpDiagnosticId);
      assert.equal(event.targetId, 'detail');
      assert.equal(event.handshakeHttpStatus, 404);
      assert.equal(event.method, 'Input.dispatchMouseEvent');
      assert.equal(event.mouseEvent, 'mousePressed');
      assert.equal(event.commandSent, opened);
      assert.equal(event.kind, opened ? 'socket_error' : 'handshake_error');
      cdp.captureFailedTarget(error);
      return true;
    });
    await new Promise(resolve => setImmediate(resolve));
    const snapshot = lines.at(-1);
    assert.equal(snapshot.result, result);
    assert.equal(snapshot.diagnosticId, lines.at(-2).diagnosticId);
  }
  assert.equal(targets.mock.callCount(), 3);
  assert.equal(sockets.length, 3);
  assert.doesNotMatch(JSON.stringify(lines), /secret|omit-test/);

  const stopped = AbortSignal.abort();
  cdp.captureFailedTarget({ cdpDiagnosticId: 'no-probe', cdpTargetId: 'detail' }, stopped);
  assert.equal(targets.mock.callCount(), 3);
});

test('CDP 协议拒绝保留原错误并记录协议错误码，与连接失败分开', async t => {
  let socket;
  let request;
  class Socket extends EventTarget {
    constructor() { super(); socket = this; }
    send(data) { request = JSON.parse(data); }
    close() {}
  }
  useFakeWebSocket(t, Socket);
  const logs = [];
  t.mock.method(console, 'error', line => logs.push(JSON.parse(line.slice(line.indexOf('{')))));
  const call = cdp.cdpCall('detail', 'Runtime.evaluate', { expression: 'private-payload' }, 100);
  socket.dispatchEvent(new Event('open'));
  socket.dispatchEvent(new MessageEvent('message', { data: JSON.stringify({
    id: request.id, error: { code: -32000, message: 'No execution context' },
  }) }));
  await assert.rejects(call, error => {
    assert.equal(error.message, 'No execution context');
    assert.equal(error.cdpFailureKind, 'protocol_error');
    assert.equal(logs[0].diagnosticId, error.cdpDiagnosticId);
    assert.equal(logs[0].protocolErrorCode, -32000);
    assert.equal(logs[0].commandSent, true);
    return true;
  });
  assert.doesNotMatch(JSON.stringify(logs), /private-payload/);
});
