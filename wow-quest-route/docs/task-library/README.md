# Task Card：单任务事实库规范

用途：`data/task-cards/<task_id>.json`承担**单任务当前有效事实的唯一机器真源**；本README只定义这些字段的语义、三层边界和消费者。Task Card描述“这个任务本身是什么、怎么做、有哪些机制和证据”，不描述“某条路线现在要不要做、排第几步”。

机器字段名、required、枚举和`additionalProperties`等shape只以`data/task-cards/schema.json`为权威；本README中的反引号字段名必须与schema一致，不得另造一套目标字段名。旧人工表格、`data/observations/`和各地图foundation在兼容迁移期间只作为证据/旧输入，独有信息迁入Task Card前不得删除，但也不得继续作为新事实写入口。

## 1. 核心边界

### Task Card保存

- 任务身份与版本事实；
- 接取条件、直接前置与互斥关系；反向后续关系由索引派生；
- 任务目标、数量、目标实体/物品；
- 接取/目标/交付位置和隐藏地形；
- 任务物、掉落、事件、护送、载具、Boss等完整机制事实；
- 五开各阶段真实共享/个人机制；
- 完整详细攻略；
- 当前仍未确认的问题；
- 实测/资料证据、日期和置信度；
- 与路线无关的固有奖励/基础数值；
- 五开状态/标签变量与必要的人工推荐备注override；
- 可复用的任务级实测样本。

### Task Card不保存

- `必做/跳过/条件做/以后做`；
- P1/P2/P3/P4或其它路线删留优先级；
- DK/圣骑某条路线的步骤号、顺序、回访点；
- `先别交/和B一起做/做完去下一Hub`等路线指令；
- 当前角色预计交任务等级；
- 当前路线派生经验；
- 当前路线预计耗时/整图墙钟；
- 当前Route Profile的炉石/飞行点状态；
- 可以由统一机制模板自动生成的重复前端文案；
- 旧错误值作为当前字段。

一句话：**任务卡只保存任务事实；路线决策属于Route Profile/规则；派生计算属于模型。**

## 2. 稳定身份

每张卡顶层必须有`task_id`，并在`identity`中保存：

- `name_zhcn`：当前客户端完整中文名；
- `game_variant_id`：当前游戏/服务器变体稳定标识；
- `version_scope`：适用版本/服务器环境；
- `faction`：阵营限制；
- `repeatability`：一次性/可重复/日常等。

事实闭合程度不再放进identity；统一由顶层`coverage`按`availability / objectives / locations / rewards / mechanics / fivebox / guide`分别记录`unknown / partial / verified / not_applicable`。

任务中文名可修正，不能作为跨文件关联主键。同名任务、翻译更新和展示格式变化不得破坏引用。

## 3. Availability / 任务链字段

当前v1 schema中的`availability`字段为：

- `quest_level`：任务等级；
- `min_level`：最低接取等级；
- `pre_any`：直接前置中满足任一即可的集合；
- `pre_all`：必须全部满足的直接前置；
- `parent_active`：需要父任务处于活动态等关系；
- `exclusive_with`：互斥/替代可接关系；
- `required_reputation`：声望门槛对象或`null`；
- `required_class`：职业限制数组；
- `required_race`：种族限制数组；
- `required_skill`：当前已建模的技能限制数组；
- `hidden_requirements`：Questie漏记但已由实服/可靠资料确认的硬门槛。

职业技能、专业、法术等以后若出现当前真实需求，先扩展schema再使用新字段名；README不能提前声明机器契约中不存在的字段。

### 字段语义

- Task Card只保存一个权威方向的直接关系/已确认隐藏关系；反向followup与完整依赖闭包由索引/路线算法派生，不能在每张卡双写正反关系或复制整棵祖先树。
- `exclusive_with`不能解释成前置。
- 数据库“没有记录前置”只能记`unknown/no_record`，不能自动证明独立根。
- 用户实服已成功接到任务，是该时点可达性的最高优先级证据；旧隐藏前置假设必须让位。

这些字段供Route Optimization做可达性/状态传播，Task Card本身不产生“应该做/不做”结论。

## 4. Rewards / 固有奖励

Task Card保存与路线无关的原始/规范化奖励事实，例如：

- `base_xp`及来源；
- `reward_money`；
- 固定/可选奖励物品ID；
- 奖励装备基础卖店价值的权威数据引用；
- 满级XP折金计算所需的任务基础输入。

Task Card不保存：

- “角色72级交时实际获得多少XP”这种上下文派生值；
- 当前服务器倍率公式副本；
- “当前做比80后做多赚多少”这种选择结果。

经验派生统一调用`docs/rules/xp-model.md`；经济删留结论由任务选择规则计算。

