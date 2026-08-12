from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from .case_repository import ConfirmedCase, JsonCaseRepository, default_case_path
from .case_validation import audit_case_file
from .order_identity import (
    order_structure_signature,
    same_order_signature_key,
    total_product_signature,
)
from .recommendation_events import (
    audit_recommendation_events,
    count_event_types,
    default_event_path,
    read_recommendation_events,
)
from .recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_HISTORICAL_PACKAGE_COMPOSITION,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    MATCH_SINGLE_PACKAGE_TOTAL,
    RecommendationCandidate,
    RecommendationResult,
    find_exact_recommendations,
    find_historical_package_composition_recommendations,
    find_single_package_capacity_recommendations,
    find_single_package_total_recommendations,
)


OUTCOME_MATCHED = "matched"
OUTCOME_UNSAFE_SINGLE_PACKAGE = "unsafe_single_package"
OUTCOME_PACKAGE_COUNT_INEFFICIENT = "package_count_inefficient"
OUTCOME_WRONG_RECOMMENDATION = "wrong_recommendation"
OUTCOME_CONFLICT_ACTUAL_INCLUDED = "conflict_actual_included"
OUTCOME_NO_RECOMMENDATION = "no_recommendation"

OUTCOME_LABELS = {
    OUTCOME_MATCHED: "方案一致",
    OUTCOME_UNSAFE_SINGLE_PACKAGE: "安全错误：误推单包",
    OUTCOME_PACKAGE_COUNT_INEFFICIENT: "可能不优：包裹数偏多",
    OUTCOME_WRONG_RECOMMENDATION: "推荐方案不一致",
    OUTCOME_CONFLICT_ACTUAL_INCLUDED: "正常冲突：实际方案在候选中",
    OUTCOME_NO_RECOMMENDATION: "无推荐",
}

DEFAULT_PROBLEM_SET_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "replay-problem-set.json"
)


@dataclass(frozen=True)
class ReplayStageAttempt:
    match_type: str
    candidate_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "matchType": self.match_type,
            "candidateCount": self.candidate_count,
        }


@dataclass(frozen=True)
class ReplayCandidateDetail:
    match_type: str
    algorithm_version: int
    packages: tuple[str, ...]
    source_case_ids: tuple[str, ...]
    matches_actual: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "matchType": self.match_type,
            "algorithmVersion": self.algorithm_version,
            "packages": list(self.packages),
            "sourceCaseIds": list(self.source_case_ids),
            "matchesActual": self.matches_actual,
        }


@dataclass(frozen=True)
class ReplayTargetDetail:
    target_case_id: str
    confirmed_at: str
    products: tuple[str, ...]
    actual_packages: tuple[str, ...]
    decision_source: str
    recommendation_modified: bool
    confirmed_recommendation_match_type: str
    outcome: str
    advisory_note: str
    stage_attempts: tuple[ReplayStageAttempt, ...]
    candidates: tuple[ReplayCandidateDetail, ...]

    @property
    def outcome_label(self) -> str:
        return OUTCOME_LABELS.get(self.outcome, self.outcome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "targetCaseId": self.target_case_id,
            "confirmedAt": self.confirmed_at,
            "products": list(self.products),
            "actualPackages": list(self.actual_packages),
            "decisionSource": self.decision_source,
            "recommendationModified": self.recommendation_modified,
            "confirmedRecommendationMatchType": (
                self.confirmed_recommendation_match_type
            ),
            "outcome": self.outcome,
            "outcomeLabel": self.outcome_label,
            "advisoryNote": self.advisory_note,
            "stageAttempts": [item.to_dict() for item in self.stage_attempts],
            "candidates": [item.to_dict() for item in self.candidates],
        }


