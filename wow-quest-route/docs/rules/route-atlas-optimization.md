# Route Atlas 路线优化算法

用途：这是项目中**“已知要做哪些任务后，如何把Task Card事实编排成合法、低墙钟、可局部重算的Route Profile”**的唯一路线算法owner。

本次治理只重新划清职责，不改变当前已验证的核心算法：`Target Cluster / Spatial Instance / Background Layer → 插入时闭合 → 局部重放 → 最终薄审查`仍是现役方法。

本文件不决定任务值不值得做，不保存任务事实，不实现XP/Timing公式，也不定义玩家备注/颜色。

## 1. 输入与输出

### 输入

路线优化至少消费：

- Route Profile的scope、entry state、goal和当前任务集合；
- 当前Profile属于多Profile完整方案时，同时读取Route Program的严格Profile顺序、Program goal/entry以及前后相邻Profile引用；不得从`display.order`或旧workbench顺序猜上下游；
- Task Card的稳定任务ID、Availability、奖励和`timing_rule_ref`；完整攻略事实用于人工核验，不由优化器解析自由文本；
- 当前Route Profile已有的结构化地点/动作，以及新建Profile时从Questie等证据源临时提取的规划输入；临时规划输入不能成为第二任务真源；
- CURRENT仅在“继续当前实跑”时作为当前角色runtime overlay；
- RouteState：已开飞行点、炉石、任务日志、声望/阵营、关键携带物、当前等级等；
- Timing Model提供的候选边际墙钟；
- XP Model提供的等级/衰减约束；
- Task Selection已经做出的任务集合决策/保护约束。

### 输出

输出分两种身份，不能混成第二路线真源。

**正式路线决策候选**只包含Route Profile真正需要长期保存的最小原子：

- 任务动作`接 / 做 / 交`；
- 动作顺序；同一step、同一`location_ref`的一轮无条件NPC接/交中，在任务依赖与真实交互顺序都允许时，应把同一NPC的动作排成连续run；底层action仍逐条独立保存，Display只压缩连续run，不得自行跨其它NPC重排；
- canonical真实地点/空间与movement/交通/炉石决策；
- 玩家逻辑stepGroups所需的路线边界；
- 只有无法从这些原子可靠重建、且确实改变执行/Timing/后续优化时，才保存最小通用route-only service语义。

**算法派生/诊断**包括：

- Target Cluster；
- 可由真实地点/服务事实机械形成的Spatial Instance；
- 可由路线覆盖机械形成的Background Layer/service coverage；
- RouteState转移与受影响窗口；
- 插入/重排候选、Hard Validator结果和成本诊断；
- 可重建的几何/时序分析结果。

这些派生/诊断可以重算，不因“优化器内部需要”就全部持久化进Route Profile。只有前述无法稳定重建的route-only决策才提升为Profile最小原子。路线设计/重排完成后必须做一次局部交互连续性检查：机械列出“同一地点、同一轮无条件NPC接/交中，同一NPC被其它NPC动作隔开”的候选；它是review signal而非自动重排或发布硬门禁，只有依赖/现场顺序证明安全后才修改Profile。人工/AI冷读可以补充发现，但不能替代机械检查。正式检查入口见本文§23。

不输出新的Task Card事实，也不自行生成“这个任务共享/不共享”等机制结论。

### 1.1 Stage 5 Canonical Spatial / Movement 最小合同

该合同来自现有正式路线的真实结构，而不是一般图模型：当前Route Profile都是严格线性执行链，同一物理Hub可能因前置/阶段变化被多次返回，因此**physical place 与 visit occurrence 不得混为一层**。`location` action表示一次真实visit occurrence；重复回到同一营地必须允许多个visit，即使显示名/坐标相同。

