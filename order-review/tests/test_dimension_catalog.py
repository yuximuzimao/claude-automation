from dataclasses import replace

import pytest

from order_review.carton_packing import (
    CartonAssessmentStatus,
    GeometryStatus,
    MissingProductDimensionsError,
    PackingLine,
    PlacedUnit,
    Point3D,
    assess_carton,
    assess_catalog_carton,
    layout_is_valid,
    units_from_catalog,
)
from order_review.dimension_catalog import (
    DimensionCatalog,
    DimensionsMm,
    DimensionType,
    InventoryStatus,
)


COFFEE_CODE = "6977987940138"
COCONUT_COFFEE_CODE = "6979151090014"
PROBIOTIC_CODE = "6977987940053"
BLACK_TEA_JASMINE_CODE = "6979499760044"
BLACK_TEA_PUER_CODE = "6979265440002"
BLACK_TEA_TRIAL_JASMINE_CODE = "6979499760099"
BLACK_TEA_TRIAL_PUER_CODE = "6979265440019"
FIG_JELLY_CODE = "6980319670009"


@pytest.fixture(scope="module")
def catalog() -> DimensionCatalog:
    return DimensionCatalog.load()


def test_catalog_preserves_dimension_evidence_and_inventory_state(catalog):
    assert catalog.schema_version == 2
    assert len(catalog.cartons) == 16
    assert catalog.carton_name_semantics == "label_only"
    assert all(item.dimension_type == DimensionType.OUTER for item in catalog.cartons)
    assert [item.inventory_status for item in catalog.cartons[9:12]] == [
        InventoryStatus.DEPLETING,
        InventoryStatus.DEPLETING,
        InventoryStatus.DEPLETING,
    ]
    assert len(catalog.candidate_cartons()) == 12
    assert catalog.outer_to_inner_reduction == DimensionsMm(5, 5, 5)
    assert {item.brand_id for item in catalog.cartons[:12]} == {"kgos"}
    assert {item.brand_id for item in catalog.cartons[12:]} == {"yuexi"}


def test_general_carton_candidates_must_match_product_brand(catalog):
    kgos_ids = {
        item.carton_id
        for item in catalog.candidate_cartons_for_codes([COFFEE_CODE])
    }

    assert kgos_ids == {f"carton-{index:02d}" for index in range(1, 13)}
    assert catalog.candidate_cartons_for_codes(["6950328271429"]) == ()
    assert catalog.candidate_cartons_for_codes(
        [COFFEE_CODE, "6950328271429"]
    ) == ()


def test_new_product_dimensions_are_bound_only_to_confirmed_codes(catalog):
    assert catalog.product("6979151090007").dimensions == DimensionsMm(171, 151, 73)
    assert catalog.product("6976299500108").dimensions == DimensionsMm(101, 36, 130)
    assert catalog.product("6979499760082").dimensions == DimensionsMm(275, 180, 42)
    assert catalog.product("ZZ腰围尺-绿色").dimensions == DimensionsMm(90, 63, 23)
    assert catalog.product("ZZ腰围尺-绿色").dimension_source.value == "estimated"
    assert catalog.product("6979499760037").dimensions == DimensionsMm(165, 70, 43)
    assert catalog.product("6950328271429").dimensions == DimensionsMm(128, 51, 36)
    assert catalog.product("6975183897416").dimensions == DimensionsMm(107, 53, 43)
    assert catalog.product("6977235921278").dimensions == DimensionsMm(166, 117, 24)
    assert catalog.product("旧版糖果未知编码") is None


