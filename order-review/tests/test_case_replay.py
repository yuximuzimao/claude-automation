import json

from order_review.case_replay import (
    OUTCOME_CONFLICT_ACTUAL_INCLUDED,
    OUTCOME_NO_RECOMMENDATION,
    OUTCOME_PACKAGE_COUNT_INEFFICIENT,
    OUTCOME_UNSAFE_SINGLE_PACKAGE,
    ReplayCandidateDetail,
    _classify_replay_outcome,
    _render_markdown,
    build_replay_report,
)
from order_review.case_repository import (
    Decision,
    DecisionSource,
    JsonCaseRepository,
    ShippingMode,
)
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import PackageDraft, SourceSnapshot
from order_review.package_workflow import PackagePlanWorkflow
from order_review.recommendation_events import RecommendationEventStore


def _source(order_number: str, quantity: int = 2) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=(order_number,),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=quantity,
                    merchant_code="CODE-A",
                    spu_id="ITEM-A",
                    sku_id="SKU-A",
                    platform_order_number=order_number,
                )
            ],
        )
    )


def _save(
    repository: JsonCaseRepository,
    source: SourceSnapshot,
    confirmed_at: str,
    *,
    allow_same_snapshot: bool = False,
):
    return repository.confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(DecisionSource.MANUAL),
        confirmed_at=confirmed_at,
        allow_same_snapshot=allow_same_snapshot,
    )


def _split_plan(source: SourceSnapshot):
    product_id = source.products[0].source_product_id
    return (
        PackageDraft.split(source)
        .set_quantity("package-1", product_id, 1, source=source)
        .set_quantity("package-2", product_id, 1, source=source)
        .confirm(source)
    )


def _save_split(
    repository: JsonCaseRepository,
    source: SourceSnapshot,
    confirmed_at: str,
    *,
    allow_same_snapshot: bool = False,
):
    return repository.confirm(
        source,
        _split_plan(source),
        Decision(DecisionSource.MANUAL),
        confirmed_at=confirmed_at,
        allow_same_snapshot=allow_same_snapshot,
    )


def test_replay_does_not_use_target_case_as_its_own_history(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    _save(repository, _source("ORDER-1"), "2026-07-23T01:00:00Z")

    report = build_replay_report(path)

    assert report.replay_targets == 1
    assert report.recommended_targets == 0
    assert report.no_recommendation_targets == 1
    assert report.outcome_counts == {OUTCOME_NO_RECOMMENDATION: 1}
    assert report.target_details[0].outcome == OUTCOME_NO_RECOMMENDATION
    assert [
        item.candidate_count for item in report.target_details[0].stage_attempts
    ] == [0, 0, 0, 0]


def test_replay_only_uses_earlier_independent_orders(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    _save(repository, _source("ORDER-1"), "2026-07-23T01:00:00Z")
    _save(repository, _source("ORDER-2"), "2026-07-23T02:00:00Z")

    report = build_replay_report(path)

    assert report.independent_full_case_orders == 2
    assert report.recommended_targets == 1
    assert report.coverage_rate == 0.5
    assert report.single_candidate_exact_targets == 1
    assert report.actual_in_candidates_targets == 1
    assert report.wrong_recommendation_targets == 0
    exact_metrics = report.match_type_metrics["exact_structure"]
    assert exact_metrics["coverageRate"] == 0.5
    assert exact_metrics["accuracyRate"] == 1.0


def test_replay_aggregates_equivalent_flavor_rows_inside_one_package(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    historical = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-1",),
            products=[
                Product(
                    title="美式咖啡正装",
                    standard_name="美式咖啡正装",
                    short_name="美式咖啡正装",
                    quantity=2,
                    merchant_code="6977987940138",
                    platform_order_number="ORDER-1",
                )
            ],
        )
    )
    current = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-2",),
            products=[
                Product(
                    title="美式咖啡正装",
                    standard_name="美式咖啡正装",
                    short_name="美式咖啡正装",
                    quantity=1,
                    merchant_code="6977987940138",
                    platform_order_number="ORDER-2",
                ),
                Product(
                    title="生椰拿铁正装",
                    standard_name="生椰拿铁正装",
                    short_name="生椰拿铁正装",
                    quantity=1,
                    merchant_code="6979151090014",
                    platform_order_number="ORDER-2",
                ),
            ],
        )
    )
    repository.confirm(
        historical,
        PackageDraft.single_package(historical).confirm(historical),
        Decision(DecisionSource.MANUAL),
        confirmed_at="2026-07-23T01:00:00Z",
    )
    repository.confirm(
        current,
        PackageDraft.single_package(current).confirm(current),
        Decision(DecisionSource.MANUAL),
        confirmed_at="2026-07-23T02:00:00Z",
    )

    report = build_replay_report(path)

    assert report.recommended_targets == 1
    assert report.actual_in_candidates_targets == 1
    assert report.wrong_recommendation_targets == 0


