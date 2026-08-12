import pytest

from order_review.case_repository import Decision, DecisionSource, JsonCaseRepository
from order_review.models import OrderSnapshot, Product
from order_review.order_identity import (
    order_structure_signature,
    same_order_signature,
)
from order_review.package_equivalence import PACKAGE_EQUIVALENCE_GROUPS
from order_review.package_plan import PackageDraft, SourceSnapshot
from order_review.recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    apply_case_plan,
    apply_recommendation,
    find_recommendations,
)


EQUIVALENT_PAIRS = (
    ("6977987940138", "美式咖啡正装", "6979151090014", "生椰拿铁正装"),
    ("6979499760068", "美式咖啡体验装", "6978430740022", "生椰拿铁体验装"),
    ("6979499760044", "黑茶茉莉正装", "6979265440002", "黑茶普洱正装"),
    ("6979499760099", "黑茶茉莉体验装", "6979265440019", "黑茶普洱体验装"),
    ("6977987940046", "蛋白粉牛油果正装", "6977987940039", "蛋白粉莓果正装"),
    ("6977987940107", "蛋白粉牛油果体验装", "6977987940084", "蛋白粉莓果体验装"),
    ("6938582367386", "气垫亮肤色", "6938582367409", "气垫自然色"),
    ("6938582367393", "气垫替换装亮肤色", "6938582367416", "气垫替换装自然色"),
)


def product(
    merchant_code: str,
    name: str,
    quantity: int,
    order_number: str,
) -> Product:
    return Product(
        title=name,
        standard_name=name,
        short_name=name,
        quantity=quantity,
        merchant_code=merchant_code,
        spu_id=f"SPU-{merchant_code}",
        sku_id=f"SKU-{merchant_code}",
        platform_order_number=order_number,
    )


def source(
    merchant_code: str,
    name: str,
    *,
    quantity: int = 2,
    order_number: str = "ORDER-1",
    with_anchor: bool = False,
) -> SourceSnapshot:
    products = [product(merchant_code, name, quantity, order_number)]
    if with_anchor:
        products.append(product("ANCHOR-001", "固定对照商品", 1, order_number))
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=(order_number,),
            products=products,
        )
    )


def split_flavor_plan(snapshot: SourceSnapshot):
    flavor, anchor = snapshot.products
    draft = PackageDraft.split(snapshot)
    draft = draft.set_quantity(
        "package-1",
        flavor.source_product_id,
        1,
        source=snapshot,
    )
    draft = draft.set_quantity(
        "package-1",
        anchor.source_product_id,
        1,
        source=snapshot,
    )
    draft = draft.set_quantity(
        "package-2",
        flavor.source_product_id,
        flavor.quantity - 1,
        source=snapshot,
    )
    return draft.confirm(snapshot)


def assert_equivalent_split_can_apply(
    tmp_path,
    historical_code: str,
    historical_name: str,
    current_code: str,
    current_name: str,
) -> None:
    repository = JsonCaseRepository(
        tmp_path / f"{historical_code}-{current_code}.json"
    )
    historical = source(
        historical_code,
        historical_name,
        with_anchor=True,
    )
    saved = repository.confirm(
        historical,
        split_flavor_plan(historical),
        Decision(DecisionSource.MANUAL),
    )
    current = source(
        current_code,
        current_name,
        order_number="ORDER-2",
        with_anchor=True,
    )

    result = find_recommendations(current, repository.list_cases())
    candidate = result.candidates[0]
    draft = apply_recommendation(current, candidate)
    plan = draft.confirm(current)

    assert candidate.match_type == MATCH_EXACT_STRUCTURE
    assert candidate.algorithm_version == 2
    assert candidate.source_case_ids == (saved.case_id,)
    assert len(plan.packages) == 2
    current_ids = {item.source_product_id for item in current.products}
    assert {
        item.source_product_id
        for package in plan.packages
        for item in package.items
    } == current_ids
    assert all(
        item.product_name != historical_name
        for package in plan.packages
        for item in package.items
    )
    assert sum(
        item.quantity
        for package in plan.packages
        for item in package.items
        if item.source_product_id == current.products[0].source_product_id
    ) == 2


@pytest.mark.parametrize(
    "first_code,first_name,second_code,second_name",
    EQUIVALENT_PAIRS,
)
def test_confirmed_equivalent_flavors_reuse_split_plan_in_both_directions(
    tmp_path,
    first_code,
    first_name,
    second_code,
    second_name,
):
    assert_equivalent_split_can_apply(
        tmp_path,
        first_code,
        first_name,
        second_code,
        second_name,
    )
    assert_equivalent_split_can_apply(
        tmp_path,
        second_code,
        second_name,
        first_code,
        first_name,
    )


