# Route Atlas 母模型选择：从现实运筹结构而不是“游戏类比”出发

日期：2026-08-13
状态：模型选型基线

## 1. 先抽象我们的真实问题

不使用“任务攻略”“分圈”这些游戏表面词汇，Route Atlas 的底层问题是：

1. 只有一个执行者在带成本的空间网络中移动；
2. 执行者允许重复经过同一地点；
3. 某些动作只有在一组前置状态满足后才变得可执行；
4. 前置条件既可能是 AND，也可能是 OR；
5. 一个普通任务可拆成 Accept / Objective / Complete / TurnIn 等逻辑事件；
6. Accept / TurnIn 往往是固定位置；Objective 往往是一组候选点或一片可服务区域；
7. 同一次物理服务可能同时满足多个逻辑需求，例如杀同一怪同时推进两个任务；
8. 有些需求是必须完成的，有些在“达到目标经验即可”的模式下可以选择跳过；
9. 目标是从当前真实状态到目标状态的**预计总完成时间最小**；
10. “第几圈”只是最优路径形成后的人类解释，不应预先作为硬结构输入。

因此我们需要寻找的不是“最像魔兽任务”的论文，而是满足上述数学结构最多、且底层假设冲突最少的运筹学母模型。

---

## 2. 候选母模型对比

### 2.1 Single-machine scheduling with precedence constraints

优点：
- DAG / 偏序、release、processing time、critical path 等理论成熟；
- 精确 DP、Branch-and-Bound、Lagrangian relaxation 都很成熟。

根本缺陷：
- 机器不在空间里移动；
- 两个动作之间的 setup/travel cost 在我们的场景中是决定性的，而且取决于动作顺序和位置。

结论：
- 适合作为 precedence / scheduling 的辅助理论；
- **不适合作为 Route Atlas 母模型**。

### 2.2 TSP with precedence / Sequential Ordering Problem (SOP)

优点：
- 一个执行者；
- 节点有顺序约束；
- 最小化完整访问序列的旅行成本；
- 精确 DP、MILP、Branch-and-Cut 研究成熟。

根本缺陷：
- 经典定义通常要求指定节点各访问一次；
- 我们需要重复经过 Hub、路线节点、甚至同一怪区；
- 节点可用性会随状态动态改变；
- Objective 常不是固定单点。

结论：
- 比单机调度接近很多；
- 是重要的求解技术来源；
- 但“每个节点一次”的结构仍不够贴底层。

### 2.3 Multi-trip vehicle routing with precedence

优点：
- 一个执行者可以多趟外出；
- 可处理 precedence；
- assignment + sequencing 的分解思想很适合解释“任务放哪一圈”。

根本缺陷：
- 经典模型把 trip / depot-return 作为问题结构的一部分；
- 我们并不知道最优路线天然应分几圈，也不应该先强迫每圈从某 depot 开始结束；
- 如果先定义 trip，可能反过来限制真正的最优路径。

结论：
- 适合做求解分解/路线解释；
- **不作为母模型**。

### 2.4 Pickup-and-Delivery TSP / VRP

优点：
- pickup 必须先于 delivery，与 Accept → TurnIn 有表面对应；
- pairing / precedence 的精确算法成熟。

根本缺陷：
- 运输问题的核心状态是“货物是否在车上/容量”；
- Quest 的 Accept 不是把某种货物装上车，Objective 也不是运输行为；
- 任意任务链 DAG 比 pickup-delivery pair 更一般。

结论：
- 某些 precedence cut / exact algorithm 可借鉴；
- 不应把 Quest 强行解释成运输请求。

### 2.5 Precedence-Constrained Generalized TSP (PCGTSP)

优点：
- 节点被分成 cluster；
- 每个 cluster 只需访问一个候选节点；
- cluster 之间有偏序；
- 2023 EJOR 已有 MILP、polyhedral study 和 Branch-and-Cut。

与 Route Atlas 的对应：
- “完成某个 Objective”可以不是固定一点，而是在候选 spawn cluster 中选择服务点；
- “访问哪个点完成这个需求”可以由优化器决定。

缺陷：
- 仍以 tour / 每 cluster 一次为主；
- 重复访问地点与状态解锁并不是其核心定义；
- 一个实际服务同时满足多个逻辑 Objective 仍需扩展。

结论：
- **非常适合做 flexible objective location 的扩展模块**；
- 不如 PC-SP 适合作为总母模型。

### 2.6 Therapist Scheduling and Routing with Flexible Service Locations

