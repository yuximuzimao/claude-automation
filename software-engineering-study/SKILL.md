# 软件工程与 AI 系统设计学习 — SKILL

## DO FIRST

1. 读取 `tasks/todo.md`。
2. 读取 `docs/CURRENT.md`。
3. 读取 `docs/INDEX.md`，按当前学习任务加载对应资料。
4. 正式学习或调整进度时读取 `docs/learning-plan.md`；教材身份和 PDF 证据读取 `docs/book-catalog.md`、`docs/book-audit.md`；逐章预处理与复核遵循 `docs/book-processing-protocol.md`；知识讲解遵循 `docs/learning-method.md`。
5. 涉及 AI Agent 工程实践时读取 `docs/ai-engineering-practice.md`。

## 学习原则

- 从用户正在处理的真实问题出发，补充解决该问题所需的系统知识；不安排无实践关联的长课程。
- 重点训练发现隐含需求、边界条件、失败模式和技术假设的能力。
- 不把自然语言解释流畅、用户表示听懂，等同于知识已掌握或设计已验证。
- 关键知识必须能够追溯到教材章节/页码、官方资料或明确标注的实践来源。
- 严格区分教材原文、解释、推论、项目建议和实际验证结果。
- 不确定的内容明确标注，不编造章节、页码、作者观点或测试结论。
- 不把整本 PDF 加载进 Chat；正式学习只读取当前章节最终稿。逐章预处理遵循 book-processing-protocol.md，由 Workbuddy / DeepSeek 主控，千问默认复核，额度不足时可替换为 Kimi K2.8 或 Kimi 3.1 Pro。

## ENTRY MAP

| 文件 | 用途 | 何时读取 |
| --- | --- | --- |
| `CLAUDE.md` | 稳定学习目标与约束 | 每次进入项目 |
| `tasks/todo.md` | 未完成事项唯一台账 | 每次进入项目 |
| `docs/CURRENT.md` | 当前进度唯一真值 | 每次进入项目 |
| `docs/book-catalog.md` | 教材版本、资源和定位 | 教材筛选/阅读 |
| `docs/book-audit.md` | PDF核验依据、质量限制和候选章节 | 确认本地教材可用性或选择章节 |
| `docs/learning-method.md` | 来源、讲解、验证和学习单元规则 | 每次正式学习 |
| `docs/learning-plan.md` | 已确认第一阶段顺序、章节、周期和知识单元 | 制定进度/开始学习 |
| `docs/book-processing-protocol.md` | 五本教材逐章原文处理、独立复核、状态机和固定提示词 | 预处理/复核工作流 |
| `docs/ai-engineering-practice.md` | AI 工程实践补充资料 | 学习 Harness / Agent 工程 |
| `docs/archive/` | 阶段历史 | 需要恢复历史决策时 |

## CORE FLOWS

### 教材学习
确认版本和目录 → 选择一个小知识单元 → 读取对应原文 → 解释与案例 → 检查假设和反例 → 用新场景验证理解 → 记录已掌握内容与未解决问题。

### 项目实践
从真实项目问题提取知识点 → 找到教材/官方来源 → 说明适用条件和限制 → 回到项目比较方案 → 记录实际验证结果。

## FAILURE PATTERNS

- 只复述 AI 的解释，没有回到原文核对。
- 把推论或架构建议说成教材结论。
- 只讲正常流程，不主动检查异常条件和边界。
- 用测试数量或覆盖率替代测试质量判断。
- 把旧教材中的工具配置直接当作 2026 年 AI 开发实践。
- 一次加载整本教材，造成无关上下文膨胀。

## PATHS

- 教材本地文件：`resources/books/`（Git 忽略）
- 教材目录：`docs/book-catalog.md`
- 本地核验报告：`docs/book-audit.md`
- 学习记录与知识成果：后续按需建立在 `knowledge/` 或专项文档中
- 阶段归档：`docs/archive/`
