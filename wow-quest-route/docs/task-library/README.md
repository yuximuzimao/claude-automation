# Task Card：单任务事实库规范

用途：`data/task-cards/<task_id>.json`承担**单任务当前有效事实的唯一机器真源**。Task Card回答“这个任务是什么、怎么做、五开总体怎么执行、当前玩家页显示什么备注”；它不保存某条路线的顺序和路线决策。

机器字段名、required、枚举和值域只以`data/task-cards/schema.json`为权威。本文件解释字段语义和归属，不另造第二套字段。

## 1. 核心原则

一张Task Card对应一个稳定`task_id`。

旧信息迁移时，以**单个task_id为处理单位**：先收集这个任务在Questie/foundation、旧fivebox、旧路线备注、semantic脚本、Journey实测等来源中的信息，再逐条归入本卡、Route Profile、Timing Observation或History/Evidence。不能用一套自然语言规则批量猜一千多个任务的语义。

批量程序只允许承担：

- 按task_id收集候选资料；
- 搬运无歧义的数据库基础字段；
- schema校验；
- 找出未归属/冲突信息。

任务攻略、特殊五开执行方式和旧备注的语义判断必须逐task_id处理。

## 2. Task Card保存什么

### 2.1 稳定身份 `identity`

保存：

- `name_zhcn`：当前客户端完整中文名；
- `name_en`：英文名，可为空；
- `game_variant_id`：当前游戏/服务器变体；
- `version_scope`：适用版本；
- `faction`：阵营限制；
- `repeatability`：一次性/日常/可重复/未知。

中文任务名不是跨文件关联主键。Route Profile和所有机器引用都使用`task_id`。

### 2.2 接取条件 `availability`

只保存适合稳定结构化、并且路线算法确实需要读取的基础条件：

- `quest_level`；
- `min_level`；
- `pre_any`；
- `pre_all`；
- `parent_active`；
- `exclusive_with`；
- 声望、职业、种族、技能限制；
- 已确认的隐藏硬门槛。

前置只保存权威方向。反向后续关系由索引根据所有Task Card派生，不在每张卡双写。

### 2.3 固有奖励 `rewards`

保存任务本身的原始奖励事实，例如：

- `full_xp`：Questie记录的完整基础任务XP；
- `reward_money_copper`：任务直接金币；
- `fixed_items`：固定奖励物，保存item_id、数量、中英文名、单件/合计卖店价；
- `choice_items_desc_by_sell`：可选奖励物，保存同样的原始字段并按合计卖店价降序，方便直接知道应选哪件卖店；
- `reputation_rewards`：Questie记录的声望奖励；
- `gear_sale_max_copper`等字段是上述稳定奖励事实的确定性汇总，方便金币模型消费。

精确金币/物品卖店价以AzerothCore WotLK `quest_template + item_template`为机器来源，中文物品名/XP/声望由当前Questie补充。`scripts/enrich_task_card_rewards.py <task_id>`只处理一张Task Card；旧`data/route-atlas/quest-reward-economy.json`仅保留为历史迁移证据，原writer已硬退役，不得重建或作为单任务/路线经济真源。

不保存“当前72级交能拿多少XP”“80级做更赚多少”等上下文派生结果；它们属于XP/Selection模型。

### 2.4 完整攻略事实 `guide`

`guide`是一张卡中任务知识的完整事实层。**任务目标、NPC/入口/楼层、任务物、Boss机制、掉落方式、事件、载具、护送、刷新、五开特殊细节等都统一进入这里，不再拆成objectives/mechanics/stages多套结构。**

典型内容包括：

- Questie已有的任务目标，例如杀多少怪、收集多少物品；
- 接取/交付NPC、洞穴入口、二楼/水下/悬崖等空间事实；
- 任务物如何获得和使用；
- Boss关键机制、召唤/事件顺序、失败/重试条件；
- 固定物刷新、特殊掉落、护送/载具操作；
- 五开执行中无法由一个总体状态表达的细节。

这里允许完整、详细。它是长期知识，不等于玩家HUD备注。

不得写入：

- “DK路线第8步”；
- “这条路线先A后B”；
- “当前为了省时间跳过”；
- “做完去下一Hub”；
- 其它只在某条Route Profile中成立的编排决定。

这些属于Route Profile。

## 3. Fivebox：只保存总体执行分类

`fivebox.status`只承担一个职责：给五开执行和玩家标签提供**粗粒度、明确、稳定**的总体分类。

当前只有五类：

- `shared` → 共享；
- `not_shared` → 不共享；
- `sequential_loot` → 依次拾取；
- `special` → 特殊；
- `pending` → 待实测。

### 3.1 分类边界

`shared`：整体可以按共享任务执行，不存在需要玩家额外理解的关键个人阶段。

`not_shared`：总体上必须按个人任务处理。

`sequential_loot`：同一尸体/同一来源可以让多角色依次拾取，且这种执行方式本身是稳定、常见、足以独立成类的机制。

`special`：一个简单“共享/不共享”标签不足以正确执行。例如：

- 击杀共享，但关键任务物个人；
- 前一部分个人、后一部分共享；
- 必须保持距离才共享；
- 某个交互后队伍同步；
- 其它需要看`guide`才能正确执行的混合/条件机制。

`pending`：现有证据不能确认总体五开分类。无需另外建立“五开open question”机器层；后续实测确认后直接修改status，并把可靠事实补进guide/evidence。

### 3.2 不再建立stage分类

Task Card不再保存`fivebox.stages`，也不为了时间模型把一个任务拆成多个fivebox阶段。

例如《阻断援军》只需要：

