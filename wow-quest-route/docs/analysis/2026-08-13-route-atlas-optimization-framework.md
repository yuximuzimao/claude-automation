# Route Atlas 路线优化理论框架（2026-08-13）

## 1. 问题重新定义

### 1.1 唯一主目标：预计总完成时间最小

Route Atlas 的优化主目标不是“圈数最少”，而是从当前真实状态出发直到计划任务集合完成的 **expected total completion time 最小**。

主目标近似拆成：

`T_total = T_travel + T_objective_service + T_accept_turnin + T_forced_wait + T_other_known_cost`

其中：

- `T_travel`：移动/骑乘/飞行/必要绕路时间；
- `T_objective_service`：杀怪、拾取、交互、等待刷新等任务目标耗时；
- `T_accept_turnin`：接取/交付及多开号操作耗时；
- `T_forced_wait`：由刷新、脚本等可建模等待造成的时间；
- `T_other_known_cost`：已验证的特殊机制成本。

圈数、折返次数、路线简洁度只能作为次级目标或解释字段。若 3 圈预计 42 分钟而 2 圈预计 50 分钟，必须选择 3 圈。

### 1.2 “全局最优”必须带证明状态

每次求解结果必须明确标记：

- `PROVEN_OPTIMAL`：精确求解器已证明当前模型目标函数下无更优解；
- `BEST_FOUND_WITH_GAP`：当前有最好可行解和下界/最优性 gap，但尚未证明最优；
- `HEURISTIC_ONLY`：仅由启发式得到，没有全局下界证明。

“理论全局最优”只允许指 `PROVEN_OPTIMAL`，且始终限定为“相对于当前模型、成本输入和约束”。模型输入错误（例如悬崖被当作直线距离）时，数学最优不等于游戏现实最优。

Route Atlas 不是单纯的地图聚类或最短路问题，而是一个带以下结构的组合优化问题：

- 单一执行者，多次外出/回访（multi-trip single vehicle）；
- 任务之间有前置、链式、AND 型解锁约束；
- 每个任务可能有接取、目标、提交三个不同空间位置；
- 同一任务链可能要求多次“回 NPC → 解锁后续 → 再去野外”；
- 某些任务目标是局部点云，某些是全图背景任务；
- 同一实际怪物/Object 可能通过“直接击杀目标”或“任务物掉落来源”被不同任务引用；
- 一个任务可以被插入多个候选圈，最终应选择边际成本最低且不破坏前置可行性的圈。

最接近的运筹学模型是 **Multi-Trip Single Vehicle Routing Problem with AND-type Precedence Constraints**。它天然可以拆为：

1. assignment master：决定任务/任务块属于第几圈；
2. sequencing subproblem：决定每圈内部的访问顺序。

这与 Route Atlas 的 A/B/C 圈 + 待插入任务 F 结构一致。

## 2. 不使用“只有关键词”的扁平标签

前端可以展示关键词，但底层必须同时保留 **typed facts + typed relations + numeric features**，否则后续推理容易把不同语义混在一起。

### 2.1 任务标签（human-facing keywords）

建议第一批稳定标签：

- `scope:local`：局部怪区；
- `scope:background`：广域/全图背景任务；
- `objective:direct-creature`；
- `objective:direct-object`；
- `objective:item-from-creature`；
- `objective:item-from-object`；
- `chain:standalone`；
- `chain:multi-stage`；
- `trip:single-pass-candidate`：理论上可单趟连续做完；
- `trip:forced-revisit`：链结构要求至少一次重新外出；
- `terrain:manual-review`：洞穴/上下层/桥/悬崖/不可直达等二维坐标不足；
- `route:background-carry`：不生成独立路线节点，只在经过重叠区时顺手推进；
- `route:isolated-chain-candidate`：与其他任务空间重合很低，但整条链自身局部集中，候选单独一次性做完。

标签是结论摘要，不作为唯一计算输入。

### 2.2 结构化关系（machine reasoning）

任务之间保留明确关系类型：

- `precedes(A,B)`：A 是 B 的前置；
- `same_accept_npc(A,B)`；
- `same_turnin_npc(A,B)`；
- `same_direct_creature(A,B)`；
- `same_resolved_creature(A,B)`：包括 direct creature 与 item→NPC drop source 交叉命中；
- `same_direct_object(A,B)`；
- `same_resolved_object(A,B)`；
- `same_required_item(A,B)`；
- `spatial_overlap(A,B)`：数值关系，不提前二值化；
- `nearby(A,B)`：仅在后续阈值/模型稳定后生成派生标签；
- `same_chain(A,B)`；
- `same_excursion_block(A,B)`：可在一次野外外出中连续兑现的链段。