现实场景：医院治疗师在医院中移动；病人治疗可以在多个服务地点之一执行；不同治疗之间存在 precedence / synchronization；论文使用 exact Branch-Price-and-Cut，并求出最多 120 个 treatment 的 proven optimum。

优点：
- 同时具备 routing + scheduling；
- 服务地点可选；
- precedence；
- 现实系统而非游戏类比；
- exact optimization 已有成功案例。

缺陷：
- 原问题有多治疗师、time windows、地点容量、同步等我们并不需要的结构；
- 它的“服务地点可选”很像 Objective 区域，但“状态解锁后地点才可进入、允许任意重复经过”的语义不如 PC-SP 直接。

结论：
- **最像我们的现实应用型先例之一**；
- 特别适合借鉴 flexible service locations + routing/scheduling 的求解架构。

### 2.7 Pickup-and-Delivery TSP with Neighborhoods (PDTSPN)

优点：
- 服务对象不是固定点，而是任意形状 neighborhood；
- 访问 neighborhood 中哪个实际点也属于决策变量；
- 2023 Transportation Science 给出 MINLP + Generalized Benders exact framework。

对应：
- Questie spawn point cloud / 怪区可以看成离散 neighborhood；
- 不应把 point-cloud centroid 当作固定服务点；
- 进入怪区的切入点本身可以成为优化变量。

缺陷：
- pickup-delivery 的 pair 结构仍不是我们完整的 DAG。

结论：
- **作为 Objective neighborhood 的数学来源非常合适**。

### 2.8 Covering Salesman / Covering Tour

现实逻辑：不必亲自访问每个需求点；访问某个服务点即可“覆盖”附近的一组需求。

对应：
- 杀一只/一批同 ID 怪，可以同时推进多个任务；
- 访问同一 Object 或实体可以同时满足多个逻辑 Objective；
- 物理服务次数与逻辑任务数量不能简单一一对应、也不能把耗时直接相加。

缺陷：
- 经典 covering 主要依赖空间覆盖半径，不处理复杂任务前置。

结论：
- **适合作为 shared service / one-action-covers-many-demands 的扩展思想**。

---

## 3. 选择：PC-SP 作为母模型

### 3.1 Precedence-Constrained Shortest Path (PC-SP)

Büsing, John, Mathwieser, Networks 2025。

其核心定义：

- 给定有向或无向图 `G=(V,A)`；
- 给定起点 `s`、终点 `t`；
- 每条边有非负成本；
- 节点间存在 precedence relation；
- 某个节点只有在它的所有前置节点已经访问后才能首次访问；
- **路径不要求 simple，可以重复访问节点**；
- 目标是满足 precedence 的最小成本 `s-t` 路径。

这个定义与 Route Atlas 最独特的几个结构高度一致：

1. 我们本质上是在地图图网络上移动，不是纯任务排序；
2. Hub / 道路 / 区域允许反复经过；
3. Quest chain 本质上是“完成前置以后后续事件才可进入”；
4. 路线目标就是从当前状态到目标状态的最低累计时间；
5. 不需要先定义 trip / circle；
6. 论文甚至用 video-game speedrun/quest unlock 和灾害救援清障作为直观应用案例。

论文还证明 AND 与 OR precedence 版本可以相互归约，并给出基于 partial-order ideals 的 exact dynamic programming。这和 Questie 的 `preQuestGroup` / `preQuestSingle` 语义非常相关。

### 3.2 为什么它比 SOP 更适合作为母模型

SOP 问：

> “这些必须访问的节点，每个访问一次，在满足 precedence 下按什么顺序最便宜？”

PC-SP 问：

> “从当前状态到目标状态，在整个图里允许重复走路，但某些节点只有满足前置后才允许进入，哪条完整路径最低成本？”

我们的游戏语义更接近第二个问题。

例如：

`玛加沙 → 鳗鱼区 → 玛加沙 → 后续任务区域`

同一个 Hub 被第二次访问是正常且可能强制发生的，不应该先通过复制“玛加沙1 / 玛加沙2 / 玛加沙3”才能勉强适配模型。

---

## 4. Route Atlas 应定义成 PC-SP 的扩展，而不是另起炉灶

暂定名称：

**PC-SP with Stateful Service Requirements and Flexible Service Locations**

即：

> 带状态化服务需求与柔性服务位置的前置约束最短路径。

### 4.1 状态层

状态不只是当前位置 `v`，还包括已经满足的逻辑事件集合 `I`：

`state = (v, I)`

`I` 必须是 precedence relation 下的一个可行 ideal / downward-closed set。

对于需要计数的 Objective，还需要保留有限的 progress state，例如：

