import pytest

from order_review.case_repository import (
    Decision,
    DecisionSource,
    JsonCaseRepository,
    ShippingMode,
)
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    DraftSnapshotMismatchError,
    PackageDraft,
    PackagePlanValidationError,
    SourceSnapshot,
)
from order_review.package_workflow import PackagePlanWorkflow
from order_review.recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_HISTORICAL_PACKAGE_COMPOSITION,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    MATCH_SINGLE_PACKAGE_TOTAL,
    _find_minimum_composition_solutions,
)


def make_product(name: str, quantity: int, order_number: str) -> Product:
    return Product(
        title=f"商品{name}（简称{name}）",
        standard_name=f"商品{name}",
        short_name=f"简称{name}",
        quantity=quantity,
        merchant_code=f"CODE-{name}",
        spu_id=f"ITEM-{name}",
        sku_id=f"SKU-{name}",
        platform_order_number=order_number,
    )


def make_order(
    order_number: str = "ORDER-1",
    quantity: int = 2,
    *,
    has_suite_action: bool = False,
) -> OrderSnapshot:
    return OrderSnapshot(
        is_expanded=True,
        order_numbers=(order_number,),
        products=[make_product("A", quantity, order_number)],
        has_suite_action=has_suite_action,
        raw_payload={"orderNumber": order_number},
    )


def make_grouped_order(groups: list[tuple[str, list[tuple[str, int]]]]) -> OrderSnapshot:
    return OrderSnapshot(
        is_expanded=True,
        order_numbers=tuple(order_number for order_number, _ in groups),
        products=[
            make_product(name, quantity, order_number)
            for order_number, items in groups
            for name, quantity in items
        ],
    )


def save_standard_module_evidence(
    repository: JsonCaseRepository,
    *,
    name: str,
    quantity: int,
    prefix: str,
) -> None:
    for index in range(3):
        items = [(name, quantity)]
        if index == 2:
            items.append((f"{name}-边界商品", 1))
        source = SourceSnapshot.from_order_snapshot(
            make_grouped_order([(f"{prefix}-{index}", items)])
        )
        if index < 2:
            plan = PackageDraft.single_package(source).confirm(source)
        else:
            first, second = source.products
            plan = (
                PackageDraft.split(source)
                .set_quantity(
                    "package-1",
                    first.source_product_id,
                    first.quantity,
                    source=source,
                )
                .set_quantity(
                    "package-2",
                    second.source_product_id,
                    second.quantity,
                    source=source,
                )
                .confirm(source)
            )
        repository.confirm(
            source,
            plan,
            Decision(source=DecisionSource.MANUAL),
        )


def save_combo_module_evidence(
    repository: JsonCaseRepository,
    *,
    quantities: tuple[int, int],
    prefix: str,
) -> None:
    for index in range(3):
        items = [("A", quantities[0]), ("B", quantities[1])]
        if index == 2:
            items.append((f"{prefix}-边界商品", 1))
        source = SourceSnapshot.from_order_snapshot(
            make_grouped_order([(f"{prefix}-{index}", items)])
        )
        if index < 2:
            plan = PackageDraft.single_package(source).confirm(source)
        else:
            first, second, boundary = source.products
            plan = (
                PackageDraft.split(source)
                .set_quantity(
                    "package-1",
                    first.source_product_id,
                    first.quantity,
                    source=source,
                )
                .set_quantity(
                    "package-1",
                    second.source_product_id,
                    second.quantity,
                    source=source,
                )
                .set_quantity(
                    "package-2",
                    boundary.source_product_id,
                    boundary.quantity,
                    source=source,
                )
                .confirm(source)
            )
        repository.confirm(
            source,
            plan,
            Decision(source=DecisionSource.MANUAL),
        )


