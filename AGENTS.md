# Codex Rules for Claude Workspace

本目录是从 Claude Code 工作流演进来的业务自动化工作区。Codex 在这里工作时，必须尊重既有 `CLAUDE.md` / `SKILL.md` 规则，不把它们当作普通说明文件。

## 启动顺序

进入 `/Users/chat/claude` 或任一子项目时：

1. 先读当前目录的 `CLAUDE.md`。
2. 如果进入子项目，先读该子项目的 `SKILL.md`，再读该子项目的 `CLAUDE.md`。
3. 再读该子项目的 `tasks/todo.md` 和 `docs/INDEX.md`，按 `SKILL.md` 的 DO FIRST 决定是否继续加载其他文档。
4. 禁止在读 `SKILL.md` 前先用大范围 grep/glob 搜索业务逻辑。`SKILL.md` 是导航地图，先看地图再走路。

## 工作区红线

- 真实业务系统写操作必须人工确认：退款、拒绝、入库、匹配写入、批量修改、提交确认、账号登录都属于高影响操作。
- 鲸灵 `scrm.jlsupp.com` 行为操作报错即停，绝不自动重试第二次。重复失败会触发风控。
- ERP 操作必须串行；同一浏览器 session、同一 tab、同一账号登录流程禁止并行。
- 验证数据必须读实时源头：从 ERP 页面、CLI 或当前文件重新读取，禁止把历史 jsonl 快照当真值。
- DOM 操作必须过滤可见元素；Element UI 弹窗必须走 Vue/按钮关闭流程，禁止直接移除 DOM。
- 截图只作为补充证据，网页操作优先用 DOM 状态和真实数据源确认。

## 项目主力工作方式

- 修改前先理解项目入口、数据流、运行时副作用和风控边界。
- 代码能确定的事不要交给模型判断；模型适合分类、摘要、起草和非结构化提取，不适合决定重试、路由、状态码或确定性变换。
- 小修直接做；涉及 3 个以上文件、流程结构、状态机、跨项目共享代码时，先给计划，并优先使用 worktree 隔离。
- 修改后必须验证：能跑测试就跑测试，能跑 CLI dry-run 就跑 dry-run，不能跑要说明原因和剩余风险。
- 写入后读回确认，尤其是 `data/` 以外的配置、规则、文档、计划、cron 或运行脚本。
- 不提交运行时数据：`data/`、`*.log`、`_sandbox/`、`_exports/`、`.server.lock` 默认不进 commit。

## 子项目入口

