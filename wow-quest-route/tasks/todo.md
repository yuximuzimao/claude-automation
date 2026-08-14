# 当前待办

只记录尚未完成且会改变下一步工作的事项。已完成过程由Git、工作区备份、`docs/analysis/`和会话归档保留，不在这里重复。

## 首组圣骑士到80级

- [ ] 从`docs/verified-routes/CURRENT.md`指定的唯一玩家攻略继续，以最低号为准；当前主线一直推进到80级，不在55级停止。
- [x] 55→58费伍德→冬泉效率分支已完成首组实跑并归档到`docs/verified-routes/sessions/2026-08-11-level55-58-felwood-winterspring-closure-neat.md`；该路线未证明优于老手艾萨拉基线，后续新号暂不直接固化替换。
- [x] 当前首组已在奥格瑞玛提前买齐最终6种雕文；后续新号路线固定在20级、40级加入拍卖行雕文检查/购买节点。
- [ ] 外域58→68首组正在实跑。当前五号均61级，地狱火Questie代表号已完成38个任务、仍有16个已接任务；继续按实际可接任务推进，不提前发布模型编排的完整任务顺序。地狱火分圈/重叠表只作辅助，任务存在性以时光服现场与历程为最高真值。阶段结束后读取Questie历程，按真实接取/交付/等级/折返重建第二版；仍保留最高号65/66/67/68四个等级截止检查。
- [ ] 68级左右进入诺森德后沿成熟主轴连续清图；同样采用单地图全清、最少折返的路线方法，直到80级停止。
- [ ] 每个实跑任务块结束后，用最低号真实等级/经验更新`CURRENT.md`；新等级覆盖旧理论预测。
- [ ] 用户反馈掉率、共享机制、地形、接交异常或额外折返时，先修当前攻略和对应任务卡，再更新`data/observations/`与`ERROR-BOOK.md`。
- [ ] Route Atlas 产品边界已冻结到`docs/analysis/2026-08-12-route-atlas-v1-contract.md`。赞加沼泽首个工作台：`data/routes/zangarmarsh-route-atlas-prototype.html`。2026-08-13用户已先后验证NPC与任务目标点云均和游戏内Questie对齐。几何分析基建已新增`lib/route_atlas_geometry.py`、`scripts/analyze_route_atlas_geometry.py`和`data/route-atlas/zangarmarsh-geometry-analysis.json`：当前58–68窗口内有45个任务具备本图可计算点云，共990个任务对；已计算中心、bbox、p50/p90半径、PCA主轴/方向强度、从接取NPC到最近目标点的方向和距离，以及双向最近邻p50/p90、中心距、最近点距和bbox IoU。首轮结果验证局部任务可自动得到进场方向/扫怪轴，同时暴露《时尚无罪》这类跨全图“背景任务”不能用单一中心代表；后续分圈必须区分局部怪区与广域背景任务。关系层同步修正为既比较直接objective，也比较Item→NPC/Object解析后的实际目标，因此可识别《偷回蘑菇》与《你死我活》虽然原始objective不同、实际却共享同一批安葛洛什怪。新增`docs/analysis/2026-08-13-route-atlas-optimization-framework.md`：路线优化正式采用“任务标签摘要 + typed relations + 事件DAG/偏序 + excursion block + multi-trip assignment master + precedence-constrained sequencing subproblem”的混合框架；事件DAG已进一步冻结为每个普通任务三个动作节点`A(Q)=接取 / C(Q)=完成 / T(Q)=交付`，内部依赖`A→C→T`，任务链依赖落在前后任务的具体事件之间（通常`T(Q1)→A(Q2)`）。任意时刻前置已全部满足且尚未执行的事件组成Ready Set；优先级不再使用模糊“高/低”或任意加权总分，而采用可复现规则：当前位置零移动成本的Ready事件先做local closure；需要移动时按`feasible → circle_slack升序 → defer_excursion_penalty降序 → defer_route_regret降序 → insertion_delta升序 → critical_unlock_gain降序 → same_stop_batch_gain降序 → stable ID`做字典序比较。Ready Accept只有在当前local closure中是必做，远距离Accept不享受永久类型bonus，其价值通过解锁收益/延期折返惩罚自然体现。以excursion depth而非普通任务链长度作为最低回访圈数下界，对待插入任务F先做前置可行性过滤，再比较插入A/B/C圈的边际成本；允许空间孤立但链内高度重合的任务链作为独立闭环候选。主优化目标进一步冻结为预计总完成时间最小，而非圈数最少；所有求解结果必须标记`PROVEN_OPTIMAL / BEST_FOUND_WITH_GAP / HEURISTIC_ONLY`，只有精确求解器证明无更优解时才称理论全局最优。当前已安装并固化`OR-Tools>=9.15,<10`作为第四层精确优化依赖；CP-SAT与SCIP/MIP均已接入，旧`slack/regret/insertion/local closure`字典序规则只作初始解/fallback，不承担最终路线决策。已核对实际Questie 11.34.0源码：`preQuestSingle`为OR（任一前置完成即可），`preQuestGroup`为AND（全部完成；正ID还涉及exclusiveTo替代语义，负ID跳过exclusiveTo检查），因此原型展示层合并的`prerequisite_ids`不能用于精确求解；已开始在生成数据中保留`pre_quest_single`与`pre_quest_group`原始类型。下一步实现稳定派生标签、A/C/T事件DAG、动态Ready Set、chain/excursion depth，并把几何、任务耗时和链结构共同送入全局求解；洞穴入口、上下层、不可直达地形等仍由任务卡人工补充。TitanReforged完整effective resolver仍是后续数据层任务。

