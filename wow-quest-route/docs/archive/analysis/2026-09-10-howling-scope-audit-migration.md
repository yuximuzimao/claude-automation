# 嚎风峡湾 scope audit → builder 迁移说明（2026-09-10）

## 结论

`scripts/audit_howling_scope.py` 名义上是 audit，实际上负责从 `northrend-task-universe.json` 生成嚎风正式任务 scope：它按当前部落/血精灵/圣骑士/户外一次性任务策略筛选任务，应用结构性排除，并补回依赖数据证明为必需的零经验前置。`build_howling_foundation.py` 直接读取它生成的 `formal_candidate_ids`。

因此它属于 builder，而不是对既有任务池做验证的 audit。

## 迁移

- 现役实现迁为 `scripts/build_howling_scope.py`。
- 现役输出迁为 `data/route-atlas/howling-fjord-scope.json`。
- 现役报告迁为 `docs/analysis/2026-08-26-howling-fjord-scope.md`。
- `scripts/build_howling_foundation.py` 改读新的 scope 文件。
- 旧 `audit_howling_scope.py`、`howling-fjord-scope-audit.json` 与旧 scope-audit 报告仅保留 RETIRED 指引。

## 等价验证

迁移前旧脚本基线：

- assigned 219；
- formal 111；
- `exclude_deprecated=2 / exclude_faction=103 / exclude_no_xp=1 / exclude_repeatable_calendar=1 / exclude_structural=1 / include_candidate=111`；
- 相对旧自动候选新增25项、旧自动多出1项。

新 builder 运行后，新旧 scope JSON 整份结构相等：`howling scope payload migration exact PASS`。

随后实际从新 scope 重建 foundation 与路线：

- foundation：111 formal、dependency hard gap 0、112 clusters、8 shared clusters；
- route：111/111、133 points、31 steps；
- `audit_howling_route_candidate.py`：PASS；missing accept / missing turn-in / duplicate accept / duplicate turn-in / dependency violations / parent-active violations 全部为0。

本次只纠正职责、命名和输入路径，不改变嚎风正式任务集合或路线顺序。
