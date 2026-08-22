# 达拉然基础任务层审计（77级血精灵圣骑士）

- 入口状态：从零路线按龙骨荒野整图完成后进入达拉然；12791《魔法王国达拉然》已携带。
- Questie：11.34.0 / 3c31d28a9c18189f3e245cdfb5b806210612e66da91c3661757c363724957861
- 旧式assigned-to-Dalaran仅9项；物理触碰达拉然召回128项；修正层提示37项；并集153项。
- 当前77级一次性正式池：5项；本地可闭合：2项；达拉然起点跨图面包屑：3项。
- scope状态：`{'boundary_turnin_only': 2, 'defer_live_unavailable': 1, 'exclude_faction': 53, 'future_level': 5, 'include_carried_in_now': 1, 'include_local_now': 1, 'include_outbound_breadcrumb_now': 3, 'knowledge_calendar_event': 4, 'knowledge_dungeon_or_raid': 31, 'knowledge_event_or_legacy_sort': 19, 'knowledge_off_axis_outbound': 3, 'knowledge_profession': 22, 'knowledge_pvp': 3, 'knowledge_repeatable_or_calendar': 3, 'knowledge_touch_only': 1}`。

## 当前正式池

- 12521《赫米特·奈辛瓦里哪去了？》｜Lv76｜include_outbound_breadcrumb_now｜startD=True finishD=False｜next=12489
- 12790《来去如风》｜Lv68｜include_local_now｜startD=True finishD=True｜next=None
- 12791《魔法王国达拉然》｜Lv74｜include_carried_in_now｜startD=False finishD=True｜next=12790
- 12853《豪华的体验！》｜Lv77｜include_outbound_breadcrumb_now｜startD=True finishD=False｜next=None
- 12974《勇士的召唤！》｜Lv75｜include_outbound_breadcrumb_now｜startD=True finishD=False｜next=12932

## 其它分类计数

- boundary_turnin_only: 2
- defer_live_unavailable: 1
- exclude_faction: 53
- future_level: 5
- knowledge_calendar_event: 4
- knowledge_dungeon_or_raid: 31
- knowledge_event_or_legacy_sort: 19
- knowledge_off_axis_outbound: 3
- knowledge_profession: 22
- knowledge_pvp: 3
- knowledge_repeatable_or_calendar: 3
- knowledge_touch_only: 1

## 发布前仍需完成

- 对6项当前正式池逐项核对NPC、触发动作、跨图目的地、是否立即执行/提前接取、任务日志成本。
- 单独审计三个物品触发达拉然交付任务的来源；没有触发物时不得让玩家主动在达拉然寻找接取NPC。
- 对80级后达拉然/冰冠链保留知识，不进入77级玩家路线。
- 完成Dalaran Hub几何顺序、预计时间、任务日志峰值、玩家冷启动和对抗式复审后，才能写入正式Route Atlas。