## 5. Locations / 空间事实

当前v1机器字段只有顶层`locations`对象；schema暂时允许对象内部按任务需要保存结构化空间事实，但**没有**把`accept_locations / objective_locations / turnin_locations / entrance / floor / vertical_relation`等名称声明为必填机器字段。

语义上仍应区分接取、目标、交付、入口、楼层/垂直关系和路线无关地标；迁移时把这些含义放进`locations`或objective自己的`locations`，并通过`coverage.locations`标记完整度。若后续需要把某个子字段冻结为正式机器契约，先修改schema，再同步本字典。

位置数据必须绑定真实语义，不保存裸坐标而不说明“这是入口/目标/NPC/物体”。

Task Card可以保存“这个Boss在二楼”；不能保存“DK路线第8步从西边上楼”，后者属于Route Profile。

Questie平面坐标不等于真实道路/楼层；已实跑地形优先覆盖静态推断。

## 6. Objectives / 任务目标

每个目标独立结构化。当前v1 schema字段为：

- `objective_id`；
- `kind`：kill / loot / interact / use_item / escort / event / talk / explore / vehicle / other；
- `target`：对象/实体/物品等目标描述；
- `required_count`；
- `source_entities`：掉落来源/触发来源；
- `locations`；
- `mechanic_refs`：关联本卡的机制块；
- `confidence`。

多个阶段机制不同必须拆开，不能用一条`shared=true`覆盖整任务。

## 7. Mechanics / 完整机制事实

Task Card的机制字段保存**已经确认的任务本身行为**。机制类别和值域由`docs/rules/execution-and-mechanics.md`定义。

可包含：

- 掉落类型与参考掉率；
- 单尸件数；
- 固定物刷新；
- 任务物使用目标；
- 召唤/事件启动条件；
- 护送脚本；
- 载具控制；
- Boss关键技能/失败条件；
- 黄色/潜行/隐形目标的真实触发方式；
- 任务起始物掉落/右键接取；
- 等待/刷新机制；
- 洞穴/楼层/水下等执行机制。

### 不允许自由推断

例如：

- 击杀共享 ≠ 任务物共享；
- 一次事件共享 ≠ 前置收集共享；
- 同尸可多人取 ≠ 普通FFA；
- 任务完成 ≠ 机制已经观察确认。

每个事实必须有来源或明确标记unknown。

## 8. Fivebox / 五开机制

五开必须按**目标/阶段**结构化，而不是只存一段自由文本。

常见枚举语义包括但不限于：

- `shared_kill`；
- `shared_progress`；
- `personal_progress`；
- `ffa_loot_pool`；
- `same_corpse_multi_character_loot`；
- `personal_drop`；
- `party_loot`；
- `per_character_interaction`；
- `shared_interaction`；
- `per_character_item_use`；
- `shared_event`；
- `escort_party_shared`；
- `unknown`。

这些名称的严格定义由Task Mechanics维护；Task Card只记录当前任务实际属于哪一类/哪几类及证据。

复杂任务应类似：

`stage A = personal_progress`  
`stage B = shared_event`

而不是写一条模糊`mixed`后丢失细节。

## 9. Guide / 完整攻略事实

`guide`允许比玩家HUD详细很多，用来保存长期可复用的“怎么做”：

- 完整执行机制；
- 容易找错的入口/层级；
- Boss打法；
- 任务物使用；
- 事件顺序；
- 失败/重试；
- 刷新/等待；
- 新手容易误解的位置。

但`guide`必须仍然是**任务本身攻略**，不能塞当前路线编排理由。

前端绝不能简单把guide摘要后当备注。HUD显示多少统一由Task Presentation决定。

## 10. Presentation / 玩家呈现元数据

Task Card中的玩家呈现分成两部分，并与事实/攻略层独立。

### 10.1 Fivebox状态 / 标签变量

fivebox内部stage保存真实细分机制；同时保存一个面向玩家执行的结构化状态摘要，当前值域：

- `shared` → 共享
- `not_shared` → 不共享
- `sequential_loot` → 依次拾取
- `pending` → 待实测

它是Task Card机器变量，不是备注文本，也不由open question或自由文本推断。复杂任务可以有更细stage事实，但前端标签读取这个明确状态。

### 10.2 人工推荐备注

`presentation.note_override`保存用户明确确认后的玩家备注结果：

- `text`：最终备注；允许空字符串，表示“已经人工判断无需备注”；
- `scope`：`all`或确有必要的特定Route Profile/版本；
- `source_ref`：用户确认/规则来源；
- `reason`：内部说明，不显示给玩家。

**明确为空**必须与“尚未迁移/尚未判断备注”区分。

