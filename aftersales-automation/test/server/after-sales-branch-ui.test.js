'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function loadStatsHelpers() {
  const source = fs.readFileSync(path.join(__dirname, '../../public/app.js'), 'utf8');
  const escapeStart = source.indexOf('function h(');
  const escapeEnd = source.indexOf('function timeAgo');
  const start = source.indexOf('function hasSpecificFeedbackComment');
  const end = source.indexOf('function generateInsights');
  assert.ok(escapeStart >= 0 && escapeEnd > escapeStart, '生产文本转义函数应存在');
  assert.ok(start >= 0 && end > start, '统计页辅助函数应存在');
  const context = {};
  vm.createContext(context);
  vm.runInContext(`${source.slice(escapeStart, escapeEnd)};
    ${source.slice(start, end)};
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
  assert.match(source, /可评估自动化/);
  assert.match(source, /仅人工/);
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

test('分支页只展示采集和归类正常的数据，并按自动化价值分层', () => {
  const { renderAfterSalesBranches } = loadStatsHelpers();
  const html = renderAfterSalesBranches({
    uniqueWorkOrders: 20,
    cases: [
      {
        afterSaleReason: '七天无理由退货（不喜欢/不合适）',
        orderType: '退货退款',
        branchLabel: '退货退款 / 已入库 / 精确退回 / 同意退款',
        registered: true, automationStatus: 'enabled', expectedAction: 'approve',
        occurrenceCount: 4, autoSuccessCount: 4, positiveCount: 4,
        negativeCount: 0, manualHandledCount: 0, missingFacts: [], notes: [],
      },
      {
        afterSaleReason: '拒收', orderType: '仅退款',
        branchLabel: '仅退款 / 所有包裹已退回 / 同意退款',
        registered: true, automationStatus: 'candidate', expectedAction: 'approve',
        occurrenceCount: 3, autoSuccessCount: 2, positiveCount: 3,
        negativeCount: 0, manualHandledCount: 1, missingFacts: [], notes: [],
      },
      {
        afterSaleReason: '次品', orderType: '退货退款',
        branchLabel: '退货退款 / 无退货单号 / 转人工',
        registered: true, automationStatus: 'manual_only', expectedAction: 'escalate',
        occurrenceCount: 2, autoSuccessCount: 0, positiveCount: 0,
        negativeCount: 0, manualHandledCount: 2, missingFacts: [], notes: [],
      },
      {
        afterSaleReason: '错误搜索结果', orderType: '仅退款',
        branchLabel: '未登记分支', registered: false,
        automationStatus: 'manual_only', expectedAction: 'escalate',
        occurrenceCount: 6, missingFacts: [], notes: [],
      },
      {
        afterSaleReason: 'ERP 少读一行', orderType: '仅退款',
        branchLabel: '资料缺失', registered: true,
        automationStatus: 'manual_only', expectedAction: 'escalate',
        occurrenceCount: 5, missingFacts: ['ERP 行缺失'], notes: [],
      },
    ],
  });

  assert.match(html, /已授权自动/);
  assert.match(html, /可评估自动化/);
  assert.match(html, /仅人工/);
  const enabledTier = html.indexOf('<section class="branch-tier branch-tier-enabled">');
  const candidateTier = html.indexOf('<section class="branch-tier branch-tier-candidate">');
  const manualTier = html.indexOf('<details class="branch-tier branch-tier-manual">');
  assert.ok(enabledTier >= 0 && enabledTier < candidateTier);
  assert.ok(candidateTier < manualTier);
  assert.doesNotMatch(html, /错误搜索结果|ERP 少读一行|资料是否缺失/);
  assert.match(html, /最近30天有效工单 9 单 · 正常固定分支 3 个/);
  assert.match(html, /branch-tier branch-tier-manual/);
  assert.doesNotMatch(html, /branch-tier branch-tier-manual" open/);
});

test('候选分支按自动化证据排序，并直接展示完整条件和历史结果', () => {
  const { renderAfterSalesBranches } = loadStatsHelpers();
  const html = renderAfterSalesBranches({ cases: [
    {
      afterSaleReason: '多拍/拍错/不想要', orderType: '仅退款',
      branchLabel: '仅退款 / 主品与赠品均未发货 / 同意退款',
      registered: true, automationStatus: 'candidate', expectedAction: 'approve',
      occurrenceCount: 16, autoSuccessCount: 15, positiveCount: 15,
      negativeCount: 0, manualHandledCount: 1, missingFacts: [],
      notes: [{ value: '真正空值', count: 12 }, { value: '不要了', count: 4 }],
    },
    {
      afterSaleReason: '拒收', orderType: '仅退款',
      branchLabel: '仅退款 / 所有包裹已退回 / 同意退款',
      registered: true, automationStatus: 'candidate', expectedAction: 'approve',
      occurrenceCount: 12, autoSuccessCount: 7, positiveCount: 11,
      negativeCount: 1, manualHandledCount: 5, missingFacts: [], notes: [],
    },
  ] });

  assert.ok(html.indexOf('多拍/拍错/不想要') < html.indexOf('拒收'));
  assert.match(html, /售后类型[\s\S]*仅退款/);
  assert.match(html, /必须满足[\s\S]*主品与赠品均未发货/);
  assert.match(html, /处理结果[\s\S]*同意退款/);
  assert.match(html, /出现次数[\s\S]*16/);
  assert.match(html, /真实自动成功[\s\S]*15/);
  assert.match(html, /好评[\s\S]*15/);
  assert.match(html, /差评[\s\S]*0/);
  assert.match(html, /人工处理[\s\S]*1/);
  assert.match(html, /真正空值（12）[\s\S]*不要了（4）/);
  assert.match(html, /<div class="branch-card-header">/);
  assert.doesNotMatch(html, /<header class="branch-card-header">/);
  assert.doesNotMatch(html, /查看详情|需要关注|is-attention|has-negative/);
});

test('候选排序依次比较自动成功、好评、差评和出现次数', () => {
  const { renderAfterSalesBranches } = loadStatsHelpers();
  const candidate = (reason, auto, positive, negative, occurrence) => ({
    afterSaleReason: reason,
    orderType: '仅退款',
    branchLabel: `仅退款 / ${reason}条件 / 同意退款`,
    registered: true,
    automationStatus: 'candidate',
    expectedAction: 'approve',
    occurrenceCount: occurrence,
    autoSuccessCount: auto,
    positiveCount: positive,
    negativeCount: negative,
    manualHandledCount: 0,
    missingFacts: [],
    notes: [],
  });
  const html = renderAfterSalesBranches({ cases: [
    candidate('基准', 2, 4, 1, 3),
    candidate('出现更多优先', 2, 4, 1, 9),
    candidate('差评更少优先', 2, 4, 0, 1),
    candidate('好评优先', 2, 5, 9, 1),
    candidate('自动成功优先', 3, 0, 9, 1),
  ] });
  const positions = [
    '自动成功优先',
    '好评优先',
    '差评更少优先',
    '出现更多优先',
    '基准',
  ].map(reason => html.indexOf(`<div class="branch-card-reason">${reason}</div>`));

  assert.deepEqual([...positions].sort((a, b) => a - b), positions);
});

test('分支卡片所有动态文本都使用生产转义函数', () => {
  const { renderAfterSalesBranches } = loadStatsHelpers();
  const html = renderAfterSalesBranches({ cases: [{
    afterSaleReason: '<img src=x onerror=alert(1)>',
    orderType: '<svg onload=alert(2)>',
    branchLabel: '<button onclick=alert(3)>条件 / 同意退款',
    registered: true,
    automationStatus: 'candidate',
    expectedAction: 'approve',
    occurrenceCount: 1,
    missingFacts: [],
    notes: [{ value: '<iframe src=javascript:alert(4)>', count: 1 }],
  }] });

  assert.doesNotMatch(html, /<img|<svg|<button|<iframe/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;button onclick=alert\(3\)&gt;条件/);
  assert.match(html, /&lt;iframe src=javascript:alert\(4\)&gt;/);
});

test('分支卡片用绿蓝灰表达自动化层级，并在窄屏改为两列指标', () => {
  const css = fs.readFileSync(path.join(__dirname, '../../public/style.css'), 'utf8');
  assert.match(css, /\.branch-tier-enabled\s*\{[^}]*--tier-color:\s*var\(--green\)/);
  assert.match(css, /\.branch-tier-candidate\s*\{[^}]*--tier-color:\s*var\(--blue\)/);
  assert.match(css, /\.branch-tier-manual\s*\{[^}]*--tier-color:\s*var\(--gray-400\)/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.branch-overview\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.branch-metrics\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.doesNotMatch(css, /branch-(?:card|tier)[^\n{]*attention|branch-result-counts \.has-negative/);
});
