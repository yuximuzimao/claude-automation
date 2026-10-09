# CURRENT — 群聊分析

这是项目当前开发状态的唯一真值。

## 当前阶段

**阶段 0/1/2/3 已完成。真实首次全量已经完成并通过程序性完整性审计；阶段 5 的每日增量已实现并通过确定性/真实 baseline 离线验证，下一步只剩一次真实增量实跑。**

正式入口仍唯一是 `python3 -m src.app.run_capture`。固定页数诊断继续使用原参数；首次全量使用 `--full --batch-id <id>`；每日增量使用 `--incremental --batch-id <id>`，两种双群模式都从本机 `config/local.json` 读取目标群与窗口参数。Python runner 独占 batch state 推进；Swift `capture-step` 只执行单次 current/scroll 副作用，`open-history` 只作为内部安全切群执行器。

## 当前已验证事实

1. 官方 QQ 的“聊天记录”独立窗口是正式采集对象；Accessibility 正文树不足以作为正文读取通道。
2. `src/capture/` 使用 ScreenCaptureKit + Apple Vision。窗口准备采用唯一同标题 `AXWindow` → 设置/读回 `AXPosition/AXSize` → 等待唯一同标题 SCK frame 稳定；不使用鼠标拖窗口 fallback。
3. SCK 偶发 1–3px 捕获尺寸漂移已实测。MAD 只容忍 `<=3px` 并把两帧渲染到共同尺寸比较；更大漂移硬停。最终帧若回到 baseline，也不得判为新页。
4. `capture-page.schema.json` 已升级为 v2：除原始 OCR 外保存私密 `dhash512` 视口指纹。该指纹**只**用于滚动前验证当前视口仍是上一份 durable raw 对应页面，不参与昵称/消息身份或去重。
5. 512-bit dHash 当前门槛为 Hamming distance `<=20`。同一未滚动视口连续 6 次实测为 `18,0,0,0,0`；三个不同真实页距离为 `46/49/31`。超过 20 时在发滚轮前停止。
6. `batch-state.schema.json` 已升级为 v4：保留 `pending_capture` / 每群 `capture_complete`，新增 `batch_kind=capture|incremental` 与不可变 `start_anchor`。旧 v2/v3 只确定性迁移为 `capture`；incremental 开始时从上一 completed 的尾部 anchor 复制 `start_anchor`。唯一页提交顺序仍是 **pending intent → Swift 单步副作用 → raw durable → record_page**。
7. `pending current + raw 缺失` 可安全重试；`pending + raw 已落盘` 直接晋升 durable raw，不重复捕获；`pending scroll + 目标 raw 缺失` 视口位置不确定，必须硬停，禁止再次滚动；没有 pending 却凭空出现 next raw 也硬停。
8. 当前 QQ 单页视觉从上到下是**新→旧**；`reconstruct_page()` 完成视觉判断后把完整候选反转为**旧→新**。页边缘 fragment 不静默丢弃，证据不足宁可保留重复。
9. 嵌入图片 OCR 命中窄几何门禁时降级为 `unknown / 非文字内容（图片/表情等，未解析）`；图片内文字不进入 GPT 输入。无 OCR 的纯图片/表情、语音、文件继续不阻塞 v1。
10. 相邻页去重仍以“漏真实消息 > 多保留重复消息”为错误成本：相似昵称不归并，一侧 sender 缺失不破坏性去重，`message_type`/双方已识别时间必须兼容，canonical 先保正文完整度。
11. `messages.jsonl` 继续使用 Schema 校验、`fsync` + 原子 replace、同 batch 幂等恢复；完成顺序固定为 **messages durable → state completed → current.md**。
12. 新唯一 runner 已真实跑通 3 页：state 最终 `completed`，`pending_capture=null`，并生成 canonical messages/current.md；completed 后删除 current.md 再重跑可纯本地重建，约 0.1 秒且不触碰 QQ。
13. 文件级故障注入已实际验证：`pending current + raw 已存在` 可无捕获恢复；`pending scroll + raw 缺失` 会保留 pending/next_page_index 并停止，不会再发滚轮。
14. 正式 `open-history` 已实机验证两个目标群往返：会话列表先用 OCR 找唯一目标行并限制在左侧安全区；选中后重新核对聊天头部；只有 hover 后局部 OCR 精确得到 `聊天记录` 才点击历史按钮；最后要求历史窗口标题精确匹配目标群。任何一步不满足都停止。
15. 两个历史窗口精确标题已确认：`魔兽世界无限+时光服玩家群`、`魔兽世界2无限国服备战总群`。实测切换时成员数 1815/1777 只作为额外证据，不写成长期身份条件。
16. 重新打开历史窗口时暴露了正文区潜伏 bug：聊天正文 `坐下）表情` 曾被误当过滤工具栏，导致 content_region 高度从正常约 `0.852` 截成 `0.192`。现已改为“同一水平带至少两个过滤控件共同出现”才可定义工具栏，并完成真实页回归。
17. 两群同 batch 编排已完成：`page_index` 继续按整个 batch 全局递增；第一群结束后 batch 仍保持 incomplete，只有第二群也 `capture_complete` 后才统一 normalize / messages durable / state completed / current.md。
18. 首次全量历史边界采用连续两次独立 `NO_CHANGE`：每次滚动前都先用上一 durable 页的 dHash 验证视口、重新定位正文锚点、QQ 必须前台且历史窗口标题唯一；任一次出现变化都会清零 no-change 连续计数。
19. 首次全量默认每次最多新增 20 页。达到分片预算只在 raw 已 durable、`pending_capture=null` 的安全点返回 incomplete，不切下一个群、不标记 capture_complete；恢复已有 durable 页时禁止重新打开历史窗口，避免把视口重置到最新。
20. 真实首次全量 `first-full-20261008` 已完成：第一群 `page 0–890` 共 **891 页 / 5700 条 canonical messages**；第二群 `page 891–1146` 共 **256 页 / 1593 条 canonical messages**；合计 **1147 页 / 7293 条**。
21. 低运动滚屏模糊区门禁已继续用真实增量校准：`MAD 2.00–2.50` 只有最终相邻帧稳定，且新旧正文 OCR 各至少 8 条、Jaccard `<=0.85` 时才保守保存为新/部分推进页；真实增量 page 33 观测到 Jaccard `0.706` 的部分推进。高重叠页宁可多保留，由后续相邻页去重处理，避免再次滚动跳过消息。
22. 1147 页中唯一异常页 `wow-infinite-2/page-001038.json` 是“日期 + 3 个消息头、无正文 OCR”；现已改为 header-only fragment fallback，不生成伪正文。修复后真实 **1147/1147 页逐页 reconstruct bad=0**。
23. 程序性完整性审计通过：全局 `page_index 0–1146` 连续无缺页/重复；两个群 canonical sequence 各自从 0 连续；无未知 group、无重复 `record_id`；state 中两个连续消息 anchor 均准确对应各群 canonical 尾部。
24. 每日增量已实现：新的 incremental batch 每群首次进入时必须重新打开“聊天记录”刷新快照；同一未完成 batch 已有 durable raw 时恢复不重开。每抓完 durable 页就检查上一 completed 的连续 `start_anchor`；命中后只提交 anchor 之后的新消息。0/1 条新消息、分片恢复、completed 本地重建、历史边界先于 anchor 的硬失败均有回归。
25. 真实 baseline 离线验证通过：第一次全量的两组 anchor 都只在各自 canonical 最尾部命中（5700/5700、1593/1593），裁剪后均为 0；真实 v3 state 副本可确定性升级 v4，并把两组真实尾部 anchor 精确复制到新 incremental `start_anchor`。
26. `python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **96/96 通过**。

27. 第一次真实增量 `incremental-20261009-001` 已完成：共 95 个 raw pages，最终裁剪得到 **611 条新增 canonical messages**（第一群 609 / 第二群 2）。两群旧 `start_anchor` 均未重复入库，sequence 连续、record_id 无重复，新 completed anchor 正确前滚。
28. 真实增量期间继续校准两类边界：低运动“部分推进页”允许在 `MAD 2.00–2.50 + 最终帧稳定 + OCR Jaccard <=0.85` 时保守保存；消息头高度门槛从 `0.95×body` 调整为 `1.05×body`，真实 page 93 的 `00:49/00:47` 头部因此恢复正确重建。全套测试当前 **96/96 通过**。
29. 第一版报告已按当前魔兽项目重排为 v2：`runtime/reports/2026-10-09-incremental-001-v2.md`；同时生成简洁页面 v1：`runtime/reports/2026-10-09-intel-v1.html`。一级结构固定试行为“重点发现 / 当前项目 / 新增黑话 / 全部有效信息”，排序只影响阅读顺序、不删除低优先级有效信息；黑话附最小必要原文。

## 尚未验证 / 尚未实现

- 日报格式仍需结合用户实际阅读体验继续收敛；黑话/简称必须优先结合群聊上下文，遇到不确定或时效性强的词再查公开资料核对。
- 更大单日上下文的分块分析策略尚未实测；不能用关键词预筛替代完整读取。
- 手动增量还需要多跑几次稳定后，才考虑每天一次的自动调度。
- 语音和文件继续延期；无 OCR 的纯图片/表情按 v1 文字优先目标忽略。

## 下一恢复点

直接执行 `tasks/todo.md` 顶部唯一下一步：**阶段 4：评审“项目导向报告 v2 + 简洁页面 v1”，先讨论信息排序、标签数量和页面阅读方式；确认展示结构后，再做7293条历史基线分块语义分析。**

这里的 `dhash512` 是临时视口连续性证据，不是头像指纹。头像/昵称视觉身份辅助仍不属于 v1 去重门禁。