- 每个visit通过`location_ref`读取自己的执行/空间上下文；Profile提供结构化`primary_zone_id`，跨图visit才单独覆盖`zone_id`。不得从Profile标题、subtitle、图片文件名或中文地点名猜zone；
- `geometry.locations[*].location_role`默认是`map_anchor`：这是玩家需要在当前地图上导航/定位的真实点，必须有可证实坐标；坐标暂时拿不到就保持UNKNOWN，不得补假点。对于NPC/任务传送、相位/镜像/灵魂视角、载具脚本等**只用于保持执行顺序与交通状态、玩家不需要依靠本地图坐标导航**的中间状态，可显式使用`transition_context`；它的`x/y`必须为null，且“没有地图点”本身不是requirement。若玩家必须在该上下文内自主走/飞/游或坐标会改变执行决策，就不能用`transition_context`逃避空间建模，必须回到`map_anchor`或保持UNKNOWN；
- 相邻两个visit之间只允许一条canonical incoming edge。`cross_zone`由两端zone_id是否不同机械得到，**不是交通方式**；
- 普通自主移动的edge只保存真正需要的`ride / fly / swim`移动方式；
- `taxi / use_hearth / fixed_transport / quest_transport / move`等显式动作是玩家必须执行的操作。若某条edge由一个显式移动动作产生，canonical edge只引用该`action_id`，交通kind从action机械得到，不能在edge再抄一份；
- 一个visit区间出现多个会改变位置的显式动作，说明旧point压缩了中间真实visit，必须报告`compound_movement_requires_visit_split`并保留review，不能把多段移动合成一条edge；
- Profile最后一个visit之后仍有移动动作时属于Profile出口移动。Route Program上下文把**唯一一条**出口移动绑定到下一Profile首visit；若有多条则说明中间真实落点被压缩，必须拆visit；
- 若跨Profile边界没有离图动作，只允许两端首尾visit显式使用相同`handoff_ref`证明“这是同一个自然交接点”（例如同一地图边界落点）；Program顺序本身、地点名相似或坐标看起来接近都不能代替这一证明。没有离图动作也没有共同handoff时保持`program_boundary_transition_unproven`；
- 这对应项目既有跨图经验中的四段合同：上一图真实终点/交通状态 → 离图动作或显式自然handoff → 下一图真实落点 → Stage 4核入口任务/第一Hub状态。Stage 5只拥有前三段空间/移动，不复制Stage 4任务状态；
- 旧`geometry.locations[*].transport`的历史语义是“前一点→本点”的前端线型/入边提示。Stage 5迁移期只能把它当**migration evidence**：`ride/fly/swim`在没有显式移动动作时可以形成机械迁移候选；`taxi/hearth/script/crossmap`不得单凭线型自动造玩家动作。新canonical edge闭合后该字段只能由Stage 5/Display projection生成，任何下游不得直接读取它决定业务移动。

Stage 5输出按visit/edge携带来源、fingerprint、UNKNOWN/冲突诊断；Stage 6只消费这份fresh输出形成Service Context，Stage 7只消费它计算movement Timing。旧point index永远不是稳定edge身份。

### 1.2 Stage 6 Service Context 最小合同

Stage 6回答“当前Route Profile中的任务服务发生在哪里、哪些服务真正共享、哪些任务只是被主体路线背景覆盖”，不重新决定任务集合或路线顺序。现役唯一解释器是`lib/route_service_context.py`；正式执行范围与入口见本文§23。完整诊断工具不是日常写入口。

- 每个结构化`objective` action天然是一条foreground service event；它绑定Stage 5当前真实visit occurrence。`objective`只表示“这里发生任务服务”，不表示任务在此已经完成；任务完成/交付状态仍由Stage 3 Replay的turnin语义拥有。
- 默认每条objective service独立形成一个Target Cluster。多个objective恰好在同一visit，只能证明共处，**不能自动证明同目标/零边际成本**；真正的共享服务必须由Profile最小`service_overrides.kind=shared_service`显式保存，且当前合同只允许同一visit内的objective actions组成一组。跨visit共享/持续累计应使用background window，不把多个地点伪装成同一个Target Cluster。
- Spatial Instance默认只派生到canonical visit occurrence这一保守粒度：同一visit内的Target Clusters共享一个visit-level instance；不得用Questie平均坐标、旧`phase`字符串、地图距离或旧target-cluster文件自动声称洞穴/楼层/相位可互通。以后若新优化确实需要更强拓扑，必须先有独立可验证空间owner/原子，而不是在Stage 6偷偷猜。
- `service_overrides.kind=background_window`只保存**无法从objective actions稳定重建、但会改变Timing/Optimization的route-only决策**：`task_id + start_action_id + end_action_id + end_policy`。窗口只引用稳定action身份，不引用旧step号/point index。
- `end_policy=carry_if_incomplete`：窗口结束仍未完成时不建立专门补刷段，任务继续携带；例如《赞加沼泽的植物》在后续路线自然累计，不够就继续保留。
- `end_policy=fill_if_incomplete`：先吃主体路线自然覆盖，到窗口收口点仍不足才补缺口；例如《热情的欢迎》《成熟的孢子》《远古的圣物》《等肉下锅》《敌人的耳环》。Stage 6只保存这个服务策略，不在此估算剩余数量/分钟，具体边际时间交Stage 7 Timing。
- `end_policy=covered_complete`：本任务不建立独立服务时间，预期由窗口内其它主体服务完全覆盖；例如《猎人的挑战》随其它狩猎任务自然累计。若实跑证明覆盖不足，进入Observation/Review，不自动新增隐藏刷怪段。
- `shared_service`与`background_window`都不是Task Card任务固有事实。Task Card guide可以保留完整攻略知识，但Stage 6运行时**禁止解析guide、presentation.note_override、旧semantic文案、旧`*-target-clusters.json`或HTML**来猜Service Context；这些旧资料只可作为迁移/人工review证据。
- 旧foundation/target-cluster数据继续保留为历史优化证据，不能被新Route Lifecycle消费为Stage 6真源。当前Stage 6输出中的Target Cluster、Spatial Instance、Background Layer均可删除重建；Profile只保存上述确实无法机械重建的最小service override。

