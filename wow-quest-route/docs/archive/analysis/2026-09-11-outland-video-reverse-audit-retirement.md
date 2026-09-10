# 外域 video reverse audit 退役说明（2026-09-11）

## 结论

`scripts/audit_outland_video_reverse.py` 是 2026-08-20 视频 POST 阶段针对赞加沼泽 / 纳格兰的一次性路线纠错分析，不符合当前“正式路线冻结前整图视频反向审查门禁”的长期职责。

它仍能重算“视频独有任务离当前路线多远”等候选信息，但存在四个结构性问题：

- 没有比较共同保留任务的相对顺序 / 邻接关系，因此只覆盖现行视频反查规则的一部分；
- 没有 PASS/FAIL 或阻断退出码，不能作为真正 gate；
- 直接读取历史 `_sandbox/sources/Questie-v11.32.3.zip`，而项目当前正式 Questie 已是 11.34.0；
- 大量赞加恢复项、纳格兰排除项和 `10109→10111` 等人工结论硬编码在脚本里，属于当时路线状态的人工分类，不应长期伪装成通用审计引擎。

项目内没有现役 builder、audit 或 test 消费 `data/video-route/outland-route-reverse-audit.json`。2026-08-20 的实际结论已经由 `docs/archive/video/neat/2026-08-20-video-collection-complete-neat.md` 和 `docs/archive/analysis/video-route-outland-reverse-audit.md` 保留；其中 `10109→10111` 鸟蛋链“未来专项压缩纳格兰冲刺候选、暂不替换当前稳定基线”的结论也已写入 `docs/video-extraction/CURRENT.md`，不会因退役脚本而丢失。

2026-09-11 重新运行旧脚本时，它仍只给出视频独有候选分类：赞加共同任务15；纳格兰共同任务12、41个视频独有候选、0个 `route_overlap_review`。与此同时当前路线任务计数已经与历史基线变化，进一步说明这份脚本会把新路线状态套入旧人工分类，而不是执行一次完整的新终审。

## 处理

- `scripts/audit_outland_video_reverse.py` 退役为 RETIRED guard。
- `data/video-route/outland-route-reverse-audit.json` 改为 RETIRED 指引，避免被误当当前门禁结果。
- 历史分析报告继续保留在 archive。
- `docs/video-extraction/CURRENT.md` 不再把该 JSON 列为当前可重复审计入口，只保留 canonical 视频事件 / 地图索引及历史终审记录。

如果未来赞加或纳格兰发生足以重新触发视频终审的路线重构，应按 `docs/rules/route-atlas-optimization.md` 当前规则建立新的整图反向审查：使用当前正式任务事实源，先过滤阵营/副本/互斥/明确排除项，再同时检查遗漏与共同任务相对顺序/邻接，并让未解释项真正阻断通过；不要复用这份绑定 2026-08-20 冲刺状态的脚本。