def test_same_order_versions_and_exact_reuse_do_not_inflate_observed_orders(
    tmp_path,
):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    source = _source("ORDER-1")
    _save(repository, source, "2026-07-23T01:00:00Z")
    _save(
        repository,
        source,
        "2026-07-23T02:00:00Z",
        allow_same_snapshot=True,
    )

    workflow = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(
            tmp_path / "events.jsonl",
            session_id="replay-test",
        ),
    )
    workflow.load_order(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-2",),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=2,
                    merchant_code="CODE-A",
                    spu_id="ITEM-A",
                    sku_id="SKU-A",
                    platform_order_number="ORDER-2",
                )
            ],
        )
    )
    workflow.confirm()

    report = build_replay_report(path, event_path=tmp_path / "events.jsonl")

    assert report.complete_case_count == 2
    assert report.independent_full_case_orders == 1
    assert report.observed_order_count == 1
    assert report.replay_targets == 1


def test_replay_identifies_wrong_recommendation_and_later_conflict(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    _save(repository, _source("ORDER-1"), "2026-07-23T01:00:00Z")
    _save_split(repository, _source("ORDER-2"), "2026-07-23T02:00:00Z")
    _save_split(repository, _source("ORDER-3"), "2026-07-23T03:00:00Z")

    report = build_replay_report(path)

    assert report.recommended_targets == 2
    assert report.actual_in_candidates_targets == 1
    assert report.single_candidate_exact_targets == 0
    assert report.conflict_targets == 1
    assert report.wrong_recommendation_targets == 1
    metrics = report.match_type_metrics["exact_structure"]
    assert metrics["coveredTargets"] == 2
    assert metrics["actualIncludedTargets"] == 1
    assert metrics["conflictTargets"] == 1
    assert metrics["wrongTargets"] == 1
    assert metrics["accuracyRate"] == 0.5
    assert report.outcome_counts[OUTCOME_UNSAFE_SINGLE_PACKAGE] == 1
    assert report.outcome_counts[OUTCOME_CONFLICT_ACTUAL_INCLUDED] == 1


def test_replay_classifies_more_candidate_packages_as_possible_inefficiency(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    target = _save_split(
        repository,
        _source("ORDER-TARGET"),
        "2026-07-23T01:00:00Z",
    )
    candidates = (
        ReplayCandidateDetail(
            match_type="historical_package_composition",
            algorithm_version=1,
            packages=("商品A ×1", "商品A ×1", "商品A ×1"),
            source_case_ids=("case-source",),
            matches_actual=False,
        ),
    )

    assert (
        _classify_replay_outcome(target, candidates)
        == OUTCOME_PACKAGE_COUNT_INEFFICIENT
    )


def test_problem_set_validates_named_real_problem_baseline(tmp_path):
    case_path = tmp_path / "cases.json"
    repository = JsonCaseRepository(case_path)
    target = _save(
        repository,
        _source("ORDER-1"),
        "2026-07-23T01:00:00Z",
    )
    problem_path = tmp_path / "problem-set.json"
    problem_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "problems": [
                    {
                        "id": "known-no-recommendation",
                        "label": "首个订单没有历史证据",
                        "targetCaseId": target.case_id,
                        "expectedOutcome": OUTCOME_NO_RECOMMENDATION,
                        "desiredDirection": "保持不推荐",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = build_replay_report(
        case_path,
        problem_set_path=problem_path,
    )

    assert report.problem_set is not None
    assert report.problem_set.valid
    assert report.problem_set.passed_count == 1
    assert report.to_dict()["problemSet"]["valid"] is True
    assert "targetDetails" not in report.to_dict()
    assert report.to_dict(include_details=True)["targetDetails"][0][
        "outcome"
    ] == OUTCOME_NO_RECOMMENDATION


def test_detailed_markdown_explains_actual_candidate_and_stage_path(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    _save(repository, _source("ORDER-1"), "2026-07-23T01:00:00Z")
    _save_split(repository, _source("ORDER-2"), "2026-07-23T02:00:00Z")

    rendered = _render_markdown(
        build_replay_report(path),
        include_details=True,
    )

    assert "## 需要关注的逐单结果" in rendered
    assert "安全错误：误推单包" in rendered
    assert "人工实际：包裹 1" in rendered
    assert "推荐路径：" in rendered
    assert "来源案例：" in rendered


def test_current_maturity_uses_latest_order_version_but_replay_uses_first(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    source = _source("ORDER-VERSIONED")
    _save(repository, source, "2026-07-23T01:00:00Z")
    _save_split(
        repository,
        source,
        "2026-07-23T02:00:00Z",
        allow_same_snapshot=True,
    )

    report = build_replay_report(path)

    assert report.complete_case_count == 2
    assert report.independent_full_case_orders == 1
    assert report.current_final_case_orders == 1
    assert report.replay_targets == 1
    assert report.no_recommendation_targets == 1
    assert report.single_package_cases == 0
    assert report.multi_package_cases == 1


def test_replay_counts_freight_separately_and_excludes_it_from_targets(tmp_path):
    path = tmp_path / "cases.json"
    repository = JsonCaseRepository(path)
    source = _source("ORDER-FREIGHT", quantity=80)
    repository.confirm(
        source,
        PackageDraft.single_package(source).confirm(source),
        Decision(
            DecisionSource.MANUAL,
            shipping_mode=ShippingMode.FREIGHT,
            estimated_package_band="6+",
            shipping_reasons=("manual_judgment", "many_packages"),
        ),
        confirmed_at="2026-07-23T01:00:00Z",
    )

    report = build_replay_report(path)

    assert report.freight_cases == 1
    assert report.single_package_cases == 0
    assert report.multi_package_cases == 0
    assert report.replay_targets == 0
