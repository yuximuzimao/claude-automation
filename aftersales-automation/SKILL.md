---
name: aftersales-automation
description: 鲸灵售后自动化——工单扫描、信息采集、规则推理、退款审批/拒绝。CDP 直连 Chrome 操作鲸灵SCRM+快麦ERP。
skill_dir: aftersales-automation
entry: cli.js
---

## DO FIRST

1. **找 CLI 命令** → `cli.js`（18 个命令，JSON 输出 `{success, data/error}`）
2. **找流程逻辑** → `lib/server/pipeline.js`（scan→collect→infer→approve/reject）
3. **找规则/红线** → `docs/INDEX.md`（错误分级、工单路由、已知坑位 §6）
4. **不要直接读 `routes.js`**——它是 Express 薄层，业务逻辑在 `lib/` 下
5. **ERP 操作串行**——所有 ERP 命令用 `&&` 串行，禁止并行

## ENTRY MAP

| 文件 | 作用 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，18 个命令的路由分发 | 需要了解可用命令或新增命令时 |
| `server.js` | Express 服务（port 3457），队列管理 + Web 面板。**定时扫描/ERP心跳/启动自动入队已停用（2026-06-16 停旧系统）**，待第二三步以新安全注入路径重建 | 改 API/队列/定时任务时 |
| `lib/infer.js` | 规则推理引擎（1118行），主入口 `inferDecision()` | 改决策逻辑/文案时 |
| `lib/ai-infer.js` | AI 推理集成（Anthropic API） | 调 AI 推理参数/prompt 时 |
| `lib/cdp.js` | CDP 直连 Chrome（WebSocket port 9222），`eval/clickAt/navigate` | 写/改浏览器操作时 |
| `lib/targets.js` | 查找鲸灵+ERP 浏览器 tab ID | 需要定位浏览器标签时 |
| `lib/wait.js` | `sleep()`, `waitFor()`, `retry()` 工具；内置 `FORCE_NO_RETRY_DOMAINS` 自动禁止鲸灵重试 + `isRiskControlError()` 风控信号检测 + 熔断钩子 | 需要等待/重试/风控防护时 |
| `lib/helpers.js` | 共享工具函数 `extractShippedTrackings()` + `createReminder()` | 提取快递单号或创建 Mac Reminder 时 |
| `lib/result.js` | `ok()/fail()` JSON 封包 | 新增 CLI 命令时 |
| `lib/constants.js` | 共享常量（扫描时间/关键词/红灯） | 查常量定义时 |
| `lib/erp/navigate.js` | ERP 页面导航+登录恢复（最长文件） | ERP 页面跳转/登录异常时 |
| `lib/erp/search.js` | ERP 订单搜索，`READ_ROWS_JS` 解析订单状态 | 查 ERP 订单数据时 |
| `lib/erp/aftersale.js` | ERP 售后工单搜索（退货快递单号） | 退货核验时 |
| `lib/erp/read-logistics.js` | ERP 订单物流读取 | 查 ERP 物流时 |
| `lib/erp/shop-map.js` | 账号→ERP店铺名 + 供应商ID→店铺名映射（sku-calculator 共享） | 需要确定 ERP 店铺时 |
| `lib/jl/list.js` | 鲸灵工单列表扫描 | 改列表扫描逻辑时 |
| `lib/jl/read-ticket.js` | 读单条工单详情 | 改工单数据提取时 |
| `lib/jl/session-filter.js` | 最小注入白名单——`filterAuthCookies`/`filterIdentityLocalStorage`，只搬认证态+账号身份，丢弃设备/网络指纹（跨设备搬指纹触发风控） | 改注入字段白名单时 |
| `lib/jl/approve.js` | 同意退款（处理三层弹窗） | 改审批流程时 |
| `lib/jl/reject.js` | 拒绝退款（含物流截图上传） | 改拒绝流程时 |
| `lib/jl/add-note.js` | 添加内部备注 | 改备注逻辑时 |
| `lib/jl/navigate.js` | 鲸灵页面导航 | 需要跳鲸灵页面时 |
| `lib/jl/logistics.js` | 读鲸灵物流信息 | 查鲸灵侧物流时 |
| `lib/jl/alerts.js` | 鲸灵首页平台提醒采集，按账号缓存 `data/jl-alerts-cache.json`，前端触发条+展开面板展示 | 改平台提醒逻辑时 |
| `lib/jl-session-state.js` | 鲸灵当前账号缓存读写（`data/current-session.json`） | 改多账号扫描、采集注入、op-queue 注入判断时 |
| `lib/jl-account-config.js` | 重新登录保存时合并账号配置，保留 phone/name/note/file | 改店铺管理重登保存逻辑时 |
| `lib/product/match.js` | ERP 商品对应表查询 | 查商品匹配时 |
| `lib/product/archive.js` | ERP 商品档案V2查询 | 查商品档案时 |
| `lib/server/routes.js` | Express API 路由（639行，45 路由） | 改 API 端点时 |
| `lib/server/data.js` | JSON/jsonl 数据持久化 | 改数据读写时 |
| `lib/server/op-queue.js` | 全局操作队列（串行化浏览器操作） | 改队列逻辑时 |
| `lib/server/account-session-status.js` | 账号 session 状态判定——`getAccountOpenGuard()` 按 ok/unknown/expired/error 决定是否拦截打开后台 | 改打开后台/状态拦截逻辑时 |
| `lib/server/pipeline-status.js` | 扫描终态归类——明确终态 skip 进 auto_executed 而非静默 done | 改终态归档逻辑时 |
| `lib/server/sse.js` | Server-Sent Events 实时推送 | 改前端实时更新时 |
| `lib/server/auto-exec-confidence.js` | 自动执行置信度系统 — 场景指纹+人工反馈驱动 auto 判定 | 查/改自动执行条件时 |
| `public/app.js` | 前端主逻辑（2026行）— 8 Tab 渲染、快递行动分类 `isReturnWaitingAction()`、徽章计数、品牌分组、倒计时格式化 | 改前端展示/分类逻辑时 |
| `public/index.html` | 前端 HTML 骨架 — 8 Tab 结构、模版、header 控件 | 改页面结构时 |
| `public/style.css` | 前端样式 — 紧急度颜色、面板布局、响应式 | 改样式时 |
| `../return-inbound/SKILL.md` | 退货入库项目导航地图（跨目录） | 调试/改退货入库 op 时；op-queue 的 `return-inbound` case 调用 `../return-inbound/lib/workflow.js` |

