# 2026-11-03 — Silver→QA 正式展示投影与 QA 级审核收口

## 阶段范围

本阶段承接 `2026-11-01-complete-silver-knowledge-candidate-conversion.md`。

此前 348 条 Silver 的事实层和私密 FAQ 候选已完成全量覆盖审计，但用户实际阅读发现：候选正文仍有大量防御性语言、来源说明和重复条件，阅读成本过高。用户明确要求**不重做数据清洗**，只重构展示方式。

本阶段继续冻结新 QQ 采集，不采第二群，也不补第一个群 2026-10-19 之后消息。

## 用户确认的展示规则

最终确认的现役规则：

1. **Silver 不拆，页面 QA 可拆。** Silver 继续作为稳定事实主题与证据容器；展示层可以把一个 Silver 拆成多个能独立搜索、独立改变判断或操作的 QA。
2. **默认只看结论。** 默认层为“问题 + 直接结论 + 单字置信度”；证据、来源、判档理由和具体核验建议默认折叠。
3. **除置信度外默认零标签。** 已由分类、搜索、问题或答案提供的职业、副本、来源等信息不得重复做标签。
4. **置信度属于 QA。**
   - 高：可直接使用；
   - 中：核心可用，重要场景建议核验；
   - 低：仅供参考，执行前应核验。
   置信度不是概率，也不能由“玩家实测/群友建议/人数”机械映射。
5. **缺口不是必填。** 只有缺失信息可能改变结论、适用条件或实际操作时，才记录核验内容；默认正文不展开。
6. **时效性信息不得污染长期资料库。** 首周、首CD、活动窗口、短期行情等使用 `time_bound + time_context`，只能“没用 / 留阶段记录”，不能普通“存资料库”。
7. **QA 可独立裁决。** 同一 Silver 的一个 QA 可以丢弃而不影响其它 QA；既有 Silver 级用户 knowledge/discard 决定继续作为兼容基线，不被展示重构改写。
8. **仅改置信度不重新打扰用户。** QA 语义指纹忽略 confidence；问题、结论、生命周期或时间范围实质变化才使旧 QA 裁决失效。

长期 owner 为 `docs/rules/presentation.md`。

## 实现

新增：

- `src/analysis/knowledge_display_projection.py`
  - 校验 `knowledge-display-projection-v1.json`；
  - 约束 qa_id、confidence、lifecycle、time_context；
  - 生成 QA semantic fingerprint；
  - 启用全覆盖门禁：只要存在展示投影，必须覆盖全部正式 Silver，否则页面构建失败。
- `src/analysis/display_review_decision_store.py`
  - 独立持久化 QA 级 `discard / knowledge / archive`；
  - `time_bound → knowledge` 服务端硬拒绝；
  - durable QA 不接受 archive；
  - 语义指纹变化时旧裁决自动视为 stale。
- `src/analysis/page_builder.py`
  - 正式构建阶段 overlay QA 展示投影，不修改 Silver 本体。
- `src/analysis/page_renderer.py`
  - 默认显示问题、结论和高/中/低单字置信度；
  - time-bound 显示时间节点；
  - 依据/核验说明折叠；
  - 搜索可直接命中 QA 问题/答案；
  - QA 粒度“没用 / 存资料库 / 留阶段记录”。
- `src/app/serve_analysis.py`
  - 新增 `/api/display-review-state` 和 `/api/display-review-decision`；
  - QA 裁决独立于 Silver semantic state。

新增展示层回归测试，并保留既有 Silver 页面兼容测试。

## 348 条历史 Silver 全量迁移

私密 FAQ 候选中此前已经完成 348 条 Silver 的全量事实→Q/A 审计。此次不重新清洗语义，而是把已审候选压成正式展示投影。

最终：

- Silver 覆盖：**348 / 348**；
- QA：**1034**；
- 当前首次阅读：**301 Silver / 899 QA**；
- confidence：**18 high / 861 medium / 155 low**；
- lifecycle：**972 durable / 62 time_bound**；
- mechanical fallback：**0**。

自动投影采取保守策略：

- 不自动授予 high；high 只来自明确人工覆盖；
- 机械压缩默认只给 medium/low；
- time-bound 按 QA 的实际用途窗口判断，不因为证据里恰好提到价格/工资就把整个主题标成时效性。

复杂样本人工覆盖包括用户确认的 #012 / #083 / #119 / #160 / #193 / #202，以及原私密候选没有标准 Q/A 结构的 31 条复杂 Silver。

## 旧私密预览退役

用户明确确认私密预览只属于测试阶段，不再需要。

已删除：

- `history-knowledge-preview.html`
- `build_history_knowledge_preview.py`
- `faq-projection-preview-v1.md`
- `faq-projection-v1.json`
- 五案例临时预览
- 临时 fallback dump / implementation plan

保留历史候选批次、全量覆盖审计、跨批边界和主领域索引，继续作为迁移与证据审计材料，不作为正式页面 owner。

## 正式页面

正式入口仍为：

`python3 -m src.app.serve_analysis`

正式页面：

`runtime/reports/review-live/page.html`

顶层分类结构不变：新信息 / 资料库 / 无限服 / 黑话；普通信息一级分类和职业/副本二级分类也保持原设计。

## 验证

本阶段建立并验证：

- 多 QA 投影；
- time-bound 必须带时间节点；
- 重复 qa_id / 未知 Silver / 投影漏 Silver 均拒绝；
- 置信度变化不改变 QA semantic fingerprint；
- 结论变化会改变 fingerprint；
- QA 级裁决可独立持久化；
- stale QA 裁决不会继续继承；
- time-bound 不能进入长期知识库、可以留阶段记录；
- 正式 page builder 可在 348 / 348 全覆盖投影下重建 review-live。

完整回归：

`python3 -m unittest discover -s tests -p 'test_*.py' -q`

结果：**316 tests OK**。

## 下一阶段

不再继续改私密预览。

下一步只让用户按正常方式浏览正式 `review-live` 页面，不要求逐条看完 899 个首次阅读 QA；一旦发现稳定的拆分、置信度、时效性或表达错误，就按错误类型修展示投影。

用户确认正式页面稳定后，才恢复真实 incremental batch。恢复后，新增/实质改写 Silver 必须在正式发布前同步生成完整 QA 投影或显式 `hidden_no_value`，全覆盖门禁禁止旧式长正文悄悄回流。
