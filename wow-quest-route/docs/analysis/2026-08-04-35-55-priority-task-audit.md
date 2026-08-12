# 35—55高优先任务分类审计

> 本文是覆盖层审计，不改基础任务JSON，不宣布最终路线、最终任务数或总时长。`needs_live_test`表示当前服务器五开机制不能由静态数据库证明。

## 1. 审计结果

- 并集审计任务：278个。
- 状态：confirmed 56个；needs_live_test 222个。
- 倾向：conditional_candidate_with_stop_loss 174个；defer_until_evidence_or_live_test 32个；exclude_from_current_outdoor_optimizer 16个；retain_as_structurally_valid_candidate 56个。
- 所有修正只保存在本覆盖层；本轮没有用不确定推断覆盖基础事实。

## 2. 范围覆盖

| 范围 | 数量 |
| --- | ---: |
| `c1_high_value_strong_overlap_low_confidence` | 14 |
| `current_processable_88` | 88 |
| `dungeon_objective_source` | 16 |
| `escort_or_defense` | 2 |
| `feralas_remaining` | 33 |
| `item_source_missing` | 35 |
| `object_respawn_and_multi_click_unknown` | 60 |
| `objective_count_review` | 65 |
| `scripted_event_mechanic` | 1 |
| `tanaris_remaining` | 46 |

## 3. 关键机制区分

- 所有已知物品来源均为100%参考概率：94个任务；仍不能据此假定同一尸体可供五号分别拾取。
- 至少一个参考概率低于100%：59个任务；必须按五号最慢完成者处理掉落方差。
- 至少一个物品来源缺失：35个任务；来源补齐前不进入无条件保留集合。
- 固定物体与怪物掉落分别保留原机制；物体刷新、五号连续交互、护送、防守、限时和区域事件只要静态不可证实，均标记`needs_live_test`。
- `dungeon_objective_source`统一倾向排除出当前户外优化器，但保留数据，不等于永久删除任务。

## 4. 按地图审计

### Sunken Temple

- 《阿塔哈卡神庙》（1445）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：1444, 1446；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, not_in_world_candidate_union, rare, rare_elite, server_drop_rate_needed。
- 《预言者迦玛兰》（1446）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：single_named_creature_task_item；强重叠：1445；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, objective_count:implicit_single。
- 《神灵哈卡》（3528）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：4787, 5065；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, item_source_missing:10662, not_in_world_candidate_union, objective_count:implicit_single。
- 《除草器的燃料》（4146）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：4147, 4148；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, not_in_world_candidate_union, server_drop_rate_needed。

### 东瘟疫之地

- 《失落的摩沙鲁石板》（5065）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：3528；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《帕米拉的洋娃娃》（5149）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：5142, 5152, 5241, 5601；风险：fivebox_mechanic_unconfirmed, item_source_missing:12885, objective_count:implicit_single。
- 《古怪的历史学家》（5153）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5152, 5154；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《达隆郡的英雄》（5168）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5206, 5210；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《达隆郡的恶魔》（5181）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5206, 5210；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《达隆郡的掠夺者》（5206）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：5168, 5181, 5941；风险：fivebox_mechanic_unconfirmed, item_source_missing:13155。
- 《失落的荣耀》（5845）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5781, 5846；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《瘟疫与你》（5901）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5902；风险：active_item_or_spell_use, cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《杀戮的理由》（6022）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:15448, objective_count:ambiguous_extra_numbers。
- 《狮子大开口》（6026）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：item_source_not_in_questie；强重叠：6041；风险：fivebox_mechanic_unconfirmed, item_source_missing:10560, item_source_missing:10562, item_source_missing:11128, item_source_missing:12359。
- 《游侠之王的命令》（6133）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills, task_item_world_object_pickup；强重叠：13906, 13908；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《奥古斯图斯的收据册》（6164）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。

### 丹莫罗

- 《设备之战》（2841）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops, task_item_world_object_pickup；强重叠：无强重叠；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, object_respawn_and_multi_click_unknown, objective_count:missing_counts, server_drop_rate_needed。
- 《主工程师斯库提》（2842）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, not_in_world_candidate_union。

### 冬泉谷

- 《雪怪计划！》（5163）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：977；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:missing_counts。

### 凄凉之地

