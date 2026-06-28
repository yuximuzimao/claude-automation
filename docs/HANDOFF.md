# Handoff

更新时间：2026-06-27
当前负责人：Claude Code
当前分支：data-model-restructure
当前焦点：**售后 A1 账号 14 no-auto 最小整账号固定清单批次已验证；正式 op-queue/API 入口、前端按钮和真实自动执行仍未交付。**

## ⏭️ 下一窗口接手：第三步 A1 逐账号扫描处理闭环

**计划文件**：
- 总计划：`/Users/chat/.claude/plans/codex-3-2-ip-codex-3-codex-1-1-1-1-code-twinkling-emerson.md`
- 第二步清cookie方案：`~/.claude/plans/piped-juggling-giraffe.md`
- 本轮待用户确认：`aftersales-automation/docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`

**起因**：百浩账号3点"打开后台"卡住、重复点2次→IP被封。根因=注入不像真人（不清旧态、reload双身份）+ 失败不回写重复注入 + 刷新状态多账号连续登录。

### ✅ 第一步：停旧系统（已完成真机验证，commit a66720b）
- server.js 启动纯手动模式（不自动扫描/心跳/入队）；删刷新状态全链路；前端摘除扫描/批量入口

### ✅ 第二步：A2 安全打开店铺后台（2026-06-17 历史真机三场景）
最终方案（多次迭代后定稿）：**tab数量门 → 读登录态 → 复用(匹配)/清cookie+注入(未登录或错号)**

以下只描述 2026-06-17 当时版本的真机结果：
1. **已登录目标账号(汐澜)** → reuse 复用，不清不注入 ✓
2. **错号切换(账号1界面切汐澜)** → 清cookie+注入，原账号不被破坏 ✓
3. **未登录页注入(账号3百浩，历史验证路径)** → 清cookie+注入+reload → 进店铺 ✓

**2026-06-19 新增安全约束（仅纯单测，尚未真机）**：
- Cookie 清理增加二次验证：只有 `success === true && verified === true` 才允许注入；分身 A 已实现，必须保留。
- `openAccountFlow` 把同一个已解析/已清理 `targetId` 传给 04；04 只导航和验证该 tab。CLI 未传 targetId 时只接受唯一鲸灵 tab，多个直接报错。
- 注入后由 reload 改为固定导航售后列表；这项新路径和 Cookie 二次验证都没有沿用 2026-06-17 的真机结论。

关键模块（commit 93cf0e6→db05941）：
- `lib/jl/login-state.js` 三条件登录态判据+店铺名匹配（单测）
- `scripts/jl-steps/01~07`：01开login/02读店铺/03退出(**已停用**)/04注入+绑定 targetId 固定导航售后列表/05数tab/06关多余tab/07清cookie并二次验证
- `lib/jl/open-account-flow.js` `resolveJlTab`(tab数量门)+`openAccountFlow`(复用/清注)
- `lib/cdp.js` 新增 `reload`(Page.reload)+`clearJlCookiesAndStorage`(全域清)+`closeTarget`+`cdpCall`导出
- `lib/server/op-queue.js execOpenAccount` 调 open-account.js 编排

**核心铁律（接手必读，血泪换来）**：
- **切账号禁用"退出登录"**（破坏性，让原账号服务端 session 失效）→ 改清cookie（lesson #58）
- **清cookie必须显式覆盖全 jlsupp 子域**：真凭证 JSESSIONID 在 `seller-portal.jlsupp.com/merchant`，`getCookies({})` 看不到→漏清→混账号。用 `getCookies({urls:[...]})`（lesson #58）
- **注入后禁止 Page.reload 继承旧 URL**：旧 tab 若停在工单详情，reload 会把新店铺认证态与旧工单路径组合，可能造成店铺/工单上下文错配。当前统一 `cdp.navigate` 到 `https://scrm.jlsupp.com/micro-customer/business/after-sale-list`，再校验店铺名
- 已登录目标账号禁止重复注入（lesson #56）
- 判"清干净"看 JSESSIONID/_us 全域清零，不数 cookie 条数（WAF 指纹重生正常）
- 注入失败若报"仍未登录"且账号 session 是旧的(如6/7保存)→是 session 过期需 `jl add` 重登，不是流程 bug
- 排查 cookie 工具：`_sandbox/observe-clear-cookies.js <targetId>`

