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

- `app/run_capture.py`：唯一正式运行入口；承载固定页数诊断、`--full` 首次全量和 `--incremental` 每日增量，独占 state 推进、pending/raw reconcile、normalize/finalize 编排。
- `app/full_capture.py`：双群安全串行基础编排；首次全量使用双 no-change 边界和每轮页预算，不复制底层恢复状态机。
- `app/incremental_capture.py`：复用 full runner 的串行/恢复能力；新增量 batch 每群先重开历史窗口刷新快照，命中上一 completed `start_anchor` 后停止；已有 durable 页的同批次恢复不重开。
- `app/capture-step.swift`：内部单步 current/scroll capture；不维护恢复状态；滚动确认无变化时使用专用退出码交给 Python 状态机处理。
- `app/open-history.swift`：安全打开指定群的聊天记录窗口；只调用经过视觉/位置/标题多重门禁的切群适配器。
- `capture/ConversationSwitcher.swift`：主 QQ 左侧会话 OCR 唯一定位 → 选中后头部复核 → `聊天记录` tooltip 精确确认 → 历史窗口标题精确匹配；任一门禁失败即停止。
- `capture/WindowPreparation.swift`：唯一同标题 AXWindow，设置/读回几何，再等待唯一同标题 SCK frame 稳定；无鼠标拖窗 fallback。
- `capture/QQHistoryCapture.swift` / `ChangeDetector.swift`：窗口级 SCK、Vision OCR、正文安全滚轮、有限 MAD 稳定门禁；MAD 仅容忍 `<=3px` SCK 尺寸漂移。
- `capture/VisualFingerprint.swift`：`dhash512` 视口连续性门禁，当前阈值 20；只用于发滚轮前确认仍停留在上一 durable raw 对应视口。
- `capture/CaptureModels.swift` / `RawPageWriter.swift`：capture-page v2 数据结构与 raw 原子写入。
- `normalize/page_reconstruct.py`：正文区、视觉行、消息头/正文、页边缘 fragment、system、媒体 OCR unknown 降级；原始单页上→下新→旧，完整候选输出旧→新。
- `normalize/assemble.py` / `overlap.py`：按同群连续 page_index 组装，fragment 不静默丢失，只删除高置信相邻页连续重叠。
- `normalize/incremental.py`：保守匹配上一 completed 连续 anchor；命中后裁掉 anchor 及更旧记录，只重编号真正新增消息；重复 anchor 序列取最早匹配以偏向多保留。
- `store/message_record.py`：从正式 Schema 读取字段/枚举/const 真值并校验。
- `store/message_store.py`：canonical `messages.jsonl` 的 fsync + 原子 replace、同 batch 幂等重试与冲突拒绝。
- `store/batch_state.py`：batch-state v4；保留 `pending_capture` / 每群 `capture_complete`，新增 `batch_kind` 与 immutable `start_anchor`，支持 v2/v3 确定性迁移、全 batch 页恢复位置、群级连续锚点和原子 state replace。
- `store/finalize.py`：capture 继续使用 `messages durable → state completed → current.md`；incremental 额外支持 0/1 新消息、anchor 滚动和 completed 本地重建。
- `inbox/builder.py`：只从 completed/analyzed 的 canonical records 生成 current.md，非法或不一致输入不得覆盖旧文件。

尚未完成：

- `--incremental` 的第一次真实 QQ 实跑与完成后新增消息/anchor 审计。
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

## 首次全量运行门禁

首次全量的代码门禁已全部满足：两群同 batch、双 no-change 历史边界、状态冲突 UI 前硬停、已有 durable 页不重开历史窗口、20 页安全分片均有确定性测试。真实运行要求：

1. 只使用唯一 `--full` 入口与本机 `config/local.json`；
2. 每轮最多新增 20 页，在 `pending_capture=null` 的安全点结束；
3. 同一 incomplete batch 恢复时沿用原 batch_id，不创建新批次；
4. 两群都 capture_complete 后才允许 finalized current.md，并立即做完整性审计。
