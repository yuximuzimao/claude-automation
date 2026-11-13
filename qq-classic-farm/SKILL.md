# QQ经典农场辅助 SKILL.md

## DO FIRST

1. 先读 `docs/CURRENT.md`，确认 QQ / 微信当前运行边界和最近现场状态。
2. 读 `tasks/todo.md` 与 `docs/INDEX.md`，确认现有功能和待办；用户发起开发或继续开发时，按 Todo 的当前优先事项进入，不先重做已验收流程。
3. 用户发起“操作农场／收菜／跑一轮”时先读 `docs/operation-sop.md`，使用上轮收尾时已校验的实种记录，根据当天已完成动作和田内状态选脚本；再按需读 `docs/gameplay-rules.md`。当前 Chat 的操作请求即为对应例行范围授权，不要求用户逐项点名脚本。
4. 选种、库存或种植计划问题读 `docs/seed-catalog.md`、`data/seed-catalog.json`；收益、经验和生长时间计算再读 `docs/farm-planning-reference.md` 与对应 JSON。
5. 任何种植后的提醒操作，先读工作区根目录 `docs/reminders.md`，复用现有快捷指令。

具体工具、完整参数、成功返回值、异常截图/关闭和未实现入口，统一见 `docs/execution-tools.md`。进入实际操作前按该页区分已具备能力与缺口，不临时选择通用桌面工具替代缺失流程。

用户明确要求定时收种、定时日常或自动安排下一轮时，先读 `docs/automation-trial.md` 的有界试验规则；通用时间转换与排期读回唯一 owner 见工作区根 `docs/scheduling.md`；当前轮次只见CURRENT。

## 当前运行边界

- **QQ：保持现有 PC 独立脚本可用。** 按用户当前授权操作；确有需要时可以继续开发 QQ 的独立功能。
- **微信：真机封存。** `data/wechat-live-status.txt` 为 `sealed`。未经用户明确恢复，不打开、不登录、不进行田内操作，也不做微信真机补采。代码、坐标和资料保留。
- **旧 Runner 已彻底退役。** 不恢复 Planner → RUN_PLAN → Runner、自恢复续跑或旧库存状态模型；用户授权的定时与有限续排边界见CURRENT。现役执行以独立脚本为单位，不另建通用执行器。
- **当前种植计划只有一份：** `data/operation-plan.json`。不再建立下一轮副本或多轮预排计划。
- QQ 自动化不等于无人监管运行；没有用户明确要求，不创建定时执行、自动重试或后台续跑。

## 种植后的强制收尾

实际种植时执行本节；白萝卜补货只执行对应补货记账，不创建收菜提醒。白萝卜月度补货与每日经验循环分开：补货脚本一次购买 37×99=3663 颗；每日白萝卜 5 轮固定消耗 120 颗，不为这些临时萝卜创建收菜提醒。

1. **按键精灵口径。** 已验证脚本正常退出 0，就按计划动作成功处理，不做例行截图、不让 Agent 再逐格判断。计划含耗尽补种时由种植脚本连续完成全部段，入口与失败边界见 operation-sop；不再交由Agent选择补种地块。其它明确 `stopped` / 非0、界面阻断或实际遗漏再诊断。
2. **实种记录写完即验。** 正式种植完成后，保存完整实种记录，立即读回并按 `docs/operation-sop.md`「实种记录的必检规范」校验；不合规当场打回重写，校验通过后再登记CURRENT，不把主校验留到下次操作。
3. **按计划扣库存。** 正式种植脚本正常完成后，四格特殊种子按计划每颗扣 1；普通种子按计划实际应铺的空格数扣减。白萝卜经验循环正常完成后按 `轮数 × 24` 扣减白萝卜已知库存。更新 `data/seed-catalog.json` 与 `docs/seed-catalog.md`，具体工具/字段及重复扣减检查见种子文档“文件回写步骤”，不为正常轮次重新打开仓库。
4. **白萝卜补货是唯一购买例外。** `farm_radish_restock.py` 正常完成后，按实际完成购买次数 ×99 直接增加白萝卜已知库存；默认 37 次即 +3663，不再为这次补货打开仓库清点。
5. **补记人工种植。** 如果 `docs/CURRENT.md` 明确记录有一轮用户手动种植尚未入账，则下一次由助手完成正式种植后，把这笔待补差额和本轮差额一起写入，再清掉待补标记。
6. **其他操作不更新库存。** 收获、施肥、日常、好友互动都不改库存。
7. **其它新种子才重扫。** 仓鼠末尾购买后的库存刷新已经获得用户授权，按 `docs/operation-sop.md`“仓鼠末尾收尾”执行，包括新种子重开后的顺序核对；完整调用及已验收范围见docs/inventory-sop.md，使用farm_inventory捕获、AI读图及apply回写；陌生未建档种子仍需补资料。用户购买/获得了萝卜以外的其它种子并明确要求更新库存时，再完整打开仓库「种子」页清点，更新数量与顺序，直接读取值标为 `verified`。
8. **计算提醒时间。** 先确定本批正式作物预计成熟时刻。若规划底表有可靠的阶段数据，则提醒设在“最后一个非零生长阶段开始”时刻：`成熟时刻 − 最后非零阶段基础秒数 × 对应土地耗时倍率`。若没有可用阶段数据，才回退为成熟前 1 小时。 自动排期若按用户当前规则改为提前一阶段双肥，介入时间选择见automation-trial、动作顺序见operation-sop§2，提醒随选定介入时间，不在提示词重复定义。
9. **同批混种。** 统一收菜的一批作物若提醒时刻不同，取最早需要介入的提醒时刻，避免错过任何作物的最后阶段。
10. **创建并核验提醒。** 按工作区根 `docs/reminders.md` 调用现有「创建提醒」快捷指令，再读回标题和时间。提醒发送失败要明确报告。

