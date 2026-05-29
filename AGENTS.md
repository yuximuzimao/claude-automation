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

# [claude] recent context, 2026-05-29 11:06pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (13,575t read) | 418,461t work | 97% savings

### May 29, 2026
1050 6:46p ⚖️ 商品转移功能将从 product-mapping 独立为单独项目
1051 6:53p 🔄 transfer 功能独立项目开始创建
1052 " 🔄 三个核心文件已复制到独立项目
S377 修复 zip 包在 Windows 上中文文件名乱码的编码问题 (May 29 at 6:54 PM)
1053 6:54p 🔄 generate.js 重构完成——zip 输出路径改为桌面
1056 " 🔄 Task 6 完成——独立项目创建闭环，Task 5 开始清理
1054 " 🟣 独立 CLI 入口 cli.js 创建完成——命令改为 collect/pack
1055 " 🟣 SKILL.md + CLAUDE.md + package.json 创建完成
1057 " 🔄 旧项目残留开始清理——lib/transfer/ 和 data/transfers/ 已删除
1058 " 🔄 发现 cli.js 中 transfer 残留引用——transfer-pack 行待清理
1059 " 🔵 product-mapping/cli.js 转移残留范围确认——12 行需清理
1060 6:55p 🔴 cli.js Python 清理脚本失败——中转命令块未被移除
1061 " 🔴 cli.js 从 git HEAD 恢复——Python 清理脚本误删后的抢救
1062 " 🔵 product-mapping/SKILL.md 也有 12 行转移残留需清理
1063 " 🔄 SKILL.md 转移残留已清理——关键字行过滤删除
S378 修复 zip 包在 Windows 上中文文件名乱码的编码问题 (May 29 at 6:56 PM)
1087 7:00p 🔵 Zip encoding fix: generate.js being investigated
1088 7:03p 🔵 Zip encoding fix: full zip creation code revealed
1089 7:04p 🔴 Zip encoding fix implemented: macOS zip replaced with Python zipfile
1090 " 🔵 Python zipfile UTF-8 flag test passed: fix verified
1091 " 🔴 Zip encoding fix fully verified: UTF-8 flag confirmed for Chinese filenames
1092 " 🔴 Zip encoding fix closed: node --check passed, fix fully verified
S379 修复 zip 包 Windows 中文乱码 + 最终清理验证 (May 29 at 7:04 PM)
1094 7:05p ✅ Project file inventory confirmed: transfer and product-mapping structure intact
1095 " 🔵 Product-mapping decontamination confirmed: zero transfer references in SKILL.md
1096 " 🔵 MEMORY.md index still shows old transfer project description
1097 " ✅ MEMORY.md index updated to reflect independent transfer project
1098 " ✅ Obsolete plan file vast-roaming-crescent.md deleted
S380 重复的进度总结请求 — 确认全部工作已闭环 (May 29 at 7:05 PM)
S384 User asked Claude Code to call Codex CLI and negotiate a collaboration protocol between the two agents (May 29 at 7:06 PM)
1112 9:29p 🔵 Codex CLI and Claude Code dual-agent collaboration model explored
1113 9:30p 🔵 Codex CLI config.toml confirmed with MCP server and plugin state
S385 用户要求 Claude Code 主动调用 Codex CLI 协商两个 agent 的协作协议 (May 29 at 9:30 PM)
S381 User asked how Codex CLI and Claude Code collaborate when working in the same shared directory, after adding Codex alongside existing Claude Code workflow (May 29 at 9:30 PM)
S383 查询 superpowers、pua、neat-freak 三个技能的 Git 仓库地址（安装来源） (May 29 at 9:30 PM)
1122 9:37p 🔵 Three skills' git repository addresses confirmed
S386 neat-freak — 工作区文档/内存洁癖级审计与同步修复 (May 29 at 9:38 PM)
1160 10:08p 🔵 Codex CLI `codex exec` cross-agent handshake succeeded despite persistent WebSocket failures
1161 " ✅ End-of-session knowledge cleanup with neat-freak skill
1148 10:09p 🔵 Codex CLI command surface mapped for Claude Code integration
1149 10:11p 🔵 Claude Code invoked Codex CLI via `codex exec` to negotiate collaboration protocol
1150 " 🔄 CLAUDEMD reloaded — project rules reviewed
1151 " 🔵 Shared workspace structure and hook system investigated
1152 " ⚖️ Collaboration handoff method discussed between sessions
1153 10:12p 🔵 Claude Code and Codex dual CLI environment mapped
1154 " 🔵 Codex plugin hook infrastructure mapped
1155 " 🔵 Session lifecycle hook internals understood
1156 " 🔵 Stop-time review gate blocks session end on code issues
1157 " 🔵 Jingling multi-account session management system documented
1158 " 🔵 Codex companion state persistence internals revealed
1159 " 🔵 Workspace root directory structure fully enumerated
1162 10:24p 🔵 neat-freak 内存审计发现 33 个孤儿文件
1163 10:25p 🔵 CLAUDE.md 与 AGENTS.md / HANDOFF.md 零引用——文档层断裂
1164 " ✅ CLAUDE.md Git scope 新增 transfer 子项目
1165 " ✅ CLAUDE.md 新增 Codex 协作章节与 AGENTS.md/HANDOFF.md 引用
1166 " 🔵 AGENTS.md 同样不引用 HANDOFF.md——双向断裂
1167 10:26p ✅ AGENTS.md 新增 HANDOFF.md 引用——双向文档断裂修复完成
S387 neat-freak — 工作区文档/内存洁癖级审计完成 (May 29 at 10:26 PM)
1183 10:59p ⚖️ Git backup strategy for AI change recovery
1184 11:01p ⚖️ Codex Git optimization plan reviewed with risk assessment

Access 418k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>