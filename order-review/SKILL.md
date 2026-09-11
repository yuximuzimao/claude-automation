---
name: order-review
description: 审单项目导航：原订单读取、本地包裹方案、受控ERP执行和独立装箱实验规划。
---

# 订单审核系统导航

## DO FIRST

1. 读 `AGENTS.md` / `CLAUDE.md` 的安全边界。
2. 读 `tasks/todo.md` 和 `docs/INDEX.md`，按当前任务选择专项文档。
3. 读 `docs/CURRENT.md` 恢复唯一当前状态；不要从历史归档推断实现进度。
4. ERP操作仍按当次当前订单授权；本地装箱模拟不能触发真实业务操作。

## ENTRY MAP

| 任务 | 入口 |
|---|---|
| 接手装箱实验 / 下一步算法研究 | `tasks/todo.md` → `docs/CURRENT.md` → `docs/2026-09-08-packing-simulator-plan.md` → `docs/archive/2026-09-11-packing-simulator-p1/neat-handoff.md` |
| 包裹业务规则 | `docs/rules/README.md` → `docs/2026-07-23-package-rule-foundation.md` |
| ERP审核/拆分与读取 | `docs/rules/erp-execution.md`；`src/order_review/audit_runner.py`、`split_runner.py`、`erp_reader.py` |
| 原单、草稿和推荐 | `package_plan.py`、`package_workflow.py`、`recommendations.py`（均在`src/order_review/`） |
| 尺寸与单箱求解 | 纸箱/规则 `data/packing-dimensions.json`；单品尺寸 `data/packing-product-dimensions.json`；`dimension_catalog.py`、`carton_packing.py` |
| 案例/备份/回放 | `docs/usage.md`；`case_repository.py`、`case_restore.py`、`case_replay.py`、`packing_case_audit.py` |
| 界面 | 审单浮窗：`src/order_review/ui.py`；装箱实验：`src/order_review/packing_simulator_web.py`、`packing_simulator_service.py`、`packing_simulator_static/` |
| 本阶段证据 | P1收口：`docs/archive/2026-09-11-packing-simulator-p1/neat-handoff.md`；前置规划：`docs/archive/2026-09-09-packing-simulator-planning/neat-handoff.md` |

## CORE FLOWS

- 日常审单：读取原订单 → 恢复/编辑本地方案 → 用户逐单点击 → 独立ERP执行验证。
- 装箱实验：只读快照/实验副本 → 指定箱型与约束 → 计算/独立校验 → 展示；是否已实现以CURRENT为准。
- 资料补充：保留完整名称、简称及原始尺寸 → 核实来源与估计轴 → 更新资料 → 读回；不自动扩大白名单。

## FAILURE PATTERNS

- 同一SKU不等于同一固定组合；组合相同比例也不能自动推断为同一套餐。
- 几何UNKNOWN不等于装不下；规则支持不等于三维求解成功。
- 当前求解器的“完整底面支撑”是已知过严的算法假设，不得升级成业务装箱规则；几何可行性与运输稳定性后续分层。
- 礼盒内部商品不能与封装礼盒重复计体积；礼袋估计厚度不能标成实测。
- `pendingMappings`和`giftPackingFitChecks`目前含待集成资料/实验坐标，不能当作加载器已经启用的产品或箱型。
- 正式案例、原始活动笔记和ERP日志保持事实，不为通过回放或匹配计划改写。

## PATHS

- `AGENTS.md`、`CLAUDE.md`、`README.md`
- `tasks/todo.md`
- `docs/INDEX.md`、`docs/CURRENT.md`、`docs/usage.md`
- `docs/rules/README.md`、`docs/rules/erp-execution.md`
- `docs/2026-07-23-package-rule-foundation.md`
- `docs/2026-09-08-packing-simulator-plan.md`
- `docs/archive/README.md`、`docs/archive/2026-09-11-packing-simulator-p1/`、`docs/archive/2026-09-09-packing-simulator-planning/`
- `data/packing-dimensions.json`、`data/packing-product-dimensions.json`、`data/replay-problem-set.json`
- `data/packing-campaign-notes-2026-09-08.txt`（未解析原文）
- `src/order_review/`、`tests/`、`pyproject.toml`
