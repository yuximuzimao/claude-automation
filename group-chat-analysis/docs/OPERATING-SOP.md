# 群聊分析项目 SOP：任务分类与完整运行

用途：这是本项目唯一的运行与任务分类 SOP。它回答三件事：当前工作属于哪一类、下一份唯一应该读取的 owner 是什么、一个正常批次怎样从 QQ 走到分析结果。

本文件不复制 OCR 算法、状态机细节、页面规则或隐私条款。分类完成后，具体操作、失败边界和数据契约只以对应 owner 为准。

## 0. 先拆任务，再分类

一条输入可能同时包含多类工作，必须拆开处理。例如：

- “抓今天新增消息” → `ROUTINE_INCREMENTAL`
- “这条 DK 经验应该排在前面” → `ANALYSIS_DESIGN`
- “把确认后的任务机制写到魔兽项目” → `PROMOTION`
- “滚动后状态不确定” → `CAPTURE_RECOVERY`

每一项只进入一个主分类。先处理上游采集/数据完整性，再处理依赖它的分析与跨项目候选；不能用修改分析文案掩盖采集或规范化问题。

## 1. 分类表

| 分类 | 只用于区分的定义 | 唯一下一步 |
| --- | --- | --- |
| `ROUTINE_INCREMENTAL` | 从上一 completed anchor 之后采集新增消息，生成本批 `current.md`。 | `rules/capture.md` 的“每日增量”与 `rules/storage.md`；正式入口只用 `src/app/run_capture.py --incremental`。 |
| `FIRST_FULL_CAPTURE` | 首次建立历史基线，或用户明确批准重新补采大段历史。 | `rules/capture.md` 的“首次全量”与 `rules/storage.md`；正式入口只用 `src/app/run_capture.py --full`。 |
| `BOUNDED_DIAGNOSTIC` | 固定群、固定少量页验证 QQ UI、OCR、滚动或几何，不建立正式全量/增量语义。 | `rules/capture.md` 与 `tests/README.md` 的本地适配器/端到端层。 |
| `CAPTURE_RECOVERY` | 现有 batch incomplete、pending/raw 冲突、视口不确定、completed 后 `current.md` 缺失。 | `rules/storage.md` 的恢复语义；涉及 QQ 视口再读 `rules/capture.md`。 |
| `NORMALIZATION_CONTRACT` | 修改 OCR block 如何组成消息、顺序、fragment、媒体占位、跨页去重或 anchor 匹配。 | `rules/normalization.md`。 |
| `STORAGE_CONTRACT` | 修改 runtime 生命周期、batch state、canonical messages、current.md、原子提交或隐私数据落点。 | `rules/storage.md`；权限或敏感数据边界再读 `rules/privacy-and-safety.md`。 |
| `ANALYSIS_BATCH` | 对一个 completed `current.md` 做话题归组、事实/原文展示、价值排序和报告生成。 | `rules/analysis.md` 的“批次分析 SOP”。 |
| `ANALYSIS_DESIGN` | 修改分类、价值等级、可信度、长期跟踪、攻略知识、黑话或页面 v2 展示契约。 | `rules/analysis.md`。 |
| `PROMOTION` | 把群聊候选交给 `wow-quest-route` 或其它项目核验/保存。 | 先读 `rules/analysis.md` 的跨项目边界；用户确认后退出本项目，进入目标项目自己的 SKILL/SOP。 |
| `AUTOMATION` | 定时运行、失败告警或无人值守编排。 | 先读 `rules/capture.md`、`rules/storage.md` 和 `tests/README.md`；手动增量未稳定前不得启用。 |
| `PRIVACY_OR_SAFETY` | 权限、QQ 操作范围、模型数据暴露、Git 私密数据或禁止技术路线。 | `rules/privacy-and-safety.md`。 |
| `ARCHITECTURE_MIGRATION` | capture/normalize/store/inbox/analyze 边界、Schema owner 或唯一入口需要改变。 | `ARCHITECTURE.md`，并为当次迁移单独制定计划；历史只从 `archive/` 定向考古。 |

