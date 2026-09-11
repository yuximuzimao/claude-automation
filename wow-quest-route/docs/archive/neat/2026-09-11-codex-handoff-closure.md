# 2026-09-11 Codex 工程交接闭环 NEAT

## 阶段结论

`tasks/codex-handoff.md` 中两项受权限限制的工程收尾均已完成：

1. 赞加 Route Atlas 已从现役生成源码重新物化，唯一正式工作台已重建。
2. Python 3.13 独立虚拟环境能够安装项目 `test` extra，指定 pytest 用例通过。

原活跃交接文件已经移入本历史记录，`tasks/` 重新只保留当前业务待办与临时教训。

## 赞加正式产物同步

执行 `scripts/refactor_zang_route.py` 后，`data/route-atlas/workbench-routes.json` 的赞加路线已与 `scripts/zang_semantic_steps.py` 一致：

- 步骤10与步骤13中，《多头蛇之王》《猎杀恐爪》都只在“若已完成”时交付；未完成时继续保留，不等待刷新。
- 玩家动作文本与 `actionHtml` 使用相同条件语义。
- 正式 `data/routes/route-atlas-workbench.html` 已通过 `scripts/build_route_atlas_workbench.py` 重建。

结构对比确认：其它地图完全未变；赞加仍为57个几何点、13个玩家步骤，坐标、步骤范围、任务集合和接/做/交事件顺序均未变化。

重建时还确认工作台构建器会在每次替换内联补丁区后累积空行，造成同一输入重复构建仍产生无意义 diff。`scripts/build_route_atlas_workbench.py` 已统一清理补丁边界空白；连续构建两次得到相同 SHA-256，正式 HTML 回到幂等生成。

## 生成器一致性修正

首次重新物化时还发现两处源码与正式条件语义不一致：

- 《赞加沼泽的植物》备注要求“五号都够10株才交”，源码动作却会生成无条件交付。
- 《枯萎的孢芽》属于随机掉落触发任务，备注要求“没掉就忽略”，源码动作却会生成无条件交付。

已在 `scripts/zang_semantic_steps.py` 中把两处玩家动作和 `actionHtml` 都改为条件交付。这样以后再次运行正式生成链，不会把已正确的路线重新改坏。

NEAT 反向引用审计还发现 `scripts/rewrite_route_atlas_player_copy.py` 是无调用方的一次性旧改写脚本，内部会把上述条件交付重新改回无条件交付。该脚本已移入 `docs/archive/scripts/`，退出现役实现链；历史内容保留用于考古，但不得作为 builder、audit、test 或 CLI 入口。

## 可重复测试环境

首次在全新 Python 3.13 虚拟环境执行 `pip install -e '.[test]'` 时，setuptools 因扁平目录中同时发现 `lib` 与 `data` 而拒绝构建。只声明 pytest extra 仍不足以形成可重复安装流程。

修正如下：

- `pyproject.toml` 用 `[tool.setuptools] packages = ["lib"]` 明确唯一 Python 包，禁止把 `data/` 误识别为包。
- `.gitignore` 忽略项目根 `/.venv/`，避免本地测试环境进入版本管理。
- `tests/README.md` 补充 Python 3.13 建立 `.venv`、安装 `test` extra 和运行 pytest 的完整命令。

在全新隔离环境中重新安装成功，项目依赖仍遵守原有版本范围，没有修改系统 Python。

## 验证

- `scripts/refactor_zang_route.py`：成功，57点、13步骤、13个语义步骤。
- `scripts/build_route_atlas_workbench.py`：成功重建唯一正式 HTML。
- 同一输入连续构建两次：HTML SHA-256 一致。
- `scripts/audit_route_atlas_action_sequence.py zang`：自动异常信号为“无”。
- `scripts/audit_route_atlas_player_text.py`：`player-text audit PASS`。
- `tests/test_route_atlas_workbench.py::test_player_visible_handoffs_are_explicit_and_lifecycle_closes`：`1 passed`。
- HTML 内联 JavaScript 提取后执行 `node --check`：通过。
- `tests/test_rule_routing.py`：验证历史脚本没有重新进入现役代码引用。

## 未改变的当前状态

本次只完成工程交接，没有改动首组实跑进度、任务集合、路线顺序、估时模型或 `tasks/todo.md`。当前恢复点继续以 `docs/verified-routes/CURRENT.md` 为唯一真值：从新阿加曼德首轮接任务阶段继续嚎风峡湾实跑。