def test_regular_and_trial_packages_never_match(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = source("6977987940138", "美式咖啡正装")
    repository.confirm(
        historical,
        PackageDraft.single_package(historical).confirm(historical),
        Decision(DecisionSource.MANUAL),
    )

    current = source(
        "6978430740022",
        "生椰拿铁体验装",
        order_number="ORDER-2",
    )

    assert find_recommendations(current, repository.list_cases()).candidates == ()


def test_unknown_flavor_is_not_guessed_as_equivalent(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = source("UNKNOWN-A", "未知口味A")
    repository.confirm(
        historical,
        PackageDraft.single_package(historical).confirm(historical),
        Decision(DecisionSource.MANUAL),
    )

    current = source("UNKNOWN-B", "未知口味B", order_number="ORDER-2")

    assert find_recommendations(current, repository.list_cases()).candidates == ()


def test_order_identity_remains_flavor_specific():
    american = source("6977987940138", "美式咖啡正装")
    coconut = source("6979151090014", "生椰拿铁正装")

    assert same_order_signature(american) != same_order_signature(coconut)
    assert order_structure_signature(american) != order_structure_signature(coconut)
    assert american.products[0].match_key != coconut.products[0].match_key
    assert (
        american.products[0].package_match_key
        == coconut.products[0].package_match_key
    )


def test_same_order_restore_keeps_original_flavor_distribution(tmp_path):
    snapshot = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-1",),
            products=[
                product("6977987940138", "美式咖啡正装", 1, "ORDER-1"),
                product("6979151090014", "生椰拿铁正装", 1, "ORDER-1"),
            ],
        )
    )
    american, coconut = snapshot.products
    plan = (
        PackageDraft.split(snapshot)
        .set_quantity(
            "package-1",
            american.source_product_id,
            1,
            source=snapshot,
        )
        .set_quantity(
            "package-2",
            coconut.source_product_id,
            1,
            source=snapshot,
        )
        .confirm(snapshot)
    )
    repository = JsonCaseRepository(tmp_path / "cases.json")
    saved = repository.confirm(
        snapshot,
        plan,
        Decision(DecisionSource.MANUAL),
    )

    restored = apply_case_plan(snapshot, saved).confirm(snapshot)

    assert restored.packages[0].items[0].source_product_id == american.source_product_id
    assert restored.packages[1].items[0].source_product_id == coconut.source_product_id


def test_equivalent_flavor_can_reuse_lower_single_package_capacity(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = source("6977987940046", "蛋白粉牛油果正装", quantity=3)
    repository.confirm(
        historical,
        PackageDraft.single_package(historical).confirm(historical),
        Decision(DecisionSource.MANUAL),
    )
    current = source(
        "6977987940039",
        "蛋白粉莓果正装",
        quantity=2,
        order_number="ORDER-2",
    )

    candidate = find_recommendations(
        current,
        repository.list_cases(),
    ).candidates[0]
    plan = apply_recommendation(current, candidate).confirm(current)

    assert candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY
    assert candidate.algorithm_version == 4
    assert (
        plan.packages[0].items[0].source_product_id
        == current.products[0].source_product_id
    )
    assert plan.packages[0].items[0].product_name == "蛋白粉莓果正装"


def test_whitelist_contains_only_confirmed_eight_spec_groups():
    assert set(PACKAGE_EQUIVALENCE_GROUPS) == {
        "coffee_regular",
        "coffee_trial",
        "black_tea_regular",
        "black_tea_trial",
        "protein_regular",
        "protein_trial",
        "cushion_regular",
        "cushion_refill",
    }
    assert all(len(products) == 2 for products in PACKAGE_EQUIVALENCE_GROUPS.values())


def test_cushion_regular_and_refill_never_match(tmp_path):
    repository = JsonCaseRepository(tmp_path / "cases.json")
    historical = source("6938582367386", "气垫亮肤色")
    repository.confirm(
        historical,
        PackageDraft.single_package(historical).confirm(historical),
        Decision(DecisionSource.MANUAL),
    )

    current = source(
        "6938582367393",
        "气垫替换装亮肤色",
        order_number="ORDER-2",
    )

    assert find_recommendations(current, repository.list_cases()).candidates == ()
