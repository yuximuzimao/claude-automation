# 农场 Runner V2 实施计划

当前唯一现役计划。设计依据：
`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`

## 目标

把 QQ / 微信农场的重复操作做成固定流程 Runner：

```text
EMPTY → PLANTING → GROWING/MATURE → HARVESTING → EMPTY
DIRTY/UNKNOWN → STOP
```

正常路径依靠固定窗口、固定网格、固定 ROI 找图/找色和确定性状态转换，不构建通用农田视觉理解。

## V2-0 清理旧路线 — 已完成

- [x] 正常 Runner 已断开整田视觉研究依赖。
- [x] V1 diagnostic-only 脚本已物理删除。
- [x] 复杂 planting recovery 已删除；异常统一 DIRTY/STOP。
- [x] 只保护旧路线的测试已删除。
- [x] 反向搜索确认现役脚本/测试对旧模块引用为 0。

已删除：
`farm_scene.py`、`farm_clean_field.py`、`farm_clean_replay.py`、
`farm_field.py`、`farm_field_delta.py`、`farm_field_postcondition.py`、
`farm_qq_landing.py`、`farm_plant_recovery.py`。

验证：清理前 226 项测试；清理后 173 项现役测试全部通过。
`farm_qq_clean.py` 暂留，V2-1 只复用“小 ROI 空地模板”思路并重写接口。

## V2-1 QQ 空田检查器 — 离线完成，live EMPTY 终验待授权

目标：

```text
check-empty --platform qq → EMPTY | NOT_EMPTY | UNKNOWN
```

- [x] 固定 603×1111 QQ 农场窗口模型。
- [x] 复用固定 4×6 网格，不逐格找土地。
- [x] 在 `ui-layout.json -> qq.empty_check` 固化两个 5×5 ROI：
  - 土地颜色点：相对既有 origin `(-34,-11)`；
  - 占用点：相对既有 origin `(-16,+16)`。
- [x] 空地只按当前颜色就近匹配紫/金原型，不再依赖历史 `land_grades` 判定土地等级。
- [x] 占用点亮度 <130 为明确非空，>160 才可成为空地候选，130–160 为 UNKNOWN。
- [x] 实现 `EMPTY / NOT_EMPTY / UNKNOWN`。
- [x] Runner 新增只读 `check-empty`：两次窗口身份确认 + 一次截图，0 点击。
- [x] 真实截图离线回放：真空田=EMPTY（24/24）；当前24格月见草=NOT_EMPTY（24/24）；全屏遮罩=UNKNOWN（24/24）；残留大型作物=NOT_EMPTY。
- [ ] 等用户在当前 Chat 明确允许且获得新的 QQ 空田现场后，执行 live EMPTY 终验。

旧 19×19 atlas 与两张 sentinel negative 资产已删除；受控白萝卜 empty/seedling/mature/harvested 四态样本保留作历史实测证据。

## V2-2 QQ 完整种植 — 纯事务层完成，live 接线待校准

```text
EMPTY → 四格 placement → 普通一键种植 → GROWING
```

- [x] Planner 只提供种子/数量/placement。
- [x] Phase 开始只要求一次 `EMPTY`；之后 Runner 自己维护 `known_occupied`。
- [x] Picker 继续用 stable_order + quantities 计算 page/slot。
- [x] Picker 唯一选择入口保持“验证哪个目标槽位，就只能点击刚验证的同一槽位”。
- [x] 四格事务只验证目标 preview、confirm 关闭和计划 2×2 ROI 已占用；不重建 24 格语义图。
- [x] 四格确认后直接把该 placement 四格加入 Runner `known_occupied`。
- [x] 普通剩余格数由 `24 - known_occupied` 直接计算。
- [x] 普通事务要求 picker 明确验证 one-key ON 后，只选择一次已验证槽位。
- [x] 异常统一 DIRTY/STOP；已删除 checkpoint / preaction / 崩溃自动续播职责。
- [x] 纯事务层 23 项专项测试通过；当前全项目 155 项测试全部通过。
- [ ] live adapter：固定格 open_plot 坐标接线。
- [ ] live adapter：四格 preview / confirm ROI 校准。
- [ ] live adapter：`verify_cells_occupied(cells)` 用 V2 固定 ROI 实现。
- [ ] live adapter：one-key ON 正例校准。
- [ ] 获得用户当前 Chat 明确授权后，做真实 EMPTY → 完整种植验收。

验收不变：QQ 一个本地 phase 从 EMPTY 连续完成整轮种植；正常路径无逐点击模型往返。

## V2-3 QQ 完整收获

```text
MATURE → 四格可摘 → 一键收获 → EMPTY
```

- [ ] 只在已知 placement 附近检查“可摘”标志。
- [ ] 收获已确认的四格。
- [ ] 点击游戏一键收获。
- [ ] 等动画。
- [ ] 用 V2 空田检查器验证 EMPTY。
- [ ] 非 EMPTY → DIRTY/STOP。

## V2-4 微信参数化

- [ ] 采微信独立空地模板与网格起点/偏移。
- [ ] 必要按钮/标志用微信独立模板。
- [ ] 复用同一状态机。
- [ ] 跑通微信完整种植和收获一轮。

## V2-5 Planner / 库存

双平台机械闭环稳定后再接：

- [ ] 当前库存同步。
- [ ] 连续 3 轮计划。
- [ ] 成功种植后更新确认库存。
- [ ] 活动优先、成熟时间对齐继续由 ChatGPT / Planner 决定。

## V2-6 定时化

- [ ] 只在 Runner 稳定后重新评估。
- [ ] 定时任务只调用 Runner / 报告 STOP。
- [ ] 不恢复此前“每小时自主研发 Runner”的自动任务。

## 第一里程碑

不是测试数量，而是：

> QQ 从 EMPTY 按计划连续种植；成熟后连续收获并再次验证 EMPTY。
