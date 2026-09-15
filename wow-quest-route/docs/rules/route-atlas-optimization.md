# Route Atlas 路线优化算法

用途：这是项目中**“已知要做哪些任务后，如何把Task Card事实编排成合法、低墙钟、可局部重算的Route Profile”**的唯一路线算法owner。

本次治理只重新划清职责，不改变当前已验证的核心算法：`Target Cluster / Spatial Instance / Background Layer → 插入时闭合 → 局部重放 → 最终薄审查`仍是现役方法。

本文件不决定任务值不值得做，不保存任务事实，不实现XP/Timing公式，也不定义玩家备注/颜色。

## 1. 输入与输出

### 输入

路线优化至少消费：

- Route Profile的scope、entry state、goal和当前任务集合；
- Task Card的稳定任务ID、Availability、objectives、locations、typed relations、机制/地形事实；
- CURRENT仅在“继续当前实跑”时作为当前角色runtime overlay；
- RouteState：已开飞行点、炉石、任务日志、声望/阵营、关键携带物、当前等级等；
- Timing Model提供的候选边际墙钟；
- XP Model提供的等级/衰减约束；
- Task Selection已经做出的任务集合决策/保护约束。

### 输出

只输出路线计划：

- 任务动作`接 / 做 / 交`；
- 动作顺序；
- Target Cluster / Spatial Instance / Background Layer结构；
- 交通/炉石选择；
- RouteState转移；
- 玩家逻辑stepGroups所需的路线边界；
- 插入/重排诊断；
- 可重建的几何/时序派生结果。

不输出新的Task Card事实，也不自行生成“这个任务共享/不共享”等机制结论。

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

数据库缺少前置记录不能自动证明任务为独立根；遇到会改变路线的大依赖UNKNOWN，返回事实层核验。

## 4. Target Cluster

完全相同真实服务目标优先形成Target Cluster。

聚类依据来自Task Card结构化关系和目标事实，例如：

- same target entity/object；
- same required item/source；
- same cave/event；
- shared objective service；
- 真实空间重叠。

不能只凭Questie点位接近、任务名相似或旧页面曾经放在一起就归为同簇。

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

新地图路线先建立入口合同，再排内部任务。

至少明确：

- 上一Profile/上一地图真实结束状态；
- 离开动作；
- 下一地图真实落点/入口Spatial Instance；
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

1. 从CURRENT读当前profile/version与现场状态；
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

是否在某个阶段必须做视频反向审查属于Route Lifecycle SOP/当前项目阶段策略；本算法只定义视频能作为哪类输入。

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

玩家文案/HTML冷读不属于本算法，Route Lifecycle SOP调用Route Display/Task Presentation对应门禁。

## 23. 本文件明确不负责

- Task Card字段/事实：`docs/task-library/README.md`；
- 任务机制核验：`execution-and-mechanics.md`；
- 任务删留：`leveling-and-selection.md`；
- XP：`xp-model.md`；
- 时间公式：`timing-and-benchmarking.md`；
- Route Profile身份/生命周期：`route-profile-and-lifecycle.md`；
- Route Atlas路线显示：`route-atlas-route-display.md`；
- 任务备注/标签：`route-atlas-task-presentation.md`；
- 页面/地图工程：`route-atlas-ui-and-assets.md`；
- 何时调用算法/测试/人工终审：Route Lifecycle SOP。
