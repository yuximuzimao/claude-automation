# 群聊分析文档索引

用途：只负责导航，不承载全部规则正文。

## 当前状态与整体设计

| 需求 | 入口 |
| --- | --- |
| 当前做到哪里、已验证什么、下一步是什么 | `CURRENT.md` |
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

- `../schemas/message-record.schema.json`：单条规范化文字消息。
- 后续如状态机需要独立版本化，再新增明确 schema；不把临时实现字段提前固化。

## 代码与测试

- `../src/README.md`：正式代码模块边界与依赖方向。
- `../tests/README.md`：验证策略。
- 正式代码尚未开始，不存在现役 CLI/daemon 入口。

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
