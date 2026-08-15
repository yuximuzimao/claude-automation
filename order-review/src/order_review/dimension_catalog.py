from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import permutations
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping


DEFAULT_DIMENSION_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "packing-dimensions.json"
)


class DimensionType(StrEnum):
    INNER = "inner"
    OUTER = "outer"
    UNKNOWN = "unknown"


class InventoryStatus(StrEnum):
    ACTIVE = "active"
    DEPLETING = "depleting"
    RETIRED = "retired"


class DimensionSource(StrEnum):
    MEASURED = "measured"
    DESIGN_DRAWING = "design_drawing"
    SUPPLIER = "supplier"
    ESTIMATED = "estimated"
    USER_PROVIDED = "user_provided"
    DERIVED_FROM_CONFIRMED_CARTONS = "derived_from_confirmed_cartons"
    UNKNOWN = "unknown"


class OrientationPolicy(StrEnum):
    FIXED = "fixed"
    ALL_AXIS_ALIGNED = "all_axis_aligned"


class CartonUsagePolicy(StrEnum):
    GENERAL_CANDIDATE = "general_candidate"
    CONFIRMED_SCOPE_ONLY = "confirmed_scope_only"
    MANUAL_ONLY = "manual_only"
    FIXED_PLAN_ONLY = "fixed_plan_only"


@dataclass(frozen=True, order=True)
class DimensionsMm:
    length: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if any(value <= 0 for value in self.as_tuple()):
            raise ValueError("长、宽、高必须是正整数毫米")

    @classmethod
    def from_value(cls, value: object) -> DimensionsMm:
        if not isinstance(value, list) or len(value) != 3:
            raise ValueError("尺寸必须是包含三个正整数的数组")
        if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
            raise ValueError("尺寸必须使用整数毫米")
        return cls(*value)

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.length, self.width, self.height)

    @property
    def volume(self) -> int:
        return self.length * self.width * self.height

    def orientations(
        self,
        policy: OrientationPolicy = OrientationPolicy.ALL_AXIS_ALIGNED,
    ) -> tuple[DimensionsMm, ...]:
        if policy == OrientationPolicy.FIXED:
            return (self,)
        return tuple(
            DimensionsMm(*values)
            for values in sorted(set(permutations(self.as_tuple())))
        )

    def fits_inside(self, container: DimensionsMm) -> bool:
        return all(
            item <= available
            for item, available in zip(self.as_tuple(), container.as_tuple())
        )


@dataclass(frozen=True)
class CartonSpec:
    carton_id: str
    display_name: str
    brand_id: str
    dimensions: DimensionsMm
    dimension_type: DimensionType
    inventory_status: InventoryStatus
    evidence_source: DimensionSource
    usage_policy: CartonUsagePolicy = CartonUsagePolicy.GENERAL_CANDIDATE

    @property
    def can_be_new_candidate(self) -> bool:
        return (
            self.inventory_status != InventoryStatus.RETIRED
            and self.usage_policy == CartonUsagePolicy.GENERAL_CANDIDATE
        )


@dataclass(frozen=True)
class ProductDimensionSpec:
    product_spec_id: str
    display_name: str
    brand_id: str
    merchant_codes: tuple[str, ...]
    dimensions: DimensionsMm
    dimension_source: DimensionSource
    orientation_policy: OrientationPolicy
    stackable: bool


@dataclass(frozen=True)
class ConfirmedCartonArrangement:
    product_spec_id: str
    grid: tuple[int, int, int]
    item_orientation: DimensionsMm

    @property
    def quantity(self) -> int:
        first, second, third = self.grid
        return first * second * third

    @property
    def occupied_dimensions(self) -> DimensionsMm:
        return DimensionsMm(
            self.grid[0] * self.item_orientation.length,
            self.grid[1] * self.item_orientation.width,
            self.grid[2] * self.item_orientation.height,
        )