- 《凄凉之地的科卡尔部族》（1362）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：cross_zone_or_multi_zone。
- 《戴兹帕可汗》（1365）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《偷取物资》（1370）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：1373；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《瓦鲁格的玩具》（1371）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：1375；风险：fivebox_mechanic_unconfirmed, item_source_missing:4392, objective_count:implicit_single。
- 《堕落者》（1488）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：elite_or_boss_shared_kills, regular_shared_kills；强重叠：无强重叠；风险：elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《埃鲁索斯之手》（5381）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：5581；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《食鱼度日》（5386）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, item_source_missing:13546。
- 《幽灵电浆》（6134）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：无强重叠；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《蚌肉鱼饵》（6142）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1482, 2950, 6143, 6161；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《另一种鱼》（6143）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：6142, 6161；风险：fivebox_mechanic_unconfirmed。
- 《拉克摩尔的财宝！》（6161）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1482, 6142, 6143；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, rare, server_drop_rate_needed。

### 千针石林

- 《流放者马特克》（1106）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1108；风险：cross_zone_or_multi_zone。
- 《坚硬的尾鳍》（1107）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：339, 340, 341, 342；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《精铁碎片》（1108）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：1106, 1137, 2283；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, not_in_world_candidate_union, server_drop_rate_needed。
- 《地精的谣言》（1117）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1118；风险：cross_zone_or_multi_zone。
- 《地精赞助商》（1183）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1186；风险：cross_zone_or_multi_zone。
- 《拉泽瑞克的调整》（1187）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：1186, 1188；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《兄弟》（5361）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：cross_zone_or_multi_zone。

### 塔纳利斯

- 《谢申克的救赎》（10）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：82, 110；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《异种蝎的威胁》（32）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：113；风险：cross_zone_or_multi_zone。
- 《腐化之巢》（82）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：10, 992；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《昆虫研究》（110）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：10, 113；风险：无新增风险标记。
- 《昆虫研究》（113）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：32, 110；风险：无新增风险标记。
- 《进入沙漠》（243）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：238, 379；风险：cross_zone_or_multi_zone。
- 《寻找OOX-17/TN！》（351）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《口渴的比格维兹》（379）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：243, 654, 841, 1690, 1691, 1707, 2875, 8365；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《塔纳利斯的样本》（654）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：379, 864；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《另一个能量源？》（841）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：379, 1690, 1691, 1707, 2875, 8365；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《加基森水业公司》（992）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：82；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:8585, objective_count:implicit_single。
- 《废土的公正》（1690）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：379, 841, 1691, 1707；风险：fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《废土的公正》（1691）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：379, 841, 1690, 1707；风险：fivebox_mechanic_unconfirmed。
- 《收集水袋》（1707）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：379, 841, 1690, 1691, 2875, 8365；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《口渴的地精》（2605）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_regular_creature_task_item；强重叠：2606；风险：fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《好味道》（2606）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2605, 2641；风险：无新增风险标记。
- 《斯普琳科的秘密佐料》（2641）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：2606, 2661；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《给马林的粉末》（2661）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2641, 2662；风险：无新增风险标记。
- 《诺格弗格药剂》（2662）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2661；风险：无新增风险标记。
- 《超级测蛋器》（2741）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《探水棒》（2768）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：cross_zone_or_multi_zone, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《加兹瑞拉》（2770）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：automatic_route_candidate_missing, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, objective_count:implicit_single。
- 《通缉：卡利夫·斯科比斯汀》（2781）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《深渊皇冠》（2846）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：single_named_creature_task_item；强重叠：2861, 3527；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, objective_count:implicit_single。
- 《塔贝萨的任务》（2861）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2846；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, not_in_world_candidate_union。
- 《特兰雷克》（2864）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2865；风险：cross_zone_or_multi_zone。
- 《圣甲虫的壳》（2865）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：2864；风险：cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《斯杜雷的债务》（2872）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2873；风险：cross_zone_or_multi_zone。
- 《斯杜雷的货物》（2873）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：2872, 2874；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《给马克基雷的货物》（2874）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2873；风险：cross_zone_or_multi_zone。
- 《通缉：安德雷·费尔比德》（2875）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：379, 841, 1707, 8365；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《船运时刻表》（2876）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《巨魔调和剂》（3042）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：3527；风险：cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare_elite, server_drop_rate_needed。
- 《加兹瑞迪安》（3161）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《灌木谷》（3362）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed。
- 《石环》（3444）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：3380, 3446, 3447；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《尖啸者的灵魂》（3520）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：3527；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed。
- 《摩沙鲁的预言》（3527）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops；强重叠：2846, 3042, 3520, 4787；风险：cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《擒虫先擒王》（4496）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：713, 3761, 3882, 3962, 4145, 4284, 4289, 4291, 4292, 4300, 4494, 4501…；风险：cross_zone_or_multi_zone, drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, rare, rare_elite, server_drop_rate_needed。
- 《极度粘稠的沥青》（4504）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：713, 3761, 4284, 4496；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《捕捉皇后》（4507）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：3761, 4496, 4509；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《临危不惧》（4509）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：4507, 4511；风险：cross_zone_or_multi_zone。
- 《砂槌食人魔》（5863）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《拉斯塔哈之手》（8182）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：8181；风险：cross_zone_or_multi_zone。
- 《海盗的帽子！》（8365）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：379, 841, 1707, 2875, 8366；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《南海复仇》（8366）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：8365；风险：fivebox_mechanic_unconfirmed。

