# 群聊分析交接

本文件只记录跨 agent 接续时必须知道、但不应复制到长期 owner 的临时交接注意事项。

当前进度、已验证状态与下一目标只以 `docs/CURRENT.md` 为真；未完成事项只以 `tasks/todo.md` 为真。不要在本文件维护第二份状态清单。

## 本轮接续要点

- 最新阶段已归档到 `docs/archive/neat/2026-10-21-atomic-claim-question-cluster-cleaning.md`：36日历史基线不变，Atomic Claim 生产已推进至 B37，no-claim reviewed 退出机制已正式启用。现役恢复点是**重建 work queue 后从 H27 / `T-20261012-053` 继续 high-anchor 清洗，清完后进入 direct-source-retrieval**。旧页面压缩口径只保留为历史，不要恢复旧流程。
- 第一轮 topic card 现役定义仍是“候选索引层”；用户真正看到的是**首次阅读队列**：尽量不漏掉第一次值得看一眼的游戏特异信息，通过语义去重、已有知识比对、基础身份补齐和同话题合并降低阅读摩擦。
- 当前 runtime 页面仍输出到 `runtime/reports/page-v2-prototype-light.html`，但 UI 已切成 **新信息 / 资料库 / 无限服 / 黑话** 四入口；职业和副本/任务/装备/插件/防骗等都是同级专题，不做交叉筛选。
- 用户终审只有“没用 / 存资料库”：两者都视为已阅，相同语义不再重复；只有“存资料库”进入长期知识。纯可信度升降只后台静默更新，不重新占阅读队列。
- 展示前应尽量补齐对象身份。`T-20260925-020` 已作为样例补成“风暴峭壁 · 《弥补关系》#12915 + 任务目标 + 土灵宠物式控制栏技巧”。基础身份补齐是分析职责；需要额外联网研究的才标“可补全”。
- 无限服是当前唯一动态专题，runtime 草案为 `runtime/analysis-work/infinite-dossier-v1.json`；普通讨论热度不单独当趋势，只有能解释发展阶段、供需或潜在打金机会时才进入综合判断。
- 下一会话严格从 `tasks/todo.md` 顶部恢复：先重建 `atomic-claim-work-queue-v1.json`，随后从 H27 继续按 `canonical → claim quality → existing-cluster assignment → bootstrap → recall audit → reviewed registry` 批量清洗。相似度始终只做召回，禁止自动合并；没有可复用命题的卡进入 no-claim reviewed，不要为了 schema 制造知识。
- 当前正式 Silver 已推进到 **105 个知识单元 / 624 张完整吸收来源卡**；候选层为 613 full / 1644 unabsorbed / 21 partial，叠加 dossier 等 normalized components 后为 657 full / 1600 unabsorbed / 21 partial。历史分析窗口与用户阅读批次必须分离，当前页面每批最多40个阅读单元。
- 黑话继续作为独立词典入口。
- 原文回链已禁止用全日关键词/数字相似度冒充证据，优先使用卡片自身时间/来源范围；证据不足宁可待补。
- 2026-10-12 ZAM/树皮原文重复根因已定位：旧页 `top fragment` 被下一页完整回复吸收时会阻断旧 overlap。normalizer 已按保守条件修复并有 26 项相关测试通过；旧 canonical 未直接删行，以免破坏大量历史 source_ranges。
- 正式采集入口仍唯一为 `python3 -m src.app.run_capture`；不要恢复旧 planner、Python 日历格、旧 completion 阈值或其它平行入口。

其余规则一律按 `SKILL.md → docs/OPERATING-SOP.md → 对应 rules owner` 进入，不从历史 archive 或旧聊天记录反推现役流程。
