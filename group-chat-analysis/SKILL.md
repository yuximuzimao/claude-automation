# 群聊分析 SKILL.md

## DO FIRST

1. 读 `tasks/todo.md`，确认当前尚未完成事项。
2. 读 `docs/INDEX.md`，只做导航。
3. 涉及当前实现阶段、已验证能力或下一恢复点时，读 `docs/CURRENT.md`。
4. 涉及采集、恢复、分析、页面设计、跨项目候选或自动化时，先进入 `docs/OPERATING-SOP.md` 分类，再只读命中的规则 owner。
5. `docs/rules/README.md` 只用于查看 owner 目录，不承担任务分类。
6. 涉及整体数据流或模块边界时，读 `docs/ARCHITECTURE.md`。
7. 正式实现后，代码入口统一从 `src/` 的现役入口进入；在入口尚未创建前不得自行发明临时正式入口。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `README.md` | 人类快速理解项目 | 需要项目概览时 |
| `CLAUDE.md` | 稳定目标、安全边界、Session规则 | 每次进入项目 |
| `tasks/todo.md` | 唯一当前待办 | 每次进入项目 |
| `docs/INDEX.md` | 文档/数据导航 | 每次进入项目 |
| `docs/CURRENT.md` | 当前开发阶段与已验证事实 | 继续当前工作时 |
| `docs/HANDOFF.md` | 跨 agent 接续注意事项；不复制当前状态清单 | 跨 agent 接续工作时 |
| `docs/OPERATING-SOP.md` | 唯一任务分类与完整运行 SOP | 采集、恢复、分析、跨项目候选或自动化时 |
| `docs/ARCHITECTURE.md` | 稳定模块边界与数据流 | 设计/实现跨模块功能时 |
| `docs/rules/README.md` | 长期规则 owner 目录 | SOP 已完成分类、需要查看 owner 清单时 |
| `schemas/capture-page.schema.json` | 单页原始OCR捕获的数据契约 | 改capture输出/normalize输入时 |
| `schemas/message-record.schema.json` | 单条规范化消息的数据契约 | 改消息结构/存储/去重时 |
| `schemas/batch-state.schema.json` | 可恢复批次状态与页恢复契约 | 改恢复点/批次状态时 |
| `schemas/incremental-checkpoint.schema.json` | 独立历史补采结果给“下一批 incremental”提供一次性逐群 anchor override 的契约 | 改历史→增量接棒时 |
| `schemas/analysis-work-package.schema.json` | completed batch + 分析起始知识基线的冻结输入契约 | 改 daily 分析起点/恢复时 |
| `schemas/analysis-review-receipt.schema.json` | completed batch、work package 与已审分析产物的发布收据契约 | 改分析发布门禁时 |
| `schemas/analysis-result.schema.json` | immutable analysis release 的结果索引契约 | 改正式分析结果时 |
| `src/README.md` | 代码模块职责与依赖方向 | 开始实现或调整模块时 |
| `src/app/run_capture.py` | 唯一正式采集入口；固定页数诊断、`--full`、`--incremental`、`--history-date` 单日历史补采及其 `--background` 长跑启动 | 改采集/恢复 CLI 时 |
| `src/app/manage_incremental_checkpoint.py` | 从已完成独立 runtime 为下一次 incremental 创建/查看一次性逐群 checkpoint；不操作 QQ | 历史补采比主 anchor 更新时 |
| `src/app/run_analysis.py` | 已审语义产物的正式发布 runner；工单 hash、质量门禁、staging render、immutable release、原子发布、`analyzed` 推进与回滚 | 改分析发布/恢复时 |
| `src/app/serve_analysis.py` | 仅监听 `127.0.0.1` 的阅读页面入口；把“没用 / 存资料库”写入正式 reviewed semantic state | 改页面裁决持久化时 |
| `src/analysis/page_builder.py` / `page_renderer.py` | 正式 Gold/页面构建与渲染；运行数据仍来自 `runtime/` | 改页面投影时 |
| `src/app/full_capture.py` | 两群首次全量与单群按日期历史补采编排 | 改首次全量/单日历史编排时 |
| `src/app/incremental_capture.py` | 两群每日增量、强制刷新历史快照与 anchor 停止 | 改增量编排时 |
| `src/app/capture-step.swift` | 内部单步 current/scroll capture | 改 Swift 单步执行边界时 |
| `src/app/open-history.swift` | 内部安全打开目标群聊天记录窗口 | 改两群切换入口时 |
| `src/app/select-history-date.swift` | history-date 模式内部日期定位 CLI 适配器 | 改单日历史定位入口时 |
| `src/capture/ConversationSwitcher.swift` | 会话 OCR 定位、目标复核、聊天记录 tooltip/窗口门禁 | 改 QQ 群切换安全逻辑时 |
| `src/capture/HistoryDateSelector.swift` | 日期筛选、月份导航、日期格计算与双重 OCR 复核 | 改 QQ 日期筛选逻辑时 |
| `src/capture/` | AX/SCK/Vision/变化检测/dhash/raw 写入 | 改 QQ 捕获与滚动时 |
| `src/normalize/page_reconstruct.py` | 单页 bbox→消息/fragment/media unknown | 改几何重建时 |
| `src/normalize/assemble.py` | 同群多页组装与 Schema records | 改跨页组装时 |
| `src/normalize/overlap.py` | 相邻页保守去重与 capture→聊天顺序转换 | 改跨页去重/顺序时 |
| `src/normalize/incremental.py` | 上一 completed anchor 匹配、裁剪与新增消息重编号 | 改增量停止/裁剪时 |
| `src/store/batch_state.py` | 可恢复 batch/state；新 incremental 创建时可接收已验证的逐群 start-anchor override，创建后仍不可变 | 改恢复点/状态机时 |
| `src/store/incremental_checkpoint.py` | checkpoint 来源 state/messages hash、canonical tail、base batch 与一次性生效门禁 | 改历史→日常增量接棒时 |
| `src/store/message_record.py` | message-record 正式运行时校验 | 改消息持久化契约时 |
| `src/store/message_store.py` | canonical messages.jsonl 原子/幂等持久化 | 改消息库时 |
| `src/store/finalize.py` | messages→completed→current 提交/恢复 | 改完成顺序时 |
| `src/inbox/builder.py` | completed batch → current.md | 改分析输入生成时 |
| `tests/README.md` | 验证层级与测试边界 | 写/跑测试时 |

