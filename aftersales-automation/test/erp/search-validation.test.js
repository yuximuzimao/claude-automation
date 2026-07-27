'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  makeSearchJS,
  parsePlatformOrderIds,
  runSearchWithSingleRecovery,
  validatePlatformOrderRows,
} = require('../../lib/erp/search');

test('平台交易号支持单号、中文分号和英文分号', () => {
  assert.deepEqual(parsePlatformOrderIds('756292468'), ['756292468']);
  assert.deepEqual(parsePlatformOrderIds('756292468；756311711'), ['756292468', '756311711']);
  assert.deepEqual(parsePlatformOrderIds('756292468; 756311711'), ['756292468', '756311711']);
});

test('合并发货行只要包含本次搜索子订单号即为有效', () => {
  assert.doesNotThrow(() => validatePlatformOrderRows([
    { platformOrderIds: ['756292468', '756311711'] },
  ], '756292468'));
});

test('任何一行不包含本次搜索子订单号时整次搜索失败', () => {
  assert.throws(() => validatePlatformOrderRows([
    { platformOrderIds: ['756292468', '756311711'] },
    { platformOrderIds: ['999999999'] },
  ], '756292468'), /第2行.*不包含.*756292468/);
});

test('任何一行没有读到平台交易号时整次搜索失败', () => {
  assert.throws(() => validatePlatformOrderRows([
    { platformOrderIds: [] },
  ], '756292468'), /第1行.*未读取到平台交易号/);
});

test('订单搜索保留原有 Enter，不改成点击搜索按钮', () => {
  const expression = makeSearchJS('756292468');
  assert.match(expression, /execCommand\('insertText'/);
  assert.match(expression, /KeyboardEvent/);
  assert.doesNotMatch(expression, /搜索按钮/);
});

test('首次搜索失败时先恢复页面，再且仅再搜一次', async () => {
  const calls = [];
  const result = await runSearchWithSingleRecovery(
    async attempt => {
      calls.push(`search-${attempt}`);
      if (attempt === 0) throw new Error('读到空搜索默认列表');
      return { rows: [{ platformOrderIds: ['756292468'] }] };
    },
    async error => calls.push(`recover-${error.message}`)
  );

  assert.deepEqual(calls, [
    'search-0',
    'recover-读到空搜索默认列表',
    'search-1',
  ]);
  assert.deepEqual(result.rows[0].platformOrderIds, ['756292468']);
});

test('页面恢复后第二次仍失败则停止，不进行第三次搜索', async () => {
  let searchCount = 0;
  let recoverCount = 0;
  await assert.rejects(
    runSearchWithSingleRecovery(
      async () => {
        searchCount++;
        throw new Error(`第${searchCount}次失败`);
      },
      async () => { recoverCount++; }
    ),
    /第2次失败/
  );
  assert.equal(searchCount, 2);
  assert.equal(recoverCount, 1);
});
