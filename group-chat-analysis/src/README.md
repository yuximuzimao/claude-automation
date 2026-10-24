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
  analysis/     # Silver/已阅/dossier/质量门禁/正式页面与 release 契约
```

当前已有：

- `app/run_capture.py`：唯一正式运行入口；承载固定页数诊断、`--full` 首次全量、`--incremental` 每日增量和 `--history-date YYYY-MM-DD` 单日历史补采，独占 state 推进、pending/raw reconcile、normalize/finalize 编排；history-date 可加 `--background` detached 启动同一 runner，并用全局 PID 锁禁止并发历史任务。history-date 遇到 `pending scroll + raw 缺失` 时由同一 runner 自动重锚定，不存在第二个 recovery CLI。
- `app/swift_sources.py`：所有正式 Swift target 与 Swift 纯测试共用的唯一 source manifest；生产编译和测试不得各自手写依赖列表。
- `app/full_capture.py`：复用同一状态机编排双群首次全量和单群按日期历史补采；单日模式在首个 durable page 前调用日期定位，已有 durable 页恢复时不重新选日期；pending-scroll 自动重锚定也不重选日期/开窗。
- `app/pending_scroll_recovery.py`：只提供纯匹配门禁：dHash + 正文 OCR 同位置匹配，以及连续两张 rewind probe 对连续 durable 页的唯一序列确认；不操作 QQ、不写 state。
- `app/incremental_capture.py`：复用 full runner 的串行/恢复能力；新增量 batch 每群先重开历史窗口刷新快照，命中上一 completed `start_anchor` 后停止；已有 durable 页的同批次恢复不重开。若存在与上一 completed batch 精确绑定的一次性 checkpoint，会在任何 QQ UI 动作前先校验来源 state/messages hash 与 canonical tail，并只对指定群覆盖**新 batch 创建时**的 start_anchor。
- `app/manage_incremental_checkpoint.py`：独立 history runtime 已推进到比主运行链更新边界时，创建/查看下一批 incremental 的一次性逐群 checkpoint；只写本地 runtime，不触碰 QQ，也不改写旧 completed state。
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
- `store/batch_state.py`：batch-state v4 唯一现役 schema；保留 `pending_capture` / 每群 `capture_complete`、`batch_kind` 与 immutable `start_anchor`，提供全 batch 页恢复位置、群级连续锚点和原子 state replace；新 incremental **创建时**可接收已验证逐群 start-anchor override，但一旦进入 incomplete 就不可改；旧 schema 直接拒绝，不保留运行时迁移层。
- `store/incremental_checkpoint.py`：一次性逐群 checkpoint owner；绑定上一主 completed batch id、独立来源 runtime/state/messages hash 和来源 canonical tail，来源变化即拒绝，上一主 batch 改变后旧 checkpoint 自动失效。
- `store/finalize.py`：capture 继续使用 `messages durable → state completed → current.md`；incremental 额外支持 0/1 新消息、anchor 滚动和 completed 本地重建。
- `inbox/builder.py`：只从 completed/analyzed 的 canonical records 生成 current.md，非法或不一致输入不得覆盖旧文件。
- `app/run_analysis.py`：**正式分析发布 runner**。语义审阅仍由模型/人工完成，但发布状态机完全确定性：review receipt 精确绑定 completed batch、`current.md`、canonical batch 和分析产物 hash；随后质量门禁 → staging render → immutable release → 原子 current 指针 → 最后 `mark_analyzed()`。失败只留 run manifest，不碰 canonical；重复执行幂等；发布指针已切但状态写失败可向前恢复；历史 release 可显式回滚。
- `analysis/analysis_release.py`：review receipt / release hash、原子 JSON、release current 指针与回滚完整性门禁。
- `analysis/page_builder.py` / `page_renderer.py`：正式 Gold/阅读页面构建 owner；页面代码不再依赖 Git 忽略的 runtime 脚本。
- `analysis/review_decision_store.py`：用户“没用 / 存资料库”唯一持久写入逻辑；只允许正式 queue Silver，写 reviewed semantic decisions/state，不修改 Silver 事实层。
- `app/serve_analysis.py`：仅监听 `127.0.0.1` 的正式本机阅读入口；同源 + CSRF 门禁持久化用户裁决，并在写入后重建 review 页面。

尚未完成：

- 每日新增消息的**语义生产判断**仍由 Codex/模型执行，但 daily work package 与发布血缘已正式化：`run_analysis --prepare-work` 冻结 completed batch 与当前 Question Registry/Silver/已阅/dossier 基线，完成 incremental Question assignment/bootstrap、Silver routing/authoring、dossier `silent_support / visible_update` 后再生成 reviewed receipt。历史 `question-cluster-registry-v71.json` 已只作为 bootstrap 快照；现役默认入口统一为 `question-cluster-registry-current.json`，由 `question_registry_store.py` 做单调发布和 hash 快照。仍待验证的是**真实新 incremental batch 上的语义 delta 编排**，不是 work package/发布状态机本身。
- 真实新 incremental batch 上的完整“采集 → 语义分析 → reviewed receipt → 正式发布 → 页面终审”多次实测。
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
