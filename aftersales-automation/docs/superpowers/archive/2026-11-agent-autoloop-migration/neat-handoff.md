# Agent Autoloop 接入售后操作队列 — NEAT 交接

**归档日期：** 2026-11-05（原始只读审查基线）

**状态更新（2026-11-06）：** 本文件继续保存 2026-11-05 售后现状与 Autoloop 源码只读审查证据。后续已完成第 1 阶段“适配层”和第 2 阶段“统一桌面调度运行模型”的架构讨论；未安装 Autoloop，未改生产代码，未改变现有运行方式。后续确认的跨项目职责边界和更新后的阶段顺序，以工作区归档 `docs/archive/2026-11-06-autoloop-adapter-runtime-design/README.md` 为准。

**下一会话入口：** 从第 3 阶段“任务入口与触发源映射”开始；本文件作为售后现状、原有入口和安全机制的只读审查参考，不再从第 1 项重新讨论。

## 0. 本次归档的目的

本文件是后续逐项迁移的完整交接，不是实施授权，也不是当前生效的售后规则。

用户要求的推进方式：

1. 先完成现有售后项目审查，以及 Autoloop 源码研究和功能对照。
2. 先 NEAT 归档，再开始正式讨论。
3. 每个会话只讨论一个编号：解释现状和实际逻辑 → 用户确认方案 → 实施 → 反向检查 → 确认完成 → 下一项。
4. 不要求所有实施都交给 Codex。简单、范围明确的工作可由 ChatGPT 直接完成；Codex 留给独立反查、复杂代码验证和对抗性审查，以节省额度。

本次已完成前两步，并将所有映射、风险和待决事项保存在本文件。后续会话不应重新从头审查，也不应把本文件中的“候选方案”误认为已经确认或实施。

## 1. 用户已确认的迁移方向

### 1.1 售后项目的方向更新

2026-11-04 的工作区 Autoloop 讨论曾倾向于“Autoloop 作为现有 op-queue 外层调度器”。2026-11-05 用户明确更新方向：

- 采用 Autoloop 的调度结构，整体改造现有售后操作队列。
- 页面按钮、手动操作、定时扫描等现有入口都要纳入统一调度。
- 不是只给现有 op-queue 外面再套一层长期并存的第二队列。
- 售后原有业务规则、自动执行授权、执行前事实核验、页面操作边界和数据记录仍由售后项目负责。
- Autoloop 的失联、停止、恢复、任务接管逻辑必须按售后安全要求局部调整。
- **只要不能确认旧任务已经失去操作能力，就不得释放桌面资源给下一项任务。** 状态不明时宁可继续占用、报警和等待人工确认，也不能猜测任务已经结束。

本次新方向覆盖并取代 11 月 4 日“仅做外层调度”的旧建议；旧归档保留作历史，不再作为本轮迁移决策依据。

### 1.2 本轮范围与明确排除

本轮重点是 aftersales-automation 的实际队列、入口和调度迁移。

- QQ/微信农场、群聊分析：只设计未来可接入的通用任务接口原则，不做具体迁移审查和实施。
- 不搭建云端平台，不接入 Webhook、飞书通知、模型路由或完整的统一业务规则引擎。
- 不把退款、拒绝、入库等业务决策搬进 Autoloop rules.json。
- 不改变现有自动执行授权，不扩大自动同意范围，不新增自动拒绝。
- 不安装 Autoloop，不升级售后服务的 Node 运行环境，不改 LaunchAgent，不改生产入口。
- 不恢复 legacy scan-all.js、collect.js、pipeline.js 作为正式执行入口。

## 2. 审查基线

### 2.1 售后项目

审查对象：工作区内 aftersales-automation，以及其调用的 return-inbound 模块。

已检查的主要入口和资料：

- SKILL.md、CLAUDE.md、tasks/todo.md、docs/INDEX.md。
- docs/automation-policy.md、docs/ops-queue.md、docs/ops-testing.md、docs/ops-tech.md。
- server.js、lib/server/op-queue.js、lib/server/routes.js、lib/server/a1-fixed-batch-entry.js。
- lib/server/data.js、lib/server/auto-execution-journal.js、lib/server/auto-execution-recovery.js。
- scripts/jl-steps/14-process-single-account-fixed-batch.js。
- public/app.js、lib/server/sse.js、lib/server/scan-hud.js、scripts/scan-status-hud.js。
- wanwu/ 调度与巡检模块。
- return-inbound/lib/workflow.js 及售后队列中的调用方式。
- cli.js 和 sessions/jl.js 的入口形态。

