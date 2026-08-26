# 冰冠冰川基础任务层审计

- 当前状态：首组已80级并完成风暴峭壁；冰冠从一开始按满级一次性任务金币清理建模。
- 交通：不学习寒冷天气飞行；继续使用K3借用双足飞龙。13419《作战准备》保持排除，不作为冰冠运输入口。
- effective Northrend universe归属冰冠：279项；跨图任务链桥接：1项（[13078]）；物理touch：222项；touch-only=[12142, 12144, 12170, 12444, 24442]。
- 当前首轮路线候选：61项；状态统计：`{'exclude_cold_weather_flying_gate': 2, 'exclude_dependency_on_blocked_task': 102, 'exclude_manual_non_executable': 22, 'exclude_route_economics': 2, 'exclude_unavailable_or_policy': 82, 'include_candidate': 55, 'include_first_run_repeatable_or_calendar': 6, 'knowledge_external_acquisition': 9}`。日常/重复只代表首轮一次，不生成第二轮循环。
- 候选任务80级XP折金小计：约771.33G/角色；该数尚未包含普通直接金币和装备/物品变现，不能当整图最终金币。
- 冰冠内部强制依赖缺口：0。
- 经济待核：0项（XP折金=0且无已索引奖励物，直接金币尚未全局物化）；服务时间未知=0；objective review=0。
- 真实Target Cluster：90；多任务共享目标簇：15。

## 入口决策

- 从风暴峭壁进入冰冠时，第一地理落点固定为地图东北的银色比武场；不再绕到东南银色前线基地作为入口。
- 13419《作战准备》：exclude_cold_weather_flying_gate。当前不学寒冷天气飞行，因此保持不可执行。
- 13036《无上的荣耀》已应用实服隐藏前置13419，当前状态=exclude_dependency_on_blocked_task，pre_any=[13419]；其独占后续必须递归传播不可达，不能再把它当独立根。
- 13224《奥格瑞姆之锤》当前状态=exclude_dependency_on_blocked_task，pre_any=[13157]；因此不能拿它解锁飞艇上的《破碎前线》《前往伊米海姆！》《萨隆邪铁的奴隶》《伊米亚之血》《协助突袭》。
- 12892《乐趣十足》仍是当前唯一需要现场直接核验的飞艇根候选：从银色比武场进入后直接前往奥格瑞姆之锤检查库尔迪拉；如果不可接，就把暗影拱顶组件整体从当前可执行路线剔除。

## 下一步

- 先清dependency/economy/objective-review待核项，形成可冻结scope。
- 再按真实目标簇、独立任务Hub、前置解锁与地图几何形成整图初始空间序列；随后逐簇插入并重放交通状态。
- 路线成稿前补齐五开共享/个人机制、component timing、semantic-hud-v45和玩家冷启动/几何/依赖门禁。
