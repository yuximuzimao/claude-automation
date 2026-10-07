# 群聊分析交接

## 当前完成

阶段 2 的确定性核心已经从测试原型迁入正式 `src`：

- `src/normalize/overlap.py`：相邻页保守去重 + capture 页顺序转聊天时间顺序。
- `src/store/batch_state.py`：可恢复 batch/state。
- `src/store/message_record.py`：从正式 JSON Schema 读取结构真值并做运行时 record 校验。
- `src/inbox/builder.py`：completed/analyzed batch 的 current.md 原子生成。

测试已删除对应实现副本，`tests/test_normalize_overlap.py`、`tests/test_batch_state.py`、`tests/test_dry_run_gate.py` 现在直接测试正式模块。

## 当前关键契约

- v1 的优先级是“漏真实消息 > 多一条重复消息”。
- 只做相邻/近邻页面连续序列去重，不做全局 `sender+text` 唯一化。
- 相似昵称不归并；一侧昵称缺失时不做破坏性去重。
- `message_type` 必须一致；双方存在 `timestamp_text` 时必须兼容。
- 正文受控模糊阈值为 `0.90`。
- 默认最小连续重叠为 2 条；只有两条时必须再有昵称、时间或至少 8 个规范化字符的匿名精确正文强锚点。
- canonical 重复消息先保留更完整正文，再比较元数据完整度和 OCR confidence。
- `page_index` 递增代表从最新向历史采集；`merge_capture_order_pages()` 负责显式转成最终旧→新顺序。
- incomplete batch 不生成 current.md；analyzed 只能复现原 completed 输入；非法 message record 不得覆盖旧 current.md。
- 头像指纹不是 v1 门禁，只有真实 dry-run 证明重复量已经影响使用时才重新评估。

## 验证

`python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **40/40 通过**。

新增回归覆盖包括：

- 不同 `message_type` 不得去重；
- 双方已识别但不同时间不得去重；
- 一侧昵称缺失不得破坏性去重；
- 两条匿名短文本不足以确认重叠；
- 高 confidence 的截短 OCR 不得覆盖更完整正文；
- capture 的“新→旧”页面必须先转换后再全局合并；
- 合成 dry-run 全程使用正式 `src.normalize/src.store/src.inbox`，不再通过测试副本得到假绿。

## 下一步

按 `tasks/todo.md` 顶部执行阶段 2-4：

1. 从旧 capture worktree 只迁移仍有效的 ScreenCaptureKit / Vision / 安全滚轮能力；窗口准备改用现役 Accessibility 设置/读回方案，并适配当前 capture Schema 与变化检测门禁。
2. 把已验证 bbox 规则实现到正式 normalize。
3. 设计并实现 `messages.jsonl` 与 batch state 的崩溃安全持久化顺序。
4. 在一个目标群上跑 3–5 页真实 dry-run，通过后才进入两群切换和首次全量。
