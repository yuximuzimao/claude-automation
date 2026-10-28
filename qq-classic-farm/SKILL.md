# QQ经典农场辅助 SKILL.md

## DO FIRST

1. 读 `tasks/todo.md`。
2. 读 `docs/INDEX.md`。
3. 只要要实际操作 QQ / 微信农场，先读 `docs/CURRENT.md`，再读 `docs/gameplay-rules.md`。
4. 涉及选种、库存、成熟时间或图标匹配时，再读 `docs/seed-catalog.md`，精确数据查 `data/seed-catalog.json`。
5. 只在 neat 收尾或需要历史追溯时读 `docs/archive/README.md`；历史归档不是当前操作依据。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `CLAUDE.md` | 项目目标、安全边界、Git/数据边界 | 需要确认红线或项目职责时 |
| `docs/CURRENT.md` | 当前农田、任务和日常状态快照 | 每次继续实际游戏操作前 |
| `docs/gameplay-rules.md` | 收获、种植、务农、商人、任务、分享、商城、窗口恢复的唯一操作规则 | 任何游戏操作前 |
| `docs/seed-catalog.md` | 种子资料字段、库存刷新与图标使用约定 | 选种或刷新库存 |
| `data/seed-catalog.json` | 名称—图标—平台观察值 | 精确查种子 |
| `data/ui-layout.json` | QQ / 微信 4×6 土地网格、窗口基线与合法 2×2 锚点 | 任何土地坐标操作 |
| `data/ui-anchors.json` | 一键按钮 / 化肥菜单视觉锚点、阈值与偏移 | 动态 UI 识别 |
| `data/inventory-live-2026-10-28.json` | 当前两边仓库实时库存与 picker 页码/槽位基线 | 每日首轮计划 / 库存核对 |
| `data/next-cycle-plan.json` | 基于当前库存预先计算的 3 轮日批次计划 | 每次种植前直接执行对应轮次 |
| `data/picker-order.json` | 旧的隐藏排序研究表 | 仅历史研究 / 异常分析 |
| `assets/seeds/` | 种子图标资产 | 视觉匹配种植选择器 |
| `assets/ui/` | 稳定 UI 锚点模板（手形按钮 / 务农 / 化肥 / 可摘） | 找图 |
| `scripts/ui_probe.py` | 裁好后的农场窗口只读状态探测 + 24 格坐标生成 | 实际操作每个状态入口 |
| `scripts/pickable_locator.py` | 一次返回全部 4 格植物“可摘”坐标；已被 `ui_probe.py` 集成 | 特殊植物收获 |
| `scripts/picker_simulator.py` | 旧顺序模型推演工具 | 仅异常研究，不作为正常选种入口 |
| `scripts/seed_picker_locator.py` | 按种子名称定位当前选择器图标 | 异常校准/兜底 |
| `scripts/anchor_locator.py` | 单模板 ROI 找图与截图→逻辑坐标映射 | 新增/调试锚点 |
| `tasks/todo.md` | 尚未验证/实现事项的唯一台账 | 每次启动 |
| `docs/archive/README.md` | 已完成阶段索引 | neat 收尾或历史追溯 |

## ROUTING

- **收获 / 种植 / 化肥 / 务农 / 神秘商人 / 每日任务 / 分享 / 商城福利 / 小程序窗口恢复**：直接进入 `docs/gameplay-rules.md` 对应章节；重复日常优先看 §8“日常快速执行策略”。实际农田操作先对当前农场窗口截图运行 `scripts/ui_probe.py`，再按状态机决定是否点击；不得跳过探测直接凭旧坐标操作。
- **种什么、库存够不够、picker 第几页第几个**：当天优先读最新 `data/inventory-live-*.json` 和 `data/next-cycle-plan.json`；种子属性再查 `docs/seed-catalog.md` / `data/seed-catalog.json`。仓库实时快照的数量与顺序优先级高于 catalog 中历史 quantity。
- **继续上次现场**：以 `docs/CURRENT.md` 为导航，但执行前重新看实时画面；CURRENT 是快照，不替代实时状态。
- **尚未跑通的新机制**：先看 `tasks/todo.md`，实测后把稳定规则迁到唯一 owner；完成过程再在 neat 时进入 archive。
- **脚本化 / 定时化**：当前仍属于 Todo；未验证稳定前不得从聊天中的临时坐标直接固化为自动脚本。

## PATHS

- 稳定规则：`docs/gameplay-rules.md`
- 当前状态：`docs/CURRENT.md`
- 种子说明：`docs/seed-catalog.md`
- 种子数据：`data/seed-catalog.json`
- UI 网格：`data/ui-layout.json`
- UI 锚点配置：`data/ui-anchors.json`
- 种子图标：`assets/seeds/`
- UI 锚点模板：`assets/ui/`
- 状态探测：`scripts/ui_probe.py`
- 多目标可摘定位：`scripts/pickable_locator.py`
- 当前库存快照：`data/inventory-live-2026-10-28.json`
- 当前 3 轮计划：`data/next-cycle-plan.json`
- 旧选择器顺序研究：`data/picker-order.json` + `scripts/picker_simulator.py`
- 种子图标校准：`scripts/seed_picker_locator.py`
- 单锚点调试：`scripts/anchor_locator.py`
- 待办：`tasks/todo.md`
- 历史索引：`docs/archive/README.md`
