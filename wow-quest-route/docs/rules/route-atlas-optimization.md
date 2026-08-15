# Route Atlas 数据、状态与路线优化规则

用途：修改 `workbench-routes.json`、做当前路线裁剪、任务簇插入、路线状态机、炉石重算、精确优化器或全图几何审计时读取。HTML视觉和地图资源见 `route-atlas-ui-and-assets.md`。

## 1. 数据分层

长期分层固定为：

`Questie Raw（不可改写） → Questie Effective/派生事实 → 单任务知识节点 + typed relations + numeric features → 路线版本/路线节点 → HTML执行工作台`

- Questie Raw保存插件原始事实，实跑观察不得覆盖。
- 单任务知识节点保存与某条具体路线无关的可复用知识。
- 路线节点保存这版路线的合并、位置、边际移动/服务成本等版本特定信息。
- HTML是执行前端，不是事实数据库。

任务知识可关联：typed facts/relations、numeric features、稳定标签、Target Cluster、Spatial Instance、五开机制、地形、特殊操作、掉落/等待风险、可交易/可购买三态、source/confidence和实跑纠错。

稳定标签家族至少包括 `scope:*`、`objective:*`、`chain:*`、`trip:*`、`terrain:*`、`route:*`；机器关系至少支持 `precedes`、`same_accept_npc`、`same_turnin_npc`、`same_direct/resolved_creature`、`same_direct/resolved_object`、`same_required_item`、`spatial_overlap`、`same_chain`、`same_excursion_block`。标签用于解释，不能替代底层事实和成本计算。

掉落物必须保存真实五开拾取机制；同一次掉落事件如果同尸体五号都能分别拿任务物，期望击杀次数不能机械乘五。

## 2. 从零主路线和当前执行路线

Route Atlas永久区分：

- 从零复用主路线：下一批完整地图路线。
- 当前执行路线：按当前角色状态裁剪。

当前任务完成只裁当前执行动作；任务知识、从零路线和历史不删除。裁剪后必须重算受影响窗口的前置、Hub、条件分支、炉石和路线几何。

## 3. Target Cluster / Spatial Instance / Background Layer

- 完全相同真实目标实体优先形成Target Cluster。
- Questie刷新点/平均坐标不等于一次真实可服务区域。
- 道路、桥、洞穴、楼层和实跑可达性决定Spatial Instance。
- 广域累计、沿途杀怪、背景拾取和低掉率自然触发可进入Background Layer。
- Background Layer不能反过来拖着主体路线绕路；预计自然覆盖不足时必须转成显式服务段。

## 4. 路线构建固定采用“候选 → 硬门禁 → 成本比较”

基础流程：

1. 建Questie/人工事实层；
2. 形成Target Cluster；
3. 建Prerequisite / Availability Network；
4. 人工解析Spatial Instance；
5. 分离Background Layer；
6. 用当前真实玩家状态建立RouteState；
7. 对待插入任务/任务簇只枚举受影响窗口内候选位置；
8. 每个候选逐项通过Hard Validator；任一失败即淘汰；
9. 只有全部通过的候选才比较成本；
10. 插入后重放受影响窗口状态；
11. 已验收前缀默认冻结，只有状态连续性被破坏时向后扩大窗口；
12. 不同Target Cluster默认没有顺序，只有前置/Availability/真实成本证据才排序。

## 5. Hard Validator

候选至少独立检查：

1. `player_state`：当前等级/经验/位置/任务状态和动作一致。
2. `quest_prerequisite`：preQuestGroup / preQuestSingle / parent / chain满足。
3. `availability`：等级、声望、职业、种族、技能/法术等满足。
4. `objective_ready`：C前任务已接且目标未完成；T前目标已完成。
5. `xp_deadline`：计划交付时不越完整经验截止。
6. `transport`：炉石绑定/冷却、飞行点、交通动作真实可用。
7. `branch_state`：条件/声望/机会任务裁成真实分支。
8. `fivebox_mechanic`：服务时间与真实共享/个人机制一致。
9. `spatial_service`：至少能定位正确宏观Spatial Instance；局部几何未知可标 `MANUAL_SPATIAL_REVIEW`，不能伪造局部最优。
10. `background_capacity`：主体路线预计覆盖量足够才可背景化。
11. `no_dead_step`：不能生成已完成、条件必假或已被前面覆盖的空步骤。
12. `trigger_source_documented`：怪物掉落物触发任务必须完整说明来源怪、刷点、触发物、任务和特殊出现/等待策略。
13. `state_continuity`：插入后向后重放冻结后缀；后续动作一旦失效就扩大受影响窗口，而不是强接旧状态。

返回值：`PASS / FAIL(reason) / UNKNOWN(reason)`。

UNKNOWN不能统一放行：

