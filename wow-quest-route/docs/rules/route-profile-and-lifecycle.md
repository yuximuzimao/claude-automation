# Route Profile / Route Program 与生命周期规则

用途：这是项目中**单段正式路线是什么、多个Profile怎样组成完整执行方案、二者保存什么、如何被重建和退役**的唯一规则 owner。它不负责 Task Card 事实、任务删留、路线排序、玩家备注或复杂传播分类。

## 1. Route Profile 的身份

Route Profile 表示一个明确 scope 下可重复执行的正式路线段。一个 `profile_id` 只允许一份正式路线真源；同一地图可以有普通、DK 或其它不同 Profile。所有任务只用稳定 `task_id` 引用 Task Card。

`scope.character_profile`必须引用`data/character-profiles/<id>.json`中的机器配置。该配置只保存Availability真正需要的稳定静态身份（当前为game variant、faction、race、class、party_size及来源）；等级/经验、声望、装备、天赋和当前任务状态都不属于Character Profile。Route Profile不得靠`horde-fivebox-current`这类字符串名字本身推断种族/职业。

## 1.1 Route Program 的身份

当一套业务路线需要连续执行多个Route Profile时，必须有一个薄的Route Program作为**Profile组合顺序的唯一真源**。它回答“先执行哪个Profile、再执行哪个Profile，以及整套Program从什么结构化起始状态/目标开始”；若两个相邻Profile之间存在**不能诚实归入任一本地图Profile**的跨图换乘/传送链，Program还可用`boundary_transitions`保存这条边界操作链。

最小Program只保存无法从各Profile内部重新得到的组合决策：

- `program_id / version / status / scope / goal`；
- 严格有序的`profile_ids`；
- Program级初始状态中真实需要提供给第一个Profile/整链模型的最小字段；
- 必要的Program级变更记录。

Route Program**不复制**Profile的task_ids/actions/geometry/stepGroups，也不保存Task Card事实。Profile之间的普通连续性由“前一个Profile fresh exit → 后一个Profile entry”机械验证，不在Program逐边复制状态。只有跨Profile边界本身存在真实玩家操作且这些操作不属于任一成员Profile时，才允许写`boundary_transitions`；其中只允许移动/系统飞行/固定交通/任务传送/炉石类操作，不允许借此承载接做交任务或复制本地图路线。若Profile出口动作/共享handoff与Program边界链同时宣称同一边界真值，必须blocked而不是二选一猜测。

`display.order`只是页面呈现顺序，不能代替Route Program业务顺序。若只独立执行一个Profile，可以显式使用单Profile冷启动entry state而不创建Program；一旦要计算跨Profile XP、满级时点、继承飞行点/炉石、整套墙钟/经济/Gh或验证跨图连续性，必须有Program上下文。

## 2. 保存什么

Route Profile 只保存无法从 Task Card、公共规则或其它已保存路线原子重新得到的**正式路线决策与最小原子信息**：

- 当前路线采用的 task_id 集合；
- 结构化动作及严格顺序；
- stepGroups；
- 真实visit/地点的空间归属与必要坐标原子，以及动作对地点的稳定引用。Profile以`scope.primary_zone_id`提供主要地图空间，跨图visit才在location上覆盖`zone_id`；不得从标题/图片名猜地图；
- NPC/地点等动作参与者的原子引用；
- Profile 特有的原子movement/交通、炉石、飞行点、条件动作。线性Profile中每个非首visit通过`incoming_movement`拥有唯一入边：普通点到点只需保存`self_move`，不要求为路线业务强行区分骑马/步行；只有已明确且会影响计算的飞行/游泳等特殊自主移动才补充mode。显式系统鸟/炉石/固定交通/任务传送等只引用对应movement action_id，不复制第二份kind；
- 真实影响Timing/Optimization、但无法从上述原子可靠重建的最小route-only service语义；当前只允许写入`service_overrides`：同visit已证实共享服务，或按稳定action范围表达的background coverage window及其收口策略；
- 最小 `entry_requirements`；Profile 不人工保存可由“Program/冷启动真实入口状态 + actions”唯一重放得到的 exit state；
- Profile 自身的 scope、版本、状态、display元数据和变更记录。

