# 诺森德视频反向路线审查（北风 / 龙骨 / 灰熊 / 祖达克）

- 视频只做共同任务顺序对照和遗漏审计，不覆盖部落五开任务事实、互斥、副本边界或实跑结果。
- 自动顺序比较只把视频明确完成与路线显式交付做对照；出现逆序是人工复查信号，不等于路线错误。
- 祖达克52—53集已同时用于基础任务池预审和正式路线整图反向审查；任何未解释的新逆序都会重新阻塞冻结。

## 北风苔原

- 视频：[34, 35, 36, 37, 38, 39]；视频不同任务132；当前路线任务名188；共同任务名63。
- 视频独有项分类：`{'expected_not_in_current_route_scope': 69}`。
- 可能属于正式池但路线缺失：0。
- 明确完成共同任务：62；可比较成对顺序1868；逆序141（仅报警）。
- 视频相邻共同任务在路线中反向：6组；未完成人工归因：0组。
- 整图视频反向审查状态：`pass_whole_map_video_reverse_review`。
- **相邻逆序候选：**
  - 视频 `情势扭转 → 决战奈辛瓦里`；路线交付点 `116 → 83`；人工结论：keep_current: video crosses a different Alliance map progression; current Horde route closes Nessingwary before the later Kaskala chain and does not create a shared local detour.
  - 视频 `先祖的回归 → 别让他们逃了！`；路线交付点 `99 → 95`；人工结论：keep_current: both Coldrock chains are active in the same local loop; their turn-in order differs but current route completes both without an extra revisit.
  - 视频 `敌人的耳环 → 帮助弱小`；路线交付点 `106 → 89`；人工结论：keep_current: Help the Weak is shared/fast and is turned in immediately; Earrings remains a background personal-drop task to avoid dedicated five-box farming.
  - 视频 `调查 → 监视裂谷：悬崖异常`；路线交付点 `158 → 155`；人工结论：keep_current: the rift task is already available on Amber Ledge arrival while Investigation unlocks after the jailbreak return; the current order follows availability and the same hub cycle.
  - 视频 `重铸钥匙 → 监视裂谷：峭壁断层`；路线交付点 `161 → 158`；人工结论：keep_current: the cliff-fault objective is completed on the outbound local pass; Reforging the Key unlocks later through the interrogation/time-race chain at the same hub.
  - 视频 `监视裂谷：冬鳞洞穴 → 侦查虫孔`；路线交付点 `220 → 123`；人工结论：keep_current: these belong to separate Taunka/Winterfin phases; video episode order is not a local adjacency claim. Current route carries the rift quest through the north loop and uses the opened flight network for its final turn-in.

## 龙骨荒野

- 视频：[40, 41, 42]；视频不同任务48；当前路线任务名147；共同任务名36。
- 视频独有项分类：`{'expected_not_in_current_route_scope': 12}`。
- 可能属于正式池但路线缺失：0。
- 明确完成共同任务：31；可比较成对顺序459；逆序8（仅报警）。
- 视频相邻共同任务在路线中反向：4组；未完成人工归因：0组。
- 整图视频反向审查状态：`pass_whole_map_video_reverse_review`。
- **相邻逆序候选：**
  - 视频 `搜索因度雷村 → 不要浪费`；路线交付点 `87 → 83`；人工结论：keep_current: video begins this section already on the Indu'le line. The Horde route from Agmar first reaches Moa'ki to unlock Don't Waste and the Kalu'ak chain, then threads back through Indu'le while those tasks are active; no duplicate standalone Indu'le revisit is introduced.
  - 视频 `图尔凯的螃蟹陷阱 → 长者玛纳洛`；路线交付点 `96 → 88`；人工结论：keep_current: both are accepted from the same Moa'ki visit; current route advances Mana'loa/Indu'le before sweeping the southern coast so crab traps are collected along the coast loop instead of forcing an early shoreline return.
  - 视频 `魔网能量线的终端 → 海洋女神`；路线交付点 `99 → 96`；人工结论：keep_current: the ley-line quest stays active while the coastal Ocean Goddess chain is closed, then is turned after the Moa'ki-to-Agmar flight; this batches the return transport rather than adding a separate Agmar trip.
  - 视频 `向德弗雷斯塔兹领主报到 → 红玉巨龙圣地的命运`；路线交付点 `123 → 121`；人工结论：keep_current: both resolve inside Wyrmrest/Ruby chain state; the video Alliance unlock order differs, while the current route turns the Ruby Brooch as soon as it is obtained and immediately continues the same tower/hub chain.

## 灰熊丘陵

