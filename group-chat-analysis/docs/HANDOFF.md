# 群聊分析交接

本文件只记录跨 agent 接续时必须知道、但不应复制到长期 owner 的临时交接注意事项。

当前进度、已验证状态与下一目标只以 `docs/CURRENT.md` 为真；未完成事项只以 `tasks/todo.md` 为真。不要在本文件维护第二份状态清单。

## 本轮接续要点

- 当前正式阶段已经从“私密 FAQ 候选试验”切换到 **正式 Silver→QA 展示层验收**。旧私密 FAQ/HTML 预览已退役并删除，不再恢复或继续维护。
- 现有 **348 / 348 Silver 已投影为 1034 个 QA**；当前正式首次阅读为 **301 个 Silver 主题 / 899 个 QA**。Silver 事实层和历史用户 knowledge/discard 裁决没有因为展示拆分而改写。
- 页面默认只显示 **问题 + 直接结论 + 高/中/低单字置信度**；必要条件只有省略会导致误用时才显示。依据、来源、判档理由和具体核验建议默认折叠；除置信度外默认零标签。现役契约见 `docs/rules/presentation.md`。
- **Silver 不拆，页面 QA 可拆。** 拆分标准是答案能否被独立搜索并独立改变判断/操作。QA 有独立语义指纹和独立裁决；仅置信度变化不会重新进入待审，问题/结论/生命周期或时间范围实质变化会使旧 QA 裁决失效。
- 时效性 QA 使用 `time_bound + time_context`。durable QA 的动作是“没用 / 存资料库”；time-bound QA 是“没用 / 留阶段记录”，服务端硬拒绝 time-bound → knowledge，避免首周行情、活动窗口、短期价格进入长期资料库。后续“已验证 / 被推翻 / 部分验证”关系仍在 Todo，等恢复新数据后再做。
- QA 级裁决写入 `runtime/analysis-work/display-review-decisions-v1.json`；正式投影为 `runtime/analysis-work/knowledge-display-projection-v1.json`。页面构建要求投影覆盖全部 Silver，缺任一 knowledge_id 会失败，不允许静默回退旧长正文。
- 正式页面仍由 `src/analysis/page_builder.py` / `page_renderer.py` 构建，正式用户裁决仍通过 `src/app/serve_analysis.py` 持久化。不要恢复 runtime 原型脚本为代码 owner。
- 当前完整回归为 **316 tests OK**；正式 `runtime/reports/review-live/page.html` 已按 QA 投影重建。下一步是用户直接浏览该正式页面，发现稳定错误类型后按类型修，不要求逐条重审全部 QA。
- 继续只使用 `wow-infinite-time` 已完整验收的 2026-09-13 → 2026-10-18 共 36/36 天历史；第二群暂不采，第一个群也不补 2026-10-19 之后消息。用户确认正式 QA 页面稳定后，才考虑恢复真实 incremental batch。
- 当前正式基线仍为 **348 Silver / 301 首次阅读 Silver / 10 reviewed knowledge / 44 reviewed semantic states（10 knowledge + 34 discard）/ 38 dossier signals**。QA 展示层是在此基线上叠加，不改变这些 Silver 语义统计。
- 当前稳定清洗边界仍不变：具体事实优先于泛化方法论；`coverage=full` 不代表 canonical 原文没有其它事实；上层 discard 不向下继承原文；窄用途事实保持窄表达；冲突口径保留冲突；连续原文窗口允许夹相邻无关聊天，但不得把邻聊当新知识来源。资料库 knowledge 允许重构内容，但用户 knowledge/discard 裁决不可被模型改变。`#114 / #150 / #152 / #171` 当前仍明确保留待看。
- 正式 Question Registry 入口仍是 `runtime/analysis-work/question-cluster-registry-current.json`；历史 v71 只作 bootstrap 快照。当前没有待消费 incremental checkpoint。
- 页面一级分类保持“职业 / 副本攻略 / 任务与练级 / 装备机制 / 专业技能 / 经济与打金 / 插件与故障排查 / 防诈骗经验 / PVP与野外生态 / 其他”；仅职业和副本提供现有二级；无限服继续独立 dossier。
- 最新阶段证据归档：`docs/archive/neat/2026-11-03-silver-to-qa-display-projection.md`；上一阶段候选知识化归档：`docs/archive/neat/2026-11-01-complete-silver-knowledge-candidate-conversion.md`。

其余规则一律按 `SKILL.md → docs/OPERATING-SOP.md → 对应 rules owner` 进入，不从历史 archive 或旧聊天记录反推现役流程。
