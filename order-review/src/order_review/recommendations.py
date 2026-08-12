from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from typing import Mapping

from .case_repository import ConfirmedCase, RuleStats
from .order_identity import (
    package_order_structure_signature,
    package_order_structure_signature_key,
    package_total_product_signature,
    package_total_product_signature_key,
    same_order_signature_key,
    total_product_signature,
)
from .package_plan import (
    Package,
    PackageDraft,
    PackageItem,
    PackagePlanValidationError,
    SourceProduct,
    SourceSnapshot,
)
from .package_equivalence import PACKAGE_EQUIVALENCE_KEY_PREFIX


RECOMMENDATION_ALGORITHM_VERSION = 1
PACKAGE_EQUIVALENT_RECOMMENDATION_ALGORITHM_VERSION = 2
SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION = 3
PACKAGE_EQUIVALENT_SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION = 4
HISTORICAL_PACKAGE_COMPOSITION_ALGORITHM_VERSION = 2
PACKAGE_EQUIVALENT_COMPOSITION_ALGORITHM_VERSION = 3
FREIGHT_REMINDER_ALGORITHM_VERSION = 1
MATCH_EXACT_STRUCTURE = "exact_structure"
MATCH_SINGLE_PACKAGE_TOTAL = "single_package_total"
MATCH_SINGLE_PACKAGE_CAPACITY = "single_package_capacity"
MATCH_HISTORICAL_PACKAGE_COMPOSITION = "historical_package_composition"
MAX_COMPOSITION_PACKAGES = 5
MAX_COMPOSITION_CANDIDATES = 5
MAX_COMPOSITION_SEARCH_STATES = 50_000
MIN_COMPOSITION_MODULE_CASES = 3


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
    advisory_note: str = ""


@dataclass(frozen=True)
class _HistoricalPackageModule:
    signature: tuple[tuple[tuple[str, ...], int], ...]
    source_case_ids: tuple[str, ...]
    observation_count: int


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