- 视频：[47, 48, 49, 50, 51]；视频不同任务90；当前路线任务名83；共同任务名42。
- 视频独有项分类：`{'video_faction_or_other_zone_only': 48}`。
- 可能属于正式池但路线缺失：0。
- 明确完成共同任务：40；可比较成对顺序768；逆序157（仅报警）。
- 视频相邻共同任务在路线中反向：8组；未完成人工归因：0组。
- 整图视频反向审查状态：`pass_whole_map_video_reverse_review`。
- **相邻逆序候选：**
  - 视频 `解读象形文字 → 清理天灾`；路线交付点 `15 → 14`；人工结论：keep_current: both lie on the same westward Drakuru/Forgotten-depths sweep; current route takes the nearby mummified-crusader branch before the first brazier with no later revisit.
  - 视频 `蘑菇汤！ → 古树精华宝石`；路线交付点 `24 → 19`；人工结论：keep_current: Mushroom Soup is collected as a background task while the route continues east with the Drakuru gem chain; its delayed turn-in avoids returning to Granite Springs solely for the soup.
  - 视频 `灰尘之声 → 跟我的小朋友打招呼`；路线交付点 `52 → 39`；人工结论：keep_current: both are long-carried tasks whose turn-in order reflects different endpoints; the route hands Little Friend at Harkor when first entering the northeast, while Dust Voice waits for the later Drakil'jin spatial instance.
  - 视频 `等肉下锅 → 心灵的创伤`；路线交付点 `69 → 53`；人工结论：keep_current: Meat for the Pot is intentionally background-collected through later northeast/giant terrain; Healing with Herbs closes earlier when its local targets finish, avoiding dedicated meat farming.
  - 视频 `金亚拉克的末日 → 破损的日记`；路线交付点 `55 → 32`；人工结论：keep_current: the diary is collected/turned during the earlier Thor Modan pass; Jin'arrak is a later Harkor/Drakil'jin chain. Video's Alliance macro traversal reaches these chains in the opposite order.
  - 视频 `攻破防线 → 卢娜的要求`；路线交付点 `38 → 26`；人工结论：keep_current: Luna is closed before the northern giant chain because it is already available on the route into Onu'va; Break Through is a later strict giant-chain continuation, so swapping them would delay an already-open local loop.
  - 视频 `……我们没有能源 → 可能的关联`；路线交付点 `65 → 34`；人工结论：keep_current: Possible Link is an earlier Vordrassil/Conquest Hold chain and is intentionally closed before the late Dun Argol golem chain. Video Alliance hub progression unlocks the counterpart later.
  - 视频 `终获解救 → 沃达希尔的种子`；路线交付点 `70 → 44`；人工结论：keep_current: Vordrassil Seeds is completed in the mid-map Vordrassil pass and immediately unlocks the bear-god continuation; Free at Last is the terminal northern giant-chain task and cannot justify delaying the earlier tree pass.

## 祖达克

- 视频：[52, 53]；视频不同任务43；当前路线任务名105；共同任务名42。
- 视频独有项分类：`{'video_faction_or_other_zone_only': 1}`。
- 可能属于正式池但路线缺失：0。
- 明确完成共同任务：37；可比较成对顺序655；逆序35（仅报警）。
- 视频相邻共同任务在路线中反向：5组；未完成人工归因：0组。
- 整图视频反向审查状态：`pass_whole_map_video_reverse_review`。
- **相邻逆序候选：**
  - 视频 `风暴将至 → 圣光不能为我复仇`；路线交付点 `10 → 7`；人工结论：keep_current: Vargul Revenge is completed beside Gork during the same missing-crusader sweep, so turning it in immediately costs no revisit. Reproducing the video completion order would require carrying it away from its local turn-in and returning later.
  - 视频 `希姆埃巴的祝福 → 银色北伐军的降落伞`；路线交付点 `59 → 39`；人工结论：keep_current: Zim'Abwa requires personal Drakkari Offerings. The five-box route keeps this as background accumulation through the southern Drakkari loops and closes it on the final south return instead of forcing a dedicated early personal-drop farm.
  - 视频 `银色北伐军的降落伞 → 潜入沃尔塔鲁斯`；路线交付点 `39 → 28`；人工结论：keep_current: after the Gymer material loop the route is already back at Ebon Watch with Infiltrating Voltarus unlocked. Closing the phased Ebon chain before the one-way east transition avoids the video's later Ebon revisit after Argent Stand.
  - 视频 `给斯塔哈默中士的新命令 → 实验室的学徒`；路线交付点 `44 → 40`；人工结论：keep_current: both orders are dependency-legal, but the current Argent→Heb'Valok→spirits→Heb'Valok→Sseratus→bat→Heb'Valok→Argent loop is about 76.3 map-percent versus about 84.3 for the video-shaped Sseratus-first alternative using the same route anchors.
  - 视频 `温暖的篝火 → 扔手雷`；路线交付点 `62 → 52`；人工结论：keep_current: Throwing Down is turned in early specifically to unlock Cocooned, allowing Cocooned and One of a Kind? rescue targets to share one rescue pass. Creature Comforts remains a background wood collection and is turned later near the mushroom/basilisk return, avoiding a dedicated Drak'Jin wood loop.
