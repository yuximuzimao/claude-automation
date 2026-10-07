# CURRENT — 群聊分析

这是项目当前开发状态的唯一真值。

## 当前阶段

**阶段 0/1 已完成；阶段 2 的真实 capture → normalize → messages → state → current.md 链已经跑通。下一步是把这条链收成唯一正式运行入口并验证中断恢复，然后进入双群/首次全量。**

现役代码已经不再依赖旧 capture worktree：Swift capture、Python bbox 重建/跨页去重、canonical messages 持久化、batch state 和 current.md 都已有正式 `src/` 实现。真实 3 页 dry-run 使用临时输出目录完成，没有污染正式 `runtime/messages/messages.jsonl`。

## 当前已验证事实

1. 官方 QQ 的“聊天记录”独立窗口是正式采集对象；Accessibility 正文树不足以作为正文读取通道。
2. `src/capture/` 已正式迁入 ScreenCaptureKit + Apple Vision。窗口准备采用唯一同标题 `AXWindow` → 设置/读回 `AXPosition/AXSize` → 等待唯一同标题 SCK frame 稳定；不使用鼠标拖窗口 fallback。
3. 真实扰动回归已验证：窗口可从缩小/移位状态恢复到本机目标几何；首次发现“AX 已读回但 SCK 尚未稳定”的瞬时 frame 漂移后，已增加有限 SCK 几何稳定门禁。
4. 正文区域由工具栏 OCR 动态定位；正式滚动只在正文安全落点发送系统滚轮事件。真实 3 页测试的两次滚动 MAD 分别约为 `7.62 → 0.007`、`3.32 → 0.000`，符合“明显变化后重新稳定”门禁。最终帧若回到 baseline，不得判为新页。
5. `capture-page.schema.json` 的 `page_index` 表示全 batch 采集顺序，从最新位置向历史滚动时递增。当前 QQ 单页视觉从上到下也是**新→旧**；`reconstruct_page()` 完成视觉判断后把完整候选反转为**旧→新**。
6. `src/normalize/page_reconstruct.py` 已正式实现：正文区域过滤、视觉行归并、日期/消息头识别、sender 缺失保持未知、多行正文、异常大间距、页顶/页底残片、居中 system 候选。
7. 嵌入图片中的 OCR 已在真实页发现。当前只在“至少 3 行且 ≥80% 行高度 `<=0.85 ×` 正文主高度”的窄门禁下把候选降级为 `unknown / 非文字内容（图片/表情等，未解析）`；图片内 OCR 不进入 GPT 文字输入。无 OCR 的纯图片/表情按 v1 目标继续忽略。
8. `src/normalize/overlap.py` 只做相邻页保守连续序列去重：正文模糊阈值 `0.90`；默认至少 2 条连续消息；相似昵称不归并；一侧昵称缺失时不破坏性去重；`message_type` 和双方已识别时间必须兼容；canonical 先保正文完整度再看 confidence。
9. 页边缘可见 fragment 不直接丢弃。能结构化的 fragment 可参与相邻页重叠；无法可靠识别头部的可见文字保留为 sender/time 未知的 text。真实 3 页 assembly 得到 24 条记录，可靠去掉 2 条重复，同时保留短文本/坏头部等不确定重复。
10. `src/store/message_store.py` 已实现 `runtime/messages/messages.jsonl` 的 Schema 校验、`fsync` + 原子 replace、同 batch 幂等恢复和冲突拒绝。
11. `src/store/finalize.py` 固定提交顺序为 **canonical messages durable → state completed → current.md**。崩在 messages/state 或 state/current 之间都可重跑恢复；若 state 已 completed 但 canonical messages 缺失/不一致，硬报错而不静默修补。
12. 真实 3 页全链 dry-run 已通过：24 条记录全部持久化到临时 canonical store，state 为 completed，current.md 成功生成，最终顺序 `08:59 → 09:16`；其中 1 条媒体候选为 unknown，current.md 不包含媒体 OCR/占位文本。
13. `python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **63/63 通过**，其中包含 Swift capture 编译/纯函数测试、MAD 回弹反例、bbox/assembly、message store 和崩溃恢复门禁。

## 尚未验证 / 尚未实现

- 还缺一个唯一正式运行入口，把 Swift capture、raw/state 页进度、normalize/finalize 串成可直接恢复的流程；当前真实 dry-run 是对正式模块逐段编排验证。
- 捕获进程在“页已写/刚滚动/下一页未写”等任意时点被杀后的自动恢复尚未做真实故障注入；这是首次全量前的最后一个 P0。
- Apple Vision 长时间大量连续页面的性能/稳定性、首次全量历史边界、每日增量停止锚点、两个目标群的安全切换仍未验证。
- 语音和文件继续延期；无 OCR 的纯图片/表情按 v1 文字优先目标忽略，不作为阻塞项。

## 下一恢复点

直接执行 `tasks/todo.md` 顶部唯一下一步：**把现役模块收成唯一运行入口，并对中断恢复做故障注入；通过后进入两个目标群的切换与首次全量。**

头像指纹不再是 v1 门禁。只有真实运行证明保守去重产生的重复量已经影响分析时，才重新评估视觉身份辅助。
