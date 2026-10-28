# CURRENT — 群聊分析

这是项目当前现场状态的唯一真值。历史过程不在这里展开；未完成事项只看 `tasks/todo.md`。

## 当前阶段

“魔兽世界无限+时光服玩家群”（`wow-infinite-time`）从用户入群日 **2026-09-13** 到 **2026-10-18 23:59** 的单群文字历史基线与第一轮完整历史语义分析均已完成。

当前正式阶段是：**Silver 语义清洗批量化 → 首次阅读队列 / 资料库 / 无限服动态专题稳定化 → 唯一分析结果结构定型**。第一轮 topic cards 继续只作为候选索引层；现阶段主任务不是继续逐卡筛选，而是把事实切片跨日去重、实体对齐并转换成规范化知识单元。页面目标仍是“尽量不漏掉第一次值得看一眼的游戏特异信息，同时把用户需要亲自做的去重、合并和结构化工作降到最低”。用户最终只做“没用 / 存资料库”两类判断。

第二群暂不补历史；多群搜索/自动切群与无人值守调度继续后移。

## 当前稳定采集能力

- 正式采集入口唯一为 `python3 -m src.app.run_capture`；单日历史使用 `--history-date YYYY-MM-DD --group-key wow-infinite-time`。
- 正式状态机唯一为 `pending intent → capture side effect → raw durable → record_page`；batch-state 现役只接受 schema v4。
- 正文只走 ScreenCaptureKit 精确 QQ 历史窗口；无全屏裁剪 fallback。
- 首次全量/单日历史以连续两次独立 `NO_CHANGE` 确认可取边界；incremental 使用连续 `start_anchor`。
- 滚轮前会再次同步确认 QQ 前台；外部窗口抢焦点时自动恢复 QQ 并从上一 durable 视口重试一次，该次不计 `NO_CHANGE`。滚轮可能已生效而状态不确定时仍硬停。
- 新 `history-date` 日包会先安全关闭同名旧聊天记录窗口，验证当前目标群并重新点击右上角“聊天记录”图标刷新历史快照，再选择日期；已有 durable 页的 incomplete 恢复不重开窗口、不重选日期。
- `pending scroll + raw 缺失` 的 history-date 恢复仍使用自动重锚定；找不到唯一连续锚点或回放不一致就保持 incomplete，不猜。
- Normalize 已恢复 `message_date` 和可确认的绝对 timestamp；单日 finalization 拒绝跨目标日 canonical。
- 相邻页保守去重，错误成本保持 **漏真实消息 > 多保留重复消息**。
- 2026-10-16 已补充一个真实边界：旧页 `top fragment` 被下一页完整消息吸收时，只在“长文本明确包含 + 前序连续多消息 overlap 仍成立”条件下允许该 fragment 不阻断重叠；`fragment_kind` 只作为 normalize 瞬态元数据，不进入 message-record schema。
- 2026-10-19 补采 10/13 时发现 ScreenCaptureKit 偶发把同一窗口帧以 90° 方向交给 Vision，导致现役 `.up/.down` OCR 无法定位工具栏。生产实现现为 `.up` 正常路径失败后才在**同一帧**尝试 `.down/.right/.left`，bbox 映射回显示坐标，并继续要求同一工具栏水平带至少两个已知控件；没有降低安全门槛。Swift 采集回归 5/5 通过，真实故障窗口 current-only 复测恢复正常。
- runtime 全部为私密本地数据并被 `.gitignore` 排除。
- 当前已运行 `python3 -m unittest discover -s tests -p 'test_*.py' -q`，确定性回归 **303 tests OK**；其中包含采集 Swift 纯测试、normalize/store/runner，以及来源、Atomic Claim、Question Cluster、Silver publication、首次阅读投影、语义指纹、已阅状态、资料库迁移与无限服 dossier 路由/幂等回归。

## 已验证历史基线

