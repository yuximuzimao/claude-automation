from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from .case_repository import ConfirmedCase, RuleStats
from .order_identity import (
    order_structure_signature,
    order_structure_signature_key,
    total_product_signature,
    total_product_signature_key,
)
from .package_plan import (
    Package,
    PackageDraft,
    PackageItem,
    PackagePlanValidationError,
    SourceProduct,
    SourceSnapshot,
)


RECOMMENDATION_ALGORITHM_VERSION = 1
SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION = 2
FREIGHT_REMINDER_ALGORITHM_VERSION = 1
MATCH_EXACT_STRUCTURE = "exact_structure"
MATCH_SINGLE_PACKAGE_TOTAL = "single_package_total"
MATCH_SINGLE_PACKAGE_CAPACITY = "single_package_capacity"


@dataclass(frozen=True)
class RecommendationItem:
    match_key: tuple[str, ...]
    product_name: str
    quantity: int


@dataclass(frozen=True)
class RecommendationPackage:
    items: tuple[RecommendationItem, ...]


@dataclass(frozen=True)
class RecommendationCandidate:
    recommendation_id: str
    rule_id: str
    match_type: str
    packages: tuple[RecommendationPackage, ...]
    source_case_ids: tuple[str, ...]
    usage_count: int
    algorithm_version: int = RECOMMENDATION_ALGORITHM_VERSION
    quantity_note: str = ""


@dataclass(frozen=True)
class RecommendationResult:
    candidates: tuple[RecommendationCandidate, ...]
    conflict: bool


@dataclass(frozen=True)
class FreightReminder:
    total_quantity: int
    product_kind_count: int
    source_case_ids: tuple[str, ...] = ()

    @property
    def has_history(self) -> bool:
        return bool(self.source_case_ids)

    @property
    def message(self) -> str:
        parts = [f"本单共 {self.total_quantity} 件、{self.product_kind_count} 种商品"]
        if self.total_quantity >= 70:
            parts[0] += "，已达到 70 件物流复核提醒线"
        if self.has_history:
            parts.append("历史相同商品总量曾选择物流发货")
        return (
            "；".join(parts)
            + "。系统只按总件数和历史案例提醒，不会估算包裹数；"
            "是否发物流仍需人工结合原箱、重量和商品组合判断。"
        )


def find_freight_reminder(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
) -> FreightReminder | None:
    total_signature = total_product_signature(source)
    matching = [
        case
        for case in cases
        if case.is_freight
        and total_product_signature(case.source_snapshot) == total_signature
    ]
    if source.total_quantity < 70 and not matching:
        return None
    return FreightReminder(
        total_quantity=source.total_quantity,
        product_kind_count=len({product.match_key for product in source.products}),
        source_case_ids=tuple(sorted(case.case_id for case in matching)),
    )


def _template(case: ConfirmedCase) -> tuple[RecommendationPackage, ...]:
    products = case.source_snapshot.product_by_id
    packages: list[RecommendationPackage] = []
    for package in case.package_plan.packages:
        totals: defaultdict[tuple[str, ...], int] = defaultdict(int)
        names: dict[tuple[str, ...], str] = {}
        for item in package.items:
            product = products.get(item.source_product_id)
            if product is None:
                raise PackagePlanValidationError("历史案例引用了不存在的原商品")
            totals[product.match_key] += item.quantity
            names[product.match_key] = item.product_name or product.display_name
        packages.append(
            RecommendationPackage(
                items=tuple(
                    RecommendationItem(key, names[key], quantity)
                    for key, quantity in sorted(totals.items())
                )
            )
        )
    return tuple(
        sorted(
            packages,
            key=lambda package: tuple(
                (item.match_key, item.quantity) for item in package.items
            ),
        )
    )


def _template_key(packages: tuple[RecommendationPackage, ...]) -> str:
    value = [
        [
            {"matchKey": list(item.match_key), "quantity": item.quantity}
            for item in package.items
        ]
        for package in packages
    ]
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rule_id(
    source: SourceSnapshot,
    packages: tuple[RecommendationPackage, ...],
    match_type: str,
) -> str:
    scope = (
        order_structure_signature_key(source)
        if match_type == MATCH_EXACT_STRUCTURE
        else total_product_signature_key(source)
    )
    payload = f"{match_type}:{scope}:{_template_key(packages)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"rule-v1-{digest}"


