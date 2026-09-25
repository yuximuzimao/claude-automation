# `scripts/` 目录

用途：这是`scripts/`文件夹的当前脚本目录，只回答“这里有什么、每个脚本现在做什么”。**它不决定业务流程**；该运行哪个脚本只看对应业务owner/SOP。已经退出当前体系的脚本只在`docs/archive/scripts/`保留，不在本目录维护兼容入口。

当前顶层共有 **115 个 `.py` 文件**。

视频取证与OCR辅助工具位于[`video-extraction/`](video-extraction/README.md)，只在需要重新核验原始视频画面时按视频流程调用。

| 文件 | 当前用途 |
| --- | --- |
| `analyze_dragonblight_reachability.py` | 分析龙骨荒野可达性 |
| `analyze_icecrown_components.py` | 分析冰冠组件/依赖 |
| `analyze_loot_reward_filter.py` | 分析掉落奖励筛选 |
| `analyze_questie_journey.py` | 分析Questie历程 |
| `analyze_route_atlas_geometry.py` | 分析Route Atlas几何 |
| `audit_all_route_profiles.py` | 只读批量包装唯一`rebuild_route_profile.audit_profile()`，逐正式Profile汇总Stage 1–14 implementation/artifact状态与Stage 14 issue counts；可选读取统一XP/Economy/Review JSON输入，不修改Route Profile或Generated Product。 |
| `audit_generated_cutover.py` | 只读14张正式Route当前generated artifacts与真源schema/依赖指纹，调用现有Stage 14/project gate做最终cutover机械审计；不会重跑任何业务owner，也不会写正式页面。动态XP/Economy/Review缺完整runtime时明确保留requirements，不伪造pass。 |
| `audit_hd_route_maps.py` | 核对高清路线地图资源/配准 |
| `audit_icecrown_draft_readiness.py` | 冰冠维护期非阻塞review queue；只检查现役结构/机制风险，旧`level_80_economy`已退出review触发，经济完整性统一交Stage 9/10 |
| `audit_route_atlas_player_text.py` | 直接读取当前Publisher结构化步骤，检查Route Display/Task Presentation已定义的玩家可见文字机械规则。 |
| `audit_route_interaction_continuity.py` | 路线设计/重排后的固定只读局部优化检查；机械列出同step、同location的一轮无条件NPC接/交里被其它NPC隔开的同NPC候选，不自动重排、不作发布硬门禁。 |
| `audit_route_objective_anchors.py` | 用当前Route Profile执行坐标与Questie目标刷新坐标做空间审计；缺外部Questie证据时明确返回requirements。 |
| `audit_sholazar_whole_map_merge.py` | 索拉查整图合并/访问次数核对 |
| `audit_workbench_browser.py` | 直接打开当前正式Route Atlas页面，检查页面可加载、地图/HUD/步骤/控件等基本运行状态；不与旧页面对拍。 |
| `audit_workbench_surface_semantics.py` | 对14张候选路线做玩家表面语义、任务标签与接/做/交样式机械检查；只验证Stage 13输出。 |
| `audit_workbench_visible_task_semantics.py` | 浏览器层核对可见任务动作、标签和颜色是否与Publisher结构一致；不从DOM反推Task Card/Profile。 |
| `audit_zangarmarsh_global_solver_input.py` | 全局求解器输入内部实现；CLI已退役，当前wrapper可能复用 |
| `audit_zangarmarsh_task_profiles.py` | 赞加任务画像内部实现；CLI已退役，当前refiner可能复用 |
| `build_35_55_candidate_catalog.py` | 构建35–55候选目录；旧练级链，需确认是否仍是现役输入 |
| `build_35_55_overlap_blocks.py` | 构建35–55任务重叠块；可作为Route Optimization输入辅助 |
| `build_35_55_task_foundation.py` | 构建35–55任务foundation；保留旧调用接口，但任务XP公式与服务器倍率已全部委托`lib/route_xp.py` + `data/xp-model/model-config.json`，本脚本不再拥有XP规则。 |
| `build_39_55_eastern_kingdoms_candidate.py` | 构建39–55东部王国候选；旧路线链待现役性审查 |
| `build_39_55_evidence_budget.py` | 构建39–55路线研究的证据/经验预算；XP计算委托统一XP模型，不维护第二套XP公式。 |
| `build_39_55_zero_purchase_budget.py` | 构建39–55零采购预算；阶段模型待现役性审查 |
| `build_borean_tundra_foundation.py` | 构建北风候选路线研究所需的Task foundation；只服务候选/证据研究，不是正式Route Profile真源。 |
| `build_cold_weather_flying_gate_state.py` | 构建寒冷天气飞行门槛状态；RouteState/Availability派生 |
| `build_daily_task_timing_samples.py` | 从当前Task Card识别日常、从Route Profile判断当前路线成员，再从Journey生成接取→完成墙钟样本。 |
| `build_dalaran_foundation.py` | 构建达拉然候选路线研究所需的foundation；XP值委托统一XP owner，不维护第二套倍率。 |
| `build_dragonblight_foundation.py` | 构建龙骨foundation |
| `build_grizzly_hills_foundation.py` | 构建灰熊foundation |
| `build_grizzly_hills_route_skeleton.py` | 构建灰熊路线骨架/空间结构 |
| `build_grizzly_hills_scope.py` | 构建灰熊正式scope |
| `build_hd_route_maps.py` | 构建高清路线地图资源 |
| `build_hellfire_chain_overlap.py` | 构建地狱火任务链/重叠关系辅助数据 |
| `build_howling_foundation.py` | 构建嚎风foundation |
| `build_howling_scope.py` | 构建嚎风正式scope |
| `build_icecrown_entry_route.py` | 构建冰冠入口路线草稿/转场 |
| `build_icecrown_foundation.py` | 构建冰冠foundation |
| `build_icecrown_route_structured.py` | 构建冰冠结构化正式候选 |
| `build_program_continuity.py` | 仅在Program顺序/version/entry contract变化或没有可用基线时完整重建Program Continuity；调用共享Replay引擎，但不运行Movement/Service/Timing/XP/Economy/Display/Publisher。 |
| `build_program_economy.py` | 从当前Program XP/Timing建立Economy基线；若XP合法为requirements且没有member reports，直接刷新Program Economy requirements/Timing依赖，不预加载所有成员；成本只读显式runtime输入。 |
| `build_program_movement.py` | 只读取各成员当前Movement artifact并计算Program边界；成员Movement缺失直接失败，禁止内部重算各图。 |
| `build_program_service_context.py` | 从当前Program Movement一次建立Program成员Service Context基线；不重算成员Movement。 |
| `build_program_timing.py` | 初次/明确全Program Timing重建时，从当前Continuity/Movement/Service计算各成员Timing一次并汇总边界与总时间。 |
| `build_program_xp.py` | 用显式Program XP起点建立当前Program XP基线；缺entry_state时立即生成requirements，不预加载所有成员Profile/Task Card，也不从标题/旧路线猜。 |
| `build_route_atlas_layered.py` | Route Atlas早期分层工作台构建器；需确认是否仍有现役消费者，否则退役 |
| `build_route_atlas_prototype.py` | Route Atlas原型构建器；需确认是否仍有现役消费者，否则退役 |
| `build_route_display.py` | 从当前Profile/Task Card真源 + 已有Movement/Timing artifacts生成一张完整Route Display基线；不会重算任何业务owner。 |
| `build_route_economy.py` | 只读取当前XP/Timing artifacts并重算一个Profile Economy/G-hour；成本输入显式传入，缺失时保持partial/requirements。 |
| `build_route_map_labels.py` | 构建地图中文叠加标签 |
| `build_route_movement.py` | 只重算一个Profile的canonical Movement并写入generated store；不调用Replay/Program/Service/Timing/XP/Economy。 |
| `build_route_replay.py` | 只重算一个Profile的Replay/Availability并写入generated store；不调用Program/Movement/Service/Timing/XP/Economy。 |
| `build_route_review_trigger.py` | Stage 10独立物化入口；按`program/profile + id`只读取当前Stage 3/4–9 generated artifacts和可选version-bound review context，生成`review-trigger` artifact；Program成员必须走Program scope，独立Profile才走Profile scope；不得重算上游、决定now/later/never或修改Route Profile。 |
| `build_route_service_context.py` | 只读取当前Movement artifact并重算一个Profile的Service Context；缺Movement直接失败，不偷偷重算上游。 |
| `build_route_timing.py` | 只读取当前Replay/Movement/Service artifacts并重算一个Profile Timing；不重跑上游，也不自动执行XP/Economy。 |
| `build_route_xp.py` | 只读取当前Replay并重算一个Profile XP；外部起始XP通过显式runtime JSON传入，缺失时保留requirements，不推断。 |
| `build_sholazar_cluster_insertion.py` | 构建索拉查任务簇插入分析/数据 |
| `build_sholazar_foundation.py` | 构建索拉查foundation |
| `build_sholazar_inserted_route.py` | 构建索拉查插入后路线中间结果 |
| `build_sholazar_route_skeleton.py` | 构建索拉查路线骨架 |
| `build_storm_peaks_foundation.py` | 构建风暴峭壁foundation |
| `build_task_evidence_index.py` | 解析Questie有效任务库、奖励库、当前Task Card和现役结构化资料，生成可删除重建的Task Evidence查询缓存。 |
| `build_task_presentation.py` | 只把一个Task Card在指定Profile下的Task Presentation打印到stdout，用于检查；正式写入Display走`update_route_display_task.py`，不产生可手改中间文件。 |
| `build_timing_quest_source_inputs.py` | Stage 7 Effective Quest Source输入构建器；只从当前Questie包机械派生objective数量/来源关系，可写`data/timing/quest-source-inputs.json`缓存；不得读取Task Card guide/路线文案，也不得独立成为Derived Timing真源。 |
| `build_uprez_zone_map.py` | 对地图底图进行高清化/uprez处理 |
| `build_video_map_reference.py` | 构建视频拆解地图参考 |
| `build_video_route_reference.py` | 构建视频任务相对顺序/路线参考 |
| `build_zangarmarsh_global_solver_input.py` | 构建赞加全局求解器输入，包装内部compat模块 |
| `build_zangarmarsh_task_profiles.py` | 构建赞加任务画像初始数据 |
| `build_zuldrak_foundation.py` | 构建祖达克foundation |
| `build_zuldrak_pre_route_audit.py` | 构建祖达克路线前置审计/准备数据；名字虽为build，需按输出确认最终归类 |
| `build_zuldrak_scope.py` | 构建祖达克正式scope |
| `check_workbench_js.py` | 用真实浏览器检查候选workbench JS初始化/运行时错误；不解释业务数据。 |
| `check_workbench_resume_playback.py` | 验证候选页Profile/step恢复、播放和HUD交互行为；只检查UI合同。 |
| `download_route_map_assets.py` | 下载/缓存Route Atlas地图底图资源 |
| `enrich_35_55_task_loot.py` | 为35–55候选研究数据补掉落/奖励证据；运行时必须用`--database`显式提供AzerothCore WotLK五份SQL所在目录，正式单任务事实仍以Task Card为准。 |
| `enrich_task_card_rewards.py` | 单task_id精确补Task Card rewards；AzerothCore提供金币/奖励物/SellPrice，Questie补zhCN名、full XP、声望；逐任务迁移使用 |
| `export_a_route_task_details.py` | 导出旧A路线任务明细供分析 |
| `export_icecrown_entry_tasks.py` | 导出冰冠入口任务集合 |
| `export_zone_task_universe.py` | 导出指定地图任务全集 |
| `extract_route_task_evidence.py` | 从现有来源提取路线任务证据；最终应落Task Card evidence |
| `finalize_hd_map_manifest.py` | 生成/收口高清地图manifest |
| `icecrown_route_task_index.py` | 冰冠路线任务索引/映射辅助；需确认是否仍参与现役builder |
| `import_leatrix_flight_times.py` | 把Leatrix Plus静态飞行秒数转换成项目内版本化Timing输入；当前只是stage 7外部source importer，flight-point registry与Timing resolver未接通前必须标“未接入”，不能独立算作Derived Timing完成 |
| `inspect_icecrown_quest_records.py` | 只读查看冰冠Questie任务记录 |
| `inspect_icecrown_repeat_clones.py` | 只读比较冰冠首轮/重复/日常clone差异 |
| `inspect_quest_ids.py` | 只读查询/核对任务ID |
| `inspect_questie_package.py` | 只读检查Questie包内容/字段 |
| `inspect_task_evidence.py` | 按task_id读取当前Task Evidence Index中的聚合证据；只读。 |
| `optimize_35_55_route.py` | 35–55旧路线优化器；确认是否仍需保留为现役Route Optimization消费者 |
| `rank_zero_purchase_zone_pool.py` | 对零采购候选地图池做排序/分析；阶段模型待现役性审查 |
| `rebuild_publisher_payload.py` | 只读取generated store当前单Route Display + Route UI并重新生成该Route Publisher payload，再写回generated store；不解释业务真源。 |
| `rebuild_route_profile.py` | 显式完整诊断/对抗审计一个Profile的各owner产物；不是日常修改入口，也不负责正式写页。 |
| `record_route_economy_observation.py` | 追加一条原始全路线 Economy Observation；只记录金币差/资产数量/污染事实，不修改 Task Card rewards，不自行生成市场估值 |
| `refine_zangarmarsh_task_profiles.py` | 细化赞加任务画像，包装旧内部audit实现 |
| `render_route_assets.py` | 只按profile_id读取generated store当前Publisher payload并渲染HTML/player-view；要求显式`--output-dir`，不会自动选择正式目录，也不运行任何业务计算。 |
| `report_icecrown_airship_starts.py` | 输出冰冠飞艇/入口候选报告 |
| `report_sholazar_phase_tasks.py` | 输出索拉查阶段任务报告 |
| `solve_zangarmarsh_exact_v0.py` | 赞加exact v0求解器实验 |
| `solve_zangarmarsh_exact_v1.py` | 赞加exact v1求解器实验 |
| `solve_zangarmarsh_first_run_v1.py` | 赞加首跑v1求解/候选方案 |
| `solve_zangarmarsh_global_core43.py` | 赞加global core43求解器 |
| `summarize_a_route_task_details.py` | 汇总旧A路线任务明细 |
| `summarize_dragonblight_hubs.py` | 汇总龙骨Hub/任务中心信息 |
| `summarize_grizzly_candidate.py` | 汇总灰熊候选路线/任务 |
| `trace_icecrown_deaths_rise.py` | 追踪冰冠死亡高地相关任务链 |
| `trace_icecrown_mid_south.py` | 追踪冰冠中南部任务链/依赖 |
| `trace_icecrown_shadow_vault.py` | 追踪冰冠暗影拱顶任务链 |
| `trace_icecrown_vanguard_chain.py` | 追踪冰冠先锋军相关任务链 |
| `update_program_continuity_from_member.py` | 成员Replay/Availability状态变化时保留变化点之前的Continuity edge；CLI显式接收本次真实变更成员集合并按需加载Replay输入，只向后传播到新RouteState重新与旧输出收敛的位置，之后后缀直接复用。Program顺序/version/entry变化会拒绝增量并要求完整基线。 |
| `update_program_member_economy.py` | 只重算指定成员Economy并重新求Program总和/Gh；其它成员Economy原样保留。XP若影响一段后缀，则SOP只逐个更新那段后缀成员，不碰前缀。 |
| `update_program_member_service_context.py` | 只重算指定Program成员的Service Context并重新汇总Program状态；其它成员结果原样保留。 |
| `update_program_member_timing.py` | 只重算指定Program成员Timing，再用现有其它成员Timing重新汇总Program总时间；不重算其它成员。 |
| `update_program_xp_from_member.py` | XP变化时保留变化点之前的成员结果，只从指定成员开始向Program末尾传播重算；前缀绝不重算。 |
| `update_route_display_task.py` | 读取当前Display + Task Card，重算该task Presentation并只替换Display对应字段；结果通过generated store写回。备注/fivebox不动地图/Timing，任务名变化才用`--identity-changed`更新动作文本。 |
