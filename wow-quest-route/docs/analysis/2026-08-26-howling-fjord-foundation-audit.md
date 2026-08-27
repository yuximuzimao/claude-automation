# 嚎风峡湾基础层审计（未排正式路线）

- 输入直接来自已清洗的诺森德任务宇宙；本步骤只建立嚎风正式scope、依赖闭包和目标簇。
- 正式候选：111项；requiredLevel：`{68: 62, 69: 46, 70: 2, 71: 1}`。
- task class：`{'elite_or_boss_kill': 1, 'item_source_not_in_questie': 6, 'mixed_objectives': 9, 'mixed_with_personal_item': 5, 'multi_creature_personal_drop': 11, 'multi_target_shared_kill': 15, 'shared_kill': 11, 'single_named_drop': 7, 'single_named_kill': 11, 'travel_dialogue_or_turnin': 28, 'world_object_item_collection': 7}`。
- 精确目标簇：112；多个任务共享实体簇：8。
- 强依赖缺口：0。
- 服务时间仍未知：13。

## 入图合同

- 灰熊正式设计出口：加弗洛克交《终获解救》。
- 利用灰熊已开的欧尼瓦/征服堡飞行网络：加弗洛克骑到欧尼瓦 → 系统飞行征服堡 → 陆路越境进入嚎风西侧药剂师营地；不假设嚎风任何飞行点已开。
- 第一个正式Hub固定为药剂师营地；其飞行点首次到达时开启，之后才允许使用药剂师营地→征服堡/冬蹄/新阿加曼德/卡玛古等已知航线。

## 强依赖缺口

- 无。111项正式候选在当前scope内依赖闭合。

## 下一步

- 以复仇港东线为第一任务簇，逐簇插入；每插一簇同步检查交后解锁、同NPC、同Spatial Instance和当时交通。海盗湾/慈悲修女号整链作为独立完整任务簇插入，不再沿用旧自动路线漏项结构。
