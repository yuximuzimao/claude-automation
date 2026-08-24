'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  recordKey,
  imageFileName,
  findRecord,
} = require('../lib/sku-identity');
const { attachImageUrlsByLink } = require('../lib/correspondence');

test('different product links sharing one platform code keep separate identities', () => {
  assert.equal(recordKey('yxjy-ms', '260605-15'), 'yxjy-ms::260605-15');
  assert.equal(recordKey('yxjy-yr', '260605-15'), 'yxjy-yr::260605-15');
  assert.notEqual(
    recordKey('yxjy-ms', '260605-15'),
    recordKey('yxjy-yr', '260605-15')
  );
});

test('image filename contains both product and platform codes', () => {
  assert.equal(imageFileName('yxjy-ms', '260605-15'), 'yxjy-ms__260605-15.jpg');
  assert.equal(imageFileName('0409fs', '260605- 8'), '0409fs__260605- 8.jpg');
});

test('record lookup supports composite and legacy records', () => {
  const composite = {
    'a::same': { productCode: 'a', platformCode: 'same' },
    'b::same': { productCode: 'b', platformCode: 'same' },
  };
  assert.equal(findRecord(composite, 'a', 'same').productCode, 'a');
  assert.equal(findRecord(composite, 'b', 'same').productCode, 'b');

  const legacy = {
    same: { productCode: 'a', platformCode: 'same' },
  };
  assert.equal(findRecord(legacy, 'a', 'same').productCode, 'a');
  assert.equal(findRecord(legacy, 'b', 'same'), null);
});

test('image URLs stay isolated when different links reuse one platform code', () => {
  const products = [
    { productCode: 'link-a', skus: [{ platformCode: 'same', imgUrl: '' }] },
    { productCode: 'link-b', skus: [{ platformCode: 'same', imgUrl: '' }] },
  ];
  attachImageUrlsByLink(products, {
    'link-a::same': 'https://img.example/a.jpg',
    'link-b::same': 'https://img.example/b.jpg',
  });

  assert.equal(products[0].skus[0].imgUrl, 'https://img.example/a.jpg');
  assert.equal(products[1].skus[0].imgUrl, 'https://img.example/b.jpg');
});
