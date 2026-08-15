# Codex Rules for Claude Workspace

本目录是从 Claude Code 工作流演进来的业务自动化工作区。Codex 在这里工作时，必须尊重既有 `CLAUDE.md` / `SKILL.md` 规则，不把它们当作普通说明文件。

## 启动顺序

进入 `/Users/chat/claude` 或任一子项目时：

1. 先读当前目录的 `CLAUDE.md`。
2. 用户用中文项目名、简称或业务词描述任务时，先查 `docs/project-aliases.md` 定位英文目录；命中后进入该目录读入口文档，未命中才允许搜索。
3. 如果进入子项目，先读该子项目的 `SKILL.md`，再读 `CLAUDE.md`。若旧项目缺 `SKILL.md`，先读现有 `CLAUDE.md/README/CURRENT` 恢复最小上下文，同时明确标记“项目骨架不合规”；本次若涉及结构性维护，先按 `docs/new-project-template.md` 补齐骨架。
4. 再读该子项目的 `tasks/todo.md` 和 `docs/INDEX.md`；不存在时不得猜测其职责，按项目入口表与现有文件工作。正常项目按 `SKILL.md` 的 DO FIRST 决定是否继续加载其它文档。
5. 禁止在有 `SKILL.md` 的项目里先用大范围 grep/glob 搜索业务逻辑再回来读SKILL。`SKILL.md` 是导航地图，先看地图再走路。

## 工作区红线

- 真实业务系统写操作必须人工确认：退款、拒绝、入库、匹配写入、批量修改、提交确认、账号登录都属于高影响操作。
- 鲸灵 `scrm.jlsupp.com` 行为操作报错即停，绝不自动重试第二次。重复失败会触发风控。
- ERP 操作必须串行；同一浏览器 session、同一 tab、同一账号登录流程禁止并行。
- 验证数据必须读实时源头：从 ERP 页面、CLI 或当前文件重新读取，禁止把历史 jsonl 快照当真值。
- DOM 操作必须过滤可见元素；Element UI 弹窗必须走 Vue/按钮关闭流程，禁止直接移除 DOM。
- 截图只作为补充证据，网页操作优先用 DOM 状态和真实数据源确认。
- 所有图片生成与图片编辑默认禁用连续意图：只允许依据用户当前消息中的明确执行命令调用一次，禁止继承上一轮的生图/编辑意图。普通分析、反馈、确认、讨论和“继续”只能文字回复；每次调用后立即恢复讨论模式。
- 禁止在本工作区使用 `scripts/image_gen.py`、OpenAI Images API、`OPENAI_API_KEY` 或任何 CLI/API 备用生图路径。内置生图工具不可用时不得自动降级。

## 项目主力工作方式

- 默认个人本地使用：只写解决问题所需的最少代码，不加推测性功能，不为一次性使用建抽象；除非是大型或高风险任务，不套用上线标准和完整设计流程。
- 流程从简不等于逻辑从简；仍要弄清输入、状态、边界、失败方式和写入影响。售后、审单、ERP 写操作等高风险业务必须严格验证。
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
| `order-review/` | 当前旧结构：项目内 `AGENTS.md`、`CLAUDE.md`、`README.md`、`docs/CURRENT.md`；缺 `SKILL.md/tasks/todo.md/docs/INDEX.md`，下次结构性维护先按新项目规范补骨架 |
| `product-ad-studio/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |
| `wow-quest-route/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；当前状态再按SKILL读 `docs/verified-routes/CURRENT.md` |

## Codex / Claude Code 协作

