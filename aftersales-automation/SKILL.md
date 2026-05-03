---
name: aftersales-automation
description: 鲸灵售后自动化——工单扫描、信息采集、规则推理、退款审批/拒绝。CDP 直连 Chrome 操作鲸灵SCRM+快麦ERP。
skill_dir: aftersales-automation
entry: cli.js
---

## DO FIRST

1. **找 CLI 命令** → `cli.js`（17 个命令，JSON 输出 `{success, data/error}`）
2. **找流程逻辑** → `lib/server/pipeline.js`（scan→collect→infer→approve/reject）
3. **找规则/红线** → `docs/INDEX.md`（错误分级、工单路由、已知坑位 §6）
4. **不要直接读 `routes.js`**——它是 Express 薄层，业务逻辑在 `lib/` 下
5. **ERP 操作串行**——所有 ERP 命令用 `&&` 串行，禁止并行

## ENTRY MAP

| 文件 | 作用 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，17 个命令的路由分发 | 需要了解可用命令或新增命令时 |
| `server.js` | Express 服务（port 3457），定时扫描+队列管理+Web 面板 | 改 API/队列/定时任务时 |
| `lib/infer.js` | 规则推理引擎（926行），主入口 `inferDecision()` | 改决策逻辑/文案时 |
| `lib/ai-infer.js` | AI 推理集成（Anthropic API） | 调 AI 推理参数/prompt 时 |
| `lib/cdp.js` | CDP 直连 Chrome（WebSocket port 9222），`eval/clickAt/navigate` | 写/改浏览器操作时 |
| `lib/targets.js` | 查找鲸灵+ERP 浏览器 tab ID | 需要定位浏览器标签时 |
| `lib/wait.js` | `sleep()`, `waitFor()` 工具 | 需要等待/重试逻辑时 |
| `lib/result.js` | `ok()/fail()` JSON 封包 | 新增 CLI 命令时 |
| `lib/constants.js` | 共享常量（扫描时间/关键词/红灯） | 查常量定义时 |
| `lib/erp/navigate.js` | ERP 页面导航+登录恢复（最长文件） | ERP 页面跳转/登录异常时 |
| `lib/erp/search.js` | ERP 订单搜索，`READ_ROWS_JS` 解析订单状态 | 查 ERP 订单数据时 |
| `lib/erp/aftersale.js` | ERP 售后工单搜索（退货快递单号） | 退货核验时 |
| `lib/erp/read-logistics.js` | ERP 订单物流读取 | 查 ERP 物流时 |
| `lib/erp/shop-map.js` | 账号→ERP 店铺名映射 | 需要确定 ERP 店铺时 |
| `lib/jl/list.js` | 鲸灵工单列表扫描 | 改列表扫描逻辑时 |
| `lib/jl/read-ticket.js` | 读单条工单详情 | 改工单数据提取时 |
| `lib/jl/approve.js` | 同意退款（处理三层弹窗） | 改审批流程时 |
| `lib/jl/reject.js` | 拒绝退款（含物流截图上传） | 改拒绝流程时 |
| `lib/jl/add-note.js` | 添加内部备注 | 改备注逻辑时 |
| `lib/jl/navigate.js` | 鲸灵页面导航 | 需要跳鲸灵页面时 |
| `lib/jl/logistics.js` | 读鲸灵物流信息 | 查鲸灵侧物流时 |
| `lib/product/match.js` | ERP 商品对应表查询 | 查商品匹配时 |
| `lib/product/archive.js` | ERP 商品档案V2查询 | 查商品档案时 |
| `lib/server/routes.js` | Express API 路由（569行，43 路由） | 改 API 端点时 |
| `lib/server/data.js` | JSON/jsonl 数据持久化 | 改数据读写时 |
| `lib/server/op-queue.js` | 全局操作队列（串行化浏览器操作） | 改队列逻辑时 |
| `lib/server/sse.js` | Server-Sent Events 实时推送 | 改前端实时更新时 |

## CORE FLOWS

### 主流程：scan → collect → infer → approve/reject

1. **scan** — `scan-all.js` → 多账号扫描工单列表 → 写入 `data/queue.json` (anchor: listTickets)
2. **collect** — `collect.js` → 读工单详情+ERP数据+商品信息 → 写入 `data/simulations.jsonl` (anchor: readTicket, erpSearch, productMatch, productArchive)
3. **infer** — `lib/infer.js` → 规则推理 → 输出 decision (anchor: inferDecision, inferRefundOnly, inferRefundReturn)
4. **execute** — `lib/jl/approve.js` 或 `lib/jl/reject.js` → 执行审批 (anchor: approveTicket, rejectTicket)

### 重试与重启

- **采集重试**：collect.js 失败（含 SIGTERM kill → exit code null）最多重试 3 次（`collectRetries` 计数器在 `pipeline.js` processOne），第 3 次失败标记 `simulated` 上报人工。成功进入 `inferring` 时计数器清零。
- **延迟重查**：推理返回 `waitingRescan: true` 时工单进入 `waiting` 状态，距上次推理 ≥ `RESCAN_INTERVAL_HOURS`(4h) 后下次扫描自动重置为 `pending` 重采。
- **代码生效**：修改 `lib/` 下决策逻辑文件后，必须执行 `/aftersales-restart` 重启 server（server 启动时加载模块到内存，不重启新逻辑不生效）。重启后自动批量重跑未处理工单。

