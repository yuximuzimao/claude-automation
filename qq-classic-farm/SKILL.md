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
| `assets/seeds/` | 种子图标资产 | 视觉匹配种植选择器 |
| `tasks/todo.md` | 尚未验证/实现事项的唯一台账 | 每次启动 |
| `docs/archive/README.md` | 已完成阶段索引 | neat 收尾或历史追溯 |

## ROUTING

- **收获 / 种植 / 务农 / 神秘商人 / 每日任务 / 分享 / 商城福利 / 小程序窗口恢复**：直接进入 `docs/gameplay-rules.md` 对应章节，不在本文件复制规则正文。
- **种什么、库存够不够、成熟时间是否一致、图标对应哪个种子**：先读 `docs/seed-catalog.md`，再按需读取 `data/seed-catalog.json`。
- **继续上次现场**：以 `docs/CURRENT.md` 为导航，但执行前重新看实时画面；CURRENT 是快照，不替代实时状态。
- **尚未跑通的新机制**：先看 `tasks/todo.md`，实测后把稳定规则迁到唯一 owner；完成过程再在 neat 时进入 archive。
- **脚本化 / 定时化**：当前仍属于 Todo；未验证稳定前不得从聊天中的临时坐标直接固化为自动脚本。

## PATHS

- 稳定规则：`docs/gameplay-rules.md`
- 当前状态：`docs/CURRENT.md`
- 种子说明：`docs/seed-catalog.md`
- 种子数据：`data/seed-catalog.json`
- 图标：`assets/seeds/`
- 待办：`tasks/todo.md`
- 历史索引：`docs/archive/README.md`
