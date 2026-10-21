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
- 归档前已运行 `python3 -m unittest discover -s tests -p 'test_*.py' -q`，当前确定性回归 **172 tests OK**；其中包含采集 Swift 纯测试、normalize/store/runner，以及分析质量/来源/Atomic Claim/Question Cluster 回归。

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
- 黑话基础规则已写入 `docs/rules/analysis.md`；当前 runtime 页面黑话页已能展示 **29 个词条**。
- 完整历史第一轮语义基线归档见 `docs/archive/neat/2026-10-15-complete-history-semantic-analysis.md`。

## 当前阅读 / 资料库原型状态

当前私密原型仍输出到：`runtime/reports/page-v2-prototype-light.html`；文件名暂未迁移，页面内容已经切换到新信息模型。

当前已验证结构：

- 第一轮 topic card = 候选索引，不是最终展示清单；
- 页面顶层只保留 **新信息 / 资料库 / 无限服 / 黑话** 四个入口；旧“主信息 / 待核验 / 合集 / 本期总览 / 长期追踪 / 攻略知识 / 项目相关”不再作为默认 UI；
- “职业”与“副本攻略 / 任务与练级 / 装备机制 / 专业技能 / 经济打金 / 插件故障 / 防诈骗”等是同级专题，不做职业 × 专题交叉筛选；本次无内容的专题自动不显示；
- 新信息是首次阅读队列：只要具有明确、游戏特异的信息增量且系统不能确认用户已经掌握，就优先让用户第一次看到；封测/待版本核验不等于无价值；
- 用户终审只有 **没用 / 存资料库**。两者都视为已阅，相同语义以后不重复占队列；只有可信度升降或更多人重复同一结论时只在后台静默更新；
- 用户明确判定有用的知识进入资料库；资料库以部分关键词搜索为第一使用方式，并保留专题层级；
- 展示前需要做基础身份补齐。当前已用 `T-20260925-020` 验证：把“弗约恩任务”补成“风暴峭壁 · 《弥补关系》#12915”，并带任务目标，再显示群聊新增的宠物式控制栏/先护盾控制技巧；
- 2026-10-18 已确认仅按“同一天 + 同话题”收容器仍不够：正式分析窗口必须先跨日做 Silver 层语义清洗，再生成阅读单元；自然日只保留为证据时间，不能成为话题边界；
- Silver 已从4条 pilot 样例进入正式工作集 `runtime/analysis-work/silver-knowledge-v1.json`：当前共 **105 个知识单元 / 624 张完整吸收来源卡**。除原有 NAXX追赶、区服组团差异、坦克学习阶梯、双持冰DK武器链外，已完成惩戒骑首批清洗；冰DK的构筑分流、70→80保留冰天赋顶T升级路线、副本难度边界、命中/精准阈值、饰品预算层级、够用型配装和入门循环；DKT 的起手仇恨/异常诊断/岗位压力；BDK 的属性阈值、饰品取舍、强度与就业分离；NAXX 稳定工资与时间成本、新号 P4→NAXX→P5 低成本成型路线；猎人专业目标分层、敏捷/攻强条件树和近战猎传闻动态信号；冰法低操作下限/成长上限、急速饱和与爆发错峰、旧套2+2与4件套取舍；整合插件省事/性能权衡、BIS工具可信边界、团本提示链失效、插件安装更新诊断与下载来源安全；首号自练/后续小号直升、任务+随机本混合升级、快飞ROI、G团工资资格和老板位→工资位的资本转换策略；以及双采顺路收益/专门搬砖分流、直升角色知识债、公会团/野团组织取舍、包团/拍团价格风险结构；此后继续完成直升礼包权益/直升装工资位边界、80后任务启动资金、账号控制权风险、专业冲满ROI、奥杜尔时长与观星职责/削弱、美酒节追赶与限时窗口、G团团规透明度/岗位补贴/收入方差/排骨ROI、随机本混合升级与AA固定本路线，以及ZG低成本追赶件与跳Boss路线经济；随后继续收敛插件整合包性能、团本视觉降噪、一键输出辅助边界，以及坦克学习/岗位压力、坦克稀缺与信任门槛、不同坦克专精职责比较。实例与重复说法均降为 evidence，不再重复占阅读队列；
- 分析窗口与阅读批次已经分离：历史半月数据可以整体去重/合并，页面再按每批最多40个阅读单元分页；分页不参与语义切分；
- 2026-10-18 第二批清洗进一步校准 Silver 方法：`evidence_refs` 区分 `coverage=full|partial`，避免混合卡只吸收一半却整卡消失；实体只负责召回，最终按 `question` 决定合并边界；已阅核心与新增条件/例外分离，不能用新 queue 覆盖旧 knowledge；新的 queue 单元默认必须至少含一条当前首次阅读候选，禁止因为“与当前项目相关”而擅自复活旧 hidden/collection-only 内容。页面构建同时生成私密 `runtime/analysis-work/silver-candidates-v1.json`，作为后续批量清洗的明确候选工作集；
- “可补全”只标记那些需要额外联网/资料比对才能补足关键事实的候选；用户可在看完本批后统一要求补全；
- 原文右侧抽屉继续保留，回链仍以卡片自身时间范围/来源范围为主锚点，不用全日关键词搜索冒充证据；
- 黑话继续独立维护语境化词典。
- 2026-10-18 开始工程化分析质量改造：已新增 `docs/ANALYSIS-DATA-QUALITY-SOP.md`、`src/analysis/quality.py`、来源回填/审核/应用、`atomic_claim_queue.py`、`cluster_proposals.py` 及回归测试。当前 **2278 张首次阅读候选**均纳入数据质量快照；当前 105 条 Silver、原文、已阅和 9 条资料库知识均继续沿用同一工程化质量门禁；本轮新增清洗未改动已阅结果或资料库知识。来源债仍为 **698 张**；当前候选锚点为 **1575 high / 5 medium / 698 none**，其中已 full 但仍缺直达锚点 **160 张**。人工语义复核已形成 **909 条 verified source anchor**，并反向发现 **15 张旧 Topic Card 语义抽取错误**；这些卡进入 quarantine，不能参与自动聚类或评测真值。45 条旧引用仍依赖隐式 full，1 条外部引用缺正式 locator。词面召回的 known-positive recall@5 仍为 75.6%、@10 为 85.6%，top5 已标注一致率 65.9%，只作为召回基线。Atomic claim 已进入稳定生产批次：15 张纠错卡→22 claims、12 张 pilot→18 claims、独立 20 张 holdout→31 claims，生产批次已持续推进至 B37。全部 claim 自带 canonical `source_refs`。reviewed atomic registry 现为 **879 张来源卡 / 965 条 reviewed claims / 40 个数据批次**。召回器采用 `lexical_topk + same_source_card + same_entity` 多路 union，所有路线只负责召回；calibration、frozen holdout 与 B1–B6 的人工 gold 正关系均能进入候选池。高分线仍不是合并概率：独立 holdout 固定 0.075 线 precision 65.2% / recall 88.2%，B3/B5 等批次也再次出现高分误报。经过人工 existing-cluster assignment / new-question bootstrap，Question Cluster Registry v45 已有 **965 reviewed claims / 466 reviewed questions / 191 个多命题问题 / 416 条 boundary negative links**。2026-10-21 已按最新审核状态刷新 atomic-claim work queue：**227 ready-from-high-anchor / 0 needs-anchor-review / 522 direct-source-retrieval，active 749**；其余为613 already_full_silver、44 already_normalized、841 atomic_claim_reviewed、31 atomic_claim_no_claim_reviewed。该队列是待处理路由元数据，不代表语义审核完成。15张旧语义错误 Topic Card 继续 quarantine，其正确原子命题已进入 reviewed registry。

