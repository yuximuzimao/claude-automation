# QQ经典农场辅助

用于维护 QQ / 微信《QQ经典农场》的玩法事实、种子资料、土地坐标和独立操作脚本。当前以 QQ PC 操作为现役范围；微信真机操作封存。

当前状态和唯一种植计划见 [CURRENT](docs/CURRENT.md) 与 `data/operation-plan.json`；未完成的 QQ 功能见 [Todo](tasks/todo.md)。

## 当前范围

- **QQ：** 保留现有 PC 独立脚本，按用户授权操作；需要时可以继续开发具体功能。
- **微信：** `data/wechat-live-status.txt` 保持 `sealed`。保留代码和资料，不进行真机操作，直到用户明确恢复。
- **旧 Runner：** 已退役并清理，不恢复通用执行器或自恢复续跑；单次定时授权见CURRENT。
- **规划资料：** 保留种子数据库、土地等级与种植规则、收益和经验计算。
- **提醒：** 每次实际种植完成后，更新已知种子库存并创建收菜提醒。

## 当前入口

- Agent 入口与操作边界：`SKILL.md`
- 稳定工作约束：`CLAUDE.md`
- 当前平台状态与最近现场：`docs/CURRENT.md`
- 未完成事项：`tasks/todo.md`
- QQ / 微信统一坐标核对页：工作区根目录 `_sandbox/farm-coordinate-review.html`
- 用户确认的土地中心、四格映射与坐标层：`data/ui-layout.json`
- 用户确认的 UI 点、版本限定样本与候选点：`data/ui-anchors.json`
- 稳定玩法事实：`docs/gameplay-rules.md`
- 种子资料与已知库存：`docs/seed-catalog.md` / `data/seed-catalog.json`
- 收益、经验、生长阶段与土地升级：`docs/farm-planning-reference.md` / `data/farm-planning-reference.json`
- 唯一种植计划：`data/operation-plan.json`
- 共享 Mac 提醒事项协议：工作区根目录 `docs/reminders.md`
- 历史归档：`docs/archive/README.md`

## 坐标数据边界

QQ / 微信坐标必须区分 `scene`、`fixed_ui` 和未分类的场景内 UI。候选点只有用户明确确认后才进入正式配置。坐标核对期间只标点，不执行收获、种植、施肥、购买、领奖或分享发送等业务动作。

## 独立操作脚本

首页确认器及离线图片测试见[首页检查说明](docs/home-check.md)。基础真机验收已完成，开工前使用确认器；未通过时交Agent诊断。

田内脚本从已打开、无遮挡、土地无偏移的标准农场首页出发。

