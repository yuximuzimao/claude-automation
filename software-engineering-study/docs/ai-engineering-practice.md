# AI 工程实践补充资料

本文件记录传统教材之外、需要结合 2025–2026 年 AI Agent 实践核对的资料。它们是补充阅读，不替代基础软件工程原理。

## 官方工程文章

以下链接已核对为发布方官方页面；正式学习时仍需按主题选择章节，不必一次性阅读全文。

- [OpenAI：Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)（2026-02-11）。重点：让代码库、架构、文档、日志、指标和 Trace 对 Agent 可理解；使用结构化约束、静态检查和持续清理维持一致性。
- [Anthropic：Effective harnesses for long-running agents](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents)（2025-11-26）。重点：跨多个上下文窗口的长程任务、初始化环境、进度持久化、增量执行和端到端验证。
- [Google Developers Blog：The Anatomy of Harness Engineering: How to Evaluate, Iterate, and Guard AI Coding Agents](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/)（2026-09-09）。重点：行为评估、迭代反馈、护栏和回归判断。

这些文章来自不同组织、不同产品和实验条件。它们是工程案例，不是经过普遍验证的统一标准；需要结合项目规模、风险和维护成本判断适用性。

## 需要研究的实践主题

- Agent 的代码库上下文与渐进式信息加载。
- 模块接口契约和架构约束。
- 统一日志、Trace、Metrics 与故障定位。
- 静态检查、架构适应度检查和生成式模块骨架。
- 长程任务的进度持久化与跨上下文交接。
- 风险驱动测试、行为评估和回归测试。
- 文档与代码的一致性、维护成本和知识过期。
- 何时值得采用形式化规约（例如 TLA+），何时不值得。

## 来自实践者讨论的待验证想法

用户提供了一段程序员关于 AI 长程开发的经验分享，核心包括：

- 不期待 AI 一次设计正确，重点是快速反馈、定位和修正。
- 模块间统一输入输出、Trace 和性能信息，减少每次从入口重新定位。
- 使用模块模板、注册机制和静态检查收敛 AI 的实现自由度。
- 将反复出现的问题逐步转化为 Skill、Agent 规则、静态检查或测试。
- 测试应按风险和业务契约设计，避免重复、昂贵且无意义的全量测试。
- 文档应区分设计意图、接口事实和运行记录。
- 对复杂状态/并发约束，评估是否需要形式化建模。

这些是有价值的工程假设，不是已验证的通用标准。后续应逐项研究其适用条件、成本和反例，再决定是否用于实际项目。