@dataclass(frozen=True)
class DedicatedOriginalCartonSpec:
    carton_id: str
    display_name: str
    brand_id: str
    capacity: int
    minimum_shippable_quantity: int
    dimensions: DimensionsMm | None
    dimension_type: DimensionType
    inventory_status: InventoryStatus
    evidence_source: DimensionSource
    allowed_merchant_codes: tuple[str, ...]
    allow_mixed_eligible_products: bool
    closed_shipping_unit: bool
    allow_other_products: bool
    confirmed_arrangement: ConfirmedCartonArrangement | None

    def accepts_closed_unit(self, quantities: Mapping[str, int]) -> bool:
        normalized = {
            code.strip(): quantity
            for code, quantity in quantities.items()
            if quantity > 0
        }
        if not normalized or any(
            code not in self.allowed_merchant_codes for code in normalized
        ):
            return False
        if len(normalized) > 1 and not self.allow_mixed_eligible_products:
            return False
        total_quantity = sum(normalized.values())
        return self.minimum_shippable_quantity <= total_quantity <= self.capacity


@dataclass(frozen=True)
class ConfirmedCapacityEvidence:
    carton_id: str
    capacity: int
    product_spec_id: str | None
    allowed_merchant_codes: tuple[str, ...]
    is_maximum: bool
    scope_complete: bool
    mixing_policy: str


@dataclass(frozen=True)
class ConfirmedParcelQuantityRule:
    rule_id: str
    display_name: str
    allowed_merchant_codes: tuple[str, ...]
    minimum_quantity: int
    maximum_quantity: int
    allow_mixed_eligible_products: bool
    blocks_geometry_above_maximum: bool
    reason: str

    def matches_scope(self, quantities: Mapping[str, int]) -> bool:
        normalized = {
            code.strip(): quantity
            for code, quantity in quantities.items()
            if code.strip() and quantity > 0
        }
        if not normalized or any(
            code not in self.allowed_merchant_codes for code in normalized
        ):
            return False
        return self.allow_mixed_eligible_products or len(normalized) == 1

    def accepts(self, quantities: Mapping[str, int]) -> bool:
        if not self.matches_scope(quantities):
            return False
        total_quantity = sum(quantities.values())
        return self.minimum_quantity <= total_quantity <= self.maximum_quantity


@dataclass(frozen=True)
class ConfirmedSinglePackageExclusionRule:
    rule_id: str
    exact_items: tuple[FixedBundleItem, ...]
    allowed_merchant_codes: tuple[str, ...]
    total_quantity: int | None
    allow_mixed_eligible_products: bool
    reason: str

    def matches(self, quantities: Mapping[str, int]) -> bool:
        normalized = {
            code.strip(): quantity
            for code, quantity in quantities.items()
            if code.strip() and quantity > 0
        }
        if self.exact_items:
            expected: dict[str, int] = {}
            for item in self.exact_items:
                expected[item.merchant_code] = (
                    expected.get(item.merchant_code, 0) + item.quantity
                )
            return normalized == expected
        if not normalized or any(
            code not in self.allowed_merchant_codes for code in normalized
        ):
            return False
        if len(normalized) > 1 and not self.allow_mixed_eligible_products:
            return False
        return sum(normalized.values()) == self.total_quantity


@dataclass(frozen=True)
class GeometryExclusionRule:
    rule_id: str
    product_name_contains: tuple[str, ...]
    fallback: str
    reason: str

    def matches(self, product_name: str) -> bool:
        return any(marker in product_name for marker in self.product_name_contains)


@dataclass(frozen=True)
class FixedBundleItem:
    merchant_code: str
    quantity: int


@dataclass(frozen=True)
class FixedPackingRule:
    rule_id: str
    carton_id: str
    bundle_items: tuple[FixedBundleItem, ...]
    minimum_bundles_per_carton: int
    maximum_bundles_per_carton: int
    split_strategy: str
    fallback: str


