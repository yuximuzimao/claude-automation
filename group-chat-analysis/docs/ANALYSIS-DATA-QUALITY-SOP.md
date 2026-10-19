# 群聊语义数据质量工程 SOP（v1）

> 作用：作为 `docs/rules/analysis.md` 的工程执行补充，不另设分析业务规则 owner。适用于群聊，也可迁移到其他非结构化语料。**本 SOP 不是声称获得 ISO 认证。**

## 0. 依据与边界

- ISO/IEC 25012:2008：以数据适用性为目标设定质量维度与可测指标，不照搬结构化数据的全部指标；https://webstore.iec.ch/en/publication/11246
- ISO 8000-1:2022：质量管理原则与质量改进路径；https://www.iso.org/standard/81745.html
- DAMA-DMBOK（2024 修订）：质量、元数据、治理与责任边界；https://dama.org/dama-dmbok-revision/
- Databricks Medallion：原始保留、逐层质量提升、可从原始重建；https://docs.databricks.com/gcp/en/lakehouse/medallion
- Great Expectations：Expectation / Checkpoint / 验证报告的做法；https://docs.greatexpectations.io/docs/core/define_expectations/
- OpenLineage：Job / Run / Dataset 输入输出和转换血缘的元数据模型；https://openlineage.io/docs/spec/object-model/

**不可误用：**这些是互补参考，不是“一份公认最好且强制逐步执行的唯一 SOP”。本项目以本地轻量实现满足相同控制目标，不需要为了概念一致引入 Spark、数据湖平台、云服务。

## 1. 数据契约与不可变性

- **Bronze**：QQ 屏幕采集的 durable raw、canonical messages。保留原始文本、时间、群、批次和采集上下文；任何后续清洗不回写原始语义。采集侧依旧由 `capture/normalize/store` 各自 owner 管理。
- **Topic candidate**：全窗口宽松提取的候选语义索引。它可能包含多个原子命题，不等同一条知识；不允许凭分类/重复度直接删除。
- **Atomic claim（工作队列已建立，抽取层待批量实现）**：每个独立事实或待检验说法有 claim_id、card_id、statement、entity、canonical_question、scope、evidence_type、time、uncertainty、source_ref、transform_version。一个 card 可拆多个 claim；旧 Topic Card 标题/摘要只允许作为检索提示，不能未经原文核对直接复制。
- **Cluster proposal（待建立）**：全量生成的问句级聚合提案。输出源集合、聚类理由、模型/算法版本和风险分数；聚类结果**不是**已验证的 Silver。
- **Silver**：人工/规则验证后的独立决策问题，附 full/partial 的证据覆盖、条件、反例、相互冲突的数值以及动态状态；历史的 48 个 Silver 是冻结对照集，不自动改写。
- **Gold**：供用户首读/资料库/动态专题使用的视图。Gold 表示展示质量，不代表用户终审“有用”。只有用户明确“存资料库”才能进入长期 KB。

## 2. 全量分析流水线（按 DAG 顺序）

| 阶段 | 全窗口输入 → 产物 | 质量控制 | 失败处理 |
|---|---|---|---|
| 0. Scope & Snapshot | 完成的 canonical/候选，记录输入 hash、窗口、版本 | 消息数/时间边界/群身份、不可变原文 | 阻断；不能生成假完整报告 |
| 1. Profile | 数据分布、缺失、异常、重复、时间跨度、证据质量分布 | 无隐式丢失；必需字段覆盖；异常可见 | 隔离异常并留原因 |
| 2. Parse & Standardize | **全量**实体、时间、版本、原子命题候选 | 规范化前后对照；一条卡可多命题；保留原始说法 | 低置信命题保留待复核 |
| 3. Retrieve & Cluster | 所有命题的高召回候选对 → question-level 簇提案 | 同实体不同问题须分开；同问题不同日期可合并；禁止传递链式误合并 | 不确定簇拆开/待审；不自动吞卡 |
| 4. Resolve & Enrich | 簇提案 → Silver 草稿及来源图 | 区分事实/传闻/AI/样本/反例；保留范围、冲突、价格日期 | 标注 unsupported/unresolved |
| 5. Quality Gate | 全量结构与血缘检查 + 人工标注集评估 | 硬错误为 0；语义误合并有独立抽样指标 | 阻断发布，保留上一成功版本 |
| 6. Publish | 通过校验的 Silver → 首读/资料库/动态档案 | 记录产物 hash、作业版本和关键计数，支持重建 | 回滚到上一版，不覆盖原始 |
| 7. Observe | 每次增量的质量报告、漂移和异常清单 | 关注异常增长、实体新别称、新分歧、准确率退化 | 触发规则修订与回归复测 |

**分类只用于检索和导航，不是先验分桶后强行分桶清洗。** 全量实体召回和问题聚合先于人工按职业阅读；类别交叉的信息可以属于多个专题，但同一决策问题不因此重复发布。

### 2.1 历史来源回填与语义隔离

早期 Topic Card 没有保存 `time_range` 时，必须把“找来源”和“判语义”拆开：检索算法只负责给出 canonical 原文候选；只有逐条语义核对后才能写入 `verified-source-anchors-v1.json`。检索窗口不是最终证据边界，审核可收窄、扩展或组合同日多段精确行号。

三类问题必须分别处理：

- **provenance debt**：卡片可能是对的，但缺可靠原文定位；继续找来源，不修改语义。
- **semantic extraction error**：已找到原文，但旧卡存在错误泛化、去掉不确定性、把提问/推断提升为事实、添加无来源对象/数字/结果等；进入 `semantic-correction-queue-v1.json`，隔离出聚类与评测，必须从 canonical 原文重建。
- **evidence verification issue**：卡片忠实复述了玩家说法，但玩家说法本身仍需版本/官方/外部资料核验；保留为未核验 evidence，不把它误判成抽取错误。