- 覆盖：**2026-09-13 → 2026-10-18，共 36/36 个自然日**。
- 合计：**12973 raw pages / 85655 canonical**。
- 每日均已检查 `completed / pending_capture=null`、raw page 连续、canonical sequence 连续、`record_id` 唯一、已恢复日期/时间不跨目标日。
- 2026-09-25 → 2026-10-04 的 legacy 日包此前已使用当前 normalizer 从 raw 独立重建并 exact match；其它日包由当前 runner/normalizer 直接生成。
- 前 30 日阶段明细与逐日统计见 `docs/archive/neat/2026-10-13-complete-single-group-history-baseline.md`。
- 2026-10-19 已完成 **2026-10-13 → 2026-10-18** 补采并纳入当前语义基线。六天均逐日确认 `completed / pending_capture=null / capture_complete=true`：10/13 page 0–296、10/14 0–335、10/15 0–296、10/16 0–646、10/17 0–237、10/18 0–396；串行 supervisor 最终于 2026-10-19 04:15:13 输出 `ALL DONE`，当前无残留采集进程。

旧的 `first-full-20261008` 与 `incremental-20261009-001` 继续只作为原运行链/anchor 的历史事实，不充当统一历史分析日包真值。

## 已完成历史语义分析基线

- 已完整按时间顺序阅读 **36 天历史**，未使用关键词预筛代替全文阅读。
- 当前第一轮细粒度语义候选索引为 **3442 张 topic cards**；其中 10/13 → 10/18 新增 **318 张**（70 / 54 / 49 / 55 / 50 / 40），均完成整日全文复核、来源范围门禁并 promotion。
- 旧跨日归一层保留 **20 个合集**，但当前只视为历史/实验结构，不再默认视作最终页面方案。
- 黑话基础规则已写入 `docs/rules/analysis.md`；当前 runtime 页面黑话页已能展示 **30 个词条**。
- 完整历史第一轮语义基线归档见 `docs/archive/neat/2026-10-15-complete-history-semantic-analysis.md`。

## 当前阅读 / 资料库原型状态

静态预览仍可输出到 `runtime/reports/page-v2-prototype-light.html`；正式人工终审使用 `python3 -m src.app.serve_analysis` 提供的本机 review 页面，运行页为 `runtime/reports/review-live/page.html`。只有通过 review server 打开的页面才会把“没用 / 存资料库”写入正式 durable state。

当前已验证结构：

