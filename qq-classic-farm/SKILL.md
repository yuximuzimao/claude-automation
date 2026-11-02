# QQ经典农场辅助 SKILL.md

## DO FIRST

1. Runner 开发/重构：读 `IMPLEMENTATION_PLAN.md`。
2. 读 `tasks/todo.md`。
3. 读 `docs/INDEX.md`。
4. 真机操作前读 `docs/CURRENT.md`，再读 `docs/gameplay-rules.md`。
5. 选种/库存/成熟时间：读 `docs/seed-catalog.md` 与 `data/seed-catalog.json`。
6. 历史只在考古或 neat 收尾时进入 `docs/archive/`；历史不得驱动现役流程。

## 当前架构

当前只采用 Runner V2：

> ChatGPT / Planner 决定种什么；本地 Runner 按固定 UI 流程执行。视觉只在小 ROI 检查预期状态，不理解整幅农田。

```text
EMPTY → PLANTING → GROWING/MATURE → HARVESTING → EMPTY
DIRTY/UNKNOWN → STOP
```

设计全文：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`

## ENTRY MAP

| 文件 | 用途 |
| --- | --- |
| `IMPLEMENTATION_PLAN.md` | Runner V2 当前实施顺序与验收 |
| `tasks/todo.md` | 全部未完成事项唯一台账 |
| `docs/CURRENT.md` | 当前 QQ/微信现场 |
| `docs/gameplay-rules.md` | 游戏稳定操作规则 |
| `docs/seed-catalog.md` / `data/seed-catalog.json` | 种子资料 |
| `data/ui-layout.json` | 固定 4×6 网格、窗口基线、四格 placement |
| `data/ui-anchors.json` | 稳定 UI 局部锚点 |
| `scripts/open_qq_farm.swift` | QQ 固定入口/恢复 |
| `scripts/restore_wechat_main.swift` | 微信窗口恢复 |
| `scripts/window_registry.swift` | 农场窗口发现 |
| `scripts/farm_capture.py` / `farm_geometry.py` / `farm_io.py` | 截图、坐标、窗口 I/O |
| `scripts/farm_click_batch.swift` / `farm_drag.swift` | CGEvent 输入 |
| `scripts/seed_order.py` | stable_order / visible_order / page-slot |
| `scripts/farm_plant_picker.py` | Picker 确定性翻页 contract |
| `scripts/farm_picker_vision.py` / `farm_text_ocr.swift` | Picker 局部页码/图标/数量 |
| `scripts/farm_runner.py` | Runner V2 总入口 |
| `scripts/farm_harvest*.py` | V2 收获链 |
| `scripts/farm_plant*.py` | V2 种植链 |

## ROUTING

- QQ：固定使用 `open_qq_farm.swift`。
- 微信：固定使用 `restore_wechat_main.swift` 后按 gameplay-rules 进入农场。
- 土地：固定网格 + 平台独立空地小 ROI；不做通用整田视觉。
- Picker：Planner 不写 page/slot；Runner 计算后用局部图标/页码/数量验证。
- 四格：Planner 给 placement；确认成功后 Runner 直接记录本轮 placement。
- 普通一键：剩余空格数从计划推导；不重新构建一般占用语义。
- 收获：已知 placement 可摘标志 + 游戏一键按钮，最后用空地 ROI 终验。
- 异常：DIRTY/UNKNOWN 立即 STOP，不补洞、不猜恢复点。
- 定时：当前暂停；稳定后只允许调用 Runner，不承担开发。

## PATHS

- 当前计划：`IMPLEMENTATION_PLAN.md`
- 当前现场：`docs/CURRENT.md`
- Todo：`tasks/todo.md`
- V2 设计：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`
- 稳定玩法：`docs/gameplay-rules.md`
- 种子：`docs/seed-catalog.md`、`data/seed-catalog.json`
- 网格：`data/ui-layout.json`
- UI 锚点：`data/ui-anchors.json`
- 历史：`docs/archive/`
