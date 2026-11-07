# QQ经典农场辅助 SKILL.md

## DO FIRST

1. 先读 docs/CURRENT.md 和 tasks/todo.md，确认独立操作设计范围、微信试行节奏和补采事项；需要回看点位时打开工作区根目录 _sandbox/farm-coordinate-review.html。
2. 读 docs/INDEX.md，按当前场景只加载所需规则和资料。
3. 真机观察前读 docs/CURRENT.md；有游戏操作时再读 docs/gameplay-rules.md。
4. 选种/库存/成熟时间问题：读 docs/seed-catalog.md 与 data/seed-catalog.json。
5. 新增独立动作前先读 tasks/todo.md 的后续脚本条目。
6. 历史只在考古或 NEAT 收尾时进入 docs/archive/；历史不得驱动当前坐标核对。
7. 按键精灵式独立操作见 README.md「独立操作脚本」。

## 当前阶段

当前阶段以 CURRENT 为准。按已确认的玩法与坐标设计正式流程，条件性点位按 Todo 补采。

工作方式：
- 用户逐步指挥页面、场景和点位；助手负责截图/标注/坐标整理与文档同步。
- 唯一坐标核对页是工作区根目录 _sandbox/farm-coordinate-review.html，所有场景共用。
- 候选点只有用户明确确认后才成为正式点位。
- 坐标核对阶段只标点，不点击有业务副作用的按钮。
- 用户确认的点位、映射和颜色状态是准据。重叠的旧配对、旧偏移和旧计划作废，额外旧数据等用到再核对。禁止从拖动 preview 或未验证公式推导正式坐标。
- 各操作先独立设计与验证，再由调用方按上次种植记录和 if/else 组合。进场异常与定时安排见 CURRENT 和 Todo。

## 坐标规则

- QQ 标准窗口：603×1111；微信标准农场画布：625×1155。
- 土地网格等场景层使用已验证的 scene 换算；首页贴窗口边缘的固定控件使用 fixed_ui 轴向比例换算。
- picker、弹窗、动态按钮、preview、确认按钮等未分类控件必须有直接样本验证，不能套用 scene / fixed_ui 公式。
- 窗口或场景不符合标准基线时，不得直接复用标准坐标。
- 结构化坐标事实保存在 data/ui-layout.json 和 data/ui-anchors.json；土地中心以各平台 confirmed_land_centers 显式点为准，拟合公式仅供近似。不同版本的样本不得互相冒充；pending 候选不是正式坐标。

## ENTRY MAP

| 文件 | 用途 |
| --- | --- |
| docs/CURRENT.md | 当前阶段、已确认坐标范围、现场与操作边界 |
| tasks/todo.md | 独立操作设计、真机验收和条件性补采 |
| docs/INDEX.md | 文档导航 |
| 工作区根 _sandbox/farm-coordinate-review.html | QQ / 微信统一坐标核对页 |
| data/ui-layout.json | 土地网格、标准窗口和坐标层 |
| data/ui-anchors.json | 固定 UI、已确认点与待确认候选 |
| docs/gameplay-rules.md | 游戏规则、独立动作条件和开场方式 |
| docs/seed-catalog.md / data/seed-catalog.json | 种子资料 |
| docs/farm-planning-reference.md / data/farm-planning-reference.json | 规划公式、商店种子、生长阶段和土地升级 |
| scripts/farm_fertilize_once.py | 从标准农场首页给作物施普通肥一次 |
| scripts/farm_harvest_once.py | 从标准农场首页点一次手形「一键收获」 |
| scripts/farm_plant_once.py | 从标准农场首页按本轮计划种普通种子或四格混种 |
| scripts/farm_daily_task_once.py | 当天收获后，首位好友互动一次并点一次任务领奖 |
| scripts/farm_daily_fertilizer_reward.py | 领取礼包商城的每日免费化肥 |
| scripts/farm_hamster_once.py | 从首页识别仓鼠，命中后购买一次 |
| docs/archive/ | 历史阶段归档 |

## 安全边界

- 坐标核对只标点；收获、种植、施肥、购买、领取奖励、发送分享等有业务副作用的按钮不点击。
- 仓鼠气泡只在自然出现时采集，不主动等待或制造出现条件。
- 好友农场只在用户明确授权的坐标核对或正常日常互动中观察，不主动单独进入。
- 真机输入须取得当前 Chat 对该平台及动作的明确授权。遇到账号安全或重新登录提示即停，交由用户处理。
- 候选坐标、历史截图位置和脚本常量都不能替代用户确认。

## PATHS

- 当前阶段：docs/CURRENT.md
- Todo：tasks/todo.md
- 坐标核对页：工作区根目录 _sandbox/farm-coordinate-review.html
- 网格与坐标层：data/ui-layout.json
- UI 点位：data/ui-anchors.json
- 玩法事实：docs/gameplay-rules.md
- 种子资料：docs/seed-catalog.md、data/seed-catalog.json
- 规划底表：docs/farm-planning-reference.md、data/farm-planning-reference.json
- 普通施肥一次：scripts/farm_fertilize_once.py
- 一键收获一次：scripts/farm_harvest_once.py
- 普通种植与四格混种：scripts/farm_plant_once.py、assets/ui/planting/
- 种植计划：data/operation-plan.json、data/operation-plan-next.json，设置规则见 README.md「本轮计划文件」
- 日常任务与免费化肥：scripts/farm_daily_task_once.py、scripts/farm_daily_fertilizer_reward.py，公用脚本 scripts/farm_daily_clicks.py，回家按钮模板 assets/ui/daily/
- 仓鼠：scripts/farm_hamster_once.py，按钮模板 assets/ui/merchant/
- 历史索引（含点按试验）：docs/archive/README.md
