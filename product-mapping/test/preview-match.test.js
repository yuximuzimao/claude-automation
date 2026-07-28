'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { getPreviewDetails } = require('../lib/preview-match');

test('preview combines AI recognition and injected accessories in the final detail table', () => {
  const details = getPreviewDetails({
    platformCode: '260805-4',
    recognition: {
      items: [{ name: '基础商品', qty: 1 }],
    },
  }, 'hee');

  assert.match(details.finalRows, /基础商品/);
  assert.match(details.finalRows, /HEE悦希印花礼盒（天地盖）白色/);
  assert.match(details.finalRows, /HEE悦希印花礼袋-白/);
  assert.match(details.finalRows, /HEE悦希雪梨纸/);
  assert.match(details.finalRows, /class="recognition-row"/);
  assert.match(details.finalRows, /class="accessory-row"/);
  assert.equal(details.recognitionItems.length, 1);
  assert.equal(details.accessoryItems.length, 3);
});

test('preview final detail contains only AI recognition when the SKU has no accessory rule', () => {
  const details = getPreviewDetails({
    platformCode: 'no-accessory-rule',
    recognition: {
      items: [{ name: 'KGOS商品', qty: 2 }],
    },
  }, 'kgos');

  assert.match(details.finalRows, /KGOS商品/);
  assert.doesNotMatch(details.finalRows, /accessory-row/);
  assert.equal(details.accessoryItems.length, 0);
});
