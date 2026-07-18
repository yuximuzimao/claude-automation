# 售后分支统计页清晰化 Implementation Plan

> 归档状态（2026-07-19）：已完成并被后续“自动化优先”展示计划收口。本文件只用于追溯第一轮页面改造。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把售后分支统计页改成“概览 → 售后原因 → 最小结果 → 详情”的清晰层级，并隐藏没有具体评论内容的反馈明细。

**Architecture:** 保留现有 `/auto-exec-confidence`、`/feedback` 和 SSE 数据流，只修改 `public/app.js` 的前端整理与模板，以及 `public/style.css` 的专用样式。测试通过 Node `vm` 执行统计页的纯渲染函数，验证实际输出与排序，不新增后端接口、缓存或定时任务。

**Tech Stack:** 原生 JavaScript、HTML 字符串模板、CSS、Node.js `node:test`、`node:vm`。

---

## 文件范围

- 修改 `test/server/after-sales-branch-ui.test.js`：验证评论过滤、概览、排序、默认展开和详情层级。
- 修改 `public/app.js`：过滤反馈明细，重写售后分支渲染结构。
- 修改 `public/style.css`：增加统计页专用样式和窄屏换行。
- 不修改后端分类器、自动门禁、历史统计接口和业务数据。

### Task 1: AI 洞察只展示有具体评论的反馈

**Files:**
- Modify: `test/server/after-sales-branch-ui.test.js`
- Modify: `public/app.js:1380-1460`

- [x] **Step 1: 写失败测试**

在 `test/server/after-sales-branch-ui.test.js` 中加入：

```js
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
```

- [x] **Step 2: 运行测试并确认失败原因正确**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: FAIL，提示找不到 `hasSpecificFeedbackComment`。

- [x] **Step 3: 写最小实现**

在 `loadStats()` 前加入：

```js
function hasSpecificFeedbackComment(feedback) {
  return Boolean(String(feedback && feedback.reason || '').trim());
}
```

把待洞察反馈与反馈记录统一先过滤：

```js
const visiblePendingInsight = (pendingInsight || []).filter(hasSpecificFeedbackComment);
const pendingCount = visiblePendingInsight.length;
// 模板使用 visiblePendingInsight

const recentFb = (feedbacks || [])
  .filter(hasSpecificFeedbackComment)
  .reverse();
```

总体正确率、好评数、差评数和历史反馈数据保持不变。

- [x] **Step 4: 运行目标测试**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: PASS。

- [x] **Step 5: 提交独立修改**

```bash
git add aftersales-automation/public/app.js aftersales-automation/test/server/after-sales-branch-ui.test.js
git commit -m "fix(aftersales): hide empty feedback details"
```

### Task 2: 建立概览、原因分组和按需详情层级

**Files:**
- Modify: `test/server/after-sales-branch-ui.test.js`
- Modify: `public/app.js:1460-1535`
- Modify: `public/style.css`

- [x] **Step 1: 写失败测试**

扩展 `loadStatsHelpers()`，同时暴露 `renderAfterSalesBranches`，并加入真实渲染断言：

```js
vm.runInContext(
  `${source.slice(start, end)}; this.renderAfterSalesBranches = renderAfterSalesBranches;`,
  context,
);

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
  assert.match(html, /最近30天工单[\s\S]*12/);
  assert.match(html, /已授权分支[\s\S]*1/);
  assert.match(html, /需要关注[\s\S]*1/);
  assert.ok(html.indexOf('需关注原因') < html.indexOf('七天无理由退货'));
  assert.ok(html.indexOf('七天无理由退货') < html.indexOf('普通原因'));
  assert.match(html, /<details[^>]*open[^>]*>[\s\S]*需关注原因/);
  assert.match(html, /查看详情/);
  assert.match(html, /真实自动成功 4/);
});
```

同时保留原测试对“最近 30 天”“不会自动学习”和三种权限状态的断言。

- [x] **Step 2: 运行测试并确认失败原因正确**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: FAIL，缺少 `branch-overview` 或排序、详情结构不符合预期。

- [x] **Step 3: 写最小渲染实现**

在 `renderAfterSalesBranches(report)` 中：

