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

# [claude] recent context, 2026-06-01 4:53pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (14,643t read) | 994,765t work | 99% savings

### May 29, 2026
1163 10:25p 🔵 CLAUDE.md 与 AGENTS.md / HANDOFF.md 零引用——文档层断裂
1164 " ✅ CLAUDE.md Git scope 新增 transfer 子项目
1165 " ✅ CLAUDE.md 新增 Codex 协作章节与 AGENTS.md/HANDOFF.md 引用
1166 " 🔵 AGENTS.md 同样不引用 HANDOFF.md——双向断裂
1167 10:26p ✅ AGENTS.md 新增 HANDOFF.md 引用——双向文档断裂修复完成
1183 10:59p ⚖️ Git backup strategy for AI change recovery
1184 11:01p ⚖️ Codex Git optimization plan reviewed with risk assessment
1190 11:06p ✅ .gitignore updated with runtime data, model weights, and Codex internal file exclusions
1191 " 🔵 Git index unwritable prevents git rm --cached from removing tracked runtime files
1192 11:10p ✅ .gitignore updated with runtime data, model weights, and Codex internal file exclusions
1193 " 🔵 Codex sandbox cannot write to .git/index.lock blocking all git write operations
1194 " 🔵 Tracked runtime data inventory: 85 files identified for git index removal
1195 " 🔵 Full tracked file inventory under data/products/ and lkwj/ revealed
1196 11:11p 🔵 Complete tracked data/ inventory: 85+ files across lkwj and product-mapping
1197 " ✅ .gitignore rewritten from broad negation pattern to targeted per-project exclusion
1198 " ✅ Aftersales runtime data removed from git index via git rm --cached
1199 11:12p ✅ Product-mapping image collection files removed from git index
1200 " ✅ auto-match-log.json removed from git index
1201 " 🔵 product-mapping/data/imgs/ files already deleted from disk, not just index
1203 11:15p ⚖️ Codex-Claude 协作协议设计方向明确
1204 " 🔵 现有 AGENTS.md 已有 Codex 协作规则但缺乏双向通信协议
1205 11:25p 🟣 创建协作协议基础设施目录 docs/codex-handoff/
1210 " 🟣 Codex-Claude Code collaboration protocol v1 implemented (pending registration)
1211 11:34p 🟣 Codex-Claude Code bidirectional handoff protocol fully implemented and verified
1215 11:37p 🔵 Protocol gap: Codex cannot read Claude Code's in-process text responses
### May 30, 2026
1241 12:28a 🔵 No primary session activity detected for observation
1242 " 🔵 Flow document reference text located for after-sale reason field
1243 " 🔵 Root cause area identified: reject.js fills the detailed reason field
1244 " 🔵 Root cause identified: dynamic rejection text in infer.js overrides fixed template
1245 12:29a 🔵 CLI reject command flow confirmed for detail text passing
S399 Fix flow-5.3 (仅退款-已发货) rejection detail text — replace dynamic tracking number concatenation with fixed platform template text in lib/infer.js (May 30 at 12:31 AM)
S400 Fix flow-5.3 (仅退款-已发货) Step 4 "详细原因" rejection text in lib/infer.js — change dynamic tracking-number-containing text to static template "订单已发出，已通知快递拦截暂未退回，等快递退回我司后再退款" (May 30 at 12:33 AM)
S401 User reported work orders not appearing in queue; primary session investigated queue state and server health instead of applying the requested infer.js fix (May 30 at 12:43 AM)
1246 12:46a 🔵 Primary session still investigating queue instead of applying infer.js fix
S402 User asked why work orders still not appearing in queue after previous changes; primary session continues investigating queue behavior instead of applying the infer.js fix (May 30 at 12:46 AM)
S403 User reported work orders not appearing in queue; primary session continues server restart loop without applying requested infer.js fix (May 30 at 12:47 AM)
1247 12:51a 🔵 Queue state unchanged despite multiple server restarts and scan cycles
1249 " 🔵 Scan cycle completed — 3 new flow-5.3 (仅退款) tickets enqueued, 2 waiting items reset
S405 Primary session previously claimed "修复生效了" for queue fix after scan cycle — now shifted to exploring project docs instead of applying remaining infer.js fix (May 30 at 12:51 AM)
1248 12:52a 🔵 Full scan cycle completed across all 12 accounts with zero new queue entries
S404 Primary session claims "fix took effect" after scan cycle — 3 new tickets enqueued — but the infer.js rejection detail text fix remains unexecuted (May 30 at 12:52 AM)
1250 12:53a 🔵 All 5 queue items processed through pipeline — 2 full runs, 3 skipped as reprocess
S406 Primary session continues queue-reprocessing tangent after pipeline.js guard deletion — infer.js rejection detail fix still completely ignored (May 30 at 12:53 AM)
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
1269 5:10p ✅ End-of-session knowledge cleanup with neat-freak skill
S411 Documentation debt cleanup — user independently identified and fixed SKILL.md missing front-end file entries, synced HANDOFF.md, and updated project memory to reflect the isReturnWaitingAction() refactoring from the prior session (May 30 at 5:13 PM)
### May 31, 2026
1284 11:09p ✅ Codex Monitor 阶段 0/1 审计通过，阶段 2 正式放行
1285 11:55p ✅ Codex-Handoff 收件箱：阶段审计任务标记完成

Access 995k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>