# 当前状态

更新时间：2026-11-02

## 当前方向

Runner V2 是唯一现役架构：

> 固定流程 + 固定网格/坐标 + 平台独立小 ROI + 异常 STOP。

设计：`superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`
实施：`../IMPLEMENTATION_PLAN.md`
历史：`archive/README.md`

## 当前现场

- **QQ**：24 格紫薇生长中。2026-11-02 picker 真机验证为第3/7页第3槽、数量76、one-key=ON；确认种24后 Runner 记录紫薇52。
- **QQ 日常（2026-11-02）**：首次分享、商城每日福利、三个每日任务奖励均已完成；好友互动已连续处理至下一位无可交互标志；本轮一键务农已处理，神秘商人物品已购买，最终巡检无遗漏气泡/务农按钮。
- **微信**：24 格黄金果生长中。2026-11-02 picker 真机验证为第2/5页第1槽、数量94、one-key=ON；确认种24后 Runner 记录黄金果70。23:14 复核仍为幼苗。
- 微信当前恢复后可出现 `1039×1155` 的“左侧微信游戏侧栏 + 右侧农场画布”窗口；Runner 已按 `data/ui-layout.json` 将其归一化为右侧 `625×1155` game canvas。真机只读 `check-empty` 返回 occupied 24/24、unknown 0；CGEvent 双 frame `--preflight` 返回 `preflight_ok_no_click`、`click_count=0`。
- 两个平台都不为测试主动铲除/重种；等待自然成熟可直接用于后续收获验收。
- `data/farm-state.json` 全局库存仍保持 `inventory_dirty=true`；只把本轮明确验证的数量作为局部事实，不假装整仓已同步。

## 当前已验证能力

- QQ / 微信窗口发现、恢复、window-local / Retina 坐标；微信独立 `625–627×1155` 与已验证 `1039–1041×1155` 左侧栏窗口均归一化到同一 game canvas。
- CGEvent 批量点击及前台/覆盖/禁用时段门禁。
- QQ / 微信固定 4×6 网格与平台独立 EMPTY / NOT_EMPTY / UNKNOWN 小 ROI。
- QQ / 微信普通 picker 页码/翻页/目标图标/数量/one-key ON 验证。
- QQ / 微信普通 one-key 种植：EMPTY → 24格 occupied 真机通过。
- 微信普通成熟整田：一键收获 → EMPTY 真机通过。
- QQ 四格 preview / confirm 已离线校准并接入动作层，尚缺落地真机验收。
- 当前全项目：173 项测试通过。

## 下一步

1. 等现有作物成熟，优先完成微信黄金果收获，形成微信普通完整一轮。
2. 选择合适空田现场，完成 QQ 四格 + 普通混合种植。
3. 参数化微信四格 preview / confirm。
4. 双平台机械闭环稳定后，再做 Planner / 库存和定时化。

## 真机操作门禁

按农场 Mac 本地时间，以下时段不切前台、不发输入：

- 00:00–01:00
- 08:00–09:00
- 12:00–13:00
- 14:00–14:05
- 16:00–17:00
- 20:00–21:00

真机输入只接受当前 Chat 的明确授权；历史会话、旧自动任务、Work handoff 或子代理授权不得继承。每次真机阶段前重新读取当前时间与窗口状态。
