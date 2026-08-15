from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Iterator

from .dimension_catalog import (
    CartonSpec,
    DimensionCatalog,
    DimensionsMm,
    DimensionType,
    OrientationPolicy,
    ProductDimensionSpec,
)


DEFAULT_MAX_SEARCH_NODES = 100_000


class GeometryStatus(StrEnum):
    FOUND = "found"
    PROVEN_IMPOSSIBLE = "proven_impossible"
    UNKNOWN = "unknown"


class CartonAssessmentStatus(StrEnum):
    FITS_INNER_GEOMETRY = "fits_inner_geometry"
    FITS_OUTER_BOUND_ONLY = "fits_outer_bound_only"
    DOES_NOT_FIT = "does_not_fit"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PackingLine:
    merchant_code: str
    quantity: int

    def __post_init__(self) -> None:
        if not self.merchant_code.strip():
            raise ValueError("商家编码不能为空")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity <= 0
        ):
            raise ValueError("商品数量必须是正整数")


@dataclass(frozen=True)
class PackingUnit:
    instance_id: str
    merchant_code: str
    product_spec_id: str
    display_name: str
    dimensions: DimensionsMm
    orientation_policy: OrientationPolicy
    stackable: bool


@dataclass(frozen=True)
class Point3D:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class PlacedUnit:
    instance_id: str
    merchant_code: str
    product_spec_id: str
    display_name: str
    position: Point3D
    dimensions: DimensionsMm
    stackable: bool

    @property
    def right(self) -> int:
        return self.position.x + self.dimensions.length

    @property
    def back(self) -> int:
        return self.position.y + self.dimensions.width

    @property
    def top(self) -> int:
        return self.position.z + self.dimensions.height


@dataclass(frozen=True)
class PackingGeometryResult:
    status: GeometryStatus
    container: DimensionsMm
    placements: tuple[PlacedUnit, ...]
    searched_nodes: int
    max_search_nodes: int
    reason: str


@dataclass(frozen=True)
class CartonAssessment:
    carton: CartonSpec
    status: CartonAssessmentStatus
    geometry: PackingGeometryResult
    message: str
    occupied_volume_ratio: float


class MissingProductDimensionsError(ValueError):
    def __init__(self, merchant_codes: Iterable[str]) -> None:
        self.merchant_codes = tuple(sorted(set(merchant_codes)))
        super().__init__(
            "缺少商品尺寸：" + "、".join(self.merchant_codes)
        )


def units_from_catalog(
    catalog: DimensionCatalog,
    lines: Iterable[PackingLine],
) -> tuple[PackingUnit, ...]:
    line_items = tuple(lines)
    if not line_items:
        raise ValueError("装箱商品不能为空")

    missing: list[str] = []
    units: list[PackingUnit] = []
    counts_by_code: dict[str, int] = {}
    for line in line_items:
        code = line.merchant_code.strip()
        product = catalog.product(code)
        if product is None:
            missing.append(code)
            continue
        previous_count = counts_by_code.get(code, 0)
        units.extend(
            _expand_product_units(
                product,
                merchant_code=code,
                quantity=line.quantity,
                start_index=previous_count + 1,
            )
        )
        counts_by_code[code] = previous_count + line.quantity

    if missing:
        raise MissingProductDimensionsError(missing)
    return tuple(units)


def assess_catalog_carton(
    catalog: DimensionCatalog,
    carton_id: str,
    lines: Iterable[PackingLine],
    *,
    max_search_nodes: int = DEFAULT_MAX_SEARCH_NODES,
) -> CartonAssessment:
    carton = catalog.carton(carton_id)
    units = units_from_catalog(catalog, lines)
    return assess_carton(
        carton,
        units,
        container_dimensions=catalog.usable_carton_dimensions(carton),
        effective_dimension_type=(
            DimensionType.INNER
            if carton.dimension_type == DimensionType.OUTER
            else carton.dimension_type
        ),
        dimension_note=(
            "按已确认规则由外尺寸长宽高各减5mm得到可用内径"
            if carton.dimension_type == DimensionType.OUTER
            else ""
        ),
        max_search_nodes=max_search_nodes,
    )


def assess_carton(
    carton: CartonSpec,
    units: Iterable[PackingUnit],
    *,
    container_dimensions: DimensionsMm | None = None,
    effective_dimension_type: DimensionType | None = None,
    dimension_note: str = "",
    max_search_nodes: int = DEFAULT_MAX_SEARCH_NODES,
) -> CartonAssessment:
    unit_items = tuple(units)
    container = container_dimensions or carton.dimensions
    dimension_type = effective_dimension_type or carton.dimension_type
    geometry = search_packing(
        container,
        unit_items,
        max_search_nodes=max_search_nodes,
    )
    status, message = _interpret_geometry(dimension_type, geometry)
    if dimension_note:
        message = f"{dimension_note}；{message}"
    occupied_volume = sum(item.dimensions.volume for item in unit_items)
    return CartonAssessment(
        carton=carton,
        status=status,
        geometry=geometry,
        message=message,
        occupied_volume_ratio=occupied_volume / container.volume,
    )


