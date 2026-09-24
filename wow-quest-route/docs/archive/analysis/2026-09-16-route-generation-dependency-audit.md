# Route Atlas 新架构生成依赖审计（2026-09-16）

用途：记录当前架构迁移阶段对“路线真源改变后，哪些结构/算法/页面必须联动”的实现审计证据。永久工作流归 `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`；各业务公式仍归各自 rules owner。本文不是第二规则 owner。

## 1. 结论

此前的“14/14 candidate 与旧 workbench 字段一致”只能证明**迁移保真**，不能证明新架构已经闭环。当前实现已经完成 Task Card / Route Profile / Presentation / 地图点线的一部分单向投影，但 Timing、XP阶段模型、RouteState审计、任务日志、经济/Gh、旧消费者退役、派生物 stale/rebuild 仍未全部切到新真源。因此正式 Publisher 不能切换。

最终不能把“路线”理解为一个包含所有任务事实的大 JSON。规范化根真源是：

- Task Card：任务本身事实，稳定 `task_id`；
- Route Profile：一段路线选择哪些任务、动作顺序、步骤、真实地点/movement和状态合同；
- Route Program：多Profile完整执行方案的严格`profile_ids`顺序、Program目标/起始状态；不复制成员Profile内部路线；
- Rules/Models：Timing、XP、Economy、Selection、Optimization 等通用算法；
- Observations：实跑样本/历史证据；
- Route UI / Map Assets：纯视觉标签与地图资源；
- CURRENT：当前角色 runtime overlay，执行属于Program时同时绑定Program版本。

单段最终路线由 Route Profile 作为**路线决策根**引用 Task Cards；多段完整方案再由Route Program组合Profiles。二者经同一SOP派生链生成，不把 Task Card 内容复制进 Route Profile，也不拿`display.order`代替业务Profile顺序。

## 2. 当前规模与已成立部分

当前 `data/route-profiles/` 有 14 个 Profile，合计 1180 个 task 引用、4966 个动作、341 个玩家步骤、1472 个结构化 location。`data/route-ui/` 有 14 份 UI 配置。

已经真实成立的联动：

1. Task Card `identity.name_zhcn` → Publisher 动作任务名。Profile只持 `task_id`，因此改任务名会更新所有玩家可见任务名，但不会改变点位。
2. Task Card `fivebox/presentation` → Task Presentation → HUD 标签/备注。
3. Route Profile `actions + geometry.locations` → Publisher `points` / step actions。
4. 页面 JS 按 Publisher `points` 顺序连接相邻点；因此 Profile 地点顺序/坐标变化后，地图线和当前 step 高亮可重建。
5. Route UI → 悬浮中文地图标签；标签视觉坐标不是真实路线坐标，继续保留旧版设计位置。

以上只证明 Display/Presentation/部分 Geometry 已从新真源长出来。

## 3. 当前未闭合或错误耦合

### 3.1 Timing 仍是旧快照，不是 Derived Timing

1082 张 Task Card 的 `timing_rule_ref` 当前全部为 `null`。现有 `data/route-models/*-timing.json` 是从旧 `workbench-routes.json` 的 step/route 时间迁出的兼容快照；`lib/route_publisher.py` 直接读取这些文件，并允许旧 `display_badge` 原文覆盖现场生成值。

因此现在修改 Profile 顺序/交通/几何后，地图可能更新而时间仍保留旧路线数值。当前没有：

- Task Card / Profile / Model / Observation / Leatrix 输入 hash；
- stale 判定；
- 统一 Derived Timing builder；
- 受影响窗口重算；
- Publisher 对过期时间的拒绝门禁。

### 3.2 交通存在双真源

当前 Profile 同时存在：

- 动作级 `taxi / use_hearth / fixed_transport / quest_transport / move ...`；
- `geometry.locations[*].transport = ride/fly/swim/script/taxi/hearth/crossmap`。

