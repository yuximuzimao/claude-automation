'use strict';

const { describe, it, afterEach } = require('node:test');
const assert = require('node:assert');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '../..');

function modulePath(rel) {
  return path.join(ROOT, rel);
}

function loadArchiveWithMocks(evalResults) {
  const archivePath = modulePath('lib/product/archive.js');
  const cdpPath = modulePath('lib/cdp.js');
  const navigatePath = modulePath('lib/erp/navigate.js');
  const waitPath = modulePath('lib/wait.js');

  for (const p of [archivePath, cdpPath, navigatePath, waitPath]) {
    delete require.cache[p];
  }

  const evalCalls = [];
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
    },
  };
  require.cache[navigatePath] = {
    id: navigatePath,
    filename: navigatePath,
    loaded: true,
    exports: {
      navigateErp: async () => ({ success: true }),
    },
  };
  require.cache[waitPath] = {
    id: waitPath,
    filename: waitPath,
    loaded: true,
    exports: {
      sleep: async () => {},
      retry: async (fn) => fn(),
    },
  };

  return { ...require(archivePath), evalCalls };
}

afterEach(() => {
  for (const rel of [
    'lib/product/archive.js',
    'lib/cdp.js',
    'lib/erp/navigate.js',
    'lib/wait.js',
  ]) {
    delete require.cache[modulePath(rel)];
  }
});

describe('productArchive suite sub-items', () => {
  it('套装商品子品明细读取失败时，不能返回空 subItems 的成功结果', async () => {
    const { productArchive } = loadArchiveWithMocks([
      { alreadySet: true },
      { searched: 'yyfnsyzh1' },
      {
        outerId: 'yyfnsyzh1',
        title: 'KGOS蛋白多肽营养强化粉 360g-莓果味*1盒+牛油果猕猴桃味*1盒;KGO',
        subItemNum: 2,
        type: '2',
        hasProduct: false,
      },
      { clicked: true },
      { error: '弹窗内未找到子商品行' },
      { closed: 1, remaining: 0 },
    ]);

    const result = await productArchive('erp-target', 'yyfnsyzh1');

    assert.equal(result.success, false);
    assert.match(result.error, /套装商品子品明细读取失败/);
  });

  it('读子品失败时，错误必须带上实际表头/弹窗诊断信息（不能只丢一个字符串）', async () => {
    const { productArchive } = loadArchiveWithMocks([
      { alreadySet: true },
      { searched: '260605- 8' },
      { outerId: '260605- 8', title: '套装X', subItemNum: 6, type: '2', hasProduct: false },
      { clicked: true },
      // 读到的是错误弹窗：表头不匹配 + 携带实际表头与弹窗标题
      { error: '未找到子品明细表头', dialogTitle: '订单详情', headers: ['运单号', '物流公司', '状态'] },
      { closed: 1, remaining: 0 },
    ]);

    const result = await productArchive('erp-target', '260605- 8');

    assert.equal(result.success, false);
    assert.match(result.error, /套装商品子品明细读取失败/);
    // 关键：诊断信息必须透传到最终错误里，下次不用复现就能定位
    assert.match(result.error, /实际表头/);
    assert.match(result.error, /运单号/);
    assert.match(result.error, /订单详情/);
  });

  it('找不到子商品弹窗时，要 dump 可见弹窗列表（诊断埋点）', async () => {
    const { productArchive } = loadArchiveWithMocks([
      { alreadySet: true },
      { searched: '260605- 8' },
      { outerId: '260605- 8', title: '套装X', subItemNum: 6, type: '2', hasProduct: false },
      { clicked: true },
      { error: '未找到子商品弹窗', visibleDialogs: [{ title: '订单详情', cls: 'el-dialog__wrapper trade-detail-dialog' }] },
      { closed: 1, remaining: 0 },
    ]);

    const result = await productArchive('erp-target', '260605- 8');

    assert.equal(result.success, false);
    assert.match(result.error, /可见弹窗/);
    assert.match(result.error, /trade-detail-dialog/);
  });
});
