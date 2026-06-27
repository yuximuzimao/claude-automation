'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { normalizeAfterSaleType } = require('../../lib/jl/after-sale-type');

test('normalizeAfterSaleType 统一仅退款文案和数字类型', () => {
  assert.equal(normalizeAfterSaleType('仅退款（无需退货）'), '仅退款');
  assert.equal(normalizeAfterSaleType('仅退款'), '仅退款');
  assert.equal(normalizeAfterSaleType(323), '仅退款');
  assert.equal(normalizeAfterSaleType('323'), '仅退款');
});

test('normalizeAfterSaleType 保留其他已知售后类型，未知值返回 null', () => {
  assert.equal(normalizeAfterSaleType('退货退款'), '退货退款');
  assert.equal(normalizeAfterSaleType('换货'), '换货');
  assert.equal(normalizeAfterSaleType('补寄'), '补寄');
  assert.equal(normalizeAfterSaleType(null), null);
  assert.equal(normalizeAfterSaleType('未知'), null);
});