打开小程序脚本完成后运行 `farm_home_check.py --live --prepare`：激活现有农场、等待5秒并确认标准无遮挡首页；仅 `ready_for_input=true` 才运行内部连续脚本，失败时交Agent核实。关闭后确认窗口状态。田内固定动作不插入额外 Agent 视觉确认。库存数量是最近一次仓库清点加已记录操作增减后的已知值，不是实时仓库真值。

## 坐标与操作规则

- QQ 标准窗口：603×1111；微信标准农场画布：625×1155。
- 土地中心和随场景移动的对象使用已验证的 `scene` 层；贴窗口边缘的首页控件使用 `fixed_ui` 层。
- picker、弹窗、动态按钮、preview、确认按钮等未分类控件必须有直接样本验证，不能套用 scene / fixed_ui 公式。
- 土地中心以 `data/ui-layout.json` 中用户确认的显式点为准；拟合公式只作近似。候选点不是正式坐标。
- 坐标核对只在用户明确要求时进行，并且只标点、截图和整理资料；不点击收获、种植、施肥、购买、领奖或分享等有副作用的按钮。
- 好友连续互动每位只识别底部小条并点击一次。双按钮只点击其中一个识别到的按钮中心；点击后不再检查重排后的单按钮，直接进入下一位好友。
- 日常脚本选择以operation-sop为准；每日任务领奖工具保留供明确单独请求时使用，例行安排不调用。
- 真机操作遇到账号安全、重新登录或授权提示立即停止，交由用户处理；不得盲目重试。

## ENTRY MAP

