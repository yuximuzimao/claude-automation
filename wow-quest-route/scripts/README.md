# `scripts/` 现役实现注册表

用途：本目录只放**仍可能参与当前实现链、兼容迁移或只读诊断**的顶层脚本。README负责回答每一个顶层文件是什么、当前处于什么生命周期状态；业务规则正文必须回`docs/rules/`唯一owner，脚本不能成为第二套规则。

当前顶层共有 **143 个 `.py` 文件**。这个数量本身说明历史阶段脚本尚未彻底清理，因此本轮先完成逐文件登记和状态分类，再做消费者审查/退役；不能仅凭文件名批量移动。

## 1. 状态定义

| 状态 | 含义 |
| --- | --- |
| `ACTIVE/REVIEW` | 仍可能是现役builder/model/数据构建入口；保留，后续按新Task Card/Route Profile架构审查输入输出 |
| `AUDIT` | 仍可能承担当前只读/验证职责；必须只验证对应契约，不拥有业务真值 |
| `ASSET` | 地图/资源工程工具，职责与Task Card/Route Profile业务事实分离 |
| `READ-ONLY` | 分析、inspect、report、export、trace类工具；不得写正式业务真源 |
| `SOLVER` | 求解器/算法实验或当前局部优化工具；不得绕过Task Card/Selection/Route Profile直接成为正式真源 |
| `MIGRATE` | 当前仍承载地图语义/任务事实，属于新架构明确迁移对象；迁完后应退役或纯化 |
| `INTERNAL-COMPAT` | CLI已退役但模块仍可能被现役wrapper复用；不能直接移走，先切消费者 |
| `RETIRE-CANDIDATE` | 形态上属于一次性apply/fix/migrate/refactor/update；先查现役引用，无消费者后移入archive |
| `RETIRED-GUARD` | 文件自身已经明确声明`RETIRED`；只剩防误执行guard，目标是移出顶层并在archive索引保留历史说明 |
| `REVIEW` | 当前无法仅凭命名确认生命周期，先保留并做消费者审查 |

## 2. 目录纪律

1. **脚本不拥有业务规则。** Task Card事实、Selection、XP、Timing、Route Optimization、Presentation等只读对应owner；脚本只实现。
2. **脚本不拥有具体任务事实。** 任务ID可以作为输入/测试fixture，但现役builder不得把共享机制、Boss技巧、任务物规则等硬编码成唯一事实源。
3. **Generated Product不是写入口。** 目标态地图builder写Route Profile或结构化中间层，统一publisher生成`workbench-routes.json`；不得每个脚本直接修改聚合JSON。
4. **一次性修改器不能永久留顶层。** `apply_* / fix_* / migrate_* / refactor_* / update_*`完成阶段任务且无现役消费者后，应进入`docs/archive/scripts/`。
5. **RETIRED guard不能长期占顶层。** 当前只是兼容清债状态；确认无导入/调用后移archive，并由测试阻止回流。
6. **新增顶层脚本必须同步登记本README。** 后续由Registry测试机械检查“顶层`.py`集合 = README登记集合”。
7. **archive脚本禁止现役导入。** 历史脚本只用于考古，不得被builder/audit/test/CLI加载来决定当前结果。

## 3. 当前架构迁移重点

- `*_semantic_steps.py`：当前仍保存地图玩家语义/部分任务机制，必须迁到`Task Card + Route Profile + Route Display + Task Presentation`。
- `fivebox-task-types.json`消费者：切到Task Card API后，旧文件降为兼容投影/历史证据。
- 直接写`workbench-routes.json`的builder/apply/refactor脚本：切到正式Route Profile或统一publisher。
- `build_route_atlas_workbench.py`：最终只消费聚合发布数据并产HTML；不得用prototype/fallback注入旧业务语义。
- `estimate_route_atlas_timing.py`：最终只消费结构化Task Card机制 + Route Profile，不从玩家备注反推机制。

## 4. 顶层143文件逐项注册

> 说明：`RETIRED-GUARD`来自脚本自身的显式`RETIRED`声明；`RETIRE-CANDIDATE`只是生命周期审查标记，不等于已经确认可删除。真正移动前必须检查现役import/CLI/tests/docs调用。

