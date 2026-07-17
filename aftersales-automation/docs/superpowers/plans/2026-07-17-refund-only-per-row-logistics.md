# 仅退款逐行物流判断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 仅退款工单对主品和赠品的全部已采集 ERP 行逐行判断，只有每行均未发货或已有退回物流节点时才允许退款。

**Architecture:** 保留现有采集流程和 `inferRefundOnly()` 主结构，只把赠品查询从第一个子订单补齐为全部子订单，并修正行状态汇总、带单号行的物流路由和安全放行条件。继续复用现有 ERP/鲸灵物流结果与退回关键词，不新增服务、数据文件或置信逻辑。

**Tech Stack:** Node.js、`node:test`、现有规则推理引擎。

---

### Task 1: 补齐全部赠品子订单采集

**Files:**
- Modify: `lib/jl/target-aware-collector.js`
- Modify: `test/jl/target-aware-collector.test.js`

- [ ] **Step 1: 写失败回归测试**

构造含两个赠品子订单的仅退款工单，断言两个赠品 ID 都分别执行 `erpSearch` 和 `readAllErpLogistics`，并分别保存在 `giftErpSearches`：

```js
assert.deepEqual(result.giftErpSearches.map(item => item.subOrderId), ['gift-1', 'gift-2']);
assert.equal(result.giftErpSearch.subOrderId, 'gift-1');
```

- [ ] **Step 2: 确认测试先失败**

Run: `node --test test/jl/target-aware-collector.test.js`

Expected: 当前只查询第一个赠品，新增用例失败。

- [ ] **Step 3: 写最小实现**

在 `emptyCollectedData()` 中增加 `giftErpSearches: []`；把 `(ticket.gifts || [])[0]` 改成顺序遍历全部赠品，查询结果写入数组，并继续把第一项赋给 `giftErpSearch` 兼容旧代码。

- [ ] **Step 4: 运行采集专项测试**

Run: `node --test test/jl/target-aware-collector.test.js`

Expected: 全部通过。

### Task 2: 仅退款逐行判断

**Files:**
- Modify: `lib/infer.js`
- Create: `test/infer/refund-only-row-logistics.test.js`

- [ ] **Step 1: 写失败回归测试**

覆盖以下输入与结果：

```js
// 全部无单号：待审核、待打印、待发货混合 → approve
// 第一行待审核无单号、后一行待打印有单号且物流在途 → 不得 approve
// 同样的混合行，但带单号行已有退回节点 → approve
// 有单号且物流明确未揽收 → approve
// 卖家已发货但无单号 → escalate
// 赠品行有单号且仍在途 → 不得 approve
// intercepted=true 但物流仍在途 → 不得 approve
// 有单号但物流读取不明 → 不得 approve
```

- [ ] **Step 2: 确认测试先失败**

Run: `node --test test/infer/refund-only-row-logistics.test.js`

Expected: 当前代码至少在“首行待审核、后行有单号”和“待发货无单号”场景失败。

- [ ] **Step 3: 写最小实现**

在 `lib/infer.js` 内完成以下局部调整：

```js
// 1. 待发货且无单号纳入未发货状态。
const NOT_SHIPPED = ['待审核', '待打印快递单', '待发货'];

// 2. getErpRows() 对赠品优先合并 giftErpSearches，兼容旧 giftErpSearch。
// 3. 主品或赠品任意行有单号，都跳过“全部无单号”直接退款分支，进入物流判断。
// 4. 卖家已发货/交易成功/交易关闭却无单号，直接 escalate。
// 5. 物流判断纳入所有带单号行，不再只纳入“卖家已发货”等状态行。
// 6. 每个单号只接受两种安全结果：明确未揽收，或存在退回/拒收/安排退回节点。
// 7. 在途、签收、驿站、未知以及仅有 intercepted 记录都不得 approve。
```

只增加局部纯函数识别物流结果；不修改采集器、页面操作、自动执行门禁和其他售后类型。

- [ ] **Step 4: 运行专项测试**

Run: `node --test test/infer/refund-only-row-logistics.test.js`

Expected: 全部通过。

- [ ] **Step 5: 运行推理与全量回归**

Run: `node test/flow-test.js`

Expected: 现有推理回归全部通过。

Run: `npm test`

Expected: 全量 `node:test` 通过。

- [ ] **Step 6: 检查并提交**

```bash
git diff --check
git add aftersales-automation/lib/infer.js aftersales-automation/lib/jl/target-aware-collector.js aftersales-automation/test/infer/refund-only-row-logistics.test.js aftersales-automation/test/jl/target-aware-collector.test.js
git commit -m "fix(aftersales): verify refund-only ERP rows individually"
git push origin main
```
