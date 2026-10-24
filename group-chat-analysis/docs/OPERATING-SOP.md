# 群聊分析项目 SOP：任务分类与运行

用途：这是本项目唯一的任务分类与运行 SOP。先判断当前工作属于哪一类，再进入对应 owner；这里不复制 OCR、去重、存储或分析细节。

## 1. 分类表

| 分类 | 定义 | 唯一下一步 |
| --- | --- | --- |
| `ROUTINE_INCREMENTAL` | 从上一 completed anchor 之后采集新增消息。 | `rules/capture.md` + `rules/storage.md`；正式入口 `python3 -m src.app.run_capture --incremental --batch-id <id>`。 |
| `FIRST_FULL_CAPTURE` | 建立普通全量基线，按配置串行采集全部目标群到 QQ 历史边界。 | `rules/capture.md` + `rules/storage.md`；正式入口 `python3 -m src.app.run_capture --full --batch-id <id>`。 |
| `HISTORY_DAY_BACKFILL` | 对一个目标群补采某个自然日的完整可见历史。 | `rules/capture.md` + `rules/storage.md`；只用 `run_capture --history-date`，见下文。 |
| `BOUNDED_DIAGNOSTIC` | 固定少量页验证窗口、OCR、滚动或几何，不建立正式全量/增量语义。 | `rules/capture.md` + `tests/README.md`。 |
| `CAPTURE_RECOVERY` | incomplete、pending/raw 冲突、视口不确定、completed 后派生物缺失。 | `rules/storage.md`；涉及 QQ 视口再读 `rules/capture.md`。 |
| `NORMALIZATION_CONTRACT` | OCR block 如何重建消息、日期、顺序、fragment、媒体占位或跨页去重。 | `rules/normalization.md`。 |
| `STORAGE_CONTRACT` | batch state、canonical messages、current.md、原子提交或私密数据生命周期。 | `rules/storage.md`。 |
| `ANALYSIS_BATCH` | 对 completed `current.md` 做一次正式分析。 | `rules/analysis.md`。 |
| `ANALYSIS_DESIGN` | 修改分类、价值、可信度、页面、长期追踪、黑话等分析契约。 | `rules/analysis.md`。 |
| `PROMOTION` | 把群聊候选交给魔兽或其它项目核验/保存。 | `rules/analysis.md`；用户确认后进入目标项目自己的 SKILL/SOP。 |
| `AUTOMATION` | 定时采集、定时分析、失败告警或无人值守编排。 | `rules/capture.md` + `rules/storage.md` + `tests/README.md`。 |
| `PRIVACY_OR_SAFETY` | 权限、QQ 操作范围、模型暴露、Git 私密数据或禁止技术路线。 | `rules/privacy-and-safety.md`。 |
| `ARCHITECTURE_MIGRATION` | 模块边界、Schema owner 或唯一入口需要改变。 | `ARCHITECTURE.md`，单独制定迁移计划。 |

一条请求包含多类工作时先拆开；采集/数据完整性优先于依赖它的分析。分类后不要继续从本 SOP 猜实现细节。

## 2. 唯一正式采集入口

所有正式采集都从：

```bash
python3 -m src.app.run_capture ...
```

进入。`capture-step.swift`、`open-history.swift`、`select-history-date.swift` 都只是该入口内部调用的适配器，不维护第二套 batch/state 流程。

普通 `--full` / `--incremental` 默认每轮最多新增 20 页；达到预算只在 raw 已 durable、`pending_capture=null` 的安全点返回 incomplete。继续时使用同一 batch id。

## 3. 单日历史补采

当前从入群日期向前补历史时，每个自然日只运行：

```bash
python3 -m src.app.run_capture \
  --history-date YYYY-MM-DD \
  --group-key wow-infinite-time
```

需要像长跑 check 一样启动后立即返回时，加 `--background`。它只负责 detached 启动同一个正式 runner，不建立第二套采集逻辑；全局 PID 锁保证任意时刻只能有一个历史后台任务，避免多个日期同时操作 QQ。

`--history-date` 自带以下约束：

1. 自动进入单群 full-capture 语义，不需要另外写 `--full`；
2. 默认 batch id 为 `history-YYYYMMDD-full`；
3. 默认 runtime 为 `runtime/history-days/YYYY-MM-DD/`，和日常增量/首次全量分开；
4. 默认允许单次新增最多 1000 页，适合受监督的整日长跑；每一页仍严格执行 pending → capture side effect → raw durable → record_page，任何安全门禁失败立即停；
5. 第一页前由内部日期适配器安全打开/抬起目标历史窗口，选择目标日期，并同时 OCR 验证筛选字段和聊天区日期；
6. 已有 durable page 的 incomplete batch 恢复时不重新选日期、不重开窗口，避免把已向历史推进的视口重置；
7. 仍以连续两次独立 `NO_CHANGE` 确认 QQ 当天当前可取的历史边界；
8. finalization 前必须确认 canonical 中已恢复出的 `message_date` / 绝对时间没有落到目标日期之外，否则拒绝 completed。