- 第一轮 topic card = 候选索引，不是最终展示清单；
- 页面顶层只保留 **新信息 / 资料库 / 无限服 / 黑话** 四个入口；旧“主信息 / 待核验 / 合集 / 本期总览 / 长期追踪 / 攻略知识 / 项目相关”不再作为默认 UI；
- 每个 Silver 阅读单元显示稳定基线编号（如 `#023`），编号不随筛选、搜索、翻页或用户裁决而重排，便于用户直接按编号反馈；
- 首次阅读页恢复稳定一级专题：职业、副本攻略、任务与练级、装备机制、专业技能、经济 / 打金、插件 / 故障排查、防诈骗经验、PVP / 野外生态、其他；Silver 内部细粒度 `topics` 只映射到这些稳定一级专题，不再原样展开。当前仅“职业→具体职业”“副本攻略→具体副本”提供二级，其他一级专题保持扁平；无限服继续使用独立动态专题档案；
- 新信息是首次阅读队列：只要具有明确、游戏特异的信息增量且系统不能确认用户已经掌握，就优先让用户第一次看到；封测/待版本核验不等于无价值；
- 用户终审只有 **没用 / 存资料库**。两者都视为已阅，相同语义以后不重复占队列；只有可信度升降或更多人重复同一结论时只在后台静默更新；
- 用户明确判定有用的知识进入资料库；资料库以部分关键词搜索为第一使用方式，并保留专题层级；
- 展示前需要做基础身份补齐。当前已用 `T-20260925-020` 验证：把“弗约恩任务”补成“风暴峭壁 · 《弥补关系》#12915”，并带任务目标，再显示群聊新增的宠物式控制栏/先护盾控制技巧；
- 2026-10-18 已确认仅按“同一天 + 同话题”收容器仍不够：正式分析窗口必须先跨日做 Silver 层语义清洗，再生成阅读单元；自然日只保留为证据时间，不能成为话题边界；
- Silver 已从4条 pilot 样例进入正式工作集 `runtime/analysis-work/silver-knowledge-v1.json`：在当时阶段共 **105 个知识单元 / 624 张完整吸收来源卡**。除原有 NAXX追赶、区服组团差异、坦克学习阶梯、双持冰DK武器链外，已完成惩戒骑首批清洗；冰DK的构筑分流、70→80保留冰天赋顶T升级路线、副本难度边界、命中/精准阈值、饰品预算层级、够用型配装和入门循环；DKT 的起手仇恨/异常诊断/岗位压力；BDK 的属性阈值、饰品取舍、强度与就业分离；NAXX 稳定工资与时间成本、新号 P4→NAXX→P5 低成本成型路线；猎人专业目标分层、敏捷/攻强条件树和近战猎传闻动态信号；冰法低操作下限/成长上限、急速饱和与爆发错峰、旧套2+2与4件套取舍；整合插件省事/性能权衡、BIS工具可信边界、团本提示链失效、插件安装更新诊断与下载来源安全；首号自练/后续小号直升、任务+随机本混合升级、快飞ROI、G团工资资格和老板位→工资位的资本转换策略；以及双采顺路收益/专门搬砖分流、直升角色知识债、公会团/野团组织取舍、包团/拍团价格风险结构；此后继续完成直升礼包权益/直升装工资位边界、80后任务启动资金、账号控制权风险、专业冲满ROI、奥杜尔时长与观星职责/削弱、美酒节追赶与限时窗口、G团团规透明度/岗位补贴/收入方差/排骨ROI、随机本混合升级与AA固定本路线，以及ZG低成本追赶件与跳Boss路线经济；随后继续收敛插件整合包性能、团本视觉降噪、一键输出辅助边界，以及坦克学习/岗位压力、坦克稀缺与信任门槛、不同坦克专精职责比较。实例与重复说法均降为 evidence，不再重复占阅读队列；
- 分析窗口与阅读批次已经分离：历史半月数据可以整体去重/合并，页面再按每批最多40个阅读单元分页；分页不参与语义切分；
- 2026-10-18 第二批清洗进一步校准 Silver 方法：`evidence_refs` 区分 `coverage=full|partial`，避免混合卡只吸收一半却整卡消失；实体只负责召回，最终按 `question` 决定合并边界；已阅核心与新增条件/例外分离，不能用新 queue 覆盖旧 knowledge；新的 queue 单元默认必须至少含一条当前首次阅读候选，禁止因为“与当前项目相关”而擅自复活旧 hidden/collection-only 内容。页面构建同时生成私密 `runtime/analysis-work/silver-candidates-v1.json`，作为后续批量清洗的明确候选工作集；
- “可补全”只标记那些需要额外联网/资料比对才能补足关键事实的候选；用户可在看完本批后统一要求补全；
- 原文右侧抽屉继续保留，回链仍以卡片自身时间范围/来源范围为主锚点，不用全日关键词搜索冒充证据；
- 黑话继续独立维护语境化词典。
- 2026-10-18 开始工程化分析质量改造：已新增 `docs/ANALYSIS-DATA-QUALITY-SOP.md`、`src/analysis/quality.py`、来源回填/审核/应用、`atomic_claim_queue.py`、`cluster_proposals.py` 及回归测试。当前 **2278 张首次阅读候选**均纳入数据质量快照；当时 105 条 Silver、原文、已阅和 9 条资料库知识均继续沿用同一工程化质量门禁；本轮新增清洗未改动已阅结果或资料库知识。旧候选层仍有 **698 张**未回填为正式 source anchor（其中已 full 160），45 条旧引用仍依赖隐式 full，1 条外部引用缺正式 locator；这部分现在属于来源/历史格式债，不再构成 Atomic Claim 历史队列阻塞。人工 source-anchor 阶段已形成 **909 条 verified source anchor**，并反向发现 **15 张旧 Topic Card 语义抽取错误**；这些卡继续 quarantine，不能参与自动聚类或评测真值。词面召回的 known-positive recall@5 仍为 75.6%、@10 为 85.6%，top5 已标注一致率 65.9%，只作为召回基线。Atomic Claim 生产批次已从 B1 持续推进至 **B63**；全部正式 claim 自带 canonical `source_refs`。截至 2026-10-22，reviewed atomic registry 为 **1592 张来源卡 / 1689 条 reviewed claims / 66 个数据批次**；历史 Question Cluster Registry **v71** 为 **1689 reviewed claims / 623 reviewed questions / 301 个多命题问题 / 564 条 boundary negative links**；2026-10-24 已以原内容一次性 bootstrap 为稳定现役 `question-cluster-registry-current.json`，现役 assignment / Silver routing / 页面 / release 均不再依赖 v71/v14 等历史文件名。召回器继续采用 `lexical_topk + same_source_card + same_entity` 多路 union，所有路线只负责召回；B62 再次出现高相似但不同题的“盗贼练级痛苦 vs 为缓解痛苦临时AH买装”，说明高分线仍不能当合并概率。历史 atomic-claim work queue 已完全清空：**active 0**；2278 张候选最终分区为 **613 already_full_silver + 44 already_normalized + 1554 atomic_claim_reviewed + 67 atomic_claim_no_claim_reviewed = 2278**，无残留 ready / anchor-review / direct-source work item。下一阶段不再继续逐卡清历史 Topic Card，而是从 reviewed Question Clusters 转换规范化 Silver 草稿/知识单元。15张旧语义错误 Topic Card 继续 quarantine，其正确原子命题已进入 reviewed registry。 Question Cluster→Silver 分流已工程化并 **623/623 清零**：在 publication 前正式 Silver 保持 **105 条且未被自动改写**；最终为 **140 reuse_existing / 483 new_draft / 0 needs_review / 188 existing-Silver links**，routing queue **active 0**。随后 Silver 草稿收敛也已完成：483个 new_draft 经 consolidation B01–B13 收敛为 **241 provisional groups / 31 exclusions / active 0 / 45 separation boundaries**（116 multi-question + 125 singleton）。这241组又已全部完成 materialization 与人工 authoring：**1183 Atomic Claims / 1135 evidence-card links（1094 full + 41 partial）→ 241/241 authored Silver drafts / authoring active 0**；每条均保留 claim-level canonical lineage，authoring 阶段正式 `silver-knowledge-v1.json` 仍为105条未改写。发布前完整性检查确认 materialized/authored 一一对应、无重复 knowledge_id、无与正式105条ID碰撞、必需 schema/evidence/lineage 均完整；authoring 阶段相关回归测试 **24/24 PASS**。
- 2026-10-23 完成首轮全历史 Silver publication：241/241 authored drafts 的 publication gate 已人工清零，结果为 **232 append_new / 6 update_existing / 3 hold**；3 个 hold 均由更完整上位单元覆盖，不进入正式库。publication candidate 与发布前基线对比 **warning delta=0**，相关回归测试 **29/29 PASS**；正式 `silver-knowledge-v1.json` 先从 **105 → 337** 个知识单元，source window 扩展至 **2026-09-13..2026-10-18**。正式候选索引同步为 **1696 full / 33 partial / 549 unabsorbed**，normalized 为 **1740 full / 33 partial / 505 unabsorbed**。
- 2026-10-23 随后完成首次阅读/资料库收敛：2278 张旧 Topic Card 候选均沿 `Atomic Claim → Question → routing → consolidation → publication` 获得终点，**raw card first-read queue=0**；正式 Silver 为 **337 → 344 = 335 queue + 9 knowledge**。其中 7 条旧 card 级用户确认知识已逐条回读原文并迁移为正式 Silver，资料库不再保留 legacy card 旁路。335 个 queue 是 Silver 层待决策基线，不等于最终页面可见数；无限服 dossier 动态吸收后，当时真正首次阅读为 **323**。
- 已建立正式语义指纹与已阅状态：344 条 Silver 得到 **344 个唯一 semantic fingerprint / 0 exact collision**；`reviewed-semantic-state-v1.json` 当前含 **16 个用户语义状态 = 9 knowledge + 7 discard**。只有明确用户裁决才能进入该状态，系统过滤/错误隔离/合并项不得伪装成“用户已阅”；同语义只增加证据或可信度时不重新打扰，question 或稳定适用边界发生实质变化时才允许重新进入阅读队列。页面 localStorage 继续用 semantic fingerprint 作为即时交互缓存；正式本机 review server 已建立，只监听 `127.0.0.1`，在同源 + CSRF 门禁下把“没用 / 存资料库”写入 `reviewed-semantic-decisions-v1.json` 并重建 `reviewed-semantic-state-v1.json`。用户裁决只作用于正式 queue Silver，不改写 Silver 事实层；静态直接打开页面仍只使用 localStorage。
- 来源与历史格式债已显著收敛：45 条旧 Silver 隐式 coverage 已全部显式化，唯一外部引用已补正式 locator；verified source anchors 当前 **1795**。335/335 个首次阅读 Silver 均至少有一份可靠可点原文。候选层当前 source anchor 为 **2164 high / 4 medium / 110 none**，质量门禁为 **0 error / 1 warning**；剩余 warning 是非阻塞的历史来源长尾。另有 73 个 Silver 仍存在部分辅助 evidence 未定位（446 张唯一辅助卡），但不影响任何首次阅读单元的最小可审计原文。
- 2026-10-24 已建立正式分析发布链：`run_analysis --prepare-work` 冻结 completed batch、`current.md`、canonical batch 与 Question Registry/Silver/已阅/dossier 起始 hash；语义审阅完成后 reviewed receipt 再绑定 work-package hash 和最终分析产物 hash。确定性发布顺序为 **quality gate → staging render → immutable release → 原子 current 指针 → 最后 `mark_analyzed()`**；quality/render 失败不推进 batch，重复运行幂等，指针已切但状态写失败可向前恢复，历史 release 支持完整性校验后回滚。每个 immutable release 还会冻结 work package 与 reviewed receipt 本体，避免以后只剩 hash、原审阅输入丢失。正式页面 owner 已从 Git 忽略的 runtime 原型迁入 `src/analysis/page_builder.py` / `page_renderer.py`。当前真实主 batch-state 仍是旧的 `incremental-20261009-001 / completed`，而历史语义基线已覆盖到 10/18，因此**未**用该旧 batch 冒充历史基线发布或标记 analyzed；正式 runner 等下一次真实新 incremental batch 接管。
- 2026-10-25 当前验证策略改为**冻结采集、先验收清洗成果**：第二群 `wow-infinite-2` 暂不采集，第一个群 `wow-infinite-time` 也不补 2026-10-19 之后消息；当时只使用已经完整验收的 **2026-09-13 → 2026-10-18 共 36/36 天** 历史，以 344 条正式 Silver / 323 条首次阅读作为人工验收起点，判断是否重复、是否过度合并、原文是否支撑、以及最终是否对用户有实际价值。此前为未来增量准备的一次性 checkpoint 已撤销，避免误触发采集。

