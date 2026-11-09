# 文档索引

这里只做文件导航，不维护业务判断。

## 当前入口

- ../SKILL.md：项目一级入口、平台边界和种植后强制收尾。
- ../CLAUDE.md：稳定工作约束与安全边界。
- CURRENT.md：平台运行状态、最近现场与当前种植计划。
- ../data/wechat-live-status.txt：微信真机封存开关。
- ../tasks/todo.md：QQ 可按需开发的功能与条件性补采。
- ../README.md：项目概览与独立脚本用法。
- 工作区根 _sandbox/farm-coordinate-review.html：QQ / 微信统一坐标核对页。
- 工作区根 docs/reminders.md：共享 Mac 提醒事项接入与排查。

## 独立操作

- ../scripts/farm_fertilize_once.py：带一键务农和勾选确认的普通施肥。
- ../scripts/farm_harvest_once.py 与 ../assets/ui/harvest/：四格星标与手形「一键收获」。
- ../scripts/farm_plant_once.py：普通种植与四格混种，默认读取唯一计划 ../data/operation-plan.json。
- ../scripts/farm_radish_restock.py：QQ 白萝卜月度补货，MAX 99 ×37。
- ../scripts/farm_radish_xp.py：QQ 白萝卜 5 轮 `种植 → 普通肥 → 收获` 循环。
- ../scripts/farm_qq_round.py：QQ 小程序已打开后的整轮田内串联入口。
- ../scripts/farm_daily_task_once.py：互动当前首位可互动好友并领取任务书奖励；整轮中先执行它，再做好友全扫。
- ../scripts/farm_daily_fertilizer_reward.py：领取每日免费化肥。
- ../scripts/farm_friend_sweep.py 与 ../assets/ui/friends/：连续拜访好友，点击实时识别到的偷取/务农按钮中心。
- ../scripts/farm_hamster_once.py：仓鼠识别与购买。购买和奖励画面模板在 ../assets/ui/merchant/。
- ../assets/ui/planting/：QQ / 微信种植栏第一页、开启提示和四格确认键模板。勾选状态复用 ../assets/ui/picker/ 的 `*-one-key-{on,off}.png`。
- ../assets/ui/fertilizer/：普通肥桶、未勾选框、开启提示及微信一键务农模板。
- ../scripts/farm_window.py 与 ../assets/ui/window/：小程序开关及控件模板。
- ../scripts/open_qq_farm.swift：已验证的 QQ 开场入口。窗口、点按和拖动基础工具分别为 ../scripts/window_registry.swift、../scripts/farm_click_batch.swift、../scripts/farm_drag.swift。

微信真机操作封存期间保留脚本和模板，但不得运行微信真机流程。

## 坐标与稳定资料

- ../data/ui-layout.json：用户确认的土地中心、拟合网格、标准窗口与坐标层；`plot_policy` 记录四格入口、禁点和逐格颜色状态。
- ../data/ui-anchors.json：首页固定点、场景点位、版本限定样本与待确认候选。
- gameplay-rules.md：玩法规则和独立动作条件。
- seed-catalog.md / ../data/seed-catalog.json：种子资料与已知库存。
- farm-planning-reference.md / ../data/farm-planning-reference.json：规划公式、商店种子基础数据、生长阶段及 24 块地升级表。
- ../data/operation-plan.json：唯一当前种植计划。

## 历史

- archive/README.md：阶段归档索引。
- archive/：已退出当前工作流的历史阶段。
