# Publisher 替代验收历史快照（2026-09-21）

归档说明：这是本次Route Lifecycle迁移期间的旧新页面对拍与验收记录，内容按当时状态保留。它不再承担当前待办、业务裁决或正式规则职责；未完成事项唯一看`tasks/todo.md`，当前规则看对应owner。

## A. 已确认的全局页面决定

- 新候选页：`data/routes/route-atlas-workbench-next.html`
- 旧/新同步对比页：`data/routes/route-atlas-workbench-compare.html`
- 旧正式页保持原样，只用于比较；当前仍未覆盖 main。
- 必须记住上次 Profile/路线，并分别记住每个 Profile 最后停留的 step。新页复用旧页键：`route-atlas:last-route` + `route-atlas:last-step:<publish_key>`，刷新后恢复。
- 中文地名默认常显，不再提供开关；2026-09-20已按旧正式页恢复HTML `span.mapLabel`显示方式，并用真实Chrome逐项对拍字体链/11px字号/字重/暖白文字/半透明深底/圆角/内边距/阴影/nowrap/pointer-events/absolute定位，当前computed-style差异为0。
- 地图固定完整路线全图，不再提供“完整路线 / 已走+当前 / 只看当前”、跟随当前段、自动缩放/裁剪。
- 不再提供速度下拉；播放固定为 1.8×。底层1×基准仍是普通路线边约1.4秒、炉石/固定任务传送类跳转约0.85秒，由单一播放倍率统一加速。
- “播放当前段 / 播放剩余路线”必须是真实地图移动动画，不允许只按固定时间切 step。
- HUD 可收起；HUD = 地图左上角当前步骤执行信息面板，承载当前 step 标题、接/做/交动作、标签与必要备注。收起/展开按钮已移回HUD标题栏右侧；“本段预计”固定保留标题栏占位，无Timing时显示“本段预计：—”；HUD正文已恢复旧版14px字号；`pending`玩家标签缩写为“待实测”，继续使用红色高强调样式。路线动作另有专用色：开飞行点=暖橙`#ff9f68`，绑定炉石=紫`#cf9cff`，不再与接/做/交复用。
- 备注规则已由用户固定，不再作为逐图密度待裁决项：普通任务备注只在`做/objective`步骤显示；任务物品触发接取可在`accept + when.has_item`步骤显示；普通接/交不重复备注。玩家投影统一去掉自己的完整任务名、迁移标记、实跑/已验证等形成过程前缀及纯fivebox状态长句；有效备注区恢复独立“备注”标题。全14路线当前玩家实际显示502条备注，原始Task Card证据不因投影精简而丢失。
- 已用真实 Chrome 验证：路线/step 恢复、完整 viewBox、无 follow 控件、播放白点移动、JS 无运行时错误。
- 2026-09-21最新浏览器级表面语义审计已通过：14 路线 / 343 step / 3904 行 / 3282 task refs / 502条实际显示备注；标签计数为待实测2209、特殊57、共享575、不共享381、依次拾取60。接=黄、做=蓝、交=绿+下划线，开飞行点=暖橙、绑定炉石=紫；备注标题/任务名自重复/过程词/DOM错色/标签错位均0问题。
- 已修 Stage 13 两个真实渲染 bug：生成 JS 的换行转义导致整页脚本失效；同一行同名任务“接→交”时第二次引用错误沿用第一次颜色。
- NPC交接连续性已从通用全量audit拆成路线设计后的独立局部优化步骤：`audit_route_interaction_continuity.py <profile>`机械发现同step/同location一轮无条件接交中被其它NPC隔开的同NPC候选，但不自动重排、不是发布硬门禁；依赖/现场顺序证明安全后才改Profile，人工/AI只补充发现。冰冠首轮已将`加拉希亚·晨光 → 交《碎盾训练》`与随后`接《学习驾驭》`排成连续run，Display机械合并为一行。

## B. 用户晚点逐图盘前，已发现的业务差异

### B1. 北风苔原 11930《横贯冰原》——用户已裁决并实施，待页面确认

当前已实施状态：
- Borean Profile 只保留：接11930 → 做11930 → 跨图移动到龙骨边界；不再在北风交任务；
- Dragonblight `entry_requirements.active_task_ids` 已要求11930，第一地点沃图克新增 `a0002 = turnin 11930`，之后才接龙骨本地图任务；
- Program Continuity已验证：北风出口11930为active/未完成，龙骨入口拿到active 11930，执行沃图克交付后变为completed；龙骨之后RouteState恢复原值，后续Program边直接复用。

页面验收时只需要确认：北风末段不再显示“交《横贯冰原》”，龙骨Step 1第一地点必须显示沃图克“交《横贯冰原》”。

### B2. 索拉查 12651《湖边着陆场》——明确替代 blocker，先不自动改

现状：
- 旧正式路线与现役索拉查骨架都要求：三条狩猎终极链与《猎人的挑战》满足后，在奈辛瓦里接 12651；之后到湖边着陆场塔玛拉处交。
- 当前 `sholazar-fivebox` 在对应位置直接跳过 12651，接点和交点都不存在。

推荐修法：
- 在现 Step 16 “炉石奈辛瓦里 → 步行回家”中恢复赫米特接 12651；
- 在现 Step 18 “河流之心 → 雨声树屋 → 雾语村”开头/到达河流之心时恢复塔玛拉交 12651；
- 不改变既有狩猎门槛，不提前去塔玛拉，也不借此重排索拉查其它动作。