| 子项目 | 先读 |
| --- | --- |
| `aftersales-automation/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |
| `product-mapping/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |
| `product-detect/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md` |
| `sku-calculator/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |
| `return-inbound/` | `SKILL.md`、`tasks/todo.md` |
| `sessions/` | `CLAUDE.md` |
| `transfer/` | `SKILL.md`、`CLAUDE.md` |
| `lkwj/` | `SKILL.md` |
| `douyin-workout/` | `SKILL.md` |

## Codex / Claude Code 协作

- 本工作区仍保留 Claude Code 项目规则；Codex 不应覆盖或稀释这些规则。
- 启动后先读 `CLAUDE.md` → `docs/HANDOFF.md`（如果存在）→ `docs/codex-handoff/inbox.json`（检查是否有 Claude Code 发来的协作请求）→ `git status` → `git log --oneline -5`，了解 Claude Code 最新状态。
- 完成工作后更新 `docs/HANDOFF.md`（如果做了实质性改动），确保 Claude Code 下次启动能接上。
- `codex-plugin-cc` 适合做审查和救援：普通审查用 `/codex:review`，挑战设计和风险假设用 `/codex:adversarial-review`。
- 审查和修复分阶段进行。审查阶段只报告问题；修复阶段再改代码。
- `neat-freak` 用于阶段收尾和文档/记忆同步；`systematic-debugging` 和 `verification-before-completion` 用于 bug 和完成前验证；`pua` 只在反复失败、被动等待或用户明确触发时使用。

### Codex → Claude Code 协作收件箱

当 Codex 需要 Claude Code 审查计划、方案或代码时，使用 `docs/codex-handoff/` 协议：

1. **写全文**：将完整内容写入 `docs/codex-handoff/{project}-{action}.md`
2. **注册到收件箱**：在 `docs/codex-handoff/inbox.json` 的 `pending` 数组追加条目：
```json
{
  "id": "ISO时间戳",
  "project": "项目名",
  "action": "review-plan|review-code|review-design|handoff|alert",
  "file": "docs/codex-handoff/文件名.md",
  "summary": "一句话摘要（用户会看到）",
  "from": "codex",
  "timestamp": "ISO时间戳",
  "status": "unread"
}
```
3. **通知用户**：告诉用户"可以让 Claude Code 查看 docs/codex-handoff/ 里的协作请求"，不要假设 Claude Code 会自动读。
4. **自己检查收件箱**：启动时检查 `inbox.json` 是否有 Claude Code 发来的协作请求（from: "claude"），如有则读取对应文件。

### Claude Code → Codex 协作（收件箱反向）

Claude Code 也可以通过同一收件箱向 Codex 发协作请求。格式同上，`from` 字段设为 `"claude"`，状态 `"unread"`。Codex 启动时检查 `inbox.json` 中 `from: "claude"` 且 `status: "unread"` 的条目。

## 文档维护

- 任何文件新增、删除、移动、重命名，都要检查所属项目 `SKILL.md` 的 PATHS / ENTRY MAP 是否需要同步。
- 项目规则变化先更新文档，再改实践。
- 稳定经验从 `tasks/lessons.md` 迁入 `docs/INDEX.md`，避免长期重复维护。
- 跨项目影响必须同时检查上下游文档，特别是 `aftersales-automation`、`product-mapping`、`sku-calculator`、`return-inbound` 之间共享的 ERP / 鲸灵能力。


<claude-mem-context>
# Memory Context

# [claude] recent context, 2026-06-16 3:27pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (14,163t read) | 842,021t work | 98% savings

### May 30, 2026
1241 12:28a 🔵 No primary session activity detected for observation
1242 " 🔵 Flow document reference text located for after-sale reason field
1243 " 🔵 Root cause area identified: reject.js fills the detailed reason field
1244 " 🔵 Root cause identified: dynamic rejection text in infer.js overrides fixed template
1245 12:29a 🔵 CLI reject command flow confirmed for detail text passing
1246 12:46a 🔵 Primary session still investigating queue instead of applying infer.js fix
1247 12:51a 🔵 Queue state unchanged despite multiple server restarts and scan cycles
1249 " 🔵 Scan cycle completed — 3 new flow-5.3 (仅退款) tickets enqueued, 2 waiting items reset
1248 12:52a 🔵 Full scan cycle completed across all 12 accounts with zero new queue entries
1250 12:53a 🔵 All 5 queue items processed through pipeline — 2 full runs, 3 skipped as reprocess
1251 12:55a 🔵 Pipeline reprocess gate: historical live-executed simulation records block re-processing
1252 " 🔵 Auto-archive mechanism identified: read-ticket.js returns failure for closed tickets
1253 " 🔵 Two historical execution guards identified in pipeline.js: lines 318 and 395
1254 12:56a 🔵 Three-layer historical execution guard identified in pipeline.js auto-execute path
1255 " 🔵 Circuit breaker state confirmed: erp-circuit-breaker closed, main circuit-breaker missing
1256 " 🔵 Duplicate queue entries found for 3 work orders after data.js guard removal
1257 " ✅ Queue.json modified: 4 duplicate entries deleted, 5 work orders restored to pending
1258 12:57a 🔵 Primary session planning to delete historical execution guard in pipeline.js
1259 " ✅ Historical execution guard deleted from pipeline.js lines 395-405 in reprocessOne()
1260 " ✅ Confirmed: 5 work orders now pending in queue after cleanup + guard deletion
1261 12:58a ✅ Server restarted with pipeline.js fix — PID 50852
1262 " ✅ Pipeline auto-started after restart — 1 item collecting, 4 pending
S407 修复 flow-5.3 仅退款已发货 Step 4 "详细原因"拒绝文案 — inferRefundOnly() 中 waitingRescan 路径（line 538）和 INTERCEPT_TIMEOUT 路径（line 548）的 reason 字段改为固定模板 "订单已发出，已通知快递拦截暂未退回，等快递退回我司后再退款" (May 30 at 12:58 AM)
S411 Documentation debt cleanup — user independently identified and fixed SKILL.md missing front-end file entries, synced HANDOFF.md, and updated project memory to reflect the isReturnWaitingAction() refactoring from the prior session (May 30 at 12:59 AM)
1269 5:10p ✅ End-of-session knowledge cleanup with neat-freak skill
S412 实现 Codex Monitor 应用的可折叠配额监控 UI，支持双模式（160×160 折叠 + 300×420 展开）、实时倒计时、圆弧配额可视化 (May 30 at 5:13 PM)
### May 31, 2026
1284 11:09p ✅ Codex Monitor 阶段 0/1 审计通过，阶段 2 正式放行
1285 11:55p ✅ Codex-Handoff 收件箱：阶段审计任务标记完成
### Jun 1, 2026
S413 实现 inferred_project 推断流水线：从会话内容扫描识别项目归属，作为三层 fallback 的第三级，降低「其他」占比 (Jun 1 at 5:12 PM)
1287 5:13p 🟣 Added inferred_project field to CodexUsageEvent model
1288 6:46p 🟣 Extended inferred_project field to ClaudeUsageEvent model
1289 6:47p 🟣 Added project name inference regex and skip-list to reader_claude
1290 " 🟣 Implemented _infer_project function with voting-based project detection
1291 " 🟣 Added project inference pattern constants to reader_codex module
S414 实现并验证 inferred_project 推断流水线：从会话内容扫描识别项目归属，作为三层 fallback 的最后一级，降低无法归因的「其他」占比 (Jun 1 at 6:48 PM)
S415 实现 inferred_project 推断流水线：从会话文件内容扫描识别项目归属，作为三层 fallback 的第三级，将「其他」占比从 35%+ 降至 5% (Jun 1 at 6:53 PM)
S416 验证前置改进（平台风控页面状态检测）完成情况，准备进入主要工作阶段 (Jun 1 at 6:53 PM)
### Jun 2, 2026
1296 10:17a ⚖️ Escalate lkwj data remediation to external audit (Codex agent)
S417 Audit lkwj data remediation plan before implementation due to repeated structural errors (fruit task definition confusion, obtainMethods count mismatch, task categorization errors) (Jun 2 at 1:42 PM)
1295 1:42p 🔄 Refactored listActiveProducts filter logic to detect and conditionally correct filter state
1297 2:34p ✅ Registered lkwj data audit request in Codex handoff protocol inbox
S418 Understanding product-detect project current state: Phase 3 dataset quality assessment for KGOS YOLOv8 detection model (Jun 2 at 2:36 PM)
1298 2:52p 🔵 LKWJ 任务数据质量审计：256 条伪 fruit 任务识别与修复方案
1299 4:17p 🔵 洛克收集助手数据修正计划：Codex 审计回复约束条件确认
1300 4:19p 🔵 洛克收集助手 lkwj 数据现状核验：Codex 审计结论已验证
1301 4:20p 🔵 lkwj 前端 index.html 现状检查：任务分类与形态展示设计确认
1302 " 🔵 lkwj 数据 obtainMethods 现状：fruit 任务中 95/96 已有 obtainMethods，pet_241 缺失
1303 4:21p 🔵 lkwj 全景数据检验报告：Codex 审计结论完全验证，七大修正要点确认
### Jun 4, 2026
1304 1:17p 🔵 Project inference uses path-based voting in first 100 lines of session files
1305 " 🔵 Project validation uses CLAUDE.md existence check, enabling path-based misattribution
1306 4:16p ⚖️ 混合模型修正架构用于提升图像识别准确率
1307 4:36p 🔵 product-detect 项目瓶颈确认：合成数据分布与 NMS 参数是关键制约
### Jun 8, 2026
1308 4:29p 🔵 Claude Code 版本确认
1309 " 🔵 Claude Code npm 包版本确认
1311 " ✅ Claude Code 成功升级到 2.1.168
1310 " 🔵 Claude Code 最新可用版本检测
1312 " 🔵 Claude Code 二进制路径指向 bun 安装而非 npm 全局
1314 " ✅ Claude Code 通过 bun 完成实际升级
1313 4:30p 🔵 npm 全局包版本确认已升级至 2.1.168
S419 升级 Claude Code（claudecode）到最新版本 (Jun 8 at 4:30 PM)
**Investigated**: 排查了当前版本（CLI 2.1.90 / npm 2.1.162），查询了 npm registry 最新版（2.1.168），并通过 which/ls 定位了实际调用的 claude 二进制来源

**Learned**: 用户环境中 bun 和 npm 两套包管理器共存，which claude 指向 /Users/chat/.bun/bin/claude（bun 安装），PATH 中 bun 路径优先级高于 npm 全局路径，导致 npm 升级不生效。Claude Code 的 CLI 版本号和 npm 包版本号使用不同体系（CLI 2.1.90 vs npm 2.1.162/2.1.168）

**Completed**: 先通过 npm 全局升级（仅更新了 npm 路径，未被实际调用），根因定位后通过 bun install -g 完成了真正的升级，CLI 版本从 2.1.90 升级到 2.1.168。手动执行了 bun 阻塞的 postinstall 脚本（install.cjs）完成安装

**Next Steps**: 升级已完成并验证通过，当前无下一步操作


Access 842k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>
