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
  vm.runInContext(`${source.slice(start, end)};
    this.hasSpecificFeedbackComment = hasSpecificFeedbackComment;
    this.renderAfterSalesBranches = renderAfterSalesBranches;`, context);
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

test('售后分支先显示概览，并优先展开需关注和已授权原因', () => {
  const { renderAfterSalesBranches } = loadStatsHelpers();
  const html = renderAfterSalesBranches({
    uniqueWorkOrders: 12,
    unregisteredCount: 1,
    cases: [
      {
        afterSaleReason: '普通原因', branchLabel: '普通结果', registered: true,
        automationStatus: 'manual_only', occurrenceCount: 7, positiveCount: 2,
        negativeCount: 0, autoSuccessCount: 0, manualHandledCount: 7,
        expectedAction: 'escalate', missingFacts: [], notes: [],
      },
      {
        afterSaleReason: '需关注原因', branchLabel: '资料不全', registered: false,
        automationStatus: 'manual_only', occurrenceCount: 1, positiveCount: 0,
        negativeCount: 1, autoSuccessCount: 0, manualHandledCount: 1,
        expectedAction: 'escalate', missingFacts: ['ERP 行缺失'], notes: [],
      },
      {
        afterSaleReason: '七天无理由退货（不喜欢/不合适）', branchLabel: '精确退回', registered: true,
        automationStatus: 'enabled', occurrenceCount: 4, positiveCount: 4,
        negativeCount: 0, autoSuccessCount: 4, manualHandledCount: 0,
        expectedAction: 'approve', missingFacts: [], notes: [{ value: '无', count: 4 }],
      },
    ],
  });

  assert.match(html, /branch-overview/);
  assert.match(html, /branch-overview-value">12<[\s\S]*branch-overview-label">最近30天工单/);
  assert.match(html, /branch-overview-value">1<[\s\S]*branch-overview-label">已授权分支/);
  assert.match(html, /branch-overview-value">1<[\s\S]*branch-overview-label">需要关注/);
  assert.ok(html.indexOf('需关注原因') < html.indexOf('七天无理由退货'));
  assert.ok(html.indexOf('七天无理由退货') < html.indexOf('普通原因'));
  assert.equal((html.match(/class="branch-reason-group" open/g) || []).length, 2);
  assert.match(html, /查看详情/);
  assert.match(html, /真实自动成功 4/);
  assert.match(html, /class="branch-row-detail-content"/);
});