### 奥格瑞玛

- 《诺格的手艺》（2950）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops, task_item_world_object_pickup；强重叠：339, 340, 341, 342, 600, 605, 678, 2881, 5882, 6142, 6221, 7829…；风险：cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts, rare, rare_elite, server_drop_rate_needed。

### 安戈洛环形山

- 《无人知晓的秘密》（3845）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：item_source_not_in_questie；强重叠：3844, 3908；风险：fivebox_mechanic_unconfirmed, item_source_missing:11104, item_source_missing:11105, item_source_missing:11106, objective_count:missing_counts。
- 《抢救物资》（3881）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《异型的生态》（3883）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:11131。
- 《视灵药剂》（3909）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3908, 3912；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, item_source_missing:11243, not_in_world_candidate_union, objective_count:implicit_single。
- 《墓地相见》（3912）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：travel_dialogue_or_turnin；强重叠：3909, 3913；风险：active_item_or_spell_use, automatic_route_candidate_missing, cross_zone_or_multi_zone, escort_or_defense_text, fixed_wait_or_respawn_unknown, not_in_world_candidate_union。
- 《结伴而行》（3962）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：elite_or_boss_shared_kills, task_item_world_object_pickup；强重叠：3761, 3961, 4496, 4502；风险：elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《亚奎门塔斯》（4005）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3961, 4084；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, item_source_missing:11522, objective_count:implicit_single。
- 《血瓣花除草器》（4148）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：4146；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《能量水晶》（4284）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：713, 3761, 3882, 4145, 4289, 4300, 4496, 4501, 4502, 4503, 4504；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, rare_elite, server_drop_rate_needed。
- 《拉克维的食物》（4290）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：4291；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《毒药的免疫力》（13850）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_or_rare_kill；强重叠：13887；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:ambiguous_extra_numbers。
- 《毒皮暴掠龙蛋》（13887）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：13850, 13906；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《飞速成长》（13906）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：item_source_not_in_questie, multiple_creature_task_item_drops；强重叠：1125, 2521, 2681, 2950, 3501, 3627, 3628, 3822, 4244, 5082, 5087, 5155…；风险：boss, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, item_source_missing:47196, item_source_missing:8170, objective_count:ambiguous_extra_numbers, rare, rare_elite, server_drop_rate_needed。
- 《好龙配好鞍》（13908）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：item_source_not_in_questie, multiple_creature_task_item_drops；强重叠：1125, 2521, 2681, 2950, 3501, 3627, 3628, 3822, 4244, 5082, 5087, 5155…；风险：automatic_route_candidate_missing, boss, cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, item_source_missing:8170, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union, objective_count:ambiguous_extra_numbers, rare, rare_elite, server_drop_rate_needed。

### 尘泥沼泽