本次为静态审查，没有读取真实工单，没有打开鲸灵或 ERP，没有执行扫描、审批、拒绝或入库操作，也没有运行生产服务。

### 2.2 Autoloop 源码版本

仓库：KKKKhazix/agent-autoloop

仓库地址：https://github.com/KKKKhazix/agent-autoloop

本次对照的版本：

- main：eb0c2eba3f0e397b6037940f40e0f36060df83c4
- 最新可见 release：v1.2.0，提交 196c12a221548f505403231df49ecd71e1cdfb6a
- install.sh 默认安装 Release，而不是直接安装 main。
- 本次重点检查了 worker/worker.ts、kernel/due.ts、kernel/decide.ts、kernel/state.ts、host/up.ts、host/service.ts、protocol/job.ts、protocol/validate.ts 和 docs/protocol.md。
- main 与 v1.2.0 在本次发现的关键停止宽限、进程组确认和 worker lease 行为上没有消除下文列出的安全差异。部署前仍须固定具体版本，不能把 main 的审查结果直接当成未来安装版本的永久保证。

当前售后工作区 shell 的 Node 版本为 22.22.1，时区为 Asia/Shanghai。Autoloop 安装脚本要求 Node 24 或更高版本。实际 LaunchAgent 使用的 Node 绝对路径尚未核验。后续若采用 Autoloop，应优先隔离运行时，不要为了安装 Autoloop 直接升级现有售后服务的 Node。

## 3. 售后现有队列：它实际在做什么

### 3.1 两种“队列”必须区分

售后项目有两种不同的队列：

1. 操作队列：lib/server/op-queue.js 中的 queue、running、lastCompleted、paused。它负责安排浏览器操作的先后，目前主要保存在服务进程内存中。
2. 业务工单队列：data/queue.json 等业务数据。它保存工单采集、推理、等待、执行等业务状态。

迁移 Autoloop 的对象是第一种“操作调度队列”，不是把 data/queue.json 这套业务工单数据搬进 Autoloop。

Autoloop 的 hub.db 将来可以成为任务调度状态的来源；售后原有 queue item、simulation、case、execution journal、账号状态、提醒去重和业务记录仍应由售后项目负责。

### 3.2 当前操作类型映射

| 当前操作类型 | 现有入口 | 实际工作 | 风险与迁移注意 |
|---|---|---|---|
| scan | POST /api/scan；server.js 定时触发 | 按账号配置扫描所有启用店铺，执行 A1 固定 48 小时清单和 Step14 逐单处理，并处理提醒、账号状态、扫描进度 | 不是纯读取任务；内部可能进入已授权的自动同意分支。整轮重试必须有逐单幂等和恢复边界 |
| a1-fixed-batch | POST /api/accounts/:num/a1-fixed-batch | 对指定单账号执行固定 48 小时清单 | 后端入口只允许单账号和固定时效，忽略前端可篡改的 accounts、thresholdHours、disableAutoExecute 等参数；必须保留 |
| reprocess-one | POST /api/queue/:id/reprocess、批量重采入口 | 对单个 queue item 重新打开账号、准备新鲜列表、定位工单、打开详情、重新采集和推理 | 会写回业务数据；通过 Step14 链路时可能命中现有自动执行门禁。不能因 Autoloop 重试而重复平台动作 |
| reinfer | POST /api/simulations/:id/reinfer | 带入用户提示后重新采集推理 | 实际会继续调用重采流程，不是单纯本地改文字 |
| execute | POST /api/simulations/:id/execute、批量执行入口 | 根据最新 simulation 和执行门禁，对单笔工单执行人工发起的 approve/reject | 真实平台写操作。当前 execExecute 路径没有使用 Step14 的 auto-execution-journal；不得套用 Autoloop 默认自动重试 |
| open-ticket | POST /api/open-ticket | 通过安全账号流程定位并打开指定工单详情 | 主要是导航和读取，但重复执行可能重复打开页面；仍需串行 |
| open-account | POST /api/accounts/:num/open | 通过 openAccountFlow 检查真实页面身份、账号 tab 数量和注入条件，再打开后台 | 必须保留 A2 安全打开流程；current-session 只能作辅助缓存，不能跳过页面核验 |
| wanwu-scan | server.js 定时触发 | 万物心选只读巡检；必要时单次登录，待办数字间隔 3 秒双读一致后确认，并关闭本轮创建的标签页 | 与鲸灵/ERP 共用现有 op-queue，必须纳入同一桌面调度组；提醒与状态更新要去重 |
| return-inbound | POST /api/return-inbound/run | 按输入顺序逐个快递单号执行 ERP 售后工单创建并确认入库 | 真实写操作；当前按单号边界软停止，正在处理的单号完成后才检查停止。不能因批次失败而盲目重放已完成单号 |
| scan-finalize | executeOp 分派中仍有此分支 | 旧的扫描收尾/批量重采实现 | 当前代码中未发现有效 enqueue 调用点；暂列为未使用实现，不纳入首批迁移，除非后续找到真实调用者 |

