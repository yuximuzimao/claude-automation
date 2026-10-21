# 2026-10-21 — Atomic Claim 批量清洗、Question Cluster 收敛与 no-claim 退出机制归档

## 阶段范围

本阶段承接 `2026-10-19-engineered-history-silver-cleaning.md`，不再扩大历史采集范围，而是集中处理 36 日完整历史基线上的语义清洗债：

1. 把生产批次从 B6 连续推进至 **B37**；
2. 逐批回到 canonical 原文人工核验来源，避免旧 Topic Card 标题/摘要直接升级为知识；
3. 以 Atomic Claim → existing-cluster assignment → bootstrap → recall audit 的固定链路持续收敛 Question Cluster；
4. 为“原文真实但没有可复用命题”的来源卡增加正式 **no-claim reviewed** 退出机制，避免为了满足 schema 被迫制造知识；
5. 持续维护黑话词典、动态不确定性和困难负例，不以候选数量下降替代语义正确性。

本归档只保存阶段结论与下一恢复点，不替代 `docs/CURRENT.md`、`tasks/todo.md`、`docs/rules/` 或 runtime 文件真值。

## 生产清洗推进

10/19 归档时 reviewed registry 为：

- 167 张来源卡；
- 206 条 reviewed claims；
- 127 个 reviewed questions；
- 48 个多命题问题；
- 104 条 boundary negative links；
- 9 个数据批次。

本阶段把 B7–B37 全部闭环后，正式推进到：

- **879 张来源卡**；
- **965 条 reviewed atomic claims**；
- **466 个 Question Clusters**；
- **191 个多命题问题**；
- **416 条 boundary negative links**；
- **40 个数据批次**。

新增量相对 10/19 归档为：

- +712 张 reviewed 来源卡；
- +759 条 claims；
- +339 个 reviewed questions；
- +143 个多命题问题；
- +312 条 boundary negatives；
- +31 个数据批次。

这轮已明显进入“复用已有问题簇高于新增问题簇”的收敛阶段。后段 B34–B37 的 existing-cluster 复用率多次达到约 74%–87%，说明 Question Cluster 的职责边界已开始稳定。

## canonical 优先：旧 Topic Card 永远只是检索提示

本阶段再次验证：

- Topic Card 标题/摘要可以帮助找到原文，但不能作为事实来源；
- 每张进入 Atomic Claim 的卡都重新核 canonical；
- 旧标题中过推断的数字、因果、机制、来源会直接收缩或删除；
- 同一 Topic Card 混有两个职责时必须拆 claim；
- 没有答案、只有提问、纯群管理、重复广告、无复用价值个人轶事等，不再为了过质量门禁硬造 claim。

实际纠偏包括但不限于：

- TOC 老一“灭两次”还原为重复消息，不再把重复文本误当第二次灭团；
- “34 万”还原为单次竞价截图，不再写成整车收入；
- 伟大 2500G 相关内容收缩为阶段价格/寿命预测，不扩成“所有装备削弱后都会跌”；
- 289/404 命中讨论不再附会为 AI 来源；
- 无限服、G团、WCL、多开、处罚截图等政策类消息始终保留“玩家说法 / 外部转述 / 未核验”身份；
- P6 / 奥杜尔首日预测在出现真实首日样本后优先由实测更新，而不是让旧预测继续占据事实位置。

## verified source anchor

人工 verified source anchor 从 10/19 的 **196** 条推进到 **909** 条。

主要做法：

1. 对 automatic high anchor 仍进行人工 canonical solidification；
2. 对 saved time range 错位的卡重新定位真实行号；
3. 一个 claim 可以使用多个精确 source segment，但必须都指向 canonical；
4. 不因为标题相近、时间窗相近或 lexical score 高就把证据强行挂到卡片上。

当前候选锚点统计仍为：

- high：1575；
- medium：5；
- none：698。

其中 698 个 none 是现存 direct-source retrieval 主体，仍属于明确来源债，不能靠猜测补齐。

## no-claim reviewed 正式退出机制

本阶段发现一个结构问题：Atomic Claim 质量门禁要求每个 reviewed card 至少有一条 claim，这会迫使以下卡片制造伪知识：

- 原文只有问题、没有答案；
- 同一语义已由另一张来源卡完整承担；
- 群管理/广告清理；
- 与游戏知识无关的现实闲聊；
- 只有潜在违规利用方法而没有值得保留的高层机制；
- 语义更适合进入黑话词典而不是 Atomic Claim。

因此 `src/analysis/atomic_claim_queue.py` 新增：

- `--no-claim-reviewed` 输入；
- 新 lane：`atomic_claim_no_claim_reviewed`；
- no-claim reviewed 卡与 full / normalized / reviewed claims 一样，不再重新进入 active queue；
- queue 输出记录 no-claim 文件 hash；
- 对应新增单元测试。

当前已有 **31 张**来源卡进入 no-claim reviewed。

这个机制的目标不是“丢信息”，而是明确区分：

`原文存在` ≠ `必须形成一条可复用知识`

## Question Cluster 收敛规则继续有效

现役合并边界仍然是：

`canonical_question`

而不是：

- 同实体；
- 同装备；
- 同职业；
- 标题相似；
- 高 lexical score；
- 同一天聊天。

每批固定执行：

`canonical → claim quality → existing-cluster assignment → new-question bootstrap → recall audit → reviewed registry`

召回继续只是候选生成。高分 pair 仍可能是困难负例，例如：

- 都由“奥杜尔流程很长”导致，但“2小时交易窗口”与“2–3小时让老板不愿参与”必须分开；
- 同属装备经济，但区服金价、普通材料价格和单件装备成交价不应合并；
- 同属观星，但开门前置、修星岗位经济、775/天地同寿、难度方差属于不同职责。