## 3. 前置关系：用事件级偏序/DAG，而不是任务级列表

每个普通任务 Q 拆成三个不同动作节点：

- `A(Q)` = Accept：接任务；
- `C(Q)` = Complete：完成任务目标；
- `T(Q)` = TurnIn：交任务。

任务内部固定依赖：

- `A(Q) → C(Q)`：未接任务不能把目标计为该任务完成；
- `C(Q) → T(Q)`：未完成不能交；
- `A(Q) → T(Q)`：作为显式一致性约束保留，虽然通常可由前两条传递推出。

任务链依赖则落在事件之间，而不是模糊地落在“任务之间”：

- 若 Q1 交付后才解锁 Q2：`T(Q1) → A(Q2)`；
- 若 Q2 需要一组前置全部完成，则是 AND 型：`T(Qa), T(Qb), ... → A(Q2)`；
- 若服务器语义是“接到/完成但未交即可解锁”，则按真实条件把边连到对应 `A/C/T` 事件，而不强行统一成 TurnIn。

因此完整结构类似：

`A(Q1) → C(Q1) → T(Q1) → A(Q2) → C(Q2) → T(Q2) ...`

### 3.1 Ready Set：已满足前置的动作就是当前可执行源节点

在任意游戏状态 S 下，所有前置已经满足、但动作尚未执行的事件组成 `Ready(S)`。

其中已经解锁的 `A(Q)` 没有剩余前置，可视为当前 DAG 的源节点。但不再给任何事件一个模糊、永久的“高优先级”。

**重要修正：Ready Set 的排序规则不是主求解理论，也不保证全局最优。** 它只作为：①快速构造初始可行路线；②全局求解超时时的 fallback；③解释局部决策的审计字段。主求解器应直接对整张地图的事件、trip assignment、precedence 与 sequencing 做全局组合优化；若精确算法证明 optimality，才称为相对于当前模型和目标函数的全局最优。

下面的 `P(e | S, R)` / lexicographic policy 因此降级为**候选启发式策略**，而不是冻结的最终业务规则。其各字段分别借鉴 scheduling slack、regret insertion、cheapest insertion、critical-path/precedence 信息，但字段顺序本身是本项目设计选择，后续必须用赞加真实实例与实跑结果验证。

#### 3.1.1 先做当前位置闭包，不需要排序

若当前坐标/当前 Hub 上存在可立即执行、且不增加移动成本的 Ready 事件，则执行 **local closure**：

1. 执行当前位置全部 Ready `A/C/T`；
2. 更新 DAG / Ready Set；
3. 若新解锁事件仍在当前位置，则继续执行；
4. 直到当前位置不再有零移动成本的 Ready 事件才离开。

因此“当前 NPC 已经可以接的任务全部接齐”是一个零移动成本闭包规则，而不是 Accept 的永久类型优先级。TurnIn 若解锁同 NPC 的新 Accept，也会在同一次 closure 中自动继续处理。

#### 3.1.2 需要移动时采用字典序优先规则，而不是任意加权总分

对所有需要移动才能执行的 Ready 事件，先算固定字段，再按以下顺序比较；只有上一层完全相同时才进入下一层：

1. `feasible`：硬约束，必须为 true；
2. `circle_slack` 升序：`latest_feasible_circle - earliest_feasible_circle`，越小越不能拖；
3. `defer_excursion_penalty` 降序：如果推迟该事件，会额外增加多少次 forced excursion / 区域回访；
4. `defer_route_regret` 降序：现在不做，未来最佳可行插入相较现在最佳插入会多增加多少预计路程/时间；
5. `insertion_delta` 升序：现在把事件插入当前路线需要增加多少预计路程/时间；
6. `critical_unlock_gain` 降序：执行后使剩余事件 DAG 的 critical excursion depth / 最早可解锁层数减少多少；
7. `same_stop_batch_gain` 降序：到达该地点后能一次 closure 顺带执行多少 Ready / newly-ready 事件；
8. 最后仅为保证结果确定性使用稳定 ID 排序，不赋予业务含义。

这是一套 lexicographic policy，不把“多一次整圈折返”和“多骑 300 米”通过随意权重硬加成同一个分数。只要输入状态相同，排序结果必须相同。

#### 3.1.3 三个最重要的可测量量

`circle_slack(e)`：

- `earliest_feasible_circle` = 当前前置允许它最早进入哪一圈；
- `latest_feasible_circle` = 若还想保持当前最小 excursion lower bound，它最晚必须进入哪一圈；
- slack 越小，事件越接近 critical path。

