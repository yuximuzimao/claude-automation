'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  requireKnownBrand,
  requireRecordBrand,
  assertSameBrand,
} = require('../lib/brand-scope');

test('explicit brand is normalized and must exist', () => {
  assert.equal(requireKnownBrand(' KGOS '), 'kgos');
  assert.throws(() => requireKnownBrand(''), /缺少品牌/);
  assert.throws(() => requireKnownBrand('not-a-brand'), /未知品牌/);
});

test('record brand must be present and unique for the shop', () => {
  const records = {
    a: { platformCode: 'a', shopName: '澜泽', brand: 'kgos' },
    b: { platformCode: 'b', shopName: '澜泽', brand: 'KGOS' },
    c: { platformCode: 'c', shopName: '其他', brand: 'hee' },
  };
  assert.equal(requireRecordBrand(records, '澜泽'), 'kgos');

  assert.throws(() => requireRecordBrand({
    a: { platformCode: 'a', shopName: '澜泽' },
  }, '澜泽'), /缺少品牌字段/);

  assert.throws(() => requireRecordBrand({
    a: { platformCode: 'a', shopName: '澜泽', brand: 'kgos' },
    b: { platformCode: 'b', shopName: '澜泽', brand: 'hee' },
  }, '澜泽'), /品牌不唯一/);
});

test('stored/report brand mismatch is rejected', () => {
  assert.equal(assertSameBrand('kgos', 'KGOS', '报告'), 'kgos');
  assert.throws(() => assertSameBrand('kgos', 'hee', '报告'), /品牌不一致/);
});