Stage 6输出必须带Stage 5 fingerprint + Profile service override输入fingerprint。Stage 5 blocked/requirements会原样阻止Stage 6宣称publishable exact context；但这不允许Stage 6恢复旧geometry/备注推断捷径。

## 2. Task Card / Route Profile边界

Task Card保存任务本身事实；Route Profile保存当前路线选择和顺序。

路线优化不得把以下内容重新硬编码进Profile：

- Fivebox机制；
- Boss攻略；
- 掉率/任务物用法；
- 洞穴楼层等任务固有事实。

如果优化过程中发现Task Card事实缺失/冲突：

1. 暂停该候选的最终判定；
2. 回到Task Mechanics/Task Card核验；
3. 更新事实后重新计算受影响窗口。

不能把“为这次路线临时猜一个值”藏进Builder或Profile。

## 3. Candidate Pool与Availability

路线算法只对当前Profile实际允许选择/已经由Selection决定纳入的任务工作。

可达性至少消费：

- `pre_any`；
- `pre_all`；
- `parent_active`；
- 互斥关系；
- 等级；
- 声望；
- 职业/种族/专业/技能/法术门槛；
- 已确认隐藏Availability；
- 当前RouteState中completed/active状态。

完整依赖闭包由算法计算，不在Task Card逐张复制。

Route Replay/Availability统一使用三态结果，不把“当前还不能证明”伪装成pass：

- `pass/fail`：当前结构化RouteState与Character Profile已经能机械证明；
- `required_external_state`：例如本Profile开始前必须已经完成某前置、保持某任务active、已开某飞行点，由Cross-Profile Continuity/CURRENT继续验证；
- `deferred_gate`：当前stage没有合法输入可以证明，例如Profile内未来升级才能跨过的`min_level`交Stage 8 XP逐节点消解；首跑累计声望不足以机器确定时按§17保留待校准门槛；专业/技能/隐藏硬门槛没有对应机器状态时同样显式deferred。

Stage 3“fresh”只表示Replay/Evaluator完整地输出了当前pass/fail/外部要求/deferred门槛，**不表示所有deferred都已经通过**。未在Stage 4/8或后续合法输入中消解、且足以改变可接性的门槛必须继续进入Review Trigger的`blocked_unknown`，Publisher不得把它当合法路线。

数据库缺少前置记录不能自动证明任务为独立根；遇到会改变路线的大依赖UNKNOWN，返回事实层核验。

## 4. Target Cluster

完全相同真实服务目标优先形成Target Cluster。

聚类依据来自当前路线已有的结构化动作/位置，以及新建或重排时针对当前窗口从Questie/实测证据提取的临时规划事实，例如同目标实体、同任务物来源、同洞穴/事件或真实空间重叠。

这些规划事实用于本次求解，不反向写成Task Card的新分类字段。不能只凭Questie点位接近、任务名相似或旧页面曾经放在一起就归为同簇；无法确认时进入人工核验。

Target Cluster是**服务目标聚合**，不是固定路线顺序；前置/Availability/交通变化可以打开局部窗口重新排序。

## 5. Spatial Instance

