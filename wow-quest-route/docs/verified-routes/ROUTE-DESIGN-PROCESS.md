# Route Lifecycle SOP：信息分类与唯一入口

用途：这是AI处理魔兽路线工作的唯一分类SOP。它只回答两件事：当前输入属于哪一类，以及分类后下一份唯一应该读取的owner是什么。

本文件不定义业务算法、不保存脚本命令、不维护迁移Stage，也不替owner决定具体操作。

## 0. 先拆信息，再分类

一条用户输入可以同时包含多种信息，必须拆成独立项分别分类。

例如一段实跑反馈可能同时包含：
- “这个任务五号共享” → `TASK_FACT`
- “这个任务以后删掉” → `PROFILE_TASK_SET`
- “这次因为死亡多花了12分钟” → `OBSERVATION`
- “我现在做到这里” → `CURRENT_RUNTIME`

拆完后每一项只进入一个分类。无法确认时不猜，停在缺证据或待用户裁决。

## 1. 分类表

| 分类 | 只用于区分的定义 | 唯一下一步 |
| --- | --- | --- |
| `TASK_FACT` | 改变任务本身是什么、怎么做、是否可接、奖励、五开事实或稳定任务知识。路线是否做它不属于这里。 | `../task-library/README.md`；事实尚未确认时再读`../rules/execution-and-mechanics.md`。 |
| `TASK_PRESENTATION` | 底层任务事实和路线动作不变，只改变玩家看到的任务标签、备注或强调。 | `../rules/route-atlas-task-presentation.md` |
| `PROFILE_STEPS` | 任务集合基本不变，但正式路线动作、条件、NPC/target、地点/geometry、交通、顺序或stepGroups改变。 | `../rules/route-profile-and-lifecycle.md`；真实路径/顺序变化时由该owner进入`route-atlas-optimization.md`。 |
| `PROFILE_TASK_SET` | 决定某任务在路线里做、不做、延后或恢复，导致正式任务集合变化。 | `../rules/leveling-and-selection.md` |
| `PROFILE_CONTRACT` | 改既有Profile的scope、goal、character profile、game variant、entry requirements、version或status。 | `../rules/route-profile-and-lifecycle.md` |
| `PROFILE_DISPLAY` | 只改Profile标题、subtitle、footer、map image、publish key、页面顺序等展示元数据。 | `../rules/route-profile-and-lifecycle.md` |
| `ROUTE_PROGRAM` | 改多Profile方案的成员集合、严格执行顺序、Program起始状态/目标、version或status。 | `../rules/route-profile-and-lifecycle.md` |
| `NEW_PROFILE` | 新建正式Route Profile。 | `../rules/route-profile-and-lifecycle.md`；需要任务删留/路线优化时由其进入对应owner。 |
| `CURRENT_RUNTIME` | 只描述当前角色现在做到哪里、等级经验、任务栏、暂停、异常或恢复点，不改变长期路线。 | 当前`CURRENT.md`；需要计算剩余路线时按涉及领域进入对应owner。 |
| `OBSERVATION` | 一次实际发生的计时、经济或运行样本；样本本身尚未升级成长期事实/规则。 | 按§2进入Timing或Economy owner。 |
| `UI_ENGINEERING` | 业务语义不变，只改页面壳、地图、控件、CSS、动画或离线资源。 | `../rules/route-atlas-ui-and-assets.md` |
| `MODEL_OR_RULE` | 修改跨任务/跨Profile复用的通用判断、公式、算法或展示规则。 | 需要找owner时查看`../rules/README.md`目录，然后只进入该owner。 |
| `REPUBLISH_ONLY` | Task Card/Profile/Program/规则/模型都没变，只重新渲染当前fresh Publisher产物。 | `../rules/route-atlas-ui-and-assets.md` |
| `ARCHITECTURE_MIGRATION` | 当前真源/schema/owner/消费者边界需要改变，或现有架构无法表达已经确认的合法需求。 | 当次独立迁移计划；已完成迁移只从`../archive/`按主题考古。 |

分类完成后，实际规则、正式操作命令、失败恢复与直接下游均由对应owner负责。

## 2. OBSERVATION继续怎么分

只有已确认“这是一条实跑样本，而不是长期事实”时才进入这里。

- 实际用时、暂停、死亡、跑尸、等待、迷路、脏时间 → `../rules/timing-and-benchmarking.md`
- 实际金币差、材料数量、资产估值、外部转账污染 → `../rules/economy-model.md`
- 样本直接证明任务稳定事实错了 → 重新分类为`TASK_FACT`
- 样本直接证明正式路线动作/顺序错了 → `PROFILE_STEPS`
- 样本导致以后做不做任务的决定 → `PROFILE_TASK_SET`

## 3. 最容易混淆的边界

### 3.1 事实 vs 路线

“任务X不共享”是`TASK_FACT`；“因为不共享，所以路线以后不做X”是独立的`PROFILE_TASK_SET`。

### 3.2 路线动作 vs 玩家展示

“把交任务移到另一个NPC之后”是`PROFILE_STEPS`；动作不变，只把HUD一句话写短，是`TASK_PRESENTATION`或`UI_ENGINEERING`。

### 3.3 当前状态 vs 长期真源

“我今天停在Step 8”是`CURRENT_RUNTIME`；“Step 8正式动作本身错了”是`PROFILE_STEPS`。

### 3.4 单例问题 vs 通用规则

一个任务特殊不自动升级成`MODEL_OR_RULE`。只有确认同一规律跨任务/跨Profile复用才进入通用owner。

### 3.5 业务错误 vs 架构缺口

现有schema能表达但数据写错 → 回对应`TASK_FACT / PROFILE_*`；只有现有schema/owner无法无损表达已确认合法需求，才是`ARCHITECTURE_MIGRATION`。

## 4. 多分类输入

1. 先拆独立项。
2. 每项按§1分类。
3. 先处理上游真源/业务裁决，再处理依赖它的派生结果。
4. 进入owner后按owner自己的操作章节执行；本SOP不另建中央执行链。
5. 未获授权的额外问题只记录，不扩大修改范围。

## 5. 无法继续时

- **缺证据**：保持UNKNOWN，回事实/模型owner补证据。
- **需要用户业务裁决**：不猜，写入`../../tasks/todo.md`；若阻止正式cutover，用`[CUTOVER-BLOCKER:<id>]`标记同一Todo项。
- **现有规则能表达但实现坏了**：回对应owner修实现。
- **现有架构无法表达合法需求**：进入`ARCHITECTURE_MIGRATION`。

不能用手改HTML、旧JSON、旧builder、无理由全量重跑或“选一个差不多的分类”绕过owner。
