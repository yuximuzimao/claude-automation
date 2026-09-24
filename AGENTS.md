# Codex Rules for Claude Workspace

本目录是从 Claude Code 工作流演进来的业务自动化工作区。Codex 在这里工作时，必须尊重既有 `CLAUDE.md` / `SKILL.md` 规则，不把它们当作普通说明文件。

## 启动顺序

进入 `/Users/chat/claude` 或任一子项目时：

1. 先读取根`AGENTS.md`和根`CLAUDE.md`。**CodexPro若要切换到具体子项目或`/Users/chat/.config/superpowers/worktrees/...`，必须先以`/Users/chat/claude`为workspace打开一次。** 外置worktree不在根目录祖先链上，禁止假设工作区总规则会自动继承。
2. 用户用中文项目名、简称或业务词描述任务时，先查 `docs/project-aliases.md` 定位英文目录；命中后进入该目录读入口文档，未命中才允许搜索。
3. 进入子项目后先读该项目`SKILL.md`，再按SKILL需要读项目`CLAUDE.md`、Todo、INDEX、CURRENT或专项SOP。根CLAUDE已定义的工作区共识不得在子项目重复一份。
4. 若旧项目缺`SKILL.md`，先读现有`CLAUDE.md/README/CURRENT`恢复最小上下文，同时明确标记“项目骨架不合规”；本次若涉及结构性维护，按`docs/new-project-template.md`补齐骨架。
5. 禁止在有`SKILL.md`的项目里先用大范围 grep/glob 搜索业务逻辑再回来读SKILL。SKILL是一级导航；存在语义歧义时继续进入项目专项SOP，不在SKILL猜分支。

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
- 修改后必须验证，但**验证范围必须服务当前目标**：先明确本轮真正要保护的契约，再选择相关测试/CLI/dry-run。历史快照测试、固定文案/步骤数/对象数量等不能自动升级为当前真值；测试与用户当前指令、实时状态或现役规则冲突时，先判断测试是否过时，禁止为了“跑绿”把正确的新状态改回旧快照。
- **已完成/已验证资产默认冻结。** 用户只授权文本、局部对象或某类同类问题时，只改授权范围；检查中发现其它结构性疑点先报告并请求确认。除非用户明确授权“同类全部修正/重构/重算”，不得因为审计或测试顺手扩大修改范围。
- **历史策略不得驱动现役实现。** 已被新规则覆盖的阶段方案、旧优先级、旧脚本和旧结论只能用于考古；不得被当前默认入口、builder、审计或测试继续读取为决策依据。若历史派生结论已经复制/硬编码进现役实现，视为架构缺陷，应从当前权威规则/数据重新推导并清除旧依赖。
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
| `order-review/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；状态见 `docs/CURRENT.md` |
| `product-ad-studio/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md` |
| `wow-quest-route/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；当前状态再按SKILL读 `docs/verified-routes/CURRENT.md` |
| `group-chat-analysis/` | `SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；当前状态按SKILL读 `docs/CURRENT.md` |

悦希/HEE 商品相关任务如涉及尚未完成视觉建档的新品，先读 `product-mapping/tasks/todo.md` 的当前新品待办。待办中已记录标准 ERP 名称、当前编码和缺失视觉资料的商品不得归为普通未知，也不得复用旧版外观或创建错误训练类别；装箱尺寸、箱规与组合规则统一由 `order-review` 自己维护。

## Codex / Claude Code 协作

- 本工作区仍保留 Claude Code 项目规则；Codex 不应覆盖或稀释这些规则。
- 启动后先读 `CLAUDE.md` → `docs/HANDOFF.md`（如果存在）→ `docs/codex-handoff/inbox.json`（检查是否有 Claude Code 发来的协作请求）→ `git status` → `git log --oneline -5`，了解 Claude Code 最新状态。
- 完成工作后更新 `docs/HANDOFF.md`（如果做了实质性改动），确保 Claude Code 下次启动能接上。
- `codex-plugin-cc` 适合做审查和救援：普通审查用 `/codex:review`，挑战设计和风险假设用 `/codex:adversarial-review`。
- 审查和修复分阶段进行。审查阶段只报告问题；修复阶段再改代码。
- `AGENTS.md` / `CLAUDE.md` / 项目 `SKILL.md` 是开工前的预防性入口；`neat-freak` 是阶段收尾兜底，必须全文审查当前活跃知识并反向审计项目是否偏离这些结构规范，包括职责混装、渐进式加载失效、重复权威、旧入口残留和Git忽略误伤。历史archive完整枚举但不默认全文重读，只检查archive索引、本轮有变更的历史文件和当前任务明确需要回溯的最近历史。`systematic-debugging` 和 `verification-before-completion` 用于 bug 和完成前验证。

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

- **工作区级项目结构、SKILL/SOP/Owner/README/INDEX/Todo/CURRENT/Archive职责、渐进式披露、现役/历史二分和无兼容层原则，唯一以根`CLAUDE.md §项目结构与文档职责`为准。** 本AGENTS只补Codex启动/工具差异，不维护第二套同义定义。
- 长期项目初始化/升级按根`CLAUDE.md` + `docs/new-project-template.md`执行；模板只负责搭骨架，不得覆盖根规则。
- 任何文件新增、删除、移动、重命名，按项目SKILL/INDEX实际职责更新导航；是否需要更新哪些入口由当前项目结构决定，不机械复制路径表。
- 稳定经验迁到其唯一owner；当前状态只进CURRENT；尚未完成事项只进Todo；历史阶段只进archive/NEAT。
- 修改`.gitignore`时必须检查匹配范围；只忽略根目录使用`/name/`。至少验证一个应该被忽略和一个不应被忽略的样本。项目文档被ignore时视为异常，不能靠`git add -f`作为长期方案。
- 跨项目影响必须同时检查上下游文档，特别是`aftersales-automation`、`product-mapping`、`sku-calculator`、`return-inbound`之间共享的 ERP / 鲸灵能力。

## 新项目 / 旧项目升级

- 用户提出“新项目/从零/初始化/scaffold”时，先执行 `docs/new-project-template.md`；只有代码目录、没有入口文档/别名/AGENTS登记/Git边界检查，不算初始化完成。
- 初始化结束前必须更新 `docs/project-aliases.md` 和本文件“子项目入口”表，并做一次空上下文冷启动：从SKILL开始，确认不靠聊天记忆也能找到当前状态、规则和核心入口。
- 旧项目不要求一次性全仓迁移；但只要本次任务涉及目录、入口、规则架构、归档结构等结构性维护，就先做骨架合规检查并补缺失入口。

## 历史上下文边界

- 不在 `AGENTS.md` 内粘贴大段记忆导出或会话摘要；这会快速过期，并稀释启动规则。
- 需要历史背景时，优先查项目自己的 `SKILL.md` / `CLAUDE.md` / `docs/INDEX.md` / `tasks/todo.md` / `CURRENT.md` / `docs/HANDOFF.md`，再按需使用记忆检索工具。
- 历史经验一旦稳定影响长期操作，应迁入对应唯一owner；当前状态只进CURRENT；不要把大段历史继续堆在AGENTS/CLAUDE/INDEX/lessons里。