因此本阶段继续扩充 boundary negative links，未启用自动 semantic merge。

## 黑话词典

黑话词典从 29 条增至 **30 条**。

新增：

### 烧心 / 不烧心

在本群多数游戏/网络语境中表示：

- 烧心：体验糟糕、质量差、玩起来让人难受/膈应；
- 不烧心：体验较省心、没那么折磨。

同时明确保留：字面医学语境里的“烧心”仍是另一含义，必须依上下文区分。

这类语义直接维护在黑话词典，不再额外制造 Atomic Claim。

## 现役队列

B37 正式纳入 reviewed manifest 后：

- candidate total：2278；
- already full Silver：613；
- already normalized：44；
- atomic claim reviewed：841；
- atomic claim no-claim reviewed：31；
- ready-from-high-anchor：**227**；
- needs-anchor-review：**0**；
- direct-source-retrieval：**522**；
- active work items：**749**。

相较本阶段中前期 active 1492 左右的规模，已处理约一半现役语义债。

当前最合理的推进顺序：

1. 继续清完剩余 227 个 ready-from-high-anchor；
2. 然后进入 522 个 direct-source-retrieval；
3. direct retrieval 仍必须先找 canonical locator，再生产 claim；
4. 不允许把 none-anchor 卡直接按旧摘要晋升。

## Silver 与用户可见结果的边界

本阶段主要推进的是 reviewed Atomic Claim / Question Cluster 基础层，没有为了“尽快看到页面”跳过清洗。

因此：

- 正式 Silver 数量仍维持既有 105 个知识单元 / 624 张完整吸收来源卡；
- 用户已确认资料库知识仍不因自动清洗扩张；
- Question Cluster 是后续生成更可靠 Silver / 页面卡片的语义基础，不直接等于用户最终页面；
- 等 high-anchor 与 direct-source 债进一步收敛后，再集中重建最终页面更适合用户做反推式质检。

## 工程状态

本阶段 Git tracked 的核心工程改动只有：

- `src/analysis/atomic_claim_queue.py`：新增 no-claim reviewed lane；
- `tests/test_atomic_claim_queue.py`：增加 no-claim 不重返队列的回归测试；
- `docs/CURRENT.md`：同步最新正式状态；
- `tasks/todo.md`：同步唯一下一待办；
- 本归档及 `docs/HANDOFF.md` 的 NEAT 恢复入口。

所有：

- canonical 原文；
- source anchor overlay；
- B7–B37 runtime claims；
- cluster assignment；
- gold / recall audit；
- no-claim reviewed registry；
- 黑话 runtime 词典；
- 页面运行时结果

继续保留在 `runtime/`，整个目录 Git ignored，不复制真实群聊原文或昵称进 Git。

## 归档前验证

### 全量回归

运行：

`python3 -m unittest discover -s tests -p 'test_*.py' -q`

结果：

- **172 tests**；
- **OK**。

测试过程中 stderr 仍会打印一段由 CLI 参数校验用例触发的 argparse 诊断文本，但最终 unittest 结果为 172/172 通过。

### 分析质量门禁

运行：

`python3 -m src.analysis.quality --report runtime/analysis-work/data-quality-baseline-neat-2026-10-21.json`

结果：

- **0 errors**；
- **47 warnings**；
- warning 组成：
  - 45 × `legacy_implicit_full`；
  - 1 × `external_source_no_locator`；
  - 1 × `source_anchors_need_backfill`。

当前仍是“结构/引用门禁通过，但历史来源债未清零”，不能描述为所有旧数据都已完全回填。

### 页面重建

运行：

`python3 runtime/analysis-work/build-page-v2.py`

关键统计：

- raw topic cards：3442；
- blackwords：30；
- source links：high 1996 / medium 21 / none 1426；
- Silver：105；
- Silver full-source components：624；
- dossier components：45；
- normalized components：669；
- effective queue：1724；
- knowledge：9。

页面正常输出到 runtime，不进入 Git。

## 下一阶段恢复点

新会话不要重新复盘本轮聊天上下文，直接按文件真值恢复：

1. 读 `tasks/todo.md`、`docs/CURRENT.md`；
2. 重建一次 `atomic-claim-work-queue-v1.json` 确认现役数字；
3. 从 **H27 / `T-20261012-053`** 开始下一批 high-anchor 清洗；
4. 继续每批固定链路：
   `canonical → claim quality → existing-cluster assignment → bootstrap → recall audit → reviewed registry`；
5. high-anchor 清完后进入 522 个 direct-source-retrieval；
6. no-claim 卡继续显式退出，不为满足 schema 制造知识；
7. 黑话优先进入词典，不重复形成 gameplay claim；
8. 政策/测试服/价格/预测始终保留时点和证据性质；
9. similarity 继续只负责召回，禁止自动合并；
10. 等基础层更完整后，再重建最终页面，由用户从页面结果反推清洗问题。

## NEAT 审计

- `docs/CURRENT.md` 已同步到 B37 / 909 anchors / 965 claims / 466 questions；
- `tasks/todo.md` 已同步现役 227 ready / 522 direct source / active 749；
- `docs/HANDOFF.md` 恢复入口更新到本归档；
- `docs/rules/analysis.md` 继续是分析业务规则唯一 owner；
- `docs/ANALYSIS-DATA-QUALITY-SOP.md` 继续是工程质量流程说明；
- runtime 私密数据继续 Git ignored；
- 历史 archive 只保存已完成阶段与恢复点，不反向成为现役执行入口。
