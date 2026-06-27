'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { compareSkuArchive } = require('../lib/compare');

test('missing recognition is mismatch when ERP archive has details', () => {
  const result = compareSkuArchive({
    platformCode: 'p1',
    recognition: null,
    archiveType: '0',
    archiveTitle: 'ERP 商品',
    subItems: [],
    brand: 'hee',
  });

  assert.equal(result.comparisonResult, 'mismatch');
  assert.match(result.comparisonDetail, /识图为空/);
});

test('single archive requires recognition quantity to be exactly one', () => {
  const result = compareSkuArchive({
    platformCode: 'p2',
    recognition: {
      type: '组合装',
      items: [{ name: 'ERP 商品', qty: 2 }],
      raw: 'ERP 商品×2',
    },
    archiveType: '0',
    archiveTitle: 'ERP 商品',
    subItems: [],
    brand: 'hee',
  });

  assert.equal(result.comparisonResult, 'mismatch');
  assert.match(result.comparisonDetail, /识图数量×2/);
});

test('suite archive compares resolved recognition items exactly', () => {
  const result = compareSkuArchive({
    platformCode: 'p3',
    recognition: {
      type: '组合装',
      items: [
        { name: 'A', qty: 1 },
        { name: 'B', qty: 2 },
      ],
      raw: 'A×1 B×2',
    },
    archiveType: '2',
    archiveTitle: '套件',
    subItems: [
      { name: 'B', qty: 2 },
      { name: 'A', qty: 1 },
    ],
    brand: 'hee',
  });

  assert.equal(result.comparisonResult, 'match');
});
