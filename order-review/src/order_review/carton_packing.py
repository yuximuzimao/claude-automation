from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import monotonic
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
DEFAULT_MAX_SEARCH_SECONDS = 2.0
MAX_EXHAUSTIVE_ORDER_UNITS = 8


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
    max_search_seconds: float = DEFAULT_MAX_SEARCH_SECONDS,
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
        max_search_seconds=max_search_seconds,
    )


def assess_carton(
    carton: CartonSpec,
    units: Iterable[PackingUnit],
    *,
    container_dimensions: DimensionsMm | None = None,
    effective_dimension_type: DimensionType | None = None,
    dimension_note: str = "",
    max_search_nodes: int = DEFAULT_MAX_SEARCH_NODES,
    max_search_seconds: float = DEFAULT_MAX_SEARCH_SECONDS,
) -> CartonAssessment:
    unit_items = tuple(units)
    container = container_dimensions or carton.dimensions
    dimension_type = effective_dimension_type or carton.dimension_type
    geometry = search_packing(
        container,
        unit_items,
        max_search_nodes=max_search_nodes,
        max_search_seconds=max_search_seconds,
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
    max_search_seconds: float = DEFAULT_MAX_SEARCH_SECONDS,
) -> PackingGeometryResult:
    unit_items = tuple(units)
    if not unit_items:
        raise ValueError("装箱商品不能为空")
    if isinstance(max_search_nodes, bool) or max_search_nodes <= 0:
        raise ValueError("搜索节点上限必须是正整数")
    if (
        isinstance(max_search_seconds, bool)
        or not isinstance(max_search_seconds, (int, float))
        or max_search_seconds <= 0
    ):
        raise ValueError("搜索时间上限必须是正数")

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

    deadline = monotonic() + float(max_search_seconds)
    grid_layout = _homogeneous_grid_layout(
        container,
        unit_items,
        orientations_by_id,
    )
    if grid_layout is not None:
        grid_nodes = len(grid_layout)
        if monotonic() >= deadline:
            return PackingGeometryResult(
                status=GeometryStatus.UNKNOWN,
                container=container,
                placements=(),
                searched_nodes=grid_nodes,
                max_search_nodes=max_search_nodes,
                reason="达到搜索时间上限，规则网格快速路径结果未被采纳",
            )
        if grid_nodes <= max_search_nodes:
            return PackingGeometryResult(
                status=GeometryStatus.FOUND,
                container=container,
                placements=grid_layout,
                searched_nodes=grid_nodes,
                max_search_nodes=max_search_nodes,
                reason="同类物件规则网格快速路径已找到完整底面支撑摆放",
            )

    searched_nodes = 0
    node_limit_reached = False
    deadline_reached = False
    attempted_orders = 0
    best_partial_support: tuple[PlacedUnit, ...] | None = None
    best_partial_support_ratio = -1.0

    def budget_exhausted() -> bool:
        nonlocal deadline_reached
        if node_limit_reached:
            return True
        if monotonic() >= deadline:
            deadline_reached = True
            return True
        return False

    def try_order(
        ordered_units: tuple[PackingUnit, ...],
    ) -> tuple[PlacedUnit, ...] | None:
        nonlocal searched_nodes, node_limit_reached
        placements: list[PlacedUnit] = []

        def place_next(index: int) -> tuple[PlacedUnit, ...] | None:
            nonlocal searched_nodes, node_limit_reached
            if index == len(ordered_units):
                return tuple(placements)
            if budget_exhausted():
                return None

            unit = ordered_units[index]
            for dimensions in orientations_by_id[unit.instance_id]:
                for position in _candidate_positions(container, placements, dimensions):
                    if budget_exhausted():
                        return None
                    if searched_nodes >= max_search_nodes:
                        node_limit_reached = True
                        return None
                    searched_nodes += 1
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
                    # Geometry feasibility and packing stability are separate concerns.
                    # Elevated items must touch a stackable support surface, but full
                    # footprint coverage is a preference/diagnostic rather than a hard
                    # geometry gate.
                    if candidate.position.z > 0 and support_coverage_ratio(candidate, placements) <= 0:
                        continue
                    placements.append(candidate)
                    result = place_next(index + 1)
                    if result is not None:
                        return result
                    placements.pop()
                    if budget_exhausted():
                        return None
            return None

        return place_next(0)

    for ordered_units in _candidate_unit_orders(unit_items):
        if budget_exhausted():
            break
        attempted_orders += 1
        result = try_order(ordered_units)
        if result is not None:
            minimum_support = min(
                support_coverage_ratio(item, result)
                for item in result
            )
            if minimum_support >= 1.0:
                return PackingGeometryResult(
                    status=GeometryStatus.FOUND,
                    container=container,
                    placements=result,
                    searched_nodes=searched_nodes,
                    max_search_nodes=max_search_nodes,
                    reason=(
                        "已找到边界内、不重叠且全部离地物件完整底面支撑的摆放；"
                        f"已尝试{attempted_orders}种等价去重后的物件顺序"
                    ),
                )
            if minimum_support > best_partial_support_ratio:
                best_partial_support = result
                best_partial_support_ratio = minimum_support

    if best_partial_support is not None:
        return PackingGeometryResult(
            status=GeometryStatus.FOUND,
            container=container,
            placements=best_partial_support,
            searched_nodes=searched_nodes,
            max_search_nodes=max_search_nodes,
            reason=(
                "已找到边界内、不重叠且离地物件存在承重点的几何摆放；"
                f"最低底面支撑覆盖率为{best_partial_support_ratio:.0%}，"
                "未在当前预算内找到完整底面支撑方案，稳定性需单独判断；"
                f"已尝试{attempted_orders}种等价去重后的物件顺序"
            ),
        )

    if deadline_reached:
        reason = (
            "达到搜索时间上限，尚未找到摆放；"
            f"已尝试{attempted_orders}种等价去重后的物件顺序"
        )
    elif node_limit_reached:
        reason = (
            "达到搜索节点上限，尚未找到摆放；"
            f"已尝试{attempted_orders}种等价去重后的物件顺序"
        )
    else:
        reason = (
            "当前有界摆放策略已尝试"
            f"{attempted_orders}种等价去重后的物件顺序但未找到解，"
            "不能据此证明装不下"
        )
    return PackingGeometryResult(
        status=GeometryStatus.UNKNOWN,
        container=container,
        placements=(),
        searched_nodes=searched_nodes,
        max_search_nodes=max_search_nodes,
        reason=reason,
    )


