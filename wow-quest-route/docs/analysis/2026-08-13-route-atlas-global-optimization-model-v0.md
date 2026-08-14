# Route Atlas 全局优化数学模型 v0

日期：2026-08-13
状态：首个正式数学模型草案
母模型：Precedence-Constrained Shortest Path (PC-SP)
扩展：Stateful Service Requirements + Flexible Service Locations + Shared-Service Coverage

---

## 1. 优化目标

从当前真实游戏状态出发，到达指定目标状态，使预计总完成时间最小：

`min T_total`

其中：

`T_total = T_move + T_service + T_accept_turnin + T_wait + T_special`

说明：

- `T_move`：骑乘、步行、飞行、必要绕路；
- `T_service`：杀怪、拾取、交互、探索等 Objective 执行；
- `T_accept_turnin`：接取/交付及五开操作时间；
- `T_wait`：刷新、脚本、等待类可建模时间；
- `T_special`：已验证的特殊机制成本。

圈数不是目标函数。若 3 圈 42 分钟、2 圈 50 分钟，则 3 圈是更优解。

---

## 2. 为什么采用“状态空间最短路径”而不是直接排任务顺序

普通任务排序只记录：

`Q1 -> Q2 -> Q3`

但真实路线是否可行、是否最优还依赖：

- 当前人在哪里；
- 哪些任务已经接；
- 哪些 Objective 已经部分完成；
- 哪些 TurnIn 已完成从而解锁后续；
- 当前地点一次行为可以同时推进哪些任务；
- 某 Objective 可在多个点/区域完成。

因此 Route Atlas 的基本状态不是“当前正在做哪个任务”，而是：

`S = (v, I, p)`

其中：

- `v`：当前物理位置/路网节点；
- `I`：已经满足的逻辑事件集合；
- `p`：尚未完成的有限任务进度向量。

从初始状态 `S0` 到目标状态集合 `G` 的最低成本路径，就是理论最优路线。

---

## 3. 集合与符号

### 3.1 任务

`Q`：计划范围内任务集合。

对每个任务 `q in Q`，定义：

- `A_q`：Accept milestone；
- `C_q`：Complete milestone；
- `T_q`：TurnIn milestone；
- `R_q = {r_1, r_2, ...}`：Objective requirements。

### 3.2 逻辑事件集合

`E_logic = {A_q, C_q, T_q | q in Q}`

Objective requirement 不一定直接作为单一布尔事件，因为很多目标需要计数，例如杀 12 只、拿 8 个物品；其进度进入 `p`。

### 3.3 物理位置

`V`：压缩后的物理路网节点集合。

可能包含：

- NPC 固定点；
- Object 固定点；
- Questie spawn 点或点云聚类代表节点；
- 洞穴入口/出口；
- 桥、升降梯、传送、飞行点；
- 人工验证的不可直达边界节点。

`A_move`：允许移动的有向边集合。

`t_move(u,v)`：从 `u` 到 `v` 的预计移动时间。

重要：

- 最终不应直接用欧氏距离代替移动时间；
- 欧氏/点云距离只用于初期下界或缺数据时的近似；
- 实跑和地图拓扑应逐步替换直线模型。

### 3.4 Objective service set

对每个 Objective requirement `r`，定义：

`L_r subseteq V`

表示能够推进该 requirement 的物理服务位置集合。

例如：

- 固定 Boss：`|L_r| = 1`；
- 一类怪：`L_r` 是其 Questie spawn 点集合或压缩后的怪群区域；
- Item drop：`L_r` 来自 item -> NPC/Object source 反查；
- 探索：`L_r` 是触发区域；
- 交谈：`L_r` 是对应 NPC/service point。

这就是 flexible service location / neighborhood。

---

## 4. Quest 前置逻辑

### 4.1 任务内部

普通任务固定：

`A_q -> objectives(q) -> C_q -> T_q`

更精确地：

- 未执行 `A_q`，任何 Objective progress 不计入该任务；
- 当所有必要 Objective requirement 满足后，`C_q` 自动成立；
- `T_q` 只有在 `C_q` 后才能执行。

### 4.2 Questie preQuestSingle

