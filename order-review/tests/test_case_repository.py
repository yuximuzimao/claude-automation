import json

import pytest

import order_review.case_repository as case_repository_module
from order_review.case_repository import (
    CaseRepositoryError,
    Decision,
    DecisionSource,
    DuplicateCaseError,
    JsonCaseRepository,
    RuleStats,
    ShippingMode,
)
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import PackageDraft, SourceSnapshot
from order_review.recommendations import (
    MATCH_SINGLE_PACKAGE_CAPACITY,
    apply_recommendation,
    find_exact_recommendations,
    find_freight_reminder,
    find_recommendations,
)


def make_source(*, quantity_a: int = 3, quantity_b: int = 2) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-1",),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=quantity_a,
                    merchant_code="CODE-A",
                    spu_id="ITEM-A",
                    sku_id="SKU-A",
                ),
                Product(
                    title="商品B（简称B）",
                    standard_name="商品B",
                    short_name="简称B",
                    quantity=quantity_b,
                    merchant_code="CODE-B",
                    spu_id="ITEM-B",
                    sku_id="SKU-B",
                ),
            ],
            raw_payload={"complete": True},
        ),
        captured_at="2026-07-22T12:00:00Z",
    )


def split_plan(source: SourceSnapshot):
    first_id, second_id = [item.source_product_id for item in source.products]
    return (
        PackageDraft.split(source)
        .set_quantity("package-1", first_id, source.products[0].quantity, source=source)
        .set_quantity("package-2", second_id, source.products[1].quantity, source=source)
        .confirm(source)
    )


def mixed_plan(source: SourceSnapshot):
    return PackageDraft.single_package(source).confirm(source)


def test_repository_saves_complete_versioned_case_with_atomic_json(tmp_path):
    path = tmp_path / "cases.json"
    source = make_source()
    repository = JsonCaseRepository(path)

    saved = repository.confirm(
        source,
        split_plan(source),
        Decision(source=DecisionSource.MANUAL),
        confirmed_at="2026-07-22T12:30:00Z",
    )

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["schemaVersion"] == 1
    assert stored["cases"][0]["caseId"] == saved.case_id
    assert stored["cases"][0]["sourceSnapshot"]["rawPayload"] == {"complete": True}
    assert stored["cases"][0]["packagePlan"]["packages"][0]["items"][0][
        "sourceProductId"
    ].startswith("product-1-")
    assert repository.list_cases() == [saved]


def test_repository_reuses_snapshot_until_atomic_file_change(tmp_path, monkeypatch):
    path = tmp_path / "cases.json"
    writer = JsonCaseRepository(path)
    first_source = make_source()
    writer.confirm(
        first_source,
        split_plan(first_source),
        Decision(source=DecisionSource.MANUAL),
    )

    repository = JsonCaseRepository(path)
    original_load = repository._load_payload
    load_count = 0

    def counted_load():
        nonlocal load_count
        load_count += 1
        return original_load()

    monkeypatch.setattr(repository, "_load_payload", counted_load)
    first = repository.read_snapshot()
    second = repository.read_snapshot()

    assert load_count == 1
    assert first.cases is second.cases
    first.rule_stats["local-only"] = RuleStats("local-only")
    assert "local-only" not in repository.read_snapshot().rule_stats

    second_source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-2",),
            products=[
                Product(
                    title="商品C（简称C）",
                    standard_name="商品C",
                    short_name="简称C",
                    quantity=1,
                    merchant_code="CODE-C",
                    spu_id="ITEM-C",
                    sku_id="SKU-C",
                )
            ],
        )
    )
    writer.confirm(
        second_source,
        PackageDraft.single_package(second_source).confirm(second_source),
        Decision(source=DecisionSource.MANUAL),
    )

    refreshed = repository.read_snapshot()

    assert load_count == 2
    assert len(refreshed.cases) == 2


def test_repository_reuses_cached_objects_for_the_next_write(tmp_path, monkeypatch):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    first_source = make_source()
    repository.confirm(
        first_source,
        split_plan(first_source),
        Decision(source=DecisionSource.MANUAL),
    )
    repository.read_snapshot()

    def unexpected_reload():
        raise AssertionError("缓存仍有效时不应重新解析完整案例文件")

    monkeypatch.setattr(repository, "_load_payload", unexpected_reload)
    second_source = make_source(quantity_a=4, quantity_b=2)

    repository.confirm(
        second_source,
        split_plan(second_source),
        Decision(source=DecisionSource.MANUAL),
        allow_same_snapshot=True,
    )

    assert len(repository.list_cases()) == 2