@dataclass(frozen=True)
class ReplayProblemCheck:
    problem_id: str
    label: str
    target_case_id: str
    expected_outcome: str
    actual_outcome: str
    desired_direction: str

    @property
    def passed(self) -> bool:
        return self.actual_outcome == self.expected_outcome

    def to_dict(self) -> dict[str, Any]:
        return {
            "problemId": self.problem_id,
            "label": self.label,
            "targetCaseId": self.target_case_id,
            "expectedOutcome": self.expected_outcome,
            "actualOutcome": self.actual_outcome,
            "desiredDirection": self.desired_direction,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ReplayProblemSetReport:
    path: str
    checks: tuple[ReplayProblemCheck, ...]

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.checks if item.passed)

    @property
    def valid(self) -> bool:
        return bool(self.checks) and self.passed_count == len(self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "valid": self.valid,
            "passedCount": self.passed_count,
            "totalCount": len(self.checks),
            "checks": [item.to_dict() for item in self.checks],
        }


@dataclass(frozen=True)
class ReplayReport:
    case_path: str
    complete_case_count: int
    independent_full_case_orders: int
    current_final_case_orders: int
    observed_order_count: int
    single_package_cases: int
    multi_package_cases: int
    freight_cases: int
    replay_targets: int
    recommended_targets: int
    single_candidate_exact_targets: int
    actual_in_candidates_targets: int
    conflict_targets: int
    wrong_recommendation_targets: int
    no_recommendation_targets: int
    recommendation_match_counts: dict[str, int]
    match_type_metrics: dict[str, dict[str, int | float]]
    event_counts: dict[str, int]
    event_file_valid: bool
    event_invalid_lines: int
    quantity_ladder_groups: int
    single_to_multi_transition_groups: int
    multi_branch_structures: int
    outcome_counts: dict[str, int]
    target_details: tuple[ReplayTargetDetail, ...]
    problem_set: ReplayProblemSetReport | None = None

    @property
    def coverage_rate(self) -> float:
        if self.replay_targets == 0:
            return 0.0
        return self.recommended_targets / self.replay_targets

    def to_dict(self, *, include_details: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "casePath": self.case_path,
            "completeCaseCount": self.complete_case_count,
            "independentFullCaseOrders": self.independent_full_case_orders,
            "currentFinalCaseOrders": self.current_final_case_orders,
            "observedOrderCount": self.observed_order_count,
            "singlePackageCases": self.single_package_cases,
            "multiPackageCases": self.multi_package_cases,
            "freightCases": self.freight_cases,
            "replayTargets": self.replay_targets,
            "recommendedTargets": self.recommended_targets,
            "singleCandidateExactTargets": self.single_candidate_exact_targets,
            "actualInCandidatesTargets": self.actual_in_candidates_targets,
            "conflictTargets": self.conflict_targets,
            "wrongRecommendationTargets": self.wrong_recommendation_targets,
            "noRecommendationTargets": self.no_recommendation_targets,
            "coverageRate": self.coverage_rate,
            "recommendationMatchCounts": self.recommendation_match_counts,
            "matchTypeMetrics": self.match_type_metrics,
            "eventCounts": self.event_counts,
            "eventFileValid": self.event_file_valid,
            "eventInvalidLines": self.event_invalid_lines,
            "quantityLadderGroups": self.quantity_ladder_groups,
            "singleToMultiTransitionGroups": self.single_to_multi_transition_groups,
            "multiBranchStructures": self.multi_branch_structures,
            "outcomeCounts": self.outcome_counts,
            "problemSet": self.problem_set.to_dict() if self.problem_set else None,
        }
        if include_details:
            result["targetDetails"] = [
                item.to_dict() for item in self.target_details
            ]
        return result


