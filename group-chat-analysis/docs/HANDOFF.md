# 群聊分析交接

本文件只记录跨 agent 接续时必须知道、但不应复制到长期 owner 的临时交接注意事项。

当前进度、已验证状态与下一目标只以 `docs/CURRENT.md` 为真；未完成事项只以 `tasks/todo.md` 为真。不要在本文件维护第二份状态清单。

## 本轮接续要点

- 当前阶段已经从“继续扩大历史清洗”切换为“**暂停采集，先实际验收现有清洗成果**”。
- 只使用 `wow-infinite-time` 已完整验收的 2026-09-13 → 2026-10-18 共 36/36 天历史；第二群暂不采，第一个群也不补 2026-10-19 之后消息。
- 用户当前主要要判断：323 条首次阅读 Silver 是否真的有用，而不是继续提高历史覆盖量。
- 第一轮抽查结论：明显问句近重复不是当前主要问题；36 天大集合导致的“卡片较宽”暂不改规则，未来日常一两天增量再观察。结构正确但用户不关心的信息属于终审价值判断，不先视为清洗缺陷。
- 正式页面当前应从 `src/analysis/page_builder.py` / `page_renderer.py` 构建；正式用户裁决通过 `src/app/serve_analysis.py` 持久化。不要恢复旧 runtime 原型脚本为代码 owner。
- 正式 Question Registry 入口是 `runtime/analysis-work/question-cluster-registry-current.json`；历史 v71 只作 bootstrap 快照。
- 当前没有待消费 incremental checkpoint。checkpoint 能力保留，但用户已经明确当前不继续采集。
- 最新阶段证据归档：`docs/archive/neat/2026-10-25-formal-analysis-publication-and-review-baseline.md`。

其余规则一律按 `SKILL.md → docs/OPERATING-SOP.md → 对应 rules owner` 进入，不从历史 archive 或旧聊天记录反推现役流程。
