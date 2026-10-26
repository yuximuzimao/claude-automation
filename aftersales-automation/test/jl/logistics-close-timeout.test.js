'use strict';

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '../..');

function modulePath(rel) {
  return path.join(ROOT, rel);
}

function loadLogisticsWithMocks({ evalResults, waitForImpl }) {
  const logisticsPath = modulePath('lib/jl/logistics.js');
  const cdpPath = modulePath('lib/cdp.js');
  const navigatePath = modulePath('lib/jl/navigate.js');
  const waitPath = modulePath('lib/wait.js');

  delete require.cache[logisticsPath];
  delete require.cache[cdpPath];
  delete require.cache[navigatePath];
  delete require.cache[waitPath];

  const evalCalls = [];
  const clickPointCalls = [];
  const sleepCalls = [];
  require.cache[cdpPath] = {
    id: cdpPath,
    filename: cdpPath,
    loaded: true,
    exports: {
      eval: async (targetId, js) => {
        evalCalls.push({ targetId, js });
        const next = evalResults.shift();
        if (next instanceof Error) throw next;
        return next;
      },
      clickPoint: async (targetId, x, y) => {
        clickPointCalls.push({ targetId, x, y });
        return { clicked: true, x, y };
      },
    },
  };
  require.cache[navigatePath] = {
    id: navigatePath,
    filename: navigatePath,
    loaded: true,
    exports: { navigate: async () => ({ navigated: true }) },
  };
  require.cache[waitPath] = {
    id: waitPath,
    filename: waitPath,
    loaded: true,
    exports: {
      sleep: async (ms) => {
        sleepCalls.push(ms);
      },
      waitFor: waitForImpl,
    },
  };

  return { ...require(logisticsPath), evalCalls, clickPointCalls, sleepCalls };
}

afterEach(() => {
  for (const rel of ['lib/jl/logistics.js', 'lib/cdp.js', 'lib/jl/navigate.js', 'lib/wait.js']) {
    delete require.cache[modulePath(rel)];
  }
});

it('退货签收分类只接受明确签收，否定、在途和空状态均不能判已签收', () => {
  const { classifyReturnLogistics } = require('../../lib/jl/logistics');
  for (const text of ['已签收', '签收\n2026-10-26 08:00', '已妥投', '快件由本人签收']) {
    assert.equal(classifyReturnLogistics(text), 'signed', text);
  }
  for (const text of ['尚未签收', '待签收', '签收失败', '运输中', '拒签']) {
    assert.equal(classifyReturnLogistics(text), 'not_signed', text);
  }
  assert.equal(classifyReturnLogistics('暂无信息'), 'unknown');
});

it('退货页面读取只定位可见退货模块，不点击原发货或隐藏模块', () => {
  const { readReturnLogisticsSectionFromPage } = require('../../lib/jl/logistics');
  const clicked = [];
  const section = (title, text, id, hidden = false) => ({
    innerText: text,
    getBoundingClientRect: () => ({ width: hidden ? 0 : 500, height: hidden ? 0 : 100 }),
    querySelector: () => ({ innerText: title }),
    querySelectorAll: () => [{
      innerText: '查看物流', getBoundingClientRect: () => ({ width: 80, height: 30 }),
      click: () => clicked.push(id),
    }],
  });
  const outbound = section('订单物流信息', 'JT1234567890123\n已签收', '原发货');
  const inbound = section('退货物流信息', '退货物流单号：JT1234567890123', '退货');
  const hidden = section('退货物流信息', 'JT1234567890123\n已签收', '隐藏', true);
  const read = Function('document', 'tracking', 'open', `return (${readReturnLogisticsSectionFromPage.toString()})(tracking, open)`);
  const result = read({ querySelectorAll: () => [outbound, hidden, inbound] }, 'JT1234567890123', true);
  assert.equal(result.opened, true);
  assert.equal(result.text, inbound.innerText);
  assert.deepEqual(clicked, ['退货']);
  const mismatch = read({ querySelectorAll: () => [inbound] }, 'JT9999999999999', true);
  assert.equal(mismatch.text, '');
  assert.match(mismatch.warnings.join(''), /不一致/);
  assert.deepEqual(clicked, ['退货']);
});

