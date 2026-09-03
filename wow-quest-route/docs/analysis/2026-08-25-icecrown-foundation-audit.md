# 冰冠冰川基础任务层审计

- 当前状态：首组已80级并完成风暴峭壁；冰冠从一开始按满级一次性任务金币清理建模。
- 交通：不学习寒冷天气飞行；继续使用K3借用双足飞龙。13419《作战准备》保持排除，不作为冰冠运输入口。
- effective Northrend universe归属冰冠：279项；跨图任务链桥接：2项（[13078, 13343]）；物理touch：222项；touch-only=[12142, 12144, 12170, 12444, 24442]。
- 当前首轮路线候选：164项；状态统计：`{'exclude_cold_weather_flying_gate': 2, 'exclude_manual_non_executable': 22, 'exclude_route_economics': 2, 'exclude_unavailable_or_policy': 82, 'include_candidate': 153, 'include_first_run_repeatable_or_calendar': 11, 'knowledge_external_acquisition': 9}`。日常/重复只代表首轮一次，不生成第二轮循环。
- 候选任务80级XP折金小计：约1950.48G/角色；该数尚未包含普通直接金币和装备/物品变现，不能当整图最终金币。
- 冰冠内部强制依赖缺口：0。
- 经济待核：0项（XP折金=0且无已索引奖励物，直接金币尚未全局物化）；服务时间未知=0；objective review=0。
- 真实Target Cluster：173；多任务共享目标簇：29。

## 入口决策

- 从风暴峭壁进入冰冠时，第一地理区域仍是银色比武场；13419《作战准备》继续因寒冷天气飞行技能门槛排除，但不再影响银色北伐军主链。
- 13419《作战准备》：exclude_cold_weather_flying_gate。当前不学寒冷天气飞行，因此只排除该任务本身。
- 13227《审判日降临！》为实服确认的必经桥接；完成后13036《无上的荣耀》可正常接取，pre_any=[13227]。
- 13224《奥格瑞姆之锤》随该链正常解锁，当前状态=include_candidate，pre_any=[13157]；后续飞艇任务包恢复可达。
- 12892《乐趣十足》已由首组实跑确认可正常接取并完成，不再作为未决入口探针。

## 下一步

- 先清dependency/economy/objective-review待核项，形成可冻结scope。
- 再按真实目标簇、独立任务Hub、前置解锁与地图几何形成整图初始空间序列；随后逐簇插入并重放交通状态。
- 路线成稿前补齐五开共享/个人机制、component timing、semantic-hud-v45和玩家冷启动/几何/依赖门禁。
