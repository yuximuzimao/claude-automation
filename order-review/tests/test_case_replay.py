from order_review.case_replay import build_replay_report
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


def test_same_order_versions_and_rule_adoptions_do_not_inflate_full_samples(
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
    assert report.observed_order_count == 2
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
