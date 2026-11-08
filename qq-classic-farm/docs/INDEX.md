# 文档索引

这里只做文件导航，不维护业务判断。

## 当前入口

- ../SKILL.md：项目一级入口与当前坐标核对边界。
- ../CLAUDE.md：稳定工作约束与安全边界。
- CURRENT.md：平台运行状态、当前阶段与已确认坐标范围。
- ../data/wechat-live-status.txt：微信真机开关。
- ../tasks/todo.md：后续独立脚本、验收和条件性补采。
- 工作区根 _sandbox/farm-coordinate-review.html：QQ / 微信唯一统一坐标核对页。
- ../README.md：项目概览。

## 独立操作

- ../scripts/farm_fertilize_once.py：带一键务农和勾选确认的普通施肥。
- ../scripts/farm_harvest_once.py 与 ../assets/ui/harvest/：四格星标与手形「一键收获」。
- ../scripts/farm_plant_once.py：普通种植与四格混种。
- ../scripts/farm_daily_task_once.py、../scripts/farm_daily_fertilizer_reward.py：日常任务和每日免费化肥。共用 ../scripts/farm_daily_clicks.py 与 ../assets/ui/daily/ 中的回家按钮模板。
- ../scripts/farm_friend_sweep.py 与 ../assets/ui/friends/：连续拜访与两种互动按钮模板。
- ../scripts/farm_hamster_once.py：仓鼠识别与购买。购买和奖励画面模板在 ../assets/ui/merchant/。
- ../data/operation-plan.json、../data/operation-plan-next.json：本轮和下一轮计划（本地文件），字段见 ../README.md「本轮计划文件」。
- ../assets/ui/planting/：QQ / 微信种植栏第一页、开启提示和四格确认键模板。勾选状态复用 ../assets/ui/picker/ 的 `*-one-key-{on,off}.png`。
- ../assets/ui/fertilizer/：普通肥桶、未勾选框、开启提示及微信一键务农模板。两端已勾选小勾见 ../assets/ui/qq-fertilizer-onekey-tick.png、../assets/ui/wechat-fertilizer-onekey-tick.png。
- ../scripts/farm_window.py 与 ../assets/ui/window/：小程序开关及控件模板。
- ../scripts/open_qq_farm.swift：已验证的 QQ 开场入口。窗口、点按和拖动基础工具分别为 ../scripts/window_registry.swift、../scripts/farm_click_batch.swift、../scripts/farm_drag.swift。

## 坐标与稳定资料

- ../data/ui-layout.json：用户确认的土地中心、拟合网格、标准窗口与坐标层。 `plot_policy` 记录四格入口、禁点和逐格颜色状态。
- ../data/ui-anchors.json：首页固定点、场景点位、版本限定样本与待确认候选。
- gameplay-rules.md：玩法规则和独立动作条件。
- seed-catalog.md / ../data/seed-catalog.json：种子资料。
- farm-planning-reference.md / ../data/farm-planning-reference.json：规划公式、商店种子基础数据、生长阶段及 24 块地升级表。

## 历史

- archive/README.md：阶段归档索引，含坐标核对和微信点按试验。
- archive/：退出当前工作流的历史阶段。
