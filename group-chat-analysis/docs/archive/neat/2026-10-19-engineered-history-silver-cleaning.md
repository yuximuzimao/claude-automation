# 2026-10-19 — 36日历史补齐、分析质量工程化与 Silver 批量清洗归档

## 阶段范围

本阶段承接 `2026-10-18-first-read-to-silver-normalized-knowledge.md`，完成三件此前尚未闭环的工作：

1. 把 2026-10-13 → 2026-10-18 六个自然日的聊天补采、全文语义阅读与 Topic Card promotion 纳入正式历史基线；
2. 把“AI先理解聊天再做清洗”从人工批次经验提升为可验证、可追溯的数据质量流水线；
3. 在新门禁下继续批量 Silver 清洗，把现役 Silver 从 48 个推进到 105 个，同时严格保留原文证据、partial 语义和动态不确定性。

本归档保存阶段结论与恢复点，不替代 `docs/CURRENT.md`、`tasks/todo.md` 或 `docs/rules/`。

## 36日完整历史基线

“魔兽世界无限+时光服玩家群”当前正式历史窗口为：

- 2026-09-13 → 2026-10-18；
- 36/36 个自然日；
- 12973 raw pages；
- 85655 canonical messages。

2026-10-13 → 2026-10-18 新增六日日包均已完成：

- 10/13 page 0–296；
- 10/14 page 0–335；
- 10/15 page 0–296；
- 10/16 page 0–646；
- 10/17 page 0–237；
- 10/18 page 0–396。

六日均确认 `completed / pending_capture=null / capture_complete=true`，总新增 14682 canonical / 2212 raw pages。

六日又完成逐日全文语义复核并 promotion，共新增 318 张 Topic Card：

- 10/13：70；
- 10/14：54；
- 10/15：49；
- 10/16：55；
- 10/17：50；
- 10/18：40。

当前正式 Topic Card 索引总数为 3442，36天均有正式 Topic candidate，不存在缺失日期。

## 采集侧：90° Vision 帧方向异常已纳入正式防护

10/13 补采过程中出现一个真实环境边界：ScreenCaptureKit 偶发把同一 QQ 历史窗口帧以 90° 方向交给 Vision，原实现只支持 `.up/.down`，导致工具栏定位失败。

现役处理改为：

1. 仍优先使用正常 `.up`；
2. 只有正常路径无法通过工具栏门禁时，才对**同一帧**尝试 `.down / .right / .left`；
3. bbox 映射回显示坐标；
4. 多个方向都能识别时，以同一工具栏水平带中的已知控件证据数择优；
5. 继续要求原有工具栏/正文安全门禁，不降低安全条件，也不因为重试方向再次滚动页面。

因此这是 OCR 方向兼容修复，不是放宽采集安全规则。

## 分析方法：AI语义标准化不替代原文

本阶段进一步确认一个核心原则：

聊天记录中每个人表达方式不同，AI 先把原始话语理解成统一语义表达，再做跨日去重、实体对齐和知识结构化，是当前场景的正确方向；但 AI 产出的 Topic Card / Atomic Claim / Silver 都只是变换层，**原文证据必须始终可以回到 canonical source**。

因此现役分析链路为：

`canonical原文 → Topic candidate → Atomic Claim / Question Cluster → Silver规范化知识 → 页面/资料库/动态专题`

而不是：

`聊天 → AI总结 → 丢弃原文`

不同领域可以复用同一工程框架，但具体清洗动作必须受领域语义约束。例如魔兽聊天需要识别：

- 职业/专精与版本阶段；
- 团本、Boss、难度和机制；
- 装备、套装、属性阈值；
- 玩家口述、实测、传闻、未来阶段预测；
- G团团规、市场成交、极端价格样本；
- RNG个案与机制结论的边界；
- 动态规则与静态知识的差异。

所以“流程相同”不代表“清洗动作相同”。领域规则决定 claim 如何拆、question 如何定边界、哪些数字必须带条件、哪些说法只能保留为动态/未核验信号。

## 工程化质量体系

新增 `docs/ANALYSIS-DATA-QUALITY-SOP.md`，并把分析质量体系落实到代码，而不是只保留为文档理念。

现役层次：

