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
- 历史归档：docs/archive/README.md

## 坐标数据边界

QQ / 微信坐标必须区分 scene、fixed_ui 和未分类的场景内 UI。候选点只有用户明确确认后才进入正式配置。坐标核对期间只标点，不执行收获、种植、施肥、购买、领取奖励或分享发送等业务动作。

## 独立操作脚本

田内脚本从已打开、无遮挡、土地无偏移的标准农场首页出发。

- `scripts/farm_window.py` 打开或关闭小程序。QQ 打开复用现有 Swift 入口，现行规则见[窗口与状态恢复](docs/gameplay-rules.md#7-窗口与状态恢复)。
- `scripts/farm_fertilize_once.py` 按[施肥规则](docs/gameplay-rules.md#化肥催熟)处理一键务农与勾选状态，再点普通肥一次。
- `scripts/farm_harvest_once.py` 在当前画面识别手形「一键收获」，匹配成功后点一次并等待 2.8 秒。混种时加 `--planted-plan`，按已确认的实种计划逐个收四格星标，再点手形按钮。支持范围见[收获规则](docs/gameplay-rules.md#4-格特殊植物)。
- `scripts/farm_plant_once.py` 读取[本轮计划文件](#本轮计划文件)。先逐颗种四格，再按需要补普通种子。种植步骤见[玩法规则](docs/gameplay-rules.md#3-种植)。
- `scripts/farm_daily_task_once.py` 在当天已收获一次后使用。拜访首位可互动好友，点击一次单个一键按钮，回家后点任务书首个领取按钮一次。等待 0.9 秒，点空白再关任务书。
- `scripts/farm_friend_sweep.py` 连续拜访好友，每人按[好友互动规则](docs/gameplay-rules.md#好友连续互动)操作一次，首次无按钮时回家。
- `scripts/farm_daily_fertilizer_reward.py` 在当天每日福利仍可领时使用。右上商城 → 礼包商城 → 免费 → 空白 → 返回农场。
- `scripts/farm_hamster_once.py` 在标准首页识别仓鼠。加 `--execute` 时命中就购买并关闭奖励。没识别到时点击数为零。

从本项目目录调用。田内操作要求目标农场处于前台。默认命令仅做无点击预检，传入 `--execute` 才发送点击。开跑前查[平台运行状态](docs/CURRENT.md#平台运行状态)。微信封存时，开关小程序和鼠标输入入口返回 `WECHAT_FARM_SEALED`。

```sh
python3.13 scripts/farm_window.py open --platform qq --execute
python3.13 scripts/farm_window.py close --platform qq --execute
python3.13 scripts/farm_fertilize_once.py --platform qq
python3.13 scripts/farm_fertilize_once.py --platform qq --execute
python3.13 scripts/farm_harvest_once.py --platform qq
python3.13 scripts/farm_harvest_once.py --platform qq --execute
python3.13 scripts/farm_harvest_once.py --platform qq --planted-plan data/operation-plan.json
python3.13 scripts/farm_friend_sweep.py --platform qq
python3.13 scripts/farm_daily_task_once.py --platform qq
python3.13 scripts/farm_daily_fertilizer_reward.py --platform qq
python3.13 scripts/farm_hamster_once.py --platform qq --execute
```

填写本轮计划后，先检查所选平台的步骤，再从标准农场首页启动。`--check-plan` 只读文件，农场窗口可以关闭。

```sh
python3.13 scripts/farm_plant_once.py --platform qq --check-plan
python3.13 scripts/farm_plant_once.py --platform qq --execute
```

可用退出码做 if/else 拼接。已成熟的普通作物可直接执行收获脚本。若上轮种植记录表明一次普通肥足以催熟，可以按下面的顺序衔接。

```sh
python3.13 scripts/farm_fertilize_once.py --platform qq --execute &&
  sleep 2.2 &&
  python3.13 scripts/farm_harvest_once.py --platform qq --execute
```

田内脚本执行模式退出码 `0` 表示点击已发送并完成脚本内的等待。正常流程结束时按需核对游戏画面。退出码 `2` 时读取停止原因并检查现场，避免整段重放。缺少本地 Swift 辅助程序或辅助程序有改动时，先运行以下命令。

```sh
mkdir -p _sandbox
swiftc scripts/window_registry.swift -o _sandbox/farm_window_registry
swiftc scripts/farm_click_batch.swift -o _sandbox/farm_click_batch
swiftc scripts/farm_drag.swift -o _sandbox/farm_drag
```

### 本轮计划文件

默认读取 `data/operation-plan.json`。这是每轮手动更新的本地文件，可以用 `--plan` 指定另一份同格式文件。下一轮草案保存在 `data/operation-plan-next.json`，使用前复核种子页槽。QQ 和微信各有自己的 `planting` 和 `daily`。每次启动只校验并使用所选平台的配置。

```json
{
  "qq": {
    "planting": {"special": [], "ordinary": {"page": 2, "slot": 3}},
    "daily": {"tasks": false, "fertilizer_reward": false, "share": false}
  },
  "wechat": {
    "planting": {
      "special": [{"plot": 1, "page": 2, "slot": 2}, {"plot": 7, "page": 2, "slot": 2}],
      "ordinary": {"page": 2, "slot": 3}
    },
    "daily": {"tasks": false, "fertilizer_reward": false, "share": false}
  }
}
```

- 页码从 `1` 起，槽位填 `1` 到 `5`。地块号填整数，例如 `1` 对应 01 号地。每条种植步骤填写轮到它时的实际页码和槽位。四格种子用完导致槽位前移时，后续步骤填写前移后的位置。
- `special` 按数组顺序逐颗执行，无四格填 `[]`。四格入口遵循[种植规则](docs/gameplay-rules.md#4-格特殊种子种植)，禁止重复或覆盖重叠。`ordinary` 填普通种子的页码和槽位，纯普通从 01 号地开始，混种从 24 号地补。24 已被本轮四格覆盖时，该混种计划会报错。不种普通填 `null`，两种都空时跳过种植。
- 三个日常开关都填 JSON 布尔值 `true` 或 `false`。`tasks` 是每日任务领奖，`fertilizer_reward` 是日常化肥领取，`share` 是每日分享。地里施普通肥由独立施肥脚本处理。当前种植脚本把开启的日常项目列为 `daily_pending`，由后续日常入口接入。
- 预检输出的 `steps` 每项依次为地块、页码、槽位。脚本读取计划后按本次读取的内容执行，计划文件由你手动更新。执行过的轮次再次启动仍会按文件里的步骤点按。

临时到点提醒使用工作区的 Mac「提醒事项」快捷指令。当前批次已设的提醒见 [CURRENT](docs/CURRENT.md#本轮种植与提醒)，接入规则见[共享提醒文档](../docs/reminders.md)。
