'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '../..');

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8');
}

test('SKU计价确认区默认隐藏，只在待确认页顶部提供勾选、全选、主品/赠品编辑和批量确认', () => {
  const html = read('public/index.html');
  const app = read('public/app.js');

  assert.match(html, /id="sku-pricing-panel" class="sku-pricing-panel hidden"/);
  assert.ok(html.indexOf('id="sku-pricing-panel"') < html.indexOf('id="pending-list"'));
  assert.match(app, /sku-pricing-select-all/);
  assert.match(app, /toggleAllSkuPricing/);
  assert.match(app, /sku-pricing-check/);
  assert.match(app, /sku-pricing-paid/);
  assert.match(app, /sku-pricing-gift/);
  assert.match(app, /确认已勾选/);
  assert.match(app, /\/sku-pricing\/confirm/);
  assert.match(app, /filter\(row => row\.querySelector\('\.sku-pricing-check'\).*\.checked/);
});

test('没有SKU待确认项时确认区会清空并隐藏', () => {
  const app = read('public/app.js');
  assert.match(app, /if \(!rows\.length\) \{[\s\S]*panel\.classList\.add\('hidden'\);[\s\S]*panel\.innerHTML = '';/);
});
