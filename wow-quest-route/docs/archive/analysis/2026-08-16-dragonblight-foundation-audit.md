# 龙骨荒野任务基础与攻略备注预审（未开始插路线）

## 边界

- 本轮只建立任务事实、前置边界、目标簇、特殊机制与攻略备注判定；未做任务插入、路线排序、炉石优化或HTML改动。
- 北风自然入口为11930《横贯冰原》；12117《前往莫亚基港口》跨图携带，到莫亚基港口自然交。
- Questie 11.34.0 effective facts；入口等级下限按71，第一遍纳入requiredLevel≤74，更高等级门槛保留后续回访候选。
- 视频40—42集只作为单号地点/任务机制证据；视频角色为联盟，不能直接证明部落ID、五开共享或五开耗时。

## 基础统计

- primary候选：266；连同一跳前置/后续边界：278。
- scope：`{'defer_future_level_revisit': 11, 'defer_to_80_after_live_failure': 3, 'exclude_alliance_or_other_faction': 87, 'exclude_current_entry_axis_alternate': 3, 'exclude_deprecated_or_system': 1, 'exclude_no_xp': 4, 'exclude_other_class': 1, 'exclude_profession': 1, 'exclude_removed_or_unavailable': 4, 'exclude_repeatable_calendar': 3, 'include_cross_map_inbound': 2, 'include_cross_map_outbound': 4, 'include_leveling_cross_map': 1, 'include_leveling_dungeon': 4, 'include_leveling_local': 136, 'include_structural_zero_xp_prerequisite': 1}`。
- 精确目标簇：133；多任务共享目标簇：34。
- 最终攻略备注判定：`{'must_note': 76, 'not_route_candidate': 122, 'review_before_route': 1, 'reviewed_no_extra_note': 67}`。
- 当前纳入范围 must_note=76，review_before_route=1，reviewed_no_extra_note=67，manual_review_pending=0。
- 仍需首组五开实测或交通核验的后台机制项=107；这些不等于都要显示在玩家攻略里。

## 必须写攻略备注的任务

