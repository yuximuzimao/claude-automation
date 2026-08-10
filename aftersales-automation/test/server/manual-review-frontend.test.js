'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('换货或商责显示人工核对提醒并保留系统执行入口', () => {
  const appSource = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const routesSource = fs.readFileSync(path.join(__dirname, '../../lib/server/routes.js'), 'utf8');
  const queueSource = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');

  assert.match(appSource, /decision\.recommendedActionLabel/);
  assert.match(appSource, /需人工核对后执行/);
  assert.match(appSource, /▶ 执行操作/);
  assert.doesNotMatch(appSource, /!sim\.decision\.manualOnly/);
  assert.match(routesSource, /humanTriggeredExecutionAllowed === false/);
  assert.match(queueSource, /humanTriggeredExecutionAllowed === false/);
  assert.match(routesSource, /尚无可安全执行/);
  assert.match(queueSource, /尚无可安全执行/);
  assert.match(appSource, /manualArchiveOnly/);
  assert.match(appSource, /请人工确认后归档/);
  assert.match(appSource, /当前无需平台操作，请人工确认后手动归档/);
  assert.match(routesSource, /当前无需平台操作，请人工确认后手动归档/);
  assert.match(queueSource, /当前无需平台操作，请人工确认后手动归档/);
});
