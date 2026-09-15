# 旧状态/验证规则入口（已拆分，兼容指针）

状态：**不再是现役规则owner。**

本文件过去同时承载当前状态、Route Profile裁剪、候选完整性、Availability、局部重放、测试范围、用户反馈写回、NEAT和Git等多个领域，已经违反单一职责。2026-09-15架构治理后，这些职责已拆到各自唯一owner。

保留本文件只是为了兼容仍未更新的旧引用；新规则不得继续写入这里。顶层路由迁移完成、全库现役引用清零后，本文件应移入archive或删除。

## 当前职责入口

| 旧内容 | 当前唯一owner |
| --- | --- |
| 当前角色等级/位置/任务状态/唯一恢复点 | `docs/verified-routes/CURRENT.md` |
| 正式路线 vs 当前角色runtime overlay | `route-profile-and-lifecycle.md` |
| Task Card字段、事实、证据、五开标签/备注层 | `docs/task-library/README.md` |
| Availability / RouteState / 候选覆盖 / 动态飞行点 / 局部重放算法 | `route-atlas-optimization.md` |
| 任务机制分类 | `execution-and-mechanics.md` |
| Task Selection | `leveling-and-selection.md` |
| XP | `xp-model.md` |
| Timing | `timing-and-benchmarking.md` |
| 实跑反馈如何写回、局部修改怎么验证 | `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` |
| 测试范围与测试组合 | `tests/README.md` |
| 现役/历史脚本边界 | `scripts/README.md` |
| ERROR-BOOK历史案例 | `docs/verified-routes/ERROR-BOOK.md` |
| NEAT归档流程 | NEAT技能本身；本项目只保archive入口，不复制技能规则 |
| Git/敏感数据/项目级修改纪律 | `CLAUDE.md` |
| 永久规则目录与唯一owner治理 | `docs/rules/README.md` |

## 兼容纪律

- 旧文档/脚本仍引用本文件时，应按上表改到新owner。
- 禁止为了兼容旧引用在本文件重新复制一份现役规则。
- 任何当前实现若“只有读本文件才能知道正确做法”，都算迁移未完成。
- 最终对抗式验收要求：现役SKILL、CLAUDE、INDEX、rules README、SOP、scripts、tests、builder均不再把本文件当规则来源。
