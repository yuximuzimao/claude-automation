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
