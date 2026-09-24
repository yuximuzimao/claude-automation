# 2026-09 Route Lifecycle 架构迁移历史索引

用途：只保存本次架构迁移的形成过程、阶段材料和当前替代状态入口。它不是永久SOP，也不定义以后任何一次迁移必须照抄的步骤。

## 本次迁移目标

把旧Route Atlas/semantic/builder混合真源迁到当前单一职责架构：

Task Card / Route Profile / Route Program / Rules & Models / Observations / Generated Product / Publisher / Player Assets。

本次迁移中的Stage编号、建设顺序、旧消费者退役顺序和Publisher对拍方法只属于这次历史。

## 主要历史入口

- 架构治理验收：`2026-09-15-architecture-governance-acceptance.md`
- 架构迁移矩阵：`2026-09-15-architecture-governance-migration-matrix.md`
- 生成依赖审计：`2026-09-16-route-generation-dependency-audit.md`
- Stage 1–3 / SOP验证恢复记录：`../archive/neat/2026-09-16-route-lifecycle-sop-validation-handoff-neat.md`
- Stage 8 / DK恢复记录：`../archive/neat/2026-09-17-route-lifecycle-stage8-and-dk-live-anchor-neat.md`
- 跨图转场与冰冠迁移记录：`../archive/neat/2026-09-19-cross-map-transition-and-icecrown-migration-neat.md`
- SOP实跑可接入与纳格兰handoff记录：`../archive/neat/2026-09-19-sop-live-run-ready-and-nagrand-handoff-neat.md`
- Publisher替代审查历史快照：`../archive/analysis/2026-09-21-publisher-replacement-review.md`

## 当前状态

截至2026-09-25：

- 新Route Lifecycle各owner已有独立实现入口，正式操作已归回对应owner，不再维护中央execution文档；
- 新Publisher / Player Assets已完成14个Profile浏览器与语义验收；
- Review Trigger已物化为正式generated artifact；
- 用户裁决保留旧路线中的12651《湖边着陆场》；现役Sholazar Profile已恢复“赫米特接取 → 塔玛拉交付”，并清理与旧正式路线相冲突的单边12651→12654互斥迁移错误；
- 项目最终机械cutover为`cutover_status=pass`、`cutover_ready=true`，14/14 Profile均`cutover_publishable=true`且无cutover error；
- 正式`data/routes/route-atlas-workbench.html`与`player-view/`已由当前Publisher payload经Stage 13唯一渲染入口直接生成；
- 本次candidate/compare/旧正式builder等迁移专用路径已完成反向审计：长期有价值的JS/恢复播放/正式页面语义审计能力改为直接验证正式页面，其余迁移专用工具与产物归档；
- 未完成事项唯一读Todo；原独立human-decision ledger已退出当前体系。

实时未完成工作只看`tasks/todo.md`，当前实跑状态只看`docs/verified-routes/CURRENT.md`；本文件只保存迁移形成过程。

## 2026-09-25治理收口

本轮最终确认：
- 工作区级渐进式披露、README/Todo/Skill/SOP/Owner职责与“现役/历史二分、无长期兼容层”已经上提到工作区根`/Users/chat/claude/CLAUDE.md`；
- 项目`SKILL.md`只做成熟低歧义一级分流，Route Lifecycle内部歧义交给`ROUTE-DESIGN-PROCESS.md`；
- SOP只分类并指向唯一owner，规则与正式操作归回对应owner；
- `docs/rules/README.md`和`docs/INDEX.md`只做目录/导航；
- 所有未完成事项只在`tasks/todo.md`，机器cutover直接读取Todo blocker；
- 迁移期间试验过的独立workflow governance、中央lifecycle execution、human-decision ledger和state compatibility pointer均退出当前体系；
- Publisher替代审查的已完成内容只作为历史快照归档，不再承担待办或当前规则职责。

## 迁移完成后的处理

