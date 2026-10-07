# 当前待办

只记录尚未完成且会改变下一步工作的事项。

## 下一步（新窗口从这里开始）

**阶段 2-4：把真实 QQ capture 与 bbox 消息重建接到现役 `src`，再跑一个群 3–5 页真实 dry-run。** 去重、batch/state、message-record 校验和 current.md builder 已正式化；当前缺的是正式 capture 适配器、bbox→消息重建、messages.jsonl 持久化与真实端到端验证。

## B. 阶段 2 — 消息重建与完整保存

- [ ] **迁移真实 capture 到现役入口。** 只复用旧 capture worktree 已验证的 ScreenCaptureKit / Vision / 安全滚轮能力；窗口准备必须按现役规则使用 Accessibility 设置/读回几何，不复活鼠标拖窗口方案；输出必须符合当前 `capture-page.schema.json`，并接入现役变化检测门禁。
- [ ] **实现正式 bbox 消息重建。** 按 `docs/rules/normalization.md` 已实测规则实现视觉行归并、消息头/正文分组、页边缘残片、系统消息和 unknown 非文字占位；语音/文件继续延期，不阻塞 v1。
- [ ] **实现规范化消息库。** 把通过 `src/store/message_record.py` 校验的 canonical 记录安全写入 `runtime/messages/messages.jsonl`；必须先设计清楚 incomplete/completed 与消息文件之间的崩溃恢复顺序，不能出现 state 已 completed 但消息未落盘的伪完成。
- [ ] **真实 3–5 页 dry-run。** 一个目标群、小范围历史，验证 capture 顺序转聊天顺序、误去重/漏去重、OCR轻微差异、页恢复点、messages 持久化和 current.md 门禁。证据不足的重复允许保留，真实消息不得因去重丢失。

已完成的阶段 2 基础契约不再作为待办重复维护：相邻页保守去重、`batch-state`、message-record 校验、current.md builder、合成 dry-run 已进入正式 `src`，测试直接覆盖正式实现。

头像指纹不再是 v1 门禁。只有真实 dry-run 证明保守去重产生的重复量已经影响实际使用时，才重新评估视觉身份辅助。

## C. 阶段 3 — 两群与首次全量抓取

- [ ] **安全切换两个目标群。** 先设计并验证群定位/切换，不允许盲点坐标或可能触发发送/确认的 UI 动作。
- [ ] **首次全量抓取。** 明确历史边界后抓取两个群文字；允许长任务分批恢复，但最终只把经过完整性确认的 batch 标为 completed。
- [ ] **人工抽样/程序性完整性审计。** 重点检查漏页、乱序、误去重、其它群污染，不要求用户逐条人眼核对。

## D. 阶段 4 — GPT 分析

- [ ] **确定日报输出格式。** GPT 只读 `runtime/inbox/current.md`，区分值得关注、多人共识、单人经验/传闻、争议、待核验、可能影响现有项目。
- [ ] **验证大批量上下文策略。** 如果单日文本超出一次读取/分析的合理规模，分块必须保持群、时间与讨论连续性，再做全局合并；不能先用关键词硬筛导致重要消息永久丢失。
- [ ] **保存本地报告。** 输出到 `runtime/reports/`；不自动写入魔兽项目。

## E. 阶段 5 — 每日增量与自动化

- [ ] **建立每日增量锚点。** 从上次 completed 序列锚点向新消息收敛，验证不会重复抓一整天或漏掉跨日讨论。
- [ ] **稳定后再决定是否定时。** 只有手动流程多次稳定后才考虑每天一次的调度；调度失败必须可见且不得产生伪 completed。
