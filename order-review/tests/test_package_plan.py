from dataclasses import FrozenInstanceError

import pytest

from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    DraftSnapshotMismatchError,
    PackageDraft,
    PackagePlanValidationError,
    SourceSnapshot,
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
