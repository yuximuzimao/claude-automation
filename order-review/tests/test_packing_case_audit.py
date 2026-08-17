from order_review.case_repository import (
    ConfirmedCase,
    Decision,
    DecisionSource,
    ShippingMode,
)
from order_review.dimension_catalog import DimensionCatalog
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import PackageDraft, SourceSnapshot
from order_review.packing_case_audit import (
    PackageEvidenceStatus,
    build_packing_case_audit,
)


def _source(
    products: list[tuple[str, str, int]],
    *,
    order_number: str = "ORDER-1",
) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id=order_number,
            order_numbers=(order_number,),
            products=[
                Product(
                    title=name,
                    standard_name=name,
                    short_name=name,
                    quantity=quantity,
                    merchant_code=code,
                    platform_order_number=order_number,
                )
                for code, name, quantity in products
            ],
        ),
        captured_at="2026-08-13T00:00:00Z",
    )


def _case(
    source: SourceSnapshot,
    *,
    case_id: str = "case-1",
    split_quantities: tuple[int, ...] | None = None,
    order_version: int = 1,
    shipping_mode: ShippingMode = ShippingMode.PARCEL,
) -> ConfirmedCase:
    if split_quantities is None:
        plan = PackageDraft.single_package(source).confirm(source)
    else:
        assert len(source.products) == 1
        source_product_id = source.products[0].source_product_id
        draft = PackageDraft.split(source, package_count=len(split_quantities))
        for index, quantity in enumerate(split_quantities, start=1):
            draft = draft.set_quantity(
                f"package-{index}",
                source_product_id,
                quantity,
                source=source,
            )
        plan = draft.confirm(source)
    return ConfirmedCase(
        schema_version=1,
        case_id=case_id,
        confirmed_at=f"2026-08-13T00:00:0{order_version}Z",
        source_snapshot=source,
        package_plan=plan,
        decision=Decision(
            source=DecisionSource.MANUAL,
            shipping_mode=shipping_mode,
        ),
        order_version=order_version,
    )


def test_coffee_confirmed_capacity_and_partial_original_carton_are_supported():
    catalog = DimensionCatalog.load()
    three = _case(
        _source([("6977987940138", "生椰咖啡", 3)], order_number="COFFEE-3"),
        case_id="coffee-3",
    )
    fifty_four = _case(
        _source([("6977987940138", "生椰咖啡", 54)], order_number="COFFEE-54"),
        case_id="coffee-54",
    )
    sixty = _case(
        _source([("6977987940138", "生椰咖啡", 60)], order_number="COFFEE-60"),
        case_id="coffee-60",
    )

    report = build_packing_case_audit([three, fifty_four, sixty], catalog)

    assert [item.status for item in report.package_details] == [
        PackageEvidenceStatus.CONFIRMED_CAPACITY,
        PackageEvidenceStatus.DEDICATED_ORIGINAL,
        PackageEvidenceStatus.DEDICATED_ORIGINAL,
    ]
    assert all(
        "54–60件" in item.note for item in report.package_details[1:]
    )
    assert report.fully_supported_order_count == 3


def test_fig_jelly_original_carton_supports_confirmed_partial_shipping_range():
    fifty_six = _case(
        _source([("6980319670009", "无花果果冻", 56)], order_number="FIG-56"),
        case_id="fig-56",
    )
    sixty_four = _case(
        _source([("6980319670009", "无花果果冻", 64)], order_number="FIG-64"),
        case_id="fig-64",
    )

    report = build_packing_case_audit(
        [fifty_six, sixty_four],
        DimensionCatalog.load(),
    )

    assert all(
        item.status is PackageEvidenceStatus.DEDICATED_ORIGINAL
        for item in report.package_details
    )
    assert all("56–64件" in item.note for item in report.package_details)


def test_enzyme_original_carton_supports_confirmed_partial_shipping_range():
    fifteen = _case(
        _source([("6979151090007", "酵素4.0", 15)], order_number="ENZYME-15"),
        case_id="enzyme-15",
    )
    eighteen = _case(
        _source([("6979151090007", "酵素4.0", 18)], order_number="ENZYME-18"),
        case_id="enzyme-18",
    )

    report = build_packing_case_audit([fifteen, eighteen], DimensionCatalog.load())

    assert all(
        item.status is PackageEvidenceStatus.DEDICATED_ORIGINAL
        for item in report.package_details
    )
    assert all("15–20件" in item.note for item in report.package_details)