- Bronze / canonical：不可破坏的原始事实层；
- Topic candidate：宽召回语义索引；
- Atomic Claim：单一可验证命题；
- Cluster proposal：召回/聚类建议，永远不自动成为 Silver；
- Silver：按 question 边界合并后的规范化知识；
- Gold / 页面投影：展示结果，不等同于用户已确认资料库知识。

质量维度包括：

- completeness；
- consistency；
- lineage；
- semantic accuracy / completeness；
- timeliness；
- reproducibility / stability。

核心工程原则：

- 分类只用于召回/导航，不作为硬清洗分区；
- 最终合并边界是 `canonical_question`，不是实体相同、标题相似或词面分数高；
- 相似度只负责召回候选，不能自动判定同义；
- wrong merge 的代价高于 missed merge；
- 原卡是混合语义时使用 `coverage=partial`，只吸收对应命题，不允许整卡消失；
- `full` 必须表示整张 Topic Card 的全部有价值语义都已被 Silver 覆盖；
- 同一来源被多个 Silver 使用时，只有一个问题可在确有完整覆盖时标 full；其余应 partial；
- 动态信号、玩家预测、传闻、商业来源和外部证据必须保留来源性质，不清洗成无条件事实；
- 已发现语义失真的 Topic Card 进入 quarantine，不能继续作为自动聚类真值。

## 来源真实性与历史债

工程化审计首次把“原文对不上”变成可量化问题。

当前 2278 张首次阅读候选的来源锚点：

- high：1552；
- medium：28；
- none：698。

其中无可靠锚点的 698 张主要来自旧 Topic Card 没有保存可直接定位的 time range，而不是“698条事实一定是错的”。

已人工复核形成 196 条 verified source anchor，并反向发现 15 张旧 Topic Card 存在语义抽取错误；这些卡已进入 semantic quarantine，其正确命题从 canonical 原文重建。

仍存在：

- 160 张已经 full 但没有 high/medium 直达原文锚点；
- 45 条早期 Silver 引用依赖 legacy implicit full；
- 1 条外部证据没有正式 locator。

这些属于明确的数据质量债，不能通过猜 URL、关键词近似搜索或批量改 full 来“消红”。

## Atomic Claim / Question Cluster 验证

Atomic Claim 已形成稳定生产批次：

- 15 张纠错卡 → 22 claims；
- 12 张 pilot → 18 claims；
- 独立 20 张 holdout → 31 claims；
- 生产 B1–B6 共 120 张来源卡；
- reviewed registry：167 张来源卡 / 206 claims / 9 个数据批次。

Question Cluster Registry 当前：

- 206 reviewed claims；
- 127 reviewed questions；
- 48 个多命题问题；
- 104 条 boundary negative links。

召回器采用：

`lexical_topk + same_source_card + same_entity`

这些路线只负责召回。独立 holdout 在固定 0.075 线上的结果为：

- precision 65.2%；
- recall 88.2%。

该结果再次证明：高相似分数不能当“合并概率”。B3/B5 等批次仍出现高分误报，因此没有启用自动合并。

旧 Silver 可以作为 calibration，但不是独立 holdout；正式自动合并必须继续扩大独立留出集和困难负例。

## Silver 批量清洗进度

本阶段开始时现役 Silver 为 48 个，本轮推进到：

- **105 个 Silver 知识单元**；
- **624 张完整吸收来源卡**；
- 候选层：613 full / 1644 unabsorbed / 21 partial；
- 加上无限服 dossier 等 normalized components 后：657 full / 1600 unabsorbed / 21 partial；
- 页面有效待看：1724；
- 用户已确认资料库知识仍为 9 条，没有因自动清洗扩大。

本轮不以“清零 partial”或“减少候选数字”为目标，而是以 question 边界和来源真实性为目标。典型做法：

- 80后任务金、直升礼包、账号控制权、专业ROI、奥杜尔时长等跨日重复被合成独立问题；
- 美酒节 46 张相关候选只先处理可靠 high-anchor 部分，未锚定来源继续留在来源债；
- 观星拆成修星岗位、数值削弱 vs 机制、T/N减伤职责等问题，时长样本则回填既有奥杜尔时长单元；
- G团把工资资格、团规披露、岗位补贴、收入方差、排骨ROI拆开，避免一句群聊同时承担多个概念；
- 随机本/练级优先扩旧“任务+随机本混合升级”，只为 AA 固定副本路线新增独立单元；
- BIS工具可信度、准BIS预算化、剩余游玩周期ROI分成三个问题；
- 多个职业域继续按“练级 / 就业 / 团队价值 / 装备 / 操作 / 阶段动态”分离，避免把职业讨论压成单一强弱排序。

