# CURRENT — 群聊分析

这是项目当前开发状态的唯一真值。

## 当前阶段

**阶段 0 已完成；阶段 1 真实采集路径已验证；阶段 2 的确定性核心已正式化，正在接真实 capture 与 bbox 重建。**

当前正式代码已经包含相邻页保守去重、batch/state、message-record 校验和 current.md builder。测试不再维护这些逻辑的副本，而是直接覆盖 `src/`。尚未完成的是：把真实 QQ capture 迁入现役入口、把已实测 bbox 规则实现为正式消息重建、落盘 `messages.jsonl`，以及跑真实 3–5 页端到端 dry-run。

## 当前已验证事实

1. 官方 QQ 的“聊天记录”独立窗口是正式采集对象；Accessibility 正文树不足以作为正文读取通道。
2. ScreenCaptureKit 可稳定做窗口级捕获，Apple Vision 本地 OCR 可读群名、日期、时间、昵称和正文。
3. 窗口准备可通过 Accessibility 设置并读回 `AXPosition/AXSize`；现役规则不使用鼠标拖窗口 fallback。
4. 正文区域可从窗口/OCR结构动态定位；系统滚轮可只作用于消息正文。变化检测阈值、等待时序和失败边界以 `docs/rules/capture.md` 为唯一规则。
5. `capture-page.schema.json` 的 `page_index` 从 0 开始表示采集顺序：从最新位置向历史滚动时递增，因此多页输入天然是“新→旧”；单页内部消息视觉顺序仍为“旧→新”。
6. 普通文字、多块文字、视觉行横向拆分、页边缘残片、系统消息及可见图片/表情区域均已有真实 QQ 多页证据；具体几何重建规则以 `docs/rules/normalization.md` 为准。语音与文件继续延期，不阻塞 v1。
7. 相邻页去重正式实现位于 `src/normalize/overlap.py`：正文模糊阈值 `0.90`；默认至少 2 条连续消息；两条最小重叠还需额外强锚点；匿名精确正文锚点至少 8 个规范化字符。
8. v1 不做相似昵称身份归并。一侧昵称缺失时不做破坏性去重；`message_type` 必须一致，双方都有 `timestamp_text` 时也必须兼容。证据不足宁可保留重复。
9. canonical 重复消息先保留更完整正文，再比较元数据完整度和 OCR confidence；高 confidence 不再能覆盖明显更完整的低 confidence 正文。
10. `merge_capture_order_pages()` 显式把 `page_index` 递增的“新→旧”页面转换为最终“旧→新”消息，避免调用方默认方向导致漏去重或乱序。
11. `src/store/batch_state.py` 正式实现 `incomplete/completed/analyzed`、批次级连续页恢复点、每群连续完成锚点和原子 state replace。
12. `src/store/message_record.py` 从 `schemas/message-record.schema.json` 读取字段集合、枚举和 const，并统一承担运行时 message-record 校验；inbox/test 不再各维护一份 Schema 副本。
13. `src/inbox/builder.py` 只允许 completed/analyzed batch 生成 `runtime/inbox/current.md`；非法记录或错误 batch/group/sequence 不得覆盖上一份已完成输入。
14. `python3 -m unittest discover -s tests -p 'test_*.py'` 当前 40/40 通过，并且全部直接测试正式 `src`；额外覆盖 incomplete 恢复群集合漂移、completed 空消息伪输入、message-record 时间/字段契约等门禁。

## 尚未验证 / 尚未实现

- 旧 capture worktree 中的 Swift 采集代码尚未按现役 AX 窗口准备、变化检测和最新 Schema 迁入正式 `src/capture`。
- bbox → 视觉行 → 消息候选的正式代码尚未落地；目前只有规则与真实诊断证据。
- `runtime/messages/messages.jsonl` 的正式持久化与跨 state/messages 的崩溃恢复顺序尚未实现。
- 当前正式模块尚未跑真实 QQ 3–5 页端到端 dry-run。
- Apple Vision 长时间大量连续页面的性能/稳定性、首次全量历史边界、每日增量停止锚点、两个目标群的安全切换仍未验证。
- 非文字图片/表情已有视觉证据，但“无 OCR block 时如何可靠生成 unknown 占位”仍需随正式 bbox/capture 实现决定；不得为占位功能增加高风险读取路径。

## 下一恢复点

直接执行 `tasks/todo.md` 顶部的唯一下一步：**阶段 2-4：迁移真实 capture + 实现正式 bbox 重建和 messages 持久化，然后在一个目标群上跑 3–5 页真实 dry-run。**

头像指纹不再是 v1 门禁。只有真实 dry-run 证明保守去重导致的重复已经影响实际分析时，才重新评估视觉身份辅助。