def search_packing(
    container: DimensionsMm,
    units: Iterable[PackingUnit],
    *,
    max_search_nodes: int = DEFAULT_MAX_SEARCH_NODES,
) -> PackingGeometryResult:
    unit_items = tuple(units)
    if not unit_items:
        raise ValueError("装箱商品不能为空")
    if isinstance(max_search_nodes, bool) or max_search_nodes <= 0:
        raise ValueError("搜索节点上限必须是正整数")

    orientations_by_id: dict[str, tuple[DimensionsMm, ...]] = {}
    for unit in unit_items:
        fitting = tuple(
            item
            for item in unit.dimensions.orientations(unit.orientation_policy)
            if item.fits_inside(container)
        )
        if not fitting:
            return PackingGeometryResult(
                status=GeometryStatus.PROVEN_IMPOSSIBLE,
                container=container,
                placements=(),
                searched_nodes=0,
                max_search_nodes=max_search_nodes,
                reason=f"商品 {unit.instance_id} 的所有允许朝向都超过纸箱边界",
            )
        orientations_by_id[unit.instance_id] = _ordered_orientations(
            container,
            fitting,
        )

    total_volume = sum(item.dimensions.volume for item in unit_items)
    if total_volume > container.volume:
        return PackingGeometryResult(
            status=GeometryStatus.PROVEN_IMPOSSIBLE,
            container=container,
            placements=(),
            searched_nodes=0,
            max_search_nodes=max_search_nodes,
            reason="商品总体积大于纸箱空间",
        )

    ordered_units = tuple(
        sorted(
            unit_items,
            key=lambda item: (
                -item.dimensions.volume,
                -max(item.dimensions.as_tuple()),
                item.product_spec_id,
                item.instance_id,
            ),
        )
    )
    placements: list[PlacedUnit] = []
    searched_nodes = 0
    limit_reached = False

    def place_next(index: int) -> tuple[PlacedUnit, ...] | None:
        nonlocal searched_nodes, limit_reached
        if index == len(ordered_units):
            return tuple(placements)

        unit = ordered_units[index]
        for dimensions in orientations_by_id[unit.instance_id]:
            for position in _candidate_positions(container, placements):
                searched_nodes += 1
                if searched_nodes > max_search_nodes:
                    limit_reached = True
                    return None
                candidate = PlacedUnit(
                    instance_id=unit.instance_id,
                    merchant_code=unit.merchant_code,
                    product_spec_id=unit.product_spec_id,
                    display_name=unit.display_name,
                    position=position,
                    dimensions=dimensions,
                    stackable=unit.stackable,
                )
                if not _inside(container, candidate):
                    continue
                if any(_overlaps(candidate, placed) for placed in placements):
                    continue
                if not _fully_supported(candidate, placements):
                    continue
                placements.append(candidate)
                result = place_next(index + 1)
                if result is not None:
                    return result
                placements.pop()
                if limit_reached:
                    return None
        return None

    result = place_next(0)
    if result is not None:
        return PackingGeometryResult(
            status=GeometryStatus.FOUND,
            container=container,
            placements=result,
            searched_nodes=searched_nodes,
            max_search_nodes=max_search_nodes,
            reason="已找到边界内、不重叠且完整支撑的摆放",
        )
    return PackingGeometryResult(
        status=GeometryStatus.UNKNOWN,
        container=container,
        placements=(),
        searched_nodes=min(searched_nodes, max_search_nodes),
        max_search_nodes=max_search_nodes,
        reason=(
            "达到搜索节点上限，尚未找到摆放"
            if limit_reached
            else "当前有界摆放策略未找到解，不能据此证明装不下"
        ),
    )


def layout_is_valid(
    container: DimensionsMm,
    placements: Iterable[PlacedUnit],
) -> bool:
    placed_items = tuple(placements)
    for index, item in enumerate(placed_items):
        if not _inside(container, item):
            return False
        if any(_overlaps(item, other) for other in placed_items[:index]):
            return False
        if not _fully_supported(item, placed_items[:index]):
            return False
    return True