it('退货区块已有明确签收时直接读取，不打开物流弹窗', async () => {
  const loaded = loadLogisticsWithMocks({
    evalResults: [{ text: 'JT1234567890123\n已签收', canOpen: true, warnings: [] }],
    waitForImpl: async () => assert.fail('已有明确签收无需打开弹窗'),
  });
  const result = await loaded.getReturnLogistics('detail-tab', 'work-order', 'JT1234567890123');
  assert.equal(result.success, true);
  assert.equal(result.data.status, 'signed');
  assert.equal(loaded.evalCalls.length, 1);
});

it('退货物流弹窗核对同一运单后读签收并关闭本次弹窗', async () => {
  const evalResults = [
    { text: 'JT1234567890123', canOpen: true, warnings: [] },
    0, { opened: true }, 1,
    { currentText: '物流单号：JT1234567890123\n已签收' },
    1, { closed: true }, 0,
  ];
  const loaded = loadLogisticsWithMocks({
    evalResults,
    waitForImpl: async predicate => {
      const value = await predicate();
      if (!value) throw new Error('测试等待失败');
      return value;
    },
  });
  const result = await loaded.getReturnLogistics('detail-tab', 'work-order', 'JT1234567890123');
  assert.equal(result.success, true);
  assert.equal(result.data.status, 'signed');
  assert.equal(evalResults.length, 0, '本次弹窗必须已关闭并读回确认');
  assert.equal(loaded.clickPointCalls.length, 0);
});

it('弹窗是其他运单时不采信签收，停止读取并关闭弹窗，不重试点击', async () => {
  const evalResults = [
    { text: 'JT1234567890123', canOpen: true, warnings: [] },
    0, { opened: true }, 1,
    { currentText: '物流单号：OTHER1234567890\n已签收' },
    1, { closed: true }, 0,
  ];
  const loaded = loadLogisticsWithMocks({
    evalResults,
    waitForImpl: async predicate => {
      const value = await predicate();
      if (!value) throw new Error('对应运单物流未确认');
      return value;
    },
  });
  const result = await loaded.getReturnLogistics('detail-tab', 'work-order', 'JT1234567890123');
  assert.equal(result.success, false);
  assert.match(result.error, /对应运单物流未确认/);
  assert.equal(evalResults.length, 0);
  assert.equal(loaded.evalCalls.filter(call => call.js.endsWith(', true)')).length, 1);
});

