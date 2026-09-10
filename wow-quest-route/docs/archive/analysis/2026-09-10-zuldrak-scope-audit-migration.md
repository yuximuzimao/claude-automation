# 祖达克 scope audit → builder 迁移说明（2026-09-10）

## 结论

`scripts/audit_zuldrak_scope.py` 名义上是 audit，实际负责从 `northrend-task-universe.json` 生成祖达克正式任务 scope：它应用当前户外部落路线的结构性排除/纳入规则，并生成 `formal_candidate_ids`。`build_zuldrak_foundation.py` 直接读取这份结果，因此它属于 builder，不是独立审计。

## 迁移

- 现役实现：`scripts/build_zuldrak_scope.py`
- 现役输出：`data/route-atlas/zuldrak-scope.json`
- 现役报告：`docs/analysis/2026-08-19-zuldrak-scope.md`
- `build_zuldrak_foundation.py` 改读新 scope 文件。
- `tests/test_zuldrak_foundation.py` 同步改读新 scope 文件。
- 旧 audit 名、旧 `*-scope-audit.json` 和旧报告只保留 RETIRED 指引。

## 等价验证

迁移前旧脚本基线：

- assigned 134；
- formal 105；
- old auto missing 15；
- old auto extra 6；
- 状态分布：exclude_no_xp=2、exclude_repeatable_calendar=19、exclude_structural=8、include_candidate=104、include_structural_zero_xp_scripted_child=1。

新 builder 生成后，新旧 scope JSON 整份结构完全相等：`zuldrak scope payload migration exact PASS`。

随后从新 scope 重建 foundation：

- formal 105；
- dependency hard gap 0；
- cluster 149；
- shared cluster 83；
- unknown service 0。

并直接调用 `test_zuldrak_scope_and_dependency_pool_is_closed()` 通过。

本次只纠正职责、命名和输入路径，不改变祖达克任务集合、结构性例外或路线顺序。
