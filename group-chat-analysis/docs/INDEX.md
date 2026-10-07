# 群聊分析文档索引

用途：只负责导航，不承载全部规则正文。

## 当前状态与整体设计

| 需求 | 入口 |
| --- | --- |
| 当前做到哪里、已验证什么、下一步是什么 | `CURRENT.md` |
| Codex/Claude 当前交接与已完成验证 | `HANDOFF.md` |
| 理解整体模块/data flow | `ARCHITECTURE.md` |
| 当前待办 | `../tasks/todo.md` |

## 永久规则

总入口：`rules/README.md`

| 主题 | 文档 |
| --- | --- |
| QQ窗口定位、滚动、截图/窗口捕获、Apple Vision OCR | `rules/capture.md` |
| 运行时数据、文件生命周期、GPT稳定分析入口 | `rules/storage.md` |
| OCR结果重建消息、排序、跨屏去重 | `rules/normalization.md` |
| GPT筛选、摘要、输出、跨项目写入边界 | `rules/analysis.md` |
| 权限、隐私、安全禁止路径 | `rules/privacy-and-safety.md` |

## 数据契约

- `../schemas/capture-page.schema.json`：单页窗口级捕获 + Apple Vision OCR 的原始输出；页级元数据与 OCR blocks 分离。
- `../schemas/message-record.schema.json`：Normalize 后的单条规范化消息。
- `../schemas/batch-state.schema.json`：可恢复批次的状态、页恢复位置和每群已完成连续锚点；不包含截图、头像指纹或昵称别名。

## 代码与测试

- `../src/README.md`：正式代码模块边界、依赖方向与当前门禁。
- `../src/app/run_capture.py`：唯一正式运行入口与 pending/raw 恢复编排。
- `../src/app/capture-step.swift`：内部单步 current/scroll capture。
- `../src/app/open-history.swift`：安全打开目标群聊天记录窗口。
- `../src/capture/ConversationSwitcher.swift`：会话 OCR 定位、目标复核、`聊天记录` tooltip 与历史窗口标题门禁。
- `../src/capture/`：AX/SCK/Vision、正文区、滚动/MAD、dhash 视口门禁与 raw 原子写入。
- `../src/normalize/page_reconstruct.py`：单页 bbox→视觉行→消息/fragment/media unknown。
- `../src/normalize/assemble.py`：同群连续 capture pages → Schema message records。
- `../src/normalize/overlap.py`：相邻页保守去重与 capture 页方向转换。
- `../src/store/batch_state.py`：可恢复 batch/state。
- `../src/store/message_record.py`：message-record 正式运行时校验。
- `../src/store/message_store.py`：canonical messages.jsonl 原子/幂等持久化。
- `../src/store/finalize.py`：messages→completed→current 提交与恢复。
- `../src/inbox/builder.py`：completed batch 的 current.md builder。
- `../tests/README.md`：验证策略。
- 现役代码入口与实现阶段以 `../src/README.md` 和 `CURRENT.md` 为准。

## 运行时私密数据

整个 `../runtime/` 被 Git 忽略，并且默认不出现在项目历史中。

规划路径：

- `runtime/raw/`：原始 OCR/屏幕批次的结构化中间记录；用于纠错。
- `runtime/messages/`：规范化、去重后的本地消息库。
- `runtime/inbox/current.md`：GPT/CodexPro 唯一默认分析入口；保存“本批待分析的全部文字消息”。
- `runtime/reports/`：GPT分析结果。
- `runtime/state/`：采集锚点、上次完成位置、批次状态。
- `runtime/diagnostics/`：只有显式诊断时才允许临时落盘截图；完成后清理。

## 历史

- `archive/README.md`：历史档案索引。
- 历史文档只能用于考古，不得覆盖 CURRENT 或 rules。
