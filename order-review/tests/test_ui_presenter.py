from order_review.models import OrderSnapshot, Product
from order_review.ui import (
    DETAIL_COLLAPSED_TEXT,
    DETAIL_EXPANDED_TEXT,
    MACOS_THEME,
    build_sidebar_view,
    format_sidebar_lines,
)


def test_format_sidebar_lines_shows_judgment_and_product_quantity():
    snapshot = OrderSnapshot(
        is_expanded=True,
        has_can_merge_mark=True,
        products=[
            Product(
                title="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）",
                standard_name="KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21",
                short_name="KGOS黑茶 茉莉味",
                quantity=7,
                merchant_code="6979499760044",
                spu_id="kgoshcml-cx",
                sku_id="130292082",
            )
        ],
    )

    lines = format_sidebar_lines(snapshot)

    assert lines[0] == "判断：可进入人工判断"
    assert "1 种 / 7 件" in lines
    assert "KGOS黑茶 茉莉味 x7" in lines
    assert "编码：6979499760044" in lines
    assert "SPU：kgoshcml-cx" in lines
    assert "SKU：130292082" in lines
    assert "可合单标记：有" in lines


def test_format_sidebar_lines_shows_unexpanded_message_only():
    lines = format_sidebar_lines(OrderSnapshot(is_expanded=False))

    assert lines == ["判断：请先展开订单"]


def test_format_sidebar_lines_shows_distinct_main_code():
    snapshot = OrderSnapshot(
        is_expanded=True,
        products=[
            Product(
                title="商品A（简称A）",
                standard_name="商品A",
                short_name="简称A",
                quantity=2,
                merchant_code="MERCHANT-2",
                main_merchant_code="MAIN-1",
            )
        ],
    )

    lines = format_sidebar_lines(snapshot)

    assert "主商家编码：MAIN-1" in lines
    assert "商家编码：MERCHANT-2" in lines


def test_build_sidebar_view_separates_products_into_cards():
    snapshot = OrderSnapshot(
        is_expanded=True,
        has_can_merge_mark=False,
        products=[
            Product(
                title="商品A（简称A）",
                standard_name="商品A",
                short_name="简称A",
                quantity=2,
                merchant_code="CODE-A",
                spu_id="spu-a",
                sku_id="sku-a",
            ),
            Product(
                title="商品B（简称B）",
                standard_name="商品B",
                short_name="简称B",
                quantity=3,
                merchant_code="CODE-B",
                spu_id="spu-b",
                sku_id="sku-b",
            ),
        ],
    )

    view = build_sidebar_view(snapshot)

    assert view.status == "判断：可进入人工判断"
    assert view.summary_lines == ["2 种 / 5 件", "可合单标记：无"]
    assert len(view.product_cards) == 2
    assert view.product_cards[0].title == "简称A x2"
    assert view.product_cards[0].details == ["商品A", "编码：CODE-A", "SPU：spu-a", "SKU：sku-a"]
    assert view.product_cards[1].title == "简称B x3"


def test_macos_theme_uses_readable_controls():
    assert MACOS_THEME["titlebar_bg"] == "#f5f5f7"
    assert MACOS_THEME["refresh_text"] == "刷新"
    assert MACOS_THEME["close_text"] == "×"
    assert MACOS_THEME["accent"] == "#007aff"


def test_product_card_omits_missing_spu_sku_for_split_orders():
    snapshot = OrderSnapshot(
        is_expanded=True,
        products=[
            Product(
                title="拆分商品（拆分简称）",
                standard_name="拆分商品",
                short_name="拆分简称",
                quantity=1,
                merchant_code="SPLIT-CODE",
            )
        ],
    )

    view = build_sidebar_view(snapshot)

    assert view.product_cards[0].title == "拆分简称 x1"
    assert view.product_cards[0].details == ["拆分商品", "编码：SPLIT-CODE"]
    assert all(not detail.startswith("SPU：") for detail in view.product_cards[0].details)
    assert all(not detail.startswith("SKU：") for detail in view.product_cards[0].details)


def test_detail_toggle_copy_is_explicit():
    assert DETAIL_COLLAPSED_TEXT == "展开详情"
    assert DETAIL_EXPANDED_TEXT == "隐藏详情"