真实数据中已出现同一点两边语义不一致，例如 taxi action 对应 location transport 为 `ride/crossmap`、fixed transport 对应 `ride/taxi`。若地图线样式读 location transport、Timing/RouteState读 action，就会产生分叉。

正式结构必须只有一个 canonical movement/transport edge truth；其它表现必须由它派生。具体 schema 在完成实际案例分类前不在本文拍板。

### 3.3 Background / shared-service 语义不能从现有动作稳定恢复

已发现多种真实路线决策无法只用 `accept -> objective -> turnin` 表达，例如：

- 《赞加沼泽的植物》：接取后跨多个区域自然累计，不专门刷；满足条件才在后续Hub交付；
- 《成熟的孢子》：沿主体北线背景采集；
- 《热情的欢迎》：跨多处泵区自然累计；
- 《猎人的挑战》：其它狩猎任务中的击杀自然累计，独立服务时间为0；
- 《远古的圣物》《等肉下锅》等：在一个动作窗口内持续背景服务，最后只补缺口。

这些信息会改变边际Timing、Target Cluster/Background Layer和Selection成本。如果不能从其它稳定结构机械重建，就需要一个**通用的服务覆盖/背景窗口语义**，而不是为每个旧备注造字段。需先把全部实例分类后再冻结最小 schema。

### 3.4 旧 Generated Product 仍被大量反向当输入

静态扫描发现仍有 35 个 scripts/libs 引用 `workbench-routes.json`。其中包括现役/待迁的 Timing、XP、RouteState、player-view、各地图旧 builder/audit。正式切换后 `workbench-routes.json` 必须只作为 Publisher 生成物，不能再被业务模型反向消费。

重点债务：

- `estimate_route_atlas_timing.py`：读旧 workbench、旧 fivebox、foundation，并含大量 task-name/route-specific override；应由通用 Timing Rule Registry + Task Card refs + Profile + Observations + Leatrix 取代。
- `audit_route_atlas_flight_state.py`：从旧 point 中文/transport 猜飞行点和系统飞行；应直接 replay `open_flight_point/taxi` 原子。
- `audit_icecrown_structured_candidate.py`：从 `actionHtml` 正则反推接交与任务日志；应直接用 Profile actions + `lib/quest_log_counter.py`。
- `build_northrend_68_80_time_xp_model.py`：读旧 workbench/foundation；应消费统一 XP/Timing 派生层。
- `build_daily_task_timing_samples.py`：用任务中文名搜索旧 route 文本判断路线归属；应使用 task_id → Profile 反向索引。
- `export_route_atlas_player_view.py`：直接读旧 workbench；应消费统一 Publisher 输出。
- `build_route_atlas_workbench.py`：仍含硬编码 prototype/特定 step semantic fallback；最终必须只做 UI shell，不拥有业务文案。

### 3.5 Observations/CURRENT 缺版本绑定门禁

`route-timing-runs.json` 仍主要使用旧 `route_key + step文本/编号` 描述范围。Profile结构改变后，历史样本仍应保存，但不能无条件校准新路线。目标要求每条可参与模型的Observation至少能绑定：

`profile_id + profile_version + action/step range + source precision`

跨Profile样本还需要`program_id + program_version + profile/action边界`。CURRENT同理必须引用当前Profile/version/action位置；执行属于Program时同时绑定Program版本。Profile/Program重大改版时应显式迁移恢复点，而不是按旧step编号或display顺序静默继续。

## 4. 目标生成DAG

### 4.1 根真源/配置

A. Task Cards
- identity
- availability/dependencies
- rewards/XP基础事实
- guide/fivebox
- `timing_rule_ref`
- presentation

B. Route Profile
- scope / goal / version
- task set
- route actions + strict order
- step groups
- canonical route geometry/movement semantics
- entry/exit state
- 经审计证明无法从原子重建的通用 route-only service semantics

C. Route Program（跨Profile完整方案时）
- program scope / goal / version / status
- 严格有序profile_ids
- Program级最小起始状态
- 不复制成员Profile内部路线

D. 通用模型/参数
- Timing Rule Registry + profile/global calibration params
- XP model params
- Economy policy
- Leatrix-derived taxi table

