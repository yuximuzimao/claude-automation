# 当前状态

更新时间：2026-11-03

## 当前方向

Runner V2 是唯一现役架构：

> 固定流程 + 固定网格/坐标 + 平台独立小 ROI + 异常 STOP。

设计：`superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`
实施：`../IMPLEMENTATION_PLAN.md`
历史：`archive/README.md`

## 当前现场

- **QQ**：2026-11-03 紫薇自然成熟后，只发一次一键收获；QQ 1.16.2.7 EMPTY 校准修正后真机确认 24/24 EMPTY。当前田为空。
- **QQ 四格校准**：泡泡棉花糖 one-key 已受控切为 OFF；以已真机校准的 `(3,2)` 打开 picker，数量 21。只选择一次进入预览态，通过拖动绿色 2×2 到 24 个地块中心完成全量映射，4 个分散位置复测全部一致；最后只点红色取消，最终 picker 再读仍为数量21、OFF，未确认/未消耗。结果：`data/qq-special-placement-map.json`。
- **QQ 日常（2026-11-02）**：首次分享、商城每日福利、三个每日任务奖励均已完成；好友互动已连续处理至下一位无可交互标志；本轮一键务农已处理，神秘商人物品已购买，最终巡检无遗漏气泡/务农按钮。
- **微信**：2026-11-03 黄金果自然成熟后，只发一次一键收获；双 occupancy ROI 修正后 fresh capture 真机确认 24/24 EMPTY。当前田为空。
- 微信恢复后仍可能出现 `1039×1155` 的“左侧微信游戏侧栏 + 右侧农场画布”窗口；Runner 已归一化为右侧 `625×1155` game canvas。
- `data/farm-state.json` 全局库存仍保持 `inventory_dirty=true`；只把本轮明确验证的局部数量作为事实，不假装整仓已同步。

## 当前已验证能力

- QQ / 微信窗口发现、恢复、window-local / Retina 坐标；微信独立 `625–627×1155` 与已验证 `1039–1041×1155` 左侧栏窗口均归一化到同一 game canvas。
- CGEvent 批量点击、可选 hover、受控拖拽及前台/覆盖门禁；**交互 Chat 不再使用固定时间门禁**，售后冲突时段留给未来自动调度器。
- QQ / 微信固定 4×6 网格与平台独立 EMPTY / NOT_EMPTY / UNKNOWN 小 ROI。
- QQ / 微信普通 picker 页码/翻页/目标图标/数量/one-key ON 验证；QQ 1.16.2.7 的 ON checkbox 改为读取稳定绿色核心，且已真机完成 ON→OFF 受控切换。
- QQ / 微信普通 one-key 种植：EMPTY → 24格 occupied 真机通过；两平台普通成熟整田均已完成“一键收获 → 24/24 EMPTY”真机闭环。
- QQ 四格 preview 改用独立地块中心 ROI；24 个“拖到目标格中心 → 实际2×2覆盖”已真机穷举并写入 `data/qq-special-placement-map.json`，不再依赖边界方向推导。
- QQ 四格绿色 confirm 仍未实际点击；**尚缺第一次真实落地与四格+普通混合种植验收**。
- 当前全项目：177 项 Python 测试通过；`farm_click_batch.swift`、`farm_drag.swift`、`open_qq_farm.swift`、`restore_wechat_main.swift` 均重新编译通过。

## 下一步

1. 将 QQ 四格种植正式路径改为“固定 `(3,2)` 打开 picker → 查 `qq-special-placement-map.json` → 拖预览到目标格 → preview 验票 → confirm”，不再用单一 `plot_click_offset` 猜 24 格入口。
2. 当前 QQ 空田可直接用于第一次四格真实落地 + 普通混合种植验收。
3. 参数化微信四格 preview / confirm。
4. 双平台机械闭环稳定后，再做 Planner / 库存和定时化。

## 真机操作授权

当前 **Chat 交互实测不设固定时间门禁**：用户发出真机操作指令时，视为已人工确认不会与售后自动化冲突。原 00:00–01:00、08:00–09:00、12:00–13:00、14:00–14:05、16:00–17:00、20:00–21:00 冲突窗口只属于未来“自动收菜调度器”，届时在 scheduler 层实现，不再下沉到 Runner / CGEvent helper。

真机输入仍只接受当前 Chat 的明确授权；历史会话、旧自动任务、Work handoff 或子代理授权不得继承。
