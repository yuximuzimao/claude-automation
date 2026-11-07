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

## 独立操作脚本

`scripts/farm_fertilize_once.py` 从已打开、无遮挡、土地无偏移的农场首页出发。01 号地需能打开已核对的两肥面板。脚本只做一轮普通肥，按小区域里的勾决定是否需要先勾选一键施肥。

让目标农场处于前台，再从本项目目录调用。默认命令仅做无点击预检，传入 `--execute` 才发送点击。微信将 `qq` 换成 `wechat`。

微信开关小程序和试行节奏见 [当前状态](docs/CURRENT.md#微信试行操作节奏)。

```sh
python3.13 scripts/farm_fertilize_once.py --platform qq
python3.13 scripts/farm_fertilize_once.py --platform qq --execute
```

可用退出码做 if/else 拼接。执行模式退出码 `0` 表示普通化肥的点击已发送。退出码 `2` 时读取输出的停止原因，避免整段重放。缺少本地 Swift 辅助程序时，先运行以下命令。

```sh
mkdir -p _sandbox
swiftc scripts/window_registry.swift -o _sandbox/farm_window_registry
swiftc scripts/farm_click_batch.swift -o _sandbox/farm_click_batch
```

## 旧代码边界

工作区保留此前的 Runner、脚本和测试，供新流程设计按需评估。是否复用以新流程的需求和验证结果为准。
