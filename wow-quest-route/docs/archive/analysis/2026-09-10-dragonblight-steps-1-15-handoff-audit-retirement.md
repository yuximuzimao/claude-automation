# 龙骨荒野步骤1–15 handoff audit 退役说明（2026-09-10）

## 结论

`scripts/audit_dragonblight_steps_1_15_handoffs.py` 不是验证型审计。它只按一组写死的任务 ID，从 `dragonblight-task-foundation.json` 摘录接取/交付 NPC、前置与 next quest，输出 `dragonblight-steps-1-15-handoff-audit.json`；任务缺失只写入 `missing_qids`，不会失败退出。

定向引用检查确认，没有现役 builder、audit 或 test 读取该输出。2026-09-10 运行旧脚本得到 49 rows、missing=[]。

当前龙骨最终路线已有 `test_dragonblight_foundation_coverage_has_no_accidental_missing_tasks()` 等现役测试保护正式任务覆盖，并有玩家步骤完整覆盖、关键机制与玩家文案测试；foundation 继续是接取/交付/前置事实源。因此这份局部 foundation 摘录已完成建设期作用。

## 处理

- 旧脚本退役为 RETIRED guard。
- 旧 handoff JSON 改为 RETIRED 指引。
- 当前事实继续由 `dragonblight-task-foundation.json`、正式 route coverage 与现役 tests 负责。

本次不改变龙骨荒野路线、任务集合或玩家文案。