def _candidate_unit_orders(
    units: tuple[PackingUnit, ...],
) -> Iterator[tuple[PackingUnit, ...]]:
    def stable_key(item: PackingUnit) -> tuple[str, str]:
        return (item.product_spec_id, item.instance_id)

    def max_face_area(item: PackingUnit) -> int:
        length, width, height = item.dimensions.as_tuple()
        return max(length * width, length * height, width * height)

    deterministic_orders = (
        tuple(
            sorted(
                units,
                key=lambda item: (
                    -item.dimensions.volume,
                    -max(item.dimensions.as_tuple()),
                    *stable_key(item),
                ),
            )
        ),
        tuple(
            sorted(
                units,
                key=lambda item: (
                    not item.stackable,
                    -max_face_area(item),
                    min(item.dimensions.as_tuple()),
                    -item.dimensions.volume,
                    *stable_key(item),
                ),
            )
        ),
        tuple(
            sorted(
                units,
                key=lambda item: (
                    not item.stackable,
                    min(item.dimensions.as_tuple()),
                    -max_face_area(item),
                    -item.dimensions.volume,
                    *stable_key(item),
                ),
            )
        ),
        tuple(
            sorted(
                units,
                key=lambda item: (
                    -max(item.dimensions.as_tuple()),
                    -max_face_area(item),
                    -item.dimensions.volume,
                    *stable_key(item),
                ),
            )
        ),
    )

    equivalence_key_by_id = {
        item.instance_id: _unit_order_equivalence_key(item) for item in units
    }
    seen_sequences: set[tuple[object, ...]] = set()

    for ordered_units in deterministic_orders:
        sequence = tuple(
            equivalence_key_by_id[item.instance_id] for item in ordered_units
        )
        if sequence in seen_sequences:
            continue
        seen_sequences.add(sequence)
        yield ordered_units

    if len(units) > MAX_EXHAUSTIVE_ORDER_UNITS:
        return

    members_by_key: dict[object, list[PackingUnit]] = {}
    key_order: list[object] = []
    for item in sorted(units, key=stable_key):
        key = equivalence_key_by_id[item.instance_id]
        if key not in members_by_key:
            members_by_key[key] = []
            key_order.append(key)
        members_by_key[key].append(item)

    remaining = {key: len(members) for key, members in members_by_key.items()}
    prefix: list[object] = []

    def build_sequences() -> Iterator[tuple[object, ...]]:
        if len(prefix) == len(units):
            yield tuple(prefix)
            return
        for key in key_order:
            if remaining[key] <= 0:
                continue
            remaining[key] -= 1
            prefix.append(key)
            yield from build_sequences()
            prefix.pop()
            remaining[key] += 1

    for sequence in build_sequences():
        if sequence in seen_sequences:
            continue
        seen_sequences.add(sequence)
        indexes = {key: 0 for key in members_by_key}
        ordered_units: list[PackingUnit] = []
        for key in sequence:
            index = indexes[key]
            ordered_units.append(members_by_key[key][index])
            indexes[key] = index + 1
        yield tuple(ordered_units)


