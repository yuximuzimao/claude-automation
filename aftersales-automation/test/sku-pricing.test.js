'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const {
  chineseNumberToInt,
  parseGiftPricing,
  resolveSkuPricing,
  saveConfirmedSkuPricing,
  setConfigPathForTests,
} = require('../lib/sku-pricing');

function withTempConfig(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'aftersales-sku-pricing-'));
  const file = path.join(dir, 'sku-pricing.json');
  setConfigPathForTests(file);
  try {
    return fn(file);
  } finally {
    setConfigPathForTests(null);
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('中文数字和阿拉伯数字的买赠名称都能解析', () => {
  assert.equal(chineseNumberToInt('十五'), 15);
  assert.equal(chineseNumberToInt('两'), 2);

  assert.deepEqual(parseGiftPricing('美式风味咖啡15盒送3盒', 18), {
    suspected: true,
    parsed: true,
    pricedQty: 15,
    bundledGiftQty: 3,
  });
  assert.deepEqual(parseGiftPricing('美式风味咖啡 十五盒赠三盒', 18), {
    suspected: true,
    parsed: true,
    pricedQty: 15,
    bundledGiftQty: 3,
  });
  assert.deepEqual(parseGiftPricing('咖啡10盒+2盒', 12), {
    suspected: true,
    parsed: true,
    pricedQty: 10,
    bundledGiftQty: 2,
  });
});

test('普通规格名不因重量或袋数数字被误判为买赠', () => {
  assert.deepEqual(parseGiftPricing('甘油二酯咖啡固体饮料 8g*12袋/盒', 12), {
    suspected: false,
    parsed: false,
    pricedQty: 12,
    bundledGiftQty: 0,
  });
});

test('同规格商家编码保存后复用，ERP实际组成变化时必须重新确认', () => withTempConfig(() => {
  saveConfirmedSkuPricing([{
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡15盒送3盒',
    physicalQty: 18,
    pricedQty: 15,
    bundledGiftQty: 3,
  }], () => '2026-10-12T00:00:00.000Z');

  const reused = resolveSkuPricing({
    specCode: 'KGOS-15-3',
    specName: '名称后来改过，但编码没变',
    physicalQty: 18,
  });
  assert.equal(reused.status, 'resolved');
  assert.equal(reused.source, 'saved');
  assert.equal(reused.pricedQty, 15);
  assert.equal(reused.bundledGiftQty, 3);

  const mismatch = resolveSkuPricing({
    specCode: 'KGOS-15-3',
    specName: '美式风味咖啡18盒送2盒',
    physicalQty: 20,
  });
  assert.equal(mismatch.status, 'confirmation_required');
  assert.equal(mismatch.compositionMismatch, true);
  assert.equal(mismatch.savedPhysicalQty, 18);
  assert.equal(mismatch.physicalQty, 20);
}));