**测试基线**：2026-06-19 全量纯单测 138/138 通过；新固定导航、Cookie 二次验证和 targetId 绑定仍未真机验证。

### 旧路径冲突审计（第三步的 checklist，commit c963d2f）
`docs/codex-handoff/archive/2026-06-19-aftersales-a1-predecessor-audits/legacy-conflict-audit.md` 标记 34 项与新计划冲突点（高10/中15/低9）。第三步重建 A1 时**逐项收口**，重点高风险：
- 旧 API 仍活：`routes.js` POST `/api/scan`、`/queue/batch-reprocess`、`/simulations/batch-execute`（前端按钮摘了但后端能触发旧不安全链路）
- 直接 jl.js inject 绕过 A2 安全编排：`scan-all.js:32`、`collect.js:49`、`op-queue.js:546/633`、`pipeline.js:98`（只看缓存不读实时登录态→重复注入/注错tab）
- 停扫描后逻辑失真：`constants.js:76`+`pipeline.js:186` `getHoursUntilNextScan`（flow-5.3 安全边际基于不存在的自动扫描周期）

### 第三步（进行中）—— A1 逐账号扫描处理闭环

**2026-06-27 CodexPro 已完成：live 三标签店铺筛选与批量作用域加固。** `待确认` 和 `等待重查` 均新增 `全部/店铺` 筛选；前端批量执行/批量重来现在必须发送 `{statusScope, accountNum?}`，筛选视角不会再静默作用隐藏店铺。后端新增 `lib/server/live-batch-scope.js` 统一验证 `accountNum/statusScope` 并按页面 deadline/urgency 顺序选择候选；`等待重查` 只开放批量重来，不开放批量执行。原计划已在 `aftersales-automation/docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md` 原地归档；neat 交接见 `aftersales-automation/docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`。已跑 `npm test`，228/228 通过。未重启售后 server，线上加载仍需用户另行授权 `/aftersales-restart`。

**2026-06-27 CodexPro 已完成：auto-execution journal recovery 设计 + Phase 1 代码基础。** 设计文件：`aftersales-automation/docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`。结论：journal 是自动执行审计/恢复账本，不是重试助手；任何页面动作不确定都禁止盲重试 approve/reject；人工归档必须同步关闭 journal、queue、simulation/audit 和执行门禁，不能只把 journal 改成 `manually_resolved` 后让 queue/simulation 残留异常状态。代码已完成第一层：`lib/server/auto-execution-journal.js` 支持 `auto_executing/auto_executed/failed/manually_resolved`、phase 和人工归档 helper；新增 `lib/server/auto-execution-recovery.js` 做本地状态收口；Step14 safety gate 已改为优先读 journal blocking record，`auto_executed` journal 即使 simulation 缺失也阻断重复自动执行。未增加 CLI/API/UI，未启用真实自动执行。随后按 Codex 复核意见补了 3 个小风险：非 executed 人工结论会清理旧 `executedAt/autoExecutedAt/execution`，journal phase 只能按 `reserved -> page_action_started -> page_action_succeeded` 推进，recovery audit simulation 使用稳定 id 并避免 journal resolve 失败后重试重复追加 audit。全量 `npm test` 242/242 通过。

**2026-06-27 CodexPro 已完成：前端 A1 按钮加载/只读冒烟计划。** 计划文件：`aftersales-automation/docs/superpowers/plans/2026-06-27-frontend-button-load-smoke-plan.md`。结论：单账号 no-auto `A1固定清单` 按钮已经存在，不要重复实现；后续只允许在用户另行授权重启后做只读 UI smoke，检查按钮只在 `ok + has session` 账号显示、页面加载不发送 `POST /api/accounts/:num/a1-fixed-batch`、不调用旧 `/api/scan` / batch endpoints。该计划未改运行代码、未重启、未点击真实按钮、未跑 fixed-batch。

