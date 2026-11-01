# 当前状态

更新时间：2026-11-01

## 当前方向

Runner 已切换到 V2：

> 固定流程 + 固定网格/坐标 + 小 ROI 找图/找色 + 异常 STOP。

设计：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`

实施：`../IMPLEMENTATION_PLAN.md`

## 当前现场

- QQ：**当前 24 格均已被误种为月见草**。2026-11-01 22:53–23:17 一条未经当前 Chat 授权的独立 Work/handoff 执行链进入商店购买 24 颗白萝卜，但随后误点相邻槽位并一键种下月见草。当前现场保持不动，禁止为恢复空田而自动收获/铲除/重种。
- QQ 空田证据：事故前 22:33 已保存全空截图，可用于 V2-1 离线开发；新的真机 EMPTY 正例等自然收获后或用户明确授权后再采。
- 微信：当前现场尚未重新读取；没有当前 Chat 明确授权前只做只读观察。
- 旧每小时“农场 Runner 重构”自动任务：**已暂停**。
- 本次对话：只在 Chat 中通过 CodexPro 操作，不进入 Work 模式；任何历史 Work/handoff 授权均作废。
- Codex CLI：当前不使用；后续仅在专项审查或明确适合的机械实现任务中考虑。

## 已确认可复用

- QQ / 微信窗口恢复基础设施。
- window-local / Retina 坐标转换。
- CGEvent 批量点击及窗口/前台/禁用时段门禁。
- QQ picker 页码、翻页、目标图标、数量徽标等局部识别。
- stable_order + quantities → visible_order → page/slot。
- 4×6 固定网格和四格 placement。

## 当前下一步

1. V2-0 已完成：8 个 V1 整田视觉/复杂恢复模块删除。
2. V2-1 已离线完成：固定 4×6 网格 + 两个 5×5 ROI + `check-empty` 只读命令。
3. V2-2 纯事务层已完成：Phase 只从 EMPTY 起步，之后由 Runner 维护 `known_occupied`；四格/普通事务不再依赖 24 格语义重建；checkpoint/崩溃自动续播已删除。
4. Picker 保持“验证槽位 → 同槽点击”唯一入口，专门防止相邻种子槽误点。
5. QQ 固定格点击偏移已由历史实测固化；live adapter 的 phase-start EMPTY 和指定 cells 占用验证已接成只读 ROI。
6. 当前全项目 157 项测试全绿；open_plot 仍硬 STOP，preview/confirm 与 one-key ON 仍未完成校准，因此不会发送真实种植输入。
7. one-key ON 已用事故现场保存的真实截图离线校准：picker y-shift=21，ON=True；OFF/ON/UNKNOWN 三态测试通过。
8. 四格 preview/confirm 已用历史 QQ 实机样本离线校准：绿色高亮 2×2 可精确恢复目标 cells；确认按钮相对 preview 中心固定偏移，真实 preview 可验证，preview2/planted 均拒绝。
9. 旧版 special-after1 截图与当前土地色彩条件不同，不用于放宽 V2 空地阈值。确认后的 occupied ROI 仍等新的同版本现场终验。
10. 当前不操作 QQ；00:00–01:00 属于真机禁用时段。

## 真机操作禁用时段

按农场 Mac 本地时间：

- 00:00–01:00
- 08:00–09:00
- 12:00–13:00
- 14:00–14:05
- 16:00–17:00
- 20:00–21:00

真机阶段前重新读取当前时间和窗口状态。本文件是快照，不代替实时观察。