```js
const needsAttention = item =>
  item.registered === false
  || Number(item.negativeCount || 0) > 0
  || (item.missingFacts || []).length > 0;

const enabledCount = (report.cases || [])
  .filter(item => item.automationStatus === 'enabled').length;
const attentionCount = (report.cases || []).filter(needsAttention).length;
```

原因组增加 `hasAttention`、`hasEnabled`，按以下元组排序：

```js
const priority = group => group.hasAttention ? 0 : group.hasEnabled ? 1 : 2;
return priority(a) - priority(b)
  || b.total - a.total
  || a.reason.localeCompare(b.reason, 'zh-CN');
```

结果行使用同样优先级；主行只显示名称、权限、出现次数、好评和差评。`autoSuccessCount`、`manualHandledCount`、`expectedAction`、`missingFacts` 与 `notes` 放入嵌套 `<details class="branch-row-details">`。

原因 `<details>` 的 `open` 属性只由 `hasAttention || hasEnabled` 决定，不再默认展开前三组。

概览使用四个 `.branch-overview-card`，原因、结果和详情分别使用 `.branch-reason-group`、`.branch-result-row`、`.branch-row-details`。

- [x] **Step 4: 增加专用 CSS**

在 `public/style.css` 末尾新增：

```css
.branch-overview { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 8px; margin: 12px 0 16px; }
.branch-overview-card { padding: 10px 12px; border: 1px solid var(--gray-200); border-radius: 8px; background: var(--gray-50); }
.branch-overview-value { font-size: 20px; line-height: 1; font-weight: 700; }
.branch-overview-label { margin-top: 5px; font-size: 11px; color: var(--gray-600); }
.branch-reason-group { border: 1px solid var(--gray-200); border-radius: 8px; margin-bottom: 8px; background: #fff; }
.branch-reason-summary { display: flex; align-items: center; gap: 8px; padding: 11px 12px; cursor: pointer; }
.branch-reason-name { flex: 1; min-width: 0; font-weight: 600; }
.branch-reason-meta { color: var(--gray-600); font-size: 12px; }
.branch-result-list { border-top: 1px solid var(--gray-100); padding: 0 12px; }
.branch-result-row { padding: 10px 0; border-bottom: 1px solid var(--gray-100); }
.branch-result-row:last-child { border-bottom: 0; }
.branch-result-main { display: grid; grid-template-columns: minmax(220px, 1fr) auto auto; align-items: center; gap: 12px; }
.branch-result-counts { display: flex; gap: 10px; color: var(--gray-600); font-size: 12px; white-space: nowrap; }
.branch-row-details { margin-top: 7px; color: var(--gray-600); font-size: 12px; }
.branch-row-detail-content { margin-top: 6px; padding: 8px 10px; border-radius: 6px; background: var(--gray-50); line-height: 1.6; }
@media (max-width: 760px) {
  .branch-overview { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
  .branch-result-main { grid-template-columns: 1fr; gap: 6px; }
  .branch-result-counts { flex-wrap: wrap; }
}
```

- [x] **Step 5: 运行目标测试**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: PASS。

- [x] **Step 6: 提交独立修改**

```bash
git add aftersales-automation/public/app.js aftersales-automation/public/style.css aftersales-automation/test/server/after-sales-branch-ui.test.js
git commit -m "feat(aftersales): clarify branch stats hierarchy"
```

### Task 3: 回归验证与服务加载

**Files:**
- Verify only: `public/app.js`, `public/style.css`, `test/server/after-sales-branch-ui.test.js`

- [x] **Step 1: 运行语法和格式检查**

Run: `node --check public/app.js`

Expected: exit code 0。

Run: `git diff --check HEAD~2`

Expected: 无输出，exit code 0。

- [x] **Step 2: 运行完整测试**

Run: `npm test`

Expected: 全部测试通过，无失败或跳过。

- [x] **Step 3: 重启服务，不运行扫描**

Run: `launchctl kickstart -k gui/501/com.heizong.aftersale-server`

Expected: 服务重新启动，命令无报错。

- [x] **Step 4: 验证服务和只读接口**

Run: `curl --noproxy '*' -sS http://127.0.0.1:3457/health`

Expected: 返回 `{ "ok": true, ... }`。

Run: `curl --noproxy '*' -sS http://127.0.0.1:3457/api/auto-exec-confidence`

Expected: HTTP 200，仍返回 `uniqueWorkOrders`、`cases` 和原统计字段；不触发扫描或真实售后操作。