def _unit_order_equivalence_key(unit: PackingUnit) -> tuple[object, ...]:
    orientations = tuple(
        item.as_tuple()
        for item in unit.dimensions.orientations(unit.orientation_policy)
    )
    return (orientations, unit.stackable)


def layout_is_valid(
    container: DimensionsMm,
    placements: Iterable[PlacedUnit],
) -> bool:
    """Validate geometry only: non-empty, inside the container, and non-overlapping."""
    placed_items = tuple(placements)
    if not placed_items:
        return False
    for index, item in enumerate(placed_items):
        if not _inside(container, item):
            return False
        if any(_overlaps(item, other) for other in placed_items[:index]):
            return False
    return True


def layout_is_fully_supported(
    container: DimensionsMm,
    placements: Iterable[PlacedUnit],
) -> bool:
    """Validate full footprint support separately from geometric feasibility."""
    placed_items = tuple(placements)
    if not layout_is_valid(container, placed_items):
        return False
    return all(_fully_supported(item, placed_items) for item in placed_items)


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


def _homogeneous_grid_layout(
    container: DimensionsMm,
    units: tuple[PackingUnit, ...],
    orientations_by_id: dict[str, tuple[DimensionsMm, ...]],
) -> tuple[PlacedUnit, ...] | None:
    if not units:
        return None
    first = units[0]
    equivalence_key = _unit_order_equivalence_key(first)
    if any(_unit_order_equivalence_key(item) != equivalence_key for item in units[1:]):
        return None

    ordered_units = tuple(sorted(units, key=lambda item: item.instance_id))
    for dimensions in orientations_by_id[first.instance_id]:
        nx = container.length // dimensions.length
        ny = container.width // dimensions.width
        nz = container.height // dimensions.height
        if nx <= 0 or ny <= 0 or nz <= 0:
            continue
        if not first.stackable:
            nz = 1
        layer_capacity = nx * ny
        if layer_capacity * nz < len(ordered_units):
            continue

        placements: list[PlacedUnit] = []
        for index, unit in enumerate(ordered_units):
            layer = index // layer_capacity
            offset = index % layer_capacity
            row = offset // nx
            column = offset % nx
            placements.append(
                PlacedUnit(
                    instance_id=unit.instance_id,
                    merchant_code=unit.merchant_code,
                    product_spec_id=unit.product_spec_id,
                    display_name=unit.display_name,
                    position=Point3D(
                        column * dimensions.length,
                        row * dimensions.width,
                        layer * dimensions.height,
                    ),
                    dimensions=dimensions,
                    stackable=unit.stackable,
                )
            )
        if layout_is_fully_supported(container, placements):
            return tuple(placements)
    return None