一天是否完整不要求第一条必须恰好 `00:00`、最后一条必须恰好 `23:59`；当天凌晨或午夜附近本来可能没有发言。完整的机器证据是：目标日期选择已验证、页状态连续、连续两次 `NO_CHANGE`、finalization 日期审计通过、state 为 completed 且 `pending_capture=null`。

补历史时按日期一天一天向入群日推进；每一天都只由日期定位、durable raw、双 `NO_CHANGE` 和 finalization 日期审计共同确定完成状态。

## 4. 日常增量

新批次运行：

```bash
python3 -m src.app.run_capture --incremental --batch-id <batch_id>
```

每个新 incremental batch 必须重新安全打开目标群历史窗口刷新 QQ 快照；已有 durable 页的同一未完成 batch 恢复时不重开。命中上一 completed 的连续 `start_anchor` 后停止并只提交 anchor 之后的新消息。

如果某一群经过**独立 history-date 补采**已经拥有比主运行链更新、且已 completed 的可靠尾部 anchor，禁止手改旧 main batch。先执行 `python3 -m src.app.manage_incremental_checkpoint --source-runtime <独立runtime> --group-key <group>` 创建一次性 checkpoint。它必须与当前上一 main completed batch id 精确绑定，并在下一批 incremental 开始前复核来源 state/messages hash、completed anchor 与 canonical tail；任一不一致都在打开 QQ 前硬停。checkpoint 只覆盖指定群的新 batch `start_anchor`，其他群仍沿用上一 main completed anchor；新批次一旦创建，start_anchor 继续按原规则不可变。上一 main batch 已变化时旧 checkpoint 自动失效。

输出 `status=incomplete` 时继续同一命令；输出 `status=completed` 后 canonical messages、state 和 `runtime/inbox/current.md` 才可进入分析。

## 5. 批次分析与跨项目

completed 后进入 `rules/analysis.md`。日常分析只读 `runtime/inbox/current.md`，不从 raw OCR 重猜消息；报告/页面保存到 `runtime/reports/`。群聊内容只生成跨项目候选，用户确认后再进入目标项目独立核验。

分析已经拆成“语义生产”和“确定性发布”两层。语义判断仍由 GPT/Codex 按 analysis owner 完成，任何相似度/召回 proposal 都不能自动晋升；确定性状态机统一从 `python3 -m src.app.run_analysis` 进入。一个 completed batch 先用 `--prepare-work` 冻结 `current.md + canonical + 当前 Question Registry/Silver/已阅/dossier` 起点 hash，语义审阅完成后用 `--prepare-review` 生成 draft receipt 并由审阅者显式改成 `reviewed_analysis_ready`，最后才允许正式发布。发布顺序固定为质量门禁 → staging render → immutable release → 原子 current 指针 → `mark_analyzed()`；任一步失败都不得重新采集或提前推进 analyzed。

## 6. 恢复原则

- incomplete：继续原 batch，不删除 runtime、不另起 batch 猜测恢复。
- `pending current + raw 缺失`：可重试当前页，因为没有滚动副作用。
- pending 对应 raw 已 durable：校验后晋升，不重复捕获。
- 明确的 pre-scroll rejection：允许清 pending 后重试。
- `pending scroll + raw 缺失`：普通 full/incremental 仍停止且不再次滚动。history-date 由同一 runner 进入自动 `CAPTURE_RECOVERY`，不把故障现场屏直接当目标页。
- history-date `CAPTURE_RECOVERY`：先截当前屏作 probe，再向较新方向最多回退 6 次；只有连续两张 probe **唯一**匹配连续两个已 durable 页时才认为重新进入已知区域。随后按 durable 页号逐页向历史方向回放，每一步都必须重新匹配对应 durable raw；最终再次确认回到最后 durable 页后，才允许清原 pending，让普通 runner 从最后 durable 页重新滚动并重新读取失败目标页。
- 任一 probe 无法形成唯一连续锚点、回放页不匹配、窗口/滚动门禁失败或 OCR 无法形成足够证据时，保持 incomplete 并停止；不得用“当前看起来像下一屏”、单条 OCR、单次 dHash 或时间文本猜测晋升。
- completed 但 `current.md` 缺失：原模式重跑，必须纯本地重建，不触碰 QQ。
- 分析失败：只重跑分析，不修改 completed canonical，不重新采集。

## 7. 当前仍未自动化

- 每日新增消息的语义生产编排仍需在真实 incremental batch 上继续验证：Atomic Claim → stable Question Registry assignment/bootstrap → Silver routing/authoring/publication → dossier `silent_support / visible_update` → reviewed receipt；确定性发布 runner、正式结果结构、页面裁决持久化已经建立；
- 每日无人值守调度。

这些只以 `tasks/todo.md` 作为未完成事项真源。