| 文件 | 用途 |
| --- | --- |
| `docs/inventory-sop.md` | 仓库捕获、AI读图、库存回写与待核标记处理 |
| `data/.inventory-apply.lock` | 库存文件读改写的本地提交锁；不承担桌面互斥 |
| `scripts/farm_inventory.py` / `tests/test_inventory.py` | QQ完整库存捕获和校验回写入口及无输入测试 |
| `assets/ui/warehouse/` | 仓库标题/种子页模板及真实截图来源 |
| `docs/execution-tools.md` | 具体工具调用、返回判据、诊断/退出与缺失能力 |
| `docs/automation-trial.md` | 收种与日常的有限续排规则 |
| `docs/archive/neat/2026-11-12-continuous-farm-trial.md` | 本阶段收种、库存入口和有限续排试验归档 |
| `docs/archive/neat/2026-11-12-daily-zero-review-closeout.md` | 日常灰零、Review收敛及连续试跑阶段归档 |
| `docs/CURRENT.md` | 当前平台状态、最近现场与现行计划 |
| `data/wechat-live-status.txt` | 微信真机封存开关 |
| `tasks/todo.md` | QQ 可按需开发的功能与条件性补采 |
| 工作区根 `_sandbox/farm-coordinate-review.html` | QQ / 微信统一坐标核对页 |
| `data/ui-layout.json` | 土地中心、四格映射、土地等级与坐标层 |
| `data/ui-anchors.json` | 固定 UI、场景点位与待确认候选 |
| `docs/operation-sop.md` | 按日期、已完成项目和土地状态选择脚本；耗尽补种接续 |
| `docs/gameplay-rules.md` | 玩法规则与独立动作条件 |
| `docs/seed-catalog.md` / `data/seed-catalog.json` | 种子资料与已知库存 |
| `docs/farm-planning-reference.md` / `data/farm-planning-reference.json` | 收益、经验、生长阶段和土地升级计算 |
| `data/operation-plan.json` | 唯一种植计划 |
| `docs/home-check.md` | 本地首页确认器的模式、识别边界与离线复验入口 |
| `scripts/farm_home_check.py` / `scripts/farm_home_window.swift` | 图片首页识别与QQ窗口状态检查 |
| `data/home-recognition.json` / `assets/ui/home/` | 首页识别配置、模板和来源记录 |
| `tests/test_home_check.py` / `tests/check_home_screenshots.py` / `tests/home-screenshot-corpus.json` | 首页边界测试与本地历史截图回放清单 |
| `scripts/farm_window.py` | 小程序开关 |
| `scripts/farm_fertilize_once.py` / `assets/ui/fertilizer/qq-organic.png` | 普通肥与 QQ 有机肥图片定位 |
| `scripts/farm_level_up.py` / `assets/ui/level-up/` / `tests/test_level_up.py` | QQ 经验动作后的升级提示局部识别及离线验证 |
| `scripts/farm_harvest_once.py` | 实种记录离线校验、四格固定点与手形一键收获 |
| `tests/test_harvest_record.py` | 实种记录前置拒绝、成熟条件及固定点收获的无输入测试 |
| `scripts/farm_plant_once.py` | 普通种植与四格混种 |
| `scripts/farm_radish_restock.py` / `assets/ui/shop/qq-white-radish.png` | QQ 白萝卜月度补货及商店首格识图模板；流程见 `docs/gameplay-rules.md`「白萝卜补货」 |
| `scripts/farm_radish_xp.py` | QQ 白萝卜 5 轮种植→普通肥→有机肥→收获循环 |
| `scripts/farm_release_input.swift` | 异常停止后仅释放左键；正常流程不调用 |
| `scripts/farm_process.py` / `tests/test_process_cleanup.py` | 动作进程组清理与售后扫描启动避让 |
| `tests/test_open_qq_farm.py` | 开窗入口身份、遮挡和焦点无输入验证 |
| `data/qq-radish-progress.json` | 运行时每日成功收获萝卜轮数；按需创建 |
| `data/hamster-inventory-pending.json` | 仓鼠购买后库存核对标记；核清后移除 |
| `scripts/farm_qq_round.py` | QQ 小程序已打开后的整轮田内串行入口 |
| `assets/ui/share/` | 分享领取文字模板与来源；点击前拒绝同位置分享按钮 |
| `scripts/farm_daily_clicks.py` / `tests/test_friend_sweep_and_harvest.py` | 日常共享输入与单/双按钮交互验证 |
| `scripts/farm_share_once.py` | QQ固定联系人分享、领奖并回土地；流程与验收边界见gameplay-rules「每日首次分享」 |
| `scripts/farm_daily_task_once.py` | 互动首位可互动好友 + 每日任务领奖；仅明确单独请求时使用 |
| `scripts/farm_daily_fertilizer_reward.py` | 每日免费化肥 |
| `docs/mischief.md` | 好友种草/放虫流程、共享次数与验收入口 |
| `scripts/farm_mischief_once.py` / `scripts/farm_path_drag.swift` | 好友种草/放虫独立流程与连续拖动工具 |
| `assets/ui/mischief/` / `tests/test_mischief_once.py` | 用户截图控件模板、来源及无输入测试 |
| `assets/ui/mischief/qq-disabled-menu.png` | 真实双灰零回归样本 |
| `scripts/farm_friend_sweep.py` | 好友连续互动，按识别到的实际按钮中心点击 |
| `tests/test_share_once.py` / `tests/test_batch_m1.py` | 分享流程无输入测试与CGEvent输入保护测试 |
| `scripts/farm_hamster_once.py` | 仓鼠识别与购买 |
| `../docs/reminders.md` | 共享 Mac 提醒事项接入协议 |
| `docs/archive/README.md` | 历史阶段索引（含收种与单次任务归档） |