- 《莫格穆洛克的任务》（1166）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《饿！》（1177）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1203；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《塞拉摩间谍》（1201）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：1202；风险：fivebox_mechanic_unconfirmed。
- 《塞拉摩码头》（1202）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：1201；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《死沼巨鳄》（1205）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《沼泽蛙的腿》（1218）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1206, 11225；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《遗失的报告》（1238）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1239；风险：无新增风险标记。
- 《黑色盾牌》（1251）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1321；风险：无新增风险标记。
- 《燃烧的旅店》（1263）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《可疑的蹄印》（1268）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《帕瓦尔·雷瑟上尉》（1269）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《寻找雷瑟》（1272）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《吉姆的歌谣》（1281）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《黎明号的黄昏》（9437）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills, task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《调查废墟》（11124）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《恐角袭击者》（11156）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：spell_use_area_trigger_or_scripted_event；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:missing_counts, scripted_event_mechanic。
- 《血沼羽毛》（11158）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：11160, 11161, 11184；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《石槌之魂》（11159）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：11162；风险：fivebox_mechanic_unconfirmed。
- 《憎恨的精华》（11161）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：11158；风险：fivebox_mechanic_unconfirmed, item_source_missing:33087。
- 《恐怖图腾的武器》（11169）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed。
- 《坠毁的飞艇》（11172）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：11174；风险：无新增风险标记。
- 《沼泽中的毒药》（11173）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1322；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《女巫岭的幽灵》（11180）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：11181；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed。
- 《悬赏：贪婪的血爪》（11184）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_or_rare_kill；强重叠：11158；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《背叛的端倪？》（11186）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《恐怖图腾的密谋》（11201）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：11203, 11204；风险：fivebox_mechanic_unconfirmed, item_source_missing:33051, objective_count:implicit_single。
- 《烧毁恐角岗哨！》（11205）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：11203, 11206；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《回收货物！》（11207）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：11208；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《女巫岭的隐士》（11225）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1218；风险：active_item_or_spell_use。

### 希利苏斯

- 《暮光词典》（8279）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：8285, 8287, 8323；风险：active_item_or_spell_use, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《诺格的背包》（8282）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：8278；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。

### 希尔斯布莱德丘陵

- 《意志之冠》（519）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：518, 520；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《意志之冠》（520）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：519, 521；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《通缉：瓦杜斯男爵》（566）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。

### 幽暗城

- 《意志之冠》（495）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：518；风险：cross_zone_or_multi_zone。
- 《星，手，心》（736）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：339, 340, 341, 342, 728, 737；风险：cross_zone_or_multi_zone, drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《科娜塔一家》（1164）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：无强重叠；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《联络中心》（2995）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_world_objects；强重叠：无强重叠；风险：active_item_or_spell_use, cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《堕落之水》（3568）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：item_source_not_in_questie；强重叠：3569；风险：fivebox_mechanic_unconfirmed, item_source_missing:10691, item_source_missing:10692, item_source_missing:10693, item_source_missing:10694, objective_count:missing_counts。
- 《软泥怪的样本...》（4293）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：4642；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:12234。
- 《一大堆软泥怪》（4294）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：4642；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:12236。

### 悲伤沼泽

- 《缺乏补给》（698）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：699；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《德莱尼水晶》（1389）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《木棒诺博鲁》（1392）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《尼卡·血痕》（1418）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1420；风险：cross_zone_or_multi_zone。
- 《泪水之池》（1424）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：1429；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《新鲜的螃蟹腿》（1430）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：无强重叠；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《伊兰尼库斯精华》（3374）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3373, 3512；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:10455, objective_count:implicit_single。
- 《一点食物》（9440）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, objective_count:missing_counts。

### 暮色森林

- 《真言药水》（1383）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：1372, 1388；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。

### 灰谷

- 《斥候标准护理包》（7867）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, not_in_world_candidate_union。

### 灼热峡谷

- 《铸造火炬杆》（3443）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：3442, 3452, 4022, 4023, 4449, 7728, 7729；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《烧掉它们！》（3463）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_world_objects；强重叠：3462, 3481；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《被锁起来的矮人》（4449）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, regular_shared_kills；强重叠：3442, 3443, 3452, 4022, 4023, 4450, 7723, 7728, 7729；风险：active_item_or_spell_use, drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《塔纳利斯的账本》（4450）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, task_item_world_object_pickup；强重叠：4449；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts, server_drop_rate_needed。
- 《让他们失眠！》（7702）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《绝密配方！》（7722）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《被盗：鼓风机和望远镜》（7728）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：3443, 4449；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。

### 燃烧平原

- 《烈焰精华》（4022）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_regular_creature_task_item；强重叠：3442, 3443, 3481, 4023, 4449, 7723, 7729；风险：active_item_or_spell_use, cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《烈焰精华》（4023）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_regular_creature_task_item；强重叠：3442, 3443, 4022, 4449, 7723, 7729；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《七贤石板》（4296）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, item_source_missing:11470, objective_count:implicit_single。
- 《雏龙精华》（4726）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：4808；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。