| 文件 | 当前状态 | 当前职责 / 迁移判断 |
| --- | --- | --- |
| `analyze_dragonblight_reachability.py` | READ-ONLY | 分析龙骨荒野可达性 |
| `analyze_icecrown_components.py` | READ-ONLY | 分析冰冠组件/依赖 |
| `analyze_loot_reward_filter.py` | READ-ONLY | 分析掉落奖励筛选 |
| `analyze_questie_journey.py` | READ-ONLY | 分析Questie历程 |
| `analyze_route_atlas_geometry.py` | READ-ONLY | 分析Route Atlas几何 |
| `apply_borean_winterfin_live_optimization.py` | RETIRE-CANDIDATE | 应用北风冬鳞村实跑优化；一次性/阶段性修改器形态 |
| `apply_post_extraction_nagrand_corrections.py` | RETIRE-CANDIDATE | 应用视频拆解后的纳格兰修正；一次性修改器形态 |
| `apply_post_extraction_zang_corrections.py` | RETIRE-CANDIDATE | 应用视频拆解后的赞加修正；一次性修改器形态 |
| `audit_borean_amber_bogorok_corridor.py` | RETIRED-GUARD | 北风琥珀崖→博古洛克施工期走廊诊断；文件已自声明RETIRED |
| `audit_borean_steps_50_66_handoffs.py` | RETIRED-GUARD | 北风步骤50–66施工期交接快照；已自声明RETIRED |
| `audit_cold_weather_flying_gates.py` | RETIRED-GUARD | 旧寒冷飞行门槛派生脚本，误命名为audit；已自声明RETIRED |
| `audit_dragonblight_anomalies.py` | RETIRED-GUARD | 龙骨旧异常取证快照；已自声明RETIRED |
| `audit_dragonblight_breadcrumbs.py` | RETIRED-GUARD | 龙骨旧breadcrumb/exclusiveTo清单；已自声明RETIRED |
| `audit_dragonblight_steps_1_15_handoffs.py` | RETIRED-GUARD | 龙骨步骤1–15施工期交接快照；已自声明RETIRED |
| `audit_dragonblight_steps_16_31_handoffs.py` | RETIRED-GUARD | 龙骨步骤16–31施工期交接快照；已自声明RETIRED |
| `audit_dragonblight_steps_32_51_handoffs.py` | RETIRED-GUARD | 龙骨步骤32–51施工期交接快照；已自声明RETIRED |
| `audit_grizzly_hills_handoffs.py` | RETIRED-GUARD | 灰熊施工期foundation交接快照；已自声明RETIRED |
| `audit_grizzly_hills_scope.py` | RETIRED-GUARD | 旧灰熊scope生成器，误命名audit；已自声明RETIRED |
| `audit_grizzly_hills_special_mechanisms.py` | RETIRED-GUARD | 旧灰熊特殊机制audit；已自声明RETIRED，且当前旧说明仍指semantic/fivebox旧架构 |
| `audit_hd_route_maps.py` | ASSET | 核对高清路线地图资源/配准 |
| `audit_howling_route_candidate.py` | AUDIT | 核对嚎风当前路线候选；迁移后应以Route Profile契约为输入 |
| `audit_howling_scope.py` | RETIRED-GUARD | 旧嚎风scope生成器，误命名audit；已自声明RETIRED |
| `audit_icecrown_draft_readiness.py` | AUDIT | 冰冠维护期草稿就绪/未闭合风险检查 |
| `audit_icecrown_final_publication.py` | RETIRED-GUARD | 旧61任务/16步冰冠发布模型guard；已自声明RETIRED |
| `audit_icecrown_repeat_clones.py` | RETIRED-GUARD | 旧重复/日常clone audit入口；现只剩退役guard |
| `audit_icecrown_route_coverage.py` | RETIRED-GUARD | 旧冰冠coverage audit；已由结构化coverage替代 |
| `audit_icecrown_route_dependency_order.py` | AUDIT | 检查冰冠正式任务前置顺序/首出现映射 |
| `audit_icecrown_structured_candidate.py` | AUDIT | 冰冠当前结构化候选/发布完整性审计；后续需按新测试owner拆职责 |
| `audit_legacy_route_comparison.py` | RETIRED-GUARD | 旧路线比较逻辑；已自声明RETIRED |
| `audit_northrend_video_reverse.py` | AUDIT | 当前诺森德视频反向核对/遗漏召回辅助 |
| `audit_outland_video_reverse.py` | RETIRED-GUARD | 2026-08-20外域视频POST分析；已自声明RETIRED |
| `audit_questie_package.py` | RETIRED-GUARD | 旧Questie包检查入口；已自声明RETIRED，现有inspect替代 |
| `audit_route_atlas_action_sequence.py` | AUDIT | 跨Profile动作顺序/接做交不变量检查 |
| `audit_route_atlas_flight_state.py` | AUDIT | RouteState飞行点时序/系统航线合法性检查 |
| `audit_route_atlas_objective_anchors.py` | AUDIT | 目标空间锚点/执行点检查 |
| `audit_route_atlas_player_text.py` | AUDIT | 玩家可见文本卫生/契约检查；迁移后应只实现Route Display/Task Presentation机械项 |
| `audit_route_atlas_special_mechanisms.py` | RETIRED-GUARD | 名称误导的旧赞加任务画像audit；已自声明RETIRED |
| `audit_sholazar_route_skeleton.py` | RETIRED-GUARD | 索拉查施工期粗空间bin工具；已自声明RETIRED |
| `audit_sholazar_whole_map_merge.py` | AUDIT | 索拉查整图合并/访问次数核对 |
| `audit_zangarmarsh_global_solver_input.py` | INTERNAL-COMPAT | 全局求解器输入内部实现；CLI已退役，当前wrapper可能复用 |
| `audit_zangarmarsh_special_mechanisms.py` | AUDIT | 赞加特殊机制审计；需迁到Task Card后审查是否仍有独立价值 |
| `audit_zangarmarsh_task_profiles.py` | INTERNAL-COMPAT | 赞加任务画像内部实现；CLI已退役，当前refiner可能复用 |
| `audit_zuldrak_handoffs.py` | RETIRED-GUARD | 祖达克施工期foundation交接快照；已自声明RETIRED |
| `audit_zuldrak_scope.py` | RETIRED-GUARD | 旧祖达克scope生成器，误命名audit；已自声明RETIRED |
| `build_35_55_candidate_catalog.py` | ACTIVE/REVIEW | 构建35–55候选目录；旧练级链，需确认是否仍是现役输入 |
| `build_35_55_cost_model.py` | ACTIVE/REVIEW | 构建35–55旧成本模型；迁移到统一Timing后审查 |
| `build_35_55_overlap_blocks.py` | ACTIVE/REVIEW | 构建35–55任务重叠块；可作为Route Optimization输入辅助 |
| `build_35_55_task_foundation.py` | ACTIVE/REVIEW | 构建35–55任务foundation；含旧XP实现，需迁统一XP Model |
| `build_39_55_eastern_kingdoms_candidate.py` | ACTIVE/REVIEW | 构建39–55东部王国候选；旧路线链待现役性审查 |
| `build_39_55_evidence_budget.py` | ACTIVE/REVIEW | 构建39–55证据/经验预算；需按XP owner审查 |
| `build_39_55_zero_purchase_budget.py` | ACTIVE/REVIEW | 构建39–55零采购预算；阶段模型待现役性审查 |
| `build_borean_tundra_foundation.py` | ACTIVE/REVIEW | 构建北风Task foundation/候选基础；迁移后应输出/补Task Cards |
| `build_cold_weather_flying_gate_state.py` | ACTIVE/REVIEW | 构建寒冷天气飞行门槛状态；RouteState/Availability派生 |
| `build_daily_task_timing_samples.py` | ACTIVE/REVIEW | 把日常实跑记录整理为Timing样本 |
| `build_dalaran_foundation.py` | ACTIVE/REVIEW | 构建达拉然foundation |
| `build_dalaran_route.py` | ACTIVE/REVIEW | 构建达拉然当前路线；迁移后目标输出Route Profile |
| `build_dalaran_transition_route.py` | ACTIVE/REVIEW | 构建达拉然转场路线/连接段 |
| `build_dk_outland_speed_routes.py` | ACTIVE/REVIEW | 构建DK外域速度Route Profiles；当前含自然语言fivebox状态，属于重点迁移对象 |
| `build_dragonblight_foundation.py` | ACTIVE/REVIEW | 构建龙骨foundation |
| `build_dragonblight_route.py` | ACTIVE/REVIEW | 构建龙骨路线；迁移后目标输出Route Profile |
| `build_grizzly_hills_foundation.py` | ACTIVE/REVIEW | 构建灰熊foundation |
| `build_grizzly_hills_route_skeleton.py` | ACTIVE/REVIEW | 构建灰熊路线骨架/空间结构 |
| `build_grizzly_hills_route.py` | ACTIVE/REVIEW | 构建灰熊正式路线；迁移后目标输出Route Profile |
| `build_grizzly_hills_scope.py` | ACTIVE/REVIEW | 构建灰熊正式scope |
| `build_hd_route_maps.py` | ASSET | 构建高清路线地图资源 |
| `build_hellfire_chain_overlap.py` | ACTIVE/REVIEW | 构建地狱火任务链/重叠关系辅助数据 |
| `build_hellfire_route.py` | ACTIVE/REVIEW | 构建地狱火普通路线；当前含旧fivebox自然语言，重点迁移 |
| `build_howling_foundation.py` | ACTIVE/REVIEW | 构建嚎风foundation |
| `build_howling_route.py` | ACTIVE/REVIEW | 构建嚎风正式路线；迁移后目标输出Route Profile |
| `build_howling_scope.py` | ACTIVE/REVIEW | 构建嚎风正式scope |
| `build_icecrown_entry_route.py` | ACTIVE/REVIEW | 构建冰冠入口路线草稿/转场 |
| `build_icecrown_foundation.py` | ACTIVE/REVIEW | 构建冰冠foundation |
| `build_icecrown_route_structured.py` | ACTIVE/REVIEW | 构建冰冠结构化正式候选 |
| `build_northrend_68_80_time_xp_model.py` | ACTIVE/REVIEW | 构建诺森德68–80时间/经验阶段模型；需改为消费统一XP/Timing |
| `build_northrend_task_universe.py` | ACTIVE/REVIEW | 构建诺森德任务全集；当前直接消费fivebox observations，需迁Task Card |
| `build_quest_reward_economy.py` | ACTIVE/REVIEW | 构建任务收益经济基础表 |
| `build_route_atlas_layered.py` | ACTIVE/REVIEW | Route Atlas早期分层工作台构建器；需确认是否仍有现役消费者，否则退役 |
| `build_route_atlas_prototype.py` | ACTIVE/REVIEW | Route Atlas原型构建器；需确认是否仍有现役消费者，否则退役 |
| `build_route_atlas_workbench.py` | ACTIVE/REVIEW | 唯一正式工作台HTML构建器；目标只消费publisher聚合数据，不注入业务fallback |
| `build_route_map_labels.py` | ASSET | 构建地图中文叠加标签 |
| `build_sholazar_cluster_insertion.py` | ACTIVE/REVIEW | 构建索拉查任务簇插入分析/数据 |
| `build_sholazar_foundation.py` | ACTIVE/REVIEW | 构建索拉查foundation |
| `build_sholazar_inserted_route.py` | ACTIVE/REVIEW | 构建索拉查插入后路线中间结果 |
| `build_sholazar_route_skeleton.py` | ACTIVE/REVIEW | 构建索拉查路线骨架 |
| `build_sholazar_route.py` | ACTIVE/REVIEW | 构建索拉查正式路线；迁移后目标输出Route Profile |
| `build_storm_peaks_foundation.py` | ACTIVE/REVIEW | 构建风暴峭壁foundation |
| `build_storm_peaks_route.py` | ACTIVE/REVIEW | 构建风暴峭壁正式路线；迁移后目标输出Route Profile |
| `build_uprez_zone_map.py` | ASSET | 对地图底图进行高清化/uprez处理 |
| `build_video_map_reference.py` | ACTIVE/REVIEW | 构建视频拆解地图参考 |
| `build_video_route_reference.py` | ACTIVE/REVIEW | 构建视频任务相对顺序/路线参考 |
| `build_zangarmarsh_global_solver_input.py` | ACTIVE/REVIEW | 构建赞加全局求解器输入，包装内部compat模块 |
| `build_zangarmarsh_task_profiles.py` | ACTIVE/REVIEW | 构建赞加任务画像初始数据 |
| `build_zuldrak_foundation.py` | ACTIVE/REVIEW | 构建祖达克foundation |
| `build_zuldrak_pre_route_audit.py` | ACTIVE/REVIEW | 构建祖达克路线前置审计/准备数据；名字虽为build，需按输出确认最终归类 |
| `build_zuldrak_route.py` | ACTIVE/REVIEW | 构建祖达克正式路线；迁移后目标输出Route Profile |
| `build_zuldrak_scope.py` | ACTIVE/REVIEW | 构建祖达克正式scope |
| `download_route_map_assets.py` | ASSET | 下载/缓存Route Atlas地图底图资源 |
| `dragonblight_semantic_steps_16_31.py` | MIGRATE | 龙骨16–31玩家步骤/语义拼装；迁Task Card/Route Profile/Presentation后退役或纯化 |
| `dragonblight_semantic_steps_32_51.py` | MIGRATE | 龙骨32–51玩家步骤/语义拼装；迁移后退役或纯化 |
| `dragonblight_semantic_steps.py` | MIGRATE | 龙骨基础semantic步骤/文案；当前是旧业务语义源之一 |
| `enrich_35_55_task_loot.py` | ACTIVE/REVIEW | 为35–55任务数据补掉落/奖励事实；迁移后应写Task Card事实层 |
| `estimate_route_atlas_timing.py` | ACTIVE/REVIEW | Route Atlas现役估时器；目标消费Task Card机制+Route Profile+Timing参数 |
| `export_a_route_task_details.py` | READ-ONLY | 导出旧A路线任务明细供分析 |
| `export_icecrown_entry_tasks.py` | READ-ONLY | 导出冰冠入口任务集合 |
| `export_route_atlas_player_view.py` | READ-ONLY | 从当前发布数据导出纯玩家视图用于冷读 |
| `export_zone_task_universe.py` | READ-ONLY | 导出指定地图任务全集 |
| `extract_route_task_evidence.py` | ACTIVE/REVIEW | 从现有来源提取路线任务证据；最终应落Task Card evidence |
| `finalize_hd_map_manifest.py` | ASSET | 生成/收口高清地图manifest |
| `fix_borean_amber_bogorok_transport.py` | RETIRE-CANDIDATE | 一次性修正北风琥珀崖→博古洛克交通；确认无引用后归档 |
| `grizzly_semantic_steps.py` | MIGRATE | 灰熊玩家步骤/任务语义拼装；当前旧事实/呈现源之一 |
| `howling_semantic_steps.py` | MIGRATE | 嚎风玩家步骤/任务语义拼装；当前含本轮未提交结构化status WIP |
| `icecrown_route_task_index.py` | REVIEW | 冰冠路线任务索引/映射辅助；需确认是否仍参与现役builder |
| `inspect_icecrown_quest_records.py` | READ-ONLY | 只读查看冰冠Questie任务记录 |
| `inspect_icecrown_repeat_clones.py` | READ-ONLY | 只读比较冰冠首轮/重复/日常clone差异 |
| `inspect_quest_ids.py` | READ-ONLY | 只读查询/核对任务ID |
| `inspect_questie_package.py` | READ-ONLY | 只读检查Questie包内容/字段 |
| `migrate_dragonblight_player_step_groups.py` | RETIRE-CANDIDATE | 龙骨stepGroups一次性迁移脚本；确认当前数据已迁完后归档 |
| `migrate_hellfire_dk_route_profile.py` | MIGRATE | 当前地狱火DK Route Profile一次性迁移/对账脚本；新Profile信息完整性审计通过并切换消费者后退役 |
| `migrate_hellfire_dk_task_cards.py` | MIGRATE | 当前地狱火DK Task Card一次性迁移/对账脚本；旧事实全部归属并禁止旧写入后退役 |
| `normalize_hellfire_task_cards_v1.py` | MIGRATE | 当前Task Card v1规范化脚本；数据全部符合最终schema且重复运行0变更后随迁移阶段退役 |
| `optimize_35_55_route.py` | ACTIVE/REVIEW | 35–55旧路线优化器；确认是否仍需保留为现役Route Optimization消费者 |
| `publish_icecrown_route.py` | ACTIVE/REVIEW | 冰冠当前publisher，把结构化候选写入现有workbench；未来并入统一Profile publisher |
| `rank_zero_purchase_zone_pool.py` | ACTIVE/REVIEW | 对零采购候选地图池做排序/分析；阶段模型待现役性审查 |
| `refactor_borean_steps_50_66.py` | RETIRE-CANDIDATE | 北风50–66步骤一次性重构脚本；确认已完成后归档 |
| `refactor_zang_route.py` | RETIRE-CANDIDATE | 赞加现有语义/stepGroups重构脚本；新Profile迁移后应退役 |
| `refine_zangarmarsh_task_profiles.py` | ACTIVE/REVIEW | 细化赞加任务画像，包装旧内部audit实现 |
| `report_icecrown_airship_starts.py` | READ-ONLY | 输出冰冠飞艇/入口候选报告 |
| `report_sholazar_phase_tasks.py` | READ-ONLY | 输出索拉查阶段任务报告 |
| `solve_zangarmarsh_exact_v0.py` | SOLVER | 赞加exact v0求解器实验 |
| `solve_zangarmarsh_exact_v1.py` | SOLVER | 赞加exact v1求解器实验 |
| `solve_zangarmarsh_first_run_v1.py` | SOLVER | 赞加首跑v1求解/候选方案 |
| `solve_zangarmarsh_global_core43.py` | SOLVER | 赞加global core43求解器 |
| `summarize_a_route_task_details.py` | READ-ONLY | 汇总旧A路线任务明细 |
| `summarize_dragonblight_hubs.py` | READ-ONLY | 汇总龙骨Hub/任务中心信息 |
| `summarize_grizzly_candidate.py` | READ-ONLY | 汇总灰熊候选路线/任务 |
| `summarize_grizzly_hills_handoffs.py` | RETIRED-GUARD | 汇总已退役灰熊handoff快照；文件已自声明RETIRED |
| `trace_icecrown_deaths_rise.py` | READ-ONLY | 追踪冰冠死亡高地相关任务链 |
| `trace_icecrown_mid_south.py` | READ-ONLY | 追踪冰冠中南部任务链/依赖 |
| `trace_icecrown_shadow_vault.py` | READ-ONLY | 追踪冰冠暗影拱顶任务链 |
| `trace_icecrown_vanguard_chain.py` | READ-ONLY | 追踪冰冠先锋军相关任务链 |
| `update_hellfire_entry_transport.py` | RETIRE-CANDIDATE | 一次性更新地狱火入口交通；确认无引用后归档 |
| `zang_semantic_steps.py` | MIGRATE | 赞加玩家步骤/任务语义拼装；需迁新三真源架构 |
| `zuldrak_semantic_steps.py` | MIGRATE | 祖达克玩家步骤/任务语义拼装；需迁新三真源架构 |

