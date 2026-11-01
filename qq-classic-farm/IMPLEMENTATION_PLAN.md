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

## V2-0 清理旧路线

- [ ] 移除正常 Runner 对整田视觉研究模块的依赖。
- [ ] 旧 diagnostic-only 脚本退出现役执行链。
- [ ] 删除/简化复杂 planting recovery；异常统一 DIRTY/STOP。
- [ ] 删除只保护旧路线的测试。
- [ ] 验证旧视觉研究模块不再影响收获、种植或 run-next。

退役研究模块：
`farm_scene.py`、`farm_clean_field.py`、`farm_clean_replay.py`、
`farm_field_delta.py`、`farm_field_postcondition.py`、`farm_qq_landing.py`。
`farm_qq_clean.py` 只保留“小 ROI 空地模板”思路，重写为平台化检查器。

## V2-1 QQ 空田检查器

当前用户确认 QQ 为全空田。

目标：

```text
check-empty qq → EMPTY | NOT_EMPTY | UNKNOWN
```

- [ ] 恢复/定位 QQ 固定农场窗口。
- [ ] 用 baseline window 或稳定锚点定位农田。
- [ ] 复用固定 4×6 网格推导 24 格。
- [ ] 采当前 QQ 土地版本的 purple-empty / gold-empty 小 ROI。
- [ ] 每格只检查对应土地等级的局部 ROI。
- [ ] 24 格全匹配 → EMPTY。
- [ ] 明确非空 → NOT_EMPTY。
- [ ] 定位/模板/状态不确定 → UNKNOWN。

验收：当前 QQ 空田连续返回 EMPTY；真实幼苗/成熟样本不得返回 EMPTY；收获后空地样本返回 EMPTY。

## V2-2 QQ 完整种植

```text
EMPTY → 四格 placement → 普通一键种植 → GROWING
```

- [ ] Planner 只提供种子/数量/placement。
- [ ] 四格使用固定 placement 坐标。
- [ ] Picker 用 stable_order + quantities 计算 page/slot。
- [ ] 局部验证页码、目标图标、数量。
- [ ] 四格只验证 preview / confirm ROI。
- [ ] 确认后直接记录该 placement 已落地。
- [ ] 普通剩余格数由 24 - 已知四格占用直接计算。
- [ ] 验证 one-key ON 后只选一次普通种子。
- [ ] 结果不符合预期则 DIRTY/STOP，不补洞。

验收：QQ 一个本地 phase 从 EMPTY 连续完成整轮种植；正常路径无逐点击模型往返。

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