describe('JL logistics close timeout tolerance', () => {
  it('拒绝流程复用局部关闭能力，关闭失败会在打开拒绝表单前停止', () => {
    const source = fs.readFileSync(modulePath('lib/jl/reject.js'), 'utf8');
    const closeIndex = source.indexOf('await closeLogisticsDialog(targetId, beforeClose)');
    const formIndex = source.indexOf('const alreadyOpen = await cdp.eval');

    assert.ok(closeIndex > 0, 'reject.js 应调用共享物流弹窗关闭能力');
    assert.ok(formIndex > closeIndex, '必须先确认物流弹窗关闭，再打开拒绝表单');
    assert.doesNotMatch(source, /reject-close-dialog/);
  });

  for (const { label, falseChecks } of [
    { label: '约800ms', falseChecks: 3 },
    { label: '约2s', falseChecks: 7 },
    { label: '接近5s', falseChecks: 16 },
  ]) {
    it(`关闭动画延迟${label}时持续只读等待，不重复点击`, async () => {
      let waitOptions = null;
      const evalResults = [
        { closed: true },
        ...Array(falseChecks).fill(2),
        1,
      ];
      const loaded = loadLogisticsWithMocks({
        evalResults,
        waitForImpl: async (predicate, options) => {
          waitOptions = options;
          for (let i = 0; i <= falseChecks; i++) {
            if (await predicate()) return true;
          }
          throw new Error('测试轮询未观察到弹窗关闭');
        },
      });

      const result = await loaded.closeLogisticsDialog('target-1', 2);

      assert.deepEqual(result, { closed: true, method: 'dialog-button' });
      assert.deepEqual(waitOptions, {
        timeoutMs: 5000,
        intervalMs: 300,
        label: '等待物流弹窗关闭',
      });
      assert.equal(loaded.clickPointCalls.length, 0);
      assert.equal(
        loaded.evalCalls.filter(call => call.js.includes('btn.click()')).length,
        1,
        '主关闭按钮只能点击一次'
      );
    });
  }

  it('页面同时有其他弹窗时，只要求可见弹窗数量减少，不要求全部消失', async () => {
    const loaded = loadLogisticsWithMocks({
      evalResults: [
        { closed: true },
        1,
      ],
      waitForImpl: async (predicate) => {
        assert.equal(await predicate(), true);
        return true;
      },
    });

    const result = await loaded.closeLogisticsDialog('target-1', 2);

    assert.equal(result.method, 'dialog-button');
    assert.match(loaded.evalCalls[0].js, /dialogs\[dialogs\.length - 1\]/);
    assert.equal(loaded.clickPointCalls.length, 0);
  });

  it('主关闭等待超时但固定坐标后备成功时，不记录关闭失败', async () => {
    let waitCount = 0;
    const { getLogistics, clickPointCalls, sleepCalls } = loadLogisticsWithMocks({
      evalResults: [
        0,
        1,
        'clicked',
        {
          tabCount: 1,
          tabs: [{ name: '包裹1', active: true }],
          currentText: '圆通速递 YT7623787786161\n2026-05-29 18:17 温州转运中心 已发出',
        },
        1,
        { closed: true },
      ],
      waitForImpl: async () => {
        waitCount += 1;
        if (waitCount === 1) throw new Error('waitFor 超时: 等待物流弹窗关闭');
        return true;
      },
    });

    const result = await getLogistics('target-1', '100001779964261761607');

    assert.equal(result.success, true);
    assert.equal(result.data.packages.length, 1);
    assert.deepEqual(result.data.warnings, []);
    assert.deepEqual(result.data.closeErrors, []);
    assert.equal(clickPointCalls.length, 1);
    assert.ok(sleepCalls.includes(3000), `关闭前应等待 3000ms，实际: ${JSON.stringify(sleepCalls)}`);
  });

  it('关闭物流弹窗超时时，保留已读取包裹并附加告警', async () => {
    const closeError = new Error('waitFor 超时: 等待物流弹窗关闭');
    const { getLogistics, clickPointCalls, sleepCalls } = loadLogisticsWithMocks({
      evalResults: [
        0,
        1,
        'clicked',
        {
          tabCount: 1,
          tabs: [{ name: '包裹1', active: true }],
          currentText: '圆通速递 YT7623787786161\n2026-05-29 18:17 温州转运中心 已发出',
        },
        { dialogId: 'jl-logistics-dialog-1', visible: true },
        { clicked: true, dialogId: 'jl-logistics-dialog-1' },
      ],
      waitForImpl: async () => {
        throw closeError;
      },
    });

    const result = await getLogistics('target-1', '100001779964261761607');

    assert.equal(result.success, true);
    assert.equal(result.data.packages.length, 1);
    assert.match(result.data.packages[0].text, /YT7623787786161/);
    assert.ok(result.data.warnings.some(w => w.includes('关闭物流弹窗失败')));
    assert.equal(result.data.closeErrors.length, 1);
    assert.match(result.data.closeErrors[0].message, /等待物流弹窗关闭/);
    assert.equal(clickPointCalls.length, 1);
    assert.ok(sleepCalls.includes(3000), `关闭前应等待 3000ms，实际: ${JSON.stringify(sleepCalls)}`);
    assert.deepEqual(
      { x: clickPointCalls[0].x, y: clickPointCalls[0].y },
      { x: 987, y: 184 }
    );
  });
});
