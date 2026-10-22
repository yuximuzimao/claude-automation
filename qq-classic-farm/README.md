# QQ经典农场辅助

用于维护 QQ / 微信两套《QQ经典农场》的可复用操作规则、种子图库与平台库存观察值，并逐步验证可安全复用的半自动操作流程。

当前阶段以“先把规则跑明白”为主，不构建固定坐标自动化。正式交互采用截图/视觉判断 + macOS CoreGraphics 鼠标事件；稳定、机械的中间步骤以后再按实测拆给脚本。

## 入口

- Agent 入口：`SKILL.md`
- 稳定玩法规则：`docs/gameplay-rules.md`
- 种子资料说明：`docs/seed-catalog.md`
- 种子数据：`data/seed-catalog.json`
- 当前现场：`docs/CURRENT.md`
- 未完成事项：`tasks/todo.md`
- 历史归档：`docs/archive/README.md`

## 数据边界

`data/seed-catalog.json` 是版本化知识数据。仓库数量和账号界面显示的产量/经验/收入都按平台观察值保存，不假设为全服基础值。种子图标位于 `assets/seeds/`，用于后续从种植选择器中匹配目标种子。
