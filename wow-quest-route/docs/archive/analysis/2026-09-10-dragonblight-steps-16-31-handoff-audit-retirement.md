# 龙骨荒野步骤16–31 handoff audit 退役说明（2026-09-10）

## 结论

`scripts/audit_dragonblight_steps_16_31_handoffs.py` 只按写死任务 ID 从 `dragonblight-task-foundation.json` 摘录接取/交付 NPC、前置与 next quest，输出局部 handoff JSON；即使任务缺失也只记录 `missing_qids`，不会失败退出。

定向引用检查确认没有现役 builder、audit 或 test 读取该输出。2026-09-10 运行旧脚本得到 50 rows、missing=[]。

龙骨正式 route coverage 与现役 tests 已直接保护任务覆盖、步骤覆盖、关键机制和玩家文案，因此该局部 foundation 摘录已完成建设期作用。

## 处理

- 旧脚本退役为 RETIRED guard。
- 旧 handoff JSON 改为 RETIRED 指引。
- 当前事实继续由 `dragonblight-task-foundation.json`、正式 route coverage 与现役 tests 负责。

本次不改变龙骨荒野路线、任务集合或玩家文案。