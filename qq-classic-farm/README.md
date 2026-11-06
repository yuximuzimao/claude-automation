# QQ经典农场辅助

用于维护 QQ / 微信《QQ经典农场》的玩法事实、种子资料与经过用户逐点确认的 UI 坐标。

当前进度、已确认坐标和后续安排见 [CURRENT](docs/CURRENT.md) 与 [Todo](tasks/todo.md)。

## 当前入口

- Agent 入口与操作边界：SKILL.md
- 当前阶段与坐标状态：docs/CURRENT.md
- 未完成事项：tasks/todo.md
- QQ / 微信统一坐标核对页：工作区根目录 _sandbox/farm-coordinate-review.html
- 用户确认的土地中心、拟合网格与坐标层：data/ui-layout.json
- 用户确认的 UI 点、版本限定样本与候选点：data/ui-anchors.json
- 稳定玩法事实：docs/gameplay-rules.md
- 种子资料：docs/seed-catalog.md / data/seed-catalog.json
- 已暂停的旧 Runner V2 计划：IMPLEMENTATION_PLAN.md
- 历史归档：docs/archive/README.md

## 坐标数据边界

QQ / 微信坐标必须区分 scene、fixed_ui 和未分类的场景内 UI。候选点只有用户明确确认后才进入正式配置。坐标核对期间只标点，不执行收获、种植、施肥、购买、领取奖励或分享发送等业务动作。

## 旧代码边界

工作区仍保留此前的 Runner、脚本和测试；它们目前不代表当前自动化方案。**暂缓处理仅适用于当前坐标核对阶段，不是永久弃用旧代码。**坐标完成后会整体复核项目内容，再按新需求决定旧代码和其他资料哪些值得保留、改造、合并、删除或重写；不预设必须兼容，也不预设全部重写。