@dataclass(frozen=True)
class DimensionCatalog:
    schema_version: int
    outer_to_inner_reduction: DimensionsMm
    cartons: tuple[CartonSpec, ...]
    products: tuple[ProductDimensionSpec, ...]
    dedicated_original_cartons: tuple[DedicatedOriginalCartonSpec, ...]
    confirmed_capacities: tuple[ConfirmedCapacityEvidence, ...]
    confirmed_parcel_quantity_rules: tuple[ConfirmedParcelQuantityRule, ...]
    confirmed_single_package_exclusions: tuple[
        ConfirmedSinglePackageExclusionRule,
        ...,
    ]
    geometry_exclusions: tuple[GeometryExclusionRule, ...]
    fixed_packing_rules: tuple[FixedPackingRule, ...]
    pending_mappings: tuple[Mapping[str, str], ...]
    carton_name_semantics: str
    _cartons_by_id: Mapping[str, CartonSpec]
    _original_cartons_by_id: Mapping[str, DedicatedOriginalCartonSpec]
    _products_by_merchant_code: Mapping[str, ProductDimensionSpec]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_DIMENSION_CATALOG_PATH) -> DimensionCatalog:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("尺寸目录顶层必须是对象")
        if payload.get("schemaVersion") != 2:
            raise ValueError("不支持的尺寸目录版本")
        if payload.get("unit") != "mm":
            raise ValueError("尺寸目录必须统一使用毫米")
        if payload.get("cartonNameSemantics") != "label_only":
            raise ValueError("纸箱名称必须明确为仅标签语义")
        outer_to_inner_reduction = DimensionsMm.from_value(
            payload.get("outerToInnerReductionMm")
        )

        cartons = tuple(_parse_carton(item) for item in _items(payload, "cartons"))
        products = tuple(_parse_product(item) for item in _items(payload, "products"))
        original_cartons = tuple(
            _parse_original_carton(item)
            for item in _items(payload, "dedicatedOriginalCartons")
        )
        confirmed_capacities = tuple(
            _parse_confirmed_capacity(item)
            for item in _items(payload, "confirmedCapacities")
        )
        confirmed_parcel_quantity_rules = tuple(
            _parse_confirmed_parcel_quantity_rule(item)
            for item in _items(payload, "confirmedParcelQuantityRules")
        )
        confirmed_single_package_exclusions = tuple(
            _parse_confirmed_single_package_exclusion(item)
            for item in _items(payload, "confirmedSinglePackageExclusions")
        )
        geometry_exclusions = tuple(
            _parse_geometry_exclusion(item)
            for item in _items(payload, "geometryExclusions")
        )
        fixed_packing_rules = tuple(
            _parse_fixed_packing_rule(item)
            for item in _items(payload, "fixedPackingRules")
        )
        pending_mappings = tuple(
            MappingProxyType(
                {
                    str(key): str(value)
                    for key, value in item.items()
                }
            )
            for item in _items(payload, "pendingMappings")
        )
        cartons_by_id = _unique_mapping(cartons, lambda item: item.carton_id, "纸箱ID")
        original_cartons_by_id = _unique_mapping(
            original_cartons,
            lambda item: item.carton_id,
            "专用原箱ID",
        )

        products_by_code: dict[str, ProductDimensionSpec] = {}
        product_ids: set[str] = set()
        for product in products:
            if product.product_spec_id in product_ids:
                raise ValueError(f"产品尺寸规格ID重复：{product.product_spec_id}")
            product_ids.add(product.product_spec_id)
            for code in product.merchant_codes:
                if code in products_by_code:
                    raise ValueError(f"商家编码重复登记尺寸：{code}")
                products_by_code[code] = product

        product_spec_ids = {item.product_spec_id for item in products}
        for evidence in confirmed_capacities:
            if evidence.carton_id not in cartons_by_id:
                raise ValueError(f"容量证据引用未知纸箱：{evidence.carton_id}")
            if (
                evidence.product_spec_id is not None
                and evidence.product_spec_id not in product_spec_ids
            ):
                raise ValueError(
                    f"容量证据引用未知产品规格：{evidence.product_spec_id}"
                )
        for rule in fixed_packing_rules:
            if rule.carton_id not in cartons_by_id:
                raise ValueError(f"固定规则引用未知纸箱：{rule.carton_id}")
        for original_carton in original_cartons:
            arrangement = original_carton.confirmed_arrangement
            if arrangement is None:
                continue
            if arrangement.product_spec_id not in product_spec_ids:
                raise ValueError(
                    "原箱排列引用未知产品规格："
                    f"{arrangement.product_spec_id}"
                )
            if arrangement.quantity != original_carton.capacity:
                raise ValueError(
                    f"原箱排列数量与容量不一致：{original_carton.carton_id}"
                )
            if (
                original_carton.dimensions is not None
                and not arrangement.occupied_dimensions.fits_inside(
                    original_carton.dimensions
                )
            ):
                raise ValueError(
                    f"原箱确认排列超过外箱尺寸：{original_carton.carton_id}"
                )

        return cls(
            schema_version=2,
            outer_to_inner_reduction=outer_to_inner_reduction,
            cartons=cartons,
            products=products,
            dedicated_original_cartons=original_cartons,
            confirmed_capacities=confirmed_capacities,
            confirmed_parcel_quantity_rules=confirmed_parcel_quantity_rules,
            confirmed_single_package_exclusions=confirmed_single_package_exclusions,
            geometry_exclusions=geometry_exclusions,
            fixed_packing_rules=fixed_packing_rules,
            pending_mappings=pending_mappings,
            carton_name_semantics="label_only",
            _cartons_by_id=MappingProxyType(cartons_by_id),
            _original_cartons_by_id=MappingProxyType(original_cartons_by_id),
            _products_by_merchant_code=MappingProxyType(products_by_code),
        )

    def carton(self, carton_id: str) -> CartonSpec:
        try:
            return self._cartons_by_id[carton_id]
        except KeyError as exc:
            raise KeyError(f"未知纸箱ID：{carton_id}") from exc

    def product(self, merchant_code: str) -> ProductDimensionSpec | None:
        return self._products_by_merchant_code.get(merchant_code.strip())

    def original_carton(self, carton_id: str) -> DedicatedOriginalCartonSpec:
        try:
            return self._original_cartons_by_id[carton_id]
        except KeyError as exc:
            raise KeyError(f"未知专用原箱ID：{carton_id}") from exc

    def geometry_exclusion_for_name(
        self,
        product_name: str,
    ) -> GeometryExclusionRule | None:
        return next(
            (rule for rule in self.geometry_exclusions if rule.matches(product_name)),
            None,
        )

    def candidate_cartons(self) -> tuple[CartonSpec, ...]:
        return tuple(item for item in self.cartons if item.can_be_new_candidate)

    def candidate_cartons_for_codes(
        self,
        merchant_codes: Iterable[str],
    ) -> tuple[CartonSpec, ...]:
        products = tuple(
            self.product(code)
            for code in {item.strip() for item in merchant_codes if item.strip()}
        )
        if not products or any(item is None for item in products):
            return ()
        brand_ids = {item.brand_id for item in products if item is not None}
        if len(brand_ids) != 1:
            return ()
        brand_id = next(iter(brand_ids))
        return tuple(
            item
            for item in self.candidate_cartons()
            if item.brand_id == brand_id
        )

    def usable_carton_dimensions(self, carton: CartonSpec) -> DimensionsMm:
        if carton.dimension_type == DimensionType.INNER:
            return carton.dimensions
        if carton.dimension_type != DimensionType.OUTER:
            return carton.dimensions
        outer = carton.dimensions.as_tuple()
        reduction = self.outer_to_inner_reduction.as_tuple()
        values = tuple(value - deducted for value, deducted in zip(outer, reduction))
        if any(value <= 0 for value in values):
            raise ValueError(f"纸箱扣减后内径无效：{carton.carton_id}")
        return DimensionsMm(*values)


