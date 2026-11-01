# 当前状态

更新时间：2026-11-01

## 当前方向

Runner 已切换到 V2：

> 固定流程 + 固定网格/坐标 + 小 ROI 找图/找色 + 异常 STOP。

设计：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`

实施：`../IMPLEMENTATION_PLAN.md`

## 当前现场

- QQ：用户确认当前农田为**全空**。V2-1 样本采集完成前优先保持。
- 微信：当前现场尚未重新读取；下一次进入后现场确认。若可收获，优先用“成熟→收获→空田”取得微信空地基准。
- 旧每小时“农场 Runner 重构”自动任务：**已暂停**。
- 本次对话：只在 Chat 中通过 CodexPro 操作，不进入 Work 模式。
- Codex CLI：当前不使用；后续仅在专项审查或明确适合的机械实现任务中考虑。

## 已确认可复用

- QQ / 微信窗口恢复基础设施。
- window-local / Retina 坐标转换。
- CGEvent 批量点击及窗口/前台/禁用时段门禁。
- QQ picker 页码、翻页、目标图标、数量徽标等局部识别。
- stable_order + quantities → visible_order → page/slot。
- 4×6 固定网格和四格 placement。

## 当前下一步

1. 完成 V2-0：让旧整田视觉研究退出正常 Runner 依赖。
2. 用当前 QQ 全空田做 V2-1：平台独立空地小 ROI + 固定 24 格检查器。
3. 验证 EMPTY / NOT_EMPTY / UNKNOWN。
4. 接 QQ 固定种植流程。

## 真机操作禁用时段

按农场 Mac 本地时间：

- 00:00–01:00
- 08:00–09:00
- 12:00–13:00
- 14:00–14:05
- 16:00–17:00
- 20:00–21:00

真机阶段前重新读取当前时间和窗口状态。本文件是快照，不代替实时观察。
