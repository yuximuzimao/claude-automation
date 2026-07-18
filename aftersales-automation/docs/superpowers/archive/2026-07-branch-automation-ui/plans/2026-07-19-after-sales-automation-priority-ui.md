# After-Sales Automation Priority UI Implementation Plan

> 归档状态（2026-07-19）：全部完成，代码已合并到主干提交 `57d8937`，完整测试 295/295 通过。本文件只用于追溯实施过程。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把售后分支统计页改成以自动化价值为主线的详细分支卡片，并从本页彻底排除采集或归类异常的数据。

**Architecture:** 保持现有 `/api/auto-exec-confidence` 数据和自动执行门禁不变，仅在 `renderAfterSalesBranches()` 的展示入口过滤无效分支，再按 `enabled → candidate → manual_only` 分区。卡片所需的类型、条件和结果直接拆分现有固定 `branchLabel`，不新增后端字段或推理逻辑。

**Tech Stack:** 原生 JavaScript、原生 HTML/CSS、Node.js `node:test`

---

## 文件结构

- Modify: `test/server/after-sales-branch-ui.test.js` — 用真实渲染结果锁定过滤、分区、排序、字段和窄屏规则。
- Modify: `public/app.js` — 过滤异常分支，拆分固定条件路径，渲染三层分支卡片。
- Modify: `public/style.css` — 用绿、蓝、灰建立自动化优先级，并保证窄屏可读。
- Reference: [售后分支统计页清晰化设计](../specs/2026-07-18-after-sales-branch-ui-design.md) — 已确认的产品口径，不在实现中扩展范围。

不创建新的组件文件，不改后端接口，不改 `lib/server/after-sales-auto-gate.js`，不增加自动评分或自动授权。

### Task 1: 用测试锁定正常数据边界与页面层级

**Files:**
- Modify: `test/server/after-sales-branch-ui.test.js:49-119`
- Test: `test/server/after-sales-branch-ui.test.js`

- [x] **Step 1: 将旧的“异常优先”测试改成新的数据边界测试**

测试数据同时放入已授权、候选、仅人工、未登记和资料缺失五类分支。断言只有前三类出现在页面中，并且顶部数量不包含异常分支：

```js
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
  assert.ok(html.indexOf('已授权自动') < html.indexOf('可评估自动化'));
  assert.ok(html.indexOf('可评估自动化') < html.indexOf('仅人工'));
  assert.doesNotMatch(html, /错误搜索结果|ERP 少读一行|资料是否缺失/);
  assert.match(html, /最近30天有效工单 9 单 · 正常固定分支 3 个/);
  assert.match(html, /branch-tier branch-tier-manual/);
  assert.doesNotMatch(html, /branch-tier branch-tier-manual" open/);
});
```

- [x] **Step 2: 增加卡片明细与候选排序测试**

同一候选层放入两个分支，验证真实自动成功较多的分支排在前面，并直接看到原因、类型、条件、结果、五项历史数字和备注分布：

```js
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
  assert.doesNotMatch(html, /查看详情|需要关注|is-attention|has-negative/);
});
```

- [x] **Step 3: 运行定向测试并确认先失败**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: FAIL；旧页面仍显示异常数据、四项概览和“查看详情”，也没有三层卡片结构。

### Task 2: 最小改写分支渲染器

**Files:**
- Modify: `public/app.js:1470-1578`
- Test: `test/server/after-sales-branch-ui.test.js`

- [x] **Step 1: 在渲染函数内加入正常分支过滤和证据排序**

使用现有字段，不修改接口：

