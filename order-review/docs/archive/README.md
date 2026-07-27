# 历史档案

本目录只保存已经完成或被后续需求替代的设计、实现计划和界面原型。归档内容用于追溯背景，不是当前实现依据。

当前状态与运行入口：`../../README.md`。长期业务约束：`../2026-07-23-package-rule-foundation.md`。

## 2026-07-10 初始悬浮窗实现

- `2026-07-10-initial-floating-window/implementation-plan.md`：第一版只读悬浮窗的已完成实现计划。

## 2026-07-22 只读原订单视图

- `2026-07-22-read-only-order-view/design.md`：第一阶段完整设计背景和早期页面事实。
- `2026-07-22-read-only-order-view/layout-options.html`：用于确定当前紧凑布局方向的历史视觉原型。

## 2026-07-22 本地包裹方案与精确推荐

- `2026-07-22-package-plan/requirements.md`：已完成的本地包裹编辑、案例保存和精确匹配推荐 v1 需求及完成情况。

## 2026-07-23 包裹根本规则基础实现

- `2026-07-23-package-rule-foundation/neat-handoff.md`：同一订单历史恢复、同订单方案版本、不同订单精确规则自动采用、单包跨分组复用、规则统计与完整回归的阶段收尾记录。
- 长期有效的业务规则仍位于 `../2026-07-23-package-rule-foundation.md`，不得把归档交接文件当作替代规则。

## 2026-07-24 阶段 A 数据与运行安全闭环

- `2026-07-24-stage-a-safety-closure/neat-handoff.md`：单实例、并发写锁、案例校验、滚动备份、损坏恢复、写后回滚、推荐事件隔离、无泄漏回放和降级工作区归档的最终收尾记录。
- 其中记录的案例数量是特定时间点快照；当前数量和成熟度必须以即时 `case_audit` / `case_replay` 为准。

## 2026-07-24 单包订单审核业务对齐

- `2026-07-24-single-package-review-alignment/README.md`：单包订单普通审核的业务前提、列表操作栏与右键方案取舍、多层提交核对、异常停止和分阶段授权。
- `2026-07-24-single-package-review-alignment/erp-page-evidence.md`：真实待审核页只读样本、系统订单号 `uniqueid` / `sid` 对应关系、审核弹窗截图转录和仍缺失的 DOM 事实。
- `2026-07-24-single-package-review-alignment/split-order-future-notes.md`：拆分后当前页识别、两行/三行可能状态、结果订单关联证据、样本采集要求和后续实施门禁。
- 当前活动实施依据仍是 `../2026-07-24-single-package-order-review-execution-v1.md`；业务对齐归档只解释决策来源，不能替代活动方案。

## 2026-07-27 物流独立标记与单件默认草稿

- `2026-07-27-freight-and-single-item-default/neat-handoff.md`：物流运输决策与普通包裹方案隔离、首批案例迁移、70 件人工复核提醒、提醒文案修复和总数量 1 非套件默认单包草稿的阶段收尾记录。
- 物流案例只提供人工运输决策证据，不证明系统具备箱规、体积或包裹数估算能力。

遇到归档内容与 `AGENTS.md`、根本规则、当前方向、活动实施方案或代码事实冲突时，以后者为准。