`defer_excursion_penalty(e)`：

- 比较“本圈执行 e”与“本圈跳过 e”后重新计算的最小未来 excursion count；
- 若跳过会把理论最少回访从 3 次变成 4 次，则 penalty=1，优先级应压过普通距离差。

`defer_route_regret(e)`：

- `best_future_insertion_cost_if_deferred - best_insertion_cost_now`；
- 用来识别“现在顺路几乎免费，但错过以后会专程折返”的动作；
- 与单纯 nearest-neighbor 不同，它衡量的是**错过当前机会的代价**。

#### 3.1.4 Accept 的规范化规则

Ready Accept 不再直接写成 `priority=highest`，而采用以下固定规则：

- 若 Accept 属于当前 local closure：必做；
- 若不在当前位置：与其他 Ready 事件使用完全相同的 lexicographic policy；
- Accept 的优势通过 `critical_unlock_gain`、`defer_excursion_penalty`、`defer_route_regret` 自然体现，而不是事件类型 bonus；
- 因此一个远距离 Accept 不会仅因“它是接任务”就压过一个现在不交便会造成额外整圈折返的 TurnIn。

这使优先级从人工经验变成可审计决策：每个事件都能输出“为什么排在前面”的字段值。

### 3.2 特殊任务如何兼容

- 自动完成/无目标任务：`C(Q)` 可视为零时长节点，或在求解时折叠成 `A(Q) → T(Q)`；
- 物品触发任务：`A(Q)` 的地点/触发条件来自该启动物品，而不是 NPC；
- 探索/脚本/交谈任务：`C(Q)` 仍存在，只是其空间实体不是怪物点云；
- 可重复/日常/互斥任务：通过额外 availability 状态约束控制 `A(Q)` 是否进入 Ready Set。

任务级前置关系只保留为这个事件 DAG 的人读投影。

### 3.3 longest chain 只给理论下界

若规定“一圈只能执行互相无前置关系的阶段”，则偏序分层的最少层数由最长链高度给出（Mirsky / dual Dilworth）。

但游戏里任务链不能直接按 quest count 计算圈数，因为：

- 某任务交付 NPC 就在当前路线末端；
- 交完能立刻接后续；
- 后续目标可能仍在当前圈接下来要经过的区域；

所以真正要计算的是 `excursion depth`，不是 `quest chain depth`。

## 4. Excursion Block：解决“这条链到底需要跑几次”

把一条任务链压缩成若干 **外出块（excursion blocks）**。

一个 block 表示：从某任务中心/交付节点出发，在不发生“必须结束当前野外行程才能继续”的情况下，可以连续完成的一组事件。

例如：

`NPC A 接 Q1 → 东边做 Q1 → 回 A 交 → 接 Q2 → 东边再做 Q2`

如果第二次去东边无法在第一次东边行程里提前完成，则至少 2 个 excursion blocks。

而：

`A 接 Q1 → 东边做 Q1 → 东边 NPC B 交 → B 接 Q2 → 继续向南做 Q2`

可能仍属于同一个 excursion block。

### 4.1 forced revisit lower bound

对每条链计算：

- `chain_depth`：任务级最长前置深度；
- `excursion_depth`：压缩后的外出块深度；
- `forced_return_count = excursion_depth - 1`；
- `revisit_hubs[]`：哪几个 NPC/Hub 导致重新解锁；
- `revisit_regions[]`：哪几个目标区域会被重复进入。

地图整体最少圈数的一个硬下界应来自所有链的 `max(excursion_depth)`，但它仍不是最终圈数：多个链可以共享同一圈，地形/空间也可能额外增加圈数。

## 5. F 应该放入 A/B/C 哪一圈：按“可行插入 + 边际成本”判断

对候选任务 F，不直接先选“离哪个圈最近”，而是：

### 5.1 可行性过滤

圈 k 必须满足：

- F 所有必须前置在进入圈 k 前已完成，或能在圈 k 中、F 之前完成；
- 若 F 的后续被有意安排在更早圈，则不可插入；
- 等级/阵营/服务器可用性满足；
- 若 F 是某 excursion block 的中间阶段，不能把 block 任意拆散；
- terrain/manual constraints 不冲突。

### 5.2 边际成本评分

对每个可行圈计算：

`ΔCost(F → circle k)`，至少由以下事实组成：

