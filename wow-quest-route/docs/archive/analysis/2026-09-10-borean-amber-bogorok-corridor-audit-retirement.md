# 北风苔原琥珀崖→博古洛克走廊审计退役说明（2026-09-10）

## 结论

`scripts/audit_borean_amber_bogorok_corridor.py` 是一次性路线优化诊断：针对当时固定的 Route Atlas point 169（琥珀崖）→170（博古洛克）强制陆路段，用任务起点几何位置 + 该时点前置状态筛选是否有本可顺路接取却遗漏的任务。

它不参与正式路线构建，也没有任何现役 builder、audit 或 test 读取 `borean-amber-bogorok-corridor-audit.json`。此外脚本依赖硬编码 point index，若以后路线点位重排，旧数字会失去语义，因此不适合作为长期门禁。

2026-09-10 按当前正式路线重新运行：

- corridor task starts：1；
- interior task starts：1；
- scheduled later interior：0；
- outstanding interior：0；
- Bogorok endpoint：0。

即当前没有可补的沿路任务，原建设问题已经闭环。

## 处理

- 旧脚本退役为 RETIRED guard。
- 旧 corridor audit JSON 改为 RETIRED 指引。
- 当前北风路线继续由正式 Route Atlas、foundation 与现役覆盖/玩家步骤测试保护。

若未来重新设计琥珀崖→博古洛克段，应基于届时的路线语义重新做局部几何检查，而不是复用这组旧 point index。