批量执行和批量重采路由不是独立 executor 类型，而是把多个单笔操作分别入队。

### 3.3 当前定时调度

实际常量和代码如下：

- 鲸灵售后扫描：每天 00:00、08:00、12:00、16:00、20:00。
- 万物心选巡检：每天 07:00、15:00。
- 当前机器时区为 Asia/Shanghai。
- server.js 使用 setTimeout 计算下一个未来时刻；服务重启或机器错过时刻后，不补跑之前错过的扫描，而是安排下一个未来时刻。
- scan 只有在 label 为“定时扫描工单”时才启动 10 秒预告 HUD；手动扫描不增加这个等待。
- /api/skip-next-scan 使用 server.js 内存中的一次性布尔值；当前未发现前端调用点，是否保留需确认外部调用者。
- server.js 中“扫描时间 8/12/16/20”的注释已过时，实际 SCAN_HOURS 包含 00:00。

如果改用 Autoloop cron，必须明确时区，并决定是否接受“电脑睡眠后补最近一次错过的扫描”这一行为差异。Autoloop 默认只补最近一次错过的 cron，不会把所有错过时刻全部补跑；这与当前 setTimeout 的行为不同。

### 3.4 当前前端契约

现有页面依赖的操作队列接口包括：

- GET /api/op-queue：读取队列状态。
- DELETE /api/op-queue/:id：取消排队任务或停止运行任务。
- POST /api/emergency-stop：全局紧急停止。
- POST /api/resume：恢复接收新任务。
- GET /api/stop-event：读取上次停止记录。
- POST /api/scan、账号打开、工单重采、执行、退货入库等现有业务入口。

前端还依赖 /api/events 的 SSE 更新，包括队列状态、扫描进度、工单进度、入库逐条进度、万物状态和账号状态等。

定时扫描 HUD 由 scan-hud.js 和 scan-status-hud.js 负责：10 秒预告、当前店铺/工单进度、异常和终态展示。它只观察真实操作进度，不决定业务动作。

迁移后不能只让 Autoloop 显示“任务运行中”。必须保留当前 UI 能看到的队列、当前操作、进度、逐条结果、异常、停止状态和最近完成信息。Autoloop 的状态视图需要通过适配层映射回现有前端契约，或经确认后再改前端。

### 3.5 当前并非所有浏览器入口都经过 op-queue

静态审查发现以下旁路，不能只迁移 enqueue 调用点就宣称整个桌面已经统一调度：

- server.js 启动时会直接查 ERP 登录态；未登录时调用 recoverLogin。这段浏览器操作不经过 op-queue。
- cli.js 提供直接访问鲸灵/ERP/CDP 的命令，包括读取、导航、备注以及 approve/reject 等操作；它们不自动经过 op-queue。
- 店铺新增/重新登录路由会通过 relogin-session.js 启动 sessions/jl.js 的独立可见 Playwright 登录进程，不经过 op-queue。
- return-inbound 项目也保留独立 CLI 入口；若单独运行，同样绕过售后 op-queue。
- 旧 pipeline.js、scan-all.js、collect.js 和 run-scan.sh 属于历史路径。README 已明确它们不是当前 A1 正式入口，不得在迁移时重新接回。
- startErpHeartbeat 已停用，不作为现役调度任务迁移。

