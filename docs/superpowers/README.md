# Superpowers 文档索引

这里保存跨项目能力的设计、验证与历史材料。当前规则优先级始终是：**实际 Skill / 代码 > 当前设计 > 最终验证 > 历史归档**。

## WorkBuddy 安全派工（当前）

- 权威使用规则：[个人 Skill](/Users/chat/.codex/skills/dispatching-workbuddy/SKILL.md)。
- 架构与安全边界：[最小投影执行与可回档设计](specs/2026-07-13-workbuddy-isolated-execution-design.md)。
- 实机和自动化证据：[最终验证记录](reports/2026-07-13-dispatching-workbuddy-final-validation.md)。

当前账户只派发 `dataClassification: "non_sensitive"` 的受限代码任务。含密钥、客户原始数据、生产系统或无法确认敏感性的任务必须转到独立 macOS 用户或虚拟机；文件投影和工具白名单不是同用户进程隔离。

## 历史归档

`archive/2026-07-13-workbuddy-safety/` 保存已经完成的 TDD 实施计划及 RED/GREEN 压力测试。它们用于追溯决策，**不得**当作当前操作手册；尤其不能复用其中旧的看门狗阈值、环境变量测试注入或自动终止设想。

## 其他能力

`specs/` 和 `plans/` 中的 CodexPro 文档属于独立能力，本次未修改或归档。