`state = (v, I, p)`

其中 `p` 可以记录尚未完成的有限任务进度；实际实现时必须压缩，不能直接把每只怪的击杀数全部展开。

### 4.2 事件层

普通 Quest `q`：

- `A(q)`：Accept milestone；
- `O(q,k)`：一个或多个 Objective requirement；
- `C(q)`：Complete milestone；
- `T(q)`：TurnIn milestone。

逻辑依赖：

`A(q) -> O(q,k)`

全部必须 Objective 满足后：

`O(q,1) AND ... AND O(q,m) -> C(q)`

随后：

`C(q) -> T(q)`

后续任务：

`T(q1) -> A(q2)`，或根据 Questie 实际语义构造 AND / OR 解锁。

### 4.3 物理服务位置层

- Accept / TurnIn：固定 NPC/Object 点或少量候选点；
- Objective：不是 centroid，而是一个 `service set / neighborhood`；
- Questie point cloud 提供离散 service set；
- 对移动 NPC 可进一步加入 waypoint/time-dependent service set。

因此一次逻辑事件的“访问位置”可以由求解器选择。

这部分借 PCGTSP 与 PDTSP with Neighborhoods 的成熟思想。

### 4.4 Shared Service / Coverage 层

一个物理服务 action `a` 可以覆盖一组逻辑需求：

`covers(a) = {O(q1,k1), O(q2,k2), ...}`

例如 NPC 18120：

- 是《你死我活》的 direct kill target；
- 同时是《偷回蘑菇》的 item drop source；

因此打该实体的时间成本只能支付一次，然后根据实际任务规则同时增加多个 progress。

这不是普通 TSP 的“一节点 = 一需求”；应借 covering / set-covering 的思想建成“一个 service transition 更新多个需求状态”。

### 4.5 Background task

《时尚无罪》这类广域任务不需要被人工规定成“background”。

更理想的数学结果是：

- 它的 service opportunities 广泛分布在多个主路线附近；
- 在许多状态转移上具有接近零的 marginal travel cost；
- 因而最优解自然把其进度分散吸附在其他主路径上；

`scope:background` 标签应是对这一结构的派生解释，而不是决定路线的硬规则。

---

## 5. 哪些结构不应该进入母模型

### 5.1 “圈数最少”

不是目标。

圈数应该从最终路径中的 Hub revisit / excursion 结构自动解释出来。

### 5.2 “Accept 永远优先”

不是硬规则。

如果当前就在 NPC 面前，零额外成本 Accept 自然会成为 dominance / closure；如果需要横穿地图去接，精确模型自己比较其未来收益与移动成本。

### 5.3 固定距离阈值决定 nearby

不是硬约束。

点云距离、重合、服务共享是成本结构；是否应该同路由由最优解决定。

### 5.4 人工先分 A/B/C 圈

不做。

A/B/C 只在求解后用于人读展示；除非以后为了计算分解，把它们作为内部 Benders/column generation 的辅助对象，也不能改变原问题可行域。

---

## 6. 精确求解方向

### 6.1 第一优先：State-space DP / Labeling over precedence ideals

PC-SP 2025 的 exact DP 本身就以 precedence ideal 为状态核心；SOP / precedence scheduling 也有长期使用 feasible subsets / ideals 做 DP 的传统。

Route Atlas 的自然状态可从：

`(current physical node, completed event ideal)`

开始。

优势：
- 与任务 DAG 语义完全一致；
- 重复经过地点天然支持；
- 可以产生严格 lower/upper bound；
- 方便先在赞加的压缩事件图上验证 proven optimum。

风险：
- 一旦 Objective progress 维度展开，状态爆炸；
- 需要 dominance、事件压缩、shared-service aggregation、区域压缩。

### 6.2 第二优先：MILP / Branch-and-Cut

可以借 PCGTSP/SOP 的 order/flow formulations、precedence cuts、subtour/path cuts。

适合在事件被压缩成几十个 macro service requirements 后求全局最优。

### 6.3 Flexible service location：Generalized Benders / decomposition

如果“访问哪一个 spawn / 哪个切入点”与“事件顺序”同时放进模型太大，可以借 PDTSPN：

- master 决定逻辑服务顺序；
- subproblem 决定每个 neighborhood 的最优具体服务点；
- 用 Benders cuts 反馈下界。

### 6.4 Route-based column generation / Branch-Price-and-Cut

医院 therapist routing 的 exact 方法证明：routing + scheduling + flexible service locations + precedence 的现实规模问题可以通过 branch-price-and-cut 求 proven optimum。

