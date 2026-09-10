# 灰熊丘陵 scope audit → builder 迁移说明（2026-09-10）

## 结论

`scripts/audit_grizzly_hills_scope.py` 名义上是 audit，实际上承担正式 scope 的生成职责：它从 `northrend-task-universe.json` 按当前部落/血精灵/圣骑士/户外全清策略筛选任务，应用结构性排除，并递归补回必需的零经验前置，最后产出 `formal_candidate_ids`。`build_grizzly_hills_foundation.py` 直接把这份结果作为上游输入。

因此它不是“检查既有事实是否正确”的审计器，而是 scope builder。继续以 `audit_*` 命名会违反当前审计治理原则，也会让后续维护者误以为删除该脚本只会少一层检查，实际上会切断 foundation 输入。

## 迁移

- 现役实现迁为 `scripts/build_grizzly_hills_scope.py`。
- 现役输出迁为 `data/route-atlas/grizzly-hills-scope.json`。
- 现役报告迁为 `docs/analysis/2026-08-18-grizzly-hills-scope.md`。
- `scripts/build_grizzly_hills_foundation.py` 改读新的 scope 文件。
- 旧 `audit_grizzly_hills_scope.py`、`grizzly-hills-scope-audit.json` 和旧 scope-audit 报告只保留 RETIRED 提示，防止历史命令/文件名继续冒充现役审计。

## 等价验证

迁移前先运行旧脚本，基线为：assigned/原 touching 170项、formal 83项；status counts 为 `exclude_deprecated=1 / exclude_faction=68 / exclude_no_xp=3 / exclude_repeatable_calendar=10 / exclude_structural=5 / include_candidate=83`；相对旧自动路线新增8项、额外0项。

新 builder 运行后，新旧 scope JSON 做整份结构相等比较，结果为 `scope payload migration exact PASS`。随后 `build_grizzly_hills_foundation.py` 已实际从新 scope 输入构建成功：formal 83、dependency hard gap 0、69 clusters、5 shared clusters、unknown service 0。

本次只纠正职责和命名，不改变灰熊任务集合、结构排除、任务顺序或玩家路线。
