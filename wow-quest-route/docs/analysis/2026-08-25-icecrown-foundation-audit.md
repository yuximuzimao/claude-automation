# 冰冠冰川基础任务层审计

- 当前状态：首组已80级并完成风暴峭壁；冰冠从一开始按满级一次性任务金币清理建模。
- 交通：不学习寒冷天气飞行；继续使用K3借用双足飞龙。13419《作战准备》保持排除，不作为冰冠运输入口。
- effective Northrend universe归属冰冠：279项；跨图任务链桥接：1项（[13078]）；物理touch：222项；touch-only=[12142, 12144, 12170, 12444, 24442]。
- 当前首轮路线候选：163项；状态统计：`{'exclude_cold_weather_flying_gate': 2, 'exclude_manual_non_executable': 22, 'exclude_route_economics': 2, 'exclude_unavailable_or_policy': 82, 'include_candidate': 151, 'include_first_run_repeatable_or_calendar': 12, 'knowledge_external_acquisition': 9}`。日常/重复只代表首轮一次，不生成第二轮循环。
- 候选任务80级XP折金小计：约1947.24G/角色；该数尚未包含普通直接金币和装备/物品变现，不能当整图最终金币。
- 冰冠内部强制依赖缺口：0。
- 经济待核：0项（XP折金=0且无已索引奖励物，直接金币尚未全局物化）；服务时间未知=0；objective review=0。
- 真实Target Cluster：173；多任务共享目标簇：29。

## 入口决策

- 13419《作战准备》：exclude_cold_weather_flying_gate。继续绕过该任务，但借用双足飞龙先去银色前线基地，不追移动飞艇。
- 首Hub：13036《无上的荣耀》，无显式前置，起点=[{'entity_type': 'npc', 'entity_id': 28179, 'name': '大领主提里奥·弗丁', 'x': 87.46, 'y': 75.83, 'spawn_count': 1}]。完成后同区打开13008/13039/13040三任务簇。
- 13227《审判日降临！》：80级XP折金3.24G/角色；会因先做13036失效。为它专程追飞艇再折回银色前线基地不划算，正式路线永久跳过。
- 13224《奥格瑞姆之锤》由pre_any=[13157]自然解锁，届时第一次登上奥格瑞姆之锤。
- 12892《乐趣十足》：Questie effective关系 pre_any=[] / pre_all=[] / parent_active=[] / available_starting_with=[] / required_spell=None。到13224自然登舰时再现场检查库尔迪拉是否给12892；若不给，只记录本服真实阻断，不把公开旧评论直接写成硬前置。

## 下一步

- 先清dependency/economy/objective-review待核项，形成可冻结scope。
- 再按真实目标簇、独立任务Hub、前置解锁与地图几何形成整图初始空间序列；随后逐簇插入并重放交通状态。
- 路线成稿前补齐五开共享/个人机制、component timing、semantic-hud-v45和玩家冷启动/几何/依赖门禁。