本次替代已完成：
- 本迁移历史进入archive；
- 迁移期candidate/compare/audit工具已按正向+反向消费者审查归档或转为正式页面唯一现役审计；
- 永久SOP继续只保留“如何识别ARCHITECTURE_MIGRATION并进入当次独立迁移记录”，不保留本次Stage建设步骤；
- 后续Route Atlas逐图前端规则审计、延期备注清理和DK实跑均作为普通未完成工作继续留在Todo，不重新打开本迁移。

## 迁移期完成事项原始快照

以下条目原文从当前Todo移出，仅作为本次迁移历史，不再承担当前规则或操作入口。它们是当时的状态快照；例如后续又发现HD-003，因此其中“人工决策已清零”等旧句不得解释为当前状态：

- [x] **完成旧信息→新真源的当前阻塞语义review与归属审计。** Evidence Index覆盖项目4505个task_id；正式迁移目标现为1084张Task Card，精确rewards全部verified，`unresolved_workbench=0`，Questie Corrections解析失败=0，最终机械重跑=`1084 unchanged / 0 updated / 0 review`，`review-queue.json`当前`task_review_count=0`。旧fivebox已固化202种映射/334个任务。83个旧人工`final_review.facts`已逐task复核：76个补入guide，7个确认无新增任务固有事实；76个旧正式workbench备注已先无损保全到Presentation。13677按当前服务器/Journey证据采用《学习驾驭》，Questie《学习骑战》保留为来源冲突证据。按用户决策，236段旧fivebox长备注不再阻塞迁移：已无损放入`presentation.note_override`并仅对这些段落加`【需要单独修正优化】`标记；47条尚未实测的fivebox问题无损转入`tasks/task-card-migration/fivebox-validation-todo.json`，Task Card继续以`pending`表达未知。后两项均转为后续专项优化/自然实测待办，不阻塞候选Publisher。
- [x] **各owner算法/合同的迁移实现已完成，但原“每次固定Stage 1→14全跑”的执行模型已于2026-09-19废止。** 14类owner仍用于说明职责和完整诊断；日常业务修改改为严格读SOP变更路由表，只运行本次受影响owner及其明确下游。fingerprint/hash只做审计，不负责freshness调度；`rebuild_route_profile.py`只保留显式完整诊断，不再是更新/Publisher总入口。
- [x] **Stage 1–7 implementation 已按SOP形成“状态→空间→服务→Timing”唯一执行闭环。** Stage 1–6沿用既有闭合结果；Stage 7现役唯一执行链已切到`lib/route_timing.py` + `scripts/rebuild_route_profile.py`：Timing只消费Stage 4 Replay的`action_execution`、Stage 5 canonical movement/Program boundary和Stage 6 Service Context，不再从条件、旧transport、guide、HTML或旧step分钟重复推理；Questie objective数量解析已从旧foundation脚本提成共享Effective Quest Source adapter，reviewed task参数可显式覆盖机械基线；Leatrix只经reviewed Profile/Program flight-edge binding进入，无binding/源文件即UNKNOWN；旧24条Timing run已无损迁为Observation但按clean + Profile/version + action range门禁后当前0条可自动校准；range只来自版本化component uncertainty或足够匹配的clean Observation；缺输入时保留partial `known_seconds`而不伪造center/range。Program Timing按Stage 4顺序聚合成员结果并单独计Stage 5跨Profile边界，禁止各图旧总时长直接相加。旧`estimate_route_atlas_timing.py` CLI/main已硬退役，仅保留helper作历史迁移/UI回归证据。真实`horde-fivebox-full-clear`迁移前fixture已冻结：Stage 7 implementation=`implemented`而当前artifact=`blocked`，known=52933.2s、center/range=null，证明基建完成不要求路线/Timing数据全绿；对应真实fixture测试已通过。
- [x] **Stage 8 Derived XP / Level Timeline implementation 已按SOP §17.2收口。** `data/xp-model/model-config.json` + `lib/route_xp.py`现为唯一XP owner，统一服务器任务XP倍率、1–80升级经验表、任务经验按实际交付等级衰减/取整、五号独立level/xp推进、跨Profile fresh XP传播与Stage 3 `min_level`延期门槛；唯一`rebuild_route_profile.py`提供显式`--xp-input`，无结构化起点时保持requirements且禁止从标题/goal/旧预算猜等级。保证账只算确定任务XP，自然经验默认不进入保证下界；风险上界若因提前升级改变后续衰减则保持UNKNOWN。现役达拉然/Northrend foundation倍率已切到`wotlk_quest_rewards`→Stage 8 owner/config；剩余硬编码只存在于明确硬退役的旧35–55/68–80证据脚本。真实`hellfire-dk-speed`冻结fixture以显式60级/0经验验证输入跑出55次确定turnin、59个等级门槛、保证/上界911750 XP并保留3个条件分支requirements；Stage 7迁移测试的下一未实现层已同步为Stage 9。最终Stage 3/4/7/8相关收口回归除该已修正旧断言外均通过，修正后Stage 7+8真实fixture 2/2通过。
- [x] **Stage 9 Derived Economy / G-hour implementation 已按SOP §17.2收口。** `data/economy-model/model-config.json` + `lib/route_economy.py`现为唯一Economy owner，消费Task Card rewards、fresh Stage 8逐角色交付等级和fresh Stage 7 Timing；满级折金统一使用80级衰减/取整后的基础XP×6铜，`QUEST_FLAGS_NO_MONEY_FROM_XP=0x100`已由Effective Quest Source机械迁入正式Task Card `rewards.no_money_from_xp`。正式1084张Task Card迁移后Evidence Index重建幂等=`1084 unchanged / 0 updated / 0 review`；真实`hellfire-dk-speed`迁移前/后fixture证明缺flag时只保留已知值，补齐后仅消除该requirement，Stage 7/8既有UNKNOWN仍阻止伪造G/hour。Economy Observation现有Profile/Program精确version绑定、原始金币差/资产数量/污染事实和显式市场估值门禁；当前无可无损迁移的历史完整经济样本，因此正式Observation集合保持空，不拿KPI/旧模型冒充实跑。旧`build_quest_reward_economy.py`已硬退役，冰冠维护audit不再用旧`level_80_economy`触发review；旧foundation/report字段仅作compatibility/history evidence。
- [x] **Stage 10 Review Trigger Gate implementation 已按SOP形成独立执行闭环。** `data/review-trigger/model-config.json` + `lib/route_review_trigger.py`为唯一Review Trigger算法owner；日常独立执行入口已补为`scripts/build_route_review_trigger.py`，只读取当前Stage 3/4–9 generated artifacts与可选version-bound Review Context，并把结果作为`review-trigger` artifact写入统一generated store；`rebuild_route_profile.py`只保留完整诊断用途，不再是Stage 10唯一入口。Program成员统一物化Program级Review Trigger，独立Profile物化Profile级Review Trigger；Stage 14现直接消费该artifact，不再硬编码“Review Trigger未物化= requirements”。Selection八类触发ID与Optimization十四个Hard Validator ID只作为现役owner的机器投影，不拥有第二套业务语义；Review Context必须精确绑定Profile/version或Program/version并声明coverage/source，缺输入、旧version、上游非fresh或Validator UNKNOWN均fail-closed为`blocked_unknown`。`selection_review`只请求继续按Selection比较now/later/never，`optimization_review`只请求回Route Optimization检查受影响窗口；Stage 10本身永不删任务、写Task Card、决定删留或重排Profile。2026-09-21已用当前主Program与两张独立DK实际跑通独立入口，均在缺完整Review Context/上游requirements时合法保持`blocked_unknown → requirements`。
- [x] **Stage 11 Display + Task Presentation implementation 已按SOP §17.2收口。** 新`lib/route_display.py`现为唯一玩家语义投影层，并由`rebuild_route_profile.py`接入；只消费Route Profile原子actions/stepGroups/geometry、当前Task Card identity/fivebox/presentation、fresh Stage 7 Timing与Stage 5/10 freshness，不读取旧`route-models`、workbench、semantic prose或HTML fallback。Stage 11只输出结构化地点/NPC/接做交/交通/步骤/Task Presentation，不生成HTML/CSS；Timing只有`complete=true`时才显示精确route/step分钟，上游blocked时仍可产诊断投影但artifact保持blocked。真实`hellfire-dk-speed`冻结fixture保持11步骤、153个正式task action→153个显示task ref、186行语义、86个step-task presentation且无HTML；当前4个地点名与NPC/交互对象重合、2个地点名直接编码交通/移动句，均只记录迁移requirement，不为追绿改Profile。Stage 7–11联动回归27/27通过，旧Publisher/Task Presentation/Registry兼容回归18/18通过。
- [x] **Stage 12 Publisher Payload implementation 已按SOP §17.2收口。** 新`lib/route_publisher_payload.py`现为唯一Stage 12纯JSON发布载荷入口，并由`rebuild_route_profile.py`接入；只接受Stage 11 `route_display`报告与同Profile的`data/route-ui/<profile_id>.json`，不重新加载/解释Route Profile、Task Card、旧Timing route-model、workbench、semantic prose或HTML。Stage 11 steps/Task Presentation/Timing与Stage 5 canonical movement经Stage 11投影后的`map_geometry`原样进入payload，Route UI只补纯视觉map labels；Profile/version、可选Program上下文、Stage 11 fingerprint与Publisher fingerprint全部保留，地图路径强制为离线`maps/`相对路径。Stage 11 requirements/blocked时只生成`publishable=false`诊断payload。真实`hellfire-dk-speed`冻结fixture保持11步、153个task ref、11个UI标签、63 visits/62 canonical edges且0个visit缺step映射，旧`points/actionHtml/noteHtml`不再进入新payload；当前上游blocked继续令Stage 12 blocked，不为发布追绿。Stage 7–12联动回归34/34通过。
- [x] **Stage 13 HTML / Player View / Offline Assets implementation 已按SOP §17.2收口。** 新`lib/route_player_assets.py`现为唯一Stage 13渲染入口：workbench HTML与纯文本player-view都直接消费Stage 12 Publisher payload；HTML在构建时内嵌payload，运行时只读取`maps/...`本地资源，不依赖Python/项目JSON/manifest/网络；player-view直接遍历steps/lines/task_presentations，不再从HTML剥文本。现役页面合同已按2026-09-20替代验收修正为：Profile切换、上一/下一段、步骤点击、真实当前段/剩余路线地图动画、HUD收起，以及“上次Profile + 每Profile最后step”恢复；地图固定完整路线全图，中文地名默认常显，不再保留“完整/已走+当前/只看当前”、跟随/自动zoom或速度档位，播放固定1×基准。Stage 13浏览器验收还修复了两项真实渲染bug：生成JS换行转义会令整页脚本失效；同一行同名任务“接→交”时第二次task ref会错误沿用第一次颜色。旧`build_route_atlas_workbench.py`与`export_route_atlas_player_view.py`继续作为legacy对照，待替代验收通过后归档/退役，不再作为新页面owner。
- [x] **Stage 14 Mechanical Audit + Player Cold Read implementation 已按SOP §17.2收口；Route Lifecycle Stage 1–14 implementation 至此完整闭环。** 新`docs/rules/route-lifecycle-final-audit.md` + `lib/route_final_audit.py`为唯一最终审计owner/机器入口，并由统一`rebuild_route_profile.py`执行：只汇总Stage 1–13顺序/implementation/evaluation、Stage 1 root fingerprint、Stage 11→12→13 fingerprint链、现役旧消费者边界和最终player-view冷读，不重新计算前层业务事实。项目级`evaluate_project_final_audit()`要求显式完整`required_profile_ids`，单Profile通过不得冒充全项目切换。真实`hellfire-dk-speed`冻结结果：14层implementation=`complete`、`unimplemented_stages=[]`，但当前artifact仍`blocked`；前13层有7个blocked、4个requirements，冷读11个步骤全部因动作正文>约10行进入人工复核，未自动拆步/修路线；无fingerprint串版本、legacy consumer复活、内部token/旧fallback泄漏。Stage 7–14 + Registry最终联动回归59/59通过。
- [x] **SOP自身最终逐枝干收口审计完成。** `ROUTE-DESIGN-PROCESS.md`已清理Stage 8–14完成后遗留的旧“未闭合/必须迁移”状态描述，新增§1.5统一异常/诊断路由与§17.5 SOP自身完整性定义；14类顶层变更均有独立可执行章节，`docs/rules/`每个永久owner都能反查到SOP入口/终点，主要失败类（implementation缺陷、requirements、来源冲突、迁移保真、真实业务错误、Selection/Optimization决策、模型、Presentation/UI、stale/fingerprint、legacy consumer、CURRENT stale、冷读、未裁决现场输入）均有唯一下一步。Rule Routing测试已增加防回归门禁：新增变更类型/owner缺SOP路径、旧迁移状态复活或异常路由缺项都会失败。
- [x] **“变更驱动执行”切换已完成。** 已废止`--all`全Profile循环与正式写页入口；Profile Replay/Movement/Service/Timing/XP/Economy均有独立generated-store入口。Program层已拆为Continuity/Movement/Service/Timing/XP/Economy：成员Continuity与XP只从变化点向后传播，Movement只读成员Movement artifact，Service/Timing/Economy只重算真实受影响成员并重新聚合；Program顺序/version/entry contract变化才允许完整Continuity基线。Presentation正式链直接`update_route_display_task.py → rebuild_publisher_payload.py → render_route_assets.py`，`build_task_presentation.py`仅检查。机械回归已证明Program Movement不重算成员Movement、Timing单成员更新不重算其它成员、XP保留前缀、Economy保留其它成员、Continuity保留前缀edge并只Replay后缀。完整Stage 1–14只保留专项诊断。
- [x] **Stage 3诊断期候选纠错已完成业务裁决。** Storm / Grizzly仅做迁移语义清理；Zul'Drak复合交通按旧玩家动作保真；Sholazar 12521已确认是达拉然早接、冰冠后晚用的跨地图承接；Icecrown正式v1已重新验收；13230前置状态已纠正；13276仅属13264后的重复日常版本，不进入一次性主路线。`9498/9499《猎鹰岗哨》`继续作为用户实跑+本地数据库独立确认的种族分支事实保留。日常任务不得按标签机械删除：首次执行若承担前置、解锁后续或属于正式路线首轮选择则保留，只排除后续纯重复执行。
- [x] **最终人工决策清单已清零。** 唯一ledger仍为`tasks/final-human-decisions.json`；HD-002纳格兰→北风苔原跨大陆链已关闭，HD-001《阿达尔的恩赐》也已按用户正式路线决定关闭：达拉然→炉石暗影拱顶→自主飞往沉默墓地。当前无`open`人工决策，不再因该ledger阻止`cutover_ready`。
- [x] **Icecrown 2026-08-30正式v1重排已从“只修尾段”扩大为前半→中段→尾段完整迁移保真修复。** 进一步审计发现旧Profile不仅尾段落后：暗影拱顶/Jotunheim整块被放在银色前线主线之前，黑色观察站第二阶段过早，《机会》地下链晚于莫德雷萨，《绿色科技》《预览》《离别礼物》均存在“解锁即做”旧顺序。现已按现役v1/builder只重排既有action block：银色前线/北伐军之峰→暗影拱顶/Jotunheim→先锋军港口→黑色观察站前半→第一次东行→机会地下→莫德雷萨/失落希望→辛达苟萨/白骨之庭→黑色观察站第二阶段→银色北伐军/救治链→奥尔杜萨整块→暗影拱顶后段→最终南扫/科雷萨/苦难高地。正式Profile由758→760 actions、55→56 steps；唯一action集合净变化是新增13264/13277/13379三项本图正确接取、删除错误的日常版13276接取，最终出口仍为`icecrown-p240 / 奥格瑞姆之锤`。候选Replay=0 error，18条关键顺序断言全通过，正式基础契约/Replay/Continuity/Movement/Program回归57/57通过；Stage 3真实fixture 2/2通过。Stage 4真实fixture仍断言旧`blocked`而当前已正确变为`requirements`；Stage 5两个pre-migration fixture同样冻结旧迁移状态，后续按stale fixture处理，不为旧断言回滚路线。
- [x] **Stage 5普通movement缺口已按2026-09-19用户口径收口。** 普通点到点与跨地图跑图默认都是自主移动，不再要求人工证明骑马/步行或为缺`ride`标签制造requirement；未显式给mode时Timing按普通地面坐骑粗算，圣骑使用职业移动加速校准。跨地图自主转场保留可读链路但排除在单地图墙钟/G小时之外。任务传送/位面/载具等只有结束位置会改变后续路线选择时才要求最小位置上下文；否则直接沿既定任务链/下一动作继续。真正会改变玩家操作且证据不足的跨地图问题只留在最终人工决策ledger，不再以普通movement UNKNOWN重复阻塞。
- [x] **Program Stage 4 的状态连续性 blocker 已清到只剩1个结构表达缺口，但这不再等价于玩家路线动作完整。** 9912、9797、11864、12853等跨Profile状态/归属修正仍有效；11930已按2026-09-20用户裁决修正为Borean接+做并以active状态跨图、Dragonblight入口沃图克交付；Program Continuity已验证Borean出口active→Dragonblight入口active→交付后completed，并在龙骨出口恢复原RouteState。最新Program Stage 4仍为`requirements`，`required_active_tasks_missing=0`、`exclusive_task_conflict=0`、`required_active_tasks_not_provable=1`且唯一对象为12839《元帅的计划》；这类状态证明不得再被拿来替代玩家页面语义保真检查。12839继续按item-start结构表达缺口保留UNKNOWN，不伪造必掉或普通accept。
- [x] **cutover硬门槛范围已按第一目标拆开。** 路线/Profile结构错误、已确认顺序/前置矛盾、Program状态矛盾、玩家动作丢失/错位、地图资源错误及发布链串版本仍是硬阻断；Timing/XP/Economy未成熟、fivebox pending、Presentation后置清理和非关键冷读债务继续保留诊断但不再单独阻止静态页面切换。不得伪造UNKNOWN追绿。

