from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TypeAlias

from .package_plan import Package, PackagePlan, SourceProduct, SourceSnapshot
from .split_dry_run import build_split_dry_run


ProductIdentity: TypeAlias = tuple[str, ...]
AllocationKey: TypeAlias = tuple[str, ProductIdentity]
AllocationSignature: TypeAlias = tuple[tuple[AllocationKey, int], ...]
PackageSignature: TypeAlias = AllocationSignature


@dataclass(frozen=True)
class SplitResultRow:
    """拆分后页面上的一条有效顶层订单行。"""

    sequence: int
    selected: bool
    source: SourceSnapshot | None = None


@dataclass(frozen=True)
class SplitResultObservation:
    """二次确认完成后，对当前待审核页的只读观察。"""

    loading_count: int
    visible_dialog_count: int
    rows: tuple[SplitResultRow, ...]


@dataclass(frozen=True)
class SplitResultCheck:
    code: str
    label: str
    status: str
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class SplitResultValidationReport:
    verified: bool
    target_package_count: int
    result_sequences: tuple[int, ...]
    result_system_order_ids: tuple[str, ...]
    checks: tuple[SplitResultCheck, ...]

    @property
    def blockers(self) -> tuple[SplitResultCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)

    def to_text(self) -> str:
        headline = "拆分结果验证通过" if self.verified else "拆分结果无法确认"
        icons = {"pass": "✓", "blocked": "✕"}
        lines = [
            headline,
            f"目标包裹：{self.target_package_count} 个",
            (
                "结果行："
                + (
                    "、".join(str(item) for item in self.result_sequences)
                    if self.result_sequences
                    else "未识别"
                )
            ),
        ]
        lines.extend(
            f"{icons.get(check.status, '✕')} {check.label}：{check.detail}"
            for check in self.checks
        )
        return "\n".join(lines)


def validate_split_result(
    source: SourceSnapshot,
    plan: PackagePlan,
    observation: SplitResultObservation,
) -> SplitResultValidationReport:
    """按无序包裹集合验证拆分结果，任何关键证据缺失都失败关闭。"""

    target_count = len(plan.packages)
    selected_rows = tuple(
        sorted(
            (row for row in observation.rows if row.selected),
            key=lambda row: row.sequence,
        )
    )
    result_sequences = tuple(row.sequence for row in selected_rows)
    result_system_order_ids = tuple(
        row.source.system_order_id if row.source is not None else ""
        for row in selected_rows
    )

    checks: list[SplitResultCheck] = []
    local_report = build_split_dry_run(source, plan)
    checks.append(
        _check(
            "LOCAL_PLAN_VALID",
            "本地拆分方案",
            local_report.local_plan_valid,
            (
                f"{target_count} 个非空包裹，数量共 {plan.total_quantity} 件"
                if local_report.local_plan_valid
                else "；".join(local_report.blocked_reasons)
            ),
        )
    )
    checks.append(
        _check(
            "CONFIRMATION_UI_CLOSED",
            "二次确认结束状态",
            observation.loading_count == 0
            and observation.visible_dialog_count == 0,
            (
                "加载层和可见弹窗均已消失"
                if observation.loading_count == 0
                and observation.visible_dialog_count == 0
                else (
                    f"加载状态 {observation.loading_count}，"
                    f"可见弹窗 {observation.visible_dialog_count}"
                )
            ),
        )
    )
    checks.append(
        _check(
            "SELECTED_RESULT_ROW_COUNT",
            "拆分结果勾选行数",
            len(selected_rows) == target_count,
            f"目标 {target_count} 行，实际勾选 {len(selected_rows)} 行",
        )
    )
    expected_sequences = tuple(range(1, target_count + 1))
    checks.append(
        _check(
            "SELECTED_ROWS_ARE_FIRST_N",
            "拆分结果所在位置",
            result_sequences == expected_sequences,
            (
                f"前 {target_count} 行连续勾选"
                if result_sequences == expected_sequences
                else (
                    f"期望序号 {expected_sequences or '无'}，"
                    f"实际 {result_sequences or '无'}"
                )
            ),
        )
    )
    checks.append(
        _check(
            "RESULT_SYSTEM_IDS_PRESENT",
            "结果订单身份",
            len(selected_rows) == target_count
            and all(result_system_order_ids),
            (
                "每条结果行都有系统订单号"
                if len(selected_rows) == target_count
                and all(result_system_order_ids)
                else "存在缺少系统订单号的结果行"
            ),
        )
    )

    source_identity_ready = _identity_ready(source)
    results_identity_ready = (
        len(selected_rows) == target_count
        and all(
            row.source is not None and _identity_ready(row.source)
            for row in selected_rows
        )
    )
    checks.append(
        _check(
            "RESULT_DETAILS_READY",
            "结果商品明细",
            source_identity_ready and results_identity_ready,
            (
                "原订单和每条结果行均有可比较的平台子订单及商品身份"
                if source_identity_ready and results_identity_ready
                else "商品明细尚未展开完整，或缺少稳定身份字段"
            ),
        )
    )

    expected_orders = _platform_order_universe(source)
    result_orders = frozenset(
        order_number
        for row in selected_rows
        if row.source is not None
        for order_number in _platform_order_universe(row.source)
    )
    checks.append(
        _check(
            "PLATFORM_ORDER_UNIVERSE",
            "平台子订单号全集",
            bool(expected_orders) and result_orders == expected_orders,
            (
                f"汇总去重后保持 {len(expected_orders)} 个平台子订单"
                if bool(expected_orders) and result_orders == expected_orders
                else (
                    f"拆分前 {sorted(expected_orders)}，"
                    f"拆分后 {sorted(result_orders)}"
                )
            ),
        )
    )

    total_matches = False
    packages_match = False
    if (
        local_report.local_plan_valid
        and source_identity_ready
        and results_identity_ready
        and len(selected_rows) == target_count
    ):
        expected_total = _source_signature(source)
        observed_total = _combined_result_signature(selected_rows)
        total_matches = observed_total == expected_total

        expected_packages = Counter(
            _expected_package_signature(source, package)
            for package in plan.packages
        )
        observed_packages = Counter(
            _source_signature(row.source)
            for row in selected_rows
            if row.source is not None
        )
        packages_match = observed_packages == expected_packages

    checks.append(
        _check(
            "TOTAL_DETAIL_CONSERVATION",
            "全部商品数量守恒",
            total_matches,
            (
                f"所有结果包裹合计 {source.total_quantity} 件，与原订单一致"
                if total_matches
                else "结果包裹按平台子订单和商品身份汇总后与原订单不一致"
            ),
        )
    )
    checks.append(
        _check(
            "PACKAGE_MULTISET_MATCH",
            "逐包明细匹配",
            packages_match,
            (
                "每个结果包裹都能无序匹配一个本地目标包裹"
                if packages_match
                else "结果包裹集合与本地目标方案不一致"
            ),
        )
    )

    checks_tuple = tuple(checks)
    return SplitResultValidationReport(
        verified=all(check.passed for check in checks_tuple),
        target_package_count=target_count,
        result_sequences=result_sequences,
        result_system_order_ids=result_system_order_ids,
        checks=checks_tuple,
    )


