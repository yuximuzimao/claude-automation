'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const BASE = path.join(__dirname, '../..');
const indexHtml = fs.readFileSync(path.join(BASE, 'public/index.html'), 'utf8');
const appJs = fs.readFileSync(path.join(BASE, 'public/app.js'), 'utf8');

function section(id) {
  const start = indexHtml.indexOf(`<section id="${id}"`);
  assert.notEqual(start, -1, `${id} section exists`);
  const next = indexHtml.indexOf('</section>', start);
  assert.notEqual(next, -1, `${id} section closes`);
  return indexHtml.slice(start, next);
}

test('pending toolbar has store filter and batch actions send explicit pending scope', () => {
  const pending = section('tab-pending');
  assert.match(pending, /id="pending-store-filter"/);
  assert.match(pending, /setLiveStoreFilter\('pending', this\.value\)/);
  assert.match(pending, /batchExecute\(\)/);
  assert.match(pending, /batchReprocess\('pending'\)/);

  assert.match(appJs, /function getLiveBatchScope\(tabKey\)/);
  assert.match(appJs, /statusScope: tabKey === 'waiting' \? 'waiting' : 'pending'/);
  assert.match(appJs, /batch-execute', \{ method: 'POST', body: JSON\.stringify\(scope\) \}/);
  assert.match(appJs, /queue\/batch-reprocess', \{ method: 'POST', body: JSON\.stringify\(scope\) \}/);
});

test('waiting toolbar has store filter and scoped batch reprocess but no batch execute', () => {
  const waiting = section('tab-waiting-tab');
  assert.match(waiting, /id="waiting-store-filter"/);
  assert.match(waiting, /setLiveStoreFilter\('waiting', this\.value\)/);
  assert.match(waiting, /batchReprocess\('waiting'\)/);
  assert.doesNotMatch(waiting, /batchExecute\(/);
});

test('live tab rendering filters by accountNum without changing sorted item order', () => {
  assert.match(appJs, /const visiblePendingItems = applyLiveStoreFilter\('pending', pendingItems\)/);
  assert.match(appJs, /const visibleWaitingItems = applyLiveStoreFilter\('waiting', waitingItems\)/);
  assert.match(appJs, /setScopedCount\('pending-count', visiblePendingItems\.length, pendingItems\.length\)/);
  assert.match(appJs, /setScopedCount\('waiting-count', visibleWaitingItems\.length, waitingItems\.length\)/);
  assert.match(appJs, /return \(items \|\| \[\]\)\.filter\(item => liveStoreKey\(item\) === selected\)/);
});