def _candidate_positions(
    container: DimensionsMm,
    placements: list[PlacedUnit],
    dimensions: DimensionsMm,
) -> Iterator[Point3D]:
    """Yield hybrid extreme-point/frontier candidates with Cartesian fallback.

    Direct frontier points are tried first, then the previous surface-coordinate
    Cartesian combinations are retained as a completeness-oriented fallback for
    the current bounded search. Within the same layer, positions with more
    support coverage are preferred without making full support a hard gate.
    """
    direct_points: set[Point3D] = {Point3D(0, 0, 0)}
    for item in placements:
        direct_points.update(
            {
                Point3D(item.right, item.position.y, item.position.z),
                Point3D(item.position.x, item.back, item.position.z),
                Point3D(item.position.x, item.position.y, item.top),
            }
        )

    x_values = {0, *(item.right for item in placements)}
    y_values = {0, *(item.back for item in placements)}
    z_values = {0, *(item.top for item in placements)}
    all_points = {
        Point3D(x, y, z)
        for z in z_values
        for y in y_values
        for x in x_values
        if (
            x + dimensions.length <= container.length
            and y + dimensions.width <= container.width
            and z + dimensions.height <= container.height
        )
    }

    def candidate_key(point: Point3D) -> tuple[object, ...]:
        coverage = _support_coverage_ratio_at(point, dimensions, placements)
        return (
            point.z,
            -coverage,
            point not in direct_points,
            point.y,
            point.x,
        )

    yield from sorted(all_points, key=candidate_key)


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


def _support_coverage_ratio_at(
    position: Point3D,
    dimensions: DimensionsMm,
    placements: Iterable[PlacedUnit],
) -> float:
    if position.z == 0:
        return 1.0
    right = position.x + dimensions.length
    back = position.y + dimensions.width
    supporters = tuple(
        placed
        for placed in placements
        if placed.stackable
        and placed.top == position.z
        and placed.position.x < right
        and placed.right > position.x
        and placed.position.y < back
        and placed.back > position.y
    )
    if not supporters:
        return 0.0

    x_values = sorted(
        {
            position.x,
            right,
            *(max(position.x, supporter.position.x) for supporter in supporters),
            *(min(right, supporter.right) for supporter in supporters),
        }
    )
    y_values = sorted(
        {
            position.y,
            back,
            *(max(position.y, supporter.position.y) for supporter in supporters),
            *(min(back, supporter.back) for supporter in supporters),
        }
    )
    covered_area = 0
    for x1, x2 in zip(x_values, x_values[1:]):
        for y1, y2 in zip(y_values, y_values[1:]):
            if x1 == x2 or y1 == y2:
                continue
            if any(
                supporter.position.x <= x1
                and supporter.right >= x2
                and supporter.position.y <= y1
                and supporter.back >= y2
                for supporter in supporters
            ):
                covered_area += (x2 - x1) * (y2 - y1)
    return covered_area / (dimensions.length * dimensions.width)


def support_coverage_ratio(
    item: PlacedUnit,
    placements: Iterable[PlacedUnit],
) -> float:
    return _support_coverage_ratio_at(item.position, item.dimensions, placements)


def _fully_supported(item: PlacedUnit, placements: Iterable[PlacedUnit]) -> bool:
    return support_coverage_ratio(item, placements) >= 1.0


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