### 艾萨拉

- 《会见主人》（3381）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, item_source_missing:10450, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《恶魔之名》（3510）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：3509, 3511；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《搜索知识》（3517）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：3518, 3541, 3542, 3561；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《我就是基姆加尔！》（3601）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5534；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《艾萨拉水晶》（3602）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：3511, 3621；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。

### 荆棘谷

- 《猎虎》（187）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：188；风险：fivebox_mechanic_unconfirmed。
- 《血顶巨魔的耳朵》（189）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：209, 339, 340, 341, 342, 582, 596；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《猎豹》（192）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：193, 570；风险：fivebox_mechanic_unconfirmed。
- 《猎龙》（195）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：196, 568；风险：fivebox_mechanic_unconfirmed。
- 《恶性竞争》（213）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：339, 340, 341, 342；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《荆棘谷的青山》（338）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, item_source_missing:2756, item_source_missing:2757, item_source_missing:2758, item_source_missing:2759, objective_count:missing_counts。
- 《荆棘谷的青山 - 第一章》（339）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, single_regular_creature_task_item；强重叠：189, 209, 213, 340, 341, 342, 569, 573, 576, 582, 584, 586…；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《荆棘谷的青山 - 第二章》（340）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：189, 209, 213, 339, 341, 342, 569, 573, 576, 582, 584, 586…；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《荆棘谷的青山 - 第三章》（341）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：189, 209, 213, 339, 340, 342, 569, 573, 576, 582, 584, 586…；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, rare, server_drop_rate_needed。
- 《荆棘谷的青山 - 第四章》（342）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：189, 209, 213, 339, 340, 341, 569, 573, 576, 582, 584, 586…；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《格罗姆高保卫战》（568）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：195, 569；风险：fivebox_mechanic_unconfirmed。
- 《摩克萨尔丁的魔法》（570）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：192, 572；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《摩克萨尔丁的魔法》（573）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills, task_item_world_object_pickup；强重叠：339, 340, 341, 342, 571, 617；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《威士忌斯利姆的酒》（580）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《血顶徽记》（584）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：209, 339, 340, 341, 342, 582, 585, 586；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《奈兹里奥克》（585）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：584, 588；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《甘祖拉恩》（586）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, regular_shared_kills；强重叠：209, 339, 340, 341, 342, 584, 588, 598；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《拯救耶尼库》（592）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：591；风险：fivebox_mechanic_unconfirmed, item_source_missing:3913, objective_count:implicit_single。
- 《染血的白骨项链》（596）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：189, 339, 340, 341, 342, 582, 598；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《血帆海盗》（604）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills, task_item_world_object_pickup；强重叠：339, 340, 341, 342, 576, 587, 599, 608；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《歌唱水晶碎片》（605）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：589, 600, 2950；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《吓唬病鬼》（606）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：571, 607；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《血帆海盗》（608）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：339, 340, 341, 342, 576, 587, 604；风险：fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《讨债行动》（609）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：339, 340, 341, 342, 607, 613, 621；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《刺着字母的腰带》（620）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《赞吉尔的秘密》（621）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：339, 340, 341, 342, 609, 1119；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《科泰罗的谜题》（624）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：625；风险：automatic_route_candidate_missing, not_in_world_candidate_union。
- 《暗礁海》（629）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《巨魔之敌》（638）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：639；风险：cross_zone_or_multi_zone。
- 《竞技场高手》（7810）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《竞技场高手》（7908）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《船长的箱子》（8551）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：339, 340, 341, 342；风险：elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《挑战奈古拉什》（8554）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：8553, 13906, 13908；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:ambiguous_extra_numbers, server_drop_rate_needed。

### 荒芜之地