def test_successful_write_runs_best_effort_heap_cleanup(tmp_path, monkeypatch):
    cleanup_calls = 0

    def record_cleanup():
        nonlocal cleanup_calls
        cleanup_calls += 1

    monkeypatch.setattr(
        case_repository_module,
        "_release_unused_heap_memory",
        record_cleanup,
    )
    repository = JsonCaseRepository(tmp_path / "cases.json")
    source = make_source()

    repository.confirm(
        source,
        split_plan(source),
        Decision(source=DecisionSource.MANUAL),
    )

    assert cleanup_calls == 1


def test_repository_detects_repeated_confirmation_of_same_snapshot(tmp_path):
    source = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(source, split_plan(source), Decision(DecisionSource.MANUAL))

    with pytest.raises(DuplicateCaseError, match="已经确认过"):
        repository.confirm(source, mixed_plan(source), Decision(DecisionSource.MANUAL))

    assert len(repository.list_cases()) == 1


def test_repository_does_not_report_success_when_persistence_fails(tmp_path, monkeypatch):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    source = make_source()

    def fail(_cases, _assignments, _stats):
        raise OSError("disk full")

    monkeypatch.setattr(repository, "_atomic_write_state", fail)
    with pytest.raises(OSError, match="disk full"):
        repository.confirm(source, split_plan(source), Decision(DecisionSource.MANUAL))

    assert not repository.path.exists()


