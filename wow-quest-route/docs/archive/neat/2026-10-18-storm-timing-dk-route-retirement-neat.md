# 2026-10-18 风暴实跑 / Timing闭合 / 普通外域路线退役 NEAT

## 本阶段范围

本阶段从第二组兽人双手鲜血DK五开继续实跑出发，最终收口四类工作：

1. 风暴峭壁第二段实跑、fivebox事实、独立日常删留与当前恢复点；
2. Route Atlas Timing专项修复，从“旧step预算兜底”迁到可审计的组件化任务/移动/Hub/特殊动作模型；
3. 第二组实际使用的地狱火DK、赞加DK路线完成Timing显式化；
4. 普通职业地狱火/赞加退出当前工作台，但作为可恢复Route Profile资产完整保留。

本阶段没有为这些常规数据/模型修复创建worktree。与本轮无关的DK战斗配置、坐骑宏和其单独NEAT不纳入本阶段归档/提交范围。

## 第二组当前实跑状态

- 当前执行组：兽人双手鲜血DK×5。
- 最新实跑：2026-10-16 23:02 → 2026-10-17 04:06。
- 明确暂停：01:30 → 01:53，共23分钟。
- 本段墙钟304分钟；扣暂停后的实际推进281分钟。
- 与此前达拉然→风暴155分钟续接后，第二组从达拉然路线起点到当前停点累计有效推进约436分钟。
- 当前等级79级，五号经验约33.4万–39.8万；差异来自13420《永冻之冰》的机会型触发/完成情况。
- 04:06停止在风暴当前step13内部；用户没有给出瞬间的精确action，所以CURRENT只保存“处于《清算之战》这一段”，不伪造更细恢复点。
- 已确认固定顺序：接共享《清算之战》 → 炉石回格罗玛什坠毁点 → 再去布德克拉格庇护所。

## 当前到“练完第二组”的剩余时间预测

本项目此前已经固定“练完第二组”的比较口径：**55级DK起步 → 到80后继续清正式任务地图 → 嚎风峡湾除外全部清完**。因此80级只是中间里程碑，不是本次剩余时间预测的终点。

从04:06当前风暴step13内部停点开始，按现役路线和现有clean baseline重新拼接：

- 风暴剩余：约181分钟，约3小时01分。step13精确停点未知时，按“step13起点→全图结束”与“step13结束→全图结束”两个极端取中间值；
- 冰冠现行删日常版：约204分钟，约3小时24分。旧中心289分钟，扣除本轮12个独立日常中已知的约77.6分钟objective service，并给13677《学习驾驭》保守留约7分钟；额外移动/Hub节省未全部反算，因此这个值略偏保守；
- 索拉查：约266.5分钟，约4小时27分；
- 祖达克：约498.2分钟，约8小时18分；
- 灰熊：约375.6分钟，约6小时16分。

合计中心约**1526分钟 = 25小时26分**，规划时取整按**25.5–26小时**；考虑后续地图仍有部分Timing未完全组件化，以及祖达克/索拉查存在个人任务长尾，保守可预留到约30小时。这个中心量级也与2026-10-13“龙骨步骤38中途→除嚎风外全清约35小时21分”的旧规划在扣除后续实际推进后保持一致，没有出现模型量级突变。

79→80本身仍可作为中间检查点：按当前五号约33.4万–39.8万经验，预计约2小时45分后在风暴step19末段～step20前半陆续80；达到80后继续执行冰冠→索拉查→祖达克→灰熊，不停止本组清图。

## 风暴fivebox与任务选择收口

本轮自然实跑新增确认：

- 共享：12953《燃烧吧，瓦基里安》、12886《驭龙赛》、12915《弥补关系》、13034《见证者与英雄》、13037《雷蹄的记忆》；
- 不共享/个人执行：12900《制造挽具》、12983《最后的母熊》、13064《骨肉相残》、12882《远古的圣物》、13000《紧急措施》、13055《洞穴中的药品》、13010《科洛米尔，风暴之锤》；
- 12895《失踪的布莱恩·铜须》确认依次拾取；
- 《失踪的猎人》不显示fivebox标签。

风暴fivebox pending由16降为4；当前Timing真正仍依赖pending机制的objective是12917、12984、13007。

