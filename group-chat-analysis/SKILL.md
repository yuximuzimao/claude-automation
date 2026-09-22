# 群聊分析 SKILL.md

## DO FIRST

1. 读 `tasks/todo.md`，确认当前尚未完成事项。
2. 读 `docs/INDEX.md`，只做导航。
3. 涉及当前实现阶段、已验证能力或下一恢复点时，读 `docs/CURRENT.md`。
4. 涉及规则判断时，从 `docs/rules/README.md` 只加载对应主题。
5. 涉及整体数据流或模块边界时，读 `docs/ARCHITECTURE.md`。
6. 正式实现后，代码入口统一从 `src/` 的现役入口进入；在入口尚未创建前不得自行发明临时正式入口。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `README.md` | 人类快速理解项目 | 需要项目概览时 |
| `CLAUDE.md` | 稳定目标、安全边界、Session规则 | 每次进入项目 |
| `tasks/todo.md` | 唯一当前待办 | 每次进入项目 |
| `docs/INDEX.md` | 文档/数据导航 | 每次进入项目 |
| `docs/CURRENT.md` | 当前开发阶段与已验证事实 | 继续当前工作时 |
| `docs/ARCHITECTURE.md` | 稳定模块边界与数据流 | 设计/实现跨模块功能时 |
| `docs/rules/README.md` | 永久规则路由 | 需要规则判断时 |
| `schemas/message-record.schema.json` | 单条规范化消息的数据契约 | 改消息结构/存储/去重时 |
| `src/README.md` | 代码模块职责与依赖方向 | 开始实现或调整模块时 |
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
| `docs/archive/` | 历史方案/阶段归档，默认不加载 |
| `tasks/` | 当前待办与临时教训 |
| `tests/` | 确定性逻辑、采集适配器与回归验证 |
| `runtime/` | 私密运行数据；整个目录不进 Git |
| `runtime/inbox/current.md` | GPT 默认读取的当前分析输入 |
| `runtime/reports/` | GPT分析结果，本地私密 |
