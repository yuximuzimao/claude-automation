'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  parsePlatformOrderIds,
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