```js
const cases = (report.cases || []).filter(item =>
  item.registered !== false && (item.missingFacts || []).length === 0
);
const evidenceSort = (a, b) =>
  Number(b.autoSuccessCount || 0) - Number(a.autoSuccessCount || 0)
  || Number(b.positiveCount || 0) - Number(a.positiveCount || 0)
  || Number(a.negativeCount || 0) - Number(b.negativeCount || 0)
  || Number(b.occurrenceCount || 0) - Number(a.occurrenceCount || 0)
  || String(a.branchLabel || '').localeCompare(String(b.branchLabel || ''), 'zh-CN');
const tiers = {
  enabled: cases.filter(item => item.automationStatus === 'enabled').sort(evidenceSort),
  candidate: cases.filter(item => item.automationStatus === 'candidate').sort(evidenceSort),
  manual_only: cases.filter(item => !['enabled', 'candidate'].includes(item.automationStatus)).sort(evidenceSort),
};
```

人话结果：未登记和缺资料的数据连计数都不参与；排序只是展示顺序，不写回状态、不开放权限。

- [x] **Step 2: 从固定分支名称拆出类型、条件和结果**

```js
function splitBranchPath(item) {
  const parts = String(item.branchLabel || '').split('/').map(value => value.trim()).filter(Boolean);
  if (parts[0] === item.orderType) parts.shift();
  const result = parts.length > 1
    ? parts.pop()
    : (actionLabels[item.expectedAction] || parts.pop() || '人工处理');
  return { conditions: parts, result };
}
```

这里仅拆开现有固定文字。例如“退货退款 / 已入库 / 精确退回 / 同意退款”会显示为类型“退货退款”、条件“已入库、精确退回”、结果“同意退款”。

- [x] **Step 3: 将一行结果改成直接展开的分支卡片**

每张卡片使用以下稳定结构，所有动态文本继续经过 `h()`：

```js
function renderBranchCard(item, tier) {
  const path = splitBranchPath(item);
  const conditions = path.conditions.length
    ? path.conditions.map(value => `<span class="branch-condition">${h(value)}</span>`).join('<span class="branch-arrow">→</span>')
    : '<span class="branch-condition">无额外条件</span>';
  const notes = (item.notes || []).map(note => `${h(note.value)}（${Number(note.count || 0)}）`).join('；');
  return `<article class="branch-card branch-card-${tier}">
    <header class="branch-card-header">
      <div><div class="branch-card-reason">${h(item.afterSaleReason)}</div><div class="branch-card-type">售后类型 · ${h(item.orderType)}</div></div>
      <span class="branch-status ${tier}">${statusLabels[tier]}</span>
    </header>
    <div class="branch-path">
      <div><span class="branch-field-label">必须满足</span><div class="branch-conditions">${conditions}</div></div>
      <div class="branch-outcome"><span class="branch-field-label">处理结果</span><strong>${h(path.result)}</strong></div>
    </div>
    <div class="branch-metrics">
      <div><span>出现次数</span><strong>${Number(item.occurrenceCount || 0)}</strong></div>
      <div><span>真实自动成功</span><strong>${Number(item.autoSuccessCount || 0)}</strong></div>
      <div><span>好评</span><strong>${Number(item.positiveCount || 0)}</strong></div>
      <div><span>差评</span><strong>${Number(item.negativeCount || 0)}</strong></div>
      <div><span>人工处理</span><strong>${Number(item.manualHandledCount || 0)}</strong></div>
    </div>
    ${notes ? `<div class="branch-notes"><span>历史备注</span>${notes}</div>` : ''}
  </article>`;
}
```

- [x] **Step 4: 渲染已授权、候选和仅人工三个区域**

已授权和候选直接展开，仅人工使用没有 `open` 属性的 `<details>`。顶部只保留两项重点数量，其他数字成为辅助说明：

```js
const validWorkOrders = cases.reduce((sum, item) => sum + Number(item.occurrenceCount || 0), 0);
const renderCards = (items, tier) => items.map(item => renderBranchCard(item, tier)).join('');

const enabledHtml = `<section class="branch-tier branch-tier-enabled">
  <div class="branch-tier-heading"><h4>已授权自动</h4><span>${tiers.enabled.length} 个分支</span></div>
  <div class="branch-card-list">${renderCards(tiers.enabled, 'enabled') || '<div class="branch-tier-empty">暂无已授权分支</div>'}</div>
