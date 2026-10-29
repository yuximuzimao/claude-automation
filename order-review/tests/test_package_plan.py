from dataclasses import FrozenInstanceError, replace

import pytest

from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    DraftSnapshotMismatchError,
    Package,
    PackageDraft,
    PackageItem,
    PackagePlan,
    PackagePlanValidationError,
    SourceSnapshot,
    build_package_formula,
)


def make_order_snapshot(*, order_number: str = "ORDER-1") -> OrderSnapshot:
    return OrderSnapshot(
        is_expanded=True,
        order_numbers=(order_number,),
        products=[
            Product(
                title="商品A（简称A）",
                standard_name="商品A",
                short_name="简称A",
                quantity=3,
                merchant_code="CODE-A",
                spu_id="ITEM-A",
                sku_id="SKU-A",
                platform_order_number=order_number,
                raw_dataset={"oid": "OID-A"},
            ),
            Product(
                title="商品B（简称B）",
                standard_name="商品B",
                short_name="简称B",
                quantity=2,
                merchant_code="CODE-B",
                spu_id="ITEM-B",
                sku_id="SKU-B",
                platform_order_number=order_number,
            ),
        ],
        raw_payload={"ok": True, "nested": {"value": 1}},
    )


def test_source_snapshot_is_immutable_and_keeps_complete_detached_payload():
    order = make_order_snapshot()
    source = SourceSnapshot.from_order_snapshot(order, captured_at="2026-07-22T12:00:00Z")

    order.raw_payload["nested"]["value"] = 99
    exported = source.to_dict()
    exported["rawPayload"]["nested"]["value"] = 88

    assert source.to_dict()["rawPayload"]["nested"]["value"] == 1
    assert source.products[0].details["rawDataset"] == {"oid": "OID-A"}
    with pytest.raises(FrozenInstanceError):
        source.snapshot_id = "changed"  # type: ignore[misc]


def test_source_product_ids_are_stable_for_same_order_content():
    first = SourceSnapshot.from_order_snapshot(
        make_order_snapshot(), captured_at="2026-07-22T12:00:00Z"
    )
    second = SourceSnapshot.from_order_snapshot(
        make_order_snapshot(), captured_at="2026-07-22T13:00:00Z"
    )

    assert first.snapshot_id == second.snapshot_id
    assert [item.source_product_id for item in first.products] == [
        item.source_product_id for item in second.products
    ]


def test_single_package_draft_preserves_every_source_product_reference():
    source = SourceSnapshot.from_order_snapshot(make_order_snapshot())

    draft = PackageDraft.single_package(source)
    plan = draft.confirm(source)

    assert len(plan.packages) == 1
    assert [(item.source_product_id, item.quantity) for item in plan.packages[0].items] == [
        (source.products[0].source_product_id, 3),
        (source.products[1].source_product_id, 2),
    ]


def test_split_draft_enforces_quantity_conservation_and_no_empty_packages():
    source = SourceSnapshot.from_order_snapshot(make_order_snapshot())
    first_id, second_id = [item.source_product_id for item in source.products]
    draft = PackageDraft.split(source, package_count=2)
    draft = draft.set_quantity("package-1", first_id, 3, source=source)
    draft = draft.set_quantity("package-2", second_id, 1, source=source)

    with pytest.raises(PackagePlanValidationError, match="尚有 1 件商品未分配"):
        draft.confirm(source)

    draft = draft.set_quantity("package-2", second_id, 2, source=source)
    assert draft.confirm(source).total_quantity == 5

    with pytest.raises(PackagePlanValidationError, match="不能超过原订单数量"):
        draft.set_quantity("package-2", first_id, 1, source=source)


def test_empty_package_cannot_be_confirmed_but_can_be_deleted():
    source = SourceSnapshot.from_order_snapshot(make_order_snapshot())
    draft = PackageDraft.single_package(source).add_package()

    with pytest.raises(PackagePlanValidationError, match="不允许空包裹"):
        draft.confirm(source)

    draft = draft.remove_package("package-2")
    assert len(draft.confirm(source).packages) == 1


