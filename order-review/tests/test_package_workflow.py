import pytest

from order_review.case_repository import (
    DecisionSource,
    JsonCaseRepository,
    ShippingMode,
)
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    DraftSnapshotMismatchError,
    PackagePlanValidationError,
)
from order_review.package_workflow import PackagePlanWorkflow
from order_review.recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    MATCH_SINGLE_PACKAGE_TOTAL,
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


def test_refresh_invalidates_unconfirmed_draft_even_when_order_content_is_same(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))
    workflow.load_order(make_order())
    workflow.start_split()
    assert workflow.draft is not None

    workflow.load_order(make_order())

    assert workflow.draft is None
    assert workflow.confirmed_case is None


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


def test_total_quantity_one_non_suite_defaults_to_single_package_draft(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))

    workflow.load_order(make_order(quantity=1))

    assert workflow.draft is not None
    assert len(workflow.draft.packages) == 1
    assert workflow.remaining_quantity == 0
    assert "总数量为 1 且非套件" in workflow.load_notice
    assert workflow.confirmed_case is None


def test_total_quantity_one_suite_does_not_default_to_single_package(tmp_path):
    workflow = PackagePlanWorkflow(JsonCaseRepository(tmp_path / "cases.json"))

    workflow.load_order(make_order(quantity=1, has_suite_action=True))

    assert workflow.draft is None
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

    product = current.source_snapshot.products[0]
    current.set_quantity("package-1", product.source_product_id, 2)
    assert current.recommendation_modified is False

    current.confirm()

    assert len(repository.list_cases()) == 1
    assert len(repository.list_assignments()) == 2
    assignment = repository.list_assignments()[-1]
    assert assignment.decision is not None
    assert assignment.decision.recommendation_match_type == MATCH_EXACT_STRUCTURE
    stats = repository.get_rule_stats()[current.recommendations.candidates[0].rule_id]
    assert stats.direct_use_count == 1
    assert stats.modified_count == 0


def test_adopted_order_can_later_save_its_own_linked_version(tmp_path):
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
    assert repeated.historical_case == source_case
    repeated.edit_historical_plan()
    product_id = repeated.source_snapshot.products[0].source_product_id
    repeated.set_quantity("package-1", product_id, 1)
    repeated.add_package()
    repeated.set_quantity("package-2", product_id, 1)
    version_two = repeated.confirm()

    assert version_two.previous_case_id == source_case.case_id
    assert version_two.order_version == 2
    assert version_two.source_snapshot.platform_order_numbers == ("ORDER-2",)
    latest = PackagePlanWorkflow(repository)
    latest.load_order(make_order("ORDER-2"))
    assert latest.historical_case == version_two


def test_modified_exact_rule_saves_new_branch_and_modified_stat(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = PackagePlanWorkflow(repository)
    historical.load_order(make_order("ORDER-1"))
    historical.start_single_package()
    historical.confirm()

    current = PackagePlanWorkflow(repository)
    current.load_order(make_order("ORDER-2"))
    candidate = current.selected_recommendation
    product_id = current.source_snapshot.products[0].source_product_id
    current.set_quantity("package-1", product_id, 1)
    current.add_package()
    current.set_quantity("package-2", product_id, 1)
    saved = current.confirm()

    assert saved.decision.source is DecisionSource.RECOMMENDED_MODIFIED
    assert saved.decision.recommendation_modified is True
    assert len(repository.list_cases()) == 2
    stats = repository.get_rule_stats()[candidate.rule_id]
    assert stats.direct_use_count == 0
    assert stats.modified_count == 1


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
    stats = repository.get_rule_stats()[candidate.rule_id]
    assert stats.direct_use_count == 1
    assert stats.modified_count == 0

    repeated = PackagePlanWorkflow(repository)
    repeated.load_order(make_order("ORDER-2", quantity=3))
    assert repeated.historical_case == saved
    assert repeated.historical_plan is not None
    assert repeated.historical_plan.total_quantity == 3


def test_same_total_with_different_suborder_structure_does_not_reuse_multi_package(tmp_path):
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