def _items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} 必须是数组")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} 的每一项必须是对象")
    return value


def _required_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} 必须是非空文本")
    return value.strip()


def _parse_carton(item: dict[str, Any]) -> CartonSpec:
    return CartonSpec(
        carton_id=_required_text(item, "cartonId"),
        display_name=_required_text(item, "displayName"),
        brand_id=_required_text(item, "brandId"),
        dimensions=DimensionsMm.from_value(item.get("dimensionsMm")),
        dimension_type=DimensionType(_required_text(item, "dimensionType")),
        inventory_status=InventoryStatus(_required_text(item, "inventoryStatus")),
        evidence_source=DimensionSource(_required_text(item, "evidenceSource")),
        usage_policy=CartonUsagePolicy(
            str(item.get("usagePolicy", CartonUsagePolicy.GENERAL_CANDIDATE))
        ),
    )


def _parse_product(item: dict[str, Any]) -> ProductDimensionSpec:
    codes = item.get("merchantCodes")
    if (
        not isinstance(codes, list)
        or not codes
        or any(not isinstance(code, str) or not code.strip() for code in codes)
    ):
        raise ValueError("merchantCodes 必须是非空商家编码数组")
    stackable = item.get("stackable")
    if not isinstance(stackable, bool):
        raise ValueError("stackable 必须是布尔值")
    return ProductDimensionSpec(
        product_spec_id=_required_text(item, "productSpecId"),
        display_name=_required_text(item, "displayName"),
        brand_id=_required_text(item, "brandId"),
        merchant_codes=tuple(code.strip() for code in codes),
        dimensions=DimensionsMm.from_value(item.get("dimensionsMm")),
        dimension_source=DimensionSource(_required_text(item, "dimensionSource")),
        orientation_policy=OrientationPolicy(_required_text(item, "orientationPolicy")),
        stackable=stackable,
    )