def test_fig_jelly_inventory_result_is_mapped_to_dimensions_and_original_carton(
    catalog,
):
    product = catalog.product(FIG_JELLY_CODE)
    original = catalog.original_carton("original-fig-jelly-64")
    arrangement = original.confirmed_arrangement

    assert product is not None
    assert product.display_name == "KGOS无花果果冻"
    assert product.brand_id == "kgos"
    assert product.dimensions == DimensionsMm(136, 87, 41)
    assert product.dimension_source.value == "user_provided"
    assert original.dimensions == DimensionsMm(363, 348, 290)
    assert original.capacity == 64
    assert original.minimum_shippable_quantity == 56
    assert all(
        original.accepts_closed_unit({FIG_JELLY_CODE: quantity})
        for quantity in range(56, 65)
    )
    assert not original.accepts_closed_unit({FIG_JELLY_CODE: 55})
    assert not original.accepts_closed_unit({FIG_JELLY_CODE: 65})
    assert arrangement is not None
    assert arrangement.grid == (4, 8, 2)
    assert arrangement.item_orientation == DimensionsMm(87, 41, 136)
    assert arrangement.occupied_dimensions == DimensionsMm(348, 328, 272)
    assert arrangement.occupied_dimensions.fits_inside(DimensionsMm(358, 343, 285))
    assert all(item["label"] != "无花果果冻" for item in catalog.pending_mappings)


def test_black_tea_dimension_is_marked_as_carton_derived(catalog):
    jasmine = catalog.product(BLACK_TEA_JASMINE_CODE)
    puer = catalog.product(BLACK_TEA_PUER_CODE)

    assert jasmine is puer
    assert jasmine.dimensions == DimensionsMm(157, 132, 35)
    assert jasmine.dimension_source.value == "derived_from_confirmed_cartons"
    trial_jasmine = catalog.product(BLACK_TEA_TRIAL_JASMINE_CODE)
    trial_puer = catalog.product(BLACK_TEA_TRIAL_PUER_CODE)
    assert trial_jasmine is trial_puer
    assert trial_jasmine.dimensions == DimensionsMm(115, 61, 25)


@pytest.mark.parametrize(
    "carton_id,quantity,expected_block",
    (("carton-01", 3, (157, 105, 132)), ("carton-07", 7, (245, 157, 132))),
)
def test_black_tea_dimensions_fit_three_and_seven_cartons_geometrically(
    catalog,
    carton_id,
    quantity,
    expected_block,
):
    assessment = assess_catalog_carton(
        catalog,
        carton_id,
        [PackingLine(BLACK_TEA_JASMINE_CODE, quantity)],
    )

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY
    placements = assessment.geometry.placements
    assert (
        max(item.right for item in placements),
        max(item.back for item in placements),
        max(item.top for item in placements),
    ) == expected_block


def test_black_tea_three_regular_plus_one_trial_fits_confirmed_carton(catalog):
    assessment = assess_catalog_carton(
        catalog,
        "carton-01",
        [
            PackingLine(BLACK_TEA_JASMINE_CODE, 3),
            PackingLine(BLACK_TEA_TRIAL_PUER_CODE, 1),
        ],
    )

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY
    assert len(assessment.geometry.placements) == 4
    assert layout_is_valid(
        assessment.carton.dimensions,
        assessment.geometry.placements,
    )


def test_black_tea_eighteen_uses_confirmed_capacity_despite_three_mm_gap(catalog):
    evidence = next(
        item
        for item in catalog.confirmed_capacities
        if item.carton_id == "carton-06"
        and item.product_spec_id == "black-tea-regular-package"
    )

    assert evidence.capacity == 18
    assert evidence.is_maximum
    assert catalog.product(BLACK_TEA_JASMINE_CODE).dimensions.length == 157
    assert catalog.carton("carton-06").dimensions.height == 154


def test_coffee_original_carton_accepts_confirmed_54_to_60_range(catalog):
    coffee = catalog.original_carton("original-coffee-60")

    assert coffee.minimum_shippable_quantity == 54
    assert all(
        coffee.accepts_closed_unit({COFFEE_CODE: quantity})
        for quantity in range(54, 61)
    )
    assert coffee.accepts_closed_unit({COFFEE_CODE: 30, COCONUT_COFFEE_CODE: 30})
    assert coffee.accepts_closed_unit({COFFEE_CODE: 27, COCONUT_COFFEE_CODE: 27})
    assert not coffee.accepts_closed_unit({COFFEE_CODE: 53})
    assert not coffee.accepts_closed_unit({COFFEE_CODE: 61})
    assert not coffee.accepts_closed_unit({COFFEE_CODE: 59, PROBIOTIC_CODE: 1})
    assert not coffee.allow_other_products
    assert coffee.closed_shipping_unit


