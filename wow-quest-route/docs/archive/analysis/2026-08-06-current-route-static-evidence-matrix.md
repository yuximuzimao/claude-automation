# 当前39—55路线逐任务静态证据矩阵

> 此表只压缩Questie与AzerothCore参考数据；公开玩家评论、本服实测和地点密度证据需在后续人工审计列补齐。

- 路线任务：102个。
- 已定位基础记录：97个。
- 基础表缺失：3441, 3453, 4141, 4245, 4491。

| ID | 任务 | 地图 | 要求/任务等级 | 机制、数量、五开模式、来源 | 参考概率 | 前置→后续 | 静态风险 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1117 | 地精的谣言 | 千针石林 | 30/36 | 无目标/跑腿 | — | 1116→— | — |
| 1183 | 地精赞助商 | 千针石林 | 29/37 | 无目标/跑腿 | — | 1182→1186 | — |
| 1186 | 第十八个驾驶员 | 千针石林 | 29/37 | 无目标/跑腿 | — | 1183→1187 | — |
| 1187 | 拉泽瑞克的调整 | 千针石林 | 29/41 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Gizmorium Shipping Crate) | Gizmorium Shipping Crate:100.0% | 1186→1188 | — |
| 1190 | 跟上节奏 | 千针石林 | 29/41 | 无目标/跑腿 | — | 1137→1194 | — |
| 1194 | 瑞兹尔的图表 | 千针石林 | 29/41 | 无目标/跑腿 | — | 1190→— | — |
| 10 | 谢申克的救赎 | 塔纳利斯 | 39/48 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Scrimshank's Surveying Gear) | Scrimshank's Surveying Gear:100.0% | 82→110 | — |
| 82 | 腐化之巢 | 塔纳利斯 | 39/47 | multiple_creature_task_item_drops×5[personal_loot_roll_per_character_expected](森提帕尔异种蝎/森提帕尔毒刺蝎/森提帕尔群居蝎) | 森提帕尔异种蝎:80.0%; 森提帕尔毒刺蝎:80.0%; 森提帕尔群居蝎:80.0%; 森提帕尔工蝎:80.0%; 森提帕尔掘洞蝎:80.0%; 森提帕尔沙行者:80.0% | 992→— | server_drop_rate_needed |
| 654 | 塔纳利斯的样本 | 塔纳利斯 | 38/46 | multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](晶鳞蜥蜴/晶鳞凝视者/晶鳞石化蜥蜴); multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](饥饿的疱爪土狼/疱爪土狼/疯狂的疱爪土狼); multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](沙漠猎食蝎/沙漠鞭尾蝎/沙漠疾行蝎) | 晶鳞蜥蜴:100.0%; 晶鳞凝视者:100.0%; 晶鳞石化蜥蜴:100.0%; 饥饿的疱爪土狼:100.0%; 疱爪土狼:100.0%; 疯狂的疱爪土狼:100.0%; 残忍的疱爪土狼:100.0%; 沙漠猎食蝎:100.0%; 沙漠鞭尾蝎:100.0%; 沙漠疾行蝎:100.0% | 379→864 | server_drop_rate_needed |
| 992 | 加基森水业公司 | 塔纳利斯 | 38/46 | item_source_not_in_questie×1[unknown_or_supplied_item](source?) | — | —→82 | item_source_missing:8585 |
| 1690 | 废土的公正 | 塔纳利斯 | 40/43 | regular_shared_kills×10[kill_progress_shared_expected](废土强盗); regular_shared_kills×?[kill_progress_shared_expected](废土窃贼) | — | —→1691 | objective_count:missing_counts |
| 1691 | 废土的公正 | 塔纳利斯 | 40/44 | regular_shared_kills×10[kill_progress_shared_expected](废土游荡者); regular_shared_kills×8[kill_progress_shared_expected](废土刺客); regular_shared_kills×6[kill_progress_shared_expected](废土暗法师) | — | 1690→— | — |
| 1707 | 收集水袋 | 塔纳利斯 | 40/44 | multiple_creature_task_item_drops×5[personal_loot_roll_per_character_expected](废土游荡者/废土窃贼/废土暗法师) | 废土游荡者:35.0%; 废土窃贼:35.0%; 废土暗法师:35.0%; 废土强盗:35.0%; 废土刺客:35.0%; 安德雷·费尔比德:35.0% | —→— | server_drop_rate_needed |
| 2781 | 通缉：卡利夫·斯科比斯汀 | 塔纳利斯 | 38/46 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](卡利夫·斯科比斯汀) | 卡利夫·斯科比斯汀:100.0% | —→— | — |
| 2872 | 斯杜雷的债务 | 塔纳利斯 | 40/45 | 无目标/跑腿 | — | —→2873 | — |
| 2873 | 斯杜雷的货物 | 塔纳利斯 | 40/45 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Stolen Cargo) | Stolen Cargo:100.0% | 2872→2874 | — |
| 2875 | 通缉：安德雷·费尔比德 | 塔纳利斯 | 38/45 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](安德雷·费尔比德) | 安德雷·费尔比德:100.0% | —→— | — |
| 5863 | 砂槌食人魔 | 塔纳利斯 | 44/49 | regular_shared_kills×10[kill_progress_shared_expected](砂槌蛮兵); regular_shared_kills×10[kill_progress_shared_expected](砂槌执行者); regular_shared_kills×?[kill_progress_shared_expected](掠夺者格玛洛克) | — | —→— | objective_count:missing_counts |
| 8365 | 海盗的帽子！ | 塔纳利斯 | 40/45 | multiple_creature_task_item_drops×20[personal_loot_roll_per_character_expected](南海海盗/南海劫掠者/南海码头工人) | 南海海盗:80.0%; 南海劫掠者:80.0%; 南海码头工人:80.0%; 南海流氓:80.0%; 安德雷·费尔比德:80.0%; 克雷格·尼哈鲁:80.0%; 南海绑匪:6.0% | —→— | server_drop_rate_needed |
| 8366 | 南海复仇 | 塔纳利斯 | 40/45 | regular_shared_kills×10[kill_progress_shared_expected](南海海盗); regular_shared_kills×10[kill_progress_shared_expected](南海劫掠者); regular_shared_kills×10[kill_progress_shared_expected](南海码头工人); regular_shared_kills×10[kill_progress_shared_expected](南海流氓) | — | —→— | — |
| 974 | 究根问底 | 安戈洛环形山 | 51/55 | single_named_or_rare_kill×1[kill_progress_shared_expected](克拉兰克的温度计) | — | —→980 | — |
| 980 | 新的泉水 | 安戈洛环形山 | 51/55 | 无目标/跑腿 | — | 974→4842 | — |
| 3844 | 无人知晓的秘密 | 安戈洛环形山 | 47/52 | 无目标/跑腿 | — | —→3845 | — |
| 3845 | 无人知晓的秘密 | 安戈洛环形山 | 47/52 | item_source_not_in_questie×?[unknown_or_supplied_item](source?); item_source_not_in_questie×?[unknown_or_supplied_item](source?); item_source_not_in_questie×?[unknown_or_supplied_item](source?) | — | 3844→3908 | item_source_missing:11104,item_source_missing:11105,item_source_missing:11106,objective_count:missing_counts |
| 3881 | 抢救物资 | 安戈洛环形山 | 48/53 | task_item_world_object_pickup×?[item_pickup_per_character_expected](Crate of Foodstuffs); task_item_world_object_pickup×?[item_pickup_per_character_expected](Research Equipment) | Crate of Foodstuffs:100.0%; Research Equipment:100.0% | —→— | objective_count:missing_counts |
| 3882 | 挖骨头 | 安戈洛环形山 | 49/51 | multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](剑龙/厚甲剑龙/刺尾剑龙) | 剑龙:30.0%; 厚甲剑龙:30.0%; 刺尾剑龙:30.0%; 雷霆剑龙:30.0%; 幼双帆龙:30.0%; 双帆龙:30.0%; 老双帆龙:30.0% | —→— | server_drop_rate_needed |
| 3883 | 异型的生态 | 安戈洛环形山 | 48/52 | item_source_not_in_questie×1[unknown_or_supplied_item](source?) | — | —→— | item_source_missing:11131 |
| 3908 | 无人知晓的秘密 | 安戈洛环形山 | 47/52 | 无目标/跑腿 | — | 3845→— | — |
| 4243 | 找回A-Me 01 | 安戈洛环形山 | 48/53 | 无目标/跑腿 | — | —→4244 | — |
| 4244 | 找回A-Me 01 | 安戈洛环形山 | 48/53 | single_regular_creature_task_item×1[personal_loot_roll_per_character_expected](科朗克/霜狼伐木机/雷矛伐木机) | 科朗克:4.0498%; 霜狼伐木机:8.0%; 雷矛伐木机:19.04%; 7:XT:12.1212% | 4243→— | — |
| 4284 | 能量水晶 | 安戈洛环形山 | 47/53 | multiple_creature_task_item_drops×7[personal_loot_roll_per_character_expected](魔暴龙/铁皮魔暴龙/霸王魔暴龙); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](魔暴龙/铁皮魔暴龙/霸王魔暴龙); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](魔暴龙/铁皮魔暴龙/霸王魔暴龙); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](魔暴龙/铁皮魔暴龙/霸王魔暴龙) | 魔暴龙:0.02%; 铁皮魔暴龙:0.02%; 霸王魔暴龙:0.02%; 剑龙:0.38%; 厚甲剑龙:0.1%; 刺尾剑龙:0.3%; 雷霆剑龙:0.14%; 暴掠龙:0.04%; 疾奔暴掠龙:0.06%; 狩猎暴掠龙:0.02%; 毒皮暴掠龙:0.08%; 血瓣花鞭笞者:0.08%; 血瓣花掠夺者:0.06%; 血瓣花猛击者:0.08%; 血瓣花捕兽者:0.06%; 安戈洛巨猩猩:0.02%; 安戈洛猩猩:0.02%; 安戈洛大猩猩:0.02%; 焦油兽:0.04%; 焦油潜伏者:0.06%; 焦油兽王:0.06%; 焦油爬行者:0.04%; 格里什异种蝎:0.04%; 格里什工蝎:0.02%; 格里什劫掠者:0.02%; 胶质软泥怪:0.12%; 原生软泥怪:0.06%; 粘稠的软泥怪:0.06%; 石头守护者:0.08%; 幼双帆龙:0.03%; 双帆龙:0.04%; 老双帆龙:0.03%; 小翼手龙:0.06%; 翼手龙:0.1%; 狂怒的翼手龙:0.06%; 魔暴龙:0.04%; 剑龙:0.14%; 厚甲剑龙:0.22%; 刺尾剑龙:0.12%; 雷霆剑龙:0.28%; 疾奔暴掠龙:0.04%; 毒皮暴掠龙:0.06%; 血瓣花猛击者:0.1%; 血瓣花捕兽者:0.04%; 焦油兽王:0.08%; 格里什劫掠者:0.012%; 胶质软泥怪:0.08%; 原生软泥怪:0.04%; 粘稠的软泥怪:0.04%; 石头守护者:0.1%; 格鲁夫:0.56%; 老双帆龙:0.02%; 小翼手龙:0.04%; 霸王魔暴龙:0.04%; 剑龙:0.13%; 刺尾剑龙:0.38%; 暴掠龙:0.06%; 狩猎暴掠龙:0.06%; 毒皮暴掠龙:0.02%; 血瓣花鞭笞者:0.1%; 血瓣花掠夺者:0.08%; 血瓣花猛击者:0.06%; 焦油潜伏者:0.08%; 格里什异种蝎:0.02%; 胶质软泥怪:0.06%; 幼双帆龙:0.036%; 翼手龙:0.12%; 剑龙:0.2%; 厚甲剑龙:0.26%; 刺尾剑龙:0.26%; 狩猎暴掠龙:0.04%; 毒皮暴掠龙:0.04%; 血瓣花掠夺者:0.12%; 安戈洛巨猩猩:0.04%; 焦油兽王:0.1%; 有生烈焰:0.02%; 格里什工蝎:0.06%; 胶质软泥怪:0.1%; 粘稠的软泥怪:0.08%; 石头守护者:0.04%; 幼双帆龙:0.04% | —→— | objective_count:missing_counts,server_drop_rate_needed |
| 4289 | 安戈洛的猩猩 | 安戈洛环形山 | 47/55 | multiple_creature_task_item_drops×2[personal_loot_roll_per_character_expected](安戈洛猩猩); multiple_creature_task_item_drops×2[personal_loot_roll_per_character_expected](安戈洛巨猩猩); multiple_creature_task_item_drops×2[personal_loot_roll_per_character_expected](安戈洛大猩猩) | 安戈洛猩猩:100.0%; 安戈洛巨猩猩:100.0%; 安戈洛大猩猩:100.0% | —→— | server_drop_rate_needed |
| 4290 | 拉克维的食物 | 安戈洛环形山 | 48/53 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Fresh Threshadon Carcass) | Fresh Threshadon Carcass:100.0% | —→4291 | — |
| 4291 | 拉克维的气味 | 安戈洛环形山 | 48/53 | multiple_creature_task_item_drops×2[personal_loot_roll_per_character_expected](拉克维的配偶) | 拉克维的配偶:100.0% | 4290→4292 | server_drop_rate_needed |
| 4292 | 拉克维的诱饵 | 安戈洛环形山 | 48/56 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](拉克维) | 拉克维:100.0% | 4291→— | — |
| 4301 | 强大的尤尔查 | 安戈洛环形山 | 50/55 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](尤尔查) | 尤尔查:100.0% | 4289→— | — |
| 4492 | 走丢了！ | 安戈洛环形山 | 50/55 | 无目标/跑腿 | — | —→— | — |
| 4501 | 当心翼手龙 | 安戈洛环形山 | 47/55 | regular_shared_kills×10[kill_progress_shared_expected](狂怒的翼手龙) | — | —→— | — |
| 4503 | 希兹尔的飞行器 | 安戈洛环形山 | 49/51 | multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](幼双帆龙/双帆龙/老双帆龙); multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](小翼手龙/翼手龙/狂怒的翼手龙) | 幼双帆龙:80.0%; 双帆龙:80.0%; 老双帆龙:80.0%; 小翼手龙:80.0%; 翼手龙:80.0%; 狂怒的翼手龙:80.0% | —→— | server_drop_rate_needed |
| 3442 | 无瑕之焰 | 灼热峡谷 | 40/48 | multiple_creature_task_item_drops×4[personal_loot_roll_per_character_expected](炽热元素/地狱元素/熔岩元素); multiple_creature_task_item_drops×4[personal_loot_roll_per_character_expected](温和的作战傀儡/重型作战傀儡/熔岩元素) | 炽热元素:29.0%; 地狱元素:31.0%; 熔岩元素:26.0%; 温和的作战傀儡:28.0%; 重型作战傀儡:27.0%; 熔岩元素:30.0% | 3441→3443 | server_drop_rate_needed |
| 3443 | 铸造火炬杆 | 灼热峡谷 | 40/48 | multiple_creature_task_item_drops×8[personal_loot_roll_per_character_expected](黑铁地质学家/黑铁锻造师/奴隶工) | 黑铁地质学家:80.0%; 黑铁锻造师:80.0%; 奴隶工:80.0%; 黑铁奴隶贩子:80.0%; 黑铁工头:80.0%; 黑铁哨兵:80.0%; 黑铁巡逻兵:80.0%; 黑铁绑匪:80.0% | 3442→3452 | server_drop_rate_needed |
| 3452 | 烈焰之盒 | 灼热峡谷 | 40/50 | single_regular_creature_task_item×1[personal_loot_roll_per_character_expected](暮光黑暗萨满祭司/暮光火焰卫士/暮光地占师) | 暮光黑暗萨满祭司:100.0%; 暮光火焰卫士:100.0%; 暮光地占师:100.0%; 暮光崇拜者:100.0% | 3443→3453 | — |
| 3454 | 惩戒火炬 | 灼热峡谷 | 40/50 | 无目标/跑腿 | — | 3453→— | — |
| 3462 | 侍卫玛特拉克 | 灼热峡谷 | 40/50 | 无目标/跑腿 | — | 3454→3463 | — |
| 3463 | 烧掉它们！ | 灼热峡谷 | 40/52 | multiple_world_objects×?[object_interaction_per_character_expected](Sentry Brazier); multiple_world_objects×?[object_interaction_per_character_expected](Sentry Brazier); multiple_world_objects×?[object_interaction_per_character_expected](Sentry Brazier); multiple_world_objects×?[object_interaction_per_character_expected](Sentry Brazier) | — | 3462→— | objective_count:missing_counts |
| 4449 | 被锁起来的矮人 | 灼热峡谷 | 43/45 | regular_shared_kills×8[kill_progress_shared_expected](黑铁地质学家); multiple_creature_task_item_drops×15[personal_loot_roll_per_character_expected](黑铁地质学家/黑铁锻造师/奴隶工) | 黑铁地质学家:9.8817%; 黑铁锻造师:0.02%; 奴隶工:9.7076%; 黑铁奴隶贩子:0.02%; 黑铁工头:0.02%; 重型作战傀儡:0.02%; 暮光火焰卫士:0.02%; 暮光地占师:0.02%; 黑铁巡逻兵:9.9585% | —→4450 | server_drop_rate_needed |
| 4450 | 塔纳利斯的账本 | 灼热峡谷 | 43/46 | task_item_world_object_pickup×?[item_pickup_per_character_expected](Goodsteel Ledger); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](晶网蜘蛛); task_item_world_object_pickup×?[item_pickup_per_character_expected](Damaged Crate); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](加奎亚) | Goodsteel Ledger:100.0%; 晶网蜘蛛:80.0%; Damaged Crate:100.0%; 加奎亚:100.0% | 4449→— | objective_count:missing_counts,server_drop_rate_needed |
| 4451 | 自由的钥匙 | 灼热峡谷 | 43/47 | 无目标/跑腿 | — | —→— | — |
| 7701 | 悬赏：工头玛托留斯 | 灼热峡谷 | 45/50 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](工头玛托留斯) | 工头玛托留斯:100.0% | —→— | — |
| 7702 | 让他们失眠！ | 灼热峡谷 | 30/49 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Dark Iron Pillow) | Dark Iron Pillow:100.0% | —→— | — |
| 7722 | 绝密配方！ | 灼热峡谷 | 45/50 | task_item_world_object_pickup×1[item_pickup_per_character_expected](Secret Plans: Fiery Flux) | Secret Plans: Fiery Flux:100.0% | —→— | — |
| 7723 | 该死的手指头！ | 灼热峡谷 | 45/49 | regular_shared_kills×20[kill_progress_shared_expected](重型作战傀儡) | — | —→— | — |
| 7724 | 熔岩蜘蛛的威胁！ | 灼热峡谷 | 45/49 | regular_shared_kills×20[kill_progress_shared_expected](巨型熔岩蜘蛛) | — | —→— | — |
| 7727 | 熏火龙 | 灼热峡谷 | 45/49 | regular_shared_kills×20[kill_progress_shared_expected](熏火龙) | — | —→— | — |
| 7728 | 被盗：鼓风机和望远镜 | 灼热峡谷 | 45/48 | multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](黑铁锻造师); multiple_creature_task_item_drops×?[personal_loot_roll_per_character_expected](黑铁哨兵) | 黑铁锻造师:100.0%; 黑铁哨兵:100.0% | —→— | objective_count:missing_counts,server_drop_rate_needed |
| 7729 | 工作机会：肃清竞争对手 | 灼热峡谷 | 45/48 | regular_shared_kills×15[kill_progress_shared_expected](黑铁工头); regular_shared_kills×15[kill_progress_shared_expected](黑铁奴隶贩子) | — | —→— | — |
| 13662 | 获得信任 | 灼热峡谷 | 45/60 | single_regular_creature_task_item×1[personal_loot_roll_per_character_expected](铁怒监军/铁怒狱卒/铁怒卫士) | 铁怒监军:18.1475%; 铁怒狱卒:18.1475%; 铁怒卫士:18.1475%; 铁怒步兵:18.7324%; 铁怒士兵:18.9198%; 铁怒医师:18.7936%; 铁怒军官:18.1837%; 暗炉农夫:20.0377%; 厄炉工匠:19.7698%; 铁怒队长:18.4991%; 厄炉龙骑兵:18.8746%; 厄炉魔匠:20.3048%; 暗炉平民:20.9981%; 铁怒上尉:19.2932%; 暗炉议员:21.3673%; 战斗傀儡:14.3175%; 狂怒傀儡:15.4332%; 怒锤傀儡:14.2826%; 熔岩作战傀儡:17.175%; 火焰卫士:20.4245%; 炽热火焰卫士:20.0769%; 火焰驱逐者:20.0115%; 暮光之锤拷问者:18.6764%; 暮光使者:20.9995%; 暮光保镖:19.7067%; 暮光之锤特使:19.9174%; 竞技场观众:19.6796%; 武器技师:19.7585%; 血犬:18.3036%; 巨型血犬:16.5515%; 无敌的潘佐尔:11.0%; 贝哈默斯:16.1616%; 掘泥虫:21.3333%; 深渊钉刺者:18.6026%; 黑暗尖啸者:25.3778%; 洞穴雷霆蜥蜴:29.8718%; 铁炉堡公主茉艾拉·铜须:10.0%; 钻孔甲虫:25.3769%; 洞穴爬行者:21.6193%; 傀儡统帅阿格曼奇:9.0%; 贝尔加:12.0%; 伊森迪奥斯:11.0%; 审讯官格斯塔恩:10.0%; 达格兰·索瑞森大帝:10.0%; 控火师罗格雷恩:13.0%; 洛考尔:10.0%; 征服者派隆:17.3178%; 修行者高罗什:4.0%; 格里兹尔:10.0%; 剜眼者:14.0%; 破坏者奥科索尔:12.0%; 阿努希尔:9.0%; 爬行者赫杜姆:8.0%; 安格弗将军:9.0%; 典狱官斯迪尔基斯:11.0%; 维雷克:15.0%; 弗诺斯·达克维尔:9.0%; 弗莱拉斯大使:11.0%; 驯犬者格雷布玛尔:13.0%; 暮光之锤刽子手:22.2552%; 黑暗守护者沃弗克:20.8333%; 黑暗守护者比塞克:20.6612%; 黑暗守护者尤格尔:11.5385%; 黑暗守护者希姆雷尔:20.9091%; 黑暗守护者奥弗加特:15.2941%; 黑暗守护者佩沃尔:15.2%; 黑暗卫兵:18.0581%; 卫兵杜格瑞普:13.8085%; 普拉格:14.0%; 法拉克斯:10.0%; 霍尔雷·黑须:9.0%; 黑须的亲信:17.2017%; 雷布里·斯库比格特:9.0%; 恐怖的奴隶主:21.2289%; 醉酒的奴隶主:20.3279%; 持铁锤的顾客:18.5185%; 奥格拉比斯:17.316%; 希尔·丁格:20.2073%; 火浪杀手:21.2264%; 贾兹:20.8531%; 玛格姆斯:14.0%; 雷布里的亲信:15.9079%; 索瑞森高阶女祭司:10.0%; 铁怒工头:18.5284%; 铁怒执行者:19.0486% | —→— | — |
| 571 | 摩克萨尔丁的魔法 | 荆棘谷 | 33/41 | single_regular_creature_task_item×1[personal_loot_roll_per_character_expected](老迈的薄雾谷猩猩) | 老迈的薄雾谷猩猩:10.0% | 572→573 | — |
| 2862 | 与豺狼人开战 | 菲拉斯 | 39/42 | multiple_creature_task_item_drops×10[personal_loot_roll_per_character_expected](混血木爪豺狼人/木爪捕兽者/木爪蛮兵) | 混血木爪豺狼人:80.0%; 木爪捕兽者:80.0%; 木爪蛮兵:80.0%; 木爪秘法师:80.0%; 木爪劫掠者:80.0%; 木爪突击队员:80.0% | —→2863 | server_drop_rate_needed |
| 2863 | 突然袭击 | 菲拉斯 | 39/43 | regular_shared_kills×1[kill_progress_shared_expected](木爪突击队员) | — | 2862→2902 | objective_count:ambiguous_extra_numbers |
| 2902 | 调查木爪岭 | 菲拉斯 | 39/43 | 无目标/跑腿 | — | 2863→2903 | — |
| 2903 | 作战计划 | 菲拉斯 | 39/43 | 无目标/跑腿 | — | 2902→— | — |
| 2973 | 新斗篷的光辉 | 菲拉斯 | 38/45 | multiple_creature_task_item_drops×10[personal_loot_roll_per_character_expected](小精龙/被俘获的小精龙) | 小精龙:80.0%; 被俘获的小精龙:80.0% | —→2974 | server_drop_rate_needed |
| 2974 | 可怕的发现 | 菲拉斯 | 38/45 | multiple_creature_task_item_drops×20[personal_loot_roll_per_character_expected](恐怖图腾袭击者/恐怖图腾博学者/恐怖图腾萨满祭司) | 恐怖图腾袭击者:80.0%; 恐怖图腾博学者:80.0%; 恐怖图腾萨满祭司:80.0% | 2973→2976 | server_drop_rate_needed |
| 2975 | 菲拉斯的食人魔 | 菲拉斯 | 38/43 | regular_shared_kills×10[kill_progress_shared_expected](戈杜尼食人魔); regular_shared_kills×10[kill_progress_shared_expected](戈杜尼食人魔法师); regular_shared_kills×5[kill_progress_shared_expected](戈杜尼蛮兵) | — | —→2980 | — |
| 2976 | 可怕的发现 | 菲拉斯 | 37/45 | 无目标/跑腿 | — | 2974→— | — |
| 2978 | 戈杜尼卷轴 | 菲拉斯 | 38/43 | 无目标/跑腿 | — | —→2979 | — |
| 2979 | 黑暗仪式 | 菲拉斯 | 38/46 | single_regular_creature_task_item×1[personal_loot_roll_per_character_expected](戈杜尼大法师) | 戈杜尼大法师:100.0% | 2978→3002 | — |
| 2980 | 菲拉斯的食人魔 | 菲拉斯 | 38/44 | regular_shared_kills×10[kill_progress_shared_expected](戈杜尼萨满祭司); regular_shared_kills×10[kill_progress_shared_expected](戈杜尼术士); regular_shared_kills×5[kill_progress_shared_expected](戈杜尼虐待者) | — | 2975→— | — |
| 2987 | 戈杜尼钴矿石 | 菲拉斯 | 38/43 | task_item_world_object_pickup×12[item_pickup_per_character_expected](Gordunni Dirt Mound) | Gordunni Dirt Mound:100.0% | —→— | — |
| 7730 | 祖卡什的入侵 | 菲拉斯 | 39/45 | multiple_creature_task_item_drops×20[personal_loot_roll_per_character_expected](祖卡什毒刺蝎/祖卡什异种蝎/祖卡什工蝎) | 祖卡什毒刺蝎:100.0%; 祖卡什异种蝎:100.0%; 祖卡什工蝎:100.0%; 祖卡什掘洞蝎:100.0%; 毒刺鞭笞者:100.0% | 2903→— | server_drop_rate_needed |
| 7731 | 毒刺鞭笞者 | 菲拉斯 | 39/47 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](毒刺鞭笞者) | 毒刺鞭笞者:100.0% | 2903→— | — |
| 7732 | 祖卡什报告 | 菲拉斯 | 39/48 | 无目标/跑腿 | — | 组:7730,7731→— | — |
| 4971 | 时间问题 | 西瘟疫之地 | 53/56 | single_named_or_rare_kill×1[kill_progress_shared_expected](时光寄生虫) | — | —→— | — |
| 4972 | 找回时间 | 西瘟疫之地 | 53/56 | task_item_world_object_pickup×5[item_pickup_per_character_expected](Small Lockbox) | Small Lockbox:100.0% | 4971→— | — |
| 4984 | 大自然的苦楚 | 西瘟疫之地 | 51/54 | regular_shared_kills×8[kill_progress_shared_expected](生病的狼) | — | —→4985 | — |
| 4985 | 大自然的苦楚 | 西瘟疫之地 | 51/56 | regular_shared_kills×8[kill_progress_shared_expected](生病的灰熊) | — | 4984→— | — |
| 5021 | 迟到总比不到好 | 西瘟疫之地 | 50/52 | 无目标/跑腿 | — | —→— | — |
| 5058 | 达尔松夫人的日记 | 西瘟疫之地 | 52/55 | 无目标/跑腿 | — | —→— | — |
| 5060 | 被锁起来的农夫 | 西瘟疫之地 | 52/55 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](农夫达尔松) | 农夫达尔松:100.0% | —→— | — |
| 5098 | 标记哨塔 | 西瘟疫之地 | 50/56 | regular_shared_kills×?[kill_progress_shared_expected](安多哈尔一号哨塔); regular_shared_kills×?[kill_progress_shared_expected](安多哈尔二号哨塔); regular_shared_kills×?[kill_progress_shared_expected](安多哈尔三号哨塔); regular_shared_kills×?[kill_progress_shared_expected](安多哈尔四号哨塔) | — | 5096→— | objective_count:missing_counts |
| 5228 | 瘟疫之锅 | 西瘟疫之地 | 50/53 | 无目标/跑腿 | — | 5096→5229 | not_in_world_candidate_union |
| 5229 | 目标：费尔斯通农场 | 西瘟疫之地 | 50/53 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](护锅者拜尔摩) | 护锅者拜尔摩:100.0% | 5228→5230 | — |
| 5230 | 返回亡灵壁垒 | 西瘟疫之地 | 50/53 | 无目标/跑腿 | — | 5229→5231 | — |
| 5231 | 目标：达尔松之泪 | 西瘟疫之地 | 50/55 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](护锅者玛维诺斯) | 护锅者玛维诺斯:100.0% | 5230→5232 | — |
| 5232 | 返回亡灵壁垒 | 西瘟疫之地 | 50/55 | 无目标/跑腿 | — | 5231→5233 | — |
| 5233 | 目标：嚎哭鬼屋 | 西瘟疫之地 | 50/55 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](护锅者拉扎奇) | 护锅者拉扎奇:100.0% | 5232→5234 | — |
| 6004 | 未竟的事业 | 西瘟疫之地 | 50/56 | regular_shared_kills×2[kill_progress_shared_expected](血色医者); regular_shared_kills×2[kill_progress_shared_expected](血色猎人); regular_shared_kills×2[kill_progress_shared_expected](血色法师); regular_shared_kills×2[kill_progress_shared_expected](血色骑士) | — | —→6023 | — |
| 4102 | 净化费伍德 | 费伍德森林 | 48/55 | multiple_creature_task_item_drops×15[personal_loot_roll_per_character_expected](曲木食苔者/曲木撕裂者/迪塞库斯) | 曲木食苔者:80.0%; 曲木撕裂者:80.0%; 迪塞库斯:80.0% | —→— | server_drop_rate_needed |
| 4505 | 腐化之井 | 费伍德森林 | 49/54 | item_source_not_in_questie×1[unknown_or_supplied_item](source?) | — | —→— | item_source_missing:12567 |
| 5155 | 加德纳尔的势力 | 费伍德森林 | 48/51 | regular_shared_kills×4[kill_progress_shared_expected](加德纳尔恶犬); regular_shared_kills×4[kill_progress_shared_expected](加德纳尔守护者); regular_shared_kills×6[kill_progress_shared_expected](加德纳尔精兵); regular_shared_kills×6[kill_progress_shared_expected](加德纳尔祭司) | — | —→5157 | — |
| 6162 | 最后一战 | 费伍德森林 | 46/51 | single_named_creature_task_item×1[personal_loot_roll_per_character_expected](主宰洛尔) | 主宰洛尔:100.0% | —→— | — |
| 6221 | 北方的死木熊怪 | 费伍德森林 | 45/55 | regular_shared_kills×5[kill_progress_shared_expected](死木守卫); regular_shared_kills×5[kill_progress_shared_expected](死木复仇者); regular_shared_kills×5[kill_progress_shared_expected](死木萨满祭司) | — | —→— | — |
| 8460 | 木喉熊怪的盟友 | 费伍德森林 | 45/48 | regular_shared_kills×6[kill_progress_shared_expected](死木战士); regular_shared_kills×6[kill_progress_shared_expected](死木探险者); regular_shared_kills×6[kill_progress_shared_expected](死木园丁) | — | —→— | — |
| 8461 | 北方的死木熊怪 | 费伍德森林 | 45/55 | regular_shared_kills×6[kill_progress_shared_expected](死木守卫); regular_shared_kills×6[kill_progress_shared_expected](死木复仇者); regular_shared_kills×6[kill_progress_shared_expected](死木萨满祭司) | — | —→— | — |
| 8462 | 与纳菲恩交谈 | 费伍德森林 | 45/55 | 无目标/跑腿 | — | 8460→— | — |
| 8465 | 与萨尔法交谈 | 费伍德森林 | 45/55 | 无目标/跑腿 | — | —→— | — |