## 5. 当前确定的退役清债

### 已自声明RETIRED

上表`RETIRED-GUARD`文件已经没有资格作为现役规则/审计依据。下一步只需要做消费者检查：

- 若无人import/调用：移入`docs/archive/scripts/`并在archive README登记；
- 若仍被某现役入口调用：先切消费者，再移动；
- 不允许因为guard“很短没影响”而永久留在顶层。

### 一次性修改器候选

`RETIRE-CANDIDATE`不能仅凭命名直接删除。逐项确认：

1. 是否被`cli.py`/builder/test import；
2. 是否仍是当前数据唯一重建入口；
3. 是否只对已经完成的一次迁移/修复有意义；
4. 若只剩历史解释价值，移archive；
5. 若仍有可复用逻辑，提取到正式builder/lib后再退役修改器。

## 6. 新架构切换后的目标目录

顶层`scripts/`最终只应保留：

- 当前Task Card构建/迁移入口；
- Route Profile builder/publisher；
- XP/Timing等模型实现入口；
- 跨Profile稳定audit；
- 地图/资源工具；
- 仍有明确当前用途的只读inspect/export。

一次性历史迁移、旧阶段apply/refactor、RETIRED guard进入`docs/archive/scripts/`；共享可复用代码优先进入`lib/`而不是继续堆顶层脚本。

## 7. 机械门禁

后续测试必须检查：

- scripts根目录所有`.py`均在本README登记；
- `RETIRED-GUARD`不得被现役代码import/调用；
- archive scripts不得被现役链import；
- 业务事实不能只存在于semantic/builder硬编码；
- 正式Profile切换完成后，禁止任何地图脚本直接写`workbench-routes.json`；
- 新增一次性迁移脚本必须带退出条件，完成后退役。