def test_unknown_original_carton_dimensions_do_not_block_confirmed_capacity(catalog):
    probiotic = catalog.original_carton("original-probiotic-100")

    assert probiotic.dimensions is None
    assert probiotic.dimension_type == DimensionType.UNKNOWN
    assert probiotic.accepts_closed_unit({PROBIOTIC_CODE: 100})


def test_enzyme_original_carton_accepts_confirmed_15_to_20_range(catalog):
    enzyme = catalog.original_carton("original-enzyme-4-20")

    assert enzyme.minimum_shippable_quantity == 15
    assert all(
        enzyme.accepts_closed_unit({"6979151090007": quantity})
        for quantity in range(15, 21)
    )
    assert not enzyme.accepts_closed_unit({"6979151090007": 14})
    assert not enzyme.accepts_closed_unit({"6979151090007": 21})
    assert not enzyme.accepts_closed_unit({COFFEE_CODE: 15})


def test_corn_chips_original_carton_accepts_single_or_five_plus_five(catalog):
    corn = catalog.original_carton("original-corn-chips-10")

    assert corn.dimensions is None
    assert corn.brand_id == "kgos"
    assert corn.accepts_closed_unit({"6979499760105": 10})
    assert corn.accepts_closed_unit(
        {"6979499760105": 5, "6979499760112": 5}
    )
    assert not corn.accepts_closed_unit({"6979499760105": 5})
    assert not corn.allow_other_products


def test_new_face_oil_small_carton_rule_blocks_geometry_above_five(catalog):
    rule = catalog.confirmed_parcel_quantity_rules[0]

    assert rule.rule_id == "yuexi-new-face-oil-small-carton-1-to-5"
    assert rule.accepts({"6975183897416": 5})
    assert not rule.accepts({"6975183897416": 6})
    assert rule.matches_scope({"6975183897416": 6})
    assert rule.blocks_geometry_above_maximum


def test_enzyme_nine_is_confirmed_single_package_exclusion(catalog):
    rule = catalog.confirmed_single_package_exclusions[0]

    assert rule.matches({"6979151090007": 9})
    assert not rule.matches({"6979151090007": 8})
    assert not rule.matches(
        {"6979151090007": 9, "6979499760037": 1}
    )


def test_coffee_thirty_six_requires_two_parcels_for_either_flavor(catalog):
    rule = next(
        item
        for item in catalog.confirmed_single_package_exclusions
        if item.rule_id == "coffee-regular-36-use-two-parcels"
    )

    assert rule.matches({COFFEE_CODE: 36})
    assert rule.matches({COCONUT_COFFEE_CODE: 36})
    assert rule.matches({COFFEE_CODE: 18, COCONUT_COFFEE_CODE: 18})
    assert not rule.matches({COFFEE_CODE: 35})
    assert not rule.matches({COFFEE_CODE: 36, BLACK_TEA_JASMINE_CODE: 1})


def test_black_tea_original_carton_preserves_confirmed_12_by_3_by_2_layout(catalog):
    original = catalog.original_carton("original-black-tea-72")
    arrangement = original.confirmed_arrangement

    assert arrangement is not None
    assert arrangement.grid == (12, 3, 2)
    assert arrangement.quantity == 72
    assert arrangement.item_orientation == DimensionsMm(35, 132, 157)
    assert arrangement.occupied_dimensions == DimensionsMm(420, 396, 314)
    assert arrangement.occupied_dimensions.fits_inside(original.dimensions)