def test_refresh_invalidates_unconfirmed_draft_even_when_order_content_is_same(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_split()
    assert workflow.draft is not None

    workflow.load_order(make_order())

    assert workflow.draft is None
    assert workflow.confirmed_case is None


def test_load_order_reads_case_repository_once(tmp_path, monkeypatch):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    original_load = repository._load_payload
    load_count = 0

    def counted_load():
        nonlocal load_count
        load_count += 1
        return original_load()

    monkeypatch.setattr(repository, "_load_payload", counted_load)
    workflow = PackagePlanWorkflow(repository)

    workflow.load_order(make_order())

    assert load_count == 1


def test_target_order_change_invalidates_old_draft(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order("ORDER-1"))
    workflow.start_single_package()
    stale_draft = workflow.draft

    workflow.load_order(make_order("ORDER-2"))

    with pytest.raises(DraftSnapshotMismatchError):
        stale_draft.confirm(workflow.source_snapshot)  # type: ignore[union-attr]


def test_manual_confirmation_records_manual_source_and_assignment(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    workflow = PackagePlanWorkflow(repository)
    workflow.load_order(make_order())
    workflow.start_single_package()

    saved = workflow.confirm()

    assert saved.decision.source is DecisionSource.MANUAL
    assert workflow.confirmed_case == saved
    assert workflow.confirmed_plan is not None
    assert len(repository.list_cases()) == 1
    assert len(repository.list_assignments()) == 1


def test_total_quantity_one_non_suite_builds_direct_plan_without_saving(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    workflow = PackagePlanWorkflow(repository)

    workflow.load_order(make_order(quantity=1))

    assert workflow.draft is None
    assert workflow.direct_single_item_plan is not None
    assert len(workflow.direct_single_item_plan.packages) == 1
    assert workflow.direct_single_item_plan.total_quantity == 1
    assert "不保存方案或规则采用" in workflow.load_notice
    assert workflow.confirmed_case is None
    assert repository.list_cases() == []
    assert repository.list_assignments() == []


def test_total_quantity_one_ignores_exact_history_adoption_write(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical_source = SourceSnapshot.from_order_snapshot(
        make_order("ORDER-1", quantity=1)
    )
    repository.confirm(
        historical_source,
        PackageDraft.single_package(historical_source).confirm(historical_source),
        Decision(source=DecisionSource.MANUAL),
    )

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2", quantity=1))

    assert current.direct_single_item_plan is not None
    assert current.auto_adopted_recommendation is False
    assert current.selected_recommendation is None
    assert len(repository.list_cases()) == 1
    assert len(repository.list_assignments()) == 1


def test_total_quantity_one_skips_capacity_candidate_and_uses_direct_plan(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1", quantity=2))
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2", quantity=1))

    assert current.direct_single_item_plan is not None
    assert current.auto_adopted_recommendation is False
    assert current.recommendations.candidates == ()
    assert "可直接审核" in current.load_notice


def test_total_quantity_one_suite_does_not_default_to_single_package(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))

    workflow.load_order(make_order(quantity=1, has_suite_action=True))

    assert workflow.draft is None
    assert workflow.direct_single_item_plan is None
    assert workflow.load_notice == ""


def test_freight_confirmation_is_independent_and_restores_as_freight(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    workflow = PackagePlanWorkflow(repository)
    workflow.load_order(make_order("ORDER-FREIGHT", quantity=80))
    assert workflow.freight_reminder is not None

    workflow.start_freight()
    saved = workflow.confirm_freight(
        estimated_package_band="6+",
        shipping_reasons=("manual_judgment", "many_packages"),
    )

    assert saved.decision.shipping_mode is ShippingMode.FREIGHT
    assert saved.decision.estimated_package_band == "6+"
    assert saved.decision.shipping_reasons == (
        "manual_judgment",
        "many_packages",
    )
    assert workflow.confirmed_plan is None

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(make_order("ORDER-FREIGHT", quantity=80))
    assert repeated.historical_case == saved
    assert repeated.historical_plan is None
    assert "物流发货" in repeated.load_notice


def test_single_package_reset_restores_the_initial_full_allocation(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_single_package()
    product = workflow.source_snapshot.products[0]
    workflow.set_quantity("package-1", product.source_product_id, 1)

    workflow.reset()

    assert workflow.draft.allocated_quantity(product.source_product_id) == 2
    assert workflow.remaining_quantity == 0


def test_add_package_requires_unassigned_quantity(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_single_package()

    with pytest.raises(PackagePlanValidationError, match="先从现有包裹退回商品"):
        workflow.add_package()

    product = workflow.source_snapshot.products[0]
    workflow.set_quantity("package-1", product.source_product_id, 1)
    workflow.add_package()

    assert len(workflow.draft.packages) == 2
    assert workflow.remaining_quantity == 1


def test_split_starts_with_one_package_and_requires_allocating_it_before_next(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_split()

    assert len(workflow.draft.packages) == 1
    with pytest.raises(PackagePlanValidationError, match="先给当前空包裹分配商品"):
        workflow.add_package()

    product = workflow.source_snapshot.products[0]
    workflow.set_quantity("package-1", product.source_product_id, 1)
    workflow.add_package()
    assert len(workflow.draft.packages) == 2


def test_fill_package_with_remaining_moves_every_unassigned_product_at_once(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(
        make_grouped_order(
            [
                ("ORDER-1", [("A", 3)]),
                ("ORDER-2", [("B", 4)]),
            ]
        )
    )
    workflow.start_split()
    first, second = workflow.source_snapshot.products
    workflow.set_quantity("package-1", first.source_product_id, 1)
    workflow.add_package()

    workflow.fill_package_with_remaining("package-2")

    assert workflow.remaining_quantity == 0
    assert workflow.draft.allocated_quantity(first.source_product_id) == 3
    assert workflow.draft.allocated_quantity(second.source_product_id) == 4
    second_package = workflow.draft.packages[1]
    assert {
        item.source_product_id: item.quantity for item in second_package.items
    } == {
        first.source_product_id: 2,
        second.source_product_id: 4,
    }


def test_save_remaining_creates_final_package_instead_of_expanding_current_one(
    tmp_path,
):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(
        make_grouped_order(
            [
                ("ORDER-1", [("A", 7)]),
                ("ORDER-2", [("A", 7)]),
            ]
        )
    )
    workflow.start_split()
    first, second = workflow.source_snapshot.products
    workflow.set_quantity("package-1", first.source_product_id, 7)

    moved, target_package_id, created = workflow.move_remaining_to_final_package()

    assert (moved, target_package_id, created) == (7, "package-2", True)
    assert workflow.remaining_quantity == 0
    assert [package.total_quantity for package in workflow.draft.packages] == [7, 7]
    assert [
        {item.source_product_id: item.quantity for item in package.items}
        for package in workflow.draft.packages
    ] == [
        {first.source_product_id: 7},
        {second.source_product_id: 7},
    ]


def test_save_remaining_reuses_existing_empty_final_package(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order(quantity=10))
    workflow.start_split()
    product = workflow.source_snapshot.products[0]
    workflow.set_quantity("package-1", product.source_product_id, 4)
    workflow.add_package()

    moved, target_package_id, created = workflow.move_remaining_to_final_package()

    assert (moved, target_package_id, created) == (6, "package-2", False)
    assert [package.total_quantity for package in workflow.draft.packages] == [4, 6]


def test_save_remaining_does_not_reuse_an_empty_middle_package(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order(quantity=10))
    workflow.start_split()
    product = workflow.source_snapshot.products[0]
    workflow.set_quantity("package-1", product.source_product_id, 3)
    workflow.add_package()
    workflow.set_quantity("package-2", product.source_product_id, 3)
    workflow.add_package()
    workflow.set_quantity("package-3", product.source_product_id, 2)
    workflow.set_quantity("package-2", product.source_product_id, 0)

    moved, target_package_id, created = workflow.move_remaining_to_final_package()

    assert (moved, target_package_id, created) == (5, "package-4", True)
    assert not workflow.draft.packages[1].items
    assert workflow.draft.packages[-1].total_quantity == 5


def test_last_package_cannot_be_deleted(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_split()

    with pytest.raises(PackagePlanValidationError, match="至少需要保留一个包裹"):
        workflow.remove_package("package-1")


def test_same_order_restores_saved_plan_and_merges_duplicate_rows(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    first = PackagePlanWorkflow(repository)
    first.load_order(make_order("ORDER-X", quantity=2))
    first.start_single_package()
    saved = first.confirm()

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-X",),
            products=[
                make_product("A", 1, "ORDER-X"),
                make_product("A", 1, "ORDER-X"),
            ],
        )
    )

    assert repeated.historical_case == saved
    assert repeated.historical_plan is not None
    assert repeated.draft is None
    assert repeated.recommendations.candidates == ()
    assert len(repeated.historical_plan.packages) == 1
    assert repeated.historical_plan.total_quantity == 2


def test_editing_same_order_saves_linked_order_version(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    first = PackagePlanWorkflow(repository)
    first.load_order(make_order())
    first.start_single_package()
    version_one = first.confirm()

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(make_order())
    repeated.edit_historical_plan()
    product_id = repeated.source_snapshot.products[0].source_product_id
    repeated.set_quantity("package-1", product_id, 1)
    repeated.add_package()
    repeated.set_quantity("package-2", product_id, 1)
    version_two = repeated.confirm()

    assert version_two.decision.source is DecisionSource.ORDER_VERSION
    assert version_two.previous_case_id == version_one.case_id
    assert version_two.order_version == 2
    assert len(repository.list_cases()) == 2
    assert [item.version for item in repository.list_assignments()] == [1, 2]

    latest = PackagePlanWorkflow(repository)
    latest.load_order(make_order())
    assert latest.historical_case == version_two
    assert len(latest.historical_plan.packages) == 2


def test_different_order_exact_rule_is_auto_adopted_without_duplicate_case(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1"))
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2"))

    assert current.draft is not None
    assert current.auto_adopted_recommendation is True
    assert current.selected_recommendation.match_type == MATCH_EXACT_STRUCTURE
    assert current.recommendation_modified is False
    assert "可直接审核或继续修改" in current.load_notice

    product = current.source_snapshot.products[0]
    current.set_quantity("package-1", product.source_product_id, 2)
    assert current.recommendation_modified is False

    current.confirm()

    assert len(repository.list_cases()) == 1
    assert len(repository.list_assignments()) == 1
    assert repository.get_rule_stats() == {}


def test_exact_reuse_can_later_save_modified_current_order_as_new_case(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1"))
    historical.start_single_package()
    source_case = historical.confirm()

    adopted = PackagePlanWorkflow(repository)
    adopted.load_order(make_order("ORDER-2"))
    adopted.confirm()

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(make_order("ORDER-2"))
    assert repeated.historical_case is None
    assert repeated.draft is not None
    product_id = repeated.source_snapshot.products[0].source_product_id
    repeated.set_quantity("package-1", product_id, 1)
    repeated.add_package()
    repeated.set_quantity("package-2", product_id, 1)
    version_two = repeated.confirm()

    assert version_two.previous_case_id is None
    assert version_two.order_version == 1
    assert version_two.source_snapshot.platform_order_numbers == ("ORDER-2",)
    latest = PackagePlanWorkflow(repository)
    latest.load_order(make_order("ORDER-2"))
    assert latest.historical_case == version_two


def test_modified_exact_rule_saves_new_branch_without_usage_stat(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1"))
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2"))
    product_id = current.source_snapshot.products[0].source_product_id
    current.set_quantity("package-1", product_id, 1)
    current.add_package()
    current.set_quantity("package-2", product_id, 1)
    saved = current.confirm()

    assert saved.decision.source is DecisionSource.RECOMMENDED_MODIFIED
    assert saved.decision.recommendation_modified is True
    assert len(repository.list_cases()) == 2
    assert repository.get_rule_stats() == {}


def test_single_package_rule_can_cross_different_suborder_structure(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(
        make_grouped_order(
            [("ORDER-1", [("A", 1)]), ("ORDER-2", [("B", 1)])]
        )
    )
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(
        make_grouped_order([("ORDER-3", [("A", 1), ("B", 1)])])
    )

    assert current.draft is not None
    assert current.selected_recommendation.match_type == MATCH_SINGLE_PACKAGE_TOTAL
    assert len(current.draft.packages) == 1


def test_historical_packages_can_exactly_compose_an_unseen_order(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    save_standard_module_evidence(
        repository,
        name="A",
        quantity=2,
        prefix="ORDER-A",
    )
    save_standard_module_evidence(
        repository,
        name="B",
        quantity=3,
        prefix="ORDER-B",
    )

    current = PackagePlanWorkflow(repository)
    current.load_order(
        make_grouped_order([("ORDER-C", [("A", 2), ("B", 3)])])
    )

    assert current.draft is not None
    assert current.auto_adopted_recommendation is True
    assert len(current.recommendations.candidates) == 1
    candidate = current.selected_recommendation
    assert candidate.match_type == MATCH_HISTORICAL_PACKAGE_COMPOSITION
    assert len(candidate.packages) == 2
    assert "未使用容量或比例推算" in candidate.quantity_note

    assert sorted(package.total_quantity for package in current.draft.packages) == [2, 3]
    saved = current.confirm()

    assert saved.decision.source is DecisionSource.RECOMMENDED_ACCEPTED
    assert (
        saved.decision.recommendation_match_type
        == MATCH_HISTORICAL_PACKAGE_COMPOSITION
    )
    assert len(repository.list_cases()) == 7
    assert "历史包裹组合案例" in current.confirmation_note


@pytest.mark.parametrize(
    "copy_count,expected_packages",
    (
        (3, ((6, 2), (3, 1))),
        (4, ((6, 2), (6, 2))),
        (5, ((6, 2), (6, 2), (3, 1))),
        (6, ((6, 2), (6, 2), (6, 2))),
    ),
)
def test_historical_package_modules_can_repeat_for_exact_copy_counts(
    tmp_path,
    copy_count,
    expected_packages,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    save_combo_module_evidence(
        repository,
        quantities=(6, 2),
        prefix="DOUBLE",
    )
    save_combo_module_evidence(
        repository,
        quantities=(3, 1),
        prefix="SINGLE",
    )

    current = PackagePlanWorkflow(repository)
    current.load_order(
        make_grouped_order(
            [("CURRENT", [("A", 3 * copy_count), ("B", copy_count)])]
        )
    )

    assert current.auto_adopted_recommendation is True
    assert current.selected_recommendation.match_type == (
        MATCH_HISTORICAL_PACKAGE_COMPOSITION
    )
    source = current.source_snapshot
    projected = []
    for package in current.draft.packages:
        quantities = {
            source.product_by_id[item.source_product_id].merchant_code: item.quantity
            for item in package.items
        }
        projected.append((quantities["CODE-A"], quantities["CODE-B"]))
    assert tuple(sorted(projected, reverse=True)) == tuple(
        sorted(expected_packages, reverse=True)
    )
    assert "可直接审核或继续修改" in current.load_notice


def test_historical_package_composition_search_exposes_minimum_conflicts():
    solutions = _find_minimum_composition_solutions(
        (1, 1, 1, 1),
        (
            (1, 1, 0, 0),
            (0, 0, 1, 1),
            (1, 0, 1, 0),
            (0, 1, 0, 1),
        ),
    )

    assert set(solutions) == {(0, 1), (2, 3)}


def test_historical_package_composition_does_not_scale_or_exceed_five_packages(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    save_standard_module_evidence(
        repository,
        name="A",
        quantity=2,
        prefix="ORDER-A",
    )

    not_exact = PackagePlanWorkflow(repository)
    not_exact.load_order(make_order("ORDER-2", quantity=3))
    assert not_exact.recommendations.candidates == ()

    assert (
        _find_minimum_composition_solutions(
            (1, 1, 1, 1, 1, 1),
            (
                (1, 0, 0, 0, 0, 0),
                (0, 1, 0, 0, 0, 0),
                (0, 0, 1, 0, 0, 0),
                (0, 0, 0, 1, 0, 0),
                (0, 0, 0, 0, 1, 0),
                (0, 0, 0, 0, 0, 1),
            ),
        )
        == ()
    )


def test_capacity_recommendation_waits_for_user_and_saves_current_quantity_case(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1", quantity=4))
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2", quantity=3))

    assert current.draft is None
    assert current.auto_adopted_recommendation is False
    assert len(current.recommendations.candidates) == 1
    candidate = current.recommendations.candidates[0]
    assert candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY

    current.adopt_recommendation(candidate.recommendation_id)
    assert current.draft is not None
    assert sum(package.total_quantity for package in current.draft.packages) == 3
    saved = current.confirm()

    assert saved.decision.source is DecisionSource.RECOMMENDED_ACCEPTED
    assert saved.decision.recommendation_match_type == MATCH_SINGLE_PACKAGE_CAPACITY
    assert saved.source_snapshot.products[0].quantity == 3
    assert len(repository.list_cases()) == 2
    assert repository.get_rule_stats() == {}

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(make_order("ORDER-2", quantity=3))
    assert repeated.historical_case == saved
    assert repeated.historical_plan is not None
    assert repeated.historical_plan.total_quantity == 3


def test_capacity_recommendation_is_blocked_after_real_multi_package_counterexample(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")

    larger_single = PackagePlanWorkflow(repository)
    larger_single.load_order(make_order("ORDER-SINGLE", quantity=18))
    larger_single.start_single_package()
    larger_single.confirm()

    smaller_multi = PackagePlanWorkflow(repository)
    smaller_multi.load_order(make_order("ORDER-MULTI", quantity=9))
    smaller_multi.start_split()
    product_id = smaller_multi.source_snapshot.products[0].source_product_id
    smaller_multi.set_quantity("package-1", product_id, 6)
    smaller_multi.add_package()
    smaller_multi.set_quantity("package-2", product_id, 3)
    smaller_multi.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-CURRENT", quantity=8))

    assert current.recommendations.candidates == ()
    assert "历史证据互相冲突" in current.recommendations.advisory_note
    assert "简称A ×18 曾单包" in current.recommendations.advisory_note
    assert "简称A ×9 实际用了 2 个包裹" in current.recommendations.advisory_note
    assert "系统已停止外推单包" in current.recommendations.advisory_note


def test_same_total_with_different_suborder_structure_does_not_use_one_off_modules(
    tmp_path,
):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(
        make_grouped_order(
            [
                ("ORDER-1", [("A", 2)]),
                ("ORDER-2", [("B", 2)]),
                ("ORDER-3", [("C", 2)]),
            ]
        )
    )
    historical.start_split()
    source = historical.source_snapshot
    for index, product in enumerate(source.products):
        package_id = historical.draft.packages[-1].package_id
        historical.set_quantity(
            package_id, product.source_product_id, product.quantity
        )
        if index < len(source.products) - 1:
            historical.add_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(
        make_grouped_order(
            [
                ("ORDER-4", [("A", 1), ("B", 1)]),
                ("ORDER-5", [("B", 1), ("C", 1)]),
                ("ORDER-6", [("A", 1), ("C", 1)]),
            ]
        )
    )

    assert current.draft is None
    assert current.recommendations.candidates == ()
