'use strict';

const fs = require('fs');
const path = require('path');

const PRODUCTS_DIR = path.join(__dirname, '../data/products');

function listKnownBrands() {
  if (!fs.existsSync(PRODUCTS_DIR)) return [];
  return fs.readdirSync(PRODUCTS_DIR)
    .filter(name => fs.existsSync(path.join(PRODUCTS_DIR, name, 'features.json')))
    .sort();
}

function requireKnownBrand(value, context = '本轮商品匹配') {
  const brand = String(value || '').trim().toLowerCase();
  if (!brand) {
    throw new Error(`${context}缺少品牌，请在首次 check 时使用 --brand <品牌>`);
  }
  if (!fs.existsSync(path.join(PRODUCTS_DIR, brand, 'features.json'))) {
    const known = listKnownBrands();
    throw new Error(`未知品牌「${brand}」，可用品牌：${known.join(', ') || '无'}`);
  }
  return brand;
}

function requireRecordBrand(records, shopName) {
  const scoped = Object.values(records || {}).filter(record =>
    record && typeof record === 'object' && (!shopName || record.shopName === shopName)
  );
  if (!scoped.length) {
    throw new Error(`sku-records 中没有店铺「${shopName}」的活动 SKU`);
  }

  const missing = scoped.filter(record => !record.brand).map(record => record.platformCode).filter(Boolean);
  if (missing.length) {
    throw new Error(
      `sku-records 缺少品牌字段（${missing.slice(0, 5).join(', ')}${missing.length > 5 ? '…' : ''}），`
      + '请重新运行首次 check --shop <店铺> --brand <品牌>'
    );
  }

  const brands = [...new Set(scoped.map(record => requireKnownBrand(record.brand, 'sku-records ')))];
  if (brands.length !== 1) {
    throw new Error(`sku-records 品牌不唯一：${brands.join(', ')}`);
  }
  return brands[0];
}

function assertSameBrand(expected, actual, source) {
  const expectedBrand = requireKnownBrand(expected, '预期品牌');
  const actualBrand = requireKnownBrand(actual, source || '数据');
  if (expectedBrand !== actualBrand) {
    throw new Error(`品牌不一致：本轮=${expectedBrand}，${source || '数据'}=${actualBrand}`);
  }
  return expectedBrand;
}

module.exports = {
  listKnownBrands,
  requireKnownBrand,
  requireRecordBrand,
  assertSameBrand,
};
