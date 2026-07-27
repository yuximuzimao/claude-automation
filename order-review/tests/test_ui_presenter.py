from order_review.models import OrderDetailGroup, OrderSnapshot, Product
from order_review.ui import MACOS_THEME, build_sidebar_view, format_sidebar_lines


def make_product(
    short_name: str,
    quantity: int,
    merchant_code: str,
    *,
    standard_name: str | None = None,
) -> Product:
    standard_name = standard_name or f"{short_name}标准名称"
    return Product(
        title=f"{standard_name}（{short_name}）",
        standard_name=standard_name,
        short_name=short_name,
        quantity=quantity,
        merchant_code=merchant_code,
        spu_id=f"spu-{merchant_code}",
        sku_id=f"sku-{merchant_code}",
    )


def test_format_sidebar_lines_shows_structure_quantities_and_package_placeholder():
    snapshot = OrderSnapshot(
        is_expanded=True,
        has_can_merge_mark=True,
        products=[make_product("KGOS黑茶 茉莉味", 7, "6979499760044")],
    )

    lines = format_sidebar_lines(snapshot)
    rendered = "\n".join(lines)

    assert lines[0] == "判断：可进入人工判断"
    assert "1 订单组 / 1 商品种类 / 7 商品总件数" in rendered
    assert "商品总量" in rendered
    assert "KGOS黑茶 茉莉味 x7" in rendered
    assert "当前订单组：1 种 / 7 件" in rendered
    assert "包裹方案：待计算" in rendered
    assert "待分配：1 种 / 7 件" in rendered
    assert "不代表整单可按一个包裹发出" in rendered
    assert "6979499760044" not in rendered
    assert "SPU" not in rendered
    assert "SKU" not in rendered


def test_format_sidebar_lines_shows_unexpanded_message_only():
    lines = format_sidebar_lines(OrderSnapshot(is_expanded=False))

    assert lines == ["判断：请先展开订单", "包裹方案：未开始"]


def test_build_sidebar_view_aggregates_rows_but_preserves_original_rows():
    snapshot = OrderSnapshot(
        is_expanded=True,
        has_can_merge_mark=False,
        products=[
            make_product("简称A", 2, "CODE-A"),
            make_product("简称A", 3, "CODE-A"),
            make_product("简称B", 1, "CODE-B"),
        ],
    )

    view = build_sidebar_view(snapshot)

    assert view.status == "判断：可进入人工判断"
    assert [(metric.value, metric.label) for metric in view.metrics] == [
        ("1", "订单组"),
        ("2", "商品种类"),
        ("6", "商品总件数"),
    ]
    assert [(product.title, product.quantity) for product in view.aggregate_products] == [
        ("简称A", 5),
        ("简称B", 1),
    ]
    assert len(view.order_groups) == 1
    group = view.order_groups[0]
    assert group.label == "当前订单组"
    assert group.kind_count == 2
    assert group.total_quantity == 6
    assert [(product.title, product.quantity) for product in group.products] == [
        ("简称A", 2),
        ("简称A", 3),
        ("简称B", 1),
    ]


def test_build_sidebar_view_exposes_stable_empty_package_plan():
    snapshot = OrderSnapshot(
        is_expanded=True,
        products=[
            make_product("简称A", 2, "CODE-A"),
            make_product("简称B", 3, "CODE-B"),
        ],
    )

    plan = build_sidebar_view(snapshot).package_plan

    assert plan.status == "待计算"
    assert plan.packages == []
    assert plan.unassigned_kind_count == 2
    assert plan.unassigned_quantity == 5
    assert "不代表整单可按一个包裹发出" in plan.note


def test_build_sidebar_view_uses_name_when_codes_are_missing():
    snapshot = OrderSnapshot(
        is_expanded=True,
        products=[
            Product(
                title="拆分商品（拆分简称）",
                standard_name="拆分商品",
                short_name="拆分简称",
                quantity=1,
            )
        ],
    )

    view = build_sidebar_view(snapshot)

    assert [(product.title, product.quantity) for product in view.aggregate_products] == [
        ("拆分简称", 1)
    ]
    assert view.order_groups[0].products[0].title == "拆分简称"
    assert view.order_groups[0].products[0].quantity == 1


def test_order_group_shows_related_consecutive_platform_orders():
    products = [
        Product(
            title="商品A（简称A）",
            standard_name="商品A",
            short_name="简称A",
            quantity=2,
            merchant_code="A",
            platform_order_number="756863430",
        ),
        Product(
            title="商品B（简称B）",
            standard_name="商品B",
            short_name="简称B",
            quantity=3,
            merchant_code="B",
            platform_order_number="756863431",
        ),
    ]

    view = build_sidebar_view(OrderSnapshot(is_expanded=True, products=products))

    assert [(metric.value, metric.label) for metric in view.metrics][:1] == [("1", "订单组")]
    assert len(view.order_groups) == 1
    group = view.order_groups[0]
    assert group.label == "当前订单组"
    assert group.platform_order_numbers == ("756863430", "756863431")
    assert group.relation_hint == "同一 ERP 订单组 · 平台单号连续"