## CORE FLOWS

### 主流程：scan → collect → infer → approve/reject

1. **scan** — `scan-all.js` → 多账号扫描工单列表 → 成功注入账号后写 `data/current-session.json` → 写入 `data/queue.json` (anchor: listTickets)
2. **collect** — `collect.js` → 读工单详情+ERP数据+商品信息 → 写入 `data/simulations.jsonl` (anchor: readTicket, erpSearch, productMatch, productArchive)
3. **infer** — `lib/infer.js` → 规则推理 → 输出 decision (anchor: inferDecision, inferRefundOnly, inferRefundReturn)
4. **auto-exec?** — `lib/server/auto-exec-confidence.js` → `shouldAutoExecute()` 判定场景是否达标（≥10次+零差评>15天）
5. **execute** — `lib/jl/approve.js` 或 `lib/jl/reject.js` → 执行审批 (anchor: approveTicket, rejectTicket)

### 重试与重启

- **鲸灵操禁止重试**：`lib/wait.js` 内置 `FORCE_NO_RETRY_DOMAINS = ['scrm.jlsupp.com']`，所有鲸灵行为操作（点击/提交/填写/上传）传 `domain: 'scrm.jlsupp.com'` 后强制 maxRetries=0——报错即停，绝不重试。被动等待（导航/DOM ready）最多重试 1 次（共执行 2 次）。风控信号（HTTP 426/ratelimit/captcha）→ 就地熔断，写入 `data/circuit-breaker.json`（持久化，重启不丢失），需人工 `node cli.js reset-circuit`。
- **采集重试**：collect.js 失败（含 SIGTERM kill → exit code null）最多重试 3 次（`collectRetries` 计数器在 `pipeline.js` processOne），第 3 次失败标记 `simulated` 上报人工。成功进入 `inferring` 时计数器清零。
- **延迟重查**：推理返回 `waitingRescan: true` 时工单进入 `waiting` 状态，距上次推理 ≥ `RESCAN_INTERVAL_HOURS`(4h) 后下次扫描自动重置为 `pending` 重采。
- **代码生效**：修改 `lib/` 下决策逻辑文件后，必须执行 `/aftersales-restart` 重启 server（server 启动时加载模块到内存，不重启新逻辑不生效）。**停旧系统后（2026-06-16）启动只重置残留状态为 pending、不再自动入队 reprocess，纯手动模式**——是否处理由用户手动选择。

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