def test_corn_chips_ten_unit_original_carton_supports_five_plus_five():
    case = _case(
        _source(
            [
                ("6979499760105", "香菜牛肉味玉米片", 5),
                ("6979499760112", "玉米浓汤味玉米片", 5),
            ],
            order_number="CORN-10",
        )
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    detail = report.package_details[0]
    assert detail.status is PackageEvidenceStatus.DEDICATED_ORIGINAL
    assert detail.evidence_ids == ("original-corn-chips-10",)


def test_new_face_oil_limit_overrides_outer_geometry_for_whole_order():
    case = _case(
        _source([("6975183897416", "悦希新精油", 6)]),
        split_quantities=(5, 1),
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    assert {item.status for item in report.package_details} == {
        PackageEvidenceStatus.CONFIRMED_QUANTITY_RANGE
    }
    order = report.order_details[0]
    assert order.whole_order_single_status is PackageEvidenceStatus.BUSINESS_LIMIT_EXCEEDED
    assert order.potential_package_count_mismatch is False


def test_yuexi_product_cannot_use_kgos_general_cartons():
    case = _case(
        _source([("6950328271429", "悦希防晒", 2)]),
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    detail = report.package_details[0]
    assert detail.status is PackageEvidenceStatus.NO_BRAND_COMPATIBLE_CARTON
    assert "yuexi" in detail.note


def test_enzyme_nine_confirmed_split_blocks_single_package_geometry():
    case = _case(
        _source([("6979151090007", "酵素4.0", 9)]),
        split_quantities=(6, 3),
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    order = report.order_details[0]
    assert (
        order.whole_order_single_status
        is PackageEvidenceStatus.CONFIRMED_SINGLE_PACKAGE_EXCLUDED
    )
    assert order.potential_package_count_mismatch is False


def test_coffee_thirty_six_confirmed_two_parcel_rule_blocks_single_geometry():
    case = _case(
        _source([("6977987940138", "美式咖啡", 36)]),
        split_quantities=(18, 18),
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    order = report.order_details[0]
    assert (
        order.whole_order_single_status
        is PackageEvidenceStatus.CONFIRMED_SINGLE_PACKAGE_EXCLUDED
    )
    assert order.potential_package_count_mismatch is False


def test_missing_product_dimensions_are_reported_without_guessing():
    case = _case(_source([("UNKNOWN", "三围尺", 2)]))

    report = build_packing_case_audit([case], DimensionCatalog.load())

    assert report.package_status_counts == {"missing_dimensions": 1}
    assert report.missing_product_counts == (("UNKNOWN", "三围尺", 1, 2),)
    assert report.fully_supported_order_count == 0


def test_fixed_gift_rule_has_priority_over_general_gift_exclusion():
    case = _case(
        _source(
            [
                ("6950328273508", "修颜礼盒", 2),
                ("yxxyld", "修颜礼袋", 2),
            ]
        )
    )

    report = build_packing_case_audit([case], DimensionCatalog.load())

    detail = report.package_details[0]
    assert detail.status is PackageEvidenceStatus.FIXED_PLAN
    assert detail.evidence_ids == ("xiuyan-gift-set-carton", "carton-16")


def test_other_gift_box_keeps_saved_plan_as_manual_evidence():
    case = _case(_source([("UNKNOWN-GIFT", "悦希礼盒套装", 1)]))

    report = build_packing_case_audit([case], DimensionCatalog.load())

    assert report.package_details[0].status is PackageEvidenceStatus.SAVED_PLAN_ONLY
    assert report.package_details[0].missing_products == ()


def test_split_order_is_flagged_when_geometry_supports_one_package():
    case = _case(
        _source([("6977987940138", "生椰咖啡", 6)]),
        split_quantities=(3, 3),
    )

    report = build_packing_case_audit(
        [case],
        DimensionCatalog.load(),
        max_search_nodes=10_000,
    )

    order = report.order_details[0]
    assert order.all_saved_packages_supported is True
    assert order.whole_order_single_status in {
        PackageEvidenceStatus.GEOMETRY_OUTER_FIT,
        PackageEvidenceStatus.GEOMETRY_INNER_FIT,
    }
    volumes = [
        DimensionCatalog.load().carton(carton_id).dimensions.volume
        for carton_id in order.whole_order_single_evidence_ids
    ]
    assert volumes == sorted(volumes)
    assert order.potential_package_count_mismatch is True


def test_latest_order_version_wins_and_freight_is_excluded():
    source = _source([("UNKNOWN", "旧尺寸商品", 1)], order_number="SAME-ORDER")
    old = _case(source, case_id="old", order_version=1)
    latest = _case(source, case_id="latest", order_version=2)
    freight = _case(
        _source([("UNKNOWN-2", "大货商品", 1)], order_number="FREIGHT"),
        case_id="freight",
        shipping_mode=ShippingMode.FREIGHT,
    )

    report = build_packing_case_audit([latest, freight, old], DimensionCatalog.load())

    assert report.parcel_order_count == 1
    assert report.package_count == 1
    assert report.package_details[0].case_id == "latest"
