# 魔兽任务路线永久规则注册表

用途：这是`docs/rules/`的**唯一规则目录、核心业务名词定义和规则治理入口**。它不复制子规则正文。先判断当前工作属于哪个领域，只加载对应owner。

## 1. 项目第一目标

**把“任务路线”做成可长期复用的高净金币 / 玩家真实墙钟系统。**

升级、任务选择、路线算法、时间模型、Task Card、Route Atlas页面都只是实现这一目标的工具。

固定边界：

- 任务路线自身作为独立打金方式核算，不把团本/日常等其它方式的G/小时偷换成单任务机会成本；
- 经验是未满级任务路线内部的状态变量，影响可接性、80级时点和后续XP折金；
- 低脑力、高复用不是第二目标，而是长期真实金币效率能够兑现的执行条件。

具体计算/决策只读对应子owner。

## 2. 四个核心概念

### Task Card

单任务当前有效事实的唯一知识真源。

回答：**这个任务本身是什么、怎么做、有哪些机制和证据？**

字段/数据字典：`../task-library/README.md`。

### Route Profile

一个明确scope下的唯一正式路线真源。

回答：**这条路线选择哪些任务、按什么动作/顺序/步骤执行？**

定义/生命周期：`route-profile-and-lifecycle.md`。

### CURRENT

当前这批实际角色在某个Route Profile上的runtime overlay / 唯一恢复点。

回答：**我现在做到哪里、现场状态是什么、下一步从哪里恢复？**

CURRENT不是第二份正式路线。

### Generated Product

由Task Card + Route Profile + Rules/Models生成的聚合数据和页面，例如：

- `data/route-atlas/workbench-routes.json`；
- `data/routes/route-atlas-workbench.html`。

目标态它们都可以删除后重建，不是业务真源。

## 3. 证据优先级

当前事实冲突时统一按：

**用户当前服务器实测 > 当前客户端/最新Questie现场状态 > 已验证Task Card/结构化实跑证据 > Questie/本地数据库 > 可靠公开资料 > 历史路线/旧推论。**

注意：

- 高优先级证据仍只能修改它真正证明的字段；
- 一个角色完成任务不能自动证明五号共享；
- Questie坐标不能自动证明真实入口/楼层；
- 历史页面只能解释过去，不能覆盖当前Task Card/规则。

## 4. 唯一owner注册表

| 领域 | 唯一owner | 回答的问题 |
| --- | --- | --- |
| Task Card字段/事实/证据/五开标签/人工备注层 | `../task-library/README.md` | 单个任务要存哪些变量、每个变量是什么意思 |
| 任务机制分类与核验 | `execution-and-mechanics.md` | 机制有哪些维度、怎么确认、哪些不能推断 |
| 任务删留决策 | `leveling-and-selection.md` | 何时比较now/later/never，怎么决定做不做 |
| 任务经验 | `xp-model.md` | XP公式、衰减、上下界怎么算 |
| 路线墙钟 | `timing-and-benchmarking.md` | 移动/战斗/交互/等待等怎么换算时间 |
| Route Profile与生命周期 | `route-profile-and-lifecycle.md` | 正式路线保存什么、如何重建、如何退役 |
| 路线优化算法 | `route-atlas-optimization.md` | 已决定要做的任务怎么排、状态怎么传播/局部重放 |
| Route Atlas前端总路由 | `route-atlas-player-contract.md` | 前端三子owner如何分工 |
| 路线步骤/地点/NPC/接做交 | `route-atlas-route-display.md` | Route Profile怎样变成玩家动作/步骤 |
| 任务标签/备注/角标 | `route-atlas-task-presentation.md` | Task Card怎样压缩成玩家必要信息 |
| 页面/地图/控件/资源 | `route-atlas-ui-and-assets.md` | HTML容器、地图、动画线、CSS、离线资源 |

`state-and-validation.md`已退出owner角色，只保留旧引用兼容指针。

## 5. 流程、历史、实现不是规则owner

以下文件有重要职责，但不得复制永久规则正文：

- `../verified-routes/ROUTE-DESIGN-PROCESS.md`：Route Lifecycle SOP，只编排何时调用owner、重新生成和测试；
- `../verified-routes/ERROR-BOOK.md`：历史失败案例，只保存过去怎么错/为什么复发及当前规则入口；
- `../../tests/README.md`：契约→最小测试组合；
- `../../scripts/README.md`：现役脚本注册/生命周期；
- `../INDEX.md`：纯文档导航；
- `../../SKILL.md`：用户任务→固定最小工作流路由；
- `../../CLAUDE.md`：项目级纪律。

