const assert = require('assert');
const fs = require('fs');
const path = require('path');
const test = require('node:test');

const indexHtml = fs.readFileSync(path.join(__dirname, '../../public/index.html'), 'utf8');

function sectionHtml(id) {
  const start = indexHtml.indexOf(`<section id="${id}"`);
  assert.notEqual(start, -1, `missing section ${id}`);
  const next = indexHtml.indexOf('<section ', start + 1);
  return indexHtml.slice(start, next === -1 ? indexHtml.length : next);
}

test('pending tab keeps the old top-right operation buttons visible', () => {
  const html = sectionHtml('tab-pending');

  assert.match(html, /<button id="scan-btn" class="btn-primary" onclick="scanTickets\(\)">扫描工单<\/button>/);
  assert.match(html, /<button class="btn-ghost" onclick="batchExecute\(\)">批量执行<\/button>/);
  assert.match(html, /<button class="btn-ghost" onclick="batchReprocess\(\)">批量重来<\/button>/);

  const firstButton = html.indexOf('<button id="scan-btn"');
  const stoppedComment = html.indexOf('[stopped-2026-06-16]');
  assert.equal(stoppedComment, -1, 'pending toolbar buttons must not remain hidden behind stopped-system comments');
  assert.ok(firstButton > -1, 'scan button should be in pending toolbar');
});

test('waiting tab keeps the historical guidance text instead of inventing a new batch button', () => {
  const html = sectionHtml('tab-waiting-tab');

  assert.match(html, /下次扫描时自动重新采集推理/);
  assert.doesNotMatch(html, /batchExecute\(\)|batchReprocess\(\)|scanTickets\(\)/);
});