def test_yuexi_scoped_and_fixed_cartons_are_not_general_candidates(catalog):
    candidate_ids = {item.carton_id for item in catalog.candidate_cartons()}

    assert not {"carton-13", "carton-14", "carton-15", "carton-16"} & candidate_ids
    yuexi_capacity = next(
        item for item in catalog.confirmed_capacities if item.carton_id == "carton-13"
    )
    assert yuexi_capacity.capacity == 4
    assert not yuexi_capacity.scope_complete
    assert yuexi_capacity.mixing_policy == "not_confirmed"


def test_gift_box_products_use_saved_plan_and_xiuyan_has_fixed_bundle(catalog):
    exclusion = catalog.geometry_exclusion_for_name("HEE悦希修颜沁透礼盒")
    rule = catalog.fixed_packing_rules[0]

    assert exclusion is not None
    assert exclusion.fallback == "saved_package_plan"
    assert catalog.geometry_exclusion_for_name("悦希舒缓焕颜精华乳") is None
    assert rule.carton_id == "carton-16"
    assert rule.maximum_bundles_per_carton == 2
    assert {(item.merchant_code, item.quantity) for item in rule.bundle_items} == {
        ("6950328273508", 1),
        ("yxxyld", 1),
    }


def test_confirmed_equal_size_coffee_codes_share_only_the_dimension_spec(catalog):
    american = catalog.product(COFFEE_CODE)
    coconut = catalog.product(COCONUT_COFFEE_CODE)

    assert american is coconut
    assert american is not None
    assert american.dimensions == DimensionsMm(105, 42, 154)
    assert catalog.product(PROBIOTIC_CODE).dimensions == DimensionsMm(115, 28, 93)
    assert catalog.product("UNKNOWN") is None


def test_rectangular_product_has_six_axis_aligned_orientations(catalog):
    product = catalog.product(COFFEE_CODE)

    assert product is not None
    assert len(product.dimensions.orientations(product.orientation_policy)) == 6


def test_confirmed_outer_to_inner_reduction_produces_inner_fit(catalog):
    assessment = assess_catalog_carton(
        catalog,
        "carton-08",
        [PackingLine(COFFEE_CODE, 3)],
    )

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY
    assert assessment.geometry.container == DimensionsMm(133, 110, 161)
    assert assessment.geometry.status == GeometryStatus.FOUND
    assert len(assessment.geometry.placements) == 3
    assert layout_is_valid(
        assessment.geometry.container,
        assessment.geometry.placements,
    )
    assert "外尺寸长宽高各减5mm" in assessment.message


@pytest.mark.parametrize(
    "carton_id,quantity,expected_inner,expected_block",
    (
        ("carton-08", 3, (133, 110, 161), (126, 105, 154)),
        ("carton-04", 7, (305, 105, 155), (294, 105, 154)),
        ("carton-09", 10, (315, 230, 115), (308, 210, 105)),
        ("carton-03", 16, (315, 185, 217), (308, 168, 210)),
        ("carton-02", 20, (318, 225, 220), (308, 210, 210)),
        ("carton-05", 24, (318, 267, 220), (308, 252, 210)),
    ),
)
def test_all_confirmed_coffee_cartons_fit_after_five_mm_inner_reduction(
    catalog,
    carton_id,
    quantity,
    expected_inner,
    expected_block,
):
    assessment = assess_catalog_carton(
        catalog,
        carton_id,
        [PackingLine(COFFEE_CODE, quantity)],
    )

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY
    assert assessment.geometry.container.as_tuple() == expected_inner
    placements = assessment.geometry.placements
    assert (
        max(item.right for item in placements),
        max(item.back for item in placements),
        max(item.top for item in placements),
    ) == expected_block
    assert layout_is_valid(assessment.geometry.container, placements)


def test_carton_name_is_not_used_by_geometry(catalog):
    original = catalog.carton("carton-08")
    renamed = replace(original, display_name="与商品和数量无关的标签")
    units = units_from_catalog(catalog, [PackingLine(COFFEE_CODE, 3)])

    original_result = assess_carton(original, units)
    renamed_result = assess_carton(renamed, units)

    assert renamed_result.status == original_result.status
    assert renamed_result.geometry.placements == original_result.geometry.placements