def test_merged_order_groups_are_rendered_as_separate_orders():
    products = [
        Product(
            title="商品A（简称A）",
            standard_name="商品A",
            short_name="简称A",
            quantity=2,
            platform_order_number="5942995131856908",
            source_group_index=0,
        ),
        Product(
            title="商品B（简称B）",
            standard_name="商品B",
            short_name="简称B",
            quantity=5,
            platform_order_number="5942995131856908",
            source_group_index=0,
        ),
        Product(
            title="商品C（简称C）",
            standard_name="商品C",
            short_name="简称C",
            quantity=3,
            platform_order_number="5942995131856908-ebprn3",
            source_group_index=1,
        ),
        Product(
            title="商品A（简称A）",
            standard_name="商品A",
            short_name="简称A",
            quantity=2,
            platform_order_number="5942995131856908-ebprn3",
            source_group_index=1,
        ),
    ]
    snapshot = OrderSnapshot(
        is_expanded=True,
        products=products,
        groups=[
            OrderDetailGroup(
                index=0,
                key="5942995131856908",
                order_numbers=("5942995131856908",),
                product_indexes=(0, 1),
            ),
            OrderDetailGroup(
                index=1,
                key="5942995131856908-ebprn3",
                order_numbers=("5942995131856908-ebprn3",),
                product_indexes=(2, 3),
            ),
        ],
    )

    view = build_sidebar_view(snapshot)

    assert len(view.order_groups) == 2
    assert view.metrics[0] == type(view.metrics[0])("2", "订单组")
    assert view.order_groups[0].platform_order_numbers == ("5942995131856908",)
    assert [(item.title, item.quantity) for item in view.order_groups[0].products] == [
        ("简称A", 2),
        ("简称B", 5),
    ]
    assert view.order_groups[1].platform_order_numbers == (
        "5942995131856908-ebprn3",
    )
    assert [(item.title, item.quantity) for item in view.order_groups[1].products] == [
        ("简称C", 3),
        ("简称A", 2),
    ]


def test_backend_details_show_only_useful_parsed_product_fields():
    product = Product(
        title="商品A（简称A）",
        standard_name="商品A",
        short_name="简称A",
        quantity=2,
        merchant_code="MERCHANT-1",
        main_merchant_code="MAIN-1",
        platform_spec="规格A",
        platform_name="平台商品名称A",
        spu_id="PLATFORM-ITEM-1",
        sku_id="PLATFORM-SKU-1",
        platform_order_number="756863430",
        sid="ERP-SID",
        oid="ERP-OID",
        raw_dataset={"customField": "CUSTOM-1"},
    )
    snapshot = OrderSnapshot(is_expanded=True, products=[product])

    view = build_sidebar_view(snapshot)
    normal_text = "\n".join(format_sidebar_lines(snapshot))
    backend_text = "\n".join(view.backend_details.lines)

    assert "MERCHANT-1" not in normal_text
    assert view.backend_details.summary == "1 条商品明细"
    assert "平台单号：756863430" in backend_text
    assert "   平台商品 ID：PLATFORM-ITEM-1" in view.backend_details.lines
    assert "   平台 SKU ID：PLATFORM-SKU-1" in view.backend_details.lines
    assert not any(
        "平台商品 ID" in line and "平台 SKU ID" in line
        for line in view.backend_details.lines
    )
    assert "平台规格：规格A" in backend_text
    assert "平台名称：平台商品名称A" in backend_text
    assert "商家编码：MERCHANT-1" in backend_text
    assert "主商家编码：MAIN-1" in backend_text
    assert "ERP-SID" not in backend_text
    assert "ERP-OID" not in backend_text
    assert "CUSTOM-1" not in backend_text
    assert "原始明细" not in backend_text
    assert "data-*" not in backend_text


def test_macos_theme_matches_compact_order_structure_design():
    assert MACOS_THEME["titlebar_bg"] == "#ffffff"
    assert MACOS_THEME["window_bg"] == "#f6f7f9"
    assert MACOS_THEME["refresh_text"] == "刷新"
    assert MACOS_THEME["close_text"] == "×"
    assert MACOS_THEME["accent"] == "#2563eb"
    assert MACOS_THEME["package"] == "#7451c7"
