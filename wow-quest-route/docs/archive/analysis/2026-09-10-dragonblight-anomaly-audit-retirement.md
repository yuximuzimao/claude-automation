# 龙骨荒野 Questie anomaly audit 退役说明（2026-09-10）

## 结论

`scripts/audit_dragonblight_anomalies.py` 是建设期数据取证工具，不是长期验证门禁。它针对 11916、11930、12033、12043、12050、12051、12052、12112 八个历史异常任务重新解包 Questie，对比 raw row 与 `effective_quest_rows()` 应用 correction block 后的接交、前置和目标数据，然后输出 `dragonblight-anomaly-details.json` 供人工检查。

该输出没有任何现役 builder、audit 或 test 消费。当前正式 `build_dragonblight_foundation.py` 已通过共享的 `effective_with_boundary_refs()` 使用同一套 effective correction 机制，并把 `correction_audit` 写入 foundation 产物，因此“哪些 Questie correction 被解析并应用”已经进入正式构建链，不再依赖这份独立快照。

2026-09-10 重新运行旧脚本：Questie 11.34.0，5 个 candidate correction block 全部解析成功，failed block=0、unresolved symbol=0；有效字段变化仍集中在 11930、12033、12050、12052、12112，与原用途一致。

## 处理

- 旧脚本退役为 RETIRED guard。
- `dragonblight-anomaly-details.json` 改为 RETIRED 指引。
- 当前数据修正事实与审计证据由共享 `lib/questie_effective.py` + 正式 Dragonblight foundation 构建链维护。

若未来 Questie 升级出现新的具体异常，应重新建立针对该异常的诊断/测试，不继续依赖这八个旧任务的固定取证脚本。