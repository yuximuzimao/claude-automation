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

- home-check.md：首页确认器使用、识别范围及离线复验。
- ../scripts/farm_home_check.py / ../scripts/farm_home_window.swift：图片识别与QQ窗口检查入口。
- ../data/home-recognition.json / ../assets/ui/home/：首页识别配置与模板。
- ../tests/test_home_check.py：首页边界测试。
- ../tests/check_home_screenshots.py / ../tests/home-screenshot-corpus.json：本地已存截图回放与校验清单。

- automation-trial.md：连续medium收种与日常续排试验操作边界。
- inventory-sop.md：QQ仓库捕获、AI读图、库存校验回写的完整操作。
- ../data/.inventory-apply.lock：库存文件提交锁。
- ../scripts/farm_inventory.py / ../tests/test_inventory.py：库存入口与测试。
- ../assets/ui/warehouse/：仓库标题/种子页模板及来源。
- execution-tools.md：现役工具命令、返回值、诊断/安全退出和库存入口能力边界。
- operation-sop.md：按次操作决策与脚本组合入口。

- ../scripts/farm_fertilize_once.py：带一键务农和勾选确认的普通肥/QQ 有机肥；右侧肥桶模板 ../assets/ui/fertilizer/qq-organic.png。
- ../scripts/farm_harvest_once.py：实种记录校验、四格固定点和手形「一键收获」。
- ../tests/test_harvest_record.py：记录拒绝、施肥失败停止及固定点点击的无输入测试。
- ../scripts/farm_plant_once.py：普通种植与四格混种，默认读取唯一计划 ../data/operation-plan.json。
- ../scripts/farm_radish_restock.py 与 ../assets/ui/shop/qq-white-radish.png：QQ 白萝卜补货与首格识别模板。
- ../scripts/farm_radish_xp.py：QQ 白萝卜 5 轮 `种植 → 普通肥 → 有机肥 → 收获` 循环。
- ../scripts/farm_release_input.swift：动作进程组停止后的左键释放清理。
- ../scripts/farm_process.py / ../tests/test_process_cleanup.py：动作进程组清理与扫描时段启动判定。
- ../tests/test_open_qq_farm.py：QQ开窗入口无输入保护测试。
- ../data/qq-radish-progress.json：运行时成功萝卜轮次。
- ../data/hamster-inventory-pending.json：运行时仓鼠库存核对标记。
- ../scripts/farm_qq_round.py：QQ 小程序已打开后的整轮田内串联入口。
- ../scripts/farm_share_once.py：QQ固定联系人分享、领取奖励并关闭分享页；使用条件见gameplay-rules「每日首次分享」。
- ../assets/ui/share/：领取文字模板及来源。
- ../scripts/farm_daily_clicks.py / ../tests/test_friend_sweep_and_harvest.py：日常共享输入与单/双按钮交互验证。
- ../tests/test_share_once.py：分享流程及失败停止的无输入测试。
- ../tests/test_batch_m1.py：CGEvent点击与分享Unicode输入保护的编译验证测试。
- ../scripts/farm_daily_task_once.py：独立每日任务领奖工具；使用条件见operation-sop。
- ../scripts/farm_daily_fertilizer_reward.py：领取每日免费化肥。
- mischief.md：好友种草/放虫操作规则与共享次数定义。
- ../scripts/farm_mischief_once.py / ../scripts/farm_path_drag.swift：独立种草/放虫流程与连续路径拖动。
- ../assets/ui/mischief/qq-disabled-menu.png：真实双灰零回归样本。
- ../assets/ui/mischief/：操作图标、成熟提示与零次数模板，sources.json记录来源。
- ../tests/test_mischief_once.py：分支、停止、路线与原生无输入验证。
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

- archive/neat/2026-11-12-daily-zero-review-closeout.md：日常灰零与取消修正、Review范围收敛、库存核对及连续试跑授权。

- archive/neat/2026-11-12-continuous-farm-trial.md：本阶段有限续排、库存入口及收尾纠偏记录。
- archive/README.md：阶段归档索引。
- archive/：已退出当前工作流的历史阶段。