后续必须逐一决定：这些入口是接入同一调度组，还是被明确规定为人工占用/维护模式。未决定前不能声称“所有桌面操作已串行”。

### 3.6 现有售后安全边界必须保留

- 鲸灵行为操作失败即停，不自动重试；只有 ERP 订单搜索有明确的一次重试例外，总计最多两次。
- 风控信号会触发持久化熔断，需要人工确认恢复。
- 所有账号切换必须经过 openAccountFlow 和真实店铺身份核验。
- 只有现有 automation-policy 明确授权、并通过本次事实重新证明和 executionJournal 门禁的自动同意分支可以自动执行；不得扩大范围。
- 拒绝、商责、歧义和不确定结果继续走人工边界。
- Step14 的平台写操作一旦已经发出，必须完成结果验证和 journal 记账，再停止后续工作；不能在中途强杀。
- return-inbound 当前按输入顺序处理；停止信号在每个快递单号开始前检查，当前单号执行期间不会被中途打断。
- auto-execution-journal 记录 reserve、page_action_started、page_action_succeeded、auto_executed 等阶段，目的是 fail-closed 和防重复执行，不是自动重试工具。
- 手动 execExecute 路径没有复用该 journal；return-inbound 的 op-queue 批次结果主要由运行中数组和 SSE 展示。二者都需要单独审查恢复与幂等性，不能假设 Autoloop 的任务去重已经覆盖业务副作用。

## 4. Autoloop 实际工作逻辑

### 4.1 一条任务如何流转

可把 Autoloop 理解为“接收任务、判断交给谁、排队、派发、收回结果”的调度系统：

1. Source：任务从哪里来，例如售后页面按钮或定时规则。
2. Event：一次具体的任务请求，包含 id、type、subject 等字段。
3. Rule：判断哪类事件应该交给哪个 Agent/Worker。
4. Group / Lane：限制哪些任务共享同一资源，以及哪些任务属于同一对象。
5. Worker：常驻接单程序，向 Hub 领取任务、汇报心跳、检查停止、提交结果。
6. Agent：真正执行任务的进程。可使用 command 适配器运行固定 Node 脚本，不必调用 Codex、Claude 或其他 LLM。
7. Receipt：执行完成后提交的结果，Hub 再更新任务状态、安排重试或生成待人工处理事项。

rules.json 主要负责路由和调度，不应复制售后的退款决策、业务事实判断和自动执行授权。

### 4.2 串行桌面任务如何配置

Autoloop 有三层相关限制：

- group：把共享同一资源的规则放到一个组。
- parallel：配置后按 subject 分 lane；同一对象不会同时执行，group 还会限制整个组的并发数。
- worker.capacity：限制一个 Worker 同时持有多少任务。

若要保证桌面浏览器一次只执行一项，候选配置是所有桌面任务使用同一个 group，规则统一设置 parallel: 1，桌面 Worker 的 capacity 设置为 1。

这里有一个重要区别：如果规则没有设置 parallel，同一规则下不同事件可能被合并到同一个排队线程；如果设置 parallel，subject 就决定任务按什么对象拆分。因此，工单重采可用 queueItemId，手动执行可用 simId，账号任务可用账号/请求 ID，入库任务则要先确定按批次还是单号拆分。

group 只是 Autoloop 内部的调度并发限制，不会自动阻止绕过 Autoloop 的 CLI、启动检查或独立登录窗口操作 Chrome。所有旁路必须接入或被显式隔离。

### 4.3 持久化、去重和重试

- Hub 使用本地 SQLite WAL + FULL，事实日志和任务投影持久化；服务重启后可恢复调度状态。
- 同一 source 下相同 event id 只记一次；可安全重发同一个事件。
- claim 和 receipt 也有重复提交保护。
- 这些机制保护的是调度事件和结果提交，不等于平台 approve、reject 或 ERP 入库动作天然幂等。
- 当前源码对 failed 结果采用自动重试：等待 5、10、20、40、60 分钟，之后最多按 60 分钟间隔继续，最多 10 次。该策略不是售后现有“鲸灵行为操作失败即停”的策略。
- 因此，不能把所有售后错误都映射为 failed。只有明确证明尚未发出平台写操作、可安全重复的基础设施失败，才可考虑重试。副作用可能已发生但结果不明时，必须走人工确认/恢复状态，不能触发自动重放。
- 大批量任务参数不能无条件塞进一个 event.detail：Autoloop 字段有长度限制，detail 最多 4000 字符、summary 最多 200、subject 最多 100。大批量入库或复杂参数需要使用持久 payload 引用或先拆分任务。