> ⚠️ 若交给 Codex：先读本节 + 已归档的 `docs/codex-handoff/archive/2026-06-19-aftersales-a1-predecessor-audits/legacy-conflict-audit.md` + lessons #54~#59 + 第二步章节。下面写到 Codex 冷启动可执行的颗粒度。**第三步是大工程，必须逐块设计、小步验证，不要一次性大改。**

**当前已完成到哪里（2026-06-18 Codex 真机小步验证）**：
- A2「打开店铺后台」仍是唯一已串入 UI 的按钮；A1 尚未接入旧扫描/队列主链路。
- 已沉淀 A1 原子脚本 `scripts/jl-steps/08-12`，全部按用户要求先真机最小测试再保存。
- `08-click-after-sale-menu.js`：保留为独立历史原子工具；扫描准备主链路不再调用，避免依赖首页菜单和弹窗状态。
- `09-select-overdue-sort.js`：真实鼠标打开排序下拉框，选择「按逾期时间最近排序」；已复测，不主动刷新。
- `10-read-urgent-after-sale-list.js`：读取 48 小时内工单，按逾期时间升序遇到第一条 >48h 即停止；分页下一页已改为真实鼠标点击分页按钮，保留页码/当前页识别。
- `11-prepare-after-sale-list.js`：对指定 targetId 固定导航售后列表→等待3秒→检测「售后工单」+「待商家处理」→09→等待5秒→校验排序值和时效升序→读取 48h 列表；不依赖首页菜单/弹窗。
- `12-click-work-order-action.js`：按指定工单号精确定位该工单容器内唯一「处理/查看/售后处理」按钮；按钮不在视口时用 mouseWheel 滚入视口，再真实鼠标点击，并校验新 tab URL/body 属于目标工单。已用工单 `100001781188621717210` 真机打开正确详情 tab。
- `13-open-single-account-work-order.js`：串联安全打开账号→准备 48 小时列表→确认目标工单存在于 urgent 列表→打开并定位正确详情 tab；任一步失败即停，不审批不拒绝，处理完成前不导航首页。
- 2026-06-19 Cookie 二次验证、targetId 绑定和固定导航设计见 `aftersales-automation/docs/superpowers/specs/2026-06-19-jl-direct-after-sale-navigation-design.md`；这些新增约束仅做纯单测，没有操作真实浏览器。
- 账号 4-14 弹窗枚举真机测试已停止：固定 URL 导航不再需要逐账号确认首页菜单是否被弹窗遮挡。
- 已确认步骤 10 的真实鼠标分页能力可复用；步骤 12/13 已具备按工单号打开对应处理 tab 并定位新 tab 的能力，不再重复建设。
- 列表页“共 N 条”和固定清单逐单串联已有代码草案；用户尚未确认细节，不能列为已完成能力。
- 验证基线（2026-06-19）：关键链路测试 36/36、全量 `npm test` 138/138；targetId 修复有独立 10/15（5 个预期失败）RED → 15/15 GREEN 证据。本轮未做真机。

**下一窗口第一件事**：
先让用户审阅 `aftersales-automation/docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`。未经用户逐项确认，不得继续修复或扩展本轮草案。当前质量审查尚有：初始清单翻页卡片刷新竞态、新 tab 绑定/误清理风险、倒计时解析失败漏单、journal 残留锁、target 枚举异常遗留 tab。不要恢复账号 4-14 弹窗枚举测试；任何真实浏览器操作必须另行明确指定。

**新 A1 目标流程（流程方向已讨论，实现细节待用户确认）**：
打开账号后台（用第二步安全编排：清 cookie + 注入并固定导航售后列表）→ 排序并首次读取全部 `<=48h` 工单，冻结为“本轮固定清单” → 按固定顺序逐单处理 → 每单完成后关闭详情 tab、确认关闭并回到列表 tab → 全部处理完才进首页读平台提醒 → 关闭该账号全部 tab 并确认完成 → 间隔至少 10 秒后切下一个账号。

固定清单一旦形成，本轮范围不再受后续列表增删、排序变化或已处理工单消失影响。每单链路必须是：列表定位工单号 → 复用步骤 12/13 点击对应处理按钮并锁定新 `detailTargetId` → 在该 tab 采集和推理 → 仅命中现有自动执行范围时直接处理，否则保持现有人工/模拟分支 → 关闭并验证详情 tab → 回列表 → 记录进度 → 下一单。

