# 2026-10-25 — 正式分析发布链与清洗成果验收基线

## 阶段范围

本阶段承接 2026-10-21 的 Atomic Claim / Question Cluster 清洗，完成从“历史大规模清洗”到“可正式发布、可终审、可持续日增量”的工程收口，并把当前工作重心切换为**先验证清洗结果对用户是否真的有用**。

当前不继续采集新消息：只使用已经完整验收的 `wow-infinite-time` 2026-09-13 → 2026-10-18 共 36/36 个自然日历史。

## 当前正式分析基线

- 历史窗口：2026-09-13 → 2026-10-18。
- Topic Card 候选索引：3442。
- reviewed Atomic Claims：1689。
- reviewed Question Clusters：623。
- 正式 Silver：344。
- 当前首次阅读 Silver：323。
- 初始资料库 Silver：9。
- 无限服专题吸收：12。
- 335/335 初始 queue Silver 均至少有一份可靠原文来源。
- 当前正式页面构建仍能稳定得到 323 条“新信息”与 9 条“资料库”。

## 本阶段完成的工程收口

### 1. 正式分析发布 runner

新增 `src/app/run_analysis.py`，把语义审阅与确定性发布状态机分离。

正式顺序固定为：

`completed batch → analysis work package → semantic review → reviewed receipt → quality gate → staging render → immutable release → atomic current pointer → mark_analyzed()`

关键性质：

- work package 精确冻结 completed batch、`current.md`、canonical batch 以及 Question Registry / Silver / reviewed state / dossier 等起始 hash；
- reviewed receipt 精确绑定 work-package hash 与审阅后的最终分析产物 hash；
- immutable release 同时冻结 work package 和 reviewed receipt 本体；
- quality/render 失败不推进 batch；
- 同一输入重复运行幂等；
- 发布指针已切换、但 batch state 写失败时可向前恢复；
- 历史 release 可做完整性校验后显式回滚；
- 只有发布完成后才允许调用既有 `mark_analyzed()`，没有第二套 batch 状态机。

### 2. 正式页面代码进入 src

旧 runtime 页面原型不再承担正式代码 owner。

正式 owner：

- `src/analysis/page_builder.py`
- `src/analysis/page_renderer.py`

builder 支持 staging 输出，失败不会覆盖当前正式页面。

### 3. 用户终审正式持久化

新增：

- `src/analysis/review_decision_store.py`
- `src/app/serve_analysis.py`

用户在页面点击“没用 / 存资料库”时：

- 只写 reviewed semantic decisions/state；
- 不修改 Silver 事实层；
- 同一决定幂等；
- 改判替换同一 knowledge_id 的正式用户裁决；
- 只有正式 queue Silver 可被终审；
- localhost + CSRF + Origin 门禁阻止非本机/跨域写入。

“存资料库”的 queue 单元在后续页面重建时进入资料库视图；“没用”只退出首次阅读。

### 4. Question Registry 稳定 current owner

历史 `question-cluster-registry-v71.json` 只作为 bootstrap 快照。

现役入口统一为：

`runtime/analysis-work/question-cluster-registry-current.json`

新增 `src/analysis/question_registry_store.py`：

- hash-addressed immutable snapshots；
- 旧 question 不得消失；
- 旧 claim 不得消失或换簇；
- scope/boundary 不得静默收缩；
- canonical question 改名必须有显式 revision history；
- stale previous hash 阻止并发/过期发布。

### 5. 历史补采到未来增量的安全 checkpoint

新增一次性逐群 incremental checkpoint 能力，用于独立 history runtime 比 main anchor 更新的场景。

它不会修改旧 completed batch，只允许在**下一批 incremental 创建时**覆盖指定群的 start_anchor；来源 state/messages hash、completed anchor、canonical tail 任一不一致都会在打开 QQ 前拒绝。

本阶段曾为 `wow-infinite-time` 创建 10/18 尾部 checkpoint 做真实验证，但用户随后明确决定**当前先不继续采集**，因此该 runtime checkpoint 已撤销。能力保留，当前没有待消费 checkpoint。

## 验证

- 全量 Python 回归：**293 tests OK**。
- `python3 -m compileall -q src tests`：通过。
- `git diff --check`：通过。
- 正式质量门禁：0 error，1 个非阻塞历史来源长尾 warning。
- stable Question Registry 与 v71 bootstrap 基线语义相等：623 questions / 1689 claims。
- 正式页面真实构建：344 Silver / 323 first-read / 9 knowledge。
- checkpoint 两群不同起点、来源篡改 QQ 零触碰、一次性失效等均有回归覆盖。

## 用户对当前清洗成果的第一轮判断

当前先不因为“大范围历史合并后的大卡”修改清洗规则。

原因：

1. 这次输入是 36 天的大型历史集合，同一语义吸收几十条证据属于特殊历史清洗形态；
2. 未来日常只处理一两天增量时，同类卡片不会自然膨胀到相同规模；
3. 因此“卡片过宽”暂时不作为需要立刻修复的清洗缺陷，先观察真实日增量再决定。

“结构正确但用户未必关心”的信息也暂不视为清洗错误。

例如趣闻、外观、活动日期等卡片如果事实层和证据层正确，但用户最终选择“没用”，这是**信息价值终审**，正是“没用 / 存资料库”二元终审要解决的问题，不应提前把它误判成数据清洗失败。

因此当前最重要的问题已经从：

> 数据有没有洗对？

切换为：

> 这些已经洗对的结果，对用户到底有没有实际价值？

## 当前工作策略

- 暂停第二群采集；
- 不补第一群 2026-10-19 之后消息；
- 不再扩大历史数据集；
- 先用现有 323 条首次阅读 Silver 做真实终审；
- 重点观察用户实际阅读中的价值判断、展示摩擦、证据可读性与少量真正的语义边界问题；
- 根据真实终审反馈，再决定是否需要调整低价值过滤、合并尺度或页面展示压缩。

## NEAT 结论

- CURRENT 只保留当前状态和下一目标；
- TODO 只保留尚未完成的“现有成果验收 → 再决定日增量/采集”；
- 永久分析规则没有因为本轮主观价值反馈而扩张；
- 旧 HANDOFF 中 B37 / H27 / 105 Silver 等恢复清单已退出现役交接，不再维护第二份状态；
- runtime 分析数据、页面与群聊原文继续私密、gitignored；
- 本归档记录阶段证据，不作为现役执行入口。
