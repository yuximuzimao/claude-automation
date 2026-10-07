# 群聊分析交接

## 当前完成

阶段 2 已收口为单一正式链：

- `src/app/run_capture.py`：唯一正式运行入口，独占 batch state 推进与恢复判断。
- `src/app/capture-step.swift`：内部单步执行器，只负责 current/scroll 一次捕获，不维护恢复状态。
- `src/capture/`：AX/SCK/Vision、正文区、安全滚轮、MAD、`dhash512` 视口连续性门禁、raw 原子写入。
- `src/normalize/`：bbox 重建、fragment 保留、媒体 OCR unknown、相邻页保守去重与顺序转换。
- `src/store/`：batch-state v2 `pending_capture`、canonical messages、finalize 崩溃恢复。
- `src/inbox/`：completed/analyzed → current.md。

旧批量 Swift CLI 已删除，避免第二入口；旧 capture worktree 已不再是运行依赖。

阶段 3 的安全切群也已实机往返验证：`src/capture/ConversationSwitcher.swift` + `src/app/open-history.swift` 只在“左侧会话 OCR 唯一命中 → 选中后头部复核 → tooltip 精确为 `聊天记录` → 历史窗口标题精确匹配”全部成立时执行。两个目标历史窗口标题已确认，真实成员数只作为当次额外证据，不进入长期身份配置。

## 当前关键契约

- 错误成本：**漏真实消息 > 多保留重复消息**。
- 状态推进顺序固定为 **pending intent → Swift 单步 → raw durable → record_page**。
- `pending current + raw 缺失` 可安全重试；`pending scroll + raw 缺失` 必须硬停，禁止猜当前位置再次滚动。
- 没有 matching pending，`record_page()` 不能推进；没有 pending 却出现 next raw 也硬停。
- 滚动前必须用上一份 durable raw 的 `dhash512` 验证当前视口。阈值 `<=20`；该指纹只验证视口连续性，不参与昵称/消息身份去重。
- MAD 只容忍 `<=3px` SCK 尺寸漂移并比较共同尺寸；更大漂移停止。
- QQ 单页视觉上→下是新→旧；Normalize 最终输出旧→新。
- 相似昵称不归并；一侧 sender 缺失不做破坏性去重；证据不足宁可重复。
- `messages.jsonl` 先 durable，之后才能 completed；current.md 是可重建派生物。

## 验证

`python3 -m unittest discover -s tests -p 'test_*.py'` 当前 **71/71 通过**。

真实验证包括：
- 唯一 runner 实跑 3 页并 completed；
- 同一未滚动视口 6 次 dHash 校准：`18,0,0,0,0`；三个不同页距离 `46/49/31`，因此阈值收紧为 20；
- `pending + raw 已存在` 可不触发 capture 直接恢复；
- `pending scroll + raw 缺失` 保留状态并停止，不再次滚动；
- completed 后删除 current.md 可纯本地重建，不触碰 QQ；
- MAD 回弹、SCK 小尺寸漂移、bbox/assembly、message store/finalize 均有确定性回归；
- 两个目标群正式 `open-history` 往返成功，系统窗口标题分别精确匹配目标；
- 正文消息包含“表情”时不再误截工具栏，真实页 content_region 高度由错误约 `0.192` 恢复到约 `0.852`。

## 下一步

按 `tasks/todo.md` 顶部继续阶段 3：把两个已验证目标群串进同一可恢复 batch，并建立首次全量的可验证历史边界；两项通过前不要启动真实双群全量。