无限服当前单独启用动态专题档案：`runtime/analysis-work/infinite-dossier-v1.json`。2026-10-18 已从长段自然语言摘要升级到 schema v2：仍按练级与玩家发展、经济与打金、专业与资源、规则与风险、职业玩法变化、服务器生态六个维度，但每个维度保存 `观察字段 / 当前状态 / 适用范围 / 依据 / 证据ID`，页面以结构表展示；重复观察只静默增加支持度，AI综合判断不得覆盖来源状态。

当前 runtime 原型统计：

- raw topic cards：**3442**；
- longitudinal aggregate：**1**；
- supplemental card：**1**；
- blackwords：**30**；
- source links：high **1996** / medium **21** / none **1426**；
- Silver 清洗前的首次阅读候选：**2278 条事实切片**；它们不是最终阅读单元；
- 当前正式 Silver 工作集共 **105 个知识单元 / 624 张完整吸收来源卡**；页面按 Silver 组件去重后的有效待看为 **1724**，原始 `v3_queue` 为 **2278**。当前候选索引为 **613 张 full / 1644 张 unabsorbed / 21 张 partial**；叠加无限服 dossier 等已规范化组件后，normalized 状态为 **657 full / 1600 unabsorbed / 21 partial**。`partial` 混合卡仅部分语义已归属 Silver，仍保留在首次阅读候选中；
- 无限服最近构建时有效首次阅读候选：**125 条**，后续应先吸收到结构化动态信号后再决定哪些需要单独打扰用户；
- 当前由历史用户确认结果种出的资料库知识：**9 条**，其中双持冰DK路线已用标准化阶段表替换旧长段摘要。

这些数字只是当前完整历史回看原型，不是未来每日分析的正常批量，也不是永久业务常量。

当前 Atomic Claim 批量清洗、Question Cluster 收敛与 no-claim 退出机制阶段归档见 `docs/archive/neat/2026-10-21-atomic-claim-question-cluster-cleaning.md`；此前 36 日历史补齐与分析质量工程化阶段见 `docs/archive/neat/2026-10-19-engineered-history-silver-cleaning.md`。现行信息模型只以 `docs/rules/analysis.md` 为准。

## 当前下一步

1. 从已刷新的 `atomic-claim-work-queue-v1.json` 继续按 Question Cluster Registry 增量流水线处理；现役待处理 **227 ready-from-high-anchor / 0 needs-anchor-review / 522 direct-source-retrieval，active 749**。每批固定走 canonical→claim quality→existing-cluster assignment→new-question bootstrap→多路 recall audit→reviewed registry；旧 Topic Card 永远只作检索提示，similarity 不自动合并。
2. 在批量清洗过程中同步做“对象身份 / 基础上下文补齐”，优先覆盖任务、Boss、职业阈值和装备四类；同义实例只挂证据，不重复生成知识。
3. 继续验证每批最多40个阅读单元的历史补课体验；阅读分页只控制负载，不得影响跨日语义合并。
4. 确定正式的已阅语义指纹、资料库条目与无限服动态信号的数据结构；当前浏览器 localStorage 只承担原型交互，不视作长期真值。
5. Silver层稳定后，再实现唯一正式分析结果、runner 和每日“采集 → 分析 → 首次阅读队列”流程。

下一步严格以 `tasks/todo.md` 为准。
