'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('换货或商责推荐使用专属动作标签，但不提供系统执行入口', () => {
  const appSource = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const routesSource = fs.readFileSync(path.join(__dirname, '../../lib/server/routes.js'), 'utf8');
  const queueSource = fs.readFileSync(path.join(__dirname, '../../lib/server/op-queue.js'), 'utf8');

  assert.match(appSource, /decision\.recommendedActionLabel/);
  assert.match(appSource, /仅允许在工单页面逐单人工处理/);
  assert.match(appSource, /!sim\.decision\.manualOnly/);
  assert.match(routesSource, /if \(sim\.decision\.manualOnly\)/);
  assert.match(queueSource, /if \(sim\.decision\?\.manualOnly\)/);
  assert.match(routesSource, /禁止系统执行/);
  assert.match(queueSource, /禁止系统执行/);
});