Questie刷新点/平均坐标不等于一次真实可服务区域。

Spatial Instance由真实可达性决定，至少考虑：

- 道路/桥；
- 洞穴入口与内部层级；
- 山体/悬崖；
- 水下；
- 建筑楼层；
- 刷新密度；
- 五号跟随可达性；
- 用户实跑确认路径。

宏观区域已知而局部刷法仍未知时允许`MANUAL_SPATIAL_REVIEW`；禁止为了动画完整伪造局部最优折线。

## 6. Background Layer

广域累计、沿路击杀/拾取、低掉率自然触发等可以进入Background Layer，但只有在主体路线本身预计能自然覆盖时成立。

规则：

- Background任务不能反过来拖主体路线绕路；
- 覆盖不足时转成显式服务段；
- 与前台任务共享同一服务时，Timing只计真实新增边际成本；
- `顺路`必须由当前Route Profile几何/目标重叠证明，不能作为Task Card固有属性。

## 7. 整图初始簇序列

逐簇插入前，先根据：

- 地图真实入口；
- 预期出口；
- Spatial Instances；
- Hub；
- 道路/地形；
- 当前交通网络；

形成整图初始Target Cluster序列。

这条簇序列就是整图路线初始骨架，不额外维护另一套独立“宏观路线真源”。

初始骨架可以存在暂时较长边；后续新解锁任务若能在两簇之间形成更低成本生产性路径，允许打开受影响窗口插入。

## 8. 后发现任务链必须回插

无论遗漏链在什么时候被发现：

- 候选召回；
- 依赖核验；
- 视频反查；
- 覆盖差集；
- 用户实跑；

都必须回到**第一个真实可接/解锁节点**，按每一环自然Hub、Spatial Instance和当时RouteState插入。

禁止因为“路线已经写到后面”把整条链追加到地图末尾。

只有任务依赖本身确实使它晚出现，或成本比较证明末段就是最优合法位置，才允许在末段。

跨地图唯一前置/后续同样属于依赖闭包，不能以`assigned_zone`不同为由漏掉。

## 9. 地图转场合同

新地图路线先建立入口合同，再排内部任务。多Profile完整方案中的“上一/下一”必须来自Route Program顺序；单Profile冷启动则只使用显式entry，不创造隐含前序。

至少明确：

- Route Program指定的上一Profile/上一地图真实fresh结束状态，或显式冷启动entry；
- 离开动作；
- Route Program指定的下一Profile/下一地图真实落点/入口Spatial Instance（若当前Program存在后续）；
- 入口任务/第一Hub；
- 当时可用交通；
- 必须携带的跨图任务/关键状态。

脚本运输、系统飞行、跨图breadcrumb必须分别证明当时合法。

会改变第一任务簇的入口UNKNOWN不能猜测后发布；先查资料，只有客户端/实服才能证明时进入明确验证。

## 10. 核心构建流程

路线优化固定采用：

`任务事实闭合 → 初始簇序列 → 候选插入 → 插入时闭合 → 局部重放 → 收敛 → 薄审查`

具体步骤：

1. 从Task Card/Route Profile建立当前任务集合和Availability网络；
2. 形成Target Cluster；
3. 解析Spatial Instance；
4. 分离Background Layer；
5. 用Profile entry state/CURRENT overlay初始化RouteState；
6. 对待插入任务/任务簇只枚举受影响窗口内候选位置；
7. 每个候选在插入**当时**完成必要Hard Validator；
8. 合法候选再用Timing成本排序；
9. 执行插入；
10. 从最早改变的RouteState节点向后逐项重放；
11. 状态重新接回旧后缀后停止；
12. 未被传播触及的前缀/后缀冻结；
13. 整图收敛后只检查局部无法保证的全局性质。

不设置“最后统一重新证明所有任务合法”的第二套全量流程。

## 11. Hard Validator

Hard Validator是**候选插入维度**，不是每次发布机械跑一整套的固定清单。

候选按实际相关性检查：