def build_replay_report(
    case_path: str | Path,
    *,
    event_path: str | Path | None = None,
    problem_set_path: str | Path | None = None,
) -> ReplayReport:
    path = Path(case_path)
    audit = audit_case_file(path)
    if not audit.valid:
        details = "；".join(issue.message for issue in audit.errors)
        raise ValueError(f"案例健康检查未通过，不能回放：{details}")

    repository = JsonCaseRepository(path)
    cases = sorted(
        repository.list_cases(),
        key=lambda item: (item.confirmed_at, item.case_id),
    )
    assignments = repository.list_assignments()
    representatives = _first_case_per_order(cases)
    current_final_cases = _latest_case_per_order(cases)
    parcel_representatives = [
        case for case in representatives if not case.is_freight
    ]
    current_parcel_cases = [
        case for case in current_final_cases if not case.is_freight
    ]
    observed_orders = {
        _case_order_key(case) for case in representatives
    } | {
        assignment.same_order_signature for assignment in assignments
    }

    recommended = 0
    single_candidate_exact = 0
    actual_in_candidates = 0
    conflicts = 0
    wrong_recommendations = 0
    no_recommendation = 0
    match_counts: dict[str, int] = {}
    match_metrics: dict[str, dict[str, int]] = {}
    target_details: list[ReplayTargetDetail] = []
    outcome_counts: dict[str, int] = {}
    for target in parcel_representatives:
        prior = [
            case
            for case in cases
            if (case.confirmed_at, case.case_id)
            < (target.confirmed_at, target.case_id)
            and _case_order_key(case) != _case_order_key(target)
        ]
        training = _latest_case_per_order(prior)
        result, stage_attempts = _find_recommendations_with_trace(
            target,
            training,
        )
        target_detail = _build_target_detail(target, result, stage_attempts)
        target_details.append(target_detail)
        outcome_counts[target_detail.outcome] = (
            outcome_counts.get(target_detail.outcome, 0) + 1
        )
        if result.candidates:
            recommended += 1
            actual_key = _plan_key(target)
            matching_candidates = [
                candidate
                for candidate in result.candidates
                if _candidate_plan_key(candidate) == actual_key
            ]
            if matching_candidates:
                actual_in_candidates += 1
                if len(result.candidates) == 1:
                    single_candidate_exact += 1
            else:
                wrong_recommendations += 1
            if result.conflict:
                conflicts += 1

            for match_type in {candidate.match_type for candidate in result.candidates}:
                match_counts[match_type] = match_counts.get(match_type, 0) + 1
                metrics = match_metrics.setdefault(
                    match_type,
                    {
                        "coveredTargets": 0,
                        "actualIncludedTargets": 0,
                        "singleCandidateExactTargets": 0,
                        "conflictTargets": 0,
                        "wrongTargets": 0,
                    },
                )
                metrics["coveredTargets"] += 1
                type_candidates = [
                    candidate
                    for candidate in result.candidates
                    if candidate.match_type == match_type
                ]
                type_includes_actual = any(
                    _candidate_plan_key(candidate) == actual_key
                    for candidate in type_candidates
                )
                if type_includes_actual:
                    metrics["actualIncludedTargets"] += 1
                    if len(result.candidates) == 1:
                        metrics["singleCandidateExactTargets"] += 1
                else:
                    metrics["wrongTargets"] += 1
                if result.conflict:
                    metrics["conflictTargets"] += 1
        else:
            no_recommendation += 1

    quantity_groups: dict[tuple[tuple[str, ...], ...], list[ConfirmedCase]] = {}
    for case in current_parcel_cases:
        total = total_product_signature(case.source_snapshot)
        identity_set = tuple(key for key, _ in total)
        quantity_groups.setdefault(identity_set, []).append(case)
    quantity_ladders = sum(
        1
        for group in quantity_groups.values()
        if len(
            {
                tuple(quantity for _, quantity in total_product_signature(case.source_snapshot))
                for case in group
            }
        )
        > 1
    )
    transitions = sum(
        1
        for group in quantity_groups.values()
        if {len(case.package_plan.packages) for case in group}.issuperset({1})
        and any(len(case.package_plan.packages) > 1 for case in group)
    )

    structures: dict[object, set[str]] = {}
    for case in current_parcel_cases:
        signature = order_structure_signature(case.source_snapshot)
        structures.setdefault(signature, set()).add(_plan_key(case))
    multi_branch_structures = sum(
        1 for branches in structures.values() if len(branches) > 1
    )

    resolved_event_path = (
        Path(event_path)
        if event_path is not None
        else default_event_path(path)
    )
    event_audit = audit_recommendation_events(resolved_event_path)
    events = read_recommendation_events(resolved_event_path)
    rendered_match_metrics: dict[str, dict[str, int | float]] = {}
    for match_type, metrics in match_metrics.items():
        covered = metrics["coveredTargets"]
        included = metrics["actualIncludedTargets"]
        rendered_match_metrics[match_type] = {
            **metrics,
                "coverageRate": (
                    covered / len(parcel_representatives)
                    if parcel_representatives
                    else 0.0
                ),
            "accuracyRate": included / covered if covered else 0.0,
        }
    problem_set = (
        _validate_problem_set(Path(problem_set_path), target_details)
        if problem_set_path is not None
        else None
    )
    return ReplayReport(
        case_path=str(path),
        complete_case_count=len(cases),
        independent_full_case_orders=len(representatives),
        current_final_case_orders=len(current_final_cases),
        observed_order_count=len(observed_orders),
        single_package_cases=sum(
            1 for case in current_parcel_cases if len(case.package_plan.packages) == 1
        ),
        multi_package_cases=sum(
            1 for case in current_parcel_cases if len(case.package_plan.packages) > 1
        ),
        freight_cases=sum(1 for case in current_final_cases if case.is_freight),
        replay_targets=len(parcel_representatives),
        recommended_targets=recommended,
        single_candidate_exact_targets=single_candidate_exact,
        actual_in_candidates_targets=actual_in_candidates,
        conflict_targets=conflicts,
        wrong_recommendation_targets=wrong_recommendations,
        no_recommendation_targets=no_recommendation,
        recommendation_match_counts=match_counts,
        match_type_metrics=rendered_match_metrics,
        event_counts=count_event_types(events),
        event_file_valid=event_audit.valid,
        event_invalid_lines=event_audit.invalid_line_count,
        quantity_ladder_groups=quantity_ladders,
        single_to_multi_transition_groups=transitions,
        multi_branch_structures=multi_branch_structures,
        outcome_counts=outcome_counts,
        target_details=tuple(target_details),
        problem_set=problem_set,
    )