- `fivebox.status = special`；
- `guide`写清“符文石个人拾取；五号达标后再走；炸门共享，主控完成即可”。

如果需要回答“任务怎么五开”，读取guide；如果只需要前端标签，读取status。

## 4. 玩家备注 `presentation`

完整攻略和玩家备注是两层。

迁移旧正式页面时，**先无损保存当前已经存在的备注**到`presentation.note_override`。这些备注大量经过用户实跑修改，迁移阶段不重新拆句、不重新总结、不擅自删除。

以后进行备注专项审计时，再逐条或小批量判断：

- 是否已经被共享标签覆盖；
- 是否只是攻略事实、前端无需显示；
- 是否仍然是执行时必需的最短提醒；
- 是否应明确为空。

`note_override.text = ""`表示已人工判断无需备注；它不同于“尚未迁移备注”。

备注不能反推fivebox.status，fivebox.status也不能自动生成一段长备注。

## 5. 时间规则引用 `timing_rule_ref`

Task Card不保存整步/整图墙钟，也不为了Timing再拆任务攻略。

`timing_rule_ref`只引用Timing owner中已经定义的计算规则/规则族；当前尚未完成时间分类时允许为`null`。

如果以后一个真实任务无法由现有时间规则表达，应先在Timing owner中定义新的可复用规则，再让Task Card引用它；不能在Task Card里另建一套时间公式。

任务级、地图级、step级真实墙钟样本仍进入Timing Observations，由Timing模型结合Route Profile顺序计算。

## 6. Evidence / 当前事实与来源

`evidence`保存当前事实的来源和置信度，例如：

- 用户实服反馈；
- Questie；
- 本地结构化数据库；
- 公开资料；
- 旧数据迁移来源。

每条证据用`supports_fields`说明它支持哪些当前字段。

纠错时：

1. 当前有效字段改成新值；
2. 旧来源/旧判断留在历史证据或archive；
3. 不让旧错误继续占当前字段；
4. 通过task_id重新生成引用该任务的派生结果。

## 7. Coverage

`coverage`只描述三类基础内容目前整理到什么程度：

- `availability`；
- `rewards`；
- `guide`。

值为`unknown / partial / verified / not_applicable`。

fivebox是否确认直接由`fivebox.status`表达：`pending`就是尚未确认，不再维护第二个fivebox coverage状态。

**迁移工作是否完成也不由coverage代表。** 本轮架构迁移另有逐task_id迁移清单；只有旧信息全部有归属，该task_id才可标记迁移完成。

## 8. Task Card不保存什么

- 必做/跳过/条件做；
- P1/P2/P3/P4等路线优先级；
- 某条路线的步骤号与顺序；
- 路线特有的NPC访问顺序、交通、炉石、飞行点；
- “先别交/和B一起做”等路线指令；
- 当前角色预计交任务等级；
- 当前路线派生XP/金币/整图墙钟；
- 可以由统一前端规则生成的重复说明。

一句话：**Task Card保存任务本身；Route Profile保存这条路线怎么走。**

## 9. 与Route Profile / Publisher的关系

Task Card只提供单任务当前事实，不拥有路线生成编排。Task Card修改后先用task_id反向索引找到真实引用它的Profile，再按`../rules/route-profile-and-lifecycle.md`的跨owner传播原则刷新受影响领域；本文不复制其它owner的操作，也不允许“Task Card + Profile直接到Publisher”这类旁路。

Route Profile中的任务动作只保存稳定`task_id`和路线原子，例如：

`accept task_id=10208`  
`objective task_id=10208`  
`turnin task_id=10208`

Publisher再：

1. 根据task_id读取Task Card任务名；
2. Route Display把接/做/交/NPC/地点转换成玩家动作；
3. Task Presentation读取`fivebox.status`生成标签；
4. 读取当前`presentation.note_override`附着玩家备注；
5. UI负责渲染。

Publisher不解析guide来猜共享标签，也不从旧中文路线句子反推任务事实。

## 10. 当前证据查询与修改方式

Evidence Index由`scripts/build_task_evidence_index.py`生成到`_sandbox/task-evidence-index.sqlite`。它一次解析Questie有效任务行（含Corrections）、AzerothCore奖励库、当前Task Card和仍在现役范围内的结构化资料，之后按`task_id`直接查询。它不读取旧workbench或迁移期fivebox账本。该SQLite是**可删除重建的查询缓存，不是真源，也不提交Git**；单任务查看使用`scripts/inspect_task_evidence.py`。

需要新增或修改Task Card时，先按Route Lifecycle SOP确认这确实属于`TASK_FACT`，再以本文件定义的Task Card字段职责和证据规则修改对应稳定`task_id`。Evidence Index只帮助集中查看证据，不自动替人判断共享机制、路线删留、Presentation文案或其它需要语义判断的内容。

旧Task Card迁移脚本、review queue、fivebox type mapping和workbench动作ID对照均已完成使命并进入`docs/archive/`；它们不是当前操作入口。迁移时遗留但仍未完成的fivebox实测事项已经转入唯一`tasks/todo.md`，对应Task Card继续用`fivebox.status=pending`表达未知，后续随自然实跑验证。

## 11. 修改验收

单Task Card修改至少验证：

- schema合法；
- task_id与文件名一致；
- 当前字段有来源或明确未知；
- 没有Route Profile决策泄漏进Task Card；
- fivebox.status只使用五个固定分类；
- mixed/条件机制没有被粗暴伪装成纯shared/not_shared；
- Route Profile仍能通过task_id引用；
- 玩家备注与fivebox状态相互独立。