</section>`;
const candidateHtml = `<section class="branch-tier branch-tier-candidate">
  <div class="branch-tier-heading"><h4>可评估自动化</h4><span>${tiers.candidate.length} 个分支</span></div>
  <div class="branch-card-list">${renderCards(tiers.candidate, 'candidate') || '<div class="branch-tier-empty">暂无候选分支</div>'}</div>
</section>`;
const manualHtml = `<details class="branch-tier branch-tier-manual">
  <summary class="branch-tier-heading"><h4>仅人工</h4><span>${tiers.manual_only.length} 个分支</span></summary>
  <div class="branch-card-list">${renderCards(tiers.manual_only, 'manual_only') || '<div class="branch-tier-empty">暂无仅人工分支</div>'}</div>
</details>`;

return `<div class="chart-section">
  <h3>售后自动化分支（最近30天）</h3>
  <div class="branch-section-note">最近30天有效工单 ${validWorkOrders} 单 · 正常固定分支 ${cases.length} 个。历史会自动刷新，但不会自动学习或自行开放权限。</div>
  <div class="branch-overview">
    <div class="branch-overview-card is-enabled"><div class="branch-overview-value">${tiers.enabled.length}</div><div class="branch-overview-label">已授权自动</div></div>
    <div class="branch-overview-card is-candidate"><div class="branch-overview-value">${tiers.candidate.length}</div><div class="branch-overview-label">可评估自动化</div></div>
  </div>
  ${cases.length ? enabledHtml + candidateHtml + manualHtml : '<div class="branch-tier-empty">最近30天暂无可评估的正常分支。</div>'}
</div>`;
```

空分区显示一句简短空状态，不制造额外卡片；整个页面没有正常分支时显示“最近30天暂无可评估的正常分支”。

- [x] **Step 5: 运行定向测试并确认逻辑通过**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: 新增的过滤、层级、卡片字段和排序断言 PASS；窄屏样式测试暂未调整时可以继续失败。

- [x] **Step 6: 提交渲染逻辑和测试**

```bash
git add public/app.js test/server/after-sales-branch-ui.test.js
git commit -m "feat(aftersales): prioritize automatable branches"
```

### Task 3: 建立绿、蓝、灰三层视觉和窄屏布局

**Files:**
- Modify: `test/server/after-sales-branch-ui.test.js:120-130`
- Modify: `public/style.css:1352-1491`
- Test: `test/server/after-sales-branch-ui.test.js`

- [x] **Step 1: 先把窄屏和无红色重点规则写成失败测试**

```js
test('分支卡片用绿蓝灰表达自动化层级，并在窄屏改为单列', () => {
  const css = fs.readFileSync(path.join(__dirname, '../../public/style.css'), 'utf8');
  assert.match(css, /\.branch-tier-enabled[\s\S]*var\(--green\)/);
  assert.match(css, /\.branch-tier-candidate[\s\S]*var\(--blue\)/);
  assert.match(css, /\.branch-tier-manual[\s\S]*var\(--gray-400\)/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*\.branch-metrics\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.doesNotMatch(css, /branch-(?:card|tier)[^\n{]*attention|branch-result-counts \.has-negative/);
});
```

- [x] **Step 2: 运行定向测试并确认样式断言失败**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: FAIL；新卡片还没有完整三层样式和窄屏两列指标。

- [x] **Step 3: 用专用卡片样式替换旧原因折叠行样式**

样式只承担信息层级，不增加动画、图表或交互：

