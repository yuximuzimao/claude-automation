'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const appJs = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');

test('frontend posts only the selected account to the fixed-batch endpoint', () => {
  assert.match(appJs, /async function runA1FixedBatch\(num, btn\)/);
  assert.match(appJs, /api\(`\/accounts\/\$\{num\}\/a1-fixed-batch`/);
  assert.doesNotMatch(appJs, /a1-fixed-batch[\s\S]{0,240}thresholdHours/);
  assert.doesNotMatch(appJs, /a1-fixed-batch[\s\S]{0,240}disableAutoExecute/);
  assert.doesNotMatch(appJs, /a1-fixed-batch[\s\S]{0,240}accounts/);
});
