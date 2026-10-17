# 正式代码模块边界

本文件只定义现役代码职责，避免实验代码与正式实现混在一起。

## 当前正式模块

```text
src/
  app/          # 唯一 Python runner + 内部 Swift 适配器
  capture/      # QQ窗口准备、日期定位、SCK捕获、Vision OCR、变化检测、raw写入
  normalize/    # 单页消息重建、fragment保留、跨页保守去重/顺序转换
  store/        # message-record、canonical messages、batch/state、finalize
  inbox/        # completed/analyzed batch → current.md
```

当前已有：

- `app/run_capture.py`：唯一正式运行入口；承载固定页数诊断、`--full` 首次全量、`--incremental` 每日增量和 `--history-date YYYY-MM-DD` 单日历史补采，独占 state 推进、pending/raw reconcile、normalize/finalize 编排；history-date 可加 `--background` detached 启动同一 runner，并用全局 PID 锁禁止并发历史任务。history-date 遇到 `pending scroll + raw 缺失` 时由同一 runner 自动重锚定，不存在第二个 recovery CLI。
- `app/swift_sources.py`：所有正式 Swift target 与 Swift 纯测试共用的唯一 source manifest；生产编译和测试不得各自手写依赖列表。
- `app/full_capture.py`：复用同一状态机编排双群首次全量和单群按日期历史补采；单日模式在首个 durable page 前调用日期定位，已有 durable 页恢复时不重新选日期；pending-scroll 自动重锚定也不重选日期/开窗。
- `app/pending_scroll_recovery.py`：只提供纯匹配门禁：dHash + 正文 OCR 同位置匹配，以及连续两张 rewind probe 对连续 durable 页的唯一序列确认；不操作 QQ、不写 state。
- `app/incremental_capture.py`：复用 full runner 的串行/恢复能力；新增量 batch 每群先重开历史窗口刷新快照，命中上一 completed `start_anchor` 后停止；已有 durable 页的同批次恢复不重开。
- `app/select-history-date.swift`：`run_capture --history-date` 的内部日期定位适配器；需要时先安全打开目标群历史窗口，再应用日期筛选并 OCR 双重复核，不维护第二套采集状态机。
- `app/capture-step.swift`：内部单步 current/scroll/rewind capture；不维护恢复状态。rewind 复用正常滚动稳定门禁，只把滚轮方向改为较新方向，probe 结果只供 Python 重锚定验证。
- `app/open-history.swift`：安全打开指定群的聊天记录窗口；只调用经过视觉/位置/标题多重门禁的切群适配器。
- `capture/ConversationSwitcher.swift`：主 QQ 左侧会话 OCR 唯一定位 → 选中后头部复核 → `聊天记录` tooltip 精确确认 → 历史窗口标题精确匹配；任一门禁失败即停止。
- `capture/WindowPreparation.swift`：唯一同标题 AXWindow，设置/读回几何，再等待唯一同标题 SCK frame 稳定；无鼠标拖窗 fallback。
- `capture/VisionTextRecognizer.swift`：唯一底层 Vision OCR owner；统一识别语言、候选抽取和 `.down` 180° bbox 映射。会话切换、日期选择、正文采集各自保留自己的业务门禁，不再各写一套 `VNRecognizeTextRequest`。
- `capture/HistoryDateSelector.swift`：日期筛选适配器。筛选按钮/日期字段/收起按钮使用窗口相对固定位置；月份箭头从 OCR 月份标题动态定位；日期格按目标年月计算行列；选中后必须同时 OCR 验证筛选字段和聊天区日期。
- `capture/QQHistoryCapture.swift` / `ChangeDetector.swift`：窗口级 SCK、共享 Vision OCR、正文安全滚轮、有限 MAD 稳定门禁；MAD 仅容忍 `<=3px` SCK 尺寸漂移。
- `capture/VisualFingerprint.swift`：`dhash512` 视口连续性门禁，当前阈值 20；只用于发滚轮前确认仍停留在上一 durable raw 对应视口。
- `capture/CaptureModels.swift` / `RawPageWriter.swift`：capture-page v2 数据结构与 raw 原子写入。
- `normalize/page_reconstruct.py`：正文区、视觉行、消息头/正文、页边缘 fragment、system、媒体 OCR unknown 降级；原始单页上→下新→旧，完整候选输出旧→新。
- `normalize/assemble.py` / `overlap.py`：按同群连续 page_index 组装，fragment 不静默丢失，只删除高置信相邻页连续重叠。
- `normalize/incremental.py`：保守匹配上一 completed 连续 anchor；命中后裁掉 anchor 及更旧记录，只重编号真正新增消息；重复 anchor 序列取最早匹配以偏向多保留。
- `store/message_record.py`：从正式 Schema 读取字段/枚举/const 真值并校验。
- `store/message_store.py`：canonical `messages.jsonl` 的 fsync + 原子 replace、同 batch 幂等重试与冲突拒绝。
- `store/batch_state.py`：batch-state v4 唯一现役 schema；保留 `pending_capture` / 每群 `capture_complete`、`batch_kind` 与 immutable `start_anchor`，提供全 batch 页恢复位置、群级连续锚点和原子 state replace；旧 schema 直接拒绝，不保留运行时迁移层。
- `store/finalize.py`：capture 继续使用 `messages durable → state completed → current.md`；incremental 额外支持 0/1 新消息、anchor 滚动和 completed 本地重建。
- `inbox/builder.py`：只从 completed/analyzed 的 canonical records 生成 current.md，非法或不一致输入不得覆盖旧文件。