- 触发条件：`checkLogin()` 返回 `loggedIn: false`（URL 含 login / title 不含快麦ERP-- / 有 `.inner-login-wrapper` 弹窗）
- **Phase 1**：`injectCredentials(targetId)` 直接注入三字段（companyName + userName + password），用 nativeSetter + dispatchEvent('input'/'change')，有硬编码 fallback，可选配 env vars 覆盖
  - ⚠️ Chrome 自动填充在 CDP headless 模式下**完全不可用**（测试确认），已彻底废弃
  - ⚠️ `cdp.clickAt(input)` 会清除输入框内容，禁止在登录页点击任何输入框
- **Phase 2**：点登录按钮 → 等协议弹窗（`.rc-kmui-com-dlg`）→ 点同意（`input.rc-btn-ok`）→ checkLogin 确认
- 熔断：连续 3 次认证失败 → `erp-circuit-breaker.json` state=open，15 分钟冷却后 half_open
- 保活：每 1 小时心跳，fetch 续期 session，失败则 recoverLogin；30 分钟重复 macOS 通知。**（2026-06-16 停旧系统：startErpHeartbeat 函数保留但启动时不再调用，心跳已停。ERP session 超时改靠人工触发操作时的登录恢复兜底）**
- 详见 `docs/ops-tech.md §3.2`

### 鲸灵账号重新登录机制

