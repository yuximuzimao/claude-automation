# 北风苔原基础数据与Target Cluster对抗式审查

状态：第一阶段基础层；**尚未开始按R1/R2逐簇插入路线**。

## 1. 本轮冻结规则

- 复用路线起点按飞艇刚到战歌要塞、未接未做；当前历程只用于服务器版本/现场事实参考。
- 77级前禁止个人飞行；鸟点/飞艇等系统交通仍可使用。
- 诺森德一次性有经验任务按全清建模；跨地图任务必须进入候选和任务栏容量模型。
- 无经验任务默认不进入升级路线；若它是后续有经验任务的唯一/强制前置，则保留为结构性前置。
- 联盟/非血精灵圣骑任务排除。PvP仅允许普通任务怪击杀；玩家击杀/占点/夺旗等排除。
- 任务栏硬上限25；每个接取记+1，每个交付/自动完成释放-1；22起软警告，后续每次插入必须重放计数器。
- 视频34–39集和旧部落Journey只提供任务邻接/同片区参考，不覆盖我们的前置、Target Cluster、Spatial Instance与任务栏约束。

## 2. 基础数据结果

- Questie：11.34.0；raw assigned=252，raw direct-touches=263，修正层Borean提示=13。
- 北风主候选275条；加一跳外部前置/后续边界引用后总记录287条。边界前置6条、边界后续6条。
- WotLK修正层：命中111，成功解析111，失败0。
- 北风主候选Scope分布：`{"defer_future_level_revisit": 5, "exclude_alliance_or_other_faction": 81, "exclude_deprecated_or_system": 6, "exclude_no_xp": 2, "exclude_profession": 5, "exclude_repeatable_calendar": 4, "exclude_server_variant": 3, "include_later_cross_map_followup": 1, "include_later_cross_map_inbound": 1, "include_leveling_cross_map_outbound": 2, "include_leveling_dungeon": 4, "include_leveling_local": 160, "include_structural_zero_xp_prerequisite": 1}`。
- 边界引用Scope分布：`{"boundary_followup_reference": 5, "boundary_irrelevant_reference": 5, "boundary_prerequisite_reference": 2}`。
- Target Cluster：158个，其中多任务共享实体簇22个；普通目标为空的纳入任务76个。
- Questie extraObjectives：纳入任务共31条特殊机制事实；形成37个实体锚点簇和4个纯坐标锚点。
- 全清可错过约束：2条。

## 3. 对抗式检查

- PASS `questie_corrections_parse_clean`：{"candidate_block_count": 111, "parsed_block_count": 111, "failed_block_count": 0, "unresolved_symbol_count": 0, "unresolved_symbols": {}, "kill_credit_objective_first": [11652], "parse_failures": {}, "changed_fields": {"7783": [13], "11566": [21], "11569": [13], "11570": [9], "11574": [13, 16], "11575": [16], "11576": [21], "11582": [21], "11585": [16], "11587": [13, 29], "11590": [10, 21], "11591": [16], "11592": [9], "11593": [21], "11594": [13], "11595": [12, 16], "11596": [13, 16], "11597": [12], "11606": [13], "11608": [21], "11610": [10, 21], "11611": [10, 13], "11626": [21], "11631": [21, 29], "11632": [2], "11633": [21], "11636": [29], "11637": [11], "11647": [21], "11648": [21], "11650": [21], "11652": [10, 29], "11653": [10, 21], "11654": [2, 13], "11656": [10, 21], "11661": [21], "11664": [9], "11670": [10, 21], "11671": [21, 29], "11673": [9], "11677": [10, 21], "11680": [21], "11686": [10], "11688": [13], "11690": [10, 21, 29], "11694": [10, 21], "11704": [13], "11705": [10], "11706": [10, 29], "11708": [10, 13], "11711": [9, 21, 29], "11712": [10, 21], "11713": [13], "11719": [9], "11721": [21], "11723": [10, 21], "11728": [21, 29], "11730": [10, 21], "11788": [29], "11794": [21], "11796": [21], "11798": [29], "11865": [21, 29], "11876": [21], "11878": [10, 29], "11879": [29], "11881": [21, 29], "11887": [10], "11888": [13], "11889": [21], "11890": [9], "11892": [21], "11893": [10, 21, 29], "11894": [29], "11895": [29], "11896": [10, 21], "11897": [21], "11898": [29], "11899": [10, 13, 21], "11905": [21, 29], "11906": [13], "11907": [29], "11908": [13], "11909": [29], "11913": [10, 21], "11919": [10, 17, 21, 29], "11930": [9], "11938": [10, 21], "11940": [10, 17, 21, 29], "11945": [26], "11946": [11], "11951": [21], "11956": [29], "11957": [21, 29], "11967": [29], "11969": [21, 29], "12019": [3, 29], "12035": [10, 21], "12117": [22], "12157": [16], "12171": [16], "12486": [13], "12500": [13], "12728": [21], "13242": [13], "13265": [30], "13270": [30], "13413": [29], "13414": [29], "13833": [29], "13950": [9, 13, 16]}}
- PASS `every_task_has_scope_status`：287
- PASS `every_excluded_task_has_reason`：106
- PASS `no_alliance_task_included`：无异常
- PASS `no_repeatable_calendar_task_included`：无异常
- PASS `no_disallowed_pvp_included`：无异常
- PASS `no_unjustified_zero_xp_included`：[11679]
- PASS `server_variants_resolved_or_flagged`：[]
- PASS `included_target_cluster_facts_present`：181
- PASS `shared_target_clusters_have_coordinates`：[]
- PASS `quest_log_metadata_complete`：无异常
- PASS `full_clear_availability_constraints_not_mutually_impossible`：[]
- PASS `questie_extra_objectives_materialized`：{"included_extra_objectives": 31, "entity_anchor_clusters": 37, "coordinate_anchors": 4}
- PASS `included_tasks_have_viable_external_prerequisites`：[]
- PASS `video_reference_groups_survive_scope`：[]
- PASS `known_shared_target_clusters_preserved`：[]
- PASS `known_script_mechanism_anchors_preserved`：[]
- PASS `known_full_clear_missable_constraints_preserved`：[]
- PASS `cross_map_direction_and_phase_preserved`：[]

