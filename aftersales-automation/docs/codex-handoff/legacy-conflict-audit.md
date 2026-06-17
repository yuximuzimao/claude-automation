# 售后系统旧路径冲突审计报告

日期：2026-06-17  
执行人：Codex  
范围：静态扫描 `/Users/chat/claude/aftersales-automation`、`/Users/chat/claude/sessions/jl.js`、根 `docs/HANDOFF.md`、`/Users/chat/claude/.claude/skills/aftersales-restart/SKILL.md`。未真机、未重启、未读取或写入 `data/`。

## 对照基准

1. 停旧系统：server 启动不再自动扫描、不再 ERP 心跳、不再启动自动入队处理，纯手动模式。
2. A2 安全注入：打开后台入口必须先过 tab 数量门，已登录目标账号禁止重复注入，复用现有 tab 禁止 navigate/reload。
3. 重启机制：LaunchAgent `com.heizong.aftersale-server` 托管 + `server.js` 单实例锁，重启统一用 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`。

## 冲突点清单

| # | file:line | 现状 | 与新计划的冲突 | 建议修正方向 | 风险 | 是否疑似死代码 |
|---|---|---|---|---|---|---|
| 1 | `tasks/lessons.md:307` | lesson #55 仍以 `kill` 后 launchd 自动拉起作为重启观察口径，并强调看启动时间/日志段。 | 新重启口径应显式用 `launchctl kickstart -k`，不是人工 kill 后等待 KeepAlive。 | 后续清理 lesson #55：保留历史事故，新增“当前唯一重启入口是 kickstart”。 | 中 | 否 |
| 2 | `tasks/lessons.md:237` | “launchctl restart 后检查暂停状态”未说明当前 label 与 `kickstart -k`。 | 容易让后人使用模糊的 launchctl restart/stop/start，而不是指定 LaunchAgent kickstart。 | 改为引用 `/aftersales-restart` 的 kickstart 命令。 | 低 | 否 |
| 3 | `server.js:90` | `/api/skip-next-scan` 仍存在并设置 `skipNextScan`。 | 定时扫描已停，这个 API 不再有实际调度对象；保留会误导为“还有下次自动扫描”。 | 第三步重建前隐藏或标注为 legacy no-op；若不再需要则删除。 | 低 | 是 |
| 4 | `server.js:98` | `runAutoScan()` 保留旧多账号 `scan-account` + `scan-finalize` 入队逻辑。 | 旧路径会逐账号注入并最终自动入队 reprocess，正是停旧系统要切断的行为。当前启动未调用，但函数本体仍是危险模板。 | 第三步重建时替换为 A2/A1 安全编排；重建前保持不可达并加测试防止被重新调用。 | 中 | 是 |
| 5 | `server.js:129` | `scheduleNextScan()` 保留 8/12/16/20 定时框架，内部调用 `runAutoScan()`。 | 一旦恢复调用，就会重新拉起旧自动扫描。 | 保留需加“禁止直接恢复调用”的注释或移到新计划文档；重建时改接新安全扫描闭环。 | 中 | 是 |
| 6 | `server.js:180` | server 启动时仍自动 `checkLogin()`，未登录则 `recoverLogin()`。 | 停旧系统明确停 ERP 心跳，但这里仍是启动期 ERP 自动恢复行为；虽非心跳，仍会在重启时自动操作 ERP 登录。 | 由 Claude Code 决策是否保留为 ERP 启动闸门；若保留，文档需明确“不属于心跳，不触碰鲸灵”。 | 中 | 否 |
| 7 | `lib/server/routes.js:380` | `POST /api/scan` 仍可直接入队 `scan`。 | 前端按钮已摘除，但 API 仍能触发旧 `scan-all.js` 多账号直接注入。 | 在第三步完成前增加服务端禁用门或安全确认；之后改接新 A1 安全扫描。 | 高 | 否 |
| 8 | `lib/server/op-queue.js:397` | `execScan()` 仍 spawn `scan-all.js`，扫描后 lines 462-468 自动入队 `reprocess-one`。 | 与“扫描/自动入队停旧”冲突；直接 API 调用即可触发采集推理链路。 | 拆分扫描与处理：扫描只读并报告，自动 reprocess 需显式人工触发且接安全注入。 | 高 | 否 |
| 9 | `lib/server/routes.js:164` | `POST /queue/batch-reprocess` 仍批量重置未完成 live 工单并入队 `reprocess-one`。 | 前端按钮摘除但 API 活着；会批量触发采集路径，绕过 A2 登录态判据。 | 第三步前禁用批量入口；重建后只允许安全单账号/单工单串行路径。 | 高 | 否 |
| 10 | `lib/server/routes.js:132` | `POST /simulations/batch-execute` 仍批量入队 execute。 | 前端按钮摘除但 API 活着；可能批量执行 approve/reject，且执行前注入只看缓存。 | 第三步前禁用批量执行；恢复时必须接登录态判据和人工确认门。 | 高 | 否 |
| 11 | `lib/constants.js:76` + `lib/server/pipeline.js:186` | `getHoursUntilNextScan()` 仍按固定扫描点计算，并传给推理。 | 停旧系统后不存在“下次自动扫描”，flow-5.3 安全边际会基于虚假的自动扫描周期做等待/拒绝判断。 | 纯手动模式下传 `null` 或显式“无自动扫描”；等待策略需改为人工/计划扫描时间。 | 高 | 否 |
| 12 | `public/app.js:290` | `batchExecute()` 前端函数仍存在。 | DOM 入口已注释，函数本体仍可被控制台调用并打到活 API。 | 第三步前删除或加运行期禁用提示；保留则必须后端也禁用。 | 低 | 是 |
| 13 | `public/app.js:305` | `batchReprocess()` 前端函数仍存在。 | 可从控制台触发旧批量 reprocess API。 | 同上，后端必须兜底禁用。 | 低 | 是 |
| 14 | `public/app.js:393` | `scanTickets()` 前端函数仍存在。 | 可从控制台触发旧扫描 API。 | 同上。 | 低 | 是 |
| 15 | `public/index.html:52` | 扫描/批量执行/批量重来按钮被 HTML 注释包住。 | 入口确实不可见，但注释内仍保留可复制的旧按钮和“自动处理”语义。 | 保留需写明“不可恢复使用，等待新路径”；或删除注释内按钮。 | 低 | 是 |
| 16 | `scan-all.js:32` | 多账号扫描每个账号直接 `jl.js inject`。 | 绕过 tab 数量门、登录态判定、已登录目标账号复用；会重复注入和累积多 tab 风险。 | A1 重建时改为安全编排；当前不要从 API/CLI 调用。 | 高 | 否 |
| 17 | `collect.js:49` | 采集前按 `current-session.json` 10 分钟缓存判断，否则直接 `jl.js inject`。 | 缓存不是实时 DOM 登录态；若 Chrome 实际已是目标账号但缓存过期，会重复注入。 | 用 `login-state.js` 读实时店铺名，匹配则复用；错号才走退出+注入。 | 高 | 否 |
| 18 | `lib/server/op-queue.js:271` | `execScanAccount()` 直接 `jl.js inject`。 | 旧逐账号扫描路径绕过 A2；当前仅由未调用的 `runAutoScan()` 关联。 | 若第三步不用该函数则删除；若复用必须接安全编排。 | 中 | 是 |
| 19 | `lib/server/pipeline.js:98` | 自动执行 approve 前只用 `current-session.json` 判同账号，否则直接 inject。 | 自动执行是真实写操作，缺少实时登录态复用判据；缓存错/过期会重复注入或注入错 tab。 | 自动执行恢复前必须接 A2 判据；建议暂时禁用自动执行写操作。 | 高 | 否 |
| 20 | `lib/server/op-queue.js:546` | 手动/批量 execute 前只用缓存判同账号，否则直接 inject。 | approve/reject 写操作前绕过 A2；已登录目标账号但缓存过期会重复注入。 | execute 前统一调用安全账号确保函数：读态匹配复用，错号退出注入。 | 高 | 否 |
| 21 | `lib/server/op-queue.js:633` | open-ticket 每次直接 inject，且未 `saveSessionState()`。 | 查看工单也会重复注入；且缓存不更新，后续路径可能继续误判。 | 改为安全复用/确保账号；纯查看也要先读态，不应无条件注入。 | 中 | 否 |
| 22 | `scripts/jl-steps/04-inject.js:57` | 04 原子脚本可独立直接 inject。 | 在 A2 编排内是合法“已判定需注入”的步骤；但独立运行会违反 lesson #56。 | 文档/CLI 输出强调“只能由 open-account-flow 在未登录/错号退出后调用”；或加可选 precheck。 | 中 | 否 |
| 23 | `cli.js:50` | `reload-jl` 命令对现有鲸灵 tab 直接 navigate 到售后列表。 | A2 复用 tab 禁止 navigate/reload；该命令若被人工或旧脚本调用会把当前后台页强行导走。 | 若无调用方则删除；若保留，仅允许旧 A1 扫描内部使用且需显式警告。 | 中 | 是 |
| 24 | `lib/jl/list.js:141` | 列表读取会把现有鲸灵 tab navigate 到 after-sale-list。 | 对扫描场景合理，但若从“打开后台复用 tab”状态误调用，会破坏 A2 不导航原则。 | 新 A1 扫描应独立声明会导航工单页；不要与 A2 打开后台共享复用语义。 | 高 | 否 |
| 25 | `lib/jl/alerts.js:21` | 扫描后提醒抓取会把当前鲸灵 tab navigate 到首页。 | 会改变现有 tab 页面；若扫描路径尚未安全重建，会叠加额外导航行为。 | A1 重建时明确“读提醒”是否需要单独 tab 或用户许可；旧扫描期间不要触发。 | 中 | 否 |
| 26 | `docs/HANDOFF.md:23` | “A2 安全注入路径（代码+单测完成，部分真机验证，未提交）”。 | 当前 git log 已有 `93cf0e6`、`7795cf5`，未提交描述过时。 | 更新 HANDOFF 为“已提交，待真机端到端验证/重启加载”。 | 低 | 否 |
| 27 | `docs/ops-tech.md:141` | 重新登录后“必须通过后续扫描或刷新状态验证成 ok”。 | 刷新状态全链路已删除，扫描也属于停旧旧路径；文档会诱导恢复风险动作。 | 改为“打开后台安全编排/单账号人工验证”或新 A1 验证路径。 | 中 | 否 |
| 28 | `docs/ops-tech.md:217` | ERP 保活心跳描述为现行机制。 | `startErpHeartbeat()` 已停用；文档未标注停旧系统状态。 | 标注“历史机制，2026-06-16 起不启动”。 | 中 | 否 |
| 29 | `docs/ops-tech.md:379` | “任何成功 `jl.js inject` 的路径都要写 current-session”。 | 新计划不应鼓励新增直接 inject 路径；应改为“任何安全编排确认实际账号变化后写缓存”。 | 调整为 A2 判据口径，弱化直接 inject。 | 中 | 否 |
| 30 | `SKILL.md:83` | 延迟重查写“距上次推理 >= 4h 后下次扫描自动重置”。 | 停旧系统后没有下次自动扫描；等待工单不会靠定时扫描自然重置。 | 改为“手动扫描/新 A1 扫描触发时可重置”。 | 中 | 否 |
| 31 | `public/app.js:501` | 空状态提示“点击「扫描工单」检测新工单”。 | 扫描按钮已摘除，提示与 UI/停旧状态不一致。 | 改成“暂无待确认工单”，或提示等待新扫描入口。 | 低 | 否 |
| 32 | `tasks/todo.md:27` | A2.4 仍写“打开店铺后台按钮（调用 jl <num> 打开鲸灵）”。 | 当前已改为 `/api/accounts/:num/open` → op-queue → `open-account-flow.js`。 | 更新 todo 历史说明，避免误以为仍调用 `jl <num>`。 | 低 | 否 |
| 33 | `tasks/lessons.md:326` | lesson #57 仍称 `jl.js inject` 第 357 行主动 `Page.navigate`。 | 当前 `sessions/jl.js:357` 已是日志输出，inject 已去导航；lesson 已过时。 | 改为历史记录：旧版曾主动导航，当前已解耦；A1 列表导航由 `cli.js list`/`lib/jl/list.js` 承担。 | 低 | 否 |
| 34 | `lib/erp/navigate.js:10` | 文件头仍把“保活心跳（server.js，1h fetch + checkLogin）”列为调用方。 | ERP 心跳停用后，入口地图不应把它描述为现行调用方。 | 标注 stopped-2026-06-16 或移入历史说明。 | 低 | 否 |

## 六维度结论

### 1. 重启假设过时

本轮已修 `/Users/chat/claude/.claude/skills/aftersales-restart/SKILL.md`，将 `kill` + `nohup` 改为 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`，验证改为 launchctl PID 变化、3457 监听、`/api/queue` OK。`tasks/lessons.md` #34 已补充 LaunchAgent 接管后的 kickstart 口径。

