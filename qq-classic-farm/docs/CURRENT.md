# 当前状态

更新时间：2026-11-02

## 当前方向

Runner 已切换到 V2：

> 固定流程 + 固定网格/坐标 + 小 ROI 找图/找色 + 异常 STOP。

设计：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`

实施：`../IMPLEMENTATION_PLAN.md`

## 当前现场

- QQ：2026-11-02 18:35 左右确认误种的 24 格月见草已经全部成熟；真机只点一次手形一键收获，随后得到完整空田。
- QQ V2-1 live：当前游戏版本 1.16.1.6 下重新校准 QQ 空田 ROI，连续 5 次 live check 均为 EMPTY 24/24、0 unknown。
- QQ 当前现场：18:47 前后在 picker 第3/7页第3槽真机验证紫薇图标、数量76、one-key=ON 后，只点击该已验证槽位一次；结果 24/24 occupied、0 unknown。紫薇当前数量按确认消耗记为52。
- 微信：2026-11-02 18:49 后按“发现→游戏→最近玩过 QQ经典农场”进入独立 625×1155 农场窗口；现场为 24 格成熟普通作物。只读探测确认手形一键收获，四格过滤后无特殊作物；一键收获一次后得到完整空田。
- 微信 V2 live：当前 1.16.1.6 用同版本“成熟整田/收获后空田”重校准两个固定 ROI；当前空田连续 5/5 次 live check 均为 EMPTY 24/24、0 unknown，成熟整田=NOT_EMPTY 24/24。土地等级当前为 6 紫 + 18 金，只剩一个纯紫 2×2 `purple_a`。
- 微信当前现场：完整空田。微信 picker/preview/confirm 尚未参数化，因此暂不自动种植。
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
5. QQ 固定格点击偏移已由历史实测固化；phase-start EMPTY、指定 cells 占用验证均使用小 ROI。
6. `open_plot` 已接固定格单次 CGEvent；只有本轮 EMPTY phase 授权存在时才可点击，窗口身份变化立即失效。
7. one-key ON 已用事故现场保存的真实截图离线校准：picker y-shift=21，ON=True；OFF/ON/UNKNOWN 三态测试通过。
8. 四格 preview/confirm 已用历史 QQ 实机样本离线校准；confirm 已接单次 CGEvent，只允许精确 2×2 preview + 绿色确认按钮。
9. picker 选种已分为普通 ON / 四格 OFF 两条互斥授权，并要求当前 phase、同 seed、同 slot；相邻槽误点路径不会被放行。
10. 微信 V2 空田检查器已改为当前版本两个固定 ROI：土色 + 占用亮度；同版本 live 空田/成熟整田分别稳定给出 EMPTY 24/24 与 NOT_EMPTY 24/24。
11. 微信普通成熟整田已真机跑通“一次手形一键收获 → 等待 → EMPTY 终验”。当前土地实测为 6 紫 + 18 金，旧第二个纯紫 `purple_b` 已退出现役。
12. QQ V2-1 已完成真机终验；QQ 普通 one-key 种植子路径也已真机跑通，当前 live 结果为紫薇 24/24 occupied。
13. 紫薇 picker 模板已从当前 1.16.1.6 真机第3页第3槽采样，加入 QQ 已验证普通种子；实际数量76，确认种24后记为52。
14. `farm_click_batch` 的系统透明层判断已收窄修正：只跳过全屏 Dock layer20 / Notification Center layer21；第一个其余真实窗口必须就是目标农场，WPS/Safari/Chat 覆盖仍会 STOP。
15. QQ 四格特殊+普通剩余格、微信种植完整路径仍未真机验收。用户已在当前 Chat 明确授权真机操作；每次输入仍先通过时间、窗口、遮挡门禁。

## 真机操作禁用时段

按农场 Mac 本地时间：

- 00:00–01:00
- 08:00–09:00
- 12:00–13:00
- 14:00–14:05
- 16:00–17:00
- 20:00–21:00

真机阶段前重新读取当前时间和窗口状态。本文件是快照，不代替实时观察。