如果单独读上述任何一份就足以完整重新实现某个业务规则领域，说明它越权复制了owner。

## 6. 永久规则准入与唯一owner治理

内容进入`docs/rules/`必须同时满足：

1. **跨地图/跨批次仍成立**；
2. 描述方法/模型/产品契约，不描述某个任务当前事实；
3. 有唯一owner；其它位置只能引用；
4. 不与项目第一目标冲突；
5. 代码/数据/测试实现最终能与规则一致；
6. 不把历史修复方式升级成永久规则，除非已经明确泛化验证。

### 出现重复/冲突时

不按“哪个文件更新得晚”机械覆盖。

固定处理：

1. 判断内容属于哪个领域；
2. 把完整定义保留在唯一owner；
3. 其它文档改成引用或历史说明；
4. 再同步实现/测试；
5. 不允许两边继续独立维护。

## 7. Task事实、规则、路线决策的边界

### Task Card事实

例如：

- 前置；
- 掉率；
- 洞穴楼层；
- 共享/个人拾取；
- Boss机制；
- 详细攻略；
- 五开结构化状态/标签变量；
- 用户确认的人工推荐备注override。

### Rule

例如：

- `shared_kill`是什么意思；
- XP怎么算；
- 什么时候启动删留评估；
- fivebox状态如何映射成共享/不共享/依次拾取/待实测标签；
- 人工推荐备注如何独立于标签呈现。

### Route Profile决策

例如：

- DK地狱火是否做任务X；
- 任务X放第几步；
- 此Profile什么时候交任务；
- 当前路线用哪个飞行点/炉石。

三者不得互相复制为第二真源。

## 8. 按工作类型加载

| 当前工作 | 必读owner | 按需追加 |
| --- | --- | --- |
| 查/纠正某任务机制 | Task Card + `execution-and-mechanics.md` | 公开资料/Questie/ERROR-BOOK相关案例 |
| 只改人工推荐备注/标签映射 | `route-atlas-task-presentation.md` + Task Card | 改`fivebox.status`机器状态走TASK_FACT；需要确认机制时读Task Mechanics |
| 只改步骤/接做交/步骤分段 | 对应Route Profile + `route-atlas-route-display.md` | 顺序真实变化时读Route Optimization/Timing |
| 删除/恢复/延后任务 | `leveling-and-selection.md` + Task Card + 对应Profile | XP/Timing/Route Optimization |
| 经验预算 | `xp-model.md` | Task Cards + 当前Profile/CURRENT |
| 估时/实跑比较 | `timing-and-benchmarking.md` | Task Cards + Route Profile + timing observations |
| 路线排序/局部插入/交通 | `route-atlas-optimization.md` + 对应Profile | Task Cards、XP、Timing |
| Task Card事实改动影响多个路线 | `route-profile-and-lifecycle.md` | 通过task_id反向索引找引用Profile并重新生成派生结果 |
| 页面/地图/控件 | `route-atlas-ui-and-assets.md` | 若业务字段同时变化再读对应前端owner |
| 新建/系统修订/实跑写回 | Route Lifecycle SOP | SOP按阶段加载上述owner |

不要因为“Route Atlas”三个字就一次性加载全部规则。

## 9. 规则修改的一致性门禁

本轮若新增/修改永久规则，只检查**受影响规则邻域**：

- 是否真的是永久方法；
- 是否在正确owner；
- 是否与其它owner重复/冲突；
- 是否夹带具体任务/当前阶段事实；
- 哪些数据/代码/tests是消费者；
- 是否需要迁移兼容层；
- 顶层路由是否最后同步。

只有像2026-09-15这种整体架构治理，才做全量规则矩阵；普通局部规则变更不全文重审所有规则。

## 10. 历史与当前

- `docs/archive/`：只保存历史形成过程，不参与当前默认推导；
- ERROR-BOOK：历史错误案例，不存当前正确规则正文；
- 旧Route Profile/路线版本只有标记`retired/history`后才停止参与当前重新生成链；
- `frozen reusable`仍是现役可复用路线，已知任务事实修正后必须重新生成相关派生结果，但不自动重新优化任务选择。

## 11. 一句话边界

**Task Card回答“任务是什么”；Rule回答“怎么算/怎么判断/怎么显示”；Route Profile回答“这条路线怎么走”；CURRENT回答“我现在走到哪”；HTML/聚合JSON只是把它们呈现出来。**