Questie 11.34.0 实际语义：

`preQuestSingle = OR`

即候选前置中任意一个已经完成即可满足。

记候选集合为 `P_single(q)`：

`available_single(q,I) = 1 iff exists h in P_single(q): T_h in I`

若集合为空，则此条件视为真。

### 4.3 Questie preQuestGroup

Questie 11.34.0 实际语义：

`preQuestGroup = AND`

记集合为 `P_group(q)`：

`available_group(q,I) = 1 iff forall h in P_group(q): requirement(h,I)=true`

其中还必须保留 Questie 的：

- 正 ID exclusiveTo 替代语义；
- 负 ID 跳过 exclusiveTo 检查的语义。

不能把 `preQuestSingle` 和 `preQuestGroup` 合并成一个普通 prerequisite list 参与求解。

### 4.4 Accept 可用函数

最终定义：

`Avail(A_q | I, char_state) in {0,1}`

它同时考虑：

- OR/AND 前置；
- required level；
- faction/class/race/其他角色条件；
- exclusiveTo / mutually exclusive；
- Questie/Titan effective blacklist/corrections；
- 当前是否已接/已完成。

只有 `Avail=1` 时，Accept service transition 才存在。

---

## 5. 状态定义

完整状态：

`S = (v, I, p)`

### 5.1 `v`：当前位置

`v in V`

### 5.2 `I`：已完成逻辑 milestone 集合

`I subseteq E_logic`

并且必须满足逻辑闭包：

- `C_q in I => A_q in I`
- `T_q in I => C_q in I`
- 任务链解锁必须满足对应 OR/AND 条件。

可以把 `I` 看成 precedence relation 下的 feasible ideal / downward-closed logical state。

### 5.3 `p`：Objective progress

对每个 requirement `r`：

`0 <= p_r <= d_r`

其中 `d_r` 是完成需求量。

例：

- 杀 12 只：`d_r=12`；
- 拿 8 个物品：`d_r=8`；
- Boss：`d_r=1`；
- 单次交互：`d_r=1`。

为了控制状态规模，后续可以按目标类型做压缩：

- 只关心未完成/完成的 requirement 可布尔化；
- 掉落类可按期望剩余服务时间近似，而非展开每个随机掉落状态；
- 多个同源 requirement 可聚合成 shared progress state。

---

## 6. 状态转移

所有合法行为归为两大类：Move 与 Service。

### 6.1 Move transition

若 `(u,v) in A_move`：

`(u,I,p) -> (v,I,p)`

成本：

`t_move(u,v)`

移动本身不改变 Quest 状态。

### 6.2 Accept service

若当前 `v` 是任务 `q` 的合法接取位置，且：

`Avail(A_q | I, char_state)=1`

则：

`(v,I,p) -> (v,I union {A_q},p)`

成本：

`t_accept(q,v)`

### 6.3 Objective service

若：

- `A_q in I`；
- requirement `r in R_q` 尚未满足；
- `v in L_r`；

则允许物理 service action `a`。

一般形式：

`(v,I,p) -> (v,I,p')`

成本：

`t_service(a | S)`

其中 `p'` 由 action 的 coverage / yield 决定。

### 6.4 Complete closure

若任务 `q` 所有必要 Objective 已满足：

`forall r in R_q: p_r = d_r`

则 `C_q` 自动进入 `I`。

这通常作为**零移动、零或近零逻辑闭包**处理，而不是单独要求玩家移动到一个“Complete 节点”。

### 6.5 TurnIn service

若：

- `C_q in I`；
- `v` 是合法交付点；

则：

`(v,I,p) -> (v,I union {T_q},p)`

成本：

`t_turnin(q,v)`

之后更新所有后续任务的 availability。

---

## 7. Shared-Service：一个行为同时推进多个任务

这是 Route Atlas 与普通 SOP/TSP 最大差异之一。

定义一个物理 service action `a`：

`cover(a,S) = {(r, delta_r), ...}`

表示 action `a` 在当前状态下会让若干 Objective requirement 同时增加进度。

例如同一 NPC ID 18120：

- 对任务 Q1 是直接击杀目标；
- 对任务 Q2 是所需物品掉落来源；