- 本工作区仍保留 Claude Code 项目规则；Codex 不应覆盖或稀释这些规则。
- 启动后先读 `CLAUDE.md` → `docs/HANDOFF.md`（如果存在）→ `docs/codex-handoff/inbox.json`（检查是否有 Claude Code 发来的协作请求）→ `git status` → `git log --oneline -5`，了解 Claude Code 最新状态。
- 完成工作后更新 `docs/HANDOFF.md`（如果做了实质性改动），确保 Claude Code 下次启动能接上。
- `codex-plugin-cc` 适合做审查和救援：普通审查用 `/codex:review`，挑战设计和风险假设用 `/codex:adversarial-review`。
- 审查和修复分阶段进行。审查阶段只报告问题；修复阶段再改代码。
- `AGENTS.md` / `CLAUDE.md` / 项目 `SKILL.md` 是开工前的预防性入口；`neat-freak` 是阶段收尾兜底，必须全文审查当前活跃知识并反向审计项目是否偏离这些结构规范，包括职责混装、渐进式加载失效、重复权威、旧入口残留和Git忽略误伤。历史archive完整枚举但不默认全文重读，只检查archive索引、本轮有变更的历史文件和当前任务明确需要回溯的最近历史。`systematic-debugging` 和 `verification-before-completion` 用于 bug 和完成前验证；`pua` 只在反复失败、被动等待或用户明确触发时使用。

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

## 项目结构与文档维护

- 长期项目的标准骨架与初始化门禁统一以根 `CLAUDE.md` + `docs/new-project-template.md` 为准；Codex不得维护另一套项目规范。
- 正常长期项目至少有 `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；有持续变化现场状态时另设 `CURRENT.md` 作为唯一当前真值。README只做人类概览，不复制CURRENT。
- `docs/INDEX.md` 默认是导航，不是无限扩张的规则正文。项目出现多个独立规则域/工作流，或一次读INDEX会加载大量无关规则时，建立 `docs/rules/README.md` 并按主题渐进式拆分。
- 稳定经验从 `tasks/lessons.md` 迁到正确归属：跨批次方法→`docs/rules/`；重复错误→error book/known pitfalls；单对象事实→对应知识库/observations；当前状态→CURRENT；历史阶段→archive/NEAT。迁移后删掉lessons重复项。
- 新项目历史默认用 `docs/archive/`；运行时/认证会话才使用根或运行目录 `sessions/`。现有 `docs/**/sessions/` 可保留为历史文档，但必须正常版本管理。
- 任何文件新增、删除、移动、重命名，都要同步所属项目 `SKILL.md` PATHS/ENTRY MAP、`docs/INDEX.md` 和当前入口链接。被新结构替代的旧权威文件在内容迁移和引用审计完成后直接删除；除非有明确外部消费者，不保留兼容跳转壳。
- 修改 `.gitignore` 时必须检查匹配范围；只忽略根目录使用 `/name/`。至少验证一个应该被忽略和一个不应被忽略的样本。项目文档被ignore时视为异常，不能靠 `git add -f` 作为长期方案。
- 跨项目影响必须同时检查上下游文档，特别是 `aftersales-automation`、`product-mapping`、`sku-calculator`、`return-inbound` 之间共享的 ERP / 鲸灵能力。

## 新项目 / 旧项目升级

- 用户提出“新项目/从零/初始化/scaffold”时，先执行 `docs/new-project-template.md`；只有代码目录、没有入口文档/别名/AGENTS登记/Git边界检查，不算初始化完成。
- 初始化结束前必须更新 `docs/project-aliases.md` 和本文件“子项目入口”表，并做一次空上下文冷启动：从SKILL开始，确认不靠聊天记忆也能找到当前状态、规则和核心入口。
- 旧项目不要求一次性全仓迁移；但只要本次任务涉及目录、入口、规则架构、归档结构等结构性维护，就先做骨架合规检查并补缺失入口。

## 历史上下文边界

- 不在 `AGENTS.md` 内粘贴大段记忆导出或会话摘要；这会快速过期，并稀释启动规则。
- 需要历史背景时，优先查项目自己的 `SKILL.md` / `CLAUDE.md` / `docs/INDEX.md` / `tasks/todo.md` / `CURRENT.md` / `docs/HANDOFF.md`，再按需使用记忆检索工具。
- 历史经验一旦稳定影响长期操作，应迁入对应 `docs/rules/` 或项目稳定规则文件；当前状态只进CURRENT；不要把大段历史继续堆在AGENTS/CLAUDE/INDEX/lessons里。
