# 灰熊丘陵 handoff 辅助链退役说明（2026-09-09）

## 结论

`scripts/audit_grizzly_hills_handoffs.py` 不是真正的审计器：它只从 `grizzly-hills-task-foundation.json` 抽取任务ID、接/交实体、前置与 next quest，再写出 `grizzly-hills-handoff-audit.json`；没有 PASS/FAIL、差集、依赖判断或路线执行验证。

它的唯一消费者 `scripts/summarize_grizzly_hills_handoffs.py` 只是把上述快照转成 `.ai-bridge/grizzly-handoff-summary.md`，供灰熊建设期人工阅读。项目中没有现役 builder、audit 或 test 依赖这两个脚本或该 summary。

当前有效保护已经由以下现役层承担：

- `grizzly-hills-task-foundation.json` 保存接/交实体、前置和 dependency hard-gap 状态；
- `grizzly-hills-route-coverage.json` 检查正式任务是否全部进入路线；
- `tests/test_grizzly_hills_route.py` 检查 formal task count、dependency hard gap、coverage missing/unexpected、交通等当前契约；
- `audit_route_atlas_*` 通用审计继续承担玩家文案、交通/飞行等跨地图约束。

因此这条 handoff 辅助链属于已完成建设阶段的重复快照，不再保留为现役 audit。旧文件名改为 RETIRED guard，防止历史命令继续生成看似“审计结果”的无判断快照；历史内容由 Git 与本说明追溯。

`audit_grizzly_hills_scope.py` 不在本次退役范围。它仍承担灰熊正式任务池的结构性筛选/依赖闭包职责，需要后续单独审查，不能与 handoff 辅助链批量处理。