如果赞加事件数量最终超过简单 DP/MILP 的可解规模，这会是重要升级方向。

---

## 7. 当前最重要的模型正确性要求

在写求解器前必须解决：

1. Questie effective DB：raw + WotLK/Titan corrections；
2. `preQuestSingle` OR / `preQuestGroup` AND 保持原始语义，不再为求解合并；
3. exclusiveTo / negative preQuestGroup 等 Questie 真实 availability 逻辑；
4. direct objective 与 item->NPC/Object resolved source；
5. 同实体 shared-service；
6. 每个 Objective 的 required count / item count；
7. Accept / TurnIn / Objective service location sets；
8. 真实移动时间模型，而不是只用欧氏坐标；
9. objective service time：杀怪、掉落、拾取、交互、多开操作；
10. 用户实跑发现的洞穴、桥、上下层、脚本、刷新等特殊约束。

只有这些输入足够正确，`PROVEN_OPTIMAL` 才有现实意义。

---

## 8. 与现实问题的类比

### 最接近的现实直觉 1：灾害救援/清障路径

某区域在清除障碍或建立补给路线之前不能进入；救援者可以重复经过道路；目标是到达最终目标的最短可行路径。

这正是 PC-SP 论文给出的现实应用之一。

### 最接近的现实直觉 2：医院治疗师移动与排程

一个治疗师/多个治疗师在建筑内移动；治疗有多个可选服务地点；治疗之间有 precedence；需要同时优化移动路线与治疗顺序。

这对应我们的“NPC固定服务 + 怪区柔性服务 + chain precedence”。

### 最接近的现实直觉 3：巡检/维护中的一次访问覆盖多个需求

到一个设施/区域执行一次服务，可以同时满足多个检查或覆盖周边多个需求。

这对应 shared target / background objectives。

因此 Route Atlas 不应该被描述成“魔兽版 TSP”。更准确是：

> **一个带前置解锁、柔性服务区域、共享服务状态更新的单执行者最短路径问题。**

---

## 9. 参考模型（正式来源）

1. Büsing, C.; John, D.; Mathwieser, C. (2025). *Precedence-Constrained Shortest Path*. Networks 86(3), 282–295. DOI: 10.1002/net.22282.
2. Khachai, D.; Sadykov, R.; Battaia, O.; Khachay, M. (2023). *Precedence constrained generalized traveling salesman problem: Polyhedral study, formulations, and branch-and-cut algorithm*. European Journal of Operational Research 309(2), 488–505. DOI: 10.1016/j.ejor.2023.01.039.
3. Gao, C.; Wei, N.; Walteros, J. L. (2023). *An Exact Approach for Solving Pickup-and-Delivery Traveling Salesman Problems with Neighborhoods*. Transportation Science 57(6), 1560–1580. DOI: 10.1287/trsc.2022.0138.
4. Jungwirth, A.; Desaulniers, G.; Frey, M.; Kolisch, R. (2022). *Exact Branch-Price-and-Cut for a Hospital Therapist Scheduling Problem with Flexible Service Locations and Time-Dependent Location Capacity*. INFORMS Journal on Computing 34(2), 1157–1175. DOI: 10.1287/ijoc.2021.1119.
5. Current, J. R.; Schilling, D. A. (1989). *The Covering Salesman Problem*. Transportation Science 23(3), 208–213. DOI: 10.1287/trsc.23.3.208.
6. Salii, Y. (2019). *Revisiting dynamic programming for precedence-constrained traveling salesman problem and its time-dependent generalization*. European Journal of Operational Research. DOI source in publisher record.

## 10. 选型结论

正式母模型：

> **Precedence-Constrained Shortest Path (PC-SP)**

Route Atlas 的扩展：

> **PC-SP + Stateful Service Requirements + Flexible Service Locations + Shared-Service Coverage**

辅助模型的角色：

- SOP / TSP-PC：precedence sequencing、DP/MILP/cuts；
- PCGTSP：离散候选服务点 / spawn clusters；
- PDTSP with Neighborhoods：任意形状 service neighborhood 与 Benders；
- Therapist routing：现实 routing+scheduling+flexible locations+precedence 的 exact 架构；
- Covering Salesman：一次物理服务覆盖多个逻辑需求；
- Multi-trip VRP：只用于后验 excursion/circle 分解或算法分解，不定义原问题。

下一步：基于这个母模型正式写 Route Atlas 数学变量、状态、目标函数、转移/约束和可证明最优的求解状态，不再先写 A/B/C 分圈或人工 dispatching priority。