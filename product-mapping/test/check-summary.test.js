'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { summarizeSkuComparisons } = require('../lib/check');

function recognition(name) {
  return { type: '单品', items: [{ name, qty: 1 }] };
}

test('pre-match summary separates verified mappings from expected unmatched SKUs', () => {
  const summary = summarizeSkuComparisons([
    { platformCode: 'matched', erpCode: 'ERP-1', recognition: recognition('A'), comparisonResult: 'match' },
    { platformCode: 'todo', erpCode: '', recognition: recognition('B'), comparisonResult: undefined },
  ]);

  assert.equal(summary.matchedSkuCount, 1);
  assert.equal(summary.matchedComparisonMatch, 1);
  assert.equal(summary.matchedComparisonMismatch, 0);
  assert.equal(summary.unmatchedAwaitingMatch, 1);
  assert.equal(summary.comparisonPending, 1);
});

test('final summary has no awaiting or pending SKU when all mappings match', () => {
  const summary = summarizeSkuComparisons([
    { platformCode: 'a', erpCode: 'ERP-1', recognition: recognition('A'), comparisonResult: 'match' },
    { platformCode: 'b', erpCode: 'ERP-2', recognition: recognition('B'), comparisonResult: 'match' },
  ]);

  assert.equal(summary.matchedSkuCount, 2);
  assert.equal(summary.matchedComparisonMatch, 2);
  assert.equal(summary.matchedComparisonMismatch, 0);
  assert.equal(summary.unmatchedAwaitingMatch, 0);
  assert.equal(summary.comparisonPending, 0);
  assert.equal(summary.pendingVisualReview, 0);
});