无限服当前单独启用动态专题档案：`runtime/analysis-work/infinite-dossier-v1.json`。2026-10-18 已从长段自然语言摘要升级到 schema v2：仍按练级与玩家发展、经济与打金、专业与资源、规则与风险、职业玩法变化、服务器生态六个维度，但每个维度保存 `观察字段 / 当前状态 / 适用范围 / 依据 / 证据ID`，页面以结构表展示；重复观察只静默增加支持度，AI综合判断不得覆盖来源状态。

当前 runtime 原型统计：

- raw topic cards：**3442**；
- longitudinal aggregate：**1**；
- supplemental card：**1**；
- blackwords：**30**；
- 页面全量 source links：high **2589** / medium **20** / none **834**；其中正式首次阅读候选层为 **2164 high / 4 medium / 110 none**；
- Silver 清洗前的首次阅读候选：**2278 条事实切片**；它们只是历史候选索引，当前 **0 张 raw Topic Card** 直接进入首次阅读；
- 当前正式 Silver 工作集共 **346 个知识单元 = 337 queue + 9 knowledge**；候选索引现为 **1698 full / 546 unabsorbed / 34 partial**，叠加最新 dossier 等规范化组件后 normalized 为 **1745 full / 502 unabsorbed / 31 partial**。这些 card-level 状态只描述来源覆盖，不再决定用户可见队列；
- 当前正式首次阅读队列：**299 个 Silver 阅读单元**；Silver 层 337 个 queue 中有 **12 个无限服历史基线**已吸收到动态 dossier，不再作为重复新信息展示，用户实际终审又进一步移除了已确认无用的正式 Silver。页面仍按每批最多40个阅读单元分页；
- 无限服旧阶段“约125条候选”已作废。正式 Silver 重建后实际只有 **12 个无限服 queue 单元**需要进入动态档案；当前已全部按 `baseline_absorb` 吸收，dossier 为 **6 个维度 / 38 个动态 signal**（原27 + 新11），并建立 Silver→signal→原文血缘。重复执行 JSON 全等；未来只有 `visible_update`（state/scope/boundary 实质变化）才重新进入新信息。
- 当前资料库知识：**10 条 reviewed knowledge**；已阅语义状态共 **44 条（10 knowledge + 34 discard）**。这些状态包含历史已确认语义与当前人工终审，不应把总数直接当作本轮新增点击数。正式 Silver 本体仍为 9 条 initial knowledge，其余 knowledge 状态来自用户后续终审。

