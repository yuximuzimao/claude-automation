'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadStatsHelpers() {
  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const start = source.indexOf('function hasSpecificFeedbackComment');
  const end = source.indexOf('function generateInsights');
  assert.ok(start >= 0 && end > start, '统计页辅助函数应存在');
  const context = { h: value => String(value ?? '') };
  vm.createContext(context);
  vm.runInContext(`${source.slice(start, end)}; this.hasSpecificFeedbackComment = hasSpecificFeedbackComment;`, context);
  return context;
}

test('统计页展示新的最近30天分支清单，不再展示旧10次自动学习进度', () => {
  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');

  assert.match(source, /renderAfterSalesBranches/);
  assert.match(source, /最近30天/);
  assert.match(source, /不会自动学习/);
  assert.match(source, /已授权自动/);
  assert.match(source, /候选，仍人工/);
  assert.match(source, /永不自动/);
  assert.match(source, /autoSuccessCount/);
  assert.match(source, /item\.notes/);
  assert.doesNotMatch(source, /renderAutoExecConfidence/);
  assert.doesNotMatch(source, /执行 ≥10 次/);
  assert.doesNotMatch(source, /confidence-update/);
});

test('AI 洞察明细只保留填写了具体评论的反馈', () => {
  const { hasSpecificFeedbackComment } = loadStatsHelpers();
  assert.equal(hasSpecificFeedbackComment({ verdict: 'positive', reason: '' }), false);
  assert.equal(hasSpecificFeedbackComment({ verdict: 'positive', reason: '   ' }), false);
  assert.equal(hasSpecificFeedbackComment({ verdict: 'positive', reason: '数量核对清楚' }), true);
  assert.equal(hasSpecificFeedbackComment({ verdict: 'negative', reason: 'ERP 少读一行' }), true);

  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  assert.match(source, /pendingInsight[^;]*\.filter\(hasSpecificFeedbackComment\)/s);
  assert.match(source, /feedbacks[^;]*\.filter\(hasSpecificFeedbackComment\)/s);
});
