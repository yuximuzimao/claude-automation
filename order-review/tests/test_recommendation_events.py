from order_review.case_repository import JsonCaseRepository
from order_review.models import OrderSnapshot, Product
from order_review.package_workflow import PackagePlanWorkflow
from order_review.recommendation_events import (
    RecommendationEventStore,
    audit_recommendation_events,
    count_event_types,
    read_recommendation_events,
)


class FailingEventStore:
    def record_shown(self, *_args, **_kwargs):
        raise OSError("event disk failure")

    def record_confirmed(self, *_args, **_kwargs):
        raise OSError("event disk failure")

    def record_abandoned_unknown(self, *_args, **_kwargs):
        raise OSError("event disk failure")


def _order(order_number: str, quantity: int = 2) -> OrderSnapshot:
    return OrderSnapshot(
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


def _seed_history(repository: JsonCaseRepository) -> None:
    workflow = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(
            case_path=repository.path,
            session_id="seed-session",
        ),
    )
    workflow.load_order(_order("ORDER-1"))
    workflow.start_single_package()
    workflow.confirm()


def test_shown_event_is_deduplicated_across_refresh_and_confirmed_direct(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    event_path = tmp_path / "events.jsonl"
    store = RecommendationEventStore(event_path, session_id="review-session")
    workflow = PackagePlanWorkflow(repository, store)

    workflow.load_order(_order("ORDER-2"))
    workflow.load_order(_order("ORDER-2"))
    workflow.confirm()

    counts = count_event_types(read_recommendation_events(event_path))
    assert counts["shown"] == 1
    assert counts["confirmed_direct"] == 1
    assert counts["confirmed_modified"] == 0
    assert counts["abandoned_unknown"] == 0


def test_modified_confirmation_and_unknown_abandonment_are_separate(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    event_path = tmp_path / "events.jsonl"

    modified = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(event_path, session_id="modified-session"),
    )
    modified.load_order(_order("ORDER-2"))
    product = modified.source_snapshot.products[0]
    modified.set_quantity("package-1", product.source_product_id, 1)
    modified.add_package()
    modified.set_quantity("package-2", product.source_product_id, 1)
    modified.confirm()

    abandoned = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(event_path, session_id="abandoned-session"),
    )
    abandoned.load_order(_order("ORDER-3"))
    abandoned.close()

    counts = count_event_types(read_recommendation_events(event_path))
    assert counts["confirmed_modified"] == 1
    assert counts["abandoned_unknown"] == 2
    assert repository.get_rule_stats() == {}


def test_new_session_closes_unfinished_previous_shown_as_unknown(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    event_path = tmp_path / "events.jsonl"
    first = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(event_path, session_id="crashed-session"),
    )
    first.load_order(_order("ORDER-2"))

    RecommendationEventStore(event_path, session_id="next-session")

    counts = count_event_types(read_recommendation_events(event_path))
    assert counts["shown"] == 1
    assert counts["abandoned_unknown"] == 1


def test_event_write_failure_does_not_block_in_memory_exact_reuse(
    tmp_path,
    caplog,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    workflow = PackagePlanWorkflow(repository, FailingEventStore())

    workflow.load_order(_order("ORDER-2"))
    saved = workflow.confirm()

    assert saved is workflow.confirmed_case
    assert workflow.confirmed_plan is not None
    assert workflow.draft is None
    assert len(repository.list_cases()) == 1
    assert len(repository.list_assignments()) == 1
    assert "event disk failure" in workflow.event_warning
    assert "核心案例流程继续" in caplog.text


def test_event_write_failure_cannot_block_refresh_manual_start_or_close(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    workflow = PackagePlanWorkflow(repository, FailingEventStore())

    workflow.load_order(_order("ORDER-2"))
    workflow.load_order(_order("ORDER-3"))
    workflow.start_single_package()
    workflow.close()

    assert workflow.draft is not None
    assert workflow.event_warning.endswith("event disk failure")


def test_event_store_initialization_failure_does_not_block_manual_case(
    tmp_path,
    monkeypatch,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")

    def fail_store(*_args, **_kwargs):
        raise OSError("event init failure")

    monkeypatch.setattr(
        "order_review.package_workflow.RecommendationEventStore",
        fail_store,
    )
    workflow = PackagePlanWorkflow(repository)
    workflow.load_order(_order("ORDER-MANUAL"))
    workflow.start_single_package()

    saved = workflow.confirm()

    assert saved is workflow.confirmed_case
    assert workflow.draft is None
    assert len(repository.list_cases()) == 1
    assert "event init failure" in workflow.event_warning


def test_event_audit_reports_bad_jsonl_line_without_hiding_valid_events(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    _seed_history(repository)
    event_path = tmp_path / "events.jsonl"
    workflow = PackagePlanWorkflow(
        repository,
        RecommendationEventStore(event_path, session_id="audit-session"),
    )
    workflow.load_order(_order("ORDER-2"))
    with event_path.open("a", encoding="utf-8") as handle:
        handle.write("{broken event line}\n")

    report = audit_recommendation_events(event_path)
    values = read_recommendation_events(event_path)

    assert not report.valid
    assert report.event_count == 1
    assert report.invalid_line_count == 1
    assert any(issue.code == "event_json_invalid" for issue in report.issues)
    assert len(values) == 1