### 4.4 Worker 的进程和恢复方式

- Worker 会先保存每轮 entry.json，再启动独立、detached 的 Agent 进程组。
- 标准输出、错误输出和退出码写入本地 run 目录。
- Hub/Worker 服务重启时，Worker 会重新读取这些 entry，并尝试接管仍在运行的进程；正常的服务重启不等于任务取消。
- Worker 的默认任务超时为 180 分钟。
- 任务取消时先发 SIGTERM，默认等待 10 秒，再发 SIGKILL。
- Agent 进程组与 Chrome 浏览器不是同一个进程。若执行器仍在售后 server 进程内，Worker 只管理到外部桥接命令，不能仅凭桥接命令退出就断言售后 server 中的浏览器操作已经停止。

### 4.5 Autoloop 的停止/失联默认行为与售后要求冲突

这是本次审查最重要的结论：**不能原样采用 Autoloop 当前的失联和停止策略。**

发现的具体行为：

1. Worker Fresh / Run Lease / Offline 阈值分别约为 2 分钟、5 分钟、10 分钟。
2. Worker 仍在线但某个已领取任务超过 Run Lease 没有继续被报告时，Hub 会把该任务转成 unknown。
3. claimNext 的组并发统计只把 claimed 计入；unknown 不计入。因此 unknown 任务可能仍有迟到结果，但桌面组已经允许下一任务领取。
4. 取消任务默认 10 秒后强制 SIGKILL；这短于售后部分平台提交、当前单号入库或账号原子操作可能需要的安全收尾时间。
5. groupAlive 无法运行 ps 时会返回 null；停止宽限期结束后，当前代码会发出 SIGKILL 并继续收口，而不是要求必须确认进程组确实消失。
6. 正常退出路径主要检查记录的父 PID；完整进程组检查主要用于 stopping 分支。后续还应补查 wrapper 退出但子进程仍存活的情况。
7. 停止 Autoloop 服务本身与取消某个任务不同：服务停止会退出 Hub/Worker，但 detached Agent 可能继续运行，Worker 重启后再找回它们。

售后必须做的局部安全调整：

- unknown 必须继续占用桌面组，不能因租约超时自动释放。
- 只有确认旧执行器、桥接进程及其可能继续操作的子进程都失去操作能力，才允许释放桌面。
- ps/进程组检查失败或状态不明时，保持占用并报警，不能把“查不到”当成“已经停止”。
- 取消必须支持售后安全检查点：普通读取可停止；已经发出的平台写操作、当前入库单号和其他原子步骤必须先完成必要的验证/记账。
- 10 秒固定强杀不能直接覆盖售后操作。强制终止应与安全停止分开，且不能在旧任务仍可能控制浏览器时释放调度资源。
- Hub/Worker 恢复、售后 server 恢复和业务 journal 恢复必须有明确的先后关系，避免“调度层以为已释放，业务层仍在运行”。

### 4.6 其他需要理解的 Autoloop 行为

- 当前没有可直接替代售后 /api/emergency-stop 的全局暂停 API；主要是逐个取消任务和停止服务。需要在售后适配层保留 paused gate，阻断新任务，并按现有语义取消队列任务。
- Autoloop 的 cron 有自己的时区配置和补跑语义；不能直接照抄当前 setTimeout。
- elsewhere 只用于展示“在别处运行”的任务，不会由 Autoloop 启动；现有售后扫描不能放到 elsewhere。
- command 适配器可以执行固定脚本，不需要 LLM，但它不是安全沙箱，命令拥有本机用户权限。只能配置固定的本地 runner，不能让事件输入决定任意 shell 命令。
- askFirst 等规则配置不是售后业务授权的替代品；所有退款、拒绝、入库和账号安全门禁继续由售后代码执行。

## 5. 迁移时必须解决的现有差异

### 5.1 当前紧急停止标记没有真正恢复 paused

op-queue 的 paused 是内存变量，初始值为 false。server 启动时会读取 emergency-stop.json 并打印警告，但没有据此把 paused 恢复为 true；随后 server 仍会安排扫描定时器。