1. `player_state`：当前RouteState与动作一致；
2. `quest_prerequisite`：直接前置/组合前置/父关系满足；
3. `availability`：等级、声望、职业、种族、技能/法术等满足；
4. `objective_ready`：做任务前已接，交任务前已完成；
5. `xp_deadline`：需要时调用XP Model判断；
6. `transport`：交通在**该时点**真实可用，并比较明显更短合法方案；
7. `branch_state`：Profile允许的条件状态真实成立；
8. `fivebox_mechanic`：Timing消费的Task Card机制已知/明确unknown；
9. `spatial_service`：至少能定位正确宏观Spatial Instance；
10. `background_capacity`：主体路线覆盖足够才允许背景化；
11. `no_dead_step`：不能生成已完成、条件必假或已被前面覆盖的动作；
12. `trigger_source_ready`：触发任务所需Task Card事实闭合到足以合法编排；
13. `state_continuity`：插入后状态能重新接回后缀，否则扩大窗口；
14. `map_transition_contract`：地图入口能从上一个真实结束状态推出。

以上反引号Validator标识同时是Stage 10 Review Trigger使用的稳定机器ID；`data/review-trigger/model-config.json`只允许作为本节列表的机器投影/校验表，不拥有第二套Validator语义。

返回：

`PASS / FAIL(reason) / UNKNOWN(reason)`

### UNKNOWN处理

- 可查事实先查；
- 任务机制事实回Task Card/Task Mechanics；
- 宏观空间已知、局部未知可`MANUAL_SPATIAL_REVIEW`；
- 会影响合法性/宏观排序且无法消解的UNKNOWN不能冒充已验证路线。

### FAIL处理

FAIL只否决“任务Q放在位置P”这个候选位置，不等价于永久删除任务Q。是否删任务属于Task Selection。

## 12. 可行候选成本顺序

只有Hard Validator通过后才比较软成本：

`added_wall_clock → extra_travel → service_time → forced_wait → backtrack → xp_deadline_slack → future_route_regret → hearth_opportunity → stable_id`

这些成本调用Timing/XP结果；本文件不复制它们的计算公式。

禁止用加权总分抵消硬约束失败。

`future_route_regret`至少考虑当前候选对：

- 后续Hub；
- 地图真实出口；
- 下一地图入口；
- 未来回访；
- 炉石机会；

的影响。

## 13. 插入验收轨迹

每个最终采用的插入至少能追溯：

- 枚举过哪些候选位置；
- 淘汰候选失败在哪个Validator；
- PASS候选主要成本；
- 最终选择理由；
- 最早改变的RouteState节点；
- 受影响窗口扩到哪里、在哪里重新接回。

这类轨迹是算法诊断，不进入玩家前端。

## 14. RouteState

RouteState至少显式维护：

- 当前任务active/completed状态；
- `opened_flight_points`；
- 炉石绑定点/可用状态；
- 可用脚本/固定交通；
- 声望/阵营；
- 任务日志容量；
- 关键携带任务/任务物状态；
- 当前等级/经验（由XP Model消费）；
- repeatable任务当前轮次（必要scope才启用）。

每个接/做/交/开点/炉石/转场动作都可能产生状态转移；只有会继续向后传播的状态变化才扩大重放窗口。

## 15. 动态飞行网络与交通

飞行点是随Route Profile推进扩张的网络，不是整图静态集合。

原则：

- 系统飞行目的地必须在该动作发生前已开启；
- 新开飞行点后，对尚未执行且跨片区的后缀重新比较交通；
- 比较直飞、最近飞行点+短移动、炉石组合、固定交通、自主移动；
- 不能拿整图最终已开点倒推前半段；
- 旧路线曾经骑马/中转不构成继续沿用理由；
- 没有任务/交付价值的Hub不因历史习惯保留中转。

选择某交通方式的具体墙钟由Timing Model计算。

## 16. 炉石是可重算RouteState资源

- 一图可以0次/1次/多次；
- 不为等冷却停工；
- 不能当0秒瞬移；
- 比较完整后续墙钟，而不是只看当前回Hub；
- 新任务影响炉石附近时只打开相关簇+炉石+局部后缀；
- 绑定/使用决策属于Profile路线，不写进Task Card。

## 17. 声望/动态Availability

因`requiredMinRep`暂时不可接的任务不删除Task Card事实。

当RouteState声望改变：

1. 应用真实声望变化；
2. 检查刚跨过的门槛；
3. 重新评估对应任务Availability；
4. 新可达任务回到其第一个自然位置做局部插入；
5. 插入继续改变声望时递归处理受影响门槛。

具体任务的required rep来自Task Card。

首跑缺少“做到某节点时真实累计声望”时，不把玩家路线写成无限运行时分支；先保留明确待校准状态，实跑后固定到第一个真实可接节点。

