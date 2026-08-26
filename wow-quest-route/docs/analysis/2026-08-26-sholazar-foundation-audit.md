# 索拉查盆地基础任务层与跨地图入口审计

- 当前阶段：80级一次性户外任务金币清理；不学习寒冷天气飞行。
- effective Northrend universe归属索拉查：105项；物理touch：98项。
- 当前正式候选池：66项；状态统计：`{'exclude_cold_weather_flying_chain': 15, 'exclude_deprecated': 3, 'exclude_deprecated_duplicate': 1, 'exclude_mutually_exclusive_frenzyheart_branch': 2, 'exclude_test_or_non_executable': 2, 'include_candidate': 64, 'include_conditional_route_state': 1, 'include_structural_repeatable_first_run': 1, 'knowledge_repeatable_or_calendar': 16}`。
- 寒冷天气飞行直接门槛：[12561, 12803]；连同独占后续递归阻断共15项：[12546, 12548, 12559, 12561, 12608, 12611, 12612, 12613, 12617, 12620, 12621, 12660, 12797, 12803, 12805]。
- 索拉查内部强依赖缺口：0；跨图依赖记录：0。
- 目标实体簇：92；多任务共享簇：36。
- 服务时间尚未估计：0；objective review待人工解析：0。这些是后续任务卡建设项，不在foundation阶段伪造为已完成。
- 视频：`no_sholazar_video_in_current_index`；现有项目视频索引中没有索拉查整图素材，因此本图不安排视频反向审查，除非后续新增素材。

## 跨地图转场合同

- 上一地图：冰冠冰川；当前正式路线计划终点：奥格瑞姆之锤（冰冠仍在实跑，若最终点改变只重验第一段）。
- 当前计划终点下转场合同已闭合：奥格瑞姆之锤 → K3借用双足飞龙自主飞回已开的银色比武场 → 系统飞行到达拉然 → 大法师伯塔鲁斯执行12521脚本运输 → 索拉查蛮藤谷。
- 已携带跨图引导：12521《赫米特·奈辛瓦里哪去了？》。达拉然阶段只接走，没有触发离城；任务文本明确到达索拉查后在蛮藤谷找蒙特。
- `map_transition_contract=PASS(current planned Icecrown endpoint)`；正式发布索拉查前若冰冠实跑最终点不再是奥格瑞姆之锤，重新计算上一图出口即可，索拉查脚本落点不变。

## 强依赖缺口

- 无。当前正式候选在索拉查内部没有被scope排除的强制前置缺口。

## 跨图依赖

- 无。

## 重复任务结构提升

- 12689《神谕者之手》被12695作为强制前置引用；这里只标记待人工核对，不代表已确认必须纳入。

## 待补任务卡事实

### 服务时间未知

- 无。

### objective review待人工解析

- 无。

## 下一步

- 狂心氏族 / 神谕者最终阵营二选一已由用户选择神谕者；狂心最终分支从正式池排除，神谕者结构前置保留。
- 下一步解析当前正式候选的任务卡特殊机制和Target Cluster空间序列；入口合同已PASS，可以开始排索拉查整图顺序。