本轮历史债修复暂把词面检索 `score >= 0.0425` 作为“值得人工复核旧卡”的运营下限；这是根据本数据集的留出表现和纠错率选择的临时路由阈值，**不是语义置信概率，更不是行业标准**。更低分长尾默认直接回到 canonical 原文做 Atomic claim 重建，不再继续给可能已经失真的旧 Topic Card 打补丁。

## 3. 可观测指标与门禁

- **完整性**：输入 ID 唯一、数量守恒、必填字段非空、所有有效来源可回链；缺失或孤儿引用必须报告。
- **一致性**：Silver ID 唯一；`coverage` 只能为 `full/partial`；candidate 的 full/partial/unabsorbed 状态必须与引用匹配；同一卡片多个 full 归属属于高风险检查项。
- **可追溯**：每个知识事实可回溯到卡片及 canonical 消息范围；报告记录输入文件 hash、代码版本、运行结果。
- **准确性与语义完整性**：禁止把单样本写成确定规律、把传闻写成已落地机制、把已有 knowledge 降级到 queue、把一张混合卡未经全覆盖就标 full。
- **时间适用性**：价格、团况、版本等必须保留日期和作用范围；阶段变化需复审。
- **稳定性**：同版本同输入多次重跑，产出与计数一致；失败禁止发布部分数据。

自动化质量扫描可验证上述**结构门禁**，但不能证明语义事实准确。语义准确度需要分层抽样、已人工校准的正反配对、跨日期和类别的留出集。建议把自动合并设置成高精确度优先，发布门槛由实际标注集表现确定，**不把一个拍脑袋的固定百分比当成行业标准**。

## 4. 标注评测集与持续改进

1. 从已有 48 个 Silver 生成**正样本**：相同 question、相同条件下的多条 full 证据。另生成困难负样本：同实体/同职业但不同 question、不同适用版本、数字冲突不能直接归一。
2. 对 1705 条剩余候选做**分层抽样**：高重复簇、长尾 singleton、混合卡、跨专题、价格/传闻、已阅交界。**测试集不用于调整规则**，避免虚高成绩。
3. 计算 pairwise precision/recall、错误合并（更高权重）、遗漏合并、孤立遗漏、full 误判、动态→静态误判；记录样例与修复版本。
4. 聚类系统只能写 proposal；经评审的 Silver 才可让 full 卡离开首次阅读，partial 必须保留剩余语义；不可在数据质量不足时直接批量挤掉队列。
5. Atomic claim 层必须做到**claim-level `source_refs`**；只在 Topic Card/item 级挂一段大范围来源不够。每个 statement 都要能独立回到 canonical 文件与行号。
6. Question 聚类采用两阶段召回：固定高分候选先审，complete-review 发现缺口后只能从 Top-K recall pool 定向补审，不能为追 recall 全局降低阈值。pilot 冻结阈值在独立 holdout 上证明 Top-K recall=1.0，而高分线 precision 仅 65.2%，因此 similarity 永远不是合并概率。
7. 初始小簇可使用 all-pairs 显式 review 防止传递误合并；规模扩大后必须固化为 Question Cluster Registry，以 canonical question + inclusion/exclusion boundary 审核新 claim，避免 O(n²) 两两审核。已确认 `different_question` 关系应保留为 cluster boundary / hard negative。
8. 每次变更先对既有已阅/知识、独立事实、反例、部分覆盖和高风险传闻做回归；回归通过才更新正式分析结果。

## 5. 当前实施状态

- 已有：Bronze、宽召回 Topic Card、候选索引、48 个手工校准 Silver、full/partial、展示构建。
- 本次工程化已完成第一轮端到端验证：来源回填形成 `proposal → semantic review → verified overlay`；语义失真卡进入 quarantine；Atomic claim 已有 calibration/pilot/独立 holdout，并聚合成 reviewed registry。第二批 frozen holdout 中固定词面召回 Top-K 找回 17/17 positive pairs；pilot 固定高分线 precision 65.2% / recall 88.2%，经 semantic review + targeted recall completion 后 question cluster holdout pairwise precision/recall 均为 1.0。该 1.0 只证明当前人工审核流程在此 holdout 上闭环，不代表全量自动模型准确率。
- 尚待开发验证：Question Cluster Registry 与增量 cluster assignment、继续批量生成 high-anchor 原子命题、独立扩大后的正反标注集、正式 publish/rollback。
- 在上述步骤完成前，原有 Silver 和资料库继续作为唯一正式可见知识来源，不能把自动相似度簇当作已经清洗干净的数据。

## 6. 运行入口（本项目）

```bash
python3 -m src.analysis.quality --report runtime/analysis-work/data-quality-baseline-v1.json
python3 -m src.analysis.source_anchor_backfill
python3 -m src.analysis.atomic_claim_registry
python3 -m src.analysis.atomic_claim_queue
python3 -m src.analysis.atomic_claim_pair_proposals
python3 -m src.analysis.atomic_claim_cluster_apply
python3 -m src.analysis.cluster_proposals
python3 -m unittest tests.test_analysis_quality tests.test_analysis_cluster_proposals tests.test_source_anchor_apply tests.test_atomic_claim_queue -v
```

质量报告为本地 runtime，不提交 Git；契约、程序和测试可以版本控制。必要的敏感内容不写入日志，只写 ID、状态、计数、文件 hash、问题种类。
