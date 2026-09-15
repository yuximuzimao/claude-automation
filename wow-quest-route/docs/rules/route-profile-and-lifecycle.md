# Route Profile 与生命周期规则

用途：这是项目中**一条正式路线是什么、保存什么、如何被重建和退役**的唯一规则 owner。它不负责 Task Card 事实、任务删留、路线排序、玩家备注或复杂传播分类。

## 1. Route Profile 的身份

Route Profile 表示一个明确 scope 下可重复执行的正式路线。一个 `profile_id` 只允许一份正式路线真源；同一地图可以有普通、DK 或其它不同 Profile。所有任务只用稳定 `task_id` 引用 Task Card。

## 2. 保存什么

Route Profile 只保存无法从 Task Card 或规则重新得到的路线决策与原子信息：

- 当前路线采用的 task_id 集合；
- 结构化动作及严格顺序；
- stepGroups；
- 地点/坐标/phase/transport 等路线原子信息；
- NPC/地点等动作参与者的原子引用；
- Profile 特有的交通、炉石、飞行点、条件动作；
- 最小 entry/exit state contract；
- Profile 自身的 scope、版本、状态和变更记录。

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

## 5. 路线上下文

动作顺序本身表达“什么时候接/做/交/转场”。不建立第二个 route-note 层重复“先 A 后 B”“做完继续”“与 B 一起做”。

## 6. Entry / Exit 只保存真实跨 Profile 状态

当前只加入真正需要跨 Profile 传递的状态，例如仍 active 的 task_id。不要预先建设庞大 RouteState。新增状态字段必须由真实路线需求触发。

## 7. CURRENT 不是第二路线真源

CURRENT 只是某一批角色在某 Profile 上的运行时 overlay，记录当前 step/action、暂停、异常和现场状态；不复制整条正式路线。

## 8. Task Card 变化后的处理

不建设独立 `x-impact` / 六类传播系统。

Task Card 事实变化后：

1. 通过 `task_id → Route Profile` 反向索引找出所有现役/可复用 Profile；
2. 不改这些 Profile 的路线决策；
3. 从 Task Card + Profile + 对应 Rule/Model 重新生成这些 Profile 的派生结果；
4. 如果重新计算后触发 Selection 规则，只标记需要复核，不自动重排。

Route Profile 自身的顺序/任务集合变化默认只影响本 Profile。

## 9. Generated Product

目标生成链：

`Task Card + Route Profile + Rules/Models → Publisher → workbench-routes.json → HTML`

`workbench-routes.json` 和 HTML 都是可删除重建的生成物，不能作为下一轮路线真源，也不接受地图脚本直接维护同一路线决策。

## 10. 迁移与退役门禁

旧路线源必须按固定顺序退出：

`迁入新真源 → 信息完整性审计 → 语义对账 → 切消费者 → 禁止旧写入 → 退役/归档`

只有“旧信息全部有新归属或明确批准丢弃”后，才允许开始新旧 Publisher 替代测试。

## 11. 最小机械验收

- Profile ID/scope 唯一；
- task 引用只用稳定 ID；
- 任务动作结构化；
- Profile 不复制 Task Card 事实；
- stepGroups 覆盖动作且保持顺序；
- 条件使用普通 action + `when`；
- entry/exit 状态闭合；
- 完整中文动作句不作为路线真源；
- task_id 反向索引可机械生成；
- 修改一个 Profile 不修改其它 Profile；
- workbench/HTML 最终可重建。

## 12. 不负责

- Task Card 字段：`docs/task-library/README.md`；
- Task Mechanics：`execution-and-mechanics.md`；
- Selection：`leveling-and-selection.md`；
- XP/Timing：各模型 owner；
- 路线排序：`route-atlas-optimization.md`；
- 路线动作中文转换：`route-atlas-route-display.md`；
- 标签/备注：`route-atlas-task-presentation.md`；
- 页面工程：`route-atlas-ui-and-assets.md`；
- 调度与测试组合：`ROUTE-DESIGN-PROCESS.md` 与 `tests/README.md`。