因此当前 stop 文件是“历史停止记录”，不是可靠的跨重启暂停锁。迁移时必须把暂停状态做成持久状态，并保证 server/Autoloop 启动顺序不会在恢复检查前领取新任务。

### 5.2 当前 executor 在售后 server 进程内

当前 op-queue 的执行函数直接运行在 Express server 进程中，使用同一进程的 AbortController、业务数据模块和 SSE。

spawnAsync 有定义，但当前未发现实际调用点；当前停止主要靠 AbortController 和步骤检查点，不是靠杀子进程。

如果把所有业务执行直接搬到 Autoloop 的 detached 子进程，会引入新的跨进程数据写入问题。data.js 目前主要是 JSON 临时文件替换/rename 和 JSONL append，没有发现可证明多进程写入安全的全局文件锁实现。不能未经设计就让 server 和 Worker 两边同时修改相同业务数据。

### 5.3 前端进度不能丢

Autoloop 的 command adapter 在命令仍运行时不会像当前 SSE 一样自动提供完整业务进度。若只在结束时返回 receipt，当前扫描 HUD、店铺进度、逐单结果和入库逐条进度都会退化。

必须设计进度侧通道：由售后 executor 把进度继续推给现有 SSE，或由适配层把 Autoloop 运行状态和业务进度组合后提供给前端。

### 5.4 业务动作的重试必须分类

建议至少分为：

- 可安全重试：确认没有发出平台写操作的连接失败、启动前失败、只读任务的基础设施错误。
- 不自动重试：鲸灵点击/提交/上传错误、已发出但结果不明的平台写操作、ERP 入库提交结果不明、任何无法证明未产生副作用的任务。
- 需要人工收口：旧进程是否仍在、平台是否已执行、本地 journal 是否落盘等无法确认的情况。

不得把“任务失败”统一映射为 Autoloop 的 failed。

## 6. 初步推荐架构（尚未确认，不是实施决定）

优先讨论的候选方案：

1. Autoloop 成为唯一的持久任务队列和定时调度所有者；旧 op-queue 不再保留第二套待执行队列。
2. 售后 server 继续作为业务数据的单一写入者和浏览器执行者，保留现有 executor、AbortController、安全检查点、SSE 和业务 journal。
3. 通过适配层把原有页面按钮和定时事件转换成 Autoloop event；Autoloop 的固定 command runner 调用售后内部执行接口，等待任务真正结束并提交 receipt。
4. 售后 server 对正在执行的任务持有持久 desktop lease；只有 executor 确认安全结束后才释放。Worker 必须把该 lease 纳入任务结束/接管判断，不能只看桥接进程 PID。
5. 原有 /api/op-queue 等接口先保持兼容，由适配层把 Autoloop 状态转换为旧前端契约；完成稳定验收后再讨论是否调整前端。

这样可以先避免把大量业务代码搬进另一个进程，也避免 server 与 worker 同时写 JSON 数据。

替代方案是把 executor 全部抽到 Worker 子进程中。该方案能让 Autoloop 进程组更直接对应任务执行器，但需要解决数据文件跨进程写入、SSE 进度、停止信号传递、业务模块依赖和 server 重启后的恢复，首轮不建议直接采用。

以上只是审查后的候选结构。正式实施前必须在第 1 项中把请求、执行、停止、结果和进度的实际调用链画清楚，再由用户确认。

## 7. 九项逐项讨论清单

后续按以下顺序逐项讨论，每项都走“解释 → 确认 → 实施 → 反查 → 用户确认”：

1. **适配层**：现有 enqueue、执行结果、进度、异常返回，如何映射到 Autoloop event/run/receipt；谁负责实际执行。
2. **调度所有权**：鲸灵扫描、万物巡检的 cron、时区、漏跑补跑、skipNextScan；旧 setTimeout 如何停用，避免双重调度。
3. **手动入口**：页面按钮、批量操作、CLI、账号重登/登录窗口、启动 ERP 检查如何统一登记或显式占用桌面。
4. **停止/失联/恢复/崩溃**：桌面 lease、unknown、进程组、停止检查点、server 重启、Worker 重启、结果不确定时如何 fail-closed。
5. **验收**：扫描、重采、模拟结果、人工执行边界、账号切换、退货入库和异常恢复的验收方法；真实平台写操作必须另行授权。
6. **现有能力保留**：扫描 HUD、SSE、逐单进度、提醒、账号状态、队列展示、取消/暂停/恢复、历史结果。
7. **Autoloop 任务类型与粒度**：哪些按单笔、哪些按账号、哪些按整批；subject、event id、group、parallel 和 capacity 如何设置。
8. **五阶段迁移计划**：按下面的阶段推进，阶段间有明确验收门槛。
9. **最终收口**：核对旧入口是否全部退役、是否还有绕过调度的路径、运行手册和长期 TODO 是否完整。

