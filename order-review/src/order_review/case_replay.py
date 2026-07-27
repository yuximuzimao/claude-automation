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
from .recommendations import RecommendationCandidate, find_recommendations


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

    @property
    def coverage_rate(self) -> float:
        if self.replay_targets == 0:
            return 0.0
        return self.recommended_targets / self.replay_targets

    def to_dict(self) -> dict[str, Any]:
        return {
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
        }


def build_replay_report(
    case_path: str | Path,
    *,
    event_path: str | Path | None = None,
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
    for target in parcel_representatives:
        prior = [
            case
            for case in cases
            if (case.confirmed_at, case.case_id)
            < (target.confirmed_at, target.case_id)
            and _case_order_key(case) != _case_order_key(target)
        ]
        training = _latest_case_per_order(prior)
        result = find_recommendations(target.source_snapshot, training)
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
    )


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
        items = sorted(
            (
                products[item.source_product_id].match_key,
                item.quantity,
            )
            for item in package.items
        )
        packages.append(items)
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


def _render_markdown(report: ReplayReport) -> str:
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
    return "\n".join(
        [
            "# 审单案例回放与数据成熟度",
            "",
            f"- 完整案例：{report.complete_case_count}",
            (
                "- 历史首次决策订单："
                f"{report.independent_full_case_orders}"
            ),
            f"- 当前最终知识订单：{report.current_final_case_orders}",
            f"- 已观察订单（含规则采用索引）：{report.observed_order_count}",
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
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读回放审单历史并评估数据成熟度")
    parser.add_argument("--path", type=Path, default=default_case_path())
    parser.add_argument("--events", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_replay_report(args.path, event_path=args.events)
    except ValueError as exc:
        print(f"回放失败：{exc}")
        return 1
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
