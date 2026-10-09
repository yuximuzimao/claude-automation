# 当前待办

只记录尚未完成且会改变下一步工作的事项。

## 下一步（新窗口从这里开始）

**阶段 4：按已确认契约制作分析页面 v2 原型。** AIHOT 参考研究与页面方向已经完成：分析先完整归组所有有意义话题，再按个人价值排序；每条实质信息固定展示“事实信息 → 群聊原文 → AI 扩展分析”；价值与可信度分开，讨论热度不作为核心排序值；纯黑话只进入独立词典。下一步先确定运行时分析结果结构，再用真实增量批次制作 v2 评审原型，不直接重跑大规模历史采集。

## B. 阶段 2 — 已完成，不再作为待办维护

现役能力包括：
- 唯一正式入口 `python3 -m src.app.run_capture`，Swift 仅保留内部单步 `capture-step`；
- batch-state v4：保留 `pending_capture` / 每群 `capture_complete`，新增 `batch_kind` 与 incremental `start_anchor`；顺序固定为 pending → 单步副作用 → raw durable → record_page；
- capture-page v2 `dhash512` 视口连续性门禁，当前阈值 `<=20`；
- AX/SCK/Vision、正文区、安全滚轮、MAD、`<=3px` SCK 尺寸漂移容忍；
- bbox/视觉行/fragment/media unknown 重建；
- 相邻页保守去重与新→旧/旧→新顺序转换；
- `messages.jsonl` 原子幂等持久化与 messages → completed → current 恢复；
- `pending current`、durable raw 晋升、`pending scroll` 硬停、completed current 重建等故障注入；
- 一个真实目标群的 3 页唯一 runner 全链验证。

无 OCR 的纯图片/表情、语音、文件不属于 v1 文字优先阻塞项。视口 dHash 不是头像身份指纹；头像/昵称视觉身份辅助仍不属于 v1 去重门禁。

## C. 阶段 3 — 两群与首次全量抓取

- [x] **安全切换两个目标群。** 已验证：左侧会话 OCR 唯一定位 + 安全区门禁 → 选中后头部复核 → hover 后局部 OCR 精确确认 `聊天记录` → 打开后历史窗口标题精确匹配。任何一步不满足即停止。
- [x] **两群同批次编排 + 历史边界/安全分片。** 已实现全局 page_index、每群 capture_complete、连续两次 NO_CHANGE 边界、20 页安全分片、恢复时不重开已有 durable 页群。
- [x] **真实首次全量抓取。** `first-full-20261008` 已完成：1147 页、7293 条 canonical messages，两群均 capture_complete。
- [x] **程序性完整性审计。** 全局 page 0–1146 连续；两群 sequence 连续；无未知 group、无重复 record_id；1147/1147 页 reconstruct bad=0；anchors 匹配各群 canonical 尾部。

## D. 阶段 4 — GPT 分析

- [ ] **制作页面 v2 真实批次原型并收口正式分析入口。** 先定义能表达分类、事实、原文、AI 扩展、价值等级、可信度、时间范围和页面去向的运行时结果结构；再实现“本期总览 / 话题总览 / 长期追踪 / 攻略知识 / 项目相关 / 黑话”六个视图。评审稳定后补正式批次分析 runner 与 `analyzed` 状态入口；在此之前按 `docs/OPERATING-SOP.md` 人工触发，不手改状态文件。话题总览负责覆盖，不得退化成已删除的浅层“全部信息”重复页。
- [ ] **黑话做成语境化持续词典。** 纯黑话不生成普通话题卡，只保留“解释 + 最小原文 + 适用语境 + 首次/最近出现”；同一词允许随副本、物品、服务器或语境出现不同含义，例如“片”不能永久绑定瓦兰奈尔碎片，后续新语义新增记录而不是覆盖旧解释。
- [ ] **验证大批量上下文策略。** 如果单日文本超出一次读取/分析的合理规模，分块必须保持群、时间与讨论连续性，再做全局合并；不能先用关键词硬筛导致重要消息永久丢失。
- [ ] **决定历史覆盖策略。** 当前已有 `first-full-20261008` 的 7293 条 canonical，但它只覆盖当时 QQ 本机可见历史且尚未做完整语义整理；后续需要单独讨论：是直接分块分析这 7293 条，还是重新从“入群至今”尽可能补采一遍，再建立更完整历史基线。方案未定前不重复大规模采集。
- [x] **保存第一版本地报告与页面原型。** `runtime/reports/2026-10-09-incremental-001.md`、项目导向 v2 和页面 v1 已生成；它们是评审样本，不自动写入魔兽项目，也不视为最终页面格式。

## E. 阶段 5 — 每日增量与自动化

- [x] **实现每日增量锚点。** 已完成 `--incremental`、v4 `batch_kind/start_anchor`、新 batch 强制重开历史窗口、分片续跑不重开、连续 anchor 停止/裁剪、0/1 新消息与 completed 本地重建；真实首次全量两组 anchor 离线均精确命中 canonical 尾部。
- [x] **第一次真实增量实跑与审计。** `incremental-20261009-001` 已 completed：95 个 raw pages、611 条新增 canonical（第一群 609 / 第二群 2）；两群旧 anchor 均未重复入库、sequence 连续、record_id 无重复、新 completed anchor 正确前滚。
- [ ] **稳定后再决定是否定时。** 只有手动增量流程多次稳定后才考虑每天一次的调度；调度失败必须可见且不得产生伪 completed。
