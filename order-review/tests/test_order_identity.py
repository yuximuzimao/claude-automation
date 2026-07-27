from order_review.models import OrderSnapshot, Product
from order_review.order_identity import (
    order_structure_signature,
    same_order_signature,
    total_product_signature,
)
from order_review.package_plan import SourceSnapshot


def product(name: str, quantity: int, order_number: str) -> Product:
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


def source(products: list[Product]) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(is_expanded=True, products=products)
    )


def test_same_platform_order_merges_duplicate_product_rows():
    combined = source([product("A", 6, "ORDER-X")])
    split_rows = source(
        [product("A", 3, "ORDER-X"), product("A", 3, "ORDER-X")]
    )

    assert same_order_signature(combined) == same_order_signature(split_rows)
    assert order_structure_signature(combined) == order_structure_signature(split_rows)
    assert total_product_signature(combined) == total_product_signature(split_rows)


def test_same_order_signature_keeps_platform_order_numbers():
    first = source([product("A", 2, "ORDER-X"), product("B", 2, "ORDER-Y")])
    second = source([product("A", 2, "ORDER-M"), product("B", 2, "ORDER-N")])

    assert same_order_signature(first) != same_order_signature(second)
    assert order_structure_signature(first) == order_structure_signature(second)


def test_structure_signature_preserves_each_suborder_composition():
    separated = source(
        [
            product("A", 2, "ORDER-1"),
            product("B", 2, "ORDER-2"),
            product("C", 2, "ORDER-3"),
        ]
    )
    mixed = source(
        [
            product("A", 1, "ORDER-4"),
            product("B", 1, "ORDER-4"),
            product("B", 1, "ORDER-5"),
            product("C", 1, "ORDER-5"),
            product("A", 1, "ORDER-6"),
            product("C", 1, "ORDER-6"),
        ]
    )

    assert total_product_signature(separated) == total_product_signature(mixed)
    assert order_structure_signature(separated) != order_structure_signature(mixed)


def test_same_order_signature_refuses_to_guess_without_reliable_order_mapping():
    snapshot = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            order_numbers=("ORDER-1", "ORDER-2"),
            products=[
                Product(
                    title="商品A（简称A）",
                    standard_name="商品A",
                    short_name="简称A",
                    quantity=1,
                    merchant_code="CODE-A",
                )
            ],
        )
    )

    assert same_order_signature(snapshot) is None
