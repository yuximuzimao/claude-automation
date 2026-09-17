import order_review.carton_packing as carton_packing_module
from order_review.carton_packing import (
    GeometryStatus,
    PackingUnit,
    layout_is_fully_supported,
    layout_is_valid,
    search_packing,
    support_coverage_ratio,
)
from order_review.dimension_catalog import DimensionsMm, OrientationPolicy


def _unit(
    instance_id: str,
    dimensions: DimensionsMm,
    *,
    stackable: bool = True,
) -> PackingUnit:
    return PackingUnit(
        instance_id=instance_id,
        merchant_code=instance_id,
        product_spec_id=instance_id,
        display_name=instance_id,
        dimensions=dimensions,
        orientation_policy=OrientationPolicy.FIXED,
        stackable=stackable,
    )


def test_search_reorders_thin_support_under_larger_volume_item():
    container = DimensionsMm(310, 227, 90)
    gift_box = _unit("gift-box", DimensionsMm(303, 202, 79))
    gift_bag = _unit("gift-bag", DimensionsMm(305, 225, 5))

    result = search_packing(container, (gift_box, gift_bag))

    assert result.status == GeometryStatus.FOUND
    assert tuple(item.instance_id for item in result.placements) == (
        "gift-bag",
        "gift-box",
    )
    assert result.placements[0].position.z == 0
    assert result.placements[1].position.z == 5
    assert layout_is_valid(container, result.placements)
    assert "2种" in result.reason


def test_search_can_return_partial_support_only_after_full_support_search_fails():
    container = DimensionsMm(80, 100, 40)
    base = _unit("base", DimensionsMm(50, 100, 20), stackable=True)
    top = _unit("top", DimensionsMm(80, 100, 20), stackable=False)

    result = search_packing(container, (top, base))

    assert result.status == GeometryStatus.FOUND
    assert tuple(item.instance_id for item in result.placements) == ("base", "top")
    top_placement = result.placements[1]
    assert support_coverage_ratio(top_placement, result.placements) == 0.625
    assert layout_is_valid(container, result.placements)
    assert not layout_is_fully_supported(container, result.placements)
    assert "62%" in result.reason
    assert "稳定性需单独判断" in result.reason


def test_homogeneous_grid_fast_path_avoids_backtracking_explosion():
    units = tuple(
        _unit(f"cube-{index}", DimensionsMm(20, 20, 20))
        for index in range(10)
    )

    result = search_packing(DimensionsMm(100, 100, 100), units)

    assert result.status == GeometryStatus.FOUND
    assert result.searched_nodes == 10
    assert len(result.placements) == 10
    assert layout_is_fully_supported(
        DimensionsMm(100, 100, 100),
        result.placements,
    )
    assert "规则网格快速路径" in result.reason


def test_candidate_order_search_deduplicates_equivalent_units():
    first = _unit("same-a", DimensionsMm(100, 80, 20))
    second = _unit("same-b", DimensionsMm(100, 80, 20))
    other = _unit("other", DimensionsMm(90, 70, 30))

    orders = list(
        carton_packing_module._candidate_unit_orders((first, second, other))
    )

    assert len(orders) == 3


def test_search_deadline_is_shared_and_returns_unknown(monkeypatch):
    calls = 0

    def fake_monotonic() -> float:
        nonlocal calls
        calls += 1
        return 0.0 if calls == 1 else 2.0

    monkeypatch.setattr(carton_packing_module, "monotonic", fake_monotonic)
    unit = _unit("one", DimensionsMm(10, 10, 10))

    result = search_packing(
        DimensionsMm(20, 20, 20),
        (unit,),
        max_search_seconds=1.0,
    )

    assert result.status == GeometryStatus.UNKNOWN
    assert result.searched_nodes == 1
    assert "搜索时间上限" in result.reason
