# 正式代码模块边界

本文件只定义现役代码职责，避免实验代码与正式实现混在一起。

## 当前正式模块

```text
src/
  app/          # 唯一 Python runner + 内部 Swift 单步 capture
  capture/      # QQ窗口准备、SCK捕获、Vision OCR、变化检测、raw写入
  normalize/    # 单页消息重建、fragment保留、跨页保守去重/顺序转换
  store/        # message-record、canonical messages、batch/state、finalize
  inbox/        # completed/analyzed batch → current.md
```

当前已有：

- `app/run_capture.py`：唯一正式运行入口；独占 state 推进、pending/raw reconcile、normalize/finalize 编排。
- `app/capture-step.swift`：内部单步 current/scroll capture；不维护恢复状态。
- `capture/WindowPreparation.swift`：唯一同标题 AXWindow，设置/读回几何，再等待唯一同标题 SCK frame 稳定；无鼠标拖窗 fallback。
- `capture/QQHistoryCapture.swift` / `ChangeDetector.swift`：窗口级 SCK、Vision OCR、正文安全滚轮、有限 MAD 稳定门禁；MAD 仅容忍 `<=3px` SCK 尺寸漂移。
- `capture/VisualFingerprint.swift`：`dhash512` 视口连续性门禁，当前阈值 20；只用于发滚轮前确认仍停留在上一 durable raw 对应视口。
- `capture/CaptureModels.swift` / `RawPageWriter.swift`：capture-page v2 数据结构与 raw 原子写入。
- `normalize/page_reconstruct.py`：正文区、视觉行、消息头/正文、页边缘 fragment、system、媒体 OCR unknown 降级；原始单页上→下新→旧，完整候选输出旧→新。
- `normalize/assemble.py` / `overlap.py`：按同群连续 page_index 组装，fragment 不静默丢失，只删除高置信相邻页连续重叠。
- `store/message_record.py`：从正式 Schema 读取字段/枚举/const 真值并校验。
- `store/message_store.py`：canonical `messages.jsonl` 的 fsync + 原子 replace、同 batch 幂等重试与冲突拒绝。
- `store/batch_state.py`：batch-state v2 `pending_capture`、`incomplete/completed/analyzed`、全 batch 页恢复位置、群级连续锚点和原子 state replace。
- `store/finalize.py`：唯一完成顺序 `messages durable → state completed → current.md`，支持跨文件崩溃恢复。
- `inbox/builder.py`：只从 completed/analyzed 的 canonical records 生成 current.md，非法或不一致输入不得覆盖旧文件。

尚未完成：

- 两个目标群的安全定位/切换。
- 首次全量、长时间 Vision 稳定性、每日增量。

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

## 进入首次全量前的最后门禁

单群唯一 runner 与中断恢复已经通过。首次全量前只剩：

1. 两个目标群的安全定位/切换；
2. 切换后重新确认精确目标群/窗口身份；
3. 通过后才允许双群首次全量。