练级路线同时按当前“升级不额外做独立日常”的策略清理：

- 风暴删除4个无后续关键依赖的独立日常：12981《热与冷》、12994《猎杀间谍》、13006《粘滞清洁》、13046《喂饱安格里姆》；
- 冰冠同步删除12个同类独立日常；
- 12689《神谕者之手》虽然是日常，但因解锁后续一次性任务而保留。

repeatability=daily本身仍不是删除条件；是否承担一次性链前置/关键解锁仍按Selection owner判断。

## Timing专项：结构修复

### 旧基线只保留迁移/历史身份

`component-wall-clock-v2`继续使用`legacy_step_baselines`保存迁移历史，但规则已经收紧：

- 拆step/合step、任务集合变化、关键动作重排、fivebox机制纠正会使旧step合同失效；
- 新拆step没有自己的旧baseline时不能借其它root step伪装成完整；
- `fivebox.status=pending`永远不能由legacy residual消解；
- 一个Profile完成Movement、Hub、objective service和特殊动作显式迁移后，必须关闭`compatible_step_residual_floor`，旧中心值此后只做历史比较。

### Questie Timing输入修复

- Questie/pserver掉率统一从百分数归一化到0–1；39%进入Timing即0.39，而不是39。
- 多个候选NPC若当前版本化掉率完全相同，可解析为同一`drop_rate`并保留候选NPC列表；掉率不同仍保留Requirement。
- 固定物/世界物品收集补充`interaction_count`输入。

### 规则族收口

新增/明确：

- `personal-kill-count`：个人击杀进度按`kill_count × party_size × combat_seconds_per_mob`；
- `fixed-object-interaction`：倍率直接读取Task Card `fivebox.status`，共享计一次，不共享/依次交互按队伍人数；
- `sequential-corpse-loot`：同一目标只杀一次、同一尸体由五号依次拾取时，按`N × combat + N × party_size × personal_loot`，不再为每个Boss任务重复手填60秒。

`sequential-corpse-loot`已替代多张卡的重复固定秒数写法，包括9466、10230、10834、9898、10117、9820等同型任务。

机会型`accept + when.has_item`任务在Replay为maybe时不再阻断主路线Timing baseline；只有这类天然机会任务的可选Hub成本被排除，其它条件Hub动作仍保持Requirement。

## 地狱火DK Timing闭合

当前`hellfire-dk-speed`：

- 33/33个objective task都有显式Timing规则；
- Movement、Hub、objective service、特殊传送/飞行参数均已显式化；
- 开场奥格瑞玛→诅咒之地传送、黑暗之门跨越、命运阶梯→萨尔玛任务飞行均进入profile action Timing参数；
- `compatible_step_residual_floor=false`；
- Timing状态`pass`；
- `resolved_by=legacy_step_baseline`数量0；
- `legacy_step_baseline_residual`步骤数量0；
- 当前组件化中心约169.2分钟，区间约127.2–211.1分钟。

旧330分钟首跑前预算只保留历史比较，不再参与当前中心或区间。

## 赞加DK Timing闭合

当前`zangarmarsh-dk-speed`：

- 27/27个objective task都有显式Timing规则；
- 游泳自主移动速度参数补入当前Timing模型；
- 9903/9904原先无业务意义的条件交付被恢复为确定性turn-in，避免Replay把正式固定路线误判为maybe；
- Movement、Hub、objective service、特殊动作全部显式化；
- `compatible_step_residual_floor=false`；
- Timing状态`pass`；
- `resolved_by=legacy_step_baseline`数量0；
- `legacy_step_baseline_residual`步骤数量0；
- 当前组件化中心约97.6分钟，区间约74.9–120.2分钟。

旧174分钟预算只保留历史比较。

这两个绝对总时长目前都属于**完全组件化后的provisional估值**。现有外域实跑包含首跑学习、死亡、旧Profile、折返等污染，不为了贴旧330/174分钟预算而重新注入整step residual；下一轮自然clean复跑只校准能被证据定位的具体组件。

## 普通地狱火/赞加退役策略

用户后续打金练号固定使用DK，因此普通职业完整版不再需要占当前工作台入口，但不能丢失多年积累的路线资产。

