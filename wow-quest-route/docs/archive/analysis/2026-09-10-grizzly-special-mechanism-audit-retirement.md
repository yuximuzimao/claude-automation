# 灰熊丘陵 special-mechanism audit 退役说明（2026-09-10）

## 结论

`scripts/audit_grizzly_hills_special_mechanisms.py` 已退役。

它原本维护一份 35 项手工 `MANUAL` 机制表，并生成 `grizzly-hills-special-mechanism-audit.json`。现役 `build_grizzly_hills_route.py` 实际只读取其中的 `fivebox_check`，不读取这些机制事实本身；玩家真正看到的机制说明已经由 `scripts/grizzly_semantic_steps.py` 维护，已确认的五开事实则记录在 `data/observations/fivebox-task-types.json`。

2026-09-10 灰熊首组完成后，该副本暴露出实际维护风险：正式路线已经只剩 2 个待确认项，而专项 MANUAL 表仍残留 13 个旧 `fivebox_check`。用户补充《有趣的计划》与《寻找溶解剂》后，正式路线和专项表都先校准到 0 个待确认项，再进行退役。

## 退役前覆盖检查

- MANUAL 项数：35。
- 35/35 任务名均存在于现役 `grizzly_semantic_steps.py`。
- 更严格地检查最终生成的灰熊玩家备注后，35/35 任务也都有对应玩家机制备注；不存在“只有专项审计报告里才有、正式玩家路线没有”的任务。
- `grizzly-hills-special-mechanism-audit.json` 的唯一现役代码消费者是 `build_grizzly_hills_route.py`，且只用于旧 `fivebox_check` 中转。

## 解耦验证

退役依赖前先构建灰熊路线并对 `workbench-routes.json["grizzly"]` 做规范化 JSON SHA-256：

`7e6f563d4a27dbaa2e3f3f038eb8f9ad5023cb89575021871037a3d38d0c23bb`

随后移除 route builder 对 `grizzly-hills-special-mechanism-audit.json` 的读取；旧 baseline `fb()` 仅保留为空值兼容层，现役五开不确定性由 semantic override 唯一维护。重新构建后：

- 83/83 formal tasks；
- 79 points；
- 19 player steps；
- fivebox_check_point_count = 0；
- route SHA-256 仍为 `7e6f563d4a27dbaa2e3f3f038eb8f9ad5023cb89575021871037a3d38d0c23bb`。

因此退役不会改变玩家路线。

## 当前 owner

- 玩家可见机制与尚未确认的五开提示：`scripts/grizzly_semantic_steps.py`
- 已确认的共享/不共享/拾取规则：`data/observations/fivebox-task-types.json`
- 灰熊正式任务池：`build_grizzly_hills_scope.py → grizzly-hills-scope.json → build_grizzly_hills_foundation.py`

旧专项审计脚本、JSON 和 analysis 报告只保留 RETIRED 指引；历史内容继续由 git 历史和既有 archive 保存。