## 4. 全清可错过约束与跨图边界

- `11574`《危在旦夕》必须先接，再让`11587`《越狱》进入任务栏或完成；否则Questie `exclusiveTo` 语义会使前者不可接。
- `11591`《钢腭的车队》必须先接，再让`11592`《攻击！》、`11593`《亡者的尊严》、`11594`《让他们安息》进入任务栏或完成；否则Questie `exclusiveTo` 语义会使前者不可接。
- 初次北风自然出图：`11930`《横贯冰原》、`12117`《前往莫亚基港口》；两者接取后会占用任务栏，直到龙骨荒野对应交付点释放。
- 后续回北风链：`13242`《黑暗的骚动》需要先完成龙骨荒野`12500`《返回安加萨》，之后回战歌要塞交；再解锁`13257`《战争的使者》并前往奥格瑞玛。这两条保留在全清宇宙，但不插入初次北风清图。
- 一跳跨图边界引用：
  - `11958`《不要浪费》 → `boundary_followup_reference`，由北风任务[12117]直接引用。
  - `11977`《牦牛人中的牛头人》 → `boundary_followup_reference`，由北风任务[11930]直接引用。
  - `12500`《返回安加萨》 → `boundary_prerequisite_reference`，由北风任务[13242]直接引用。
  - `12790`《来去如风》 → `boundary_followup_reference`，由北风任务[12791]直接引用。
  - `13126`《协同作战》 → `boundary_followup_reference`，由北风任务[13124]直接引用。
  - `13127`《法师领主伊洛姆》 → `boundary_prerequisite_reference`，由北风任务[13128]直接引用。
  - `13266`《毫无遗憾的一生》 → `boundary_followup_reference`，由北风任务[13257]直接引用。

## 5. 不进入初次升级路线的北风主任务与原因