- 《遗失的卷轴碎片》（692）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：656, 687, 2258；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《烧烤秃鹰翅膀》（703）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2258；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare_elite, server_drop_rate_needed。
- 《潜水采珍珠》（705）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《化解灾难》（709）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：728；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《研究石元素》（710）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：711, 2258；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《至关重要的冷却剂》（713）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_regular_creature_task_item；强重叠：714, 2881, 3761, 4284, 4496, 4504, 5882, 8460；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《有备无患》（716）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：712；风险：fivebox_mechanic_unconfirmed, item_source_missing:2868, objective_count:implicit_single。
- 《破碎的联盟》（793）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：782；风险：active_item_or_spell_use, drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。
- 《捕猎山狗》（1419）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2258；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《向赫格拉姆报到》（1420）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：1418；风险：cross_zone_or_multi_zone。
- 《奥达曼的蘑菇》（2202）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：task_item_world_object_pickup；强重叠：2258；风险：cross_zone_or_multi_zone, dungeon_objective_source, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《搜寻项链》（2283）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：single_regular_creature_task_item；强重叠：1108, 2284, 2418；风险：cross_zone_or_multi_zone, dungeon_objective_source, fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《寻找宝贝》（2339）— `needs_live_test` / `exclude_from_current_outdoor_optimizer`；机制：multiple_creature_task_item_drops, task_item_world_object_pickup；强重叠：2338, 2340；风险：cross_zone_or_multi_zone, drop_rate_required, dungeon_objective_source, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts, server_drop_rate_needed。
- 《寻找宝物》（2342）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：automatic_route_candidate_missing, cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《能量石》（2418）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2283；风险：cross_zone_or_multi_zone, drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《被抢走的财物》（9439）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。

### 菲拉斯

- 《寻找OOX-22/FE！》（2766）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《质量的保证》（2822）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：7734；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《与豺狼人开战》（2862）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2863；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《突然袭击》（2863）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：2862, 2902；风险：fivebox_mechanic_unconfirmed, objective_count:ambiguous_extra_numbers。
- 《调查木爪岭》（2902）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2863, 2903；风险：无新增风险标记。
- 《作战计划》（2903）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2902, 7730, 7731；风险：无新增风险标记。
- 《新斗篷的光辉》（2973）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2974, 3128；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《可怕的发现》（2974）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2973, 2976；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《菲拉斯的食人魔》（2975）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：2980, 2981；风险：fivebox_mechanic_unconfirmed。
- 《可怕的发现》（2976）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2974；风险：cross_zone_or_multi_zone。
- 《戈杜尼卷轴》（2978）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2979；风险：无新增风险标记。
- 《黑暗仪式》（2979）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_regular_creature_task_item；强重叠：2978, 3002；风险：fivebox_mechanic_unconfirmed, objective_count:implicit_single。
- 《菲拉斯的食人魔》（2980）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：2975；风险：fivebox_mechanic_unconfirmed。
- 《戈杜尼钴矿石》（2987）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《戈杜尼宝珠》（3002）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：2979；风险：cross_zone_or_multi_zone。
- 《黑暗之心》（3062）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《对鹰身人的复仇》（3063）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed。
- 《奇怪的要求》（3121）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：3122；风险：无新增风险标记。
- 《向巫医尤克里回复》（3122）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：3121, 3123；风险：无新增风险标记。
- 《测试容器》（3123）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3122, 3124；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:9594。
- 《角鹰兽灵魂精华》（3124）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3123, 3125；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:9595。
- 《精灵龙灵魂精华》（3125）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3124, 3126；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:9596。
- 《树人灵魂精华》（3126）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3125, 3127；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:9593。
- 《山岭巨人灵魂精华》（3127）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3126, 3129；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:9597。
- 《天然材料》（3128）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2973, 3129；风险：drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《灵魂武器》（3129）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：3127, 3128；风险：无新增风险标记。
- 《堕落的力量》（4120）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：4084, 5882；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed。
- 《被缩小的巨人》（7003）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：无强重叠；风险：active_item_or_spell_use, drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《压缩器的动力》（7721）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：无强重叠；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《祖卡什的入侵》（7730）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2903, 7731, 7732；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《毒刺鞭笞者》（7731）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：single_named_creature_task_item；强重叠：2903, 7730, 7732；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:implicit_single。
- 《祖卡什报告》（7732）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：7730, 7731；风险：cross_zone_or_multi_zone。
- 《更高的品质》（7734）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2822；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。

### 西瘟疫之地

- 《啊，安多哈尔！》（105）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5098；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, not_in_world_candidate_union, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《找回时间》（4972）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：4971；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《两半合一》（5051）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：5050；风险：fivebox_mechanic_unconfirmed, item_source_missing:12723, objective_count:implicit_single。
- 《标记哨塔》（5098）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：105；风险：active_item_or_spell_use, cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, objective_count:missing_counts。
- 《达隆郡的历史》（5154）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：5153, 5210；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《未完的任务》（6023）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：6004, 13906, 13908；风险：fivebox_mechanic_unconfirmed, objective_count:missing_counts。

