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
});
