# 审单文档与数据索引

入口顺序：项目 `SKILL.md` → `tasks/todo.md` → 本索引；当前状态只见[CURRENT](CURRENT.md)。

| 需要什么 | 去哪里 |
|---|---|
| 装箱实验现状与下一阶段 | [CURRENT](CURRENT.md)；[完整计划](2026-09-08-packing-simulator-plan.md) |
| 下一会话算法研究起点 | [待办](../tasks/todo.md)；[2026-09-11 NEAT](archive/2026-09-11-packing-simulator-p1/neat-handoff.md) |
| 已确认的业务边界 | [规则路由](rules/README.md)；[根本规则](2026-07-23-package-rule-foundation.md) |
| ERP审核/拆分的精确关卡 | [执行规则](rules/erp-execution.md) |
| 浮窗/装箱页面运行、案例恢复、回放 | [使用指南](usage.md) |
| 纸箱/原箱/规则与布局证据 | `../data/packing-dimensions.json` |
| 单品尺寸、装箱范围、零体积/排除项 | `../data/packing-product-dimensions.json` |
| 不得自行解释的活动原文 | `../data/packing-campaign-notes-2026-09-08.txt` |
| 历史回放固定问题集 | `../data/replay-problem-set.json` |
| 在售新品视觉待补 | `../../product-mapping/data/products/hee/pending-products.json`；`../../product-mapping/data/products/kgos/pending-products.json` |
| ERP正式身份参考快照 | `../../product-mapping/data/products/erp-identities.json`（200条参考，不定义在售目录） |
| 历史阶段 | [档案索引](archive/README.md) |
| 前一阶段资料规划 | [2026-09-09 NEAT](archive/2026-09-09-packing-simulator-planning/neat-handoff.md) |

## 数据层次

- 正式原单案例与执行日志在 `~/Library/Application Support/Order Review/`，不因本地实验改写。
- 商品范围来自 `product-mapping` 的现役 features/pending；ERP 200条身份快照只补正式全称/简称/编码，不代表在售。装箱项目自身只维护尺寸、包装范围与几何相关资料。
- 包装资料按源尺寸、计算尺寸、来源与估计轴记录。完整名称和简称分开，空格和符号保留。
- `pendingMappings`及`giftPackingFitChecks`含待集成元数据与实验坐标；当前解析器不会自动将其提升为有效商品/箱型。
- 活跃计划描述当前下一阶段，归档描述已经讨论/验证的阶段事实；两者都不能取代当前源数据与业务规则。
