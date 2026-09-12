'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const indexSource = fs.readFileSync(path.join(__dirname, '../../public/index.html'), 'utf8');
const styleSource = fs.readFileSync(path.join(__dirname, '../../public/style.css'), 'utf8');
const appSource = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
const serverSource = fs.readFileSync(path.join(__dirname, '../../server.js'), 'utf8');

test('顶部店铺管理后存在万物红绿状态框', () => {
  const accountsIndex = indexSource.indexOf('data-tab="accounts"');
  const wanwuIndex = indexSource.indexOf('id="wanwu-status"');
  const headerRightIndex = indexSource.indexOf('class="header-right"');
  assert.ok(accountsIndex >= 0 && wanwuIndex > accountsIndex && wanwuIndex < headerRightIndex);
  assert.match(styleSource, /\.wanwu-status\.ok/);
  assert.match(styleSource, /\.wanwu-status\.attention/);
  assert.match(styleSource, /\.wanwu-status\.error/);
});

test('前端通过接口和SSE刷新万物状态', () => {
  assert.match(appSource, /api\('\/wanwu-status'\)/);
  assert.match(appSource, /addEventListener\('wanwu-status'/);
  assert.match(appSource, /function renderWanwuStatus/);
});

test('服务调度万物扫描并纳入统一停止恢复', () => {
  assert.match(serverSource, /enqueue\('wanwu-scan', '万物定时扫描'/);
  assert.match(serverSource, /scheduleNextWanwuScan\(\)/);
  assert.match(serverSource, /clearTimeout\(wanwuScanTimer\)/);
});