- 插入后新增骑乘距离；
- F 点云与本圈点云的 NN p50/p90、中心距、重叠；
- 是否共享实际怪物/Object；
- 是否共享接取/交付 NPC；
- 是否减少未来一次 forced revisit；
- 是否导致新的额外回 Hub；
- 是否让某条链后续提前解锁并与本圈剩余路线重合；
- F 是否是 background task（背景任务通常插入成本≈0，但不产生独立节点）；
- F 是否是 isolated-chain candidate（若与所有圈都低重合，但自己的整条链集中，则比较“单独整链做完”与“分散塞圈”的成本）。

最终选择边际总成本最低的可行圈，而不是最近圈。

## 6. “孤立但链很长”的任务：允许单独闭环

用户提出的重要例外：

> 一个地点很近但与其他任务重合不多，任务链又必须反复去同一区域，那么可能应该专门把整条链做完，而不是每圈路过一次。

因此需要计算 `isolated_chain_score`：

- 与其他主圈的空间重合低；
- 链内各阶段目标彼此高度重合；
- 链内 accept/turn-in hub 稳定；
- 若拆散会制造多次相同 detour；
- 一次专程闭环的总成本 < 把各阶段分别插入其他圈的总增量成本。

满足时生成 `route:isolated-chain-candidate`，并把整条链作为一个候选 macro block 参与路线优化。

## 7. 推荐的求解结构：Assignment Master + Sequencing Subproblem

这与 AND-precedence multi-trip routing 的 Logic-Based Benders decomposition 思路对应。

### Master：决定“谁去哪一圈”

变量近似为：

`x(task_block, circle) ∈ {0,1}`

约束：

- 每个必须任务块恰好分到一个圈；
- background block 可挂多个圈但不强制形成节点；
- precedence / excursion-depth 约束；
- 某些 chain block 必须同圈或按先后圈分配。

目标：最小化估计的跨圈成本、forced revisit、孤立 detour、过晚解锁等。

### Subproblem：每一圈内部排序

给定本圈任务块后，做 precedence-constrained routing / Sequential Ordering Problem：

- 访问哪些任务中心；
- 先去哪个怪区；
- 哪个 NPC 交完马上接后续；
- 点云区域内部从哪个方向进入/退出；
- 在不破坏前置的情况下最小化骑乘距离。

可用 cheapest insertion / local search / CP-SAT/OR-Tools 做近似，不追求证明全局最优。

## 8. 当前 Route Atlas 数据层需要新增的字段

任务级：

```text
scope_class
scope_confidence
objective_modes[]
resolved_creature_ids[]
resolved_object_ids[]
chain_id
chain_depth
excursion_block_id
excursion_depth
forced_return_count
revisit_hubs[]
revisit_regions[]
background_carry
terrain_manual_review
isolated_chain_score
```

关系级：

```text
relation_type
source_task_id
target_task_id
entity_ids[]
spatial_metrics
precedence_distance
same_excursion_block
confidence
```

路线候选级：

```text
candidate_circle_id
feasible
infeasible_reasons[]
insertion_delta_distance
spatial_fit
chain_unlock_gain
revisit_reduction
hub_overlap_gain
background_gain
isolated_chain_penalty
estimated_delta_cost
```

## 9. 当前阶段的实现顺序

1. 先给已有赞加任务生成稳定标签，但标签必须由结构化事实派生；
2. 构建 task/accept/objective/turn-in/next 的事件 DAG；
3. 计算 chain depth 与 excursion blocks；
4. 从点云判定 local/background；
5. 将 actual resolved creature/object ID 作为一等关系；
6. 建 A/B/C 圈候选后，对每个任务/chain block 做 feasible-circle 集合；
7. 用 insertion delta 而非纯距离决定 F 放哪圈；
8. 最后再做每圈内部排序和路线箭头。

## 10. 理论来源

- Multi-Trip Single Vehicle Routing Problem with AND-type Precedence Constraints：任务分配到多趟 + 趟内排序 + AND 前置；论文使用 Logic-Based Benders Decomposition 将 assignment master 与 sequencing subproblems 分离。
- Sequential Ordering Problem / TSP with precedence constraints：给定访问节点与 precedence DAG 后，寻找满足前置的最低成本访问顺序。
- Mirsky theorem（dual of Dilworth）：偏序高度对应最少 antichain layers，可作为“最长依赖链决定最少阶段数”的理论原型；在 WoW 中需先把普通 quest chain 压缩为 excursion blocks 后再使用。
- Pickup-and-Delivery / precedence-constrained routing：接取必须先于提交，与 Quest 的 accept/turn-in 事件顺序天然对应。

本项目不照搬任何单一模型，而采用“偏序分层 + multi-trip assignment + precedence-constrained sequencing + Questie 空间点云 + 游戏任务链语义”的混合框架。