def test_repository_rejects_corrupted_case_quantities(tmp_path):
    source = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    case = repository.confirm(
        source,
        split_plan(source),
        Decision(DecisionSource.MANUAL),
    ).to_dict()
    case["packagePlan"]["packages"][0]["items"][0]["quantity"] = -1
    repository.path.write_text(
        json.dumps({"schemaVersion": 1, "cases": [case]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(CaseRepositoryError, match="包裹商品数量必须大于 0"):
        repository.list_cases()


def test_exact_recommendation_matches_same_combination_and_can_be_applied(tmp_path):
    historical = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    saved = repository.confirm(
        historical,
        split_plan(historical),
        Decision(DecisionSource.MANUAL),
    )
    current = make_source()

    result = find_exact_recommendations(current, repository.list_cases())
    draft = apply_recommendation(current, result.candidates[0])

    assert result.conflict is False
    assert result.candidates[0].source_case_ids == (saved.case_id,)
    assert result.candidates[0].usage_count == 1
    assert len(draft.confirm(current).packages) == 2


def test_recommendation_ignores_non_exact_order_combination(tmp_path):
    historical = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(
        historical,
        split_plan(historical),
        Decision(DecisionSource.MANUAL),
    )

    result = find_exact_recommendations(make_source(quantity_a=4), repository.list_cases())

    assert result.candidates == ()
    assert result.conflict is False


def test_single_package_capacity_recommendation_projects_current_lower_quantities(
    tmp_path,
):
    historical = make_source(quantity_a=4, quantity_b=3)
    repository = JsonCaseRepository(tmp_path / "cases.json")
    saved = repository.confirm(
        historical,
        mixed_plan(historical),
        Decision(DecisionSource.MANUAL),
    )
    current = make_source(quantity_a=3, quantity_b=2)

    result = find_recommendations(current, repository.list_cases())
    candidate = result.candidates[0]
    draft = apply_recommendation(current, candidate)

    assert result.conflict is False
    assert candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY
    assert candidate.algorithm_version == 3
    assert candidate.source_case_ids == (saved.case_id,)
    assert "历史较大数量单包参考" in candidate.quantity_note
    assert "不是连续容量结论" in candidate.quantity_note
    assert candidate.packages[0].items[0].quantity == 3
    assert candidate.packages[0].items[1].quantity == 2
    assert draft.confirm(current).total_quantity == 5


def test_single_package_capacity_recommendation_rejects_any_quantity_over_history(
    tmp_path,
):
    historical = make_source(quantity_a=4, quantity_b=3)
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(
        historical,
        mixed_plan(historical),
        Decision(DecisionSource.MANUAL),
    )

    result = find_recommendations(
        make_source(quantity_a=5, quantity_b=2),
        repository.list_cases(),
    )

    assert result.candidates == ()


def test_single_package_capacity_recommendation_does_not_learn_from_multi_package(
    tmp_path,
):
    historical = make_source(quantity_a=4, quantity_b=3)
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(
        historical,
        split_plan(historical),
        Decision(DecisionSource.MANUAL),
    )

    result = find_recommendations(
        make_source(quantity_a=3, quantity_b=2),
        repository.list_cases(),
    )

    assert result.candidates == ()


def test_freight_case_only_triggers_reminder_and_never_package_recommendation(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = make_source(quantity_a=40, quantity_b=40)
    saved = repository.confirm(
        historical,
        mixed_plan(historical),
        Decision(
            DecisionSource.MANUAL,
            shipping_mode=ShippingMode.FREIGHT,
            estimated_package_band="6+",
            shipping_reasons=("manual_judgment", "many_packages"),
        ),
    )

    exact_current = make_source(quantity_a=40, quantity_b=40)
    exact_result = find_recommendations(exact_current, repository.list_cases())
    reminder = find_freight_reminder(exact_current, repository.list_cases())
    lower_result = find_recommendations(
        make_source(quantity_a=3, quantity_b=2),
        repository.list_cases(),
    )

    assert exact_result.candidates == ()
    assert lower_result.candidates == ()
    assert reminder is not None
    assert reminder.source_case_ids == (saved.case_id,)
    assert reminder.has_history
    assert reminder.product_kind_count == 2
    assert "系统只按总件数和历史案例提醒，不会估算包裹数" in reminder.message


def test_single_package_capacity_recommendation_uses_closest_covering_capacity(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    uneven_capacity = make_source(quantity_a=5, quantity_b=2)
    balanced_capacity = make_source(quantity_a=4, quantity_b=3)
    repository.confirm(
        uneven_capacity,
        mixed_plan(uneven_capacity),
        Decision(DecisionSource.MANUAL),
    )
    closest = repository.confirm(
        balanced_capacity,
        mixed_plan(balanced_capacity),
        Decision(DecisionSource.MANUAL),
    )

    result = find_recommendations(
        make_source(quantity_a=3, quantity_b=2),
        repository.list_cases(),
    )

    candidate = result.candidates[0]
    assert candidate.source_case_ids == (closest.case_id,)
    assert "简称A ×4" in candidate.quantity_note
    assert "简称B ×3" in candidate.quantity_note


def test_exact_recommendation_preserves_source_order_grouping(tmp_path):
    historical = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(
        historical,
        split_plan(historical),
        Decision(DecisionSource.MANUAL),
    )
    current = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=3,
                    merchant_code="CODE-A",
                    spu_id="ITEM-A",
                    sku_id="SKU-A",
                    platform_order_number="PLATFORM-1",
                ),
                Product(
                    title="商品B（简称B）",
                    standard_name="商品B",
                    short_name="简称B",
                    quantity=2,
                    merchant_code="CODE-B",
                    spu_id="ITEM-B",
                    sku_id="SKU-B",
                    platform_order_number="PLATFORM-2",
                ),
            ],
        )
    )

    result = find_exact_recommendations(current, repository.list_cases())

    assert result.candidates == ()


def test_package_number_swaps_do_not_create_a_false_conflict(tmp_path):
    source = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    first_plan = split_plan(source)
    reversed_plan = type(first_plan)(packages=tuple(reversed(first_plan.packages)))
    repository.confirm(
        source,
        first_plan,
        Decision(DecisionSource.MANUAL),
        allow_same_snapshot=True,
    )
    repository.confirm(
        source,
        reversed_plan,
        Decision(DecisionSource.MANUAL),
        allow_same_snapshot=True,
    )

    result = find_exact_recommendations(make_source(), repository.list_cases())

    assert result.conflict is False
    assert len(result.candidates) == 1
    assert result.candidates[0].usage_count == 2


def test_conflicting_history_returns_all_candidates_without_silent_selection(tmp_path):
    source = make_source()
    repository = JsonCaseRepository(tmp_path / "cases.json")
    repository.confirm(
        source,
        split_plan(source),
        Decision(DecisionSource.MANUAL),
        allow_same_snapshot=True,
    )
    repository.confirm(
        source,
        mixed_plan(source),
        Decision(DecisionSource.MANUAL),
        allow_same_snapshot=True,
    )

    result = find_exact_recommendations(make_source(), repository.list_cases())

    assert result.conflict is True
    assert len(result.candidates) == 2
    assert {len(candidate.packages) for candidate in result.candidates} == {1, 2}
