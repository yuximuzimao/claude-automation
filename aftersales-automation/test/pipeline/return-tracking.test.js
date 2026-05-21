'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert');

// 测试 pageUsedBy 自引用过滤逻辑（pipeline.js 中的过滤代码）
function filterPageUsedBy(pageUsedBy, workOrderNum, dbConflictNums) {
  const filtered = pageUsedBy.filter(n => n !== workOrderNum);
  return [...new Set([...filtered, ...dbConflictNums])];
}

describe('P0-3: 退货单号 pageUsedBy 过滤自身工单号', () => {
  it('pageUsedBy 只有自己 → allUsedBy 为空', () => {
    const result = filterPageUsedBy(
      ['100001775947313424249'],  // pageUsedBy = 当前工单
      '100001775947313424249',     // workOrderNum = 当前工单
      []                            // dbConflictNums = 空
    );
    assert.deepEqual(result, []);
  });

  it('pageUsedBy 含自己和其他工单 → 只保留其他工单', () => {
    const result = filterPageUsedBy(
      ['100001775947313424249', '100001778888888888888'],
      '100001775947313424249',
      []
    );
    assert.deepEqual(result, ['100001778888888888888']);
  });

  it('dbConflictNums 有其他工单 → 合并输出', () => {
    const result = filterPageUsedBy(
      ['100001775947313424249'],
      '100001775947313424249',
      ['100001779999999999999']
    );
    assert.deepEqual(result, ['100001779999999999999']);
  });

  it('pageUsedBy 不含自己 + dbConflictNums 有重复 → 去重', () => {
    const result = filterPageUsedBy(
      ['100001778888888888888'],
      '100001775947313424249',
      ['100001778888888888888']
    );
    assert.deepEqual(result, ['100001778888888888888']);
  });
});
