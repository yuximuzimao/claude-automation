---
name: aftersales-automation
description: 鲸灵售后自动化——工单扫描、信息采集、规则推理、退款审批/拒绝。CDP 直连 Chrome 操作鲸灵SCRM+快麦ERP。
skill_dir: aftersales-automation
entry: cli.js
---

## DO FIRST

1. **找 CLI 命令** → `cli.js`（18 个命令，JSON 输出 `{success, data/error}`）
2. **找流程逻辑** → `lib/server/op-queue.js`（openAccountFlow → 列表定位 → 执行/采集推理）
3. **找规则/红线** → `docs/INDEX.md`（错误分级、工单路由、已知坑位 §6）
4. **不要直接读 `routes.js`**——它是 Express 薄层，业务逻辑在 `lib/` 下
5. **ERP 操作串行**——所有 ERP 命令用 `&&` 串行，禁止并行

## ENTRY MAP

| 文件 | 作用 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，18 个命令的路由分发 | 需要了解可用命令或新增命令时 |
| `server.js` | Express 服务（port 3457），队列管理 + Web 面板 + 定时扫描调度。定时扫描已恢复，走 opQueue scan 新路径并遵守 scanEnabled；legacy scan-all 不作为当前前端/A1处理入口 | 改 API/队列/定时任务时 |
| `lib/infer.js` | 规则推理引擎，主入口 `inferDecision()` | 改决策逻辑/文案时 |
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
| `lib/jl/login-state.js` | **安全注入判据（2026-06-17）**——`judgeLoginState`（三条件登录态：店铺名/商家登录/自动注册）+`matchShopName`/`shopKeyword`（note 取 `-` 前核心词与页面工商全称子串匹配）+`READ_LOGIN_STATE_JS` | 改登录态判定/店铺名匹配时 |
| `lib/jl/open-account-flow.js` | **A2 安全打开账号编排（2026-06-17）**——`openAccountFlow`/`resolveJlTab`/`decideOpenAccountAction`，先过 05/06 鲲灵 tab 数量门，再读态→复用(匹配)/清cookie+注入(未登录或错号)/异常停(未知)。注入前必须 `success===true && verified===true`，并把已解析/已清理的 `targetId` 传给 04。**已登录目标账号禁止注入；复用 tab 禁止 navigate/reload；错号不退出登录(破坏性)改清cookie** | 改打开后台/安全注入流程时 |
| `scripts/jl-steps/01-open-login.js` | 原子步：打开 login 页（新开标签直达，不注入不导航现有 tab） | 改打开页逻辑时 |
| `scripts/jl-steps/02-read-shop-name.js` | 原子步：读登录态（等8s+三条件判据，退出坐标常量 1358,28 / 1328,244） | 改登录态读取时 |
| `scripts/jl-steps/03-logout.js` | 原子步：退出登录。**⚠️已停用(2026-06-17)**——鲸灵退出是破坏性操作会让原账号服务端session失效，flow 不再调用，改用 07 清cookie。文件保留仅供退出坐标常量参考 | 一般不用 |
| `scripts/jl-steps/04-inject.js` | 原子步：注入账号(调 jl.js inject)+等8s+在显式 `targetId` 上固定导航售后列表+等8s+店铺名关键字匹配验证；CLI 未传 targetId 时只接受唯一鲸灵 tab，多个则报错；禁止 reload 继承旧详情 URL | 改注入验证时 |
| `scripts/jl-steps/05-count-jl-tabs.js` | 原子步：只读统计鲲灵 tab 数量，过滤 `scrm.jlsupp.com` page target | 改打开后台 tab 数量门时 |
| `scripts/jl-steps/06-close-extra-jl-tabs.js` | 原子步：关闭多余鲲灵 tab，只保留第一个；关闭失败即停不重试 | 改打开后台 tab 数量门时 |
| `scripts/jl-steps/07-clear-jl-data.js` | **原子步：注入前清场**——清当前 tab 全部 jlsupp 子域 cookie/storage，随后二次读取确认 `JSESSIONID/_us` 全域清零；只有 `verified:true` 才允许继续。WAF/设备 Cookie 重生不算失败，只清 jlsupp 不碰 ERP | 改注入前清理逻辑时 |
| `scripts/jl-steps/open-account.js` | A2 编排 CLI 包装（`node scripts/jl-steps/open-account.js <num>`），op-queue execOpenAccount 调它 | 改打开后台入口时 |
| `scripts/jl-steps/08-click-after-sale-menu.js` | **A1 原子步：真实鼠标点击左侧「售后工单」菜单**；即使当前已在列表页也不跳过；只进列表不排序不处理 | 改 A1 列表入口时 |
| `scripts/jl-steps/09-select-overdue-sort.js` | **A1 原子步：真实鼠标选择「按逾期时间最近排序」**；不主动刷新、不点击工单 | 改 A1 排序动作时 |
| `scripts/jl-steps/10-read-urgent-after-sale-list.js` | **A1 原子步：读取 48 小时内工单**；抓取数据可用 DOM，分页用真实鼠标点下一页，遇到第一条 >48h 早停 | 改 A1 列表读取/分页/时效判断时 |
| `scripts/jl-steps/11-prepare-after-sale-list.js` | **A1 列表准备编排**：对指定 targetId 固定导航售后列表→检测「售后工单」+「待商家处理」→09→校验排序值+时效升序→10；不依赖首页菜单/弹窗，不点击处理按钮 | 串联 A1 列表准备时 |
| `scripts/jl-steps/12-click-work-order-action.js` | **A1 原子步：按指定工单号定位并真实鼠标点击该工单自己的处理按钮**；按钮不在视口则 mouseWheel 滚入，打开后校验新 tab 属于目标工单 | 改 A1 打开指定工单详情时 |
| `scripts/jl-steps/13-open-single-account-work-order.js` | **A1 单账号打开工单编排**：打开账号→准备 48 小时待处理列表→确认目标在列表→只打开目标工单详情 tab；不审批不拒绝，处理完成前不导航首页 | 串联 A1 单账号工单入口时 |
| `scripts/jl-steps/14-process-single-account-fixed-batch.js` | **A1/A2 固定清单逐单生产编排**：固定 48h 清单，逐单打开详情 tab，target-aware 采集，inferDecision，shouldAutoExecute + executionJournal 安全门，命中后真实 approve/reject，否则写回待确认/等待重查 | 改 fixed-batch 生产链路、自动执行门禁或写回语义时 |
| `lib/jl/target-aware-collector.js` | **当前 A1/A2 生产采集入口**：显式绑定 JL 详情 tab 和 ERP tab；只解决 targetId-aware 采集，不替代原系统持久化/状态流转 | 与步骤 14 和后端入口一起审阅 |
| `lib/server/auto-execution-journal.js` | **自动执行审计风险层**：生产自动执行前置安全门，记录 reserve/page_action_started/page_action_succeeded/auto_executed，防重复执行并 fail-closed；不得作为自动重试助手 | 审阅自动执行异常、journal gate 或人工恢复时 |
| `lib/server/auto-execution-recovery.js` | **自动执行中断后的本地状态收口能力**：不是“停止系统后重新启用”。当前没有 routes.js / cli.js / public UI 外部入口；实际处理中断工单通常重新采集推理覆盖旧状态，或用户手动处理后归档。归档只让系统不再处理该工单，不代表系统知道平台真实执行结果 | 未来实现 CLI/API 恢复入口时；不得调用 approve/reject/浏览器操作 |
| `docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md` | 历史 A1 确认计划：只用于追溯固定清单口径和早期门禁；当前生产状态以本 SKILL、README 和 tasks/todo 最新状态为准 | 追溯历史设计时 |
| `lib/jl/approve.js` | 同意退款（处理三层弹窗） | 改审批流程时 |
| `lib/jl/reject.js` | 拒绝退款（含物流截图上传） | 改拒绝流程时 |
| `lib/jl/add-note.js` | 添加内部备注 | 改备注逻辑时 |
| `lib/jl/navigate.js` | 鲸灵页面导航 | 需要跳鲸灵页面时 |
| `lib/jl/logistics.js` | 读鲸灵物流信息 | 查鲸灵侧物流时 |
| `lib/jl/alerts.js` | 鲸灵首页平台提醒采集，按账号缓存 `data/jl-alerts-cache.json`，前端触发条+展开面板展示。**新 A1 完整闭环目标**：仅在账号工单全部处理后调用，沿用 `.scroll-item` DOM 读取且不主动关弹窗。旧停用 `op-queue.js`/`scan-all.js` 仍会列表读完即调用，恢复前必须由第三步接管或删除 | 改平台提醒逻辑时 |
| `lib/jl-session-state.js` | 鲸灵当前账号缓存读写（`data/current-session.json`） | 改多账号扫描、采集注入、op-queue 注入判断时 |
| `lib/jl-account-config.js` | 重新登录保存时合并账号配置，保留 phone/name/note/file | 改店铺管理重登保存逻辑时 |
| `lib/product/match.js` | ERP 商品对应表查询 | 查商品匹配时 |
| `lib/product/archive.js` | ERP 商品档案V2查询 | 查商品档案时 |
| `lib/server/routes.js` | Express API 路由（639行，45 路由） | 改 API 端点时 |
| `lib/server/live-batch-scope.js` | live 三标签批量操作的 account/store + statusScope 解析和候选筛选，防止筛选视角下批量误作用隐藏店铺 | 改批量执行/批量重来作用域时 |
| `lib/server/data.js` | JSON/jsonl 数据持久化 | 改数据读写时 |
| `lib/server/a1-fixed-batch-entry.js` | A1 固定清单后端入口构造和校验：`POST /api/accounts/:num/a1-fixed-batch` 只允许显式单账号入队，固定 48h，忽略前端传入的 thresholdHours / accounts / disableAutoExecute 等可篡改参数；是否自动执行由 Step14 的 shouldAutoExecute + executionJournal 决定 | 改 A1 后端入口或入队参数时 |
| `lib/server/op-queue.js` | 全局操作队列（串行化浏览器操作）。`execExecute`/`execReprocessOne`/`execReinfer` 已全面迁移到 A1 安全链路（openAccountFlow → 列表定位 → 点击处理按钮 → 执行/采集推理），不再走旧 pipeline/collect.js。**紧急停止**：AbortController + 步骤间检查点机制（2026-07-02），前端 🛑 按钮可真正中断运行中操作；详见 `docs/ops-tech.md §8` | 改队列/执行/重新采集/停止逻辑时 |
| `lib/server/account-session-status.js` | 账号 session 状态判定——`getAccountOpenGuard()` 按 ok/unknown/expired/error 决定是否拦截打开后台 | 改打开后台/状态拦截逻辑时 |
| `lib/server/pipeline-status.js` | 扫描终态归类——明确终态 skip 进 auto_executed 而非静默 done | 改终态归档逻辑时 |
| `lib/server/sse.js` | Server-Sent Events 实时推送 | 改前端实时更新时 |
| `lib/server/auto-exec-confidence.js` | 自动执行置信度系统 — 场景指纹+人工反馈驱动 auto 判定 | 查/改自动执行条件时 |
| `public/app.js` | 前端主逻辑 — 8 Tab 渲染、快递行动分类 `isReturnWaitingAction()`、徽章计数、品牌分组、倒计时格式化 | 改前端展示/分类逻辑时 |
| `public/index.html` | 前端 HTML 骨架 — 8 Tab 结构、模版、header 控件 | 改页面结构时 |
| `public/style.css` | 前端样式 — 紧急度颜色、面板布局、响应式 | 改样式时 |
| `../return-inbound/SKILL.md` | 退货入库项目导航地图（跨目录） | 调试/改退货入库 op 时；op-queue 的 `return-inbound` case 调用 `../return-inbound/lib/workflow.js` |