剩余冲突主要是历史 lessons 中仍有 kill/launchctl restart 的旧表达（#1、#2）。

### 2. 自动行为残留

启动自动扫描、ERP 心跳、启动自动 reprocess 调用点已注释停用；但旧函数、旧 API 和后端批量入口仍存在。最关键的是 `/api/scan`、`batch-reprocess`、`batch-execute` 仍可绕过前端直接调用，且 `execScan()` 会自动入队 reprocess。另有 `getHoursUntilNextScan()` 继续影响 flow-5.3 判断，这是停旧后最容易造成业务判断偏差的残留。

### 3. 绕过 A2 安全编排的直接注入

`open-account` 已接 `open-account-flow.js`，符合 A2。其余扫描、采集、自动执行、手动执行、查看工单仍存在直接 `jl.js inject` 路径，且多数只依赖 `current-session.json` 缓存，不读实时登录态。高风险点是 `scan-all.js`、`collect.js`、`pipeline.js:autoExecuteApprove()`、`op-queue.js:execExecute()`。

### 4. 复用 tab 禁导航违反点

A2 编排本身未发现对复用 tab 的 navigate/reload；`01-open-login` 是新开 tab，不算冲突。冲突集中在旧扫描/列表/提醒/`reload-jl`：它们会对现有鲸灵 tab 导航到列表或首页。新计划需要把“打开后台 A2”和“扫描 A1 会导航工单页”明确隔离。

### 5. 已登录目标账号重复注入隐患

除 `open-account-flow.js` 外，直接注入路径都没有“读实时店铺名并匹配目标账号则跳过”的保护。`collect.js`、`pipeline.js`、`op-queue.js` 的缓存判断只能证明“上次写缓存时认为是该账号”，不能证明当前 Chrome tab 仍是该账号。

### 6. 文档/地图与现状不一致

`docs/HANDOFF.md`、`docs/ops-tech.md`、`SKILL.md`、`tasks/todo.md`、`tasks/lessons.md` 均有过时描述。最需要优先改的是会误导操作的文档：`docs/ops-tech.md` 的刷新状态/扫描验证口径、ERP 心跳口径，以及 `SKILL.md` 的“下次扫描自动重置”。

## 风险计数

- 高风险：10
- 中风险：15
- 低风险：9
- 合计：34

## 审计偏离

- 未执行 `node cli.js list`：项目 CLAUDE.md 要求启动读实时工单，但本任务铁律是“不真机、不重启、不碰 data”，且该命令会访问鲸灵实时页面，故本轮用静态审计替代。
- 未修业务代码：任务 B 明确只标记，不改业务代码。