若两个任务都已接，则杀该怪的物理成本只能计算一次：

`t_kill(18120)`

但状态更新可以同时：

`p_Q1 += 1`

以及按掉落期望/随机模型更新 `p_Q2`。

不能使用：

`t_service(Q1) + t_service(Q2)`

否则会系统性高估重叠任务的耗时，并破坏最优路线。

### 7.1 确定性第一版

第一版可用期望值：

对于掉落概率 `rho`、尚需 `k` 个物品：

期望需要击杀数近似：

`E[kills] = k / rho`

但当同一击杀也推进 kill quest 时，共享成本仍只付一次。

### 7.2 后续随机模型

样本足够后可扩展：

- stochastic shortest path；
- chance constraints；
- robust / percentile objective；
- expected time + risk penalty。

当前先追求 deterministic expected-time optimum。

---

## 8. Background task 不作为硬标签驱动路线

类似《时尚无罪》的广域任务可以有很多 service opportunities：

`L_r` 跨越大量区域。

精确模型自然会发现：

- 在完成其他主任务时顺便服务它，额外移动成本接近 0；
- 为它专程跨图的边际成本高；

因此最优路径会自动把其 progress 分散吸附在其他行动上。

`scope:background` 可以在求解后根据：

- service set 广度；
- marginal travel cost；
- 是否存在独立 detour；

自动打标。

标签用于解释，不强迫求解器按标签行动。

---

## 9. 目标状态

### 9.1 指定任务全部完成模式

给定必做任务集合 `Q_req`：

目标状态满足：

`forall q in Q_req: T_q in I`

无需规定最终物理位置时：

`G = {(v,I,p) | above condition, v arbitrary}`

如需最后回 Hub/飞点，可再加终点条件。

### 9.2 升级经验阈值模式

未来真正用于 58 -> 68 等速度升级时，并不一定要求清完全部候选任务。

定义：

- `xp_q`：任务经验；
- `xp_service`：过程中怪物/发现等期望经验；
- `XP_target`：目标等级所需经验。

目标状态变为：

`XP(S) >= XP_target`

这时任务是 selectable，而不是 mandatory。

数学上更接近 prize-collecting/orienteering 与 precedence-constrained shortest path 的组合。

这应作为第二阶段模型；赞加首个验证模型先用“指定任务集合完成”降低复杂度。

---

## 10. 最优解的定义

定义状态图：

`H = (States, Transitions)`

每个 transition 成本非负。

从初始状态 `S0` 到任意目标状态 `g in G` 的最小成本路径：

`P* = argmin_P sum_{e in P} cost(e)`

就是当前数学模型下的全局最优路线。

### 10.1 关键性质

- 路线可以重复经过同一物理位置；
- 但逻辑状态不断前进，因此 `(v,I,p)` 与同一个 `v` 的旧状态不是同一个状态；
- Quest 解锁自然发生在 state transition 后；
- 不需要预先定义圈数；
- 不需要人工定义 Accept/TurnIn/Complete 类型优先级；
- 不需要先聚类再强行排序。

---

## 11. 数学模型和求解算法必须分离

本文件定义的是**问题本身**，不是某一个求解器。

正确模型确定后，可尝试多种精确算法：

1. label-setting / dynamic programming over precedence ideals；
2. Dijkstra / A* on compressed state space；
3. Branch-and-Bound with admissible lower bounds；
4. MILP + Branch-and-Cut；
5. Benders / Generalized Benders；
6. Branch-Price-and-Cut / column generation。

这些算法若搜索完整可行域并提供 matching lower/upper bound，就可以证明 `PROVEN_OPTIMAL`。

启发式只用于：

- 快速生成 incumbent / upper bound；
- warm start；
- 超大实例 fallback。

启发式解不能冒充全局最优。

---

## 12. 第一版精确求解建议

赞加沼泽原型建议先做**压缩状态图 exact DP / label-setting**，原因：

1. Quest 前置 DAG 比较稀疏；
2. PC-SP 本身已有 ideal-based DP 理论；
3. 我们目前只有几十个有点云的 leveling quests；
4. 可以先聚合 Objective 为 service region / shared target group，避免每个 spawn 都变成状态；
5. 最容易输出明确的最优性状态与 lower bound。