## CORE FLOWS

### 当前 A2 安全编排 / A1 固定清单生产流程

1. `openAccountFlow`：tab 数量门 → 实时店铺匹配 → 复用或清理验证后注入。
2. `11-prepare-after-sale-list.js`：固定导航售后列表 → 页面门禁 → 逾期排序 → 读取 48h 列表。
3. `13-open-single-account-work-order.js`：确认目标工单在 urgent 列表后，精确打开其详情 tab；当前不审批、不拒绝。
4. 步骤 14 是当前固定清单生产入口：首次读取 `<=48h` 清单作为不可变快照；逐单定位、打开详情 tab、采集、推理、自动执行判定、写回原 queue/simulation、关闭详情 tab。前端“处理工单”按钮已接入正式入口；命中 `shouldAutoExecute` 且通过 `executionJournal` 安全门时会真实 approve/reject，未命中则写回 simulated/waiting。自动执行中断后的 recovery 仅有本地状态收口能力，无外部 CLI/API/UI；当前实际处理以重采覆盖或手动处理后归档为主。
5. **执行操作 & 重新采集推理**（2026-06-29 重构）：`execExecute` 和 `execReprocessOne` 已迁移到 A1 安全编排链路，复用与步骤 14 相同的核心函数：
   - `openAccountFlow` → `prepareAfterSaleList`（仅导航+排序，不读全量列表）→ `locateWorkOrderOnFreshList` → `clickWorkOrderAction` → 执行决策（approve/reject/escalate）或 `collectTicketTargetAware` + `inferDecision`。
   - `execReinfer` 直接转调 `execReprocessOne`。
   - 重新采集推理已接入 `shouldAutoExecute` + executionJournal 自动执行链路。`execOpenTicket`（查看工单，2026-07-01 初迁→2026-07-02 完成：统一账号校验+删除 CLI fallback+完整对齐 execExecute 步骤 1-5）、`execOpenAccount`（打开店铺，2026-07-01 已模块化直接调 openAccountFlow）。`execScanAccount`（扫描工单，2026-07-01 已删除——无调用方，新扫描走 execScan → processSingleAccountFixedBatch）。