`Target Cluster / Spatial Instance / Background Layer`首先属于Route Optimization/Service Context的结构化结果：**能从Task Card + Profile原子机械重建的，不再作为第二真源写进Profile；只有真实路线决策无法重建、且会改变执行/Timing/Optimization的那部分，才允许以通用最小原子进入Profile。**

同理，movement/transport只允许一个canonical业务真源。地图point的线型、旧`location.transport`等展示/兼容字段只能由canonical movement派生，不能与动作级交通两处独立人工维护。

不得复制 Task Card 中的共享机制、掉落、Boss 技巧、详细攻略、证据或玩家备注。

## 3. 结构化动作

正式动作必须是结构化原子，例如：

    {"kind":"accept","task_id":10208,"npc_name":"前线指挥官托尔克","location_ref":"p007"}
    {"kind":"objective","task_id":10208,"location_ref":"p008"}
    {"kind":"taxi","from_name":"猎鹰岗哨","to_name":"萨尔玛"}

条件不复制动作类型，使用普通动作加可选 `when`。完整中文执行句不是 Route Profile 字段；Publisher 根据原子数据和 Route Display 规则生成。

## 4. 信息主体与转换边界

Route Profile 必须保存足以确定玩家动作语义的原子，而不是保存旧中文句子。

例如“空军指挥官布拉克 → 乘任务飞行 → 做《任务：地狱岩床》”应拆为：

- NPC：空军指挥官布拉克；
- 行为：任务脚本飞行；
- task_id：10162 的 objective；
- 对应 location/transport。

Route Display 再按固定转换规则组合中文。路径、NPC、任务动作是不同语义，不允许迁移器把“奥格瑞玛”等地点误当 NPC。

地点也区分“玩家导航点”和“仅执行上下文”。普通地点默认是`map_anchor`，应能落在对应地图坐标体系；NPC/任务传送、相位/镜像/灵魂视角等中间态若玩家只需要执行“触发 → 做事/继续 → 返回”而不需要在该层按地图点导航，可用`location_role=transition_context`保存真实顺序与状态，不强制虚构坐标。它不是特殊任务白名单，也不是绕过UNKNOWN的捷径：一旦真实玩家操作需要在该环境自行移动/定位，仍必须建可验证`map_anchor`或显式UNKNOWN。

## 5. 路线上下文

动作顺序本身表达“什么时候接/做/交/转场”。不建立第二个 route-note 层重复“先 A 后 B”“做完继续”“与 B 一起做”。

## 6. Profile 入口要求与 Program 真实起始状态

Profile 与 Program 不再把两种不同语义混成同一个 `entry_state_contract`：

- Route Program 的 `entry_state_contract` 是整套执行链唯一的**真实起始 RouteState**。`active_task_ids` 在这里是已知的精确任务栏集合；其它可选字段省略仍表示未知，显式空数组/null才表示已知为空/未绑定。
- Route Profile 只保存最小 `entry_requirements`：当前Profile真正要求进入时已经 active/completed、炉石位于何处、哪些飞行点必须已开。这里的任务/飞行点数组是**必须满足的下界要求**，不是角色全部任务栏/全部飞行点快照，也不复制与本Profile无关但仍被整套Program携带的状态。
- Profile 不保存 `exit_state_contract`。出口状态由唯一 Route Replay 使用“Program/冷启动实际入口状态 + Profile actions”确定性重放得到；Stage 4 直接把这个 fresh 输出传给下一个Profile并核其 `entry_requirements`。禁止再维护第二份人工出口数组。

单Profile脱离Program冷启动时，`entry_requirements`只能证明最低要求，不能证明未声明状态为空；依赖“某任务必须不存在/某飞行点一定没开/任务栏仍有容量”等否定事实时继续显式UNKNOWN，由CURRENT或其它合法运行时输入补齐。未满级路线若真实需要等级/经验基线，仍只按XP owner定义的机器输入接入，不在Profile另建经验状态。