- 11930《横贯冰原》：Escort the Taunka evacuees across the Borean/Dragonblight boundary to Vortuk; this is the natural map handoff.；首组待核验：fivebox escort completion sharing, failure/reset behavior。
- 11959《消灭洛根》：Kill/loot Loguhn, then actively use Blood of Loguhn on yourself before returning; killing him alone is insufficient.；首组待核验：whether each character must loot/use separately。
- 11983《部落的血誓》：This is dialogue interaction with Westwind Taunka refugees: continue the conversation until each oath/progress credit is granted; it is not a normal kill/loot quest.；首组待核验：fivebox dialogue progress sharing vs per-character。
- 11999《寻找线索》：Loot a dead Mage Hunter corpse for Personal Effects, then open/right-click the effects until the Moonrest Gardens Plans are obtained.；首组待核验：corpse/item loot mode across five characters。
- 12011《大麻烦的征兆》：At the southwest Moa'ki dock, use the breathing aid/dive to the wrecked crab trap and interact with it to obtain/start the damaged-trap follow-up.；首组待核验：fivebox object/item interaction mode。
- 12017《鱼钩上的肉》：Follow the fishing line to the hook, use the bait at the hook to summon Tugowar, then kill him.；首组待核验：whether summon/kill credit is shared for all five。
- 12028《灵魂视界》：Use the Spiritual Incense at the brazier immediately outside Toalu'u's tent; it triggers a scripted spirit-vision/flight sequence and normally needs no steering.；首组待核验：fivebox object/use action shared vs per-character。
- 12032《海洋女神》：Go to the deep-sea pearl, interact with it, follow the sea-goddess script, and when the compulsion/buff prompts you, jump into the water to continue the trial.；首组待核验：whether each character must trigger the scripted sequence。
- 12033《萨鲁法尔的信》：Read Saurfang's letter, then destroy/burn it using the nearby firepot before speaking to the messenger.；首组待核验：per-character use requirement。
- 12036《艾卓-尼鲁布的深渊》：Narjun's Pit is below ground; descend through one of the pit openings/holes and explore the lower pit rather than searching only at the surface coordinate.；首组待核验：safe fivebox descent/follow path。
- 12040《阿尔萨斯的死敌》：The target area is inside Narjun's Pit; reach Kilix in the lower pit and kill Anub'ar Underlords there. Surface map coordinates alone are insufficient.；首组待核验：fivebox descent/pathing。
- 12049《难以下咽》：Fight a Hulking Jormungar to roughly low health until it opens its mouth, then use the explosive during the mouth-open window; loot the charred meat after the explosion.；首组待核验：fivebox loot mode, whether one explosion can credit multiple characters。
- 12050《抢木材》：Use the shredder controller in the harpy area to summon/operate the shredder; collect marked lumber/trees with the vehicle and re-summon if the shredder is lost.；首组待核验：vehicle ownership per character, fivebox lumber credit mode。
- 12052《该死的鹰身人！》：Do this in the same harpy/shredder area as 12050; kill Mistress of the Coldwind and the required harpies. Keep the shredder mechanics in view because both quests naturally share the area.；首组待核验：ordinary kill sharing expected but verify current server。
- 12053《部落的力量》：Plant the Warsong battle standard at Icemist Village and defend it until the event completes; do not leave after merely placing the banner.；首组待核验：group completion sharing, failure/reset radius。
- 12057《血之魔典》：The Flesh-Bound Tome is a monster-dropped quest-start item from Anub'ar cultist/named mobs in the Icemist/Narjun area; loot it and right-click it to start the quest.；首组待核验：drop rate/source priority, same-corpse fivebox loot mode。
- 12059《奇怪的设备》：Goramosh drops the Strange Device; loot and right-click the device to start the quest. Do not treat it as an NPC pickup.；首组待核验：same-corpse fivebox loot mode。
- 12061《投影和计划》：Use the teleporter at Moonrest Gardens to reach the projection area, then move forward/observe until the scripted projection credit fires.；首组待核验：whether each character must trigger the teleporter/event。
- 12064《阿努巴尔的束缚》：Three named Icemist targets carry separate key fragments; Anok'ra is on the lower/ground level while Sinok/Tivax can be at different points. Collect all fragments before returning.；首组待核验：same-corpse fivebox fragment loot mode。
- 12066《海岸上的魔法焦点》：Kill Captain Emmy Malin for the Ley Line Focus Control Ring, then use the ring at the large ley-line focus arch on the coast to read the focus.；首组待核验：fivebox ring loot/use mode。
- 12069《大酋长归来》：Use the Anub'ar prison key to free the Taunka chieftain, help him fight Anub'ekhan, then loot the required carapace fragment; this is a rescue/event plus boss sequence.；首组待核验：event sharing, boss loot mode。
- 12072《该死的荒芜兽！》：Use the flare at Icemist Village to summon/mount a Kor'kron War Rider; use the vehicle abilities to kill the blightbeasts and return after the vehicle segment.；首组待核验：vehicle must be run per character vs shared kill credit。
- 12075《采集样本》：The sample is taken from a ravaged crystalline giant corpse near/below the Crystal Vice cave entrance; click the corpse, not living giants.；首组待核验：object sharing vs personal。
- 12076《恶心的生意》：Use Zort's Scraper on yourself when the worm applies/casts Corrosive Spit; repeat until two saliva samples are collected.；首组待核验：each character must be spat on/use scraper separately。
- 12078《抓虫子》：Inside the Crystal Vice cave, place/use the crate near a Jormungar Spawn; after the larva enters, pick/right-click the crate on the ground. Repeat for all three.；首组待核验：crate/object state shared vs personal。
- 12079《践踏大地》：The feeders are inside the northern Crystal Vice cave; use the cave entrance/path from the Crystal Vice task block rather than chasing surface coordinates.；首组待核验：fivebox cave pathing only。
- 12080《冰虫之母》：Rattlebore is inside the Crystal Vice cave; use Zort's protective elixir if available to reduce the acid hazard before the named kill.；首组待核验：whether protective item is per character。
- 12084《森林上空》：Lieutenant Ta'zinni drops the Ley Line Focus Control Amulet; use the amulet at the Lothalor Forest ley-line focus arch to obtain the reading.；首组待核验：same-corpse fivebox amulet loot mode, per-character use。
- 12085《一封家书》：Lieutenant Ta'zinni also drops the Horde letter; loot and right-click the letter to start 12085《一封家书》.；首组待核验：same-corpse fivebox quest-start-item loot mode。
- 12096《强化古树》：Obtain Woodlands Walker Bark in Lothalor and use the bark on the non-hostile/eligible Lothalor Ancients to empower them; this is an item-on-NPC action, not a normal kill.；首组待核验：fivebox item use sharing vs per-character。
- 12110《魔网能量线的终端》：Use the ley-line talisman at the Indu'le Lake focus, then continue to the Azure Dragonshrine observation point; both spatial checks are required.；首组待核验：per-character use/area trigger。
- 12111《野生动物的疫苗》：Use the vaccine package on living Snowfall Elk and Arctic Grizzlies; it is an item-use vaccination quest, not a kill quest.；首组待核验：fivebox credit sharing vs per-character。
- 12124《通知女王》：This Wyrmrest Temple handoff requires reaching the correct temple level; use the temple drake/taxi NPC to reach the upper level rather than searching the ground floor.；首组待核验：exact floor/NPC handoff for Horde branch。
- 12125《邪能之约》：Reduce a Deranged Indu'le Villager below the required health threshold, then use the Blood Gem on the weakened target to charge it.；首组待核验：per-character gem use。
- 12126《邪恶之约》：Use the Unholy Gem on Duke Vallenhal as instructed to charge it; do not simply kill the target first.；首组待核验：per-character gem use。
- 12127《冰霜之约》：Use the Frost Gem on the specified frost spirit target to charge it; this is a targeted quest-item action.；首组待核验：per-character gem use。
- 12132《毁灭的力量》：Enter the World of Shadows via Koltira's effect/dialogue, kill the Shadowy Tormentors there, then leave the phase/realm when finished rather than searching for them in normal Dragonblight.；首组待核验：phase entry per character, kill sharing inside phased state。
- 12140《洛纳乌克万岁！》：Follow the Agmar/Roanauk script and exhaust Roanauk's dialogue/conversation until the allegiance event completes; it is not a normal single named kill despite database simplification.；首组待核验：fivebox event/dialogue sharing。
- 12145《峡谷追击》：Follow the snobold trail through the canyon to Icefist rather than searching only the final coordinate; kill Icefist at the end of the trail.；首组待核验：无额外未决项。
- 12147《古怪的暗示》：Icefist drops the Ornate Battle Horn; loot and right-click the horn to start this quest, then take it to Wyrmrest Temple for evaluation.；首组待核验：same-corpse fivebox horn loot mode。
- 12149《强大的猛犸人》：The three magnataur are spread around Wyrmrest and are not identical fights; Ice Shatter has a dangerous channel, and Bloodfeast can heal from nearby maggots. Treat them as three named stops, not one generic kill area.；首组待核验：无额外未决项。
- 12150《隐居的铭语师》：Reach the runemaster on the cliff/cave side of the Mirror of Dawn; fight him only until the scripted surrender/immunity/quest update occurs. Do not keep trying to kill through the immune phase; avoid the purple runes.；首组待核验：group credit on scripted surrender。
- 12151《暴虐的酋长》：Use the Ornate Battle Horn at the Torch Ring south of Azure Dragonshrine to summon Grom'thar; fight away from the cliff because the encounter has knockback risk.；首组待核验：summon/kill credit sharing。
- 12206《测试药剂》：Stand by a Scarlet prisoner/soldier and use the blight flask on the target as instructed; the quest is item-use testing, not a normal kill.；首组待核验：per-character item use。
- 12211《确保他们不再站起来！》：Kill Scarlet Onslaught members, then use the Container of Rats on their corpses; corpse use is required for progress.；首组待核验：whether multiple characters can use the same corpse sequentially。
- 12214《补充坐骑》：Kill an Onslaught Knight to obtain a riding crop, use the crop on the riderless horse, mount it, ride back to Venomspite, and use vehicle ability 1 to deliver the horse. Killing horses directly is wrong.；首组待核验：crop loot mode, horse delivery must be repeated per character vs shared。
- 12218《传达好消息》：Mount the Forsaken Blight Spreader at Venomspite's east side/gate and use the vehicle blight bombs to kill the required Scourge outside the camp.；首组待核验：vehicle run per character vs shared kill credit。
- 12232《炸毁弩炮》：Use the collected siege bombs on New Hearthglen ballistae; the ballistae are fixed targets and must be bombed rather than attacked normally.；首组待核验：fivebox bomb/object progress sharing。
- 12234《日常计划》：The three Daily Orders are in different New Hearthglen buildings/rooms, including barracks/abbey interiors; use building/floor notes instead of treating them as one flat coordinate cluster.；首组待核验：object loot mode。
- 12240《解决方案》：Use the Levine-family termites at the lumbermill/lumber pile to force Foreman Kaleiki out, then kill him.；首组待核验：summon ownership/kill sharing。
- 12243《水火之灾》：Burn the ship's sails with the burning liquid, then use the short distraction window to go below deck, navigate the ship interior, kill Captain Shely, and loot the charts.；首组待核验：per-character sail/item credit, interior fivebox pathing。
- 12245《毫不留情》：These named Scarlet targets are not ordinary kill credits: interact/talk as required to expose/trigger them, then kill them. Check each named NPC rather than mass-killing nearby soldiers.；首组待核验：dialogue trigger sharing。
- 12252《拷问者里克拉夫》：Torturer LeCraft/Alphonse is inside the barracks/basement area; use the branding/interrogation tool five times to get the information before killing/finishing the sequence.；首组待核验：per-character interrogation progress。
- 12260《完美的伪装》：Use the Banshee's Magic Mirror on an Onslaught Raven Priest to steal/copy the disguise image; this is a targeted quest-item action.；首组待核验：per-character mirror use。
- 12261《无路可逃》：At the Obsidian Dragonshrine exit/edge where the road becomes snowy, place the Destructive Ward and defend it until it finishes charging; placement alone does not complete the quest.；首组待核验：group completion sharing, failure/reset。
- 12263《敌人的意图》：Serinar disguises you as a cultist; travel through the Maw of Neltharion cave while disguised to the deep cult area to observe their intent. If the disguise is lost, return/reapply rather than searching outside the cave.；首组待核验：disguise per character, area-trigger sharing。
- 12264《扫荡诅咒教派》：The cultist targets are inside the Maw of Neltharion cave; combine with the same cave pass as 12263/12265/12267 rather than reading flat map coordinates.；首组待核验：无额外未决项。
- 12265《污染的能量》：Inside the Maw of Neltharion cave, right-click/destroy the necromantic runes; they are fixed cave objects, not surface targets.；首组待核验：fivebox object sharing vs personal。
- 12267《奈萨里奥的烈焰》：Go deep into the Maw of Neltharion, use Neltharion's Flame on the summoning area to trigger/cleanse it and draw out Rothin the Decaying, then kill him.；首组待核验：per-character flame use, boss credit sharing。
- 12271《强制魔棒》：The Torturer's Rod is a dropped quest-start item from the Scarlet torturer chain; loot and right-click it to start 12271 before returning to Venomspite.；首组待核验：same-corpse fivebox rod loot mode。
- 12273《谴责》：Find each named Scarlet official in the specified building/floor, use the Rod of Compulsion, wait for the denunciation/script, then kill the target.；首组待核验：per-character rod use, dialogue/event sharing。
- 12274《狼狈不堪》：In disguise, enter the abbey, go up the spiral stairs to ring the bell rope, then return downstairs and speak to/follow the high abbot for the information. Onslaught Knights can see through the disguise.；首组待核验：fivebox disguise/pathing, bell/dialogue progress sharing。
- 12283《寻找真相》：Abbendis's diary is inside an upper-floor room of the house near the chapel; vertical/building location matters more than the flat coordinate.；首组待核验：world-object sharing vs personal。
- 12419《红玉巨龙圣地的命运》：This turn-in is tied to the Ruby Dragonshrine fate chain and uses the recovered ruby brooch; keep the item/chain provenance explicit so it is not mistaken for a standalone Wyrmrest pickup.；首组待核验：exact Horde predecessor item source。
- 12435《向德弗雷斯塔兹领主报到》：Wyrmrest Temple has multiple vertical levels; after the Queen/top-level handoff, use the temple drake/taxi or correct level transfer to reach Lord Devrestrasz on the proper level.；首组待核验：exact Horde floor/transfer。
- 12447《黑曜石巨龙圣地》：Serinar is inside/at the Maw of Neltharion cave in the Obsidian Dragonshrine area; use the cave entrance rather than searching the surface marker.；首组待核验：fivebox cave approach。
- 12449《重归尘土》：Enter Ruby Dragonshrine from the south path, collect/use Ruby Acorns on dead red dragons so the corpses return to the earth; this is item-on-corpse interaction.；首组待核验：same corpse usable by multiple characters vs per-character objects。
- 12450《烈焰之地》：Use the south approach into Ruby Dragonshrine; besides killing necromancers, destroy the corruption/source below the shrine. The second objective is not satisfied by kills alone.；首组待核验：object/event sharing。
- 12456《奥雷托斯的羽毛》：Use the Skytalon Molts at the southeast glade to summon Alystros, then kill and loot the plume; the named target is summoned rather than simply standing at the map point.；首组待核验：summon ownership, same-corpse plume loot mode。
- 12459《创造与毁灭的力量》：Each named target must first be weakened with Seeds of Nature's Wrath and then killed; the targets are in separate locations, including a flying frost wyrm. Do not kill them before applying the seed.；首组待核验：per-character seed use vs shared weakened state。
- 12470《永恒之龙的秘密》：Place/use the Hourglass of Eternity inside Bronze Dragonshrine to start a timed defense/event; protect it through the waves until the information is obtained. A Future You NPC may assist/tank.；首组待核验：event completion sharing, failure/reset。
- 12496《巨龙女王的指引》：The Dragon Queen is on the upper Wyrmrest Temple level; ask/use the temple transport NPC to be sent upward instead of searching the ground floor.；首组待核验：无额外未决项。
- 12498《红龙之翼》：Use the Ruby Beacon to mount a ruby drake, use vehicle abilities to kill the required Scourge, then complete the boss/scythe sequence before returning to the Queen.；首组待核验：vehicle run per character vs shared kills, scythe loot mode。
- 12767《与你们的大使相谈》：Wyrmrest Temple is multi-level; confirm the Horde ambassador's correct temple level before leaving the transport NPC, rather than relying on the flat coordinate.；首组待核验：exact level。
- 12769《龙眠神殿的执事》：Speak to Tariolstrasz at Wyrmrest and use his drake/temple transport options to move between temple levels; this is the access mechanism for several follow-ups.；首组待核验：无额外未决项。
- 13242《黑暗的骚动》：Post-Wrathgate continuation: collect Saurfang's battle armor on the battlefield, then carry it back across maps to Saurfang at Warsong Hold. This is not part of the initial Dragonblight opening block.；首组待核验：exact unlock after 12500 and current-server event state。

## 插入前仍需交通/条件复核但不先写死攻略

- 12791《魔法王国达拉然》：Outbound Dalaran breadcrumb/transport task; keep it in boundary data but decide insertion only after comparing the Dragonblight endpoint and actual transport value.；待核验：whether the NPC directly teleports current-server characters, future-route cost。

## 停止点

- 到这里为止只完成基础层。等用户明确通知后，才从第一个Target Cluster开始逐任务插入。
- 插入时不得重新把当前首组状态裁进Route Atlas；首组状态只用于CURRENT恢复与实跑反馈。
- 龙骨荒野仍加入统一Route Atlas工作台，不创建独立HTML。
