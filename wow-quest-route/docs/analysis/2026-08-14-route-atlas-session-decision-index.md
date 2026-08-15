# Route Atlas 8/12—8/14 会话决策历史索引

日期：2026-08-14
状态：历史/阶段决策索引；不再承担长期总规则入口

长期权威现为`docs/rules/README.md`路由到的Route Atlas子规则：路线数据/裁剪/优化见`docs/rules/route-atlas-optimization.md`，前端与地图资源见`docs/rules/route-atlas-ui-and-assets.md`。本文只保留8/12—8/14形成过程、赞加阶段状态、理论探索和当时专项文档导航。

用途：确认本轮围绕“地图路线 + 任务知识节点 + 关系图谱 + 路线计算 + 增量插入 + 动态HTML”的讨论是否已经落档，并明确旧方案与当时当前方案的层级。后续会话必须先读长期总规则，再按需使用本文恢复这段历史上下文。

## 1. 产品原始需求与知识图谱方向

权威记录：`docs/analysis/2026-08-12-route-atlas-quest-knowledge-graph-concept.md`

已记录：
- 地图负责执行导航，任务知识卡负责查细节，关系图谱负责设计/复盘；
- Questie提供基础事实，项目重点补关系、路线、五开经验、特殊机制与实跑纠错；
- 任务之间不仅有前置，还包括同目标怪/物、目标区重叠、同接取Hub、同交付Hub、同NPC、同洞穴/走廊、unlock-then-return、fivebox synergy/conflict、自然掉落触发等关系；
- 后台实体建议包含quest、npc、area、quest_relation、route_circle、waypoint、observation；
- Questie事实与实跑观察分层，不互相覆盖。

## 2. Route Atlas 前端与Questie数据边界

权威记录：`docs/analysis/2026-08-12-route-atlas-v1-contract.md`

当前有效：
- 唯一前端载体为HTML工作台；不再以自动导出PNG/JPG作为主实现；
- Route Atlas负责宏观方向/顺序，Questie继续承担游戏内精确目标定位；
- 数据层按 `Questie Raw → Questie Effective/Titan派生层 → 单任务知识节点+关系 → 路线版本/节点 → HTML` 分层；
- Questie Raw不可因实跑而改写；
- 地图底图按0–100 Questie坐标体系校准，3–5个固定锚点验收后锁定；
- 关系库先保留可计算原始事实，不提前硬编码“多少距离才算同一区域”。

最新界面覆盖说明：
- 旧文档允许任务卡展示Questie基础字段；当前决定是这些字段后台继续保留，但游戏插件已经能直接看到的等级、经验、普通坐标、基础目标暂不占前端卡片版面。
- “暂不展示”不是“从任务知识模型删除”。

## 3. 路线计算理论与数据标签方案

### 3.1 结构化标签/关系/数值特征

权威记录：`docs/analysis/2026-08-13-route-atlas-optimization-framework.md`

已记录并继续有效的数据原则：
- 不使用只有关键词的扁平标签；底层同时保留 `typed facts + typed relations + numeric features`；
- human-facing稳定标签包括 `scope:*`、`objective:*`、`chain:*`、`trip:*`、`terrain:*`、`route:*` 等；
- machine relations包括 `precedes`、`same_accept_npc`、`same_turnin_npc`、`same_direct/resolved_creature`、`same_direct/resolved_object`、`same_required_item`、`spatial_overlap`、`same_chain`、`same_excursion_block` 等；
- 标签用于解释，不应替代底层事实和成本计算；
- 总成本目标按 `T_travel + T_objective_service + T_accept_turnin + T_forced_wait + T_other_known_cost` 分解。

### 3.2 母模型/全局优化理论探索

权威记录：
- `docs/analysis/2026-08-13-route-atlas-mother-model-selection.md`
- `docs/analysis/2026-08-13-route-atlas-global-optimization-model-v0.md`

已记录：
- 曾选择PC-SP with Stateful Service Requirements and Flexible Service Locations作为最贴近问题结构的数学母模型；
- 讨论过state-space DP / labeling、MILP/Branch-and-Cut、flexible service location decomposition、shared-service/covering等精确优化方向；
- “理论全局最优”只有在当前模型被证明optimal时才能这样称呼。

但这套内容现在属于**理论/对照工具层**，不是最终玩家路线的直接生成规则。

### 3.3 当前真正生效的路线构建方法

最高权威：`docs/analysis/2026-08-14-route-atlas-cluster-incremental-insertion-method.md`

当前冻结方法：
1. Questie/人工事实层；
2. 完全相同真实目标实体形成Target Cluster；
3. 前置关系形成Prerequisite Network；
4. 人工把目标簇拆成真实Spatial Instance；
5. 背景目标单独作为Background Layer；
6. 选择第一个簇构造R1；
7. 后续逐簇/逐任务按 `插A → 插C → 插T → 局部稳定 → 重算炉石 → 保存Rn` 增量插入；
8. 已验收旧路线原则上只做局部重排；
9. 不同目标簇默认无先后，只有显式前置才建立顺序；
10. 旧exact/CP-SAT/MIP/solver保留为对照、异常检测、局部插入成本参考，不直接决定玩家路线。

因此“路线计算方案”并没有丢：早期全局优化理论和最终人工可审计增量法都在，并且当前优先级已经明确。

## 4. 一个一个插入、历史快照和Codex补档

权威记录：`docs/analysis/2026-08-14-zangarmarsh-route-version-index.md`