def _find_recommendations_with_trace(
    target: ConfirmedCase,
    training: list[ConfirmedCase],
) -> tuple[RecommendationResult, tuple[ReplayStageAttempt, ...]]:
    stages = (
        (MATCH_EXACT_STRUCTURE, find_exact_recommendations),
        (MATCH_SINGLE_PACKAGE_TOTAL, find_single_package_total_recommendations),
        (
            MATCH_HISTORICAL_PACKAGE_COMPOSITION,
            find_historical_package_composition_recommendations,
        ),
        (MATCH_SINGLE_PACKAGE_CAPACITY, find_single_package_capacity_recommendations),
    )
    attempts: list[ReplayStageAttempt] = []
    advisory_result = RecommendationResult(candidates=(), conflict=False)
    for match_type, finder in stages:
        result = finder(target.source_snapshot, training)
        attempts.append(
            ReplayStageAttempt(
                match_type=match_type,
                candidate_count=len(result.candidates),
            )
        )
        if result.candidates:
            return result, tuple(attempts)
        if result.advisory_note:
            advisory_result = result
    return advisory_result, tuple(attempts)


def _build_target_detail(
    target: ConfirmedCase,
    result: RecommendationResult,
    stage_attempts: tuple[ReplayStageAttempt, ...],
) -> ReplayTargetDetail:
    actual_key = _plan_key(target)
    candidate_details = tuple(
        ReplayCandidateDetail(
            match_type=candidate.match_type,
            algorithm_version=candidate.algorithm_version,
            packages=_candidate_package_summaries(candidate),
            source_case_ids=candidate.source_case_ids,
            matches_actual=_candidate_plan_key(candidate) == actual_key,
        )
        for candidate in result.candidates
    )
    return ReplayTargetDetail(
        target_case_id=target.case_id,
        confirmed_at=target.confirmed_at,
        products=_source_product_summaries(target),
        actual_packages=_actual_package_summaries(target),
        decision_source=target.decision.source.value,
        recommendation_modified=target.decision.recommendation_modified,
        confirmed_recommendation_match_type=(
            target.decision.recommendation_match_type or ""
        ),
        outcome=_classify_replay_outcome(target, candidate_details),
        advisory_note=result.advisory_note,
        stage_attempts=stage_attempts,
        candidates=candidate_details,
    )