处理方式：

- `hellfire-fivebox`：`status=retired`；
- `zangarmarsh-fivebox`：`status=retired`；
- `horde-fivebox-full-clear`普通职业Program：`status=retired`。

`retired`的长期语义已经写入Route Lifecycle owner：

- 退出当前正式工作台/现役Program；
- Profile、Task Card、geometry、历史generated、Observation都保留；
- 正式`data/routes`只渲染非retired Profile；
- 未来需要非DK练级时，恢复Profile status/Program并正常重建发布即可，不从头重做路线。

`frozen_reusable`仍属于现役可发布集合，不用它表达“隐藏但保留”。

正式工作台已按13个非retired Profile全量重渲染：

- `profile_count=13`；
- `publishable=true`；
- 普通地狱火/赞加不再出现在workbench；
- 旧`player-view/hellfire.md`、`player-view/zang.md`随正式输出同步清理；
- Player Assets writer新增清理不在本轮正式publish key集合中的陈旧`.md`玩家页，避免retired页面残留。

仓库仍保留15个Route Profile文件；“15个资产 / 13个现役发布”是当前正式口径。

## Fivebox pending清单收敛

普通地狱火/赞加退役后，只被退役Profile引用的pending不再属于当前自然实跑待办。归档前全量一致性测试又发现第二组DK速度路线有6张Task Card没有和清单对齐：9400《刺客》与10286《埃雷利恩的秘密》属于纯接交/对话链，纠正为`not_applicable`；9373《遗失的信件》、10134《火红水晶中的线索》、10393《邪恶的计划》、9911《沼泽中的伯爵》虽已跑过，但历史只确认任务起始物来源/掉落，没有明确记录五号取得方式，因此继续保留pending。

最终机器审计口径：

- 全部15个Profile资产合并后共有163个唯一pending task_id；
- 当前非retired现役路线引用其中144个；
- 19个pending只被retired Profile引用，不进入当前自然实跑清单；另有2个pending同时被retired与active Profile引用，因active仍需要而继续保留；
- 退役Profile/Task Card资产均未删除，未来重新启用普通职业路线时按当时Task Card最新状态重新生成待测范围，不恢复一份冻结旧清单。

`tasks/fivebox-pending.md`和`tasks/todo.md`已经同步到144项现役口径。

## 验证

最终相关验证：

- 地狱火DK Timing：`pass`，0 legacy-resolved，0 legacy residual；
- 赞加DK Timing：`pass`，0 legacy-resolved，0 legacy residual；
- 两张DK图Display重建：`pass`；
- 两张DK图Publisher重建：`publishable=true`；
- 正式13 Profile Player Assets全量渲染：`pass / publishable=true`；
- Timing / Questie Timing Source / drop rate / Task Card/Profile schema / Replay / Movement / Display / Publisher / Player Assets / Program contract / rule routing专项回归：**157/157通过**；NEAT一致性收口后项目**全量回归329/329通过**。

测试期间两次早期命令级失败均不是业务回归：第一次引用了不存在的`tests/test_route_programs.py`；第二次直接调用`.venv/bin/pytest`导致`from scripts...`的模块搜索路径不完整。之后全量测试真实发现fivebox checklist与retired/机会型起始物Task Card范围不一致，本轮按事实修正生命周期过滤、2个`not_applicable`状态与4个现役pending后，再以仓库根目录`.venv/bin/python -m pytest -q`执行，最终329项全部通过。

## 当前权威入口

- 当前实跑恢复点与剩余80级预测：`docs/verified-routes/CURRENT.md`；
- 当前未完成事项：`tasks/todo.md`；
- 现役fivebox待测：`tasks/fivebox-pending.md`；
- Timing永久规则：`docs/rules/timing-and-benchmarking.md`；
- Route Profile/Program生命周期：`docs/rules/route-profile-and-lifecycle.md`；
- Fivebox事实规则：`docs/rules/execution-and-mechanics.md`；
- 当前正式页面：`data/routes/route-atlas-workbench.html`。

本NEAT只保存本阶段形成过程、验证和历史结论；继续实跑时仍以`CURRENT.md`为唯一恢复点，后续Timing精度校准只随自然clean实跑增量进行。
