'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

test('定时扫描在账号循环前无条件刷新一次 ERP', () => {
  const source = fs.readFileSync(
    require.resolve('../../lib/server/op-queue'),
    'utf8'
  );
  const execScanSource = source.slice(source.indexOf('async function execScan(op)'));
  const readinessIndex = execScanSource.indexOf(
    "await prepareErpOrderPage(erpTargetId, { forceReload: true })"
  );
  const accountLoopIndex = execScanSource.indexOf('for (let i = 0; i < total; i++)');

  assert.notEqual(readinessIndex, -1, '缺少扫描前 ERP readiness');
  assert.notEqual(accountLoopIndex, -1, '缺少账号扫描循环');
  assert.ok(readinessIndex < accountLoopIndex, 'ERP readiness 必须发生在账号循环之前');
});