不要预先建设庞大RouteState；大部分中间状态由Profile actions从实际入口状态重新Replay。新增Profile入口要求字段必须由真实跨Profile需求触发，并进入Route Replay/Cross-Profile Continuity唯一机器合同。人类subtitle/goal中的“约67→68”“已经开过某点”等文字不能代替机器状态。

## 7. CURRENT 不是第二路线真源

CURRENT 只是某一批角色在某 Profile 上的运行时 overlay，记录当前 step/action、暂停、异常和现场状态；不复制整条正式路线。

## 8. Generated Product 的身份

Generated Product是由Task Card、Route Profile（跨Profile时加Route Program上下文）、Rules/Models、匹配Observations与UI输入派生出的可删除重建结果。

`workbench-routes.json`、Derived结果、Publisher payload、HTML/player-view都属于Generated Product；它们不能反向成为Task Card、Route Profile、Program、Timing/XP/Economy或RouteState的业务真源。

Generated Product的生命周期传播也由本owner负责：先从实际改动的真源/owner开始，只沿直接消费者向下刷新；每层都用当前输入重新计算并覆盖旧派生结果，禁止靠旧fingerprint结果跳过真实受影响层，也禁止为了省事默认全量重跑。具体领域内部怎么重建由该领域owner自己的“正式操作”章节负责。

## 9. 最小机械验收

- Profile ID/scope 唯一；
- task 引用只用稳定 ID；
- 任务动作结构化；
- Profile 不复制 Task Card 事实；
- stepGroups 覆盖动作且保持顺序；
- 条件使用普通 action + `when`；
- Profile `entry_requirements`只表达最低进入条件，Program `entry_state_contract`表达整链真实起点，Profile exit只由唯一Replay派生且可被下一Profile要求机械核验；
- 完整中文动作句不作为路线真源；
- task_id → Profile，以及profile_id → Route Program的反向索引可机械生成；
- 修改一个 Profile 不直接复制修改到其它 Profile或Program内容；
- 多Profile整链执行顺序来自Route Program，不从`display.order`或workbench数组顺序推断；
- Generated Product最终可删除重建。

## 10. 正式生命周期操作

### Route Replay / Program Continuity

- 单Profile的actions、entry requirements或相关任务可用性变化：`python3 scripts/build_route_replay.py <profile_id>`。
- Program成员顺序、Program version或真实entry state变化，或不存在合法continuity基线：`python3 scripts/build_program_continuity.py <program_id>`。
- 仅某成员Replay/Availability变化且Program基线合法：`python3 scripts/update_program_continuity_from_member.py <program_id> <profile_id>`，只向后传播到新RouteState重新与旧结果收敛的位置。
- `scripts/rebuild_route_profile.py`只用于显式完整诊断/迁移验收，不是普通修改入口。

### 跨owner传播

1. 先修改SOP命中的唯一真源/owner。
2. 只刷新真实受影响的直接消费者；消费者是否受影响由其owner契约判断。
3. Program成员变化时优先使用各owner的成员增量入口；Program合同本身变化才建立完整Program基线。
4. Display/Publisher/Assets只消费fresh上游，不得从HTML或旧Generated Product反推业务。
5. 需要项目级正式切换时最后进入`route-lifecycle-final-audit.md`。
6. 测试范围按`../../tests/README.md`选择，不把全量测试当传播规则。

## 11. 不负责

- 信息/变更分类：`../verified-routes/ROUTE-DESIGN-PROCESS.md`；
- 工作区级文档治理：工作区根`/Users/chat/claude/CLAUDE.md`；
- Task Card 字段：`../task-library/README.md`；
- Task Mechanics：`execution-and-mechanics.md`；
- Selection：`leveling-and-selection.md`；
- XP/Timing/Economy：各模型 owner；
- 路线排序：`route-atlas-optimization.md`；
- 路线动作中文转换：`route-atlas-route-display.md`；
- 标签/备注：`route-atlas-task-presentation.md`；
- 页面工程：`route-atlas-ui-and-assets.md`。