## 8. 五阶段迁移路线

1. **适配层**：接通任务提交、执行结果、进度和异常返回；先确认数据流和调用边界。
2. **调度所有权迁移**：把定时扫描等调度交给 Autoloop；确认后停用旧定时器，不能两套同时触发。
3. **手动入口迁移**：所有页面按钮和需统一管理的手动桌面请求都通过同一调度入口，保留原有 API 校验和返回语义。
4. **停止/恢复/崩溃安全**：完善任务完成确认、停止、重启、强制终止、残留进程和 desktop lease；不确认旧任务失去操作能力，不释放桌面。
5. **完整验收与退役旧入口**：完成真实扫描、重采、模拟/人工执行边界、账号切换、退货入库和异常恢复验收后，再删除旧队列调度入口。

## 9. 待逐项确认的问题

- 适配层采用售后 server 内部执行接口，还是把 executor 抽成 Worker 子进程？当前倾向前者，理由是避免跨进程业务数据写入和重复实现 SSE。
- desktop lease 的存储位置、所有者、进程身份校验和 stale lease 人工解除流程。
- Autoloop unknown 状态是否对桌面任务永久占用 group，何种证据允许人工释放。
- 是否需要为 Worker 增加“安全停止等待”配置，替换固定 10 秒强杀；强制终止与普通停止如何区分。
- 售后全局 emergency-stop 的持久 paused 状态和 resume 语义；已取消任务是否永不自动恢复，沿用当前人工重新发起原则。
- skipNextScan 是否保留；当前没有前端调用点，需确认外部使用者。
- cron 错过时刻后补最近一次，是否接受；当前旧调度是跳过错过时刻。
- CLI 的只读命令、人工 approve/reject、独立登录窗口和 return-inbound CLI 是否全部接入调度，还是定义明确的人工维护占用。
- return-inbound 的任务粒度和逐单持久化结果，如何避免已成功单号被批次重试。
- 手动 execExecute 的执行 journal/幂等性如何补齐。
- scan-finalize 是否彻底废弃；目前没有 active enqueue 调用点。
- Autoloop 的 Node 24 运行时如何与售后 Node 22 服务隔离；LaunchAgent 的真实 Node 路径尚未确认。

## 10. 原有 TODO 与本次新增专项的关系

原有售后 TODO 不因本次迁移审查而改变：

- “平台准备发货 + 平台无物流 + ERP 已揽收”独立拒绝分支：仍待实施，且保持人工确认，不开放自动执行。
- 部分退货金额辅助支持多主子订单：当前继续限定单主子订单，多主子订单保持人工。
- 历史工单评价与反馈集中回顾优化：仍待择时。
- 线下换货生产观察：仍等待下一次正常扫描自然出现样本，不为观察主动触发真实业务。

return-inbound 项目自己的 TODO 继续保留在 return-inbound/tasks/todo.md。本次只把它作为售后统一调度的一个高风险执行类型纳入映射，不合并或覆盖该项目的业务 TODO。

本次新增的 Autoloop 迁移专项只记录架构审查、逐项讨论和五阶段实施路线，不改变上述业务优先级和授权。

## 11. 下一会话执行要求

下一会话从第 1 项“适配层”开始。先用售后现有页面按钮举一个实际任务，按“用户点击 → 现有 API → enqueue → executor → SSE/结果”的顺序讲清楚，再映射到“source → event → rule → group/lane → worker → command → receipt”。

不要一次解释完九项，不要先写大规模代码，不要先安装 Autoloop。第一项确认后只实现第一项，并反向检查实际请求、执行、结果和进度链路；确认没有问题再进入第二项。

任何时候，只要旧任务是否仍能操作浏览器无法确认，就必须保留桌面占用，不得启动下一项任务。