## 18. 任务日志容量是RouteState约束

任务日志上限/预留策略由当前版本配置提供；算法在每次批量接取和后续解锁时检查峰值。

若容量不足，Route Optimization只能调整接取时点/路线窗口；“为了日志容量应该永久删哪个任务”必须进入Task Selection。

日志约束不能写进Task Card任务固有事实。

## 19. 当前执行恢复

继续现场实跑时：

`正式Route Profile + CURRENT overlay → 当前剩余执行视图`

恢复算法：

1. 从CURRENT读当前profile/version与现场状态；若本次执行属于Route Program，同时校验program/version及当前Profile在Program中的位置；
2. 将已完成动作视为runtime progress，不从正式Profile永久删除；
3. active任务检查剩余`做/交`；
4. unseen后续按当前Availability；
5. 若现场异常使RouteState偏离Profile，只打开最早差异窗口重排；
6. 状态重新接回正式Profile后继续。

只有用户明确修改正式路线，才把当前修正提升进Profile。

## 20. 视频路线证据

视频不是本项目路线的上位真值，只允许：

1. **共同任务顺序对照**：过滤本Profile明确不做的任务后，比较共同任务相对顺序/邻接；
2. **遗漏召回**：发现视频存在而当前候选池遗漏的任务，回Task Card/Availability核验。

视频不能直接强迫恢复已删除任务或覆盖当前优化结果。

是否需要调用视频反向证据由当前业务/迁移任务决定；本算法只定义视频能作为哪类输入，不建立第二套执行流程。

## 21. 精确优化器定位

PC-SP、DP/labeling、MILP、Branch-and-Cut、CP-SAT、flexible service location、shared-service/covering等只作为：

- 理论母模型；
- 局部插入成本估计；
- 顺序枚举；
- 异常检测；
- 与人工路线对照。

只有边界、地形、服务位置和状态约束足够准确且求解器证明optimal，才能称理论全局最优。

求解器不能绕过Task Card事实、Selection决策或Hard Validator直接修改正式Profile。

## 22. 动态整图薄审查

整图任务插入/局部恢复完成后，才做一次全局薄审查，重点找局部窗口难以发现的：

- 候选覆盖异常；
- 重复Spatial Instance；
- 后续插入造成的新合并机会；
- 大范围反向折返；
- 异常跨图；
- 炉石/交通落点错误；
- 入口/出口不闭合；
- 终点方向异常。

发现问题只打开对应局部窗口修正，不从地图起点全量重验。

玩家文案/HTML冷读不属于本算法；需要发布/冷读时进入Route Display / Task Presentation / UI & Assets，最终切换再进入Final Audit。

## 23. 正式Optimization / Movement / Service操作

- 路线设计/重排后的同NPC连续性候选检查：`python3 scripts/audit_route_interaction_continuity.py <profile_id>`。只报告候选，不自动重排。
- 单Profile canonical Movement：`python3 scripts/build_route_movement.py <profile_id>`。
- Program Movement边界：`python3 scripts/build_program_movement.py <program_id>`；只消费成员当前Movement，不在内部重算成员。
- 单Profile Service Context：`python3 scripts/build_route_service_context.py <profile_id>`。
- Program首次/合同级Service Context：`python3 scripts/build_program_service_context.py <program_id>`。
- 已有合法Program Service基线，仅某成员变化：`python3 scripts/update_program_member_service_context.py <program_id> <profile_id>`。
- Movement / Service遇到UNKNOWN或冲突必须返回requirements/blocked，不得回读旧geometry、备注或target-cluster产物补齐。

## 24. 本文件明确不负责

- Task Card字段/事实：`docs/task-library/README.md`；
- 任务机制核验：`execution-and-mechanics.md`；
- 任务删留：`leveling-and-selection.md`；
- XP：`xp-model.md`；
- 时间公式：`timing-and-benchmarking.md`；
- Route Profile身份/生命周期：`route-profile-and-lifecycle.md`；
- Route Atlas路线显示：`route-atlas-route-display.md`；
- 任务备注/标签：`route-atlas-task-presentation.md`；
- 页面/地图工程：`route-atlas-ui-and-assets.md`；
- 当前输入是否需要Route Optimization由分类SOP及Selection结果决定；测试读`../../tests/README.md`，最终项目切换读Final Audit owner。