尚未完成：

- 正式 GPT 分析 runner、Silver 规范化知识单元持久结构与最终页面生成流程；当前仍由 Codex/模型读取 `runtime/inbox/current.md` 人工执行分析，runtime 页面仅为可丢弃原型。
- 手动增量多次稳定后的定时化决策。

## 依赖方向

目标依赖方向：

`app → capture → normalize → store → inbox`

app 只负责编排；底层模块通过明确数据结构传递，不允许：

- capture 调用 GPT；
- normalize 操作 QQ；
- store 判断消息价值；
- inbox 修改 canonical messages；
- 任一模块直接写魔兽或其它项目。

## 安全优先级

v1 的错误成本不对称：**漏真实消息 > 多保留重复消息**。

因此：

1. 不做全局 `sender+text` 去重。
2. 不做相似昵称身份归并；头像指纹不是 v1 门禁。
3. 一侧 sender 缺失时不做破坏性去重。
4. 两条消息的最小重叠必须有额外强锚点；匿名正文锚点至少 8 个规范化字符。
5. canonical 先保留更完整正文，再比较元数据完整度与 OCR confidence。
6. 页边缘/坏头部可见文字证据不足时宁可保留重复，不能猜删。
7. 图片内 OCR 命中窄媒体门禁时降级为 unknown，不作为用户直接聊天正文送入 GPT。
8. completed state 永远不能领先于 canonical messages 的可靠持久化。

## 正式运行门禁

普通 `--full` / `--incremental` 保留 20 页默认安全分片；`--history-date` 是同一状态机上的单群整日模式，默认页预算提高到 1000，但每页 durable 顺序、双 `NO_CHANGE` 边界和失败硬停完全不变。

1. 所有正式采集只使用 `run_capture.py`；内部 Swift 适配器不得直接维护 batch/state；
2. 普通 full/incremental 到页预算时只在 `pending_capture=null` 的安全点返回 incomplete；
3. 单日历史模式第一份 durable page 前必须完成日期双重 OCR 验证，已有 durable page 的恢复不得重新选日期；
4. 同一 incomplete batch 恢复时沿用原 batch_id/runtime，不新建批次绕过恢复状态；
5. full 只有全部目标群 capture_complete 后才能 finalize；history-date 还必须在 finalization 前通过目标日期一致性审计。