已明显收敛的职业/主题包括：

- 战士；
- 盗贼；
- 牧师；
- 术士；
- 猎人；
- 萨满；
- 圣骑士；
- 德鲁伊；
- 法师；
- 专业技能；
- 插件/故障排查；
- 美酒节；
- 观星；
- G团工资与组织规则；
- 随机本/AA练级；
- BIS/预算配装。

特别保留的用户纠错：

- `T-20261012-008`：德鲁伊各形态都可自用树皮；给队友使用是另一条能力边界；
- `T-20261012-054`：ZAM炸弹来不及躲时，鸟德树皮硬吃属于具体Boss应急技巧。

二者已分别进入两个 Silver，不再因同属“树皮”被混为一条。

## 无限服动态专题

无限服继续保持独立 dynamic dossier，不和普通 Silver 完全同构。

当前页面中已有 45 张来源卡被 dossier normalized component 吸收；无限服首次阅读候选约 125 条。

现行原则继续是：

- 动态规则/测试服生态只记录当前状态与变化；
- 重复观察只增强后台支持度；
- 状态或边界真正变化时才产生新的可见更新；
- 商业账号、二手消息、玩家预测不得自动升级为服务器规则真值。

## 验证结果

归档前最终验证：

### 全量 Python/Swift 测试

`python3 -m unittest discover -s tests -p 'test_*.py' -q`

结果：

- **171 tests**
- **OK**

### 页面重建

`python3 runtime/analysis-work/build-page-v2.py`

最终关键统计：

- raw topic cards：3442；
- Silver：105；
- Silver full-source components：624；
- dossier components：45；
- normalized components：669；
- effective queue：1724；
- knowledge：9；
- 36天全部存在正式 topic candidates。

### 分析质量门禁

`python3 -m src.analysis.quality --report runtime/analysis-work/data-quality-baseline-neat-2026-10-19.json`

结果：

- **0 errors**；
- 47 warnings；
- warning 组成：
  - 45 × `legacy_implicit_full`；
  - 1 × `external_source_no_locator`；
  - 1 × `source_anchors_need_backfill`。

当前状态是“结构/引用门禁通过，但仍有明确历史债”，不能描述为“全部数据已具备正式自动发布质量”。

## 下一阶段恢复点

新会话不要再从聊天上下文复盘这轮手工批次，直接以文件真值恢复：

1. 先重新生成/刷新 `atomic-claim-work-queue-v1.json`，因为 Silver 已从上一版 work queue 快照后继续推进；
2. 按现役 Question Cluster Registry 继续批量清洗剩余 high-anchor 数据；
3. 每批继续走：
   `canonical → claim quality → existing-cluster assignment → new-question bootstrap → recall audit → reviewed registry → Silver`；
4. 相似度继续只做召回，禁止自动合并；
5. 无锚点/medium 来源继续单独走 source review / direct retrieval，不因同主题就自动 full；
6. 继续扩独立 holdout 与困难负例，在没有充分验证前不启用自动 semantic merge；
7. 同步逐步偿还 698 source-anchor 债、45 implicit-full 债和 1 external locator 债；
8. Silver 稳定后再冻结唯一正式分析结果结构、已阅语义指纹、资料库持久 schema 和正式分析 runner。

## NEAT 审计

- `docs/CURRENT.md` 已更新到 36日 / 105 Silver / 624 full-source 当前状态；
- `tasks/todo.md` 下一步应先刷新 work queue，再继续 Question Cluster / Silver；
- `docs/HANDOFF.md` 恢复入口更新到本归档；
- `docs/ANALYSIS-DATA-QUALITY-SOP.md` 是工程化质量执行说明；
- `docs/rules/analysis.md` 仍是分析业务规则唯一 owner；
- `docs/rules/capture.md` 仍是采集规则唯一 owner；
- runtime 私密数据继续 Git ignored，不复制群聊原文、真实昵称或运行时报告到 Git；
- 历史 archive 只记录阶段结论，不反向成为现役执行入口。