def _classify_replay_outcome(
    target: ConfirmedCase,
    candidates: tuple[ReplayCandidateDetail, ...],
) -> str:
    if not candidates:
        return OUTCOME_NO_RECOMMENDATION
    if any(candidate.matches_actual for candidate in candidates):
        return (
            OUTCOME_CONFLICT_ACTUAL_INCLUDED
            if len(candidates) > 1
            else OUTCOME_MATCHED
        )

    actual_package_count = len(target.package_plan.packages)
    candidate_package_counts = tuple(len(item.packages) for item in candidates)
    if actual_package_count > 1 and any(
        count == 1 for count in candidate_package_counts
    ):
        return OUTCOME_UNSAFE_SINGLE_PACKAGE
    if (
        candidate_package_counts
        and min(candidate_package_counts) > actual_package_count
    ):
        return OUTCOME_PACKAGE_COUNT_INEFFICIENT
    return OUTCOME_WRONG_RECOMMENDATION


def _source_product_summaries(target: ConfirmedCase) -> tuple[str, ...]:
    totals: dict[str, int] = {}
    for product in target.source_snapshot.products:
        totals[product.display_name] = (
            totals.get(product.display_name, 0) + product.quantity
        )
    return tuple(
        f"{name} ×{quantity}" for name, quantity in sorted(totals.items())
    )


def _actual_package_summaries(target: ConfirmedCase) -> tuple[str, ...]:
    products = target.source_snapshot.product_by_id
    result: list[str] = []
    for package in target.package_plan.packages:
        totals: dict[str, int] = {}
        for item in package.items:
            product = products[item.source_product_id]
            name = item.product_name or product.display_name
            totals[name] = totals.get(name, 0) + item.quantity
        result.append(_render_package_totals(totals))
    return tuple(result)


def _candidate_package_summaries(
    candidate: RecommendationCandidate,
) -> tuple[str, ...]:
    result: list[str] = []
    for package in candidate.packages:
        totals: dict[str, int] = {}
        for item in package.items:
            name = item.product_name or "未命名商品"
            totals[name] = totals.get(name, 0) + item.quantity
        result.append(_render_package_totals(totals))
    return tuple(result)


def _render_package_totals(totals: dict[str, int]) -> str:
    return " + ".join(
        f"{name} ×{quantity}" for name, quantity in sorted(totals.items())
    ) or "空包裹"


def _validate_problem_set(
    path: Path,
    details: list[ReplayTargetDetail],
) -> ReplayProblemSetReport:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"固定问题集无法读取：{path}：{exc}") from exc
    entries = payload.get("problems") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"固定问题集缺少非空 problems 数组：{path}")

    details_by_case = {item.target_case_id: item for item in details}
    checks: list[ReplayProblemCheck] = []
    seen_ids: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError(f"固定问题集包含无效条目：{path}")
        problem_id = str(raw.get("id") or "").strip()
        target_case_id = str(raw.get("targetCaseId") or "").strip()
        expected_outcome = str(raw.get("expectedOutcome") or "").strip()
        if (
            not problem_id
            or problem_id in seen_ids
            or not target_case_id
            or expected_outcome not in OUTCOME_LABELS
        ):
            raise ValueError(f"固定问题集条目标识或分类无效：{path}")
        seen_ids.add(problem_id)
        detail = details_by_case.get(target_case_id)
        checks.append(
            ReplayProblemCheck(
                problem_id=problem_id,
                label=str(raw.get("label") or problem_id),
                target_case_id=target_case_id,
                expected_outcome=expected_outcome,
                actual_outcome=detail.outcome if detail else "missing_target",
                desired_direction=str(raw.get("desiredDirection") or ""),
            )
        )
    return ReplayProblemSetReport(path=str(path), checks=tuple(checks))


def _case_order_key(case: ConfirmedCase) -> str:
    return (
        same_order_signature_key(case.source_snapshot)
        or f"snapshot:{case.source_snapshot.snapshot_id}"
    )


def _first_case_per_order(cases: Iterable[ConfirmedCase]) -> list[ConfirmedCase]:
    first: dict[str, ConfirmedCase] = {}
    for case in cases:
        first.setdefault(_case_order_key(case), case)
    return sorted(first.values(), key=lambda item: (item.confirmed_at, item.case_id))


def _latest_case_per_order(cases: Iterable[ConfirmedCase]) -> list[ConfirmedCase]:
    latest: dict[str, ConfirmedCase] = {}
    for case in cases:
        key = _case_order_key(case)
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
    return list(latest.values())


