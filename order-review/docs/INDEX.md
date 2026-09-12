# 审单文档与数据索引

入口顺序：项目 `SKILL.md` → `tasks/todo.md` → 本索引；当前状态只见[CURRENT](CURRENT.md)。

| 需要什么 | 去哪里 |
|---|---|
| 装箱算法最新研究与1～N箱结构 | [算法研究](2026-09-12-packing-algorithm-research.md) |
| 装箱实验现状与阶段边界 | [CURRENT](CURRENT.md)；[完整计划](2026-09-08-packing-simulator-plan.md) |
| 已确认的业务边界 | [规则路由](rules/README.md)；[根本规则](2026-07-23-package-rule-foundation.md) |
| ERP审核/拆分的精确关卡 | [执行规则](rules/erp-execution.md) |
| 浮窗/装箱页面运行、案例恢复、回放 | [使用指南](usage.md) |
| 纸箱、原箱、规则、待补与布局证据 | `../data/packing-dimensions.json` |
| 单品装箱尺寸、零体积配件与仓库排除项 | `../data/packing-product-dimensions.json` |
| 不得自行解释的活动原文 | `../data/packing-campaign-notes-2026-09-08.txt` |
| 历史回放固定问题集 | `../data/replay-problem-set.json` |
| 悦希新品身份和视觉待补 | `../../product-mapping/tasks/todo.md`（HEE 6 个新品视觉待办） |
| ERP正式身份参考快照 | `../../product-mapping/data/products/erp-identities.json`（2026-09-11的200条只读快照，不定义在售目录） |
| 历史阶段 | [档案索引](archive/README.md) |
| 前一阶段资料规划 | [2026-09-09 NEAT](archive/2026-09-09-packing-simulator-planning/neat-handoff.md) |
| P1页面/资料/实验服务历史收口 | [2026-09-11 NEAT](archive/2026-09-11-packing-simulator-p1/neat-handoff.md)（现行规则以CURRENT为准） |
| worktree→main最终对账与主干接管 | [2026-09-13 NEAT](archive/2026-09-13-packing-worktree-reconciliation/neat-handoff.md) |

## 数据层次

- 正式原单案例与执行日志在 `~/Library/Application Support/Order Review/`，不因本地实验改写。
- 商品匹配的视觉标签不是装箱身份。模拟器只从 `features.json` 读取 ERP 标准全名，再用200条身份快照补正式简称/编码；商品尺寸和装箱规则由 `order-review` 自己维护并按 ERP 标准全名/商家编码关联。
- 包装资料按源尺寸、计算尺寸、来源与估计轴记录。完整名称和简称分开，空格和符号保留。
- `pendingMappings`及`giftPackingFitChecks`含待集成元数据与实验坐标；当前解析器不会自动将其提升为有效商品/箱型。
- 活跃计划描述当前边界与后续方向，归档描述已经讨论/验证的历史事实；两者都不能取代当前源数据与业务规则。