### 诅咒之地

- 《弯牙土狼的颚骨》（2581）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, single_regular_creature_task_item；强重叠：2521, 2583, 2585, 2603, 3501；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《野猪的活力》（2583）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, single_regular_creature_task_item；强重叠：2521, 2581, 2585, 2601, 3501；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《决定性的打击》（2585）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, single_regular_creature_task_item；强重叠：2521, 2581, 2583, 2601, 2603, 3501；风险：drop_rate_required, elite_or_rare_target, fivebox_mechanic_unconfirmed, rare, server_drop_rate_needed。
- 《收集破碎的护符》（3627）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：2521, 3501, 3626, 3628, 13906, 13908；风险：cross_zone_or_multi_zone, drop_rate_required, elite, elite_or_rare_target, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。

### 费伍德森林

- 《腐化之井》（4505）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：6605；风险：fivebox_mechanic_unconfirmed, item_source_missing:12567, objective_count:implicit_single。
- 《收集堕落之水》（5157）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：5155, 5158；风险：fivebox_mechanic_unconfirmed, item_source_missing:12907, objective_count:implicit_single。
- 《熄灭火焰》（5165）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：multiple_world_objects；强重叠：5159, 5242；风险：active_item_or_spell_use, escort_or_defense_text, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, objective_count:missing_counts。
- 《最终一击》（5242）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops, regular_shared_kills；强重叠：5165, 5882, 13906, 13908；风险：drop_rate_required, fivebox_mechanic_unconfirmed, objective_count:missing_counts, server_drop_rate_needed。

### 辛特兰

- 《收集蜜糖》（77）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：81, 650；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《远古之卵》（4787）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：3527, 3528；风险：cross_zone_or_multi_zone, fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《邪枝窃贼》（7839）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:implicit_single。
- 《分离的痛苦》（7849）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《黑暗之瓶》（7850）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《通缉：邪恶祭司海克斯和她的爪牙》（7861）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：2881；风险：fivebox_mechanic_unconfirmed, objective_count:missing_counts。

### 银月城

- 《部落的盟约》（9627）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：cross_zone_or_multi_zone。

### 阿拉希高地

- 《山中的水晶》（635）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：无新增风险标记。
- 《Legends of the Earth <NYI>》（636）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：无强重叠；风险：automatic_route_candidate_missing, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。
- 《被困的公主》（642）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：multiple_creature_task_item_drops；强重叠：651；风险：drop_rate_required, fivebox_mechanic_unconfirmed, server_drop_rate_needed。
- 《禁锢之石》（651）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：642, 652；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《深海打捞》（662）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：663；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown, objective_count:missing_counts。
- 《法迪尔海湾》（663）— `confirmed` / `retain_as_structurally_valid_candidate`；机制：travel_dialogue_or_turnin；强重叠：662；风险：无新增风险标记。
- 《船长的复仇》（664）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：regular_shared_kills；强重叠：无强重叠；风险：fivebox_mechanic_unconfirmed。
- 《水下宝藏》（666）— `needs_live_test` / `conditional_candidate_with_stop_loss`；机制：task_item_world_object_pickup；强重叠：668；风险：fivebox_mechanic_unconfirmed, fixed_wait_or_respawn_unknown, object_respawn_and_multi_click_unknown。
- 《资源竞赛》（8438）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：无强重叠；风险：automatic_route_candidate_missing, fivebox_mechanic_unconfirmed, item_source_missing:20559, non_npc_finish_or_missing_finish, non_npc_start_or_missing_start, not_in_world_candidate_union。

### 雷霆崖

- 《晨光麦研究》（3786）— `needs_live_test` / `defer_until_evidence_or_live_test`；机制：item_source_not_in_questie；强重叠：3782；风险：active_item_or_spell_use, fivebox_mechanic_unconfirmed, item_source_missing:11040。

## 5. 给后续优化器的边界

- `confirmed`只代表静态字段内部一致，不代表任务已被最终选中。
- `needs_live_test`不得被自动改写成确认；可在路线候选中保留，但必须带止损或先做小样本实测。
- `exclude_from_current_outdoor_optimizer`只处理副本目标与当前户外目标冲突，不删除基础任务。
- 合并任务块时读取`known_overlap_task_ids`，但仍要分别处理个人掉落额外击杀、物体刷新和脚本等待。