分类完成后，不继续从本 SOP 猜具体实现；进入对应 owner 执行。

## 2. 日常完整流程

当前稳定的日常主流程是：

`增量采集 → 自动规范化/持久化 → current.md → 人工触发 GPT 分析 → 本地报告/页面 → 用户确认后的跨项目候选`

### 2.1 增量采集

为本轮选择新的 batch id，运行唯一正式入口：

```bash
python3 -m src.app.run_capture --incremental --batch-id <batch_id>
```

- 命令输出 `status=incomplete`：使用**同一个 batch id、同一条命令**继续；不得新建 batch 绕过恢复状态。
- 命令输出 `status=completed`：canonical messages、completed state 和 `runtime/inbox/current.md` 已按正式顺序生成，可以进入分析。
- 命令输出 `ERROR`：停止，不自动重复 UI 动作；按 `CAPTURE_RECOVERY` 分类检查 owner。

默认每次最多新增 20 页，所以一个真实增量可能需要多次运行同一命令。这里的重复调用是继续同一持久化 batch，不是对失败 UI 动作做盲目重试。

### 2.2 批次分析

采集 completed 后按 `ANALYSIS_BATCH` 进入 `rules/analysis.md`：

1. 只读取 `runtime/inbox/current.md`，不从 raw OCR 重新猜消息；
2. 先完整归组有意义话题，再生成事实、原文和 AI 扩展分析；
3. 价值与可信度分别判断，生成本期总览和各长期视图所需结果；
4. 报告和页面只保存到 `runtime/reports/`，不提交 Git；
5. 需要进入其它项目的信息只标为候选，等待用户确认。

当前分析阶段尚无正式 CLI，也没有自动调用模型的 worker。现阶段由 Codex/模型按 owner 规则读取 `current.md` 并生成报告；在正式分析 runner 建立前，不手改 batch state 假装完成自动化。

### 2.3 跨项目候选

群聊项目内完成的只是候选整理：

`群聊原文与分析 → 候选信息 → 用户确认 → 目标项目独立核验 → 目标项目保存`

用户未确认时流程停在本项目。确认后，新的工作从目标项目 `SKILL.md` 开始，不把本项目规则带过去代替目标项目 owner。

## 3. 首次全量流程

只有建立初始基线，或用户明确批准重新补采历史时才运行：

```bash
python3 -m src.app.run_capture --full --batch-id <batch_id>
```

`status=incomplete` 时继续使用同一个 batch id，直到 completed 或明确失败。完成后必须做页连续性、消息 sequence、record_id、unknown group、逐页重建和尾部 anchor 审计，再决定是否进入大规模历史分析。

普通日常更新不得使用 `--full`。历史覆盖策略未决定前，不因为页面设计需要而重新抓取历史。

## 4. 恢复与停止

- incomplete batch：继续原 batch，不删除 runtime、不另起 batch 猜测恢复。
- completed 但 `current.md` 缺失：使用原 batch id 和对应原模式重新运行，正式 runner 应从本地 durable 数据重建，不触碰 QQ。
- `pending scroll + raw 缺失`：视口副作用不确定，必须停止，不能再次滚动。
- 目标群、窗口标题、正文区域或配置集合不一致：在任何进一步 QQ 动作前停止。
- 分析失败：completed messages 保持不变，可以重新分析；不得反向修改 canonical messages。
- 跨项目核验失败：候选留在本项目并标明状态，不把它提升为目标项目事实。

## 5. 当前未自动化的环节

- GPT 批次分析仍是人工触发，没有正式分析 runner；
- 页面 v2 结果结构和生成流程尚待实现；
- 报告完成后的 `analyzed` 状态没有正式用户入口，不手工拼状态文件；
- 手动增量还需多批稳定验证，定时化尚未批准。

这些属于 `tasks/todo.md` 中的未完成工作，不能在 SOP 中写成已经存在的能力。
