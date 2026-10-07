# 群聊分析交接

## 当前完成

阶段 2 的真实链已进入正式 `src` 并完成一个目标群的 3 页真实 dry-run：

- `src/capture/`：AX 精确窗口准备、SCK 几何稳定、窗口级捕获、Vision OCR、正文区定位、安全滚轮、MAD 稳定门禁、raw 原子写入。
- `src/normalize/page_reconstruct.py`：视觉行、消息头/正文、页边缘 fragment、system、媒体 OCR unknown 降级。
- `src/normalize/assemble.py` + `overlap.py`：单页新→旧转旧→新、跨页保守连续序列去重、可见 fragment 保留。
- `src/store/message_store.py`：canonical `messages.jsonl` Schema 校验、fsync + 原子 replace、同 batch 幂等恢复。
- `src/store/finalize.py`：messages durable → state completed → current.md 的固定提交顺序与恢复。
- `src/store/batch_state.py` / `message_record.py` / `src/inbox/builder.py`：继续作为唯一状态、记录和分析输入边界。

真实 3 页测试只写临时 canonical store，没有污染正式 runtime。最终 assembly 为 24 条记录，可靠消除 2 条重复；1 条嵌入图片 OCR 被降级为 unknown，current.md 不包含图片内 OCR。

## 当前关键契约

- 错误成本：**漏真实消息 > 多保留重复消息**。
- QQ 历史窗口单页视觉上→下是新→旧；单页重建结束后才反转完整消息为旧→新。`page_index` 递增表示向更旧页面采集。
- 只做相邻页连续序列去重；不做全局 `sender+text` 唯一化。
- 相似昵称不归并；一侧 sender 缺失不做破坏性去重；`message_type` 和双方已识别时间必须兼容。
- 正文模糊阈值 `0.90`；最小连续重叠 2 条，两条重叠还需额外强锚点。
- 页边缘 fragment 不直接丢弃；无法可靠确认的可见文字宁可重复保留。
- 媒体 OCR 只有命中窄几何门禁才降级为 unknown；无 OCR 的纯图片/表情按 v1 文字优先目标忽略。
- `messages.jsonl` 必须先可靠落盘，之后才能 completed；current.md 是 completed 后可重建派生物。
- 头像指纹不是 v1 门禁。

## 验证

`python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **63/63 通过**。

真实验证包括：
- AX 扰动/恢复 + SCK frame 稳定；
- 3 页捕获，两次 630px 滚动均满足“明显变化后稳定”的 MAD 门禁；
- raw → bbox → assembly → canonical messages → completed state → current.md 全链；
- 图片内 OCR 不进入 current.md；
- messages/state/current 两个崩溃窗口的合成恢复；
- “画面先变化又回 baseline”不得误判为新页。

## 下一步

按 `tasks/todo.md` 顶部执行阶段 2-5：把现役模块收成唯一正式运行入口，并对捕获过程做中断故障注入。重点不是继续扩识别规则，而是确认“页已写、刚滚动、下一页未写”等状态都能确定恢复或安全停止。通过后删除旧 capture worktree，进入双群切换与首次全量。
