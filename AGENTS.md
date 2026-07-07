# Codex Rules for Claude Workspace

本目录是从 Claude Code 工作流演进来的业务自动化工作区。Codex 在这里工作时，必须尊重既有 `CLAUDE.md` / `SKILL.md` 规则，不把它们当作普通说明文件。

## 启动顺序

进入 `/Users/chat/claude` 或任一子项目时：

1. 先读当前目录的 `CLAUDE.md`。
2. 用户用中文项目名、简称或业务词描述任务时，先查 `docs/project-aliases.md` 定位英文目录；命中后进入该目录读入口文档，未命中才允许搜索。
3. 如果进入子项目，先读该子项目的 `SKILL.md`，再读该子项目的 `CLAUDE.md`。
4. 再读该子项目的 `tasks/todo.md` 和 `docs/INDEX.md`，按 `SKILL.md` 的 DO FIRST 决定是否继续加载其他文档。
5. 禁止在读 `SKILL.md` 前先用大范围 grep/glob 搜索业务逻辑。`SKILL.md` 是导航地图，先看地图再走路。

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

中文名和触发词只维护在 `docs/project-aliases.md`；本表只维护目录进入后的必读文件。

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
| `codex-monitor/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |

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


## 历史上下文边界

- 不在 `AGENTS.md` 内粘贴大段记忆导出或会话摘要；这会快速过期，并稀释启动规则。
- 需要历史背景时，优先查项目自己的 `SKILL.md` / `CLAUDE.md` / `docs/INDEX.md` / `tasks/todo.md` / `docs/HANDOFF.md`，再按需使用记忆检索工具。
- 如果某条历史经验已经稳定影响操作规则，应迁入对应项目 `docs/INDEX.md` 或根/项目 `CLAUDE.md`，不要长期停留在临时记忆块。