## CORE FLOWS

### 采集
`官方 QQ → 定位目标群/聊天区域 → 只读滚动 → 图像变化检测 → Apple Vision OCR → 结构化候选消息`

### 规范化与持久化
`候选消息 → 几何重建 → 相邻屏锚点去重 → 时间顺序整理 → 本地私密消息存储 → 生成 current.md`

### GPT 分析
`runtime/inbox/current.md → CodexPro读取 → GPT筛选/归类/摘要 → runtime/reports/ → 必要时用户确认后再进入其它项目`

## FAILURE PATTERNS

- 不因为 Accessibility 读不到正文就升级到注入、Hook、数据库解密或抓密钥。
- 不把截图/OCR临时结果当永久知识。
- 不用“单句文本相同”做全局去重；只能利用相邻屏连续序列/明确消息标识去重。
- 不把聊天群里的说法直接写进魔兽或其它项目的正式规则。
- 不把实时浮窗、自动回复、输入框回填等 Jev 功能带入本项目。
- 不让 GPT 决定滚动次数、重试策略、去重状态机等确定性控制逻辑。
- 不默认保存截图；诊断需要落盘时必须进入私密运行目录并及时清理。

## PATHS

| 路径 | 职责 |
| --- | --- |
| `src/` | 正式代码；模块边界见 `src/README.md` |
| `schemas/` | 版本化数据契约 |
| `docs/rules/` | 跨批次长期规则 |
| `docs/OPERATING-SOP.md` | 项目唯一任务分类与运行 SOP |
| `docs/archive/` | 历史方案/阶段归档，默认不加载 |
| `tasks/` | 当前待办（只保留 `todo.md`；临时教训不建空壳文件） |
| `tests/` | 确定性逻辑、采集适配器与回归验证 |
| `runtime/` | 私密运行数据；整个目录不进 Git |
| `runtime/inbox/current.md` | GPT 默认读取的当前分析输入 |
| `runtime/reports/` | GPT分析结果，本地私密 |
