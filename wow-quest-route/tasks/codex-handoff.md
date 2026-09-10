# Codex 统一收尾交接

用途：记录当前 ChatGPT/CodexPro MCP 因权限或工具边界无法安全完成、需要后续由 Codex 在本地工作区统一处理的工程事项。这里不记录等待用户实跑的任务，也不替代 `tasks/todo.md`。

## 待处理

### 1. 重新物化赞加 Route Atlas 正式产物

背景：2026-09-09 审计治理时，`scripts/zang_semantic_steps.py` 已修正步骤10的条件交付语义：

- 《多头蛇之王》《猎杀恐爪》在步骤10只有“若已完成”才交；未完成则继续保留。
- `actionHtml` 同步使用 `conditional_npc_turn_line(...)`。
- 源码步骤13本来就已经是“若已完成”条件交付。

当前正式 `data/route-atlas/workbench-routes.json` 的赞加内容比源码旧：步骤13仍物化为无条件交付，步骤10也尚未包含本次源码修正。

当前 MCP 无法安全完成正式产物同步：

- 直接运行 `scripts/refactor_zang_route.py` 会写正式 Route Atlas JSON，被当前 CodexPro MCP 安全门拒绝。
- `workbench-routes.json` 超过 MCP 精确文本编辑的安全大小限制，不应绕过限制强行手改。

后续 Codex 处理方式：

1. 在确认工作区未有冲突改动后运行正常的赞加生成/重构链，重新物化 `zang`。
2. 确认步骤10和步骤13的《多头蛇之王》《猎杀恐爪》都表现为条件交付，不改变任务集合或路线顺序。
3. 重新构建 Route Atlas workbench 页面。
4. 仅运行与本次物化直接相关的最小验证：赞加 action-sequence 诊断、player-text，以及因正式 JSON/HTML 同步而必要的构建检查；不要借机重算其它地图或历史模型。

本项只属于“源码已正确、正式生成产物待同步”，不是等待实跑反馈事项。

### 2. 恢复可重复的 pytest 测试环境并重跑目标测试

背景：项目存在 `.pytest_cache`，其中记录了约160个历史测试节点，说明 pytest 过去实际运行过；但 `pyproject.toml` 之前没有声明 pytest 测试依赖。当前 CodexPro MCP 使用的 Python 3.14 环境执行 `python3 -m pytest ...` 时提示 `No module named pytest`。

本轮已经做的工程修正：

- `pyproject.toml` 新增 `[project.optional-dependencies].test = ["pytest"]`，以后测试依赖不再依赖机器全局环境偶然安装。
- `tests/README.md` 已明确测试应使用安装了 `test` extra 的项目 Python 环境。
- 本轮目标测试 `tests/test_route_atlas_workbench.py::test_player_visible_handoffs_are_explicit_and_lifecycle_closes` 的实际业务逻辑已经通过直接运行 `scripts/audit_route_atlas_player_text.py` 验证为 PASS；缺的是 pytest 集成入口本身的环境验证。

后续 Codex 处理方式：

1. 使用项目合适的 Python/venv 安装测试 extra；不要改系统 Python，也不要为此升级项目其它依赖。
2. 先只运行 `tests/test_route_atlas_workbench.py::test_player_visible_handoffs_are_explicit_and_lifecycle_closes`。
3. 若该目标测试 PASS，即认为本项完成；不要顺手跑全量 pytest 或修与本轮无关的历史快照失败。
4. 若测试失败，先判断是本轮 player-text 审计改动的真实回归还是旧快照/环境差异；禁止为了跑绿恢复旧路线或削弱有效审计。

本项是测试环境可重复性收尾，Codex 本地执行能力应可完成。