def test_rotation_finds_coffee_layout_that_upright_only_cannot_find(catalog):
    assessment = assess_catalog_carton(
        catalog,
        "carton-09",
        [PackingLine(COFFEE_CODE, 10)],
    )

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY
    assert len(assessment.geometry.placements) == 10
    assert {
        item.dimensions.as_tuple() for item in assessment.geometry.placements
    } == {(154, 42, 105)}


def test_mixed_coffee_and_probiotic_layout_is_non_overlapping(catalog):
    assessment = assess_catalog_carton(
        catalog,
        "carton-01",
        [PackingLine(COFFEE_CODE, 1), PackingLine(PROBIOTIC_CODE, 1)],
    )

    assert assessment.geometry.status == GeometryStatus.FOUND
    assert {item.product_spec_id for item in assessment.geometry.placements} == {
        "coffee-regular-package",
        "probiotic-regular-package",
    }
    assert layout_is_valid(
        assessment.carton.dimensions,
        assessment.geometry.placements,
    )


def test_inner_dimensions_can_produce_geometry_fit(catalog):
    carton = replace(
        catalog.carton("carton-08"),
        dimension_type=DimensionType.INNER,
    )
    units = units_from_catalog(catalog, [PackingLine(COFFEE_CODE, 3)])

    assessment = assess_carton(carton, units)

    assert assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY


def test_item_exceeding_outer_dimensions_is_proven_not_to_fit(catalog):
    carton = replace(
        catalog.carton("carton-08"),
        dimensions=DimensionsMm(100, 100, 100),
    )
    units = units_from_catalog(catalog, [PackingLine(COFFEE_CODE, 1)])

    assessment = assess_carton(carton, units)

    assert assessment.status == CartonAssessmentStatus.DOES_NOT_FIT
    assert assessment.geometry.status == GeometryStatus.PROVEN_IMPOSSIBLE
    assert assessment.geometry.searched_nodes == 0


def test_total_volume_can_prove_items_do_not_fit(catalog):
    carton = replace(
        catalog.carton("carton-08"),
        dimensions=DimensionsMm(154, 105, 42),
    )
    units = units_from_catalog(catalog, [PackingLine(COFFEE_CODE, 2)])

    assessment = assess_carton(carton, units)

    assert assessment.status == CartonAssessmentStatus.DOES_NOT_FIT
    assert assessment.geometry.reason == "商品总体积大于纸箱空间"


def test_layout_validation_rejects_partial_support():
    base = PlacedUnit(
        instance_id="base",
        merchant_code="BASE",
        product_spec_id="base",
        display_name="底层",
        position=Point3D(0, 0, 0),
        dimensions=DimensionsMm(100, 100, 50),
        stackable=True,
    )
    partly_floating = PlacedUnit(
        instance_id="top",
        merchant_code="TOP",
        product_spec_id="top",
        display_name="上层",
        position=Point3D(50, 0, 50),
        dimensions=DimensionsMm(100, 100, 50),
        stackable=True,
    )

    assert not layout_is_valid(
        DimensionsMm(200, 200, 200),
        (base, partly_floating),
    )


def test_search_limit_returns_unknown_instead_of_false_not_fit(catalog):
    assessment = assess_catalog_carton(
        catalog,
        "carton-08",
        [PackingLine(COFFEE_CODE, 3)],
        max_search_nodes=1,
    )

    assert assessment.status == CartonAssessmentStatus.UNKNOWN
    assert assessment.geometry.status == GeometryStatus.UNKNOWN
    assert "上限" in assessment.message


def test_missing_product_dimensions_are_reported_together(catalog):
    with pytest.raises(MissingProductDimensionsError) as caught:
        units_from_catalog(
            catalog,
            [PackingLine("UNKNOWN-B", 1), PackingLine("UNKNOWN-A", 2)],
        )

    assert caught.value.merchant_codes == ("UNKNOWN-A", "UNKNOWN-B")
