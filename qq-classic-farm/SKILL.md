# QQ经典农场辅助 SKILL.md

## DO FIRST

1. 若任务是开发/重构本地 Runner，**先读根目录 `IMPLEMENTATION_PLAN.md`**。
2. 读 `tasks/todo.md`。
3. 读 `docs/INDEX.md`。
4. 只要要实际操作 QQ / 微信农场，先读 `docs/CURRENT.md`，再读 `docs/gameplay-rules.md`。
5. 涉及选种、库存、成熟时间或图标匹配时，再读 `docs/seed-catalog.md`，精确数据查 `data/seed-catalog.json`。
6. 只在 neat 收尾或需要历史追溯时读 `docs/archive/README.md`；历史归档不是当前操作依据。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `IMPLEMENTATION_PLAN.md` | 本地高速 Runner 的架构、数据模型、阶段任务、验收与对抗式审查 | Runner 开发/重构第一读 |
| `CLAUDE.md` | 项目目标、安全边界、Git/数据边界 | 需要确认红线或项目职责时 |
| `docs/CURRENT.md` | 当前农田、任务和日常状态快照 | 每次继续实际游戏操作前 |
| `docs/gameplay-rules.md` | 收获、种植、务农、商人、任务、分享、商城、窗口恢复的唯一操作规则 | 任何游戏操作前 |
| `docs/seed-catalog.md` | 种子资料字段、库存刷新与图标使用约定 | 选种或刷新库存 |
| `data/seed-catalog.json` | 名称—图标—平台观察值 | 精确查种子 |
| `data/ui-layout.json` | QQ / 微信 4×6 土地网格、窗口基线与合法 2×2 锚点 | 任何土地坐标操作 |
| `data/ui-anchors.json` | 一键按钮 / 化肥菜单视觉锚点、阈值与偏移 | 动态 UI 识别 |
| `data/inventory-live-2026-10-28.json` | 当前两边仓库实时库存与 picker 页码/槽位基线 | 每日首轮计划 / 库存核对 |
| `data/next-cycle-plan.json` | 旧 3 轮计划样本；含历史 page/slot 方案 | Runner 重构时仅参考，不再作为正常执行输入 |
| `data/picker-order.json` | 固定顺序→过滤零库存→分页模型的历史证据 | M0 构建 stable_order、验证“刚获取临时插入/重进恢复”假设的历史对照 |
| `assets/seeds/` | 种子图标资产 | 视觉匹配种植选择器 |
| `assets/ui/` | 稳定 UI 锚点模板（手形按钮 / 务农 / 化肥 / 可摘） | 找图 |
| `scripts/open_qq_farm.swift` | QQ 农场固定入口：定位窗口并按已验证相对坐标打开/恢复农场 | 每次需要恢复或打开 QQ 农场 |
| `scripts/ui_probe.py` | 裁好后的农场窗口只读状态探测 + 24 格坐标生成 | 实际操作每个状态入口 |
| `scripts/pickable_locator.py` | 一次返回全部 4 格植物“可摘”坐标；已被 `ui_probe.py` 集成 | 特殊植物收获 |
| `scripts/picker_simulator.py` | 旧顺序模型推演工具 | 仅异常研究，不作为正常选种入口 |
| `scripts/seed_picker_locator.py` | 按种子名称定位当前选择器图标 | 异常校准/兜底 |
| `scripts/anchor_locator.py` | 单模板 ROI 找图与截图→逻辑坐标映射 | 新增/调试锚点 |
| `tasks/todo.md` | 尚未验证/实现事项的唯一台账 | 每次启动 |
| `docs/archive/README.md` | 已完成阶段索引 | neat 收尾或历史追溯 |

## ROUTING

- **QQ 小程序窗口恢复/打开**：固定运行 `swift scripts/open_qq_farm.swift`，禁止 Agent 临场识别 QQ 左侧入口或改走“更多功能”。
- **收获 / 种植 / 化肥 / 务农 / 神秘商人 / 每日任务 / 分享 / 商城福利**：直接进入 `docs/gameplay-rules.md` 对应章节；重复日常优先看 §8“日常快速执行策略”。实际农田操作先对当前农场窗口截图运行 `scripts/ui_probe.py`，再按状态机决定是否点击；不得跳过探测直接凭旧坐标操作。
- **Runner 重构后的选种职责**：Planner 只决定种子名/数量/成熟档/placement；Runner 用 stable_order + mutable quantities 计算当前 visible_order 与 picker page/slot，并用本地图标校验。当前优先验证“刚获取临时插入、重进恢复 stable_order”的假设；只有验证失败才升级 order revision。现有 `data/inventory-live-*.json` / `data/next-cycle-plan.json` 作为 M0 初始化与历史样本，不再把 page/slot 当策略数据。
- **继续上次现场**：以 `docs/CURRENT.md` 为导航，但执行前重新看实时画面；CURRENT 是快照，不替代实时状态。
- **尚未跑通的新机制**：先看 `tasks/todo.md`，实测后把稳定规则迁到唯一 owner；完成过程再在 neat 时进入 archive。
- **脚本化**：当前最高优先级是按 `IMPLEMENTATION_PLAN.md` 完成本地 Runner；先 M0→M1→M2，M2 稳定后再接完整日常。定时化继续后置。聊天中的临时截图/绝对坐标禁止直接固化，必须进入统一 window-local 模型并经过验收。

## PATHS

- 稳定规则：`docs/gameplay-rules.md`
- 当前状态：`docs/CURRENT.md`
- 种子说明：`docs/seed-catalog.md`
- 种子数据：`data/seed-catalog.json`
- UI 网格：`data/ui-layout.json`
- UI 锚点配置：`data/ui-anchors.json`
- 种子图标：`assets/seeds/`
- UI 锚点模板：`assets/ui/`
- QQ 农场固定入口：`scripts/open_qq_farm.swift`
- 状态探测：`scripts/ui_probe.py`
- 多目标可摘定位：`scripts/pickable_locator.py`
- 当前库存快照：`data/inventory-live-2026-10-28.json`
- Runner 开发计划：`IMPLEMENTATION_PLAN.md`
- 旧 3 轮计划样本：`data/next-cycle-plan.json`
- 旧选择器顺序研究：`data/picker-order.json` + `scripts/picker_simulator.py`
- 种子图标校准：`scripts/seed_picker_locator.py`
- 单锚点调试：`scripts/anchor_locator.py`
- 待办：`tasks/todo.md`
- 历史索引：`docs/archive/README.md`
