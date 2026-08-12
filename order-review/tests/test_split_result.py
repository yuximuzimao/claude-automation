from dataclasses import replace

from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    Package,
    PackageItem,
    PackagePlan,
    SourceSnapshot,
)
from order_review.split_result import (
    SplitResultObservation,
    SplitResultRow,
    validate_split_result,
)


ENZYME = "6979151090007"
TEA = "6979499760099"
TAPE = "ZZ腰围尺-绿色"


def _product(order: str, code: str, quantity: int) -> Product:
    return Product(
        title=f"{code}（测试商品）",
        standard_name=code,
        short_name=code,
        quantity=quantity,
        merchant_code=code,
        main_merchant_code=code,
        spu_id=f"SPU-{code}",
        sku_id=f"SKU-{code}",
        platform_order_number=order,
    )


def _source(
    system_order_id: str,
    products: list[Product],
) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id=system_order_id,
            order_numbers=tuple(
                dict.fromkeys(
                    product.platform_order_number for product in products
                )
            ),
            products=products,
        ),
        captured_at="2026-07-29T08:00:00Z",
    )


def _original_source() -> SourceSnapshot:
    return _source(
        "SYSTEM-ORIGINAL",
        [
            _product("T1", ENZYME, 9),
            _product("T2", ENZYME, 9),
            _product("T3", TEA, 2),
            _product("T3", TAPE, 1),
            _product("T4", TEA, 2),
            _product("T4", TAPE, 1),
            _product("T5", TEA, 2),
            _product("T5", TAPE, 1),
            _product("T6", ENZYME, 9),
        ],
    )


def _plan(source: SourceSnapshot) -> PackagePlan:
    products = source.products
    return PackagePlan(
        packages=(
            Package(
                "package-1",
                (
                    PackageItem(
                        products[0].source_product_id,
                        products[0].display_name,
                        9,
                    ),
                    PackageItem(
                        products[1].source_product_id,
                        products[1].display_name,
                        9,
                    ),
                    PackageItem(
                        products[8].source_product_id,
                        products[8].display_name,
                        2,
                    ),
                ),
            ),
            Package(
                "package-2",
                (
                    PackageItem(
                        products[8].source_product_id,
                        products[8].display_name,
                        7,
                    ),
                ),
            ),
            Package(
                "package-3",
                tuple(
                    PackageItem(
                        product.source_product_id,
                        product.display_name,
                        product.quantity,
                    )
                    for product in products[2:8]
                ),
            ),
        )
    )


def _successful_observation() -> SplitResultObservation:
    # 页面结果顺序 20、9、7，故意不同于本地方案顺序 20、7、9。
    return SplitResultObservation(
        loading_count=0,
        visible_dialog_count=0,
        rows=(
            SplitResultRow(
                sequence=1,
                selected=True,
                source=_source(
                    "SYSTEM-ORIGINAL",
                    [
                        _product("T1", ENZYME, 9),
                        _product("T2", ENZYME, 9),
                        _product("T6", ENZYME, 2),
                    ],
                ),
            ),
            SplitResultRow(
                sequence=2,
                selected=True,
                source=_source(
                    "SYSTEM-WHOLE-GROUP",
                    [
                        _product("T3", TEA, 2),
                        _product("T3", TAPE, 1),
                        _product("T4", TEA, 2),
                        _product("T4", TAPE, 1),
                        _product("T5", TEA, 2),
                        _product("T5", TAPE, 1),
                    ],
                ),
            ),
            SplitResultRow(
                sequence=3,
                selected=True,
                source=_source(
                    "SYSTEM-NEW-MANUAL",
                    [_product("T6", ENZYME, 7)],
                ),
            ),
            SplitResultRow(
                sequence=4,
                selected=False,
                source=_source(
                    "UNRELATED",
                    [_product("OTHER", "OTHER", 1)],
                ),
            ),
        ),
    )


def _check(report, code: str):
    return next(item for item in report.checks if item.code == code)


def test_success_matches_selected_first_n_rows_as_unordered_packages():
    source = _original_source()

    report = validate_split_result(
        source,
        _plan(source),
        _successful_observation(),
    )

    assert report.verified
    assert report.result_sequences == (1, 2, 3)
    assert report.result_system_order_ids == (
        "SYSTEM-ORIGINAL",
        "SYSTEM-WHOLE-GROUP",
        "SYSTEM-NEW-MANUAL",
    )
    assert _check(report, "PLATFORM_ORDER_UNIVERSE").passed
    assert _check(report, "TOTAL_DETAIL_CONSERVATION").passed
    assert _check(report, "PACKAGE_MULTISET_MATCH").passed


def test_duplicate_platform_order_across_packages_is_allowed_after_deduplication():
    source = _original_source()

    report = validate_split_result(
        source,
        _plan(source),
        _successful_observation(),
    )

    assert report.verified
    assert "6 个平台子订单" in _check(
        report,
        "PLATFORM_ORDER_UNIVERSE",
    ).detail


def test_loading_or_confirmation_dialog_blocks_success():
    source = _original_source()
    observation = replace(
        _successful_observation(),
        loading_count=1,
        visible_dialog_count=1,
    )

    report = validate_split_result(source, _plan(source), observation)

    assert not report.verified
    assert not _check(report, "CONFIRMATION_UI_CLOSED").passed


def test_selected_rows_must_be_exactly_the_first_target_rows():
    source = _original_source()
    observation = _successful_observation()
    rows = (
        replace(observation.rows[0], selected=False),
        observation.rows[1],
        observation.rows[2],
        replace(observation.rows[3], selected=True),
    )

    report = validate_split_result(
        source,
        _plan(source),
        replace(observation, rows=rows),
    )

    assert not report.verified
    assert report.result_sequences == (2, 3, 4)
    assert not _check(report, "SELECTED_ROWS_ARE_FIRST_N").passed


def test_platform_order_universe_must_equal_original_after_deduplication():
    source = _original_source()
    observation = _successful_observation()
    bad_third = replace(
        observation.rows[2],
        source=_source(
            "SYSTEM-NEW-MANUAL",
            [_product("T-UNKNOWN", ENZYME, 7)],
        ),
    )

    report = validate_split_result(
        source,
        _plan(source),
        replace(
            observation,
            rows=(
                observation.rows[0],
                observation.rows[1],
                bad_third,
                observation.rows[3],
            ),
        ),
    )

    assert not report.verified
    assert not _check(report, "PLATFORM_ORDER_UNIVERSE").passed
    assert not _check(report, "TOTAL_DETAIL_CONSERVATION").passed


def test_global_totals_are_not_enough_when_single_package_details_are_wrong():
    source = _original_source()
    observation = _successful_observation()
    first = replace(
        observation.rows[0],
        source=_source(
            "SYSTEM-ORIGINAL",
            [
                _product("T1", ENZYME, 9),
                _product("T2", ENZYME, 8),
                _product("T6", ENZYME, 3),
            ],
        ),
    )
    third = replace(
        observation.rows[2],
        source=_source(
            "SYSTEM-NEW-MANUAL",
            [
                _product("T2", ENZYME, 1),
                _product("T6", ENZYME, 6),
            ],
        ),
    )

    report = validate_split_result(
        source,
        _plan(source),
        replace(
            observation,
            rows=(
                first,
                observation.rows[1],
                third,
                observation.rows[3],
            ),
        ),
    )

    assert not report.verified
    assert _check(report, "TOTAL_DETAIL_CONSERVATION").passed
    assert not _check(report, "PACKAGE_MULTISET_MATCH").passed
