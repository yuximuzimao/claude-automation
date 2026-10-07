# CURRENT — 群聊分析

这是项目当前开发状态的唯一真值。

## 当前阶段

**阶段 0/1 已完成；阶段 2 的单群采集、规范化、持久化和中断恢复链已经完成。下一步进入阶段 3：安全切换两个目标群，然后做首次全量。**

正式入口现在唯一是 `python3 -m src.app.run_capture`。Python runner 独占 batch state 推进；Swift `capture-step` 只执行单次当前页/滚动页捕获，不再维护第二套恢复逻辑。旧 capture worktree 已不再是运行依赖。

## 当前已验证事实

1. 官方 QQ 的“聊天记录”独立窗口是正式采集对象；Accessibility 正文树不足以作为正文读取通道。
2. `src/capture/` 使用 ScreenCaptureKit + Apple Vision。窗口准备采用唯一同标题 `AXWindow` → 设置/读回 `AXPosition/AXSize` → 等待唯一同标题 SCK frame 稳定；不使用鼠标拖窗口 fallback。
3. SCK 偶发 1–3px 捕获尺寸漂移已实测。MAD 只容忍 `<=3px` 并把两帧渲染到共同尺寸比较；更大漂移硬停。最终帧若回到 baseline，也不得判为新页。
4. `capture-page.schema.json` 已升级为 v2：除原始 OCR 外保存私密 `dhash512` 视口指纹。该指纹**只**用于滚动前验证当前视口仍是上一份 durable raw 对应页面，不参与昵称/消息身份或去重。
5. 512-bit dHash 当前门槛为 Hamming distance `<=20`。同一未滚动视口连续 6 次实测为 `18,0,0,0,0`；三个不同真实页距离为 `46/49/31`。超过 20 时在发滚轮前停止。
6. `batch-state.schema.json` 已升级为 v2，新增 `pending_capture`。唯一顺序是 **pending intent → Swift 单步副作用 → raw durable → record_page**；`record_page()` 没有匹配 pending 时不能推进状态。
7. `pending current + raw 缺失` 可安全重试；`pending + raw 已落盘` 直接晋升 durable raw，不重复捕获；`pending scroll + 目标 raw 缺失` 视口位置不确定，必须硬停，禁止再次滚动；没有 pending 却凭空出现 next raw 也硬停。
8. 当前 QQ 单页视觉从上到下是**新→旧**；`reconstruct_page()` 完成视觉判断后把完整候选反转为**旧→新**。页边缘 fragment 不静默丢弃，证据不足宁可保留重复。
9. 嵌入图片 OCR 命中窄几何门禁时降级为 `unknown / 非文字内容（图片/表情等，未解析）`；图片内文字不进入 GPT 输入。无 OCR 的纯图片/表情、语音、文件继续不阻塞 v1。
10. 相邻页去重仍以“漏真实消息 > 多保留重复消息”为错误成本：相似昵称不归并，一侧 sender 缺失不破坏性去重，`message_type`/双方已识别时间必须兼容，canonical 先保正文完整度。
11. `messages.jsonl` 继续使用 Schema 校验、`fsync` + 原子 replace、同 batch 幂等恢复；完成顺序固定为 **messages durable → state completed → current.md**。
12. 新唯一 runner 已真实跑通 3 页：state 最终 `completed`，`pending_capture=null`，并生成 canonical messages/current.md；completed 后删除 current.md 再重跑可纯本地重建，约 0.1 秒且不触碰 QQ。
13. 文件级故障注入已实际验证：`pending current + raw 已存在` 可无捕获恢复；`pending scroll + raw 缺失` 会保留 pending/next_page_index 并停止，不会再发滚轮。
14. `python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **70/70 通过**；其中 Swift 纯测试会实际调用 raw writer 的 fsync/原子写入路径。

## 尚未验证 / 尚未实现

- 两个目标群的安全定位/切换尚未正式设计和实测；不得用盲点坐标或可能碰到输入/发送控件的方式切群。
- Apple Vision 长时间大量连续页面的性能/稳定性、首次全量历史边界、每日增量停止锚点尚未验证。
- 语音和文件继续延期；无 OCR 的纯图片/表情按 v1 文字优先目标忽略。

## 下一恢复点

直接执行 `tasks/todo.md` 顶部唯一下一步：**阶段 3：先设计并验证两个目标群的安全切换，再做首次全量；在切换验证通过前不启动双群全量。**

这里的 `dhash512` 是临时视口连续性证据，不是头像指纹。头像/昵称视觉身份辅助仍不属于 v1 去重门禁。