def _template(
    case: ConfirmedCase,
    *,
    use_package_equivalence: bool = True,
) -> tuple[RecommendationPackage, ...]:
    products = case.source_snapshot.product_by_id
    packages: list[RecommendationPackage] = []
    for package in case.package_plan.packages:
        totals: defaultdict[tuple[str, ...], int] = defaultdict(int)
        names: dict[tuple[str, ...], str] = {}
        for item in package.items:
            product = products.get(item.source_product_id)
            if product is None:
                raise PackagePlanValidationError("历史案例引用了不存在的原商品")
            key = (
                product.package_match_key
                if use_package_equivalence
                else product.match_key
            )
            totals[key] += item.quantity
            names[key] = item.product_name or product.display_name
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
        package_order_structure_signature_key(source)
        if match_type == MATCH_EXACT_STRUCTURE
        else package_total_product_signature_key(source)
    )
    payload = f"{match_type}:{scope}:{_template_key(packages)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    version = (
        _composition_algorithm_version(packages)
        if match_type == MATCH_HISTORICAL_PACKAGE_COMPOSITION
        else _recommendation_algorithm_version(packages)
    )
    return f"rule-v{version}-{digest}"


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
        packages = _project_template_names(source, templates[key])
        rule_id = _rule_id(source, packages, match_type)
        # 订单精确匹配由明细签名本身证明，不使用历史“采用次数”增加置信度。
        # rule_stats 参数仅为兼容旧调用和旧文件结构保留。
        usage_count = len(grouped_cases)
        algorithm_version = _recommendation_algorithm_version(packages)
        candidates.append(
            RecommendationCandidate(
                recommendation_id=rule_id,
                rule_id=rule_id,
                match_type=match_type,
                packages=packages,
                source_case_ids=tuple(case.case_id for case in grouped_cases),
                usage_count=usage_count,
                algorithm_version=algorithm_version,
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
    signature = package_order_structure_signature(source)
    matching = [
        case
        for case in cases
        if not case.is_freight
        and package_order_structure_signature(case.source_snapshot) == signature
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

    single_total = find_single_package_total_recommendations(
        source,
        cases,
        rule_stats,
    )
    if single_total.candidates:
        return single_total

    composition = find_historical_package_composition_recommendations(
        source,
        cases,
        rule_stats,
    )
    if composition.candidates:
        return composition

    return find_single_package_capacity_recommendations(source, cases, rule_stats)


def find_single_package_total_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    """匹配商品总量完全相同、且历史已经确认为单包的案例。"""
    total_signature = package_total_product_signature(source)
    matching_single = [
        case
        for case in cases
        if not case.is_freight
        and len(case.package_plan.packages) == 1
        and package_total_product_signature(case.source_snapshot) == total_signature
    ]
    return _build_result(
        source,
        matching_single,
        match_type=MATCH_SINGLE_PACKAGE_TOTAL,
        rule_stats=rule_stats,
    )


def find_historical_package_composition_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    """用历史中原样确认过的包裹模块精确覆盖当前商品总量。"""
    current_signature = package_total_product_signature(source)
    if not current_signature:
        return RecommendationResult(candidates=(), conflict=False)
    current_keys = tuple(key for key, _ in current_signature)
    current_totals = tuple(quantity for _, quantity in current_signature)
    current_by_key = dict(current_signature)

    module_sources: defaultdict[
        tuple[tuple[tuple[str, ...], int], ...], set[str]
    ] = defaultdict(set)
    module_observations: defaultdict[
        tuple[tuple[tuple[str, ...], int], ...], int
    ] = defaultdict(int)
    module_boundary_sources: defaultdict[
        tuple[tuple[tuple[str, ...], int], ...], set[str]
    ] = defaultdict(set)
    for case in _latest_cases_per_order(cases):
        if case.is_freight:
            continue
        for package in _template(case):
            signature = tuple(
                (item.match_key, item.quantity) for item in package.items
            )
            if not signature or any(
                key not in current_by_key or quantity > current_by_key[key]
                for key, quantity in signature
            ):
                continue
            module_sources[signature].add(case.case_id)
            module_observations[signature] += 1
            if len(case.package_plan.packages) > 1:
                module_boundary_sources[signature].add(case.case_id)

    modules = tuple(
        _HistoricalPackageModule(
            signature=signature,
            source_case_ids=tuple(sorted(module_sources[signature])),
            observation_count=module_observations[signature],
        )
        for signature in sorted(
            module_sources,
            key=lambda value: json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )
        if len(module_sources[signature]) >= MIN_COMPOSITION_MODULE_CASES
        and module_boundary_sources[signature]
    )
    if not modules:
        return RecommendationResult(candidates=(), conflict=False)

    module_vectors = tuple(
        tuple(dict(module.signature).get(key, 0) for key in current_keys)
        for module in modules
    )
    solutions = _find_minimum_composition_solutions(
        current_totals,
        module_vectors,
    )
    candidates: list[RecommendationCandidate] = []
    for solution in solutions:
        raw_packages = tuple(
            RecommendationPackage(
                items=tuple(
                    RecommendationItem(key, "", quantity)
                    for key, quantity in modules[module_index].signature
                )
            )
            for module_index in solution
        )
        packages = _project_template_names(source, raw_packages)
        algorithm_version = _composition_algorithm_version(packages)
        rule_id = _rule_id(
            source,
            packages,
            MATCH_HISTORICAL_PACKAGE_COMPOSITION,
        )
        source_case_ids = tuple(
            sorted(
                {
                    case_id
                    for module_index in solution
                    for case_id in modules[module_index].source_case_ids
                }
            )
        )
        stats = (rule_stats or {}).get(rule_id)
        candidates.append(
            RecommendationCandidate(
                recommendation_id=rule_id,
                rule_id=rule_id,
                match_type=MATCH_HISTORICAL_PACKAGE_COMPOSITION,
                packages=packages,
                source_case_ids=source_case_ids,
                usage_count=len(source_case_ids)
                + (stats.direct_use_count if stats else 0),
                algorithm_version=algorithm_version,
                quantity_note=_composition_note(
                    tuple(
                        modules[module_index].observation_count
                        for module_index in solution
                    )
                ),
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.usage_count,
            _template_key(item.packages),
            item.recommendation_id,
        )
    )
    return RecommendationResult(
        candidates=tuple(candidates),
        conflict=len(candidates) > 1,
    )


def _latest_cases_per_order(
    cases: list[ConfirmedCase],
) -> tuple[ConfirmedCase, ...]:
    latest: dict[str, ConfirmedCase] = {}
    for case in cases:
        key = (
            same_order_signature_key(case.source_snapshot)
            or f"snapshot:{case.source_snapshot.snapshot_id}"
        )
        current = latest.get(key)
        if current is None or (
            case.order_version,
            case.confirmed_at,
            case.case_id,
        ) > (
            current.order_version,
            current.confirmed_at,
            current.case_id,
        ):
            latest[key] = case
    return tuple(latest.values())


def _find_minimum_composition_solutions(
    target: tuple[int, ...],
    module_vectors: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    modules_by_key = tuple(
        tuple(
            module_index
            for module_index, vector in enumerate(module_vectors)
            if vector[key_index] > 0
        )
        for key_index in range(len(target))
    )
    state_count = 0

    class SearchLimitReached(RuntimeError):
        pass

    @lru_cache(maxsize=None)
    def solve(remaining: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
        nonlocal state_count
        state_count += 1
        if state_count > MAX_COMPOSITION_SEARCH_STATES:
            raise SearchLimitReached
        if not any(remaining):
            return ((),)

        positive_keys = [
            key_index
            for key_index, quantity in enumerate(remaining)
            if quantity > 0
        ]
        pivot = min(
            positive_keys,
            key=lambda key_index: sum(
                1
                for module_index in modules_by_key[key_index]
                if _vector_fits(module_vectors[module_index], remaining)
            ),
        )
        fitting_modules = [
            module_index
            for module_index in modules_by_key[pivot]
            if _vector_fits(module_vectors[module_index], remaining)
        ]
        if not fitting_modules:
            return ()

        best_length: int | None = None
        solutions: set[tuple[int, ...]] = set()
        for module_index in fitting_modules:
            vector = module_vectors[module_index]
            next_remaining = tuple(
                quantity - used
                for quantity, used in zip(remaining, vector)
            )
            for tail in solve(next_remaining):
                solution = tuple(sorted((module_index, *tail)))
                if len(solution) > MAX_COMPOSITION_PACKAGES:
                    continue
                if best_length is None or len(solution) < best_length:
                    best_length = len(solution)
                    solutions = {solution}
                elif len(solution) == best_length:
                    solutions.add(solution)
        return tuple(sorted(solutions)[: MAX_COMPOSITION_CANDIDATES + 1])

    try:
        return solve(target)[:MAX_COMPOSITION_CANDIDATES]
    except SearchLimitReached:
        return ()


def _vector_fits(vector: tuple[int, ...], remaining: tuple[int, ...]) -> bool:
    return all(used <= quantity for used, quantity in zip(vector, remaining))


def _composition_note(observations: tuple[int, ...]) -> str:
    evidence = " / ".join(str(count) for count in observations)
    return (
        f"由 {len(observations)} 个历史已确认包裹精确组合；"
        f"各包裹历史证据 {evidence} 次。未使用容量或比例推算。"
    )


def find_single_package_capacity_recommendations(
    source: SourceSnapshot,
    cases: list[ConfirmedCase],
    rule_stats: Mapping[str, RuleStats] | None = None,
) -> RecommendationResult:
    """提供较大数量单包参考；已有反向多包证据时阻断候选。"""
    current_signature = package_total_product_signature(source)
    current_totals = dict(current_signature)
    current_keys = tuple(key for key, _ in current_signature)
    matching_by_capacity: defaultdict[
        tuple[tuple[tuple[str, ...], int], ...], list[ConfirmedCase]
    ] = defaultdict(list)

    latest_cases = _latest_cases_per_order(cases)
    for case in latest_cases:
        if case.is_freight or len(case.package_plan.packages) != 1:
            continue
        historical_signature = package_total_product_signature(case.source_snapshot)
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
    counterexample = _single_package_capacity_counterexample(
        source,
        latest_cases,
        selected_capacity=selected_capacity,
    )
    if counterexample is not None:
        return RecommendationResult(
            candidates=(),
            conflict=False,
            advisory_note=_capacity_counterexample_note(
                source,
                selected_capacity=selected_capacity,
                counterexample=counterexample,
            ),
        )
    matching = matching_by_capacity[selected_capacity]
    packages = _current_single_package_template(source)
    algorithm_version = _capacity_algorithm_version(selected_capacity)
    rule_id = _capacity_rule_id(
        selected_capacity,
        algorithm_version=algorithm_version,
    )
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
                algorithm_version=algorithm_version,
                quantity_note=_capacity_note(
                    source,
                    current_totals=current_totals,
                    historical_totals=dict(selected_capacity),
                ),
            ),
        ),
        conflict=False,
    )


def _single_package_capacity_counterexample(
    source: SourceSnapshot,
    cases: tuple[ConfirmedCase, ...],
    *,
    selected_capacity: tuple[tuple[tuple[str, ...], int], ...],
) -> ConfirmedCase | None:
    """找出不超过单包参考数量、但人工实际确认为多包的同商品反例。"""
    capacity_totals = dict(selected_capacity)
    capacity_keys = tuple(key for key, _ in selected_capacity)
    counterexamples: list[ConfirmedCase] = []
    for case in cases:
        if case.is_freight or len(case.package_plan.packages) <= 1:
            continue
        signature = package_total_product_signature(case.source_snapshot)
        if tuple(key for key, _ in signature) != capacity_keys:
            continue
        totals = dict(signature)
        if all(totals[key] <= capacity_totals[key] for key in capacity_keys):
            counterexamples.append(case)
    if not counterexamples:
        return None

    current_totals = dict(package_total_product_signature(source))

    def rank(case: ConfirmedCase) -> tuple[int, int, str, str]:
        totals = dict(package_total_product_signature(case.source_snapshot))
        distance = tuple(
            abs(totals[key] - current_totals[key]) for key in capacity_keys
        )
        return (
            sum(distance),
            max(distance, default=0),
            case.confirmed_at,
            case.case_id,
        )

    return min(counterexamples, key=rank)


def _capacity_counterexample_note(
    source: SourceSnapshot,
    *,
    selected_capacity: tuple[tuple[tuple[str, ...], int], ...],
    counterexample: ConfirmedCase,
) -> str:
    names: dict[tuple[str, ...], str] = {}
    for product in source.products:
        names.setdefault(product.package_match_key, product.display_name)

    def summary(
        signature: tuple[tuple[tuple[str, ...], int], ...],
    ) -> str:
        return "、".join(
            f"{names[key]} ×{quantity}" for key, quantity in signature
        )

    multi_signature = package_total_product_signature(counterexample.source_snapshot)
    return (
        f"历史证据互相冲突：{summary(selected_capacity)} 曾单包，"
        f"但 {summary(multi_signature)} 实际用了 "
        f"{len(counterexample.package_plan.packages)} 个包裹。"
        "这说明该商品受离散纸箱规格影响，系统已停止外推单包；"
        "请按当前箱型人工创建方案。"
    )


def _current_single_package_template(
    source: SourceSnapshot,
) -> tuple[RecommendationPackage, ...]:
    totals: defaultdict[tuple[str, ...], int] = defaultdict(int)
    names: dict[tuple[str, ...], str] = {}
    for product in source.products:
        totals[product.package_match_key] += product.quantity
        names.setdefault(product.package_match_key, product.display_name)
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
    *,
    algorithm_version: int,
) -> str:
    payload = (
        f"{MATCH_SINGLE_PACKAGE_CAPACITY}:"
        f"{json.dumps(capacity_signature, ensure_ascii=False, separators=(',', ':'))}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"rule-v{algorithm_version}-{digest}"


def _capacity_note(
    source: SourceSnapshot,
    *,
    current_totals: Mapping[tuple[str, ...], int],
    historical_totals: Mapping[tuple[str, ...], int],
) -> str:
    names: dict[tuple[str, ...], str] = {}
    for product in source.products:
        names.setdefault(product.package_match_key, product.display_name)
    historical = "、".join(
        f"{names[key]} ×{historical_totals[key]}" for key in sorted(current_totals)
    )
    current = "、".join(
        f"{names[key]} ×{current_totals[key]}" for key in sorted(current_totals)
    )
    return (
        f"历史较大数量单包参考：{historical}；当前：{current}。"
        "这不是连续容量结论，请结合实际纸箱核对。"
    )


def apply_recommendation(
    source: SourceSnapshot,
    candidate: RecommendationCandidate,
    *,
    use_package_equivalence: bool = True,
) -> PackageDraft:
    available: dict[tuple[str, ...], list[list[SourceProduct | int]]] = defaultdict(list)
    for product in source.products:
        key = (
            product.package_match_key
            if use_package_equivalence
            else product.match_key
        )
        available[key].append([product, product.quantity])

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
    packages = _template(case, use_package_equivalence=False)
    candidate = RecommendationCandidate(
        recommendation_id=f"history-{case.case_id}",
        rule_id=f"history-{case.case_id}",
        match_type=MATCH_EXACT_STRUCTURE,
        packages=packages,
        source_case_ids=(case.case_id,),
        usage_count=1,
    )
    return apply_recommendation(
        source,
        candidate,
        use_package_equivalence=False,
    )


def _project_template_names(
    source: SourceSnapshot,
    packages: tuple[RecommendationPackage, ...],
) -> tuple[RecommendationPackage, ...]:
    current_names: defaultdict[tuple[str, ...], list[str]] = defaultdict(list)
    for product in source.products:
        names = current_names[product.package_match_key]
        if product.display_name not in names:
            names.append(product.display_name)

    return tuple(
        RecommendationPackage(
            items=tuple(
                RecommendationItem(
                    item.match_key,
                    " / ".join(current_names[item.match_key]) or item.product_name,
                    item.quantity,
                )
                for item in package.items
            )
        )
        for package in packages
    )


def _recommendation_algorithm_version(
    packages: tuple[RecommendationPackage, ...],
) -> int:
    if any(
        _is_package_equivalence_key(item.match_key)
        for package in packages
        for item in package.items
    ):
        return PACKAGE_EQUIVALENT_RECOMMENDATION_ALGORITHM_VERSION
    return RECOMMENDATION_ALGORITHM_VERSION


def _capacity_algorithm_version(
    capacity_signature: tuple[tuple[tuple[str, ...], int], ...],
) -> int:
    if any(_is_package_equivalence_key(key) for key, _ in capacity_signature):
        return PACKAGE_EQUIVALENT_SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION
    return SINGLE_PACKAGE_CAPACITY_ALGORITHM_VERSION


def _composition_algorithm_version(
    packages: tuple[RecommendationPackage, ...],
) -> int:
    if any(
        _is_package_equivalence_key(item.match_key)
        for package in packages
        for item in package.items
    ):
        return PACKAGE_EQUIVALENT_COMPOSITION_ALGORITHM_VERSION
    return HISTORICAL_PACKAGE_COMPOSITION_ALGORITHM_VERSION


def _is_package_equivalence_key(key: tuple[str, ...]) -> bool:
    return bool(key) and key[0] == PACKAGE_EQUIVALENCE_KEY_PREFIX
