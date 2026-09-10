# 索拉查 route-skeleton audit 退役说明（2026-09-10）

## 结论

`scripts/audit_sholazar_route_skeleton.py` 名义上是 audit，实际上只把 `sholazar-task-foundation.json` 中 66 个正式任务按接取/交付坐标做粗粒度地理分箱。它不会对未锚定任务或分箱结果执行 PASS/FAIL，也没有现役 builder、audit 或 test 读取 `sholazar-route-skeleton-audit.json`。

当前真正承担索拉查骨架保护的是：

- `build_sholazar_route_skeleton.py`：检查正式池覆盖、额外任务、重复任务和强制前置顺序；失败会退出。
- 后续 inserted-route / whole-map merge 链：检查重复 Spatial Instance 是否有合理解释、是否存在有害拆分。

2026-09-10 复核运行：

- route skeleton：66/66，missing=[]，extra=[]，duplicates=[]，dependency order violations=0；
- whole-map merge audit：PASS，6 个重复实例全部已解释，harmful split=0。

因此旧 spatial-bin audit 已完成建设期辅助使命，继续保留只会制造一个无人消费、也不判错的“假审计”。

## 处理

- `scripts/audit_sholazar_route_skeleton.py` 退役为 RETIRED guard。
- `data/route-atlas/sholazar-route-skeleton-audit.json` 改为 RETIRED 指引。
- 正式骨架继续由 `build_sholazar_route_skeleton.py` 及后续 merge audit 保护。

本次不改变索拉查路线、任务集合或地图顺序。