### 工单类型路由（`docs/INDEX.md §2`）

| 类型 | 文档 | 对应函数 |
|------|------|---------|
| 退货退款 | `docs/flow-5.1.md` | `inferRefundReturn()` (anchor: inferRefundReturn) |
| 仅退款（未发货） | `docs/flow-5.2.md` | `inferRefundOnly()` (anchor: inferRefundOnly) |
| 仅退款（已发货） | `docs/flow-5.3.md` | `inferRefundOnly()` (anchor: inferRefundOnly) |
| 换货 | `docs/flow-5.4.md` | — |

### ERP 操作流程

1. **登录恢复** — `lib/erp/navigate.js` → 检测+恢复登录 (anchor: checkLogin, recoverLogin)
2. **导航** — `lib/erp/navigate.js` → 页面导航 (anchor: erpNav)
3. **搜索** — `lib/erp/search.js` → 订单搜索+状态解析 (anchor: erpSearch)
4. **物流** — `lib/erp/read-logistics.js` → 物流追踪 (anchor: readErpLogistics, readAllErpLogistics)

## NON-STANDARD PATTERNS

### CDP 操作范式

```js
// eval: 在浏览器 tab 中执行 JS 并返回结果
const result = await cdp.eval(targetId, `document.title`);

// clickAt: 物理点击元素（非 JS .click()）
await cdp.clickAt(targetId, 'button.el-button--primary');

// navigate: 导航到 URL（等待 Page.loadEventFired）
await cdp.navigate(targetId, 'https://...');
```

**关键约束**：
- CDP 直连 Chrome port 9222，无 proxy。port 3456 被 web-access skill 占用
- `cdp.eval()` 在页面上下文执行 JS，返回值通过 CDP Runtime.evaluate 返回
- 所有 CDP 操作**必须串行**——同一 tab 的并发 CDP 调用会冲突

### Element UI 处理规则

- **el-select 展开**：必须用 `cdp.clickAt(targetId, 'input.el-input__inner[placeholder="请选择"]')`，JS `.click()` 不触发 mousedown → 下拉不展开
- **搜索输入框**：selector = `.el-input-popup-editor`（不是普通 input）
- **多层 dialog 确定按钮**：找可见 footer（`getBoundingClientRect().height > 0`）的 primary button
- **el-input-number 值**：读 `td.querySelector('input').value`，不是 `innerText`（始终为空）
- **弹窗关闭**：尝试 `button.el-dialog__closeBtn` 和 `button.el-dialog__headerbtn`

### 登录恢复机制

- 触发条件：`checkLogin()` 返回 `loggedIn: false`
- 处理：`recoverLogin()` 自动填充账号密码+点击登录
- 密码框：必须 `cdp.clickAt(targetId, 'input[type="password"]')` 触发 Chrome 自动填充

## FAILURE PATTERNS

| # | 错误 | 正确做法 |
|---|------|---------|
| 1 | 并行操作 ERP | ERP 命令必须 `&&` 串行，违者页面状态混乱 |
| 2 | 赠品子订单号推算（主号+1） | 必须从 `giftSubBizOrderDetailDTO.subBizOrderId` 读取 |
| 3 | 靠商品名字判断商品是否一致 | 必须用规格商家编码对比 |
| 4 | 备注写编码而非名称 | 必须写 ERP shortTitle，禁止写 kgosbwh 等编码 |
| 5 | `node -e "require('./scan-all')"` 检查语法 | 用 `node --check <file>`，否则触发全量扫描 |
| 6 | 截图判断操作结果 | 截图只用于上传凭证，所有判断用 DOM 文字 |
| 7 | el-select 用 JS `.click()` | 必须用 `cdp.clickAt()` 触发物理点击 |
| 8 | ERP 状态直接决策 | ERP 状态只路由不决策；"交易关闭"走物流判断，不直接同意退款 |
| 9 | collect.js spawn timeout → exit code null | 被 SIGTERM 杀死时 exit code=null（非数字），`null !== 0` 为 true 触发重试。排查前先确认是超时还是逻辑错误 |
| 10 | collect.js 失败无上限导致死循环 | 失败→重置 pending→pipeline 重采→又失败→无限。collectRetries 计数器 3 次上限后标记 simulated；成功后（进入 inferring）清零 |

## PATHS

lib/ai-infer.js
lib/cdp.js
lib/constants.js
lib/erp/aftersale.js
lib/erp/navigate.js
lib/erp/read-logistics.js
lib/erp/search.js
lib/erp/shop-map.js
lib/infer.js
lib/jl/add-note.js
lib/jl/approve.js
lib/jl/list.js
lib/jl/logistics.js
lib/jl/navigate.js
lib/jl/read-ticket.js
lib/jl/reject.js
lib/product/archive.js
lib/product/match.js
lib/result.js
lib/server/data.js
lib/server/op-queue.js
lib/server/pipeline.js
lib/server/routes.js
lib/server/sse.js
lib/targets.js
lib/wait.js
cli.js
server.js
collect.js
scan-all.js
docs/INDEX.md