- 可查资料的事实先查并重新判定；
- 只能由五开客户端证明的机制向用户确认；
- 宏观区域已知、局部刷法未知转 `MANUAL_SPATIAL_REVIEW`；
- 会影响路线合法性/宏观排序且无法消解的UNKNOWN不能发布为已验证路线。

FAIL只否决“任务Q放在位置P”，不永久删除任务Q。

## 6. 可行候选之间的成本顺序

只有全部Hard Validator通过后比较：

`added_wall_clock → extra_travel → service_time → forced_wait → backtrack → xp_deadline_slack → future_route_regret → hearth_opportunity → stable_id`

禁止用加权总分把硬约束失败抵消掉。

`future_route_regret`必须考虑当前地图终点到下一地图入口/首个任务中心/跨图breadcrumb的真实成本。当前已READY的交付任务应向后寻找自然Hub的零/最小增量交付点，不因为历史版本写在“最终收尾”就固定拖到最后。

## 7. 插入验收轨迹

每个最终采用的插入至少保留：

- 枚举过的候选位置；
- 被淘汰候选失败在哪个Validator；
- PASS候选主要成本；
- 最终选择理由；
- 受影响窗口是否扩大。

这样实跑出错时能判断是事实层、Validator、实现还是成本排序问题，而不是重新依赖模型回忆。

## 8. 声望不足任务库

因 `requiredMinRep` 暂时不可接的任务不删除，按 `(faction_id, required_value, stable_id)` 进入待解锁库。

RouteState声望变化时：

1. 记录 `rep_before → rep_after`；
2. 先检查是否将越过 `requiredMaxRep`；
3. 应用声望变化；
4. 只激活当前最低刚达到门槛的任务；
5. 同门槛也一个一个重新插入并重放状态；
6. 当前门槛处理完再看更高门槛；
7. 新插入若继续改声望立即递归触发。

Repeatable真值读取Questie compact quest DB字段24 `specialFlags` 的bit 1，并在RouteState中维护 `turnin_count`，避免把重复任务误记成一次性completed。练级目标下第一轮后默认不生成第二轮候选；无经验重复后续默认不接，除非用户切换声望/物品目标或它是有经验任务硬前置。

## 9. 当前路线裁剪恢复流程

根据最新历程裁路线：

1. 标记 completed / active / unseen / conditional；
2. 移除completed执行动作；
3. 检查active是否仍需C/T、unseen后续能否正常解锁；
4. 局部重新排序，不机械连接旧顺序；
5. 检查关键接取是否曾被已完成任务遮住；
6. 重算起点、Hub、炉石、条件分支；
7. 整张恢复完成后再做动态图全局审查；
8. 当前裁剪不覆盖从零主路线。

## 10. 炉石和交通是可重算资源

- 炉石不是固定“一图一次”，可以0次/1次/多次；不为等冷却停工。
- 计入真实施法/交互时间，不能当0秒瞬移。
- 比较的是完整未来墙钟，不只是“现在回Hub快不快”。若自然骑回能顺路完成后续生产性动作，要与“现在炉石 + 以后再出门”比较。
- 水域、游泳、绕岸、不可骑乘地形不能按陆地坐骑直线速度折算；用户实跑耗时优先覆盖平面模型。
- 旧版本炉石点没有锁定权。新增任务影响炉石附近时，只打开受影响簇+炉石+局部后缀重新比较。
- 新地图默认沿主体路线自然经过时开飞行点/绑定炉石；只有专门预跑的额外成本能被后续明确节省覆盖时才提前初始化。

总成本结构：

`T_total = T_travel + T_objective_service + T_accept_turnin + T_forced_wait + T_other_known_cost`

移动速度加成只作用于真实纯移动段，不能乘到战斗、拾取、交互、护送、脚本飞行、炉石和等待。

## 11. 满经验截止是硬审计

每个一次性任务物化 `last_full_xp_level = quest_level + 5`。

每个T(Q)至少计算/保存：预计交付前等级经验、该等级奖励、交付后等级经验和last_full_xp_level。

- 最低号下界账证明经验够；
- 最高/最快号上界账证明不会把低级任务交进衰减。

任一计划交付出现 `predicted_level_before_turnin > last_full_xp_level`，路线必须调整。先打开最小局部窗口，优先同图Hub交付，不先全图洗牌。

## 12. 精确优化器定位

PC-SP、DP/labeling、MILP、Branch-and-Cut、CP-SAT、flexible service location、shared-service/covering等模型只用于：

- 理论母模型；
- 局部插入成本估计；
- 顺序枚举；
- 异常检测；
- 与人工路线对照。

模型不能直接替代玩家路线。只有边界、地形、服务位置和状态约束足够准确且求解器证明optimal，才可称“理论全局最优”。

## 13. 动态整图审查时机

- 先完成整图任务插入或当前状态恢复；
- 再播放全图动态路线；
- 检查大范围反向折返、异常跨图、炉石落点、阶段切换和终点方向；
- 异常只回到对应局部修正。

不得每插一个任务就做一次全图动态图审查。