```css
.branch-overview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 12px 0 18px; }
.branch-overview-card.is-enabled { border-left: 4px solid var(--green); }
.branch-overview-card.is-candidate { border-left: 4px solid var(--blue); }
.branch-tier { margin-top: 16px; }
.branch-tier-enabled { --tier-color: var(--green); --tier-bg: var(--green-light); }
.branch-tier-candidate { --tier-color: var(--blue); --tier-bg: var(--blue-light); }
.branch-tier-manual { --tier-color: var(--gray-400); --tier-bg: var(--gray-50); }
.branch-tier-heading { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.branch-card-list { display: grid; gap: 10px; }
.branch-card { overflow: hidden; border: 1px solid var(--gray-200); border-left: 4px solid var(--tier-color); border-radius: 10px; background: #fff; }
.branch-card-header { display: flex; justify-content: space-between; gap: 12px; padding: 13px 14px; background: var(--tier-bg); }
.branch-card-reason { font-size: 14px; font-weight: 700; line-height: 1.45; }
.branch-card-type, .branch-field-label, .branch-notes > span { color: var(--gray-600); font-size: 11px; }
.branch-path { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, .35fr); gap: 12px; padding: 12px 14px; }
.branch-conditions { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.branch-condition { padding: 4px 7px; border-radius: 6px; background: var(--gray-100); font-size: 12px; }
.branch-arrow { color: var(--gray-400); }
.branch-outcome { padding-left: 12px; border-left: 1px solid var(--gray-200); }
.branch-outcome strong { display: block; margin-top: 5px; }
.branch-metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border-top: 1px solid var(--gray-100); }
.branch-metrics > div { padding: 10px 12px; border-right: 1px solid var(--gray-100); }
.branch-metrics span { display: block; color: var(--gray-600); font-size: 11px; }
.branch-metrics strong { display: block; margin-top: 3px; font-size: 16px; font-variant-numeric: tabular-nums; }
.branch-notes { padding: 9px 14px; border-top: 1px solid var(--gray-100); font-size: 12px; line-height: 1.6; }
```

候选状态文字改用蓝色；仅人工折叠摘要和内部卡片降低对比度。删除 `.is-attention`、`.has-negative`、`.branch-detail-warning` 等旧异常重点规则。

- [x] **Step 4: 加入窄屏规则**

```css
@media (max-width: 760px) {
  .branch-overview { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .branch-card-header { align-items: flex-start; flex-direction: column; }
  .branch-path { grid-template-columns: 1fr; }
  .branch-outcome { padding-top: 10px; padding-left: 0; border-top: 1px solid var(--gray-200); border-left: 0; }
  .branch-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .branch-metrics > div { min-width: 0; }
}
```

- [x] **Step 5: 运行定向测试**

Run: `node --test test/server/after-sales-branch-ui.test.js`

Expected: PASS，全部售后分支 UI 测试通过。

- [x] **Step 6: 提交样式和测试**

```bash
git add public/style.css test/server/after-sales-branch-ui.test.js
git commit -m "style(aftersales): clarify branch automation tiers"
```

### Task 4: 完整验证与服务更新

**Files:**
- Verify: `public/app.js`
- Verify: `public/style.css`
- Verify: `test/server/after-sales-branch-ui.test.js`

- [x] **Step 1: 运行完整测试**

Run: `npm test`

Expected: 全部测试 PASS，无失败、无跳过增加。

- [x] **Step 2: 检查差异和无关文件**

Run: `git diff --check && git status --short`

Expected: 当前功能分支干净；没有把主工作区既有的无关改动带入提交。

- [x] **Step 3: 对照设计做只读审查**

逐项确认：异常分支已排除；已授权最前；候选第二且证据排序；仅人工折叠；卡片条件和结果没有重新推理；没有自动授权写操作；没有红色异常重点；AI 洞察过滤保持不变。

- [x] **Step 4: 重启现有服务，不触发扫描**

Run: `launchctl kickstart -k gui/501/com.heizong.aftersale-server`

Expected: launchd 完成服务重启；不运行任何扫描命令。

- [x] **Step 5: 验证服务和真实接口**

Run: `curl --noproxy '*' -sS http://127.0.0.1:3457/health`

Expected: 返回健康状态。

Run: `curl --noproxy '*' -sS http://127.0.0.1:3457/api/auto-exec-confidence`

Expected: 返回最近 30 天分支数据，原始异常记录仍在接口中，前端负责不展示；自动权限数据没有变化。