- `12791`《魔法王国达拉然》 → `defer_future_level_revisit`：required_level_74_above_first_pass_window
- `13124`《战斗仍在继续》 → `defer_future_level_revisit`：required_level_77_above_first_pass_window
- `13128`《龙翼之力》 → `defer_future_level_revisit`：required_level_77_above_first_pass_window
- `13412`《科拉丝塔萨》 → `defer_future_level_revisit`：required_level_80_above_first_pass_window
- `13413`《展翅高飞！》 → `defer_future_level_revisit`：required_level_80_above_first_pass_window
- `11575`《千钧一发》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `11599`《萨萨里安，我的哥哥》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11600`《威廉·奥雷顿之死》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11601`《柳暗花明》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11603`《酒中的真相》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11604`《逃兵》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11622`《裂鞭海岸的秘密》 → `exclude_alliance_or_other_faction`：manual_horde_scope_override_alliance_counterpart_of_11620
- `11645`《恶心的雪地狗头人！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11650`《还要一些东西……》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11653`《大块头》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11658`《B计划》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11670`《是兽人干的！真的！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11672`《应征入伍》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11673`《带我出去！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11692`《寻找比希》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11693`《好极了……天灾猛犸人！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11694`《山洞中的瘟疫》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11697`《丁奇跑进浮空城了！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11698`《顺便清理天灾士兵》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11699`《我被困在笼子里了……》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11700`《通知比希》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11701`《返回机场》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11704`《国王姆嘎姆嘎》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `11707`《迫在眉睫》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11708`《机械侏儒》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11710`《转换器怎么了？》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11712`《物质转换注射器》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11713`《侦查虫孔》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11715`《石油资源》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11718`《猛犸的毛皮》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11723`《天摇地动！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11725`《寻找“尾旋”》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11726`《一点辣椒》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11727`《英雄的时代》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11728`《狼的排泄物》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11729`《超声波螺丝刀》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf
- `11730`《主与仆》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11788`《左膀右臂》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11789`《急需帮助的士兵》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11790`《隐藏的诅咒教徒》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf
- `11791`《通知阿洛斯》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11792`《圣光的敌人》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11793`《继续调查》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11794`《猎杀行动》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11795`《紧急情况守则：第8章，第2节，第3段》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11796`《紧急情况守则：第8章，第2节，第4段》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11797`《虫临城下》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11798`《机甲专家麦卡佐德》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11873`《通知菲兹兰克》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11882`《玩火》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `11889`《空中的虫子》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11897`《炸毁虫孔》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11901`《军队？什么军队？》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `11902`《致命的谷物》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf
- `11903`《战斗的时刻》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11904`《劳动的果实》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11908`《参考资料》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11913`《万无一失》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11920`《隐藏的诅咒教徒》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf
- `11927`《坊间的传言》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11928`《致远郡》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11932`《懦夫和蠢货》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `11938`《争取时间》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11942`《通行之语》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11944`《我们被包围了！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11956`《寻找护命匣》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11962`《最后一批矿石》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11963`《给致远郡的武器》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `11965`《集结的钟声！》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `12019`《最后的义务》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `12035`《重新装配》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `12086`《卡库特之子》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf
- `12088`《死亡骑士萨萨里安》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `12141`《外交任务》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf；start_npc_alliance_only
- `12157`《失踪的信使》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `12490`《维赫亚的复仇》 → `exclude_alliance_or_other_faction`：manual_horde_scope_override_alliance_legacy_riplash_continuation
- `12794`《魔法王国达拉然》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf
- `13004`《完美宝石》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `13088`《诺森德的厨师》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；required_races_excludes_blood_elf；start_npc_alliance_only
- `13094`《他们丝毫不感到羞愧吗？》 → `exclude_alliance_or_other_faction`：required_races_excludes_blood_elf
- `13265`《布匹搜寻》 → `exclude_alliance_or_other_faction`：finish_npc_alliance_only；start_npc_alliance_only
- `11621`《利维洛斯石板》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `11939`《?????》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `12087`《A Little Help Here? DEPRECATED》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `12103`《DEPRECATED》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `12108`《DEPRECATED》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `12156`《DEPRECAED》 → `exclude_deprecated_or_system`：deprecated_placeholder_or_system_quest
- `11915`《玩火》 → `exclude_no_xp`：no_quest_xp_and_not_mandatory_for_included_xp_task
- `13950`《伙伴！》 → `exclude_no_xp`：no_quest_xp_and_not_mandatory_for_included_xp_task
- `13002`《完美宝石》 → `exclude_profession`：requires_profession_or_skill
- `13090`《诺森德的厨师》 → `exclude_profession`：requires_profession_or_skill
- `13148`《修理项链》 → `exclude_profession`：requires_profession_or_skill
- `13270`《布匹搜寻》 → `exclude_profession`：requires_profession_or_skill
- `13833`《危险的美食》 → `exclude_profession`：requires_profession_or_skill
- `11867`《更多耳环……》 → `exclude_repeatable_calendar`：not_one_time_clearable
- `11940`《猎龙》 → `exclude_repeatable_calendar`：not_one_time_clearable
- `11945`《做最坏的打算》 → `exclude_repeatable_calendar`：not_one_time_clearable
- `13414`《展翅高飞！》 → `exclude_repeatable_calendar`：not_one_time_clearable
- `11586`《地狱咆哮的堡垒》 → `exclude_server_variant`：same_server_observed_variant_is_11585
- `11595`《战歌要塞的防御》 → `exclude_server_variant`：same_server_observed_variant_is_11596
- `11597`《战歌要塞的防御》 → `exclude_server_variant`：same_server_observed_variant_is_11596

## 6. 审查结论

- 机器检查与本轮人工对抗复核全部通过。人工复核已覆盖：旧158条自动候选差集、联盟/职业/重复/无经验过滤、服务器任务版本、跨图方向与阶段、Questie `exclusiveTo` 可错过约束、`extraObjectives`脚本机制、视频34—39集任务组覆盖，以及已知共享真实目标实体簇。
- 基础任务事实层与Target Cluster层可以冻结进入下一阶段；**尚未生成R1路线**。下一步先把Target Cluster人工拆成真实Spatial Instance，再从战歌要塞构造R1，之后严格逐簇插入。
- 从R1开始，每次插入都必须重放25格任务栏计数器，并同时查看视频邻接参考；视频只能建议合并位置，不能覆盖前置、空间实例、可错过约束或任务栏容量。