E. Evidence/Observations
- Timing observations
- Journey/live samples
- 其它不会直接成为路线真源的实跑证据

F. Route UI / Map Assets
- 悬浮中文标签视觉坐标
- 地图资源/CSS等纯显示配置

G. CURRENT runtime overlay
- 当前执行位置/角色状态/暂停异常
- 在Route Program中执行时绑定program/profile版本与当前位置

### 4.2 决策层，不是静默派生层

- Task Selection：消费Rewards + Derived XP + Derived Timing/Economy + Availability；只在触发条件成立时产生 now/later/never review，不自动删任务。
- Route Optimization：消费Task Cards、RouteState、Timing/XP成本和空间结构；产出/修改 Route Profile 候选。事实变化可以使当前Profile“需复核”，但不能静默重排冻结路线。

### 4.3 可删除重建的派生层

完整执行顺序已经收口到唯一Lifecycle SOP §1.4.1，本文不再维护第二套不同编号。审计确认的14层是：

1. Dependency / Input Fingerprint（含`task_id → profiles`、`profile_id → programs`）；
2. Profile / Route Program Contract Validation；
3. Availability + Route Replay / State Timeline；
4. Cross-Profile Continuity；
5. Canonical Spatial / Movement Timeline；
6. Service Context；
7. Timing Input Resolution + Derived Timing；
8. Derived XP / Level Timeline；
9. Derived Economy / G-hour；
10. Review Trigger Gate；
11. Route Display + Task Presentation；
12. Publisher Payload；
13. HTML / Player View / Offline Assets；
14. Mechanical Audits + Player Cold Read。

关键身份不变量：1—10的可重建结果/诊断都不能反向成为Task Card/Profile/Program真源；Selection/Optimization产生的是review/候选决策，不得在rebuild中静默改正式路线；11—14只消费fresh上游，不从最终HTML反推业务事实。

## 5. 字段级影响矩阵

| 变化 | 必须失效/重建 | 明确不应变化 |
| --- | --- | --- |
| Task Card `identity.name_*` | Display/Presentation → Publisher/HTML/player-view | Profile顺序、坐标、Timing、XP、Economy |
| Task Card availability/前置/隐藏门槛 | Route legality/Availability、受影响Profile review；必要时Selection/Optimization候选 | 不自动改Profile |
| Task Card rewards | Economy/Gh；可能触发Selection Review | 地图点线、任务动作顺序 |
| Task Card `timing_rule_ref`或Timing模型输入事实 | Derived Timing → Gh → Optimization软成本/Selection触发 → Publisher时间 | 不直接改Profile |
| Task Card fivebox | Presentation；若真正影响耗时，必须另外修改`timing_rule_ref`/Timing输入 | 不允许Timing从fivebox标签猜公式 |
| Task Card presentation | Presentation → Publisher/HTML | Profile/Timing/XP/Economy |
| Profile task set | State/quest log/availability/timing/xp/economy/display/map/Publisher；Selection+Optimization流程 | Task Card事实 |
| Profile accept/objective/turnin顺序 | State/quest log/turnin XP时点/timing/economy/display/step映射；必要时flight/hearth状态 | Task Card事实 |
| Profile地点/坐标/空间归属 | Geometry点线 + movement Timing + Display；若改变服务重叠则Service Context/Timing/Optimization | Task Card名字/奖励 |
| Profile交通/炉石/飞行点 | RouteState合法性 + movement edge + map styling + Timing + badge | Task Card事实 |
| Profile stepGroups | step聚合/step Timing/HUD/玩家步骤 | 底层动作顺序/任务事实；除非同时改动作 |
| Profile entry/exit state | Route replay/跨Profile合同/飞行与炉石合法性/Timing | Task Card事实 |
| Route Program profile_ids/顺序/entry | Cross-Profile Continuity、整链XP/Timing/Economy/Gh、Program级CURRENT/Observation适用性 | 不自动修改成员Profile内部动作/任务事实 |
| Leatrix taxi表 | 使用相关taxi edge的Timing → route Timing/Gh/badge | Profile顺序、地图标签 |
| Timing通用参数/规则 | 引用规则的任务/Profile Derived Timing → Gh/相关review | Task Card任务事实 |
| XP参数/规则 | Derived XP → gate/Selection review | Profile不自动重排 |
| Timing Observation | 对匹配profile/version/range的校准结果 | 不修改Task Card/Profile；不匹配版本则只留历史 |
| Route UI/map label | Publisher/HTML视觉 | Profile geometry/Timing |
| CURRENT | runtime resume/局部剩余成本 | 不修改正式Profile，除非反馈升级为TASK_FACT/PROFILE变更 |