def _parse_original_carton(item: dict[str, Any]) -> DedicatedOriginalCartonSpec:
    dimensions_value = item.get("dimensionsMm")
    dimensions = (
        None if dimensions_value is None else DimensionsMm.from_value(dimensions_value)
    )
    dimension_type = DimensionType(_required_text(item, "dimensionType"))
    if (dimensions is None) != (dimension_type == DimensionType.UNKNOWN):
        raise ValueError("原箱尺寸未知时 dimensionType 必须为 unknown，反之亦然")
    capacity = _positive_int(item, "capacity")
    minimum_shippable_quantity = (
        _positive_int(item, "minimumShippableQuantity")
        if "minimumShippableQuantity" in item
        else capacity
    )
    if minimum_shippable_quantity > capacity:
        raise ValueError("原箱最低可发数量不能大于容量")
    return DedicatedOriginalCartonSpec(
        carton_id=_required_text(item, "cartonId"),
        display_name=_required_text(item, "displayName"),
        brand_id=_required_text(item, "brandId"),
        capacity=capacity,
        minimum_shippable_quantity=minimum_shippable_quantity,
        dimensions=dimensions,
        dimension_type=dimension_type,
        inventory_status=InventoryStatus(_required_text(item, "inventoryStatus")),
        evidence_source=DimensionSource(_required_text(item, "evidenceSource")),
        allowed_merchant_codes=_text_tuple(item, "allowedMerchantCodes"),
        allow_mixed_eligible_products=_required_bool(
            item,
            "allowMixedEligibleProducts",
        ),
        closed_shipping_unit=_required_bool(item, "closedShippingUnit"),
        allow_other_products=_required_bool(item, "allowOtherProducts"),
        confirmed_arrangement=_parse_confirmed_arrangement(
            item.get("confirmedArrangement")
        ),
    )


def _parse_confirmed_arrangement(
    value: object,
) -> ConfirmedCartonArrangement | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("confirmedArrangement 必须是对象")
    grid_value = value.get("grid")
    if (
        not isinstance(grid_value, list)
        or len(grid_value) != 3
        or any(
            isinstance(part, bool) or not isinstance(part, int) or part <= 0
            for part in grid_value
        )
    ):
        raise ValueError("原箱排列 grid 必须是三个正整数")
    return ConfirmedCartonArrangement(
        product_spec_id=_required_text(value, "productSpecId"),
        grid=tuple(grid_value),
        item_orientation=DimensionsMm.from_value(value.get("itemOrientationMm")),
    )


def _parse_confirmed_capacity(item: dict[str, Any]) -> ConfirmedCapacityEvidence:
    product_spec_id = item.get("productSpecId")
    if product_spec_id is not None:
        product_spec_id = _required_text(item, "productSpecId")
    codes = item.get("allowedMerchantCodes", [])
    if not isinstance(codes, list) or any(
        not isinstance(code, str) or not code.strip() for code in codes
    ):
        raise ValueError("allowedMerchantCodes 必须是商家编码数组")
    if product_spec_id is None and not codes:
        raise ValueError("容量证据必须指定产品规格或商家编码")
    mixing_policy = str(item.get("mixingPolicy", "confirmed_within_spec"))
    if mixing_policy not in {"confirmed_within_spec", "not_confirmed"}:
        raise ValueError(f"不支持的容量混装策略：{mixing_policy}")
    return ConfirmedCapacityEvidence(
        carton_id=_required_text(item, "cartonId"),
        capacity=_positive_int(item, "capacity"),
        product_spec_id=product_spec_id,
        allowed_merchant_codes=tuple(code.strip() for code in codes),
        is_maximum=_required_bool(item, "isMaximum"),
        scope_complete=(
            _required_bool(item, "scopeComplete")
            if "scopeComplete" in item
            else True
        ),
        mixing_policy=mixing_policy,
    )