旧页面备注迁移时：事实/攻略进入Task Card facts/guide；真正有执行价值的玩家提示进入note_override；已被标签/动作/插件覆盖的内容明确判定为冗余；无法判断则交用户确认。

标签和备注是两条独立输出：共享标签不能自动生成共享长备注，备注也不能反推fivebox状态。完整规则见`docs/rules/route-atlas-task-presentation.md`。

## 11. Verification / 未闭合问题

`verification.open_questions`保存真正需要后续实跑/查证的问题。

每一项必须包括：

- `question_id`；
- 要观察的具体变量；
- 当前状态`unknown/expected`；
- 为什么无法由现有证据确认；
- 什么证据可以关闭；
- 它影响的是哪个尚未确认的事实/模型输入。

禁止只写“共享未知”。

确认后：更新当前事实字段 + 写证据 + 关闭open question。历史问题本身可以保留在evidence/correction日志。玩家是否显示“待实测”只看fivebox状态变量，不由open question存在与否决定。

## 12. Evidence / 证据与纠错

每个非数据库显然事实应可追溯：

- `source_type`：user_live / questie / local_db / public_reference / derived等；
- `source_ref`；
- `observed_at`；
- `server/version_scope`；
- `confidence`；
- `supports_fields`：这条证据支持哪些当前字段。

优先级统一由`docs/rules/README.md`定义。

### 当前值与历史错误分离

实服纠错时：

1. 当前有效字段立即改成新值；
2. 旧值、原因、日期保存到correction/evidence历史；
3. 不能为了“保留历史”让旧值继续占据当前字段；
4. 当前事实字段实际改变后，通过task_id找到引用Profile并从真源重新生成派生结果；不维护第二套字段传播分类。

## 13. Timing / 任务级时间证据

Task Card只保存可复用的任务级实测输入/样本，例如：

- 固定动画/脚本时长；
- 独立事件持续时间；
- 能与移动、Hub、其它任务完全隔离的单任务服务样本；
- 刷新等待样本；
- 掉率/击杀样本。

不保存：

- 多任务/step/地图/整段路线共同产生的实跑墙钟（进入Timing Observations）；
- 某条路线当前“这个任务=7.2分钟”的最终派生结果；
- 整个Hub共享移动/接交成本；
- 当前Profile的地图总时间。

统一墙钟计算见`timing-and-benchmarking.md`。

## 14. 可复用关系与派生关系

Task Card只保存**不能由更基础字段稳定推导**、且确实属于任务本身的关系事实。

例如直接前置与互斥关系由Availability权威字段保存；反向后续关系、接取NPC相同、目标实体相同、所需物品相同等都应由基础字段/实体ID自动派生，不再手工双写镜像字段。

只有数据库无法表达、但经实测确认且跨Route Profile稳定成立的关系，才允许作为显式typed relation保存，并必须说明不能从哪些现有字段推导。

禁止保存“当前路线顺路”“这次和B一起做”这类上下文判断。Route Optimization根据Task Card基础事实和当前Route Profile动态计算任务簇/空间重叠。

## 15. 消费者与重新生成

Task Card不维护`x-impact`或其它字段级传播分类。

当前事实变化后：

1. 用稳定task_id反向索引找到引用它的现役/可复用Route Profile；
2. Route Profile路线决策本身不自动改变；
3. Task Presentation、Timing、XP、Availability等消费者各自重新读取当前Task Card并生成结果；
4. 若新派生结果满足Selection触发条件，再进入Selection Review。

字段字典只定义“这个字段是什么、谁可以读它”，不再定义第二套“改它以后通知谁”的业务表。

## 16. 数据写入原则

最终结构化Task Card应成为Builder的规范输入；人类Markdown可以作为说明/视图，但不能与机器卡片分别维护同一事实。

迁移完成前：

- 旧task-library Markdown；
- `fivebox-task-types.json`；
- 地图foundation/semantic脚本；

仍可能含独有事实，必须先迁入、对账、切消费者，再禁止旧写入/归档。

任何迁移都遵循：

`迁入 → 对账 → 切消费者 → 禁止旧写入 → 退役旧源`

禁止先删旧源再补Task Card。

## 17. Task Card发布/修改验收

单任务事实修改只验证受影响契约：

- schema合法；
- 当前字段与证据一致；
- 没有路线决策字段泄漏；
- 所有引用Route Profile能通过task_id反向索引正确识别；
- 当前消费者从新事实重新生成结果，不解析旧备注/guide反推事实；
- 与本次无关的其它地图/路线不因为“保险”被重算。

整条路线发布验收不属于本README，统一由Route Lifecycle SOP编排。