### 重试与重启

- **鲸灵操作禁止重试**：`lib/wait.js` 内置 `FORCE_NO_RETRY_DOMAINS = ['scrm.jlsupp.com']`，所有鲸灵行为操作（点击/提交/填写/上传）传 `domain: 'scrm.jlsupp.com'` 后强制 maxRetries=0——报错即停，绝不重试。被动等待（导航/DOM ready）最多重试 1 次（共执行 2 次）。风控信号（HTTP 426/ratelimit/captcha）→ 就地熔断，写入 `data/circuit-breaker.json`（持久化，重启不丢失），需人工 `node cli.js reset-circuit`。
- **ERP 订单搜索错误只重搜一次**：`erpSearch()` 逐行核验“平台交易号”包含本次子订单号；首次结果错误只重新执行搜索，总共最多 2 次。第二次仍失败立即报错，不继续物流采集、推理或整张工单流程。
- **延迟重查**：推理返回 `waitingRescan: true` 时工单进入 `waiting`。`scan-finalize` 会按 `lastInferAt` / `collectDoneAt` + `RESCAN_INTERVAL_HOURS` 节流重置为 pending，定时扫描已恢复但仍必须走 op-queue A1 安全路径。
- **代码生效**：修改 `lib/` 下决策逻辑文件后，必须执行 `/aftersales-restart` 重启 server（server 启动时加载模块到内存，不重启新逻辑不生效）。当前定时扫描已恢复并遵守 `scanEnabled`；真实浏览器操作必须经 op-queue 串行。

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
- 取消：点击后立即进入 `reloginCancelling`，禁用确认/取消并显示「取消中...」；只有后端成功返回才清理 `reloginConfirm`、恢复「重新登录」，失败则保留确认态供重试。不要用固定秒数判断，以按钮恢复为完成信号。
- 保存：`../sessions/jl.js --auto-save` 用 `lib/jl-account-config.js` 合并旧账号配置，必须保留 `phone`，否则新登录页无法自动填账号。
- 状态：`hasFile=true + status=unknown` 是「已保存但未单账号验证」，UI 只显示「未扫描」、不显示重新登录。验证走安全打开账号或未来新 A1 单账号流程，禁止恢复批量刷新状态。
- 按钮可见性（`public/account-relogin-state.js` `shouldShowReloginButton` + `public/app.js` 渲染，2026-06-22）：
  - **重新登录按钮**：`ok`/`expired`/`error` 或无 session 文件都显示；仅 `unknown`（未扫描）不显示。正常账号也能随时手动重登。
  - **打开店铺后台按钮**：只要 `hasFile=true` 就常显，**不再因 `expired/error` 隐藏**（旧逻辑会把误标异常的账号锁死）。
  - **异常二次确认**：`status` 为 `expired/error` 时点「打开店铺后台」先 `confirm` 人工确认，确认后请求体带 `confirmed:true`；后端 `/accounts/:num/open` 收到 `confirmed:true` 才放行被 `getAccountOpenGuard` 拦下的异常账号（否则仍 409，附 `needConfirm:true`）。

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
| 15 | ~~刷新状态/check-session 全链路~~ **已删除（2026-06-16 停旧系统）** | 原批量检测会短时连续登录多个账号。账号状态只允许通过店铺管理“打开后台”的安全编排或未来新 A1 单账号流程确认；不要重建批量刷新状态功能。 |
| 18 | hoursUntilNextScan 为 null 时 .toFixed() 崩溃 | infer.js 中 `inferRefundOnly`（flow-5.3）的 safeToWait 3 条路径在 hoursUntilNextScan 为 null 时直接调用 `.toFixed(1)` → TypeError。**规则：所有 `.toFixed()` 调用前必须 null-check**，用 `val != null ? val.toFixed(1) : '?'`。2026-05-21 修复。注意：flow-5.1 已改为简单阈值（`remaining > REMIND_HOURS`），不涉及 margin 计算。 |
| 19 | 全项目重复代码 → 提取共享函数 | pipeline.js、op-queue.js 各自复制了相同的逻辑（快递单号提取、Mac Reminder 创建）。**规则：发现 ≥2 处相同逻辑时提取共享函数**。2026-05-21：`extractShippedTrackings()` 提取到 `lib/helpers.js`。2026-05-29：`createReminder()` 同理提取到 `lib/helpers.js`，pipeline.js 和 op-queue.js 共用。 |
| 20 | `warnings.includes('X')` 是严格相等而非子串匹配 | `Array.includes()` 做 `===` 比较，不会做子串搜索。意图是判断"已有类似警告" → `some(w => w.includes('X'))`。2026-05-21 修复。 |
| 21 | 鲸灵页面操作报错后自动重试 → IP 封禁 | 2026-05-29 mimo 模型操作鲸灵页面报错后 `retry({ maxRetries: 3 })` 触发风控封禁。**根因：系统默认把"失败"视为技术异常去恢复，没有识别"失败可能是安全信号"。** 修复：`lib/wait.js` 内置域名自动识别强制 maxRetries=0 + 风控信号就地熔断 + `data/circuit-breaker.json` 持久化。规则见 CLAUDE.md "鲸灵页面操作铁律"。 |
| 22 | scan-all 切账号后不写 current-session | 多账号扫描会改变同一个 SCRM tab 的实际账号。成功 `jl.js inject` 后必须写 `data/current-session.json`；否则后续 collect/reprocess 可能误判「已经是目标账号」并跳过注入，读不到工单后错误推进 queue。 |
| 23 | 登录确认态过早退出或没有退出路径 | 点取消后必须先进入 `reloginCancelling` 并锁住按钮，等 `/relogin-cancel` 成功后再清理 `reloginConfirm`、恢复「重新登录」；失败保留确认态。提前恢复会让用户再次启动登录，旧进程失去可追踪入口。登录页关闭或 port 文件不存在时也要退出确认态，不能永久卡住。`unknown + hasFile` 表示未扫描验证，不是失效；保存 session 时必须保留旧账号 `phone`。 |
| 24 | pipeline 历史执行守卫把 skip 误判为"已执行" | `skip` action（工单暂时不可访问）也会写 `executedAt`（自动归档），但它不是真实审批操作。守卫条件 `!!s.executedAt` 会把 skip 误判为"已执行" → 工单恢复后 approve 永久被跳过。**修复**：守卫加 `&& s.decision?.action !== 'skip'`。**规则**：executedAt 语义是"曾被处理"，approve/reject 与 skip 必须分开对待。`pipeline.js:319` |
| 25 | 多弹窗共存时用 `dialogs[length-1]` 取"最后一个可见弹窗" | 套装子品明细误报「未找到子品明细表头」根因：`archive.js` READ_SUB_ITEMS_JS 赌"最后一个可见弹窗就是子商品弹窗"。但 collect 全流程里 ERP tab 可能残留/并发其他可见弹窗（如 `erp-logistics` 的 `trade-detail-dialog` 订单详情弹窗未完全关闭），`dialogs[length-1]` 取到它 → 表头不匹配。**单独跑必成功、生产偶发失败**正是此特征（同工单一成一败）。**修复**：按标题 `子商品信息`（或"含组合比例表头"兜底）精确锁定弹窗，禁止赌最后一个。**规则**：多弹窗页面定位目标弹窗必须用标题/特征匹配，不能用 DOM 序位置。失败时务必 dump 所有可见弹窗标题+class（埋点），别只丢错误字符串。`archive.js:138` |
| 26 | 单次操作报错就把账号标异常，且异常态同时隐藏按钮+后端拦截 → 账号被双重锁死 | 账号12 切换时网络抖动报一次错被标 `error`。旧逻辑下 `error/expired` 既隐藏「打开店铺后台」按钮，后端 `/open` 又直接 409 → 一个其实正常的账号无任何自助恢复路径。**根因**：把"单次失败"等同于"账号失效"，且没留人工兜底通道。**修复（2026-06-22）**：打开后台按钮只要有 session 文件就常显；异常态点击先 `confirm`，确认后带 `confirmed:true` 让后端放行。**规则**：状态标记可降级提示，但不能既挡 UI 又挡后端把入口彻底封死，高风险入口要留「人工确认放行」通道。`routes.js:747` `app.js:openAccountStore` |
| 27 | CDP `Input.dispatchMouseEvent` 在后台标签页卡死超时 | 流程中 `clickWorkOrderAction` 打开详情新 tab 后 Chrome 焦点切走 → 列表 tab 失焦 → 下次 `dispatchMouseEvent` 永不返回。**修复（2026-06-29）**：`cdp.dispatchMouseEvent()` 每次调用前自动 `activateTarget`。所有调用方从 `cdp.cdpCall(target, 'Input.dispatchMouseEvent', ...)` 迁移到 `cdp.dispatchMouseEvent(target, ...)`。 |
| 28 | ERP shop-map 店铺名与实际页面不一致 | SHOP_MAP 配 `erpShop: '16广州茗瑞'` 但 ERP 页面标签为 `广州茗瑞`（无"16"前缀）→ `makeCheckShopJS` 的 `tag.includes` 永远 false。第一条工单（百浩，无前缀问题）通过后残留状态掩盖了后续工单（茗瑞）的失败。**修复（2026-06-30）**：SHOP_MAP erpShop 对齐 ERP 实际标签（去"16"前缀）。 |
| 29 | `inferDecision` 第二参数传错对象 | `processOpenedDetail` (14-step) 传 `context.ticket`（原始扫描 ticket，只有 totalHours/type/workOrderNum）给 `inferDecision` 作为 `queueItem` → `deadlineAt`/`urgency`/`hoursUntilNextScan` 全空 → `remainingHours=null` → safeToWait/margin 检查被跳过 → 拦截件误入 reject 而非 waitingRescan。**规则**：`inferDecision(sim, queueItem)` 的第二参数必须是完整 queueItem（含 type/deadlineAt/urgency/hoursUntilNextScan）。`hoursUntilNextScan` 不在 queue item 持久化字段中，需调用 `getHoursUntilNextScan()` 动态追加。 |
| 30 | `readTicket` 退货物流区块异步加载 | 详情页 verifyJS 只等「售后类型」出现，但「退货物流信息」区域异步渲染 → `bodyText` 抓取时退货单号尚未出现 → `returnTracking` 为空 → `inferRefundReturn` 误入「无快递单号→超期无理由退货」分支。**修复（2026-06-30）**：`READ_ORDER_INFO_JS` 前轮询等「退货物流单号/退货物流信息」出现（最多 5s）。 |
| 31 | RETURN_KEYWORDS 缺少「到达商家仓库」 | 圆通退回件物流写「您的包裹即将到达商家仓库，正在验收中」不写「退回」→ 赠品实际已退回但关键词未命中 → 误判为在途。**修复（2026-06-29）**：新增 `到达商家仓库`。`入站` 被驳回（outbound 配送也出现"入站"导致误判）。 |

