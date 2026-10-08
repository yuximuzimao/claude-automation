# 当前待办

只记录尚未完成且会改变下一步工作的事项。

## 下一步（新窗口从这里开始）

**阶段 5：实现并验证每日增量。** 首次全量已经完成并通过完整性审计；下一步每个群必须先重新打开“聊天记录”窗口刷新最新快照，再从最新向旧扫描，命中上一 completed batch 的连续消息 anchor 后停止，只提交新增消息。

## B. 阶段 2 — 已完成，不再作为待办维护

现役能力包括：
- 唯一正式入口 `python3 -m src.app.run_capture`，Swift 仅保留内部单步 `capture-step`；
- batch-state v3：保留 `pending_capture`，新增每群 `capture_complete`；顺序固定为 pending → 单步副作用 → raw durable → record_page；
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

- [ ] **确定日报输出格式。** GPT 只读 `runtime/inbox/current.md`，区分值得关注、多人共识、单人经验/传闻、争议、待核验、可能影响现有项目。
- [ ] **验证大批量上下文策略。** 如果单日文本超出一次读取/分析的合理规模，分块必须保持群、时间与讨论连续性，再做全局合并；不能先用关键词硬筛导致重要消息永久丢失。
- [ ] **保存本地报告。** 输出到 `runtime/reports/`；不自动写入魔兽项目。

## E. 阶段 5 — 每日增量与自动化

- [ ] **建立每日增量锚点。** 每个群开始增量前必须重新打开“聊天记录”窗口刷新最新快照；从最新向旧扫描，命中上次 completed 的连续消息 anchor 后停止，并只提交 anchor 之后的新消息。验证不会重复抓历史、不会把 anchor 本身重复写入新 batch，也不会漏掉跨日讨论。
- [ ] **稳定后再决定是否定时。** 只有手动增量流程多次稳定后才考虑每天一次的调度；调度失败必须可见且不得产生伪 completed。
