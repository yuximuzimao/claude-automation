'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const appJs = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');

test('frontend posts only the selected account to the fixed-batch endpoint', () => {
  assert.match(appJs, /async function runA1FixedBatch\(num, btn\)/);
  assert.match(appJs, /api\(`\/accounts\/\$\{num\}\/a1-fixed-batch`/);
  // runA1FixedBatch 函数体内不应包含 disableAutoExecute 或 accounts（多账号参数）
  const fnMatch = appJs.match(/async function runA1FixedBatch[\s\S]{0,2000}?\n\}/);
  assert.ok(fnMatch, 'runA1FixedBatch function not found');
  const fnBody = fnMatch[0];
  assert.doesNotMatch(fnBody, /disableAutoExecute/);
  assert.doesNotMatch(fnBody, /accounts:/);
});
