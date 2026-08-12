from __future__ import annotations

from dataclasses import dataclass

from .package_plan import PackagePlan, SourceSnapshot


LOCAL_INTENT_NEEDS_SPLIT = "需要拆分"
LOCAL_INTENT_INSUFFICIENT = "信息不足"
DRY_RUN_BLOCKED = "blocked"

_MISSING_ERP_FACTS = (
    "混合拆分入口、弹窗行序映射和首个结果样本已经验证",
    "受保护的单订单拆分执行器已经接入，仍需第二个独立订单真实验收",
    "拆分成功后仅在审核弹窗勾选数量等于目标包裹数时继续审核",
)


@dataclass(frozen=True)
class SplitDryRunReport:
    target_system_order_id: str
    captured_at: str
    target_package_count: int
    source_total_quantity: int
    plan_total_quantity: int
    local_intent: str
    status: str
    package_lines: tuple[str, ...]
    blocked_reasons: tuple[str, ...]

    @property
    def local_plan_valid(self) -> bool:
        return self.local_intent == LOCAL_INTENT_NEEDS_SPLIT

    def to_text(self) -> str:
        lines = [
            f"本地目标：{self.local_intent}",
            f"目标订单：{self.target_system_order_id or '未识别'}",
        ]
        if self.local_plan_valid:
            lines.extend(
                (
                    f"目标包裹：{self.target_package_count} 个",
                    *self.package_lines,
                    (
                        "数量核对："
                        f"{self.plan_total_quantity} / {self.source_total_quantity} 件，守恒"
                    ),
                )
            )
        lines.extend(
            (
                "ERP 执行：由界面的受保护拆分按钮单独触发",
                "执行边界：",
                *(f"- {reason}" for reason in self.blocked_reasons),
                "本报告只验证本地方案，不会自行操作 ERP。",
            )
        )
        return "\n".join(lines)


def build_split_dry_run(
    source: SourceSnapshot,
    plan: PackagePlan,
) -> SplitDryRunReport:
    local_issues = _local_plan_issues(source, plan)
    local_plan_valid = not local_issues
    package_lines = tuple(
        _format_package_line(index, package.items)
        for index, package in enumerate(plan.packages, start=1)
    )
    return SplitDryRunReport(
        target_system_order_id=source.system_order_id,
        captured_at=source.captured_at,
        target_package_count=len(plan.packages),
        source_total_quantity=source.total_quantity,
        plan_total_quantity=plan.total_quantity,
        local_intent=(
            LOCAL_INTENT_NEEDS_SPLIT
            if local_plan_valid
            else LOCAL_INTENT_INSUFFICIENT
        ),
        status=DRY_RUN_BLOCKED,
        package_lines=package_lines if local_plan_valid else (),
        blocked_reasons=tuple(local_issues) if local_issues else _MISSING_ERP_FACTS,
    )


def _local_plan_issues(
    source: SourceSnapshot,
    plan: PackagePlan,
) -> list[str]:
    issues: list[str] = []
    if not source.system_order_id:
        issues.append("当前订单缺少可靠的 ERP 系统订单号")
    if not source.products:
        issues.append("当前订单没有可复核的商品明细")
    elif any(product.quantity <= 0 for product in source.products):
        issues.append("当前订单存在无效商品数量")
    if len(plan.packages) < 2:
        issues.append("本地目标方案不是多包方案")
        return issues
    if any(not package.items for package in plan.packages):
        issues.append("本地目标方案存在空包裹")

    source_quantities = {
        product.source_product_id: product.quantity for product in source.products
    }
    assigned_quantities = {source_product_id: 0 for source_product_id in source_quantities}
    invalid_quantity = False
    unknown_product = False
    for package in plan.packages:
        for item in package.items:
            if item.quantity <= 0:
                invalid_quantity = True
            if item.source_product_id not in assigned_quantities:
                unknown_product = True
                continue
            assigned_quantities[item.source_product_id] += item.quantity
    if invalid_quantity:
        issues.append("本地目标方案存在无效分配数量")
    if unknown_product:
        issues.append("本地目标方案引用了不属于当前订单的商品")
    if assigned_quantities != source_quantities:
        issues.append("本地目标方案与原订单商品数量不守恒")
    return issues


def _format_package_line(index: int, items) -> str:
    summary = " + ".join(
        f"{item.product_name or item.source_product_id} ×{item.quantity}"
        for item in items
    )
    return f"包裹 {index}：{summary or '空'}"