## PATHS

> Legacy 注意：`collect.js`、`scan-all.js`、`lib/server/pipeline.js` 文件仍保留，但不再作为 A1/前端采集入口；当前扫描/重采/执行入口走 `lib/server/op-queue.js` 的 A1 安全链路。只有明确修复 legacy 行为或引用历史 schema 时才读这些旧文件。

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
lib/jl/login-state.js
lib/jl/open-account-flow.js
lib/jl/target-aware-collector.js
lib/jl-account-config.js
lib/jl-session-state.js
lib/product/archive.js
lib/product/match.js
lib/server/account-session-status.js
lib/server/auto-exec-confidence.js
lib/server/auto-execution-journal.js
lib/server/auto-execution-recovery.js
lib/server/a1-fixed-batch-entry.js
lib/server/data.js
lib/server/live-batch-scope.js
lib/server/op-queue.js
lib/server/pipeline.js
lib/server/pipeline-status.js
lib/server/routes.js
lib/server/sse.js
cli.js
server.js
collect.js
scan-all.js
scripts/jl-steps/01-open-login.js
scripts/jl-steps/02-read-shop-name.js
scripts/jl-steps/03-logout.js
scripts/jl-steps/04-inject.js
scripts/jl-steps/05-count-jl-tabs.js
scripts/jl-steps/06-close-extra-jl-tabs.js
scripts/jl-steps/07-clear-jl-data.js
scripts/jl-steps/open-account.js
scripts/jl-steps/08-click-after-sale-menu.js
scripts/jl-steps/09-select-overdue-sort.js
scripts/jl-steps/10-read-urgent-after-sale-list.js
scripts/jl-steps/11-prepare-after-sale-list.js
scripts/jl-steps/12-click-work-order-action.js
scripts/jl-steps/13-open-single-account-work-order.js
scripts/jl-steps/14-process-single-account-fixed-batch.js
docs/INDEX.md
docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md
public/app.js
public/account-relogin-state.js
public/index.html
public/style.css
test/