**目标工单不在当前页时**：
- `total <= 10`、确认只有页 1 且页 1 激活：可判定已从待商家处理列表消失。
- 多页：真实点击页 1，确认页 1 激活且列表刷新，再从页 1 逐页查到末页；仍找不到才判定消失。
- 翻页失败、未加载、页码未确认或达到安全上限：不得判定消失，只能停止并保留待处理。
- “消失”仅表示当前无需处理，不等价于“客户取消”，也不能自动断言已取消/已终态。
- 这是逐单定位的恢复分支，分页直接复用步骤 10，不拆独立完整分页查找模块。

**旧处理链不能直接复用**：`lib/server/pipeline.js` 的 `autoExecuteApprove` 仍可能在账号不同时直接调用 `sessions/jl.js inject`；`collect.js` 仍按缓存直接注入并自行导航详情；`pipeline.processOne` 未导出且不接受已打开的 `detailTargetId`。本轮已有 targetId-aware 采集/推理/自动执行草案，但未获用户确认且质量审查未闭合，禁止接入正式链路。

**复用的现成基座（第二步成果，已真机验证可用）**：
- 账号切换/打开后台 = `lib/jl/open-account-flow.js openAccountFlow(num)`（tab数量门→读态→复用/清cookie+注入）。第三步切账号直接调它，**不要再自己写 jl.js inject**。
- 清场 = `scripts/jl-steps/07-clear-jl-data.js`；售后列表入口 = 04/11 调 `cdp.navigate` 固定 URL；数/关tab = `05/06`。`cdp.reload` 仍存在，但不得用于注入后继承旧路径。

**闭环组成（第 3/4 项已有未确认草案，仍按待办管理）**：
1. **固定 URL 导航**：04 注入后和 11 扫描准备均直接进入售后列表。✅ 已接链路；08 仅保留为独立工具，不再作为扫描前置。
2. **固定坐标排序**：工单按紧急度/截止排序后逐个处理。✅ 已有 `09-select-overdue-sort.js` + `10-read-urgent-after-sale-list.js` + `11-prepare-after-sale-list.js`，下步接队列处理。
3. **列表总数读取**：读取页面“共 N 条”，用于区分单页与多页定位恢复。已编码草案，待用户确认与质量修复。
4. **固定清单逐单串联**：冻结首次 `<=48h` 清单；复用步骤 12/13 打开并锁定详情 tab；通过 targetId-aware 入口采集、推理和按现有范围自动执行；每单结束关闭详情 tab、验证、回列表并记录进度。已编码草案，待用户确认与质量修复。
5. **完整串联内的停止收尾**：关 tab + 残留检测 + circuit-breaker(`data/circuit-breaker.json` 已有，`node cli.js reset-circuit` 重置) + Mac 提醒(`lib/helpers.js createReminder`)。
6. **完整串联内的首页提醒时序**：新 A1 必须等该账号固定清单全部处理完才调用 `lib/jl/alerts.js`；沿用 `.scroll-item` DOM 读取，不新增主动关闭弹窗动作。旧停用 `lib/server/op-queue.js:324-328`、`scan-all.js:154-157` 仍会列表读完即导航首页，恢复旧入口前必须由第三步接管或删除这些调用。

**必须先收口的高风险旧路径（audit 报告高10项，第三步重建时逐个处理，file:line 已现查确认）**：
- `scan-all.js:33 injectAccount()` + `:143` 多账号循环直接 `jl.js inject` → 绕过 A2 安全编排。第三步改调 openAccountFlow。
- `collect.js:49 injectAccount()` + `:348` 按 `current-session.json` 10分钟缓存判断否则直接 inject → 缓存非实时登录态，会重复注入/注错号。**注意 `collect.js:64` 注释"inject已完成导航无需reload"是基于旧jl.js(带导航)写的，第二步已去导航，该注释已失真——Codex 勿据此判断**。
- `lib/server/op-queue.js:271 execScanAccount` + `:546`/`:633 execExecute`(approve/reject前) 直接 inject 只看缓存。
- `lib/server/pipeline.js:98` 自动执行 approve 前只用缓存判同账号。
- 旧 API 仍活（前端按钮已摘但后端能触发）：`routes.js` POST `/api/scan`、`/queue/batch-reprocess`、`/simulations/batch-execute` → 第三步前禁用或接安全编排。
- `constants.js:76 getHoursUntilNextScan` + `pipeline.js:186`：停自动扫描后这个"下次扫描周期"是虚假的，flow-5.3 安全边际据此算等待/拒绝会失真 → 纯手动模式应传 null 或改人工扫描时间。

