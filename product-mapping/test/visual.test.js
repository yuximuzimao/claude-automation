'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  parseNotesToRecognition,
  recognitionType,
  selectVerdictRecords,
} = require('../lib/visual');

test('recognition notes preserve spaces inside ERP names and split on semicolons', () => {
  const result = parseNotesToRecognition(
    'HEE悦希悦美水漾光盾防晒精华 30g×3；HEE悦希保湿舒缓面膜 25ml*5片×1'
  );

  assert.deepEqual(result.items, [
    { name: 'HEE悦希悦美水漾光盾防晒精华 30g', qty: 3 },
    { name: 'HEE悦希保湿舒缓面膜 25ml*5片', qty: 1 },
  ]);
  assert.equal(result.type, '组合装');
});

test('duplicate platform codes require productCode before writing a verdict', () => {
  const records = {
    'a::same': { productCode: 'a', platformCode: 'same' },
    'b::same': { productCode: 'b', platformCode: 'same' },
  };

  assert.throws(
    () => selectVerdictRecords(records, 'same'),
    /对应多个商品链接/
  );
  assert.deepEqual(
    selectVerdictRecords(records, 'same', 'b'),
    [records['b::same']]
  );
});

test('one product with quantity greater than one is a suite', () => {
  assert.equal(recognitionType([{ name: '果冻', qty: 1 }]), '单品');
  assert.equal(recognitionType([{ name: '果冻', qty: 3 }]), '组合装');
});