- [x] 2026-08-13 母模型与 exact 求解器结构验证已落地：`PC-SP + Stateful Service Requirements + Flexible Service Locations + Shared-Service Coverage`，实现见`lib/route_atlas_exact.py`。旧8任务 exact v0 只保留为求解器结构验证：后续审查确认`questDB.lua`字段12=`preQuestGroup`、13=`preQuestSingle`，而早期Route Atlas原型常量曾写反，旧v0前置类型因此可能被交换，不能继续当赞加路线结论；已修正原型常量，下一次必须用修正后的前置数据重新求解。
- [x] 赞加任务基础数据层已完成第一版“公式+输入+物化结果”：`data/route-atlas/zangarmarsh-task-profiles.json`长期保存任务类型、数量/掉率/期望击杀、单怪时间、Objective/移动/总耗时及来源；特殊任务优先写`data/route-atlas/zangarmarsh-task-overrides.json`人工永久覆盖。CMaNGOS WotLK/TBC出生刷新代理已由Codex提取到`data/route-atlas/world-respawn-proxy.json`并接入任务公式；任务卡已显示刷新证据及Item-start起始物掉率/期望击杀/获取耗时。Item-start正式建模为`G(Q)=获取起始物 → A(Q) → Objective → T(Q)`，G可与同实体其他任务共享刷怪流；《抽水泵结构图》《你见过鱼人吗？》《枯萎的孢芽》《灵魂之盟？》《沼泽中的伯爵》已逐项补齐，《未归类的植物》改为条件库存任务。当前98任务分类仍为0未解决低置信度；第四层候选审计见`data/route-atlas/zangarmarsh-global-solver-input-audit.json`。
- [x] 第四层精确优化实验已完成阶段性验证，现降级为对照工具。4A输入审计在58–68开放世界窗口当前得到70个候选、14个硬边界/特殊阻塞、56个可直接求解；剩余阻塞主要是跨区/副本边界与声望条件，不再当作本地数据缺口。为避免错误忽略动态声望，先冻结43个“赞加本地+无声望门槛”核心任务；CP-SAT见`lib/route_atlas_cpsat.py`，SCIP/MIP交叉验证见`lib/route_atlas_mip.py`，热启动见`lib/route_atlas_initial_solution.py`。8任务统一秒级回归仍由Dijkstra证明`1293.274s PROVEN_OPTIMAL`；CP-SAT/SCIP均可复现该incumbent但当前下界较松。43任务checkpoint脚本`solve_zangarmarsh_global_core43.py`会跨短跑保留incumbent与best lower bound，最新`data/route-atlas/zangarmarsh-global-core43-checkpoint.json`为`BEST_FOUND_WITH_GAP`：incumbent `7765.337s`、best bound `4277.903s`、gap `44.91%`。下一步不盲目延长搜索，而是做结构化精确分解/更强lower bound；之后再单独加入孢子人/塞纳里奥等动态声望状态和杀怪声望收益，最后才合并跨区边界。

- [ ] Route Atlas 第一版实跑地图的数据与自动裁剪已经生成。统一五开耗时口径保持：普通击杀15秒/怪；掉落任务按五号总需求÷掉率×15秒；多刷新物等待=`刷新时间×(轮数-1)`；动态声望/地图外前置按Questie现场可用处理；Item-start仅作机会任务。当前页面直接显示166个内部动作合并后的125个真实停靠点，并按圈内不重复坐标规则切成17圈；地图只画真实坐标间的黄色方向箭头，不显示宏观编号节点、步骤数字或路线圆点。页面默认自动裁剪放大第1圈，支持17个数字圈、“下一圈 →”、“适应本圈”和“全图”。2026-08-14用户确认大部分位置可看清，箭头已按8px最小点位比例从约21px缩到8px基准。随后确认真正问题不在点位算法，而在动作排序；旧17圈/166动作不再作为最终展示真源。新的正式方法已冻结到`docs/analysis/2026-08-14-route-atlas-cluster-incremental-insertion-method.md`：先按完全相同任务怪建立目标簇，再构建前置网，再人工拆真实空间实例，最后逐簇把A/C/T动作增量插入已有稳定路线。不同目标簇默认无先后，只有显式前置才建立跨簇顺序；目标簇编号和空间骨架都不是强制顺序；每加入一个新簇只允许局部重排，已验收路线不得反复全局洗牌。广域背景任务最后再插入，旧求解器只保留为对照/异常检测/局部成本参考。下一步先从第一个主体空间块构造R1，验收后再插入第二簇。

## 死亡骑士（暂缓）

- [ ] 当前不启动死亡骑士55—80母版；等首组圣骑士达到80级后再决定DK的创建、升级和打金路线。

## 视频路线事实拆解

- [ ] 只按`docs/video-extraction/CURRENT.md`指定的下一集继续；每集完成后同步项目CURRENT、机器`progress.json`与检查点，然后停止。
- [ ] 依次完成剩余集数；逐集阶段只提取事实，不做联盟到部落映射或路线优劣判断。
- [ ] 第53集完成后按`docs/video-extraction/POST-EXTRACTION-PLAN.md`整合事件、审计跨集缺口并映射任务块。

## 后续资料

- [ ] 用户提供的诺森德日常任务资料仍只存于`docs/analysis/2026-08-08-northrend-daily-quests-unverified-source.md`；圣骑士推进到对应等级后逐项核验，不直接视为事实。

## 代码与数据

- [ ] 只有解析、候选生成或HTML输出发生修改时才运行相应测试；纯攻略修订以任务ID、链接、状态和玩家视角复走为验收。