def _check(
    code: str,
    label: str,
    passed: bool,
    detail: str,
) -> SplitResultCheck:
    return SplitResultCheck(
        code=code,
        label=label,
        status="pass" if passed else "blocked",
        detail=detail,
    )


def _platform_order_universe(source: SourceSnapshot) -> frozenset[str]:
    return frozenset(
        value
        for value in (
            *source.platform_order_numbers,
            *(product.platform_order_number for product in source.products),
        )
        if value
    )


def _identity_ready(source: SourceSnapshot) -> bool:
    return bool(source.products) and all(
        bool(_platform_order_number(source, product))
        and any(product.match_key)
        and product.quantity > 0
        for product in source.products
    )


def _platform_order_number(
    source: SourceSnapshot,
    product: SourceProduct,
) -> str:
    if product.platform_order_number:
        return product.platform_order_number
    values = tuple(
        dict.fromkeys(
            value for value in source.platform_order_numbers if value
        )
    )
    return values[0] if len(values) == 1 else ""


def _source_signature(source: SourceSnapshot) -> AllocationSignature:
    totals: defaultdict[AllocationKey, int] = defaultdict(int)
    for product in source.products:
        key = (
            _platform_order_number(source, product),
            product.match_key,
        )
        totals[key] += product.quantity
    return tuple(sorted(totals.items()))


def _combined_result_signature(
    rows: tuple[SplitResultRow, ...],
) -> AllocationSignature:
    totals: defaultdict[AllocationKey, int] = defaultdict(int)
    for row in rows:
        if row.source is None:
            continue
        for product in row.source.products:
            key = (
                _platform_order_number(row.source, product),
                product.match_key,
            )
            totals[key] += product.quantity
    return tuple(sorted(totals.items()))


def _expected_package_signature(
    source: SourceSnapshot,
    package: Package,
) -> PackageSignature:
    totals: defaultdict[AllocationKey, int] = defaultdict(int)
    products = source.product_by_id
    for item in package.items:
        product = products[item.source_product_id]
        key = (
            _platform_order_number(source, product),
            product.match_key,
        )
        totals[key] += item.quantity
    return tuple(sorted(totals.items()))
