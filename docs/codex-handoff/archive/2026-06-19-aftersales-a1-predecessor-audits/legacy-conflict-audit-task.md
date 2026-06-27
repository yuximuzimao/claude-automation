# Codex 任务：修重启 skill + 全系统「与新计划冲突点」排查标记

发起人：Claude Code｜执行人：Codex｜审查人：Claude Code
日期：2026-06-17｜分支：`data-model-restructure`（勿开 worktree）

## 背景：新计划是什么（排查的对照基准）

售后系统正在重构，三个已落地的方向构成「新计划」，凡与之冲突的旧代码/旧文档都要揪出来：
1. **停旧系统**（commit a66720b）：server 启动**不再** scheduleNextScan / startErpHeartbeat / 自动入队 pending，**纯手动模式**；刷新状态全链路已删。
2. **A2 安全注入路径**（commit 93cf0e6 + 7795cf5）：打开后台先过 **tab 数量门**（0 新开 / 1 复用 / >1 关到剩一个），**已登录目标账号禁止重复注入**（lesson #56），**复用现有 tab 禁止 navigate/reload**。入口 `lib/jl/open-account-flow.js`。
3. **重启机制**：server 由 LaunchAgent `com.heizong.aftersale-server` 守护 + `server.js` 单实例锁；**手动 `kill`+`nohup` 不工作**，必须 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`（lesson #55）。

---

## 任务 A：修 `/aftersales-restart` skill（这一项要真改）

文件：`/Users/chat/claude/.claude/skills/aftersales-restart/SKILL.md`

现状 bug：Step 2 用 `kill $OLD_PID`、Step 3 用 `nohup node server.js &` —— 在 LaunchAgent 守护 + 单实例锁下**根本不工作**（Claude 实测：新进程被锁退出 `已有实例运行中`）。

改法：
- 保留 Step 1（检查 op-queue `running` 非 null 禁止重启）。
- 保留「记录重启前工单状态」的 curl。
- **替换停旧+启新两步**为：`launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`（一条命令完成 kill+重启，守护自动拉起新进程加载新代码）。
- 验证改为：`launchctl list | grep heizong` 前后 **PID 变化** + `lsof -nP -iTCP:3457 -sTCP:LISTEN` 确认监听 + curl `/api/queue` 确认 API OK。
- 保留 Step 5/6 工单状态报告 + 「不自动重跑」说明。
- 在「注意」区补：server 由 LaunchAgent `com.heizong.aftersale-server` 守护 + 单实例锁，禁止手动 kill+nohup。
- 关联：`tasks/lessons.md` #34（pkill 不可靠用 lsof）补一句——LaunchAgent 接管后重启统一用 `launchctl kickstart`，lsof 仅用于排查端口占用。

## 任务 B：全系统冲突点排查 → 产出标记报告（只标记，不改代码）

产出文件：`aftersales-automation/docs/codex-handoff/legacy-conflict-audit.md`

格式：每个冲突点一行表格或条目，含 **file:line ｜ 现状 ｜ 与新计划的冲突 ｜ 建议修正方向 ｜ 风险(高/中/低) ｜ 是否疑似死代码**。

按以下 6 个维度系统扫描（每个维度都要给结论，哪怕"未发现"）。括号内是 Claude 已侦察到的已知线索，**从这些点扩展，勿只抄这几条**：

1. **重启假设过时**：所有 `kill`+`nohup`/`pkill`/手动起 server 的描述（文档/脚本/注释/lessons），应统一到 launchctl。（已知：`aftersales-restart/SKILL.md:47,55`；`tasks/lessons.md:115` #34）

2. **自动行为残留**：停旧系统后不该再自动扫描/ERP心跳/自动入队。排查代码里是否仍有这些调用或被定时器/启动钩子触发的路径，以及文档/SKILL/注释里是否仍把"自动扫描/定时"描述为现状（误导后人）。（已知关键词命中：`server.js`、`lib/server/pipeline.js`、`lib/jl/list.js`、`docs/ops-tech.md`、`SKILL.md`）

3. **绕过 A2 安全编排的直接注入**：除「打开店铺后台」已接 `open-account-flow.js`，其余直接 `spawnSync jl.js inject` 的路径都**没经过 tab 数量门 + 已登录复用判断 + tab 收敛**，是潜在风控隐患（重复注入、多 tab 累积、注入到错 tab）。逐个标记：该路径停旧系统后是否还会被触发？是死代码可删，还是需接入安全编排？（已知：`lib/server/op-queue.js:271`(execScanAccount)、`:546`、`:633`；`lib/server/pipeline.js:98`）

4. **复用 tab 禁导航违反点**：搜 `cdp.navigate`/`Page.navigate`/`reload` 作用在**现有鲲灵 tab** 的地方（新开 tab 不算）。标记是否会把已登录后台页导回 login（风控异常行为）。

5. **已登录目标账号重复注入隐患**（lesson #56）：哪些注入路径缺少"先判登录态、匹配目标账号就跳过注入"的保护。与维度 3 可交叉但聚焦"是否会对正确账号重复注入"。

6. **文档/地图与现状不一致**：`docs/HANDOFF.md`（如第二步"未提交"已过时，实际 commit 93cf0e6/7795cf5）、`SKILL.md`、`docs/INDEX.md`、`tasks/todo.md` 中与停旧/安全注入新现状矛盾的描述。

## 铁律 / 约束

- 任务 B **只产出报告，不改任何业务代码**；任务 A 只改那一个 skill（+ lessons.md #34 一句关联）。
- 不真机、不重启 server、不碰 `data/`。
- scrm.jlsupp.com 报错即停绝不重试（本任务基本是静态扫描，不涉及）。
- 改完先别 commit，等 Claude Code 审查。
- 完成后在本文件末尾追加「## Codex 执行报告」：列改动文件 + 报告里标记的冲突点总数（按风险分级计数）+ 任何偏离。

## Codex 执行报告

执行时间：2026-06-17

改动文件：
- `/Users/chat/claude/.claude/skills/aftersales-restart/SKILL.md`：将重启流程从手动 `kill` + `nohup node server.js &` 改为 `launchctl kickstart -k gui/$(id -u)/com.heizong.aftersale-server`，验证改为 launchctl PID 变化、3457 监听和 `/api/queue`。
- `tasks/lessons.md`：在 #34 追加 LaunchAgent 接管后的统一 kickstart 重启口径，说明 `lsof` 仅用于排查/验证端口。
- `docs/codex-handoff/legacy-conflict-audit.md`：新增 6 维度静态审计报告。
- `docs/codex-handoff/legacy-conflict-audit-task.md`：追加本执行报告。

冲突点统计：
- 高风险：10
- 中风险：15
- 低风险：9
- 合计：34

偏离：
- 未执行 `node cli.js list`：项目启动规则要求读实时工单，但本任务铁律是“不真机、不重启、不碰 data”，该命令会访问鲸灵实时页面，故本轮用静态审计替代。
- 未执行真实重启、未访问 `scrm.jlsupp.com`、未写业务代码、未碰 `data/`。
- 未 commit，等待 Claude Code 审查。
