# 2026-11-02 Runner V2 方向纠偏与真机基线

## 阶段范围

本阶段完成了农场 Runner 的架构纠偏、V1 研究路线清理，以及 QQ / 微信普通收获与普通 one-key 种植的第一轮 V2 真机验证。

方向纠偏的核心不是增加更多视觉，而是把项目重新收窄为固定环境中的 deterministic Runner：

```text
Planner / ChatGPT 决定策略
→ Runner 执行固定流程
→ 小 ROI 只验证预期状态
→ DIRTY / UNKNOWN 立即 STOP
```

V1“完整 24 格语义证明”的退役原因另见 `../2026-11-01-runner-v1-retired.md`。

## V2 已落地的架构边界

- 固定 4×6 网格，不逐格搜索土地。
- QQ / 微信分别维护窗口、土色、占用、picker 等平台参数。
- 视觉只回答小问题：空/非空、目标图标、数量、one-key、preview/confirm 等。
- Phase 只从已验证 EMPTY 开始；Runner 自己维护本轮 `known_occupied`。
- 普通 picker 必须明确 ON；四格 picker 必须明确 OFF。
- “验证哪个 seed/slot，就只能点击同一个 seed/slot”。
- 不做部分种植自动补洞，不做崩溃续播推断，不盲重试不可逆动作。
- 正常 phase 不再由 Agent 单击级遥控。

## V1 清理

已从现役代码删除整田语义/差分/复杂恢复分支，包括：

- `farm_scene.py`
- `farm_clean_field.py`
- `farm_clean_replay.py`
- `farm_field.py`
- `farm_field_delta.py`
- `farm_field_postcondition.py`
- `farm_qq_landing.py`
- `farm_plant_recovery.py`

对应只为旧路线服务的测试和旧 atlas/sentinel 资产同步清理。Git 历史保留全部实验过程。

## QQ 真机基线

当前游戏版本：1.16.1.6。

已完成：

- 误种月见草成熟后，只点击一次手形一键收获，得到完整空田。
- QQ EMPTY ROI 用当前版本空田重新校准，并在连续 5 次 live check 中稳定返回 EMPTY 24/24、0 unknown。
- picker 第3/7页第3槽验证紫薇：图标、数量76、one-key=ON。
- 只点击已验证槽位一次，一键种植24格。
- 种植后返回 occupied 24/24、0 unknown。
- 确认消耗24后，Runner 记录紫薇52。

当前现场：紫薇24格生长中。

尚未完成：四格特殊种子落地真机验收、四格+普通混合种植、QQ 四格完整收获。

## 微信真机基线

当前游戏版本：1.16.1.6。

已完成：

- 成熟普通整田探测后，只点击一次手形一键收获，收获后 EMPTY 终验通过。
- 当前土地为 6 紫 + 18 金；现役纯紫安全 2×2 只保留 `purple_a`。
- picker 第2/5页第1槽验证黄金果：图标分数1.0、数量94、one-key=ON；左右箭头均可验证。
- 固定格 open_plot、翻页和普通选种已接入正式 LivePlantAdapter。
- 一键种植黄金果24格，当前版本占用 ROI 返回 occupied 24/24、0 unknown。
- 确认消耗24后，Runner 记录黄金果70。

当前现场：黄金果24格生长中。

尚未完成：黄金果成熟后的收获终验、微信四格 preview/confirm 参数化。

## 数据与安全边界

- `data/farm-state.json` 仍保持 `inventory_dirty=true`；局部真机数量更新不等于整仓同步。
- 旧每小时“农场 Runner 重构”任务保持暂停，不恢复自主研发模式。
- 定时化只有在双平台 Runner 稳定后再评估，届时只负责调用 Runner 和报告 STOP。
- 真机输入仍必须取得当前 Chat 的明确授权，并遵守项目禁用时段与窗口覆盖门禁。

## 阶段验收

- V2 分支最终合入 main。
- 合并后 main 上 170 项测试通过。
- 原临时 V2 worktree / 分支已删除；后续直接从 main 继续。