当前状态：
- Codex在2026-08-14补齐此前因写入/协作中断缺失的17个R快照；
- 版本索引现在连续覆盖R1–R71；
- R1–R62主要是当时角色状态下的局部历史快照，不等于完整从零路线；
- R63起恢复“当前角色已完成、但下一组角色从零攻略仍必须包含”的任务；
- Rn历史快照只新增、不覆盖；
- 特殊/广域任务严格一个一个插入；
- 每版保留新增任务/簇、局部路线变化、炉石变化及理由。

这解决了此前“已完成任务从当前局部路线消失，但未来攻略仍需要”的问题：当前局部快照与最终从零复用路线被明确分开。

## 5. 完整任务宇宙与最终复用路线

任务边界权威：`docs/analysis/2026-08-14-zangarmarsh-complete-task-universe-audit.md`

结论：
- Questie候选98条全部归类；
- 普通开放世界55条；
- 副本/副本引导、跨图、库存条件、极低掉率机会、专业、职业、节日/阵营分别独立分类；
- 不再把最初53条局部清单误当作完整任务宇宙。

最终路线权威：`docs/analysis/2026-08-14-zangarmarsh-final-reusable-route-v1.md`

状态：
- 从零可复用版；
- 已补回当前角色先前完成、但未来角色需要的任务；
- 当前仍等待下一组角色实跑，不标记verified。

## 6. 动态地图审计流程

权威记录：
- `docs/analysis/2026-08-14-zangarmarsh-route-version-index.md`
- `docs/analysis/2026-08-14-zangarmarsh-final-map-audit.md`
- `data/routes/route-atlas-workbench.html`（现行唯一工作台；当时独立赞加preview已取消）

当前固定流程：
- 不是“每插一个任务就看一次完整动态图”；
- 一个地图的任务插入/恢复流程全部完成后，统一生成动态图；
- 再从整图角度检查明显异常、局部最优累积后是否形成全局问题；
- 必要时重新打开较大的局部窗口做最终调整；
- 动态HTML可以直接作为后续正式前端的基础，不再把它只当一次性审计工具。

赞加最终整图审计已记录：65个停靠点、3次炉石；重新枚举最终收尾顺序和北部终局局部顺序后，未发现需要大范围推翻的几何异常。

## 7. 当前前端显示决定（最新覆盖）

记录位置：`docs/analysis/2026-08-14-zangarmarsh-final-reusable-route-v1.md` §13。

最新决定：
- 地图在上，文字在下；不再使用窄右栏；
- 步骤直接显示中文任务名及“接/做/交”等人类语义；
- 当前步骤下面展示关联任务，点击任务名切换任务知识卡；
- 前端知识卡优先展示特殊机制、五开注意、地形入口、任务之间的关联、目标簇/空间实例、当前路线的插入理由/合并理由等；
- Questie已经能直接看到的基础信息暂不重复展示，但后台仍保留；
- 路线专属信息和单任务长期知识严格区分，前端可联动展示；
- 动态箭头视觉参数固定回R11观感：普通1.25、当前3.0、炉石1.8/3.4、箭头5×5，并使用non-scaling-stroke。

实现更新：当前HTML已接入任务知识卡第一层，包括稳定标签、部分任务关系、Target Cluster / Spatial Instance、路线编排理由和可审计路线特征；65级当前执行版也复用了这一结构。完整后台typed facts、typed relations和numeric features仍未全量消费，因此是“第一层实现完成、全量结构化接入仍待继续”。

## 8. 十字军光环与估时

记录位置：`docs/analysis/2026-08-14-zangarmarsh-final-reusable-route-v1.md` §13。

当前口径：
- 原纯跑图假设14 yd/s；
- 十字军光环使纯坐骑段按16.8 yd/s；
- 只修正纯坐骑移动；护送、脚本飞行、战斗、拾取、交互、炉石不乘1.2；
- 当前工程估算常规约5小时30分；9729条件护送触发时约5小时36分；
- 下一组角色实跑后回填实际移动/执行时间。

## 9. 当前文档优先级

长期方法现由`docs/rules/README.md`路由到对应子规则。后续恢复按以下层级理解：
1. 最新用户明确现场状态 + `docs/verified-routes/CURRENT.md`决定当前角色该做什么；
2. `docs/rules/route-atlas-optimization.md`与`docs/rules/route-atlas-ui-and-assets.md`分别决定跨地图路线方法与前端/资源契约；
3. 本索引、增量方法、赞加版本索引、complete-task-universe、final-map-audit与NEAT保存8/12—8/14形成过程和赞加地图特定事实；
4. `2026-08-12-route-atlas-v1-contract.md`与8/13 optimization/mother-model/global-model保存早期契约、理论和数据设计来源；
5. 更早concept文档保存原始需求来源，不覆盖后续长期总规则。

## 10. 本次核对结论

本轮核心讨论没有发现只存在聊天、完全没有落档的关键方法性结论。Codex已补齐缺失的历史R快照；路线计算理论、当前增量路线方法、标签/关系数据设计、完整任务宇宙、已完成任务回填、动态整图审计和最新前端规则均有持久文件。

真正仍未完成的是实现层：当前动态HTML还只是把其中一部分任务知识显示出来，尚未完整消费后台设计中的typed relations、numeric features、关系标签和逐步插入/边际成本解释。后续前端应基于这些既有结构化设计继续，而不是把任务知识简化成“只有操作备注”。