### 12.1 标签状态候选

`Label = (v, I, p_compressed, cost)`

对相同 `(v,I,p_compressed)`：

只保留 cost 最小的标签。

### 12.2 dominance

若两个标签：

`L1=(v,I1,p1,c1)`

`L2=(v,I2,p2,c2)`

若：

- `c1 <= c2`；
- `I1` 在逻辑上不少于 `I2`；
- `p1` 对所有需求均不差于 `p2`；

则 `L2` 可被支配删除。

严格 dominance 条件需要在实现前证明，避免错误剪枝破坏最优性。

### 12.3 lower bound

可组合：

- 当前点到剩余 mandatory service sets 的 MST/1-tree/shortest-path relaxation；
- 忽略 precedence 的 relaxed routing lower bound；
- 忽略空间的 precedence critical service-time lower bound；
- 对每个 remaining objective 的 minimum possible service time；

取其中最大或合法组合，作为 admissible lower bound。

用于 Branch-and-Bound / A* 时必须保证不高估剩余真实成本。

---

## 13. 第一版模型明确暂不包含

为了先得到可验证 exact prototype，以下先不同时加入：

- 随机掉落的完整概率状态；
- 战斗仇恨/拉怪路径的微观模拟；
- 玩家实时操作误差；
- 五个角色分别掉落/拾取的完整联合随机过程；
- 动态刷怪竞争；
- 飞行/炉石 cooldown 的完整时变网络；
- 全外域跨地图全局模型。

第一版目标：

> 在赞加单地图、Questie有效任务数据、确定性期望耗时和压缩移动网络下，先证明一个非玩具任务子集的 `PROVEN_OPTIMAL`，验证状态模型和精确求解链条成立。

然后逐层扩展，而不是一次把所有现实复杂度塞进模型导致无法验证。

---

## 14. 当前需要从数据层继续补齐的字段

### Quest / logic

- `pre_quest_single[]`
- `pre_quest_group[]`
- `exclusive_to[]`
- `required_level`
- `effective_available`
- `objective_requirements[]`
- `objective_required_count`
- `next_quest_ids[]`

### service

- `service_entity_id`
- `service_kind`
- `service_locations[]`
- `service_region_id`
- `shared_requirement_ids[]`
- `expected_service_time`
- `expected_yield`

### movement

- `from_node`
- `to_node`
- `expected_travel_time`
- `travel_source = geometric / calibrated / observed`
- `terrain_constraint`

### observation / uncertainty

- `sample_count`
- `mean_time`
- `variance`
- `confidence`

---

## 15. 本模型与母模型的关系

正式母模型：

`Precedence-Constrained Shortest Path`

Route Atlas 增加：

1. **Stateful Service Requirements**：完成要求不仅是“访问节点”，还有任务进度状态；
2. **Flexible Service Locations**：Objective 可在多个 spawn / region 完成；
3. **Shared-Service Coverage**：一次物理服务可同时推进多个逻辑需求；
4. 后续可增加 **Selective / Prize Collecting**：目标经验达到阈值即可，不要求所有任务。

因此暂定正式问题名：

> **Route Atlas Stateful Precedence-Constrained Service Shortest Path (RA-SPCSSP)**

名字只是工程识别符，数学定义以上述状态图为准，不需要对外推广此名称。

---

## 16. 成功标准

第一阶段模型成功，不是“页面看起来像攻略”，而是满足：

1. 输入相同，模型定义唯一；
2. 所有路线都必须满足真实 Quest 前置逻辑；
3. shared service 不重复计时；
4. flexible objective 不被错误压成 centroid；
5. 求解器能输出一条可还原为实际游戏动作的完整路线；
6. 小/中型实例能给出可验证 `PROVEN_OPTIMAL`；
7. 对比用户实际路线能说明时间差来自哪一段成本或约束；
8. 实跑反馈可直接修正参数而不改模型基本结构。

如果以上成立，Route Atlas 才真正从“智能攻略”进入“可验证路线优化系统”。