def _parse_confirmed_parcel_quantity_rule(
    item: dict[str, Any],
) -> ConfirmedParcelQuantityRule:
    minimum = _positive_int(item, "minimumQuantity")
    maximum = _positive_int(item, "maximumQuantity")
    if minimum > maximum:
        raise ValueError("包裹数量规则的最小数量不能大于最大数量")
    return ConfirmedParcelQuantityRule(
        rule_id=_required_text(item, "ruleId"),
        display_name=_required_text(item, "displayName"),
        allowed_merchant_codes=_text_tuple(item, "allowedMerchantCodes"),
        minimum_quantity=minimum,
        maximum_quantity=maximum,
        allow_mixed_eligible_products=_required_bool(
            item,
            "allowMixedEligibleProducts",
        ),
        blocks_geometry_above_maximum=_required_bool(
            item,
            "blocksGeometryAboveMaximum",
        ),
        reason=_required_text(item, "reason"),
    )


def _parse_confirmed_single_package_exclusion(
    item: dict[str, Any],
) -> ConfirmedSinglePackageExclusionRule:
    raw_exact_items = item.get("exactItems", [])
    if not isinstance(raw_exact_items, list) or any(
        not isinstance(value, dict) for value in raw_exact_items
    ):
        raise ValueError("exactItems 必须是对象数组")
    exact_items = tuple(
        FixedBundleItem(
            merchant_code=_required_text(value, "merchantCode"),
            quantity=_positive_int(value, "quantity"),
        )
        for value in raw_exact_items
    )
    raw_codes = item.get("allowedMerchantCodes", [])
    if not isinstance(raw_codes, list) or any(
        not isinstance(code, str) or not code.strip() for code in raw_codes
    ):
        raise ValueError("allowedMerchantCodes 必须是商家编码数组")
    codes = tuple(code.strip() for code in raw_codes)
    total_quantity = (
        _positive_int(item, "totalQuantity")
        if "totalQuantity" in item
        else None
    )
    if bool(exact_items) == bool(codes):
        raise ValueError("单包排除规则必须且只能使用精确商品或编码总数范围之一")
    if codes and total_quantity is None:
        raise ValueError("编码范围单包排除规则必须指定 totalQuantity")
    return ConfirmedSinglePackageExclusionRule(
        rule_id=_required_text(item, "ruleId"),
        exact_items=exact_items,
        allowed_merchant_codes=codes,
        total_quantity=total_quantity,
        allow_mixed_eligible_products=(
            _required_bool(item, "allowMixedEligibleProducts")
            if codes
            else False
        ),
        reason=_required_text(item, "reason"),
    )


def _parse_geometry_exclusion(item: dict[str, Any]) -> GeometryExclusionRule:
    return GeometryExclusionRule(
        rule_id=_required_text(item, "ruleId"),
        product_name_contains=_text_tuple(item, "productNameContains"),
        fallback=_required_text(item, "fallback"),
        reason=_required_text(item, "reason"),
    )


def _parse_fixed_packing_rule(item: dict[str, Any]) -> FixedPackingRule:
    bundle_items = tuple(
        FixedBundleItem(
            merchant_code=_required_text(bundle, "merchantCode"),
            quantity=_positive_int(bundle, "quantity"),
        )
        for bundle in _items(item, "bundleItems")
    )
    minimum = _positive_int(item, "minimumBundlesPerCarton")
    maximum = _positive_int(item, "maximumBundlesPerCarton")
    if minimum > maximum:
        raise ValueError("固定规则的最小套数不能大于最大套数")
    return FixedPackingRule(
        rule_id=_required_text(item, "ruleId"),
        carton_id=_required_text(item, "cartonId"),
        bundle_items=bundle_items,
        minimum_bundles_per_carton=minimum,
        maximum_bundles_per_carton=maximum,
        split_strategy=_required_text(item, "splitStrategy"),
        fallback=_required_text(item, "fallback"),
    )


def _positive_int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} 必须是正整数")
    return value


def _required_bool(item: dict[str, Any], key: str) -> bool:
    value = item.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} 必须是布尔值")
    return value


def _text_tuple(item: dict[str, Any], key: str) -> tuple[str, ...]:
    value = item.get(key)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(part, str) or not part.strip() for part in value)
    ):
        raise ValueError(f"{key} 必须是非空文本数组")
    return tuple(part.strip() for part in value)


def _unique_mapping(items, key, label: str):
    result = {}
    for item in items:
        value = key(item)
        if value in result:
            raise ValueError(f"{label}重复：{value}")
        result[value] = item
    return result
