# 任务选择与剔除决策规则

用途：这是项目中**“什么时候需要重新评估一个任务/任务包，以及在`现在做 / 以后做 / 永久不做`之间如何决策”**的唯一规则owner。

本文件只负责决策，不负责：任务事实、XP公式、墙钟公式、路线排序或玩家前端。任务事实读Task Card；经验值读`xp-model.md`；时间成本读`timing-and-benchmarking.md`；已经决定做的任务如何编排读`route-atlas-optimization.md`。

## 1. 默认状态：不是每个任务都重新做一次经济学证明

任务已经属于成熟、连续、可复用的正式Route Profile时，默认保持现有选择。

只有出现下列**触发事件**之一，才启动正式任务选择评估：

1. `user_selection_request`：用户明确要求删任务、补任务、比较任务价值；
2. `task_fact_cost_or_benefit_changed`：Task Card事实变化导致成本/收益明显改变，例如共享→个人、掉率/刷新、前置/奖励被修正；
3. `live_run_cost_or_variance_anomaly`：实跑证明某任务出现异常长尾、独立折返、失败重跑或高切号成本；
4. `route_overlap_structure_changed`：路线结构变化使某任务从高度重叠变成独立偏移，或反过来；
5. `xp_gap_or_redundancy`：未满级路线出现确定经验缺口/明显经验冗余，需要补任务或从后段裁任务；
6. `availability_changed`：任务因Availability变化变得不可达/重新可达；
7. `profile_goal_or_scope_changed`：用户改变当前Route Profile的目标/scope；
8. `recalled_or_new_task`：新任务/遗漏任务被召回，需要判断是否进入正式路线。

以上反引号标识是Stage 10 Review Trigger的稳定机器ID；`data/review-trigger/model-config.json`只允许作为这些owner条目的机器投影/校验表，不拥有独立业务语义，修改触发条件必须先改本owner并同步契约测试。机器层只判断“是否进入Selection Review”，不得把触发器直接解释成`now/later/never`结论。

没有触发器时，不为了“理论最优”逐任务反复重算已经验证的路线。

### 日常任务在一次性主路线中的口径

`repeatability=daily`本身不是删除条件。一次性主路线只排除“已经完成首轮后，为每日重复收益再次接/做/交”的重复执行；如果某个日常在新角色首次跑图时会解锁后续一次性任务、承担链路前置，或已被正式路线选择为首次经过必做的一次执行，则该首次执行必须保留。不得因为任务被标记为daily就机械删除其首轮动作，也不得把同一日常的后续重复接取混进一次性主路线。

## 2. 决策对象：任务包优先于孤立单任务

正式比较的最小单位是**真实边际成本可独立变化的任务或任务包**。

多个任务若共享：

- 同一转场；
- 同一Hub接交；
- 同一批怪；
- 同一洞穴/事件；
- 同一回访；

必须作为组合比较，不能把公共成本给每个任务各收一次。

只有某个任务可以独立增删且不会改变其它任务的路线/状态时，才做单任务决策。

## 3. 三个标准动作

一旦触发正式选择，至少比较：

### `now`：现在做

计算：

- 当前直接金币；
- 物品/装备变现；
- 当前实际交付等级的任务经验；
- 对后续可接性/等级门槛的价值；
- 后续任务链价值；
- 当前路线中的真实新增墙钟；
- 当前可共享的移动/Hub/战斗成本；
- 五开切号、失败、随机长尾等执行风险。

### `later`：以后做

例如80级后回图：

- 未来直接金币/物品价值；
- 满级XP折金或届时实际经验收益；
- 未来重新回图、定位、重新进入洞穴/Hub、重新接交的墙钟；
- 任务链是否仍可兑现；
- 当前跳过后对未满级阶段门槛的影响。

### `never`：永久不做

计算：

- 节省的当前和未来墙钟；
- 损失的任务金币/装备/物品；
- 损失的任务经验/满级XP折金；
- 被切断的后续任务链；
- 对后续Route Profile状态/Availability的影响。

不能只做“做 / 删”二选一而忽略延后价值。

## 4. 统一目标函数

所有选择服从项目第一目标：

**这一种任务打金方式自身的长期可重复净金币 / 玩家真实墙钟。**

其中：

- 任务金币、装备/物品变现、满级XP折金属于分子；
- 移动、战斗、交互、等待、失败重跑、切号和重新回图属于分母/执行成本；
- 经验在未满级阶段是状态变量：它决定后续任务何时可接、何时进入满级XP折金阶段；
- 认知复杂度/高方差若不能可靠折成秒数，可作为同收益方案的稳定性硬约束/次级判据。

禁止把团本、日常等其它独立打金方式的G/小时作为“省5分钟就能去别处赚钱”的单任务机会成本，除非用户明确要求跨打金方式分配总游戏时间。

## 5. 必须使用真实边际成本

选择时调用Timing Model计算**当前Route Profile中的新增/减少墙钟**，不能拿Task Card某个独立样本直接当最终边际时间。

### 沉没成本

已经支付的成本不重新计入：

- 已完成的前置；
- 已经拿到的稀有触发物；
- 已经发生的接取/转场；
- 已经完成的共享击杀/收集进度。

只比较从当前状态开始的剩余成本。

### 公共成本

同一任务包共享：

- 地图进入；
- 公共骑行；
- Hub接交；
- 重叠击杀；
- 事件/洞穴进入；
- 回城/离图。