关键例子：修改 Task Card 里的任务名只应改玩家文字；如果因为事实修正发现任务实际服务地点错了，则那不是“名字带动点位”，而是一个独立 `PROFILE_STEPS/geometry` 或 Optimization 变更，随后地图/Timing等按本表传播。

## 6. 单一真源门禁

正式切换前必须清零以下双写/反向推导：

1. 交通模式不能同时由 action 和 location.transport 独立维护。
2. `display_badge`不能保存旧页面整段字符串作为运行真值。
3. step/route timing不能人工同时存在于Profile旁边的兼容快照和Derived Timing。
4. 任务日志/飞行点/接交合法性不能从`actionHtml`或中文point文本反解析。
5. 玩家备注/共享状态不能从旧fivebox自然语言反推。
6. 经济/XP模型不能从旧workbench任务名顺序反推ID。
7. `workbench-routes.json`/HTML不得再作为业务上游输入。
8. 多Profile业务顺序只能来自Route Program；`display.order`/workbench数组顺序只能是展示projection。
9. 迁移脚本中的route-specific skip/正则仅允许用于一次性Importer，切消费者后退出运行链。

## 7. 正式切换退出条件

只有同时满足以下条件才重新进入Publisher最终替代验收：

- 所有14个Profile的派生链从新根真源可删除重建；
- 所有需要跨Profile连续执行的正式方案都有Route Program真源，Program顺序/entry可机械验证，`display.order`不再承担业务顺序；
- Derived Timing不是旧step快照，且Publisher拒绝stale结果；
- XP/Economy/quest-log/flight-state等现役消费者不再依赖旧workbench文字；
- canonical movement/transport真源唯一；
- 所有不能派生的Background/Spatial语义已经以通用结构闭合，或明确标UNKNOWN阻止可信模型输出；
- Generated Products删除后可由同一入口重建；
- 旧builder/semantic/prototype/fallback不再注入业务语义；
- 机械全量验收通过后，再从最终HTML逐Profile人工冷读；
- 备注内容优化仍排在整套路线生成链稳定之后。

## 8. SOP完整性审计后的唯一实现顺序

本审计最初的“先movement/Leatrix/Timing”顺序已经被更完整的正向+反向SOP审计取代。发现Route Program、Economy owner、Timing Input Resolution、结构化XP entry等上游缺口后，继续按旧顺序会再次制造“下游脚本先写、上游接口后补”的问题。

当前唯一实现顺序直接引用Lifecycle SOP §1.4.1 / §17：

1. Dependency / Fingerprint（同时建立`task_id → profiles`、`profile_id → programs`）；
2. Route Profile / Route Program Contract；
3. Availability / Route Replay；
4. Cross-Profile Continuity；
5. Canonical Spatial / Movement；
6. Service Context；
7. Timing Input Resolution / Derived Timing（Leatrix importer在此stage正式接入，当前提前存在但仍标“未接入”）；
8. Derived XP；
9. Derived Economy；
10. Review Trigger；
11. Display / Presentation；
12. Publisher；
13. HTML / player-view / offline assets；
14. Mechanical Audit / 玩家冷读 / 旧消费者退役。

每层只有满足SOP的stage完成定义后才进入下一层；最后再做`【需要单独修正优化】`备注专项。