def _plan_key(case: ConfirmedCase) -> str:
    products = case.source_snapshot.product_by_id
    packages: list[list[tuple[tuple[str, ...], int]]] = []
    for package in case.package_plan.packages:
        totals: dict[tuple[str, ...], int] = {}
        for item in package.items:
            key = products[item.source_product_id].package_match_key
            totals[key] = totals.get(key, 0) + item.quantity
        packages.append(sorted(totals.items()))
    return json.dumps(
        sorted(packages),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _candidate_plan_key(candidate: RecommendationCandidate) -> str:
    packages = [
        sorted(
            (item.match_key, item.quantity)
            for item in package.items
        )
        for package in candidate.packages
    ]
    return json.dumps(
        sorted(packages),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _render_markdown(
    report: ReplayReport,
    *,
    include_details: bool = False,
) -> str:
    match_summary = "、".join(
        f"{key}={value}"
        for key, value in sorted(report.recommendation_match_counts.items())
    ) or "无"
    metric_lines = [
        (
            f"  - {match_type}：覆盖 {metrics['coveredTargets']}"
            f" / {report.replay_targets}（{metrics['coverageRate']:.1%}），"
            f"实际方案命中 {metrics['actualIncludedTargets']}"
            f" / {metrics['coveredTargets']}（{metrics['accuracyRate']:.1%}）"
        )
        for match_type, metrics in sorted(report.match_type_metrics.items())
    ]
    outcome_summary = "、".join(
        f"{OUTCOME_LABELS.get(key, key)}={value}"
        for key, value in sorted(report.outcome_counts.items())
    ) or "无"
    problem_set_line = (
        (
            "- 固定真实问题集："
            f"{report.problem_set.passed_count} / {len(report.problem_set.checks)} "
            + ("分类稳定" if report.problem_set.valid else "存在变化，需复核")
        )
        if report.problem_set is not None
        else "- 固定真实问题集：未加载"
    )
    modified_target_count = sum(
        1 for item in report.target_details if item.recommendation_modified
    )
    lines = [
            "# 审单案例回放与数据成熟度",
            "",
            f"- 完整案例：{report.complete_case_count}",
            (
                "- 历史首次决策订单："
                f"{report.independent_full_case_orders}"
            ),
            f"- 当前最终知识订单：{report.current_final_case_orders}",
            f"- 已观察订单（案例与历史索引去重）：{report.observed_order_count}",
            (
                f"- 当前最终单包 / 多包 / 物流：{report.single_package_cases}"
                f" / {report.multi_package_cases} / {report.freight_cases}"
            ),
            (
                f"- 无泄漏回放覆盖：{report.recommended_targets}"
                f" / {report.replay_targets}（{report.coverage_rate:.1%}）"
            ),
            (
                "- 唯一候选与首次实际方案完全一致："
                f"{report.single_candidate_exact_targets}"
            ),
            (
                "- 候选中包含首次实际方案："
                f"{report.actual_in_candidates_targets}"
            ),
            f"- 推荐冲突、需要人工选择：{report.conflict_targets}",
            (
                "- 有推荐但候选均不符首次实际方案："
                f"{report.wrong_recommendation_targets}"
            ),
            f"- 系统主动不推荐：{report.no_recommendation_targets}",
            f"- 案例决策标记为修改过方案：{modified_target_count}",
            f"- 逐单结果分类：{outcome_summary}",
            problem_set_line,
            f"- 推荐类型：{match_summary}",
            "- 按匹配类型：",
            *(metric_lines or ["  - 无"]),
            f"- 多数量档位商品组合：{report.quantity_ladder_groups}",
            (
                "- 已观察单包到多包临界组合："
                f"{report.single_to_multi_transition_groups}"
            ),
            f"- 同结构多方案分支：{report.multi_branch_structures}",
            (
                "- 推荐事件："
                + "、".join(
                    f"{key}={value}"
                    for key, value in report.event_counts.items()
                )
            ),
            (
                "- 推荐事件文件健康："
                + (
                    "通过"
                    if report.event_file_valid
                    else f"失败（无效行 {report.event_invalid_lines}）"
                )
            ),
            "",
            "说明：历史表现使用每个订单首次确认作为测试目标，并按确认时间隔离"
            "历史、排除同一订单；当前数据成熟度使用每个订单最新有效版本。"
            "同订单版本链不会虚增独立样本。abandoned_unknown 仅表示未知离开，"
            "不作为负反馈。",
        ]
    if include_details:
        lines.extend(_render_attention_details(report))
    return "\n".join(lines)


def _render_attention_details(report: ReplayReport) -> list[str]:
    attention = [
        item
        for item in report.target_details
        if item.outcome not in {OUTCOME_MATCHED, OUTCOME_NO_RECOMMENDATION}
        or bool(item.advisory_note)
    ]
    lines = ["", "## 需要关注的逐单结果", ""]
    if not attention:
        return [*lines, "当前没有错误候选或冲突候选。"]
    match_labels = {
        MATCH_EXACT_STRUCTURE: "精确结构",
        MATCH_SINGLE_PACKAGE_TOTAL: "相同总量单包",
        MATCH_HISTORICAL_PACKAGE_COMPOSITION: "历史包裹组合",
        MATCH_SINGLE_PACKAGE_CAPACITY: "历史较大数量单包参考",
    }
    for detail in attention:
        lines.extend(
            [
                f"### {detail.outcome_label}｜{'、'.join(detail.products)}",
                "",
                f"- 目标案例：`{detail.target_case_id}`",
                "- 人工实际："
                + "；".join(
                    f"包裹 {index}：{value}"
                    for index, value in enumerate(detail.actual_packages, start=1)
                ),
                (
                    "- 人工决策：在系统推荐基础上修改后确认"
                    + (
                        f"（原推荐类型：{detail.confirmed_recommendation_match_type}）"
                        if detail.confirmed_recommendation_match_type
                        else ""
                    )
                    if detail.recommendation_modified
                    else "- 人工决策：未记录为修改推荐"
                ),
                *(
                    [f"- 系统阻断说明：{detail.advisory_note}"]
                    if detail.advisory_note
                    else []
                ),
                "- 推荐路径："
                + " → ".join(
                    f"{match_labels.get(item.match_type, item.match_type)}"
                    f"（{item.candidate_count} 个候选）"
                    for item in detail.stage_attempts
                ),
            ]
        )
        for index, candidate in enumerate(detail.candidates, start=1):
            source_preview = "、".join(candidate.source_case_ids[:3])
            if len(candidate.source_case_ids) > 3:
                source_preview += f" 等 {len(candidate.source_case_ids)} 个"
            lines.append(
                f"- 系统候选 {index}："
                + "；".join(
                    f"包裹 {package_index}：{value}"
                    for package_index, value in enumerate(
                        candidate.packages,
                        start=1,
                    )
                )
                + f"；来源案例：{source_preview or '无'}"
            )
        lines.append("")
    if report.problem_set is not None:
        lines.extend(["## 固定真实问题集", ""])
        for check in report.problem_set.checks:
            lines.append(
                f"- {'✓' if check.passed else '✕'} {check.label}："
                f"当前分类 {OUTCOME_LABELS.get(check.actual_outcome, check.actual_outcome)}；"
                f"改进方向：{check.desired_direction or '待补充'}"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读回放审单历史并评估数据成熟度")
    parser.add_argument("--path", type=Path, default=default_case_path())
    parser.add_argument("--events", type=Path)
    parser.add_argument("--problem-set", type=Path)
    parser.add_argument(
        "--details",
        action="store_true",
        help="输出错误候选、方案不优和正常冲突的逐单证据",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    problem_set_path = args.problem_set
    if (
        problem_set_path is None
        and args.path.expanduser().resolve() == default_case_path().resolve()
        and DEFAULT_PROBLEM_SET_PATH.exists()
    ):
        problem_set_path = DEFAULT_PROBLEM_SET_PATH
    try:
        report = build_replay_report(
            args.path,
            event_path=args.events,
            problem_set_path=problem_set_path,
        )
    except ValueError as exc:
        print(f"回放失败：{exc}")
        return 1
    if args.json:
        print(
            json.dumps(
                report.to_dict(include_details=args.details),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(_render_markdown(report, include_details=args.details))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