不能重复收费。

## 6. 未满级选择必须做经验闭合

未满级时，Selection调用`xp-model.md`，而不是自己实现经验公式。

如果`never`或`later`会造成下一硬门槛经验不足：

1. 明确缺多少保证经验；
2. 指定实际可能补入的任务/任务包；
3. 比较补入方案的真实墙钟和路线影响；
4. 把原方案和替代方案推到同一个后续里程碑再比较。

不能把“删掉这个任务省5分钟”当结论，却把后面为了补经验新增的15分钟忽略。

如果前段新增了高效率真实经验，优先从**尚未开始的后段任务**中触发Selection Review，而不是机械让整条路线永久堆积经验冗余。

已经满级时，不为了“补经验”虚构替代任务；直接比较金币、XP折金、后续链和墙钟。

## 7. 后续链/Availability必须计入选择

任务卡中的直接前后置、Availability由Route Optimization计算可达闭包。

准备删除根任务时必须检查：

- 哪些后续只依赖它；
- 哪些后续仍有其它`pre_any`路径；
- 是否存在面包屑/入口任务而非硬前置；
- 用户实服是否已经证明某后续可达。

Selection比较的是**整个实际受影响任务包**，不能只看根任务本身的金币/分钟。

删除决策不得直接写回Task Card。它只属于对应Route Profile/决策记录。

## 8. 随机掉落、固定物、护送不是删留规则

任务类型只是成本输入，不是决策。

### 随机掉落

需要Timing消费：

- Task Card真实掉率；
- 密度；
- Fivebox拾取类型；
- 与其它任务重叠；
- 刷新/竞争；
- 实跑方差。

低掉率可以触发Selection Review，但不能自动`never`。

### 固定物/逐号交互

无随机掉率长尾；按真实交互次数、刷新周期、路线偏移和切号成本计算。不能因为“不共享”自动降级。

### 护送/事件/载具

按真实脚本新增墙钟、失败重跑、与主路线重叠及Fivebox机制计算。不能按任务类型自动排除。

## 9. 交通/空间重叠由Route Optimization提供

Selection不自己决定：

- 地图轴；
- Target Cluster顺序；
- Hub聚合；
- 炉石位置；
- 飞行点；
- 任务应该插在哪一步。

它只消费Route Optimization给出的当前/替代路线边际成本。

如果Selection结果改变了任务集合，再由Route Optimization重排受影响窗口。

## 10. 决策输出

一次Selection Review至少产生：

- `decision_scope`：哪个Route Profile/窗口；
- `candidate_tasks`：稳定任务ID；
- `actions_compared`：now/later/never中实际比较了哪些；
- `inputs`：XP模型版本、Timing模型版本、Task Card版本/事实；
- `decision`；
- `reason_summary`：内部简短理由；
- `affected_followups`；
- `replacement_if_needed`；
- `needs_route_rebuild`；
- `confidence`。

输出进入Route Profile决策/analysis，不进入Task Card，也不进入玩家HTML。

## 11. 旧P1—P4 / A—C标签

历史P级曾作为高操作/低收益任务的初筛工具，但它**不是当前正式删留权威**。

治理后的处理原则：

- 历史标签可留在archive/analysis解释旧选择；
- 如果未来仍需要机器做“先看哪些任务”的预筛，可重新定义为**可派生的非权威候选标签**；
- 任何标签都不能直接改变Route Profile；
- 不把P级复制进Task Card固有事实；
- 旧P级脚本/删除结论不得进入现役Builder默认链。

本次架构治理不重新优化P级算法，只取消它作为长期正式决策规则的地位。

## 12. Selection如何被其它变化触发

本文件只拥有第1节的**Selection触发条件**，不维护另一套字段传播分类。

Task Card、Route Profile或公共模型变化后，先从当前真源重新生成对应Profile的XP/Timing/Availability等派生结果；只有新结果满足第1节触发条件时，才进入Selection Review。

因此：

- Selection不会因某个字段变化自动删除任务；
- 它只消费重新计算后的当前结果；
- task_id反向索引只负责找到引用该任务的Profile，不定义新的业务语义；
- 是否需要重新比较now/later/never由本文件的触发条件决定。

## 13. 正式Selection Review操作

Selection本身只做业务裁决；Review Trigger只是把当前fresh派生状态机械转换为“是否需要进入Selection/Optimization人工复审”的信号：

- Program上下文：`python3 scripts/build_route_review_trigger.py program <program_id>`
- 独立Profile：`python3 scripts/build_route_review_trigger.py profile <profile_id>`

触发结果不能自动写`now/later/never`。用户/规则完成Selection裁决后，任务集合变化写回Route Profile，再按`route-profile-and-lifecycle.md`刷新真实下游。

## 14. 本文件明确不负责

- Task Card事实与字段：`docs/task-library/README.md`；
- 任务机制分类：`execution-and-mechanics.md`；
- XP公式：`xp-model.md`；
- 时间公式：`timing-and-benchmarking.md`；
- 路线顺序/交通/聚类：`route-atlas-optimization.md`；
- Route Atlas文案：`route-atlas-player-contract.md`及其子owner；
- 输入是否属于任务删留/恢复决策由分类SOP判断；Selection裁决后的跨owner传播读`route-profile-and-lifecycle.md`，测试只读`../../tests/README.md`。
