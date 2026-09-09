# 审单文档与数据索引

入口顺序：项目 `SKILL.md` → `tasks/todo.md` → 本索引；当前状态只见[CURRENT](CURRENT.md)。

| 需要什么 | 去哪里 |
|---|---|
| 后续GPT执行装箱实验 | [完整计划](2026-09-08-packing-simulator-plan.md) |
| 已确认的业务边界 | [规则路由](rules/README.md)；[根本规则](2026-07-23-package-rule-foundation.md) |
| ERP审核/拆分的精确关卡 | [执行规则](rules/erp-execution.md) |
| 浮窗使用、运行、案例恢复、回放 | [使用指南](usage.md) |
| 包装尺寸、原箱、估计值与布局证据 | `../data/packing-dimensions.json` |
| 不得自行解释的活动原文 | `../data/packing-campaign-notes-2026-09-08.txt` |
| 历史回放固定问题集 | `../data/replay-problem-set.json` |
| 悦希新品身份和视觉待补 | `../../product-mapping/data/products/hee/pending-products.json` |
| 历史阶段 | [档案索引](archive/README.md) |
| 本轮交接与核查证据 | [2026-09-09 NEAT](archive/2026-09-09-packing-simulator-planning/neat-handoff.md) |

## 数据层次

- 正式原单案例与执行日志在 `~/Library/Application Support/Order Review/`，不因本地实验改写。
- 包装资料按源尺寸、计算尺寸、来源与估计轴记录。完整名称和简称分开，空格和符号保留。
- `pendingMappings`及`giftPackingFitChecks`含待集成元数据与实验坐标；当前解析器不会自动将其提升为有效商品/箱型。
- 活跃计划描述将来要做的事，归档描述已经讨论/验证的事；两者都不能取代当前源数据与业务规则。
