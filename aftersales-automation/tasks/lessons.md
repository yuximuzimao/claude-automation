# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

> 本文件上次清理：2026-04-22。所有历史教训（§1-§17）已迁入 `docs/INDEX.md §6`。

---

## 待处理优化项

| 优先级 | 内容 | 状态 |
|---|---|---|
| ✅ | RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，条目关闭 | 完成 |

---

> 新的 session 级发现从这里往下记，稳定后迁入 §6。

## 2026-04-23 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 18 | HTML data 属性嵌 JSON 必须单引号包裹 | feedback_jingling_dev.md §18 |
| 19 | batch-reprocess 含 auto_executed，禁止用于部分重查 | feedback_jingling_dev.md §19 |
| 20 | routes.js/data.js 改动后必须重启服务器 | feedback_jingling_dev.md §20 |

## 2026-04-28 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 21 | ERP trade-detail-dialog 关闭方式 | feedback_jingling_dev.md §21 |
| 22 | session 缓存跳过 reload 后必须清残留弹窗；`node -e require()` 会执行 main() | feedback_jingling_dev.md §22 |
| 23 | ERP 多行数据必须聚合读取 | feedback_jingling_dev.md §23 |
| 24 | ERP 交易关闭状态 fallback textSnippet | feedback_jingling_dev.md §24 |
| 25 | 已执行工单重处理防护（executedAt 检查） | feedback_jingling_dev.md §25 |
| 27 | 并发扫描同一账号导致 CDP 脏数据 crash | feedback_jingling_dev.md §27 |
| 28 | list.js 不点筛选标签会读到所有状态工单 | feedback_jingling_dev.md §28 |
| 29 | 驿站待取件 ≠ 已签收，两者处理方式不同 | feedback_jingling_dev.md §29 |
| 30 | collect.js 重采时必须继承 feedbackStatus/groundTruth | feedback_jingling_dev.md §30 |
| 31 | scan-all.js ok 状态必须整条覆盖，不能 Object.assign | feedback_jingling_dev.md §31 |
| 32 | 重启系统必须同时验证队列状态 | feedback_jingling_dev.md §32 |

## 2026-04-28 session 新发现（未入 memory，待稳定后迁入）

### 33. Express 路由顺序：字面路由必须在动态路由前注册

`router.post('/accounts/add', ...)` 必须在 `router.post('/accounts/:num/relogin', ...)` 之前注册。
即使路径段数不同（`/add` 是2段，`/:num/relogin` 是3段），Express 仍可能先尝试动态匹配，导致 `/add` 返回 404。
**修复**：所有字面路径（无 `:param`）统一注册到动态路由段之前。

### 34. pkill -f 杀进程不可靠，必须用 lsof 找 PID

`pkill -f "node server.js"` 可能杀不到真正监听端口的进程（存在多个同名进程时只杀其中一个）。
**修复**：重启服务器前先 `lsof -i :PORT` 拿到监听进程 PID，再 `kill <PID>`，再启动新进程。

## 2026-04-29 session 教训

### 35. launchd KeepAlive:true 导致多实例堆积

`KeepAlive: true` 的 plist 配置会在进程退出时无条件重启。如果同时存在手动启动的实例，launchd 会不断叠加新进程。
**根因**：6 个 server.js 同时运行 → 6 个 op-queue 同时触发 auto-scan → 6 个 cli.js list 同时操作同一 Chrome 标签页 → CDP 冲突 → workOrderNum crash + waitFor 超时。
**修复**：
1. server.js 添加 lockfile 单实例锁（启动时检查 PID，退出时清理）
2. launchd 改用 `KeepAlive: { SuccessfulExit: true }`（只在正常退出时重启）
3. 禁用重复的 launchd 扫描任务（com.jl.scan-orders 和 server.js 的 auto-scan 重叠）

### 36. Object.assign 合并状态会保留旧字段

`updateAccountStatus` 用 `Object.assign(prev, patch)` 合并，如果 patch 不含 `error` 字段，旧的 error 会残留。
**修复**：当 `patch.status === 'ok'` 时显式 `delete merged.error`。
**同类问题**：scan-all.js 的成功路径已用整条覆盖（正确），但 op-queue.js 的 updateAccountStatus 遗漏了。