def _expand_product_units(
    product: ProductDimensionSpec,
    *,
    merchant_code: str,
    quantity: int,
    start_index: int,
) -> tuple[PackingUnit, ...]:
    return tuple(
        PackingUnit(
            instance_id=f"{merchant_code}#{index}",
            merchant_code=merchant_code,
            product_spec_id=product.product_spec_id,
            display_name=product.display_name,
            dimensions=product.dimensions,
            orientation_policy=product.orientation_policy,
            stackable=product.stackable,
        )
        for index in range(start_index, start_index + quantity)
    )


def _ordered_orientations(
    container: DimensionsMm,
    orientations: tuple[DimensionsMm, ...],
) -> tuple[DimensionsMm, ...]:
    def grid_capacity(item: DimensionsMm) -> int:
        return (
            (container.length // item.length)
            * (container.width // item.width)
            * (container.height // item.height)
        )

    return tuple(
        sorted(
            orientations,
            key=lambda item: (
                -grid_capacity(item),
                item.height,
                -(item.length * item.width),
                item.as_tuple(),
            ),
        )
    )


def _candidate_positions(
    container: DimensionsMm,
    placements: list[PlacedUnit],
) -> Iterator[Point3D]:
    x_values = {0, *(item.right for item in placements)}
    y_values = {0, *(item.back for item in placements)}
    z_values = {0, *(item.top for item in placements)}
    for z in sorted(z_values):
        for y in sorted(y_values):
            for x in sorted(x_values):
                if (
                    x < container.length
                    and y < container.width
                    and z < container.height
                ):
                    yield Point3D(x, y, z)


def _inside(container: DimensionsMm, item: PlacedUnit) -> bool:
    return (
        item.position.x >= 0
        and item.position.y >= 0
        and item.position.z >= 0
        and item.right <= container.length
        and item.back <= container.width
        and item.top <= container.height
    )


def _overlaps(first: PlacedUnit, second: PlacedUnit) -> bool:
    return (
        first.position.x < second.right
        and first.right > second.position.x
        and first.position.y < second.back
        and first.back > second.position.y
        and first.position.z < second.top
        and first.top > second.position.z
    )


def _fully_supported(item: PlacedUnit, placements: Iterable[PlacedUnit]) -> bool:
    if item.position.z == 0:
        return True
    supporters = tuple(
        placed
        for placed in placements
        if placed.stackable
        and placed.top == item.position.z
        and placed.position.x < item.right
        and placed.right > item.position.x
        and placed.position.y < item.back
        and placed.back > item.position.y
    )
    if not supporters:
        return False

    x_values = sorted(
        {
            item.position.x,
            item.right,
            *(
                max(item.position.x, supporter.position.x)
                for supporter in supporters
            ),
            *(min(item.right, supporter.right) for supporter in supporters),
        }
    )
    y_values = sorted(
        {
            item.position.y,
            item.back,
            *(
                max(item.position.y, supporter.position.y)
                for supporter in supporters
            ),
            *(min(item.back, supporter.back) for supporter in supporters),
        }
    )
    for x1, x2 in zip(x_values, x_values[1:]):
        for y1, y2 in zip(y_values, y_values[1:]):
            if x1 == x2 or y1 == y2:
                continue
            if not any(
                supporter.position.x <= x1
                and supporter.right >= x2
                and supporter.position.y <= y1
                and supporter.back >= y2
                for supporter in supporters
            ):
                return False
    return True


def _interpret_geometry(
    dimension_type: DimensionType,
    geometry: PackingGeometryResult,
) -> tuple[CartonAssessmentStatus, str]:
    if geometry.status == GeometryStatus.FOUND:
        if dimension_type == DimensionType.INNER:
            return (
                CartonAssessmentStatus.FITS_INNER_GEOMETRY,
                "按纸箱内尺寸已找到三维摆放；仍需遵守包装与仓库操作限制",
            )
        if dimension_type == DimensionType.OUTER:
            return (
                CartonAssessmentStatus.FITS_OUTER_BOUND_ONLY,
                "按纸箱外尺寸理论可摆放；实际可用空间更小，需要内尺寸或实装复核",
            )
        return (
            CartonAssessmentStatus.UNKNOWN,
            "已找到几何摆放，但纸箱尺寸类型未知，不能形成装箱结论",
        )

    if geometry.status == GeometryStatus.PROVEN_IMPOSSIBLE:
        if dimension_type in {DimensionType.INNER, DimensionType.OUTER}:
            return (
                CartonAssessmentStatus.DOES_NOT_FIT,
                geometry.reason,
            )
        return (
            CartonAssessmentStatus.UNKNOWN,
            "纸箱尺寸类型未知，当前必要条件失败不能证明实际装不下",
        )

    return (
        CartonAssessmentStatus.UNKNOWN,
        geometry.reason,
    )