- 前端：店铺管理页通过 `POST /api/accounts/:num/relogin` 打开登录页，进入 `reloginConfirm` 后必须同时提供「确认保存」和「取消」。
- 后端：`/relogin-confirm` 请求临时登录进程 `/save`；`/relogin-cancel` 请求 `/cancel` 并清理 `../sessions/.relogin-port-<num>`。
- 保存：`../sessions/jl.js --auto-save` 用 `lib/jl-account-config.js` 合并旧账号配置，必须保留 `phone`，否则新登录页无法自动填账号。
- 状态：`hasFile=true + status=unknown` 是「已保存但未扫描验证」，UI 只显示「未扫描」；只有 `expired/error` 或无 session 文件才显示重新登录。

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
| 11 | querySelector 未过滤隐藏元素导致假阴性 | `document.querySelector('.el-input__inner[placeholder="X"]')` 返回 DOM 序第一个元素（可能隐藏 0×0），导致后续 Vue 父链遍历找不到 dataList。必须与其他函数一致：`querySelectorAll` + `getBoundingClientRect` 过滤 `r.width>0 && r.height>0` 再取第一个可见元素。案例：2026-05-04 archive.js READ_DATALIST_JS 读到隐藏的"主商家编码" input → dataList 为空 |
| 12 | DOM 移除 Element UI 弹窗破坏 Vue 内部状态 | `el.parentNode.removeChild(el)` 移除 `.el-dialog__wrapper` 后 Vue 的 `dialogVisible` 仍为 true。下次点击 `a.ml_15` 时 Vue 认为弹窗已打开，跳过打开逻辑 → "子商品弹窗未打开"。必须用 `btn.click()` 触发 Vue close 流程，并轮询等待弹窗从 DOM 消失。案例：2026-05-04 archive.js CLOSE_SUB_DIALOG_JS 用 DOM 移除 → 第二个工单起 subItems 全空 |
| 13 | Chrome 自动填充只触发一次 | Chrome 密码管理器在同一页面生命周期内只自动填充一次（macOS sleep / Chrome 长时间运行后尤为明显）。`recoverLogin` 必须单次尝试而非 3 次循环；仍失败时进 Phase 2 凭据注入而不是重试 reload。单点依赖 Chrome 自动填充是 ERP session 反复失效的根因。 |
| 14 | 熔断中不要重试 ERP | `erp-circuit-breaker.json` state=open 时，`erpNav()` 立即返回错误；冷却 15 分钟后进 half_open 允许一次探测。不要在调用侧再包 retry——熔断是全局保护，本地 retry 会绕过它，导致 session 耗尽还以为在"正常重试"。 |
| 15 | ~~刷新状态/check-session 全链路~~ **已删除（2026-06-16 停旧系统）** | 原 `POST /accounts/refresh-status` + `check-session` op 为每个账号逐个注入检测 = 多账号短时连续登录，踩"禁止同时多 session 登录"风控红线（曾导致 IP 封禁）。**已彻底删除。账号状态改靠扫描工单自然确认 + 店铺管理"重新登录"按钮（单账号人工）。不要重建任何"批量检测账号状态"功能。** |
| 18 | hoursUntilNextScan 为 null 时 .toFixed() 崩溃 | infer.js 中 `inferRefundOnly`（flow-5.3）的 safeToWait 3 条路径在 hoursUntilNextScan 为 null 时直接调用 `.toFixed(1)` → TypeError。**规则：所有 `.toFixed()` 调用前必须 null-check**，用 `val != null ? val.toFixed(1) : '?'`。2026-05-21 修复。注意：flow-5.1 已改为简单阈值（`remaining > REMIND_HOURS`），不涉及 margin 计算。 |
| 19 | 全项目重复代码 → 提取共享函数 | pipeline.js、op-queue.js 各自复制了相同的逻辑（快递单号提取、Mac Reminder 创建）。**规则：发现 ≥2 处相同逻辑时提取共享函数**。2026-05-21：`extractShippedTrackings()` 提取到 `lib/helpers.js`。2026-05-29：`createReminder()` 同理提取到 `lib/helpers.js`，pipeline.js 和 op-queue.js 共用。 |
| 20 | `warnings.includes('X')` 是严格相等而非子串匹配 | `Array.includes()` 做 `===` 比较，不会做子串搜索。意图是判断"已有类似警告" → `some(w => w.includes('X'))`。2026-05-21 修复。 |
| 21 | 鲸灵页面操作报错后自动重试 → IP 封禁 | 2026-05-29 mimo 模型操作鲸灵页面报错后 `retry({ maxRetries: 3 })` 触发风控封禁。**根因：系统默认把"失败"视为技术异常去恢复，没有识别"失败可能是安全信号"。** 修复：`lib/wait.js` 内置域名自动识别强制 maxRetries=0 + 风控信号就地熔断 + `data/circuit-breaker.json` 持久化。规则见 CLAUDE.md "鲸灵页面操作铁律"。 |
| 22 | scan-all 切账号后不写 current-session | 多账号扫描会改变同一个 SCRM tab 的实际账号。成功 `jl.js inject` 后必须写 `data/current-session.json`；否则后续 collect/reprocess 可能误判「已经是目标账号」并跳过注入，读不到工单后错误推进 queue。 |
| 23 | 登录确认态缺少退出路径 | 用户关闭登录页、点取消或 port 文件不存在时，前端必须清理 `reloginConfirm` 并恢复「重新登录」。`unknown + hasFile` 表示未扫描验证，不是失效。保存 session 时必须保留旧账号 `phone`。 |
| 24 | pipeline 历史执行守卫把 skip 误判为"已执行" | `skip` action（工单暂时不可访问）也会写 `executedAt`（自动归档），但它不是真实审批操作。守卫条件 `!!s.executedAt` 会把 skip 误判为"已执行" → 工单恢复后 approve 永久被跳过。**修复**：守卫加 `&& s.decision?.action !== 'skip'`。**规则**：executedAt 语义是"曾被处理"，approve/reject 与 skip 必须分开对待。`pipeline.js:319` |
| 25 | 多弹窗共存时用 `dialogs[length-1]` 取"最后一个可见弹窗" | 套装子品明细误报「未找到子品明细表头」根因：`archive.js` READ_SUB_ITEMS_JS 赌"最后一个可见弹窗就是子商品弹窗"。但 collect 全流程里 ERP tab 可能残留/并发其他可见弹窗（如 `erp-logistics` 的 `trade-detail-dialog` 订单详情弹窗未完全关闭），`dialogs[length-1]` 取到它 → 表头不匹配。**单独跑必成功、生产偶发失败**正是此特征（同工单一成一败）。**修复**：按标题 `子商品信息`（或"含组合比例表头"兜底）精确锁定弹窗，禁止赌最后一个。**规则**：多弹窗页面定位目标弹窗必须用标题/特征匹配，不能用 DOM 序位置。失败时务必 dump 所有可见弹窗标题+class（埋点），别只丢错误字符串。`archive.js:138` |

## PATHS

lib/ai-infer.js
lib/cdp.js
lib/constants.js
lib/helpers.js
lib/infer.js
lib/result.js
lib/targets.js
lib/wait.js
lib/erp/aftersale.js
lib/erp/navigate.js
lib/erp/read-logistics.js
lib/erp/search.js
lib/erp/shop-map.js
lib/jl/add-note.js
lib/jl/alerts.js
lib/jl/approve.js
lib/jl/list.js
lib/jl/logistics.js
lib/jl/navigate.js
lib/jl/read-ticket.js
lib/jl/reject.js
lib/jl/session-filter.js
lib/jl-account-config.js
lib/jl-session-state.js
lib/product/archive.js
lib/product/match.js
lib/server/account-session-status.js
lib/server/auto-exec-confidence.js
lib/server/data.js
lib/server/op-queue.js
lib/server/pipeline.js
lib/server/pipeline-status.js
lib/server/routes.js
lib/server/sse.js
cli.js
server.js
collect.js
scan-all.js
docs/INDEX.md
public/app.js
public/account-relogin-state.js
public/index.html
public/style.css
test/