### 37. list.js 导航 3 次刷新可合并为 1 次

原来的流程：`location.reload()` → Vue Router `$router.push()` → 筛选点击 = 3 次刷新。
**优化**：合并为 CDP `Page.navigate` 直接跳转完整 URL + 等待 Vue 初始化 + 筛选点击 = 1 次刷新。
**效果**：每个账号从 9-24 秒降到约 3 秒，12 账号扫描总时间从 ~3 分钟降到 ~40 秒。

### 38. Bash 工作目录陷阱

`node -e "require('./lib/...')"` 的相对路径基于 Bash 工具的持久工作目录（`/Users/chat/claude`），不是项目目录。
**修复**：用 `require('./aftersales-automation/lib/...')` 或在命令前 `cd`。反复犯同一个错误 = 转圈式失败，必须立刻换方法。

## 2026-04-30 session 教训

### 39. 对应表搜索输入框必须用 `.el-input-popup-editor`（严重 bug）

**问题**：`makeSearchBarcodeJS` 用 `inputs[pivotIdx+1]`（从 `.el-input__inner` 列表中按"平台商家编码"字段的下一个 input 定位搜索框），但实际搜索输入框在 `.el-input-popup-editor` 内，不一定出现在 `.el-input__inner` 的相邻位置。
**后果**：搜索值被填到错误的 input → 搜索不执行或搜到错误结果 → hcsp 和 kgoskfzh-sm 两个货号的 product-match 步骤持续失败 → 工单被 escalate → 69% escalation 率中约 2-3 条是这个 bug 直接造成的。
**修复**：`document.querySelector('.el-input-popup-editor').querySelector('input')` — **与 product-mapping 项目保持一致**。
**教训**：product-mapping 项目在同一个 ERP 页面早已验证了正确选择器（`.el-input-popup-editor`），aftersales 项目用了不同方法却没有拉通对齐，属于跨项目知识未复用。

### 40. NodeList 没有 .filter() 方法（JS 基础 bug）

`document.querySelectorAll(...)` 返回 NodeList，不是 Array。调用 `.filter()` 会抛 TypeError → `cdp.eval` 返回 undefined → 后续的 `=== 0` 或 `> 50` 守卫检查全部失效（undefined 不等于任何数字）。
**修复**：必须 `Array.from(document.querySelectorAll(...)).filter(...)`。

### 41. 调试 ERP 问题必须操作真实页面，禁止从旧采集数据推测

之前在 simulations.jsonl 里看到7个候选就断定"ERP对应表只有7行"，实际上那7个是在错误选择器下搜到的残留数据。正确做法：直接用 `cdp.eval` 操作真实页面、刷新后逐步检查，用眼睛看到的结果说话。
**铁律**：如果结论依赖 ERP 页面状态，必须亲自执行 DOM 操作验证，不能从有 bug 的采集结果倒推。

## 2026-05-01 session 教训

### 42. ERP 登录恢复禁止 reload 已在登录页的页面

Chrome 密码管理器在同一页面生命周期内只自动填充一次。`location.reload()` 清掉已填充的密码 → 后续点击密码框时 Chrome 不再触发。
**修复**：检测 `url.includes('login')` → 跳过 reload → 先点用户名 → 再点密码 → 3次重试。

### 43. 赠品必须和主品做完全对等的采集链路

collect.js 只对主品做了 product-match → product-archive，赠品只做了 erp-search。
**修复**：新增 Step 6b，赠品也跑完整的 product-match + product-archive 链路。
**教训**：新增采集步骤时必须检查"主品做了赠品是否也做了"。

### 44. 活动组合更新导致 archive 不含全部入库品

ERP 对应表 SKU 是当前版本，工单 attr1 是下单时版本。更新后 archive 可能缺少旧版配件。
**修复**：逐商品匹配后检查未匹配入库项 > 0 → escalate + attr1 解析提示。
**教训**：不能假设 archive.subItems 覆盖了所有入库品类。