正式 human-decision gate：`HD-003-sholazar-12651-lakeside-landing`，当前`open`。用户裁决：待确认。

### B3. 12181《给它一个名字》 ↔ 12188《凋零药剂与你：如何自保》——用户已裁决

- 保留 Dragonblight 的 12188 及其后续链；
- Howling 的 12181 不再考虑，不为旧页保真恢复；
- 用户后续很可能整张嚎风峡湾都不再执行，因此嚎风当前只作为待逐图审查/可能退出路线池的旧路线保留，未明确下令前不直接删除整张地图。

### B4. 已核实为预期变化，不列 blocker

- 12853《豪华的体验！》：在 Dalaran 段完成并于 K3 交，Storm Step 1 不再重复。
- 9797《支援加拉达尔》：Zang 末段正式接取并带入 Nagrand，属于当前正确 handoff。
- DK《邪恶的计划》《遗失的信件》：将旧备注里的条件事实结构化为“自然掉落/持有时才接”的动作，不是凭空新增。

## C. Timing 延后专项

当前 14 张新页面的 route timing 全部为 `requirements`，因此 `center_minutes=null`，页面只显示炉石链而不显示旧预计总时间。这不是 Stage 13 丢字段，而是 Stage 7 Timing owner 不允许未闭合输入冒充精确结果。

12 张 Program 成员的主要缺口：
- `map_dimensions_required`：缺游戏世界地图尺寸，无法把 0—100 坐标距离可靠换成移动秒数；
- `timing_rule_ref_required`：大量任务动作还没有正式 timing rule；
- `movement_action_timing_input_required`：任务传送/固定交通等缺明确耗时输入；
- `flight_edge_binding_required`：部分系统飞行边还没绑定 Leatrix/正式飞行数据；
- 少量 `conditional_hub_action_execution_maybe`、`background_marginal_timing_input_required`、`shared_service_timing_input_required`。

Program 当前仍能累计约 52699.2 秒“已知时间”，但因为并非 complete，不发布总中心值/区间。

DK 两张同样是 requirements：
- Hellfire DK：以 map dimensions、timing_rule_ref、条件 Hub、movement timing、flight binding 为主；
- Zang DK：以 timing_rule_ref、map dimensions、movement timing、条件 Hub、flight binding 为主。

处理优先级：页面替代/业务差异确认完成后再专项补 Timing，不阻塞当前页面使用验收；不得直接把旧总分钟复制进新 Timing owner 充数。

## D. 逐路线用户验收顺序

后续与用户一张一张盘，统一按：整体页面 → 地图点线 → Step 标题/顺序 → HUD 动作 → 标签/备注 → 与旧页差异 → 用户裁决。

1. 地狱火半岛：待用户审查。
2. 赞加沼泽：待用户审查。
3. 纳格兰：待用户审查。
4. 北风苔原：待用户审查；先关注 B1 / 11930。
5. 龙骨荒野：待用户审查；确认 11930 不重复；确认 B3 选择 12188。
6. 达拉然：待用户审查；12853 K3 交付视为预期变化。
7. 风暴峭壁：待用户审查；不再重复 12853。
8. 冰冠冰川：待用户审查；按已批准 v1 重排窗口对齐，不按旧/new step index 硬比较。
9. 索拉查盆地：待用户审查；先关注 B2 / 12651。
10. 祖达克：待用户审查。
11. 灰熊丘陵：待用户审查。
12. 嚎风峡湾：待用户审查；确认 B3 继续不做 12181。
13. 地狱火半岛（DK）：待用户审查；条件任务新增按 B4 处理。
14. 赞加沼泽（DK）：待用户审查。

## E. 正式切换后的清理边界

当前旧正式 HTML、旧 workbench-routes 数据和 legacy UI 测试仍暂时保留，只因为它们是本次替代验收的“旧版对照样本”。

只有用户确认新页可完全替代并实际切换后：
- 旧 builder / workbench-routes 直接写链 / 只服务旧视图模式、follow、速度下拉等代码与测试退出现役路径；
- 需要保留迁移证据的移入 archive；
- 新 SOP 未引用、又不承担历史审计价值的旧 Generated Product/候选页再做删除或归档裁决；
- 不允许 merge 时把旧旧新新两套页面生成链一起带回 main。

## F. 2026-09-21 收尾门禁状态

- 14个Profile当前Stage 11 Display全部`pass`，Stage 12 Publisher全部`pass + publishable=true`；新版候选页/纯文本player-view/旧新对比页已重新生成。
- Chrome验收：JS、刷新恢复、播放动画、固定全图、旧/新step同步、地图标签视觉、HUD字号、待实测样式、飞行点/炉石专用色、备注标题与备注清洗均通过；最新surface audit为14路线 / 343 step / 3904行 / 3282 task refs / 502条显示备注，0 issues / 0 page errors。
- Stage 10已补成独立generated artifact owner入口：主Program与两张独立DK均成功物化`review-trigger`；当前动态未成熟项合法保持`blocked_unknown / requirements`，不伪造`no_review`。
- 最新`audit_generated_cutover.py`显示：14/14 Profile均`cutover_status=pass + cutover_publishable=true`，没有Profile级cutover hard error；项目`cutover_ready=false`只因为`HD-003-sholazar-12651-lakeside-landing`仍为open。
- 因此技术/SOP替代链已具备进入main替换/合并方案设计的条件；真正覆盖旧正式页/提交main前，先裁决HD-003并按裁决结果走对应最小owner链，再重跑Stage 14。