这些数字只是当前完整历史回看原型，不是未来每日分析的正常批量，也不是永久业务常量。

当前 Atomic Claim 批量清洗、Question Cluster 收敛与 no-claim 退出机制阶段归档见 `docs/archive/neat/2026-10-21-atomic-claim-question-cluster-cleaning.md`；此前 36 日历史补齐与分析质量工程化阶段见 `docs/archive/neat/2026-10-19-engineered-history-silver-cleaning.md`。现行信息模型只以 `docs/rules/analysis.md` 为准。

## 当前下一步

1. 历史清洗、正式 Silver/资料库、已阅语义、无限服 dossier、稳定 Question Registry、正式页面 owner、work package、发布/回滚 runner 与本机页面裁决持久化均已完成；当前人工验收基线为 **346 Silver / 299 首次阅读 / 10 reviewed knowledge / 44 reviewed states / 38 dossier signals**。本轮相关回归测试 31/31 PASS，质量门禁 **0 errors / 1 个既有来源长尾 warning**。
2. **继续人工验收现有首次阅读 Silver，暂不恢复新采集。** 用户已经确认三类稳定质量问题：其一，把聊天抽象成泛化方法论但缺少具体对象/数值/机制/动作/门槛；其二，Topic Card 已抓到事实但 Silver 合并或页面展示把事实压没；其三，canonical 原文里本身存在独立有效事实，但 Topic Card / Atomic Claim 在切片阶段就没有抽出来。2026-10-28 已先用 `#009 / #012 / #262 / #340 / #343` 校准第二类，又用 `#058 / #059 / #061 / #079` 确认第三类；现行规则要求具体事实优先、`coverage=full` 不得被误当成“原文无其它事实”的证明，发现 raw-source omission 时必须回 canonical 补回，并按真正决策问题更新或新建 Silver。已被用户 discard 的旧聚合不得复活成新事实容器。
3. 继续观察其余条目是否存在新的稳定无用模式、误分类或展示理解成本；`#114 / #150 / #152 / #171` 当前因仅看描述仍无法判断，明确保留到用户实际阅读后再决定。`#304` 已确认是“雷霆 → 惊雷”的锻造武器升级信息，归入“装备机制”，展示文案已改成直接说明对象。
4. 只有现有清洗成果的价值验收足够稳定后，才恢复真实新 incremental batch 的语义生产增量闭环，并在 daily delta 中继续落实对象身份/基础上下文补齐与“可补全候选”持久状态；不能每次重跑全历史。
5. 剩余来源长尾 **110 none** 与部分辅助 evidence 缺口继续作为非阻塞后台债；在真实新 batch 多次手动 E2E 稳定前不进入无人值守调度。

下一步严格以 `tasks/todo.md` 为准。