def test_draft_rejects_a_different_snapshot():
    first = SourceSnapshot.from_order_snapshot(make_order_snapshot())
    second = SourceSnapshot.from_order_snapshot(make_order_snapshot(order_number="ORDER-2"))
    draft = PackageDraft.single_package(first)

    with pytest.raises(DraftSnapshotMismatchError):
        draft.confirm(second)


def test_package_formula_merges_duplicate_codes_and_keeps_letters_and_leading_zero():
    product = make_order_snapshot().products[0]
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            products=[
                replace(product, merchant_code="06931583616811", quantity=6),
                replace(product, merchant_code="6940079096228-1", quantity=4),
                replace(product, sku_id="OTHER-SKU", merchant_code="06931583616811", quantity=2),
                replace(product, merchant_code="yxxyld", quantity=2),
            ],
        )
    )
    water, lotion, extra_water, bag = source.products

    def item(product, quantity):
        return PackageItem(product.source_product_id, product.display_name, quantity)

    plan = PackagePlan(
        packages=(
            Package("1", (
                item(water, 2), item(lotion, 2), item(extra_water, 2), item(bag, 1),
            )),
            Package("2", (item(bag, 1), item(lotion, 2), item(water, 4))),
        )
    )

    assert [build_package_formula(source, package) for package in plan.packages] == [
        "06931583616811*4+6940079096228-1*2+yxxyld*1",
        "yxxyld*1+6940079096228-1*2+06931583616811*4",
    ]


@pytest.mark.parametrize("quantities", [(2, 2, 2), (2, 4), (1, 1, 4)])
def test_package_formula_uses_selected_package_quantity(quantities):
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(is_expanded=True, products=[replace(
            make_order_snapshot().products[0], quantity=sum(quantities),
        )])
    )
    product = source.products[0]
    plan = PackagePlan(
        tuple(
            Package(str(index), (PackageItem(product.source_product_id, "A", quantity),))
            for index, quantity in enumerate(quantities)
        )
    )

    assert [build_package_formula(source, package) for package in plan.packages] == [
        f"CODE-A*{quantity}" for quantity in quantities
    ]


def test_package_formula_keeps_actual_code_for_same_name_with_different_codes():
    product = make_order_snapshot().products[0]
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            products=[
                replace(product, merchant_code="CODE-A", quantity=1),
                replace(product, merchant_code="CODE-B", quantity=1),
            ]
        )
    )
    plan = PackagePlan(
        tuple(
            Package(str(index), (PackageItem(product.source_product_id, "相同名称", 1),))
            for index, product in enumerate(source.products)
        )
    )

    assert [build_package_formula(source, package) for package in plan.packages] == [
        "CODE-A*1", "CODE-B*1",
    ]


@pytest.mark.parametrize("code", ["", " ", "A+B", "A*2", "A\nB"])
def test_package_formula_requires_a_usable_merchant_code(code):
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(is_expanded=True, products=[replace(
            make_order_snapshot().products[0],
            merchant_code=code, main_merchant_code="MAIN", quantity=2,
        )])
    )
    product = source.products[0]
    plan = PackagePlan(
        tuple(
            Package(str(index), (PackageItem(product.source_product_id, "A", 1),))
            for index in range(2)
        )
    )

    assert all(build_package_formula(source, package) == "" for package in plan.packages)


def test_package_formula_rejects_empty_unknown_or_invalid_quantity():
    source = SourceSnapshot.from_order_snapshot(make_order_snapshot())
    assert build_package_formula(source, Package("empty")) == ""
    item = PackageItem(source.products[0].source_product_id, "A", 1)
    for invalid in (
        replace(item, source_product_id="unknown"),
        replace(item, quantity=0),
        replace(item, quantity=-1),
    ):
        assert build_package_formula(source, Package("invalid", (invalid,))) == ""
