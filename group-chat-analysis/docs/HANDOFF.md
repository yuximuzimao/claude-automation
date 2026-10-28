# 群聊分析交接

本文件只记录跨 agent 接续时必须知道、但不应复制到长期 owner 的临时交接注意事项。

当前进度、已验证状态与下一目标只以 `docs/CURRENT.md` 为真；未完成事项只以 `tasks/todo.md` 为真。不要在本文件维护第二份状态清单。

## 本轮接续要点

- 当前阶段已经完成 **346 条 Silver 全量二次清洗**，继续暂停采集；下一步只抽查重建后的页面质量，不再为了验证而重新逐条清全部历史。
- 只使用 `wow-infinite-time` 已完整验收的 2026-09-13 → 2026-10-18 共 36/36 天历史；第二群暂不采，第一个群也不补 2026-10-19 之后消息。
- 当前正式基线：**346 Silver / 299 首次阅读 / 10 reviewed knowledge / 44 reviewed semantic states（10 knowledge + 34 discard）/ 38 dossier signals**。本轮全量二次处理为 **60 条重写 / 286 条保持**，knowledge ID 与编号顺序不变。
- 当前稳定清洗边界：具体事实优先于泛化方法论；`coverage=full` 不代表 canonical 原文没有其它事实；上层 discard 不向下继承原文；窄用途事实保持窄表达；冲突口径保留冲突；连续原文窗口允许夹相邻无关聊天，但不得把邻聊当新知识来源。资料库 knowledge 也允许重构内容，但用户 knowledge/discard 裁决不可被模型改变。`#114 / #150 / #152 / #171` 当前仍明确保留待看。
- 正式页面当前应从 `src/analysis/page_builder.py` / `page_renderer.py` 构建；正式用户裁决通过 `src/app/serve_analysis.py` 持久化。不要恢复旧 runtime 原型脚本为代码 owner。
- 正式 Question Registry 入口是 `runtime/analysis-work/question-cluster-registry-current.json`；历史 v71 只作 bootstrap 快照。
- 当前没有待消费 incremental checkpoint。checkpoint 能力保留，但用户已经明确当前不继续采集。
- 2026-10-25 用户进一步澄清页面分类：无限服继续独立；普通信息恢复“职业 / 副本攻略 / 任务与练级 / 装备机制 / 专业技能 / 经济与打金 / 插件与故障排查 / 防诈骗经验 / PVP与野外生态 / 其他”的稳定一级结构。当前仅职业按具体职业、副本按具体副本提供二级，其他专题暂不下钻；Silver 内部细粒度 `topics` 只做映射、清洗和搜索，不直接生成新的一级标签。现役契约见 `rules/analysis.md`。
- 阅读页每个 Silver 单元已有稳定编号，不随筛选、搜索、翻页或裁决重排；用户可以直接按 `#编号` 反馈。`#304` 已纠正为“雷霆 → 惊雷（锻造武器升级）”，一级归类为“装备机制”。正式 review server 的“没用 / 存资料库”已完成真实点击、重建和重开验证，裁决可持久化。
- 最新阶段证据归档：`docs/archive/neat/2026-10-28-full-silver-secondary-cleaning.md`；上一阶段价值校准见 `docs/archive/neat/2026-10-28-first-read-value-calibration-and-review-ux.md`。

其余规则一律按 `SKILL.md → docs/OPERATING-SOP.md → 对应 rules owner` 进入，不从历史 archive 或旧聊天记录反推现役流程。