def _build_result(
    source: SourceSnapshot,
    matching: list[ConfirmedCase],
    *,
    match_type: str,
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    grouped: dict[str, list[ConfirmedCase]] = defaultdict(list)
    templates: dict[str, tuple[RecommendationPackage, ...]] = {}
    for case in matching:
        packages = _template(case)
        key = _template_key(packages)
        grouped[key].append(case)
        templates[key] = packages

    candidates: list[RecommendationCandidate] = []
    for key, grouped_cases in grouped.items():
        packages = templates[key]
        rule_id = _rule_id(source, packages, match_type)
        stats = (rule_stats or {}).get(rule_id)
        usage_count = len(grouped_cases) + (stats.direct_use_count if stats else 0)
        candidates.append(
            RecommendationCandidate(
                recommendation_id=rule_id,
                rule_id=rule_id,
                match_type=match_type,
                packages=packages,
                source_case_ids=tuple(case.case_id for case in grouped_cases),
                usage_count=usage_count,
            )
        )
    candidates.sort(key=lambda item: (-item.usage_count, item.recommendation_id))
    return RecommendationResult(
        candidates=tuple(candidates),
        conflict=len(candidates) > 1,
    )


def find_exact_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    signature = order_structure_signature(source)
    matching = [
        case
        for case in cases
        if not case.is_freight
        and order_structure_signature(case.source_snapshot) == signature
    ]
    return _build_result(
        source,
        matching,
        match_type=MATCH_EXACT_STRUCTURE,
        rule_stats=rule_stats,
    )


def find_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    """精确子订单结构优先；没有精确结果时才尝试单包总量复用。"""
    exact = find_exact_recommendations(source, cases, rule_stats)
    if exact.candidates:
        return exact

    total_signature = total_product_signature(source)
    matching_single = [
        case
        for case in cases
        if not case.is_freight
        and len(case.package_plan.packages) == 1
        and total_product_signature(case.source_snapshot) == total_signature
    ]
    single_total = _build_result(
        source,
        matching_single,
        match_type=MATCH_SINGLE_PACKAGE_TOTAL,
        rule_stats=rule_stats,
    )
    if single_total.candidates:
        return single_total

    return find_single_package_capacity_recommendations(source, cases, rule_stats)


def find_single_package_capacity_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    """只复用数量不超过已确认历史容量的单包案例。"""
    current_signature = total_product_signature(source)
    current_totals = dict(current_signature)
    current_keys = tuple(key for key, _ in current_signature)
    matching_by_capacity: defaultdict[
        tuple[tuple[tuple[str, ...], int], ...], list[ConfirmedCase]
    ] = defaultdict(list)

    for case in cases:
        if case.is_freight or len(case.package_plan.packages) != 1:
            continue
        historical_signature = total_product_signature(case.source_snapshot)
        if historical_signature == current_signature:
            continue
        if tuple(key for key, _ in historical_signature) != current_keys:
            continue
        historical_totals = dict(historical_signature)
        if all(
            current_totals[key] <= historical_totals[key] for key in current_keys
        ):
            matching_by_capacity[historical_signature].append(case)

    if not matching_by_capacity:
        return RecommendationResult(candidates=(), conflict=False)

    def capacity_rank(
        signature: tuple[tuple[tuple[str, ...], int], ...],
    ) -> tuple[int, int, tuple[int, ...], str]:
        historical_totals = dict(signature)
        slacks = tuple(
            historical_totals[key] - current_totals[key] for key in current_keys
        )
        return (
            sum(slacks),
            max(slacks, default=0),
            slacks,
            json.dumps(signature, ensure_ascii=False, separators=(",", ":")),
        )

    selected_capacity = min(matching_by_capacity, key=capacity_rank)
    matching = matching_by_capacity[selected_capacity]
    packages = _current_single_package_template(source)
    rule_id = _capacity_rule_id(selected_capacity)
    stats = (rule_stats or {}).get(rule_id)
    source_case_ids = tuple(sorted(case.case_id for case in matching))

    return RecommendationResult(
        candidates=(
            RecommendationCandidate(
                recommendation_id=rule_id,
                rule_id=rule_id,
                match_type=MATCH_SINGLE_PACKAGE_CAPACITY,
                packages=packages,
                source_case_ids=source_case_ids,
                usage_count=len(matching)
                + (stats.direct_use_count if stats else 0),
                algorithm_version=SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION,
                quantity_note=_capacity_note(
                    source,
                    current_totals=current_totals,
                    historical_totals=dict(selected_capacity),
                ),
            ),
        ),
        conflict=False,
    )


def _current_single_package_template(
    source: SourceSnapshot,
) -> tuple[RecommendationPackage, ...]:
    totals: defaultdict[tuple[str, ...], int] = defaultdict(int)
    names: dict[tuple[str, ...], str] = {}
    for product in source.products:
        totals[product.match_key] += product.quantity
        names.setdefault(product.match_key, product.display_name)
    return (
        RecommendationPackage(
            items=tuple(
                RecommendationItem(key, names[key], quantity)
                for key, quantity in sorted(totals.items())
            )
        ),
    )


def _capacity_rule_id(
    capacity_signature: tuple[tuple[tuple[str, ...], int], ...],
) -> str:
    payload = (
        f"{MATCH_SINGLE_PACKAGE_CAPACITY}:"
        f"{json.dumps(capacity_signature, ensure_ascii=False, separators=(',', ':'))}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"rule-v2-{digest}"


def _capacity_note(
    source: SourceSnapshot,
    *,
    current_totals: Mapping[tuple[str, ...], int],
    historical_totals: Mapping[tuple[str, ...], int],
) -> str:
    names: dict[tuple[str, ...], str] = {}
    for product in source.products:
        names.setdefault(product.match_key, product.display_name)
    historical = "、".join(
        f"{names[key]} ×{historical_totals[key]}" for key in sorted(current_totals)
    )
    current = "、".join(
        f"{names[key]} ×{current_totals[key]}" for key in sorted(current_totals)
    )
    return f"历史已确认单包容量：{historical}；当前：{current}。"


def apply_recommendation(
    source: SourceSnapshot,
    candidate: RecommendationCandidate,
) -> PackageDraft:
    available: dict[tuple[str, ...], list[list[SourceProduct | int]]] = defaultdict(list)
    for product in source.products:
        available[product.match_key].append([product, product.quantity])

    packages: list[Package] = []
    for package_index, template_package in enumerate(candidate.packages, start=1):
        package_items: list[PackageItem] = []
        for template_item in template_package.items:
            remaining = template_item.quantity
            for entry in available.get(template_item.match_key, []):
                product = entry[0]
                quantity_left = int(entry[1])
                if not isinstance(product, SourceProduct) or quantity_left <= 0:
                    continue
                used = min(quantity_left, remaining)
                if used:
                    package_items.append(
                        PackageItem(
                            source_product_id=product.source_product_id,
                            product_name=product.display_name,
                            quantity=used,
                        )
                    )
                    entry[1] = quantity_left - used
                    remaining -= used
                if remaining == 0:
                    break
            if remaining:
                raise PackagePlanValidationError("历史推荐与当前原订单商品无法完整对应")
        packages.append(Package(f"package-{package_index}", tuple(package_items)))

    draft = PackageDraft(snapshot_id=source.snapshot_id, packages=tuple(packages))
    draft.confirm(source)
    return draft


def apply_case_plan(source: SourceSnapshot, case: ConfirmedCase) -> PackageDraft:
    packages = _template(case)
    candidate = RecommendationCandidate(
        recommendation_id=f"history-{case.case_id}",
        rule_id=f"history-{case.case_id}",
        match_type=MATCH_EXACT_STRUCTURE,
        packages=packages,
        source_case_ids=(case.case_id,),
        usage_count=1,
    )
    return apply_recommendation(source, candidate)