## 迁移期完成事项原始快照（补充）

以下原文从当前Todo的重复总清单移出，仅作本次迁移历史：

1. [x] **特殊任务结束位置的路线表达已收口。** 位面/任务传送/任务载具等若后续由任务链、固定交接NPC或既定下一动作唯一决定，不要求补任务结束坐标；Task Card备注负责“怎么做”，Route Profile只保留“做完后下一步做什么”。只有结束位置会改变后续编排时才记录最小位置上下文；护送可用结束区域/方向/下一目标，不强制精确坐标。特殊任务Timing先按现有模型粗算，最终由段落实跑覆盖。
2. [x] **Stage 5普通自主移动与跨地图转场口径已收口。** 普通点到点统一视为自主移动，不要求为路线业务确认骑马/步行；Timing缺mode时按普通地面坐骑粗算。跨地图仍保留可读转场链（如“地狱火半岛塞纳里奥哨站 → 赞加沼泽塞纳里奥庇护所”或“纳格兰收尾 → 沙塔斯 → 奥格瑞玛 → 准备诺森德”），但不计入任一单地图墙钟/G小时。只有未知位置会真实改变下一步路线选择时才继续保留UNKNOWN。
3. [x] **最终人工决策已清零。** HD-002纳格兰→泰罗卡收尾→沙塔斯→奥格瑞玛→飞艇→北风苔原已关闭；HD-001固定为“沙塔斯接《阿达尔的恩赐》→任务传送达拉然→炉石暗影拱顶→自主飞往沉默墓地→交任务”。不再追溯历史首跑是否完全同路。
4. [x] **Stage 3诊断期候选业务修改已完成业务裁决。** Storm / Grizzly仅删除错误特殊交通样式提示，玩家语义不变；Zul'Drak复合交通属于旧玩家动作的结构化保真；Sholazar 12521已确认是“首次达拉然早接、冰冠完成后晚用任务交通”的普通跨地图承接，不存在source conflict；Icecrown正式v1迁移已重新验收；13230已移除错误`parent_active=13228`，仅保留13228已完成前置；13276作为13264后的日常重复版不进入一次性主路线。日常任务新规则：不得按daily标签一刀切，首次执行若解锁后续/承担前置/已被路线选为首次必做则保留，只排除后续纯重复执行。
