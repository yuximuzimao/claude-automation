# 灰熊丘陵基础层审计（未排正式路线）

- 当前只建立首组户外全清任务事实层、依赖闭包和真实目标簇；没有做逐任务经济删留。
- 正式候选：83项；requiredLevel：`{72: 14, 73: 69}`。
- task class：`{'elite_or_boss_kill': 1, 'item_source_not_in_questie': 5, 'mixed_objectives': 5, 'mixed_with_personal_item': 6, 'multi_creature_personal_drop': 9, 'multi_target_shared_kill': 9, 'shared_kill': 6, 'single_named_drop': 3, 'single_named_kill': 15, 'travel_dialogue_or_turnin': 20, 'world_object_item_collection': 4}`。
- 精确目标簇：69；被多个任务共享的实体簇：5。
- 强依赖缺口：0。
- 服务时间仍未知：10。

## 强依赖缺口

- 无。83项正式候选在当前入口合同下可以形成闭合依赖池。

## 服务时间仍未知/需特殊机制核验

- 11990《幻象之瓶》：{'status': 'unknown', 'minutes': None, 'basis': 'missing_mixed_item_count'}
- 12007《必要的牺牲》：{'status': 'unknown', 'minutes': None, 'basis': 'item_source_not_in_questie'}
- 12026《破损的日记》：{'status': 'unknown', 'minutes': None, 'basis': 'item_source_not_in_questie'}
- 12058《符文中的预言》：{'status': 'unknown', 'minutes': None, 'basis': 'missing_mixed_objective_count'}
- 12099《终获解救》：{'status': 'unknown', 'minutes': None, 'basis': 'unsupported_task_class:elite_or_boss_kill'}
- 12137《冷静一下，伙计》：{'status': 'unknown', 'minutes': None, 'basis': 'missing_mixed_item_count'}
- 12165《有趣的计划》：{'status': 'unknown', 'minutes': None, 'basis': 'item_source_not_in_questie'}
- 12197《我们有能源》：{'status': 'unknown', 'minutes': None, 'basis': 'missing_mixed_item_count'}
- 12241《摧毁树苗》：{'status': 'unknown', 'minutes': None, 'basis': 'item_source_not_in_questie'}
- 12279《熊的美食》：{'status': 'unknown', 'minutes': None, 'basis': 'item_source_not_in_questie'}

## 已确认的特殊路线机制

- 12177《休尼克的掩饰》：《休尼克的掩饰》需要1份煤块和5份面粉；两者都可在征服堡内向商人购买。Questie物品来源展开会把煤块的全世界掉落源带入route_zones，不能因此误判为副本任务。

## 下一步

- 只在这个闭合任务池上排征服堡→西南/沃达希尔→欧尼瓦→东北任务中心的正式Hub顺序；完成整图后再做动态飞行点、炉石、玩家视角冷启动复审。