- `scripts/farm_window.py`：打开或关闭小程序。QQ 打开复用现有 Swift 入口。
- `scripts/farm_fertilize_once.py`：检查一键务农和施肥勾选状态，再点普通肥一次；QQ 可选 `--kind organic` 识别有机肥。
- `scripts/farm_harvest_once.py`：识别手形「一键收获」；混种时使用 `--planted-plan`，通过记录校验和成熟前置确认后，按固定点逐个收四格，再点手形按钮。
- `scripts/farm_plant_once.py`：读取唯一计划 `data/operation-plan.json`，逐颗种四格，再按计划补普通种子。
- `scripts/farm_radish_restock.py`：QQ 白萝卜月度补货。按 [白萝卜补货规则](docs/gameplay-rules.md#白萝卜补货) 翻动并识别首格，命中后使用 MAX=99，连续购买 37 次并关闭商店；一次补 3,663 颗，按每天 120 颗可覆盖 30 天并余 63 颗。
- `scripts/farm_radish_xp.py`：QQ 白萝卜种植经验循环。默认 5 轮，每轮固定 `种 24 → 普通肥 → 有机肥 → 收获`，合计消耗 120 颗，理论种植经验1,200（实际受当天游戏上限影响）；不再每轮进商店，也不等待自然成熟。
- `scripts/farm_qq_round.py`：QQ 小程序已经打开后的薄串联入口。根据显式 `--field-state`、`--radish-rounds` 与日常开关组合步骤，默认萝卜0轮、日常不执行；选择条件见操作SOP。它不负责打开/关闭小程序，也不做 Agent 视觉复核。
- `scripts/farm_share_once.py`：QQ固定联系人分享、领奖并回土地；默认只打印计划，`--execute`执行。发送后按原进程返回农场，流程及验收要求见[玩法规则](docs/gameplay-rules.md#每日首次分享)，尚未接入整轮。
- `scripts/farm_daily_task_once.py`：独立每日任务领奖工具；仅明确单独请求时使用，例行选择见操作SOP。
- `scripts/farm_daily_fertilizer_reward.py`：领取礼包商城每日免费化肥。
- `scripts/farm_mischief_once.py`：好友种草/放虫，按共享余额结束；默认无输入，`--execute`连续处理至共享余额双0，见[专项流程](docs/mischief.md)。
- `scripts/farm_friend_sweep.py`：连续拜访好友；识别到「一键偷取」或「一键务农」后直接点该按钮实际中心，首次无按钮时回家。
- `scripts/farm_hamster_once.py`：标准首页识别仓鼠；加 `--execute` 时命中才购买并关闭奖励。

脚本仍保留平台参数，但微信处于封存状态时不得运行微信真机操作。所有真机操作都必须符合当前 Chat 的授权范围。

从本项目目录调用。默认命令只做无点击预检，传入 `--execute` 才发送点击。

```sh
python3.13 scripts/farm_window.py open --platform qq --execute
python3.13 scripts/farm_window.py close --platform qq --execute
python3.13 scripts/farm_fertilize_once.py --platform qq
python3.13 scripts/farm_fertilize_once.py --platform qq --execute
python3.13 scripts/farm_harvest_once.py --platform qq --ordinary-only
python3.13 scripts/farm_harvest_once.py --platform qq --ordinary-only --execute
python3.13 scripts/farm_harvest_once.py --platform qq --planted-plan ../_sandbox/本批实种.json --check-plan
python3.13 scripts/farm_plant_once.py --platform qq --check-plan
python3.13 scripts/farm_plant_once.py --platform qq --execute
python3.13 scripts/farm_radish_restock.py
python3.13 scripts/farm_radish_restock.py --execute
python3.13 scripts/farm_radish_xp.py
python3.13 scripts/farm_radish_xp.py --execute
python3.13 scripts/farm_qq_round.py --field-state mature --harvest-plan ../_sandbox/本批实种.json
# 实际参数先按 docs/operation-sop.md 选择；默认不重复萝卜和日常
python3.13 scripts/farm_qq_round.py --field-state mature --harvest-plan ../_sandbox/本批实种.json --execute
python3.13 scripts/farm_share_once.py
python3.13 scripts/farm_daily_task_once.py --platform qq
python3.13 scripts/farm_daily_fertilizer_reward.py --platform qq
python3.13 scripts/farm_friend_sweep.py --platform qq
python3.13 scripts/farm_hamster_once.py --platform qq --execute
```

执行前按当前计划和已知 picker 位置准备好流程。正常固定脚本退出 0 就按动作完成继续，不做例行截图或 Agent 二次验收；脚本明确停止、界面阻断或后续实际发现遗漏时才排错并修流程。

缺少本地 Swift 辅助程序或辅助程序有改动时，先运行：

```sh
mkdir -p _sandbox
swiftc scripts/window_registry.swift -o _sandbox/farm_window_registry
swiftc scripts/farm_click_batch.swift -o _sandbox/farm_click_batch
swiftc scripts/farm_drag.swift -o _sandbox/farm_drag
swiftc scripts/farm_home_window.swift -o _sandbox/farm_home_window
swiftc scripts/farm_path_drag.swift -o _sandbox/farm_path_drag
```

按日期与土地状态选择脚本见 [按次操作决策](docs/operation-sop.md)。

## 唯一种植计划

`data/operation-plan.json` 是唯一计划文件，也是 `farm_plant_once.py` 的默认输入。每次种植前按最新已知库存和当前 picker 页槽更新它；不再维护第二份计划或多轮预排计划。微信封存期间其计划保持空，不作为恢复后的现成方案。

计划字段、库存耗尽后的页槽更新及普通入口递减规则，唯一见[操作SOP](docs/operation-sop.md#4-正式种植与耗尽补种)。种植预检使用 `farm_plant_once.py --platform qq --check-plan`；它不执行点击。

## 种植后的库存与提醒

统一遵循 [SKILL 种植后的强制收尾](SKILL.md#种植后的强制收尾)。正常按实际完成操作记账，异常或未知库存变化才清点；正式作物提醒时间由阶段数据计算，并通过现有 Mac 快捷指令创建和读回核验。