**已知坑/约束（对话里才知道，文件看不出，Codex 必读）**：
- **多账号切换 = 多次登录操作，必须串行 + 间隔≥10秒**（lesson #56 风控红线，2026-05-28 并发4tab被封IP）。A1 逐账号循环天然要串行，且每账号处理完关窗口再切下一个。
- **每个鲸灵操作报错即停绝不重试**（不只是技术异常，可能是风控信号）。
- 切账号前确认前一账号 tab 已关或确认完成。
- 验证数据读实时源头（ERP页面/cli.js list），禁止分析 jsonl 历史快照。

**验收标准**：首次读取的 `<=48h` 固定清单不随后续页面变化；每单始终绑定正确 `detailTargetId`，只在现有自动执行范围内直接处理；详情 tab 逐单关闭且验证，列表 tab 可继续定位下一单；定位恢复只有完整、可信地查完范围后才能标记“从待处理列表消失”；连续多账号处理不触发风控、不重复注入、tab 不泄漏；处理完正确读取平台提醒；整系统停止能干净关闭所有 tab + 残留检测。**新增逻辑必须配纯单测；当前全量基线 138/138。**

### 执行铁律
- 鲸灵操作报错即停绝不重试；不能真机试错；真机"找/确认/点"三步分离由用户指挥
- server 由 LaunchAgent `com.heizong.aftersale-server` 守护+单实例锁，重启用 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`，禁手动 kill+nohup（lesson #34/#55）
- 改 `lib/` 决策逻辑后必 `/aftersales-restart` 重启加载；改 `lib/infer.js` 必跑 `node test/flow-test.js`
- worktree 用 `git worktree add ... <当前分支>` 手动指定基线（lesson #54）
- commit 排除 `data/`、`*.log`、`_sandbox/`；含文件增删移必同步 SKILL.md PATHS+ENTRY MAP

### 遗留待办
- 6 个账号(1/3/4/6/11/13)缺 phone 配置 → 重新登录不自动填手机号。**数据缺失非bug，phone真值需用户提供**。可选改进：phone缺失时前端提示而非静默跳过

---

## 已完成
- 自动化 Chrome 快捷方式已修复（2026-06-15）：
  - `/Users/chat/Applications/自动化Chrome.app/Contents/MacOS/applet` 改为 shell 入口，绕开 AppleScript `System Events` 进程索引
  - 启动路径统一为 `claude/sessions/start-chrome-debug.sh` → `127.0.0.1:9222/json/version` 端口检测 → `open -a "Google Chrome"`
  - 原 AppleScript applet 备份在同目录 `applet.apple-binary.bak-20260615`，原 `main.scpt` 备份在 `Resources/Scripts/main.scpt.bak-20260615`
  - 文档入口：`sessions/CLAUDE.md` 的“自动化 Chrome”章节
- codex-monitor 项目推断误分类已修复（2026-06-04）：
  - `reader_common.infer_project_from_handle()` 改为按事件类型加权投票，跳过 Codex `function_call_output`、`function_call`、`token_count`
  - 默认扫描窗口从 100 行提高到 200 行
  - 已补 `tests/test_reader_common.py` 覆盖工具输出路径噪声、用户消息权重、Claude Code 格式和边界场景
  - 验证：`python3 -m unittest discover -s tests -v` 40/40 通过，`python3 -m compileall app tests` 通过
- Codex 已审查 `codex-monitor` 项目推断误分类修复方案（2026-06-04）：
  - 请求文件：`docs/codex-handoff/codex-monitor-inference-fix-review.md`
  - 回复文件：`docs/codex-handoff/codex-monitor-inference-fix-review-response.md`
  - 收件箱：`docs/codex-handoff/inbox.json` 中 `2026-06-04-codex-monitor-inference-fix` 已移入 `processed`
  - 结论：方案方向通过；实施时需补 `reader_common` 回归测试，并建议将 `max_lines` 从 100 提高到 200
- Codex 已按用户原话重写 `lkwj` 数据修正计划审计回复（2026-06-02）：
  - 回复文件：`docs/codex-handoff/lkwj-data-plan-review-response.md`
  - 收件箱：`docs/codex-handoff/inbox.json` 中 `2026-06-02-lkwj-plan-review-response` 已移入 `processed`
  - 历史口径：当时任务只能来自 `课题进度` sheet 并排除 `异色`；2026-06-08 游戏更新后已局部覆盖为 `课题进度` 中 34 条 `异色` 行导入 `capture_shiny`，总任务数 1882
- `lkwj/SKILL.md` 与 `lkwj/docs/REVIEW_CHECKLIST.md` 已同步 fruit 任务口径：精灵果实课题任务为 96 条；果实图鉴是家族级记录，另算
- OpenClaw 已确认卸载并清理残留：`/Users/chat/.openclaw` 删除，`/Users/chat/.zshrc` 不再引用 OpenClaw 补全，登录 zsh 验证无报错
- Git 仓库边界优化：.gitignore 精确排除运行时数据，24 个运行时文件从索引移除（ac377b1）
- Codex ↔ Claude Code 双向协作收件箱协议落地（61473a3）
  - `docs/codex-handoff/` — 收件箱目录
  - `scripts/codex-inbox-check.cjs` — SessionStart hook 脚本
  - `~/.claude/settings.json` — hook 已注册
  - AGENTS.md 和 CLAUDE.md 已同步协议
- Codex Git 后续建议已审查回复（approved-with-notes，详见 `docs/codex-handoff/archive/2026-06-01/workspace-git-review-response.md`）
- 售后物流弹窗关闭超时容错已提交（09978b1）
- 剩余仓库资产分类已提交（ee356b2）
  - 纳入：品牌参考图、lkwj 标注成果、复盘资料、Claude 审查回复
  - 忽略：product-detect/assets、lkwj WIP CSV、product-mapping reports/visual-verdicts、return-inbound/input.html、sku-calculator/data、transfer/
- Codex handoff #1 已处理：快递行动退货待入库分类改用结构化字段判断（bf20ff0）
  - `public/app.js` 新增 `isReturnWaitingAction()` helper
  - 两处调用点（loadActionBadge + loadActionList）已统一
- 重启流程规则已同步：`/aftersales-restart` 只报告状态，不自动重跑；是否重采由用户手动选择
- 售后系统未提交改动已收尾验证：
  - `executedAt` 不再阻止 live 工单重新入队或重处理；仅保留自动执行防重复边界
  - flow-5.3 `INTERCEPT_TIMEOUT` 用户可见拒绝原因改为固定平台模板
  - 取消类工单测试口径已同步为 `wait_archive`
  - `npm test` 结果：44/44 通过
- Codex Monitor 计划 Claude Code 正式审计完成（2026-05-31 23:15）：
  - 回复文件：`docs/codex-handoff/archive/2026-06-01/codex-monitor-review-response.md`
  - 结论：方向批准，3 处必须修正（rate_limits 路径 / Codex token 字段 / Claude Code 多模型）
  - 用户决策：Python + tkinter 批准，视觉风格改为浅色（推翻 Codex 原深色方案）
  - 执行许可：修正 3 处后可开始阶段 0 + 阶段 1
- 线上仓库已同步：`data-model-restructure` 已推送到 `origin/data-model-restructure`
- product-detect 生成器已改为 KGOS 白底业务图规则（2026-05-31）：
  - `scripts/generate.py` 支持 `--profile train|business-val`
  - 训练场景固定为 20% 单品、35% 混放无遮挡、45% 混放遮挡
  - 遮挡后按最终可见 alpha mask 写 bbox，可见面积 <35% 的目标不写 label
  - `scripts/verify.py` 可用 `--dataset kgos_business_val --split val` 抽查业务验收集
  - 已新增 `tests/test_generate.py` 覆盖生成规则与 business-val 输出
- product-detect 新规则正式数据集已生成并读回验证（2026-06-01）：
  - `datasets/kgos/`：3400 train + 600 val
  - `datasets/kgos_business_val/`：600 val
  - 文件数、label 数、label 坐标范围、白底角点抽样、overlay smoke 均通过
  - 弱项类实例数相对普通类平均倍数：黑咖体验装 3.22x、酵素4.0体验装 3.54x、腰围卡尺 3.13x、冰霸杯 2.73x、KGO手提袋 2.72x
- product-detect 第 6 轮训练已由 Claude Code 启动并经 Codex 复核（2026-06-01 00:49）：
  - PID: 47371，命令：`python -u /tmp/kgos_train6_launcher.py`
  - 日志: `product-detect/runs/kgos_train6.log`
  - 输出目录: `product-detect/runs/kgos_yolov8s_train6/`
  - 日志已进入 epoch 1；`runs/kgos_yolov8s/weights/best.pt` 时间戳仍为 2026-05-31 19:13，旧第 5 轮未覆盖
  - 按 2026-06-01 00:52 日志速度估算 65-72 小时，预计 2026-06-03 晚至 2026-06-04 凌晨完成
  - 训练效果验收重点：默认 val 可小幅低于 train5，但 business-val 与真实白底混放图必须改善弱项 Recall、mAP50-95 和漏检率
- Codex Monitor 第一版已封板（2026-06-02）：
  - 功能范围：本地 Codex/Claude JSONL 读取、近 30 天聚合、Top 项目、tkinter 浮窗、折叠态、窗口位置持久化、macOS `.app` wrapper、LaunchAgent plist 生成、watchdog/轮询刷新 fallback
  - 用户确认：第一版可以封板；“本月”改“近 30 天”为用户确认口径
  - 验证：`python3.13 -m unittest discover -s tests -v` 27/27 通过，`python3.13 -m compileall app tests` 通过，`python3.13 main.py --smoke-aggregate` 通过
  - 协作材料归档：`docs/codex-handoff/archive/2026-06-02-codex-monitor-v1/`
- 工作区 Git 整理已完成（2026-06-02）：
  - `/Users/chat/claude` 已拆分并推送 5 个提交：product-detect 生成器、lkwj 核对说明、项目入口名、reviews 回顾索引、AGENTS memory context
  - 全局 Git ignore 已新增 `/Users/chat/.config/git/ignore`，排除 `.DS_Store`、`.codex-marketplace-install.json`、`.qclaw/`
  - `qclaw` 工作区仅做本地忽略，不删除内容
  - `.cc-switch/skills/web-access` 新增 CDP `/key` 键盘事件端点；原上游 `eze-is/web-access` 当前账号无写权限，已备份到 `yuximuzimao/claude-automation` 的 `backup/web-access-cdp-key-endpoint` 分支
  - 本地恢复文件：`/Users/chat/git-backups/0001-feat-cdp-add-key-dispatch-endpoint.patch`、`/Users/chat/git-backups/web-access-f2cac3b.bundle`

## 未完成
- Codex 未执行售后系统重启；如需要线上 server 立刻加载新 `lib/` 逻辑，仍需手动运行 `/aftersales-restart`
- product-mapping 品牌数据重构：图片 jpg→png 迁移，品牌目录整理
- product-detect/assets/ 16MB 训练素材已从 Git 排除，后续需决定外部存储位置
- product-detect 下一步：等待第 6 轮训练完成，并同时评估默认 val 与 `datasets/kgos_business_val/`；重点类为黑咖体验装、酵素4.0体验装、腰围卡尺、冰霸杯、KGO手提袋
- transfer/ 本地目录已从当前仓库忽略；如确认不再需要本地副本，再手动清理

## 新增协作规则
- Codex 需要审查 → 写 `docs/codex-handoff/{project}-{action}.md` → 追加 inbox.json → 告诉用户
- Claude Code 启动 → SessionStart hook 自动检查 inbox → 有待处理则通知用户
- 协议详见 `docs/codex-handoff/README.md`
