from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping
from uuid import uuid4

PRODUCT_MAPPING_DATA_ROOT = Path(__file__).resolve().parents[3] / "product-mapping" / "data"
PRODUCT_MAPPING_BRANDS = {
    "kgos": "kgos",
    "hee": "yuexi",
    "yuexi": "yuexi",
}
DEFAULT_PACKING_DIRECTORY_BRANDS = {"kgos", "yuexi"}
DEFAULT_DEPRECATED_BRAND_KEYWORDS = ("RITEKOKO", "KOKO", "希凝", "钥黑")

from .carton_packing import (
    CartonAssessment,
    CartonAssessmentStatus,
    PackingLine,
    PlacedUnit,
    assess_carton,
    assess_catalog_carton,
    units_from_catalog,
)
from .case_repository import ConfirmedCase, JsonCaseRepository, default_case_path
from .dimension_catalog import (
    DEFAULT_DIMENSION_CATALOG_PATH,
    CartonSpec,
    CartonUsagePolicy,
    DimensionCatalog,
    DimensionType,
    InventoryStatus,
)
from .order_identity import same_order_signature_key


PACKING_SIMULATOR_API_VERSION = 1
PACKING_SIMULATOR_ALGORITHM_VERSION = "single-carton-v1"


class PackingSimulatorInputError(ValueError):
    pass


@dataclass(frozen=True)
class SimulatorLine:
    merchant_code: str
    quantity: int
    source_product_id: str = ""
    product_name: str = ""
    platform_order_number: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "SimulatorLine":
        if not isinstance(value, Mapping):
            raise PackingSimulatorInputError("商品行必须是对象")
        merchant_code = str(value.get("merchantCode") or "").strip()
        quantity = value.get("quantity")
        if not merchant_code:
            raise PackingSimulatorInputError("商家编码不能为空")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise PackingSimulatorInputError("商品数量必须是正整数")
        return cls(
            merchant_code=merchant_code,
            quantity=quantity,
            source_product_id=str(value.get("sourceProductId") or ""),
            product_name=str(value.get("productName") or ""),
            platform_order_number=str(value.get("platformOrderNumber") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "merchantCode": self.merchant_code,
            "quantity": self.quantity,
            "sourceProductId": self.source_product_id,
            "productName": self.product_name,
            "platformOrderNumber": self.platform_order_number,
        }


class PackingSimulatorService:
    """装箱实验的只读服务层。

    该服务不连接ERP，也不写正式案例。第一版只开放KGOS的单箱几何实验；纸箱可自动选择或手动指定；
    审单装箱当前只保留仍在使用的 KGOS 与悦希，停用的 KOKO/希凝/钥黑不进入实验目录。
    """

    def __init__(
        self,
        *,
        dimension_catalog_path: str | Path = DEFAULT_DIMENSION_CATALOG_PATH,
        case_path: str | Path | None = None,
    ) -> None:
        self.dimension_catalog_path = Path(dimension_catalog_path)
        self.catalog = DimensionCatalog.load(self.dimension_catalog_path)
        self._raw_catalog = self._load_raw_catalog()
        version_bytes = self.dimension_catalog_path.read_bytes()
        product_dimensions_name = str(self._raw_catalog.get("productDimensionsPath") or "packing-product-dimensions.json").strip()
        self.product_dimensions_path = self.dimension_catalog_path.parent / product_dimensions_name
        try:
            self._product_dimension_payload = json.loads(self.product_dimensions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._product_dimension_payload = {}
        if self.product_dimensions_path.is_file():
            version_bytes += self.product_dimensions_path.read_bytes()
        configured_brands = self._product_dimension_payload.get("activePackingBrands", [])
        self.active_packing_brands = {
            str(value).strip() for value in configured_brands if str(value).strip()
        } if isinstance(configured_brands, list) else set()
        if not self.active_packing_brands:
            self.active_packing_brands = set(DEFAULT_PACKING_DIRECTORY_BRANDS)

        configured_deprecated = self._product_dimension_payload.get("deprecatedBrandKeywords", [])
        self.deprecated_brand_keywords = tuple(
            str(value).strip() for value in configured_deprecated if str(value).strip()
        ) if isinstance(configured_deprecated, list) else ()
        if not self.deprecated_brand_keywords:
            self.deprecated_brand_keywords = DEFAULT_DEPRECATED_BRAND_KEYWORDS

        self.excluded_packing_codes: set[str] = set()
        for item in self._product_dimension_payload.get("excludedFromWarehousePackingProducts", []):
            if not isinstance(item, Mapping):
                continue
            codes = item.get("merchantCodes", [])
            if isinstance(codes, list):
                self.excluded_packing_codes.update(str(code).strip() for code in codes if str(code).strip())

        self.zero_space_merchant_codes: set[str] = set()
        self.zero_space_product_keys: set[str] = set()
        for item in self._product_dimension_payload.get("ignoredZeroSpaceProducts", []):
            if not isinstance(item, Mapping):
                continue
            product_key = str(item.get("productKey") or "").strip()
            if product_key:
                self.zero_space_product_keys.add(product_key)
            codes = item.get("merchantCodes", [])
            if isinstance(codes, list):
                self.zero_space_merchant_codes.update(str(code).strip() for code in codes if str(code).strip())
        self.catalog_version = hashlib.sha256(version_bytes).hexdigest()[:16]
        self.case_repository = JsonCaseRepository(case_path or default_case_path())

    def catalog_view(self) -> dict[str, Any]:
        payload = self._raw_catalog
        pending = list(payload.get("pendingMappings", []))
        pending_cartons = [
            item
            for item in pending
            if item.get("recordType") == "carton_pending_integration"
            or str(item.get("cartonId") or "") in {"carton-17", "carton-18"}
        ]
        pending_units = [
            item
            for item in pending
            if item.get("recordType") == "packing_unit_pending_integration"
        ]
        brands = self._brand_capabilities(payload)
        return {
            "apiVersion": PACKING_SIMULATOR_API_VERSION,
            "algorithmVersion": PACKING_SIMULATOR_ALGORITHM_VERSION,
            "source": {
                "dimensionCatalogPath": str(self.dimension_catalog_path),
                "catalogVersion": self.catalog_version,
                "schemaVersion": payload.get("schemaVersion"),
                "unit": payload.get("unit"),
                "productMeasurementBasis": payload.get("productMeasurementBasis", ""),
                "outerToInnerReductionMm": payload.get("outerToInnerReductionMm"),
            },
            "brands": brands,
            "sections": {
                "cartons": [self._active_carton_view(item) for item in self.catalog.cartons],
                "pendingCartons": [self._pending_record_view(item) for item in pending_cartons],
                "products": [self._product_view(item) for item in self.catalog.products],
                "originalCartons": list(payload.get("dedicatedOriginalCartons", [])),
                "confirmedCapacities": list(payload.get("confirmedCapacities", [])),
                "quantityRules": list(payload.get("confirmedParcelQuantityRules", [])),
                "singlePackageExclusions": list(payload.get("confirmedSinglePackageExclusions", [])),
                "fixedPackingRules": list(payload.get("fixedPackingRules", [])),
                "geometryExclusions": list(payload.get("geometryExclusions", [])),
                "packingUnits": [self._pending_record_view(item) for item in pending_units],
                "fitChecks": list(payload.get("giftPackingFitChecks", [])),
                "measurementReceipts": list(payload.get("cartonMeasurementReceipts", [])),
                "pending": [self._pending_record_view(item) for item in pending],
                "productDirectory": self._product_directory_view(),
            },
        }

    def list_historical_cases(self) -> dict[str, Any]:
        snapshot = self.case_repository.read_snapshot()
        latest: dict[str, ConfirmedCase] = {}
        for case in snapshot.cases:
            if case.is_freight or self._case_has_deprecated_brand(case):
                continue
            key = (
                same_order_signature_key(case.source_snapshot)
                or f"snapshot:{case.source_snapshot.snapshot_id}"
            )
            current = latest.get(key)
            if current is None or (
                case.order_version,
                case.confirmed_at,
                case.case_id,
            ) > (
                current.order_version,
                current.confirmed_at,
                current.case_id,
            ):
                latest[key] = case
        cases = sorted(
            latest.values(),
            key=lambda item: (item.confirmed_at, item.case_id),
            reverse=True,
        )
        return {
            "readOnly": True,
            "casePath": str(self.case_repository.path),
            "cases": [self._case_summary(case) for case in cases],
        }

    def historical_case(self, case_id: str) -> dict[str, Any]:
        case = next(
            (
                item
                for item in self.case_repository.read_snapshot().cases
                if item.case_id == case_id
            ),
            None,
        )
        if case is None or self._case_has_deprecated_brand(case):
            raise KeyError(f"未知案例：{case_id}")
        return {
            "readOnly": True,
            "case": self._case_detail(case),
        }

    def assess_request(
        self,
        *,
        brand_id: str,
        carton_id: str | None,
        lines: Iterable[SimulatorLine | Mapping[str, Any]],
        max_search_nodes: int = 100_000,
    ) -> dict[str, Any]:
        """Run the packing lab in algorithm-only mode.

        The lab intentionally does not consume confirmed carton capacities or
        fixed packing answers. Those belong to the future production decision
        layer; keeping them out here lets saved human plans genuinely test the
        packing algorithm instead of leaking the expected answer.
        """
        normalized_lines = tuple(
            item if isinstance(item, SimulatorLine) else SimulatorLine.from_mapping(item)
            for item in lines
        )
        requested_carton_id = (carton_id or "").strip()
        if requested_carton_id:
            try:
                original_carton = self.catalog.original_carton(requested_carton_id)
            except KeyError:
                original_carton = None
            if original_carton is not None:
                result = self._assess_original_carton(
                    brand_id=brand_id,
                    carton_id=requested_carton_id,
                    lines=normalized_lines,
                    max_search_nodes=max_search_nodes,
                )
                result["selection"] = {
                    "mode": "manual",
                    "selectedCartonId": original_carton.carton_id,
                    "selectedCartonName": original_carton.display_name,
                    "consideredCartonIds": [original_carton.carton_id],
                    "message": "按你指定的产品原箱进行实验；失败时不会自动换箱。",
                }
                return result

            result = self.assess_single_carton(
                brand_id=brand_id,
                carton_id=requested_carton_id,
                lines=normalized_lines,
                max_search_nodes=max_search_nodes,
                use_confirmed_rules=False,
            )
            try:
                carton = self.catalog.carton(requested_carton_id)
            except KeyError:
                result["selection"] = {
                    "mode": "manual",
                    "selectedCartonId": None,
                    "selectedCartonName": None,
                    "consideredCartonIds": [requested_carton_id],
                    "message": "指定的纸箱尚未集成，未进行自动替换。",
                }
                return result
            result["selection"] = {
                "mode": "manual",
                "selectedCartonId": carton.carton_id,
                "selectedCartonName": carton.display_name,
                "consideredCartonIds": [carton.carton_id],
                "message": "按你指定的纸箱进行实验；失败时不会自动换箱。",
            }
            return result
        return self._assess_auto_single_carton(
            brand_id=brand_id,
            lines=normalized_lines,
            max_search_nodes=max_search_nodes,
        )

    def _assess_original_carton(
        self,
        *,
        brand_id: str,
        carton_id: str,
        lines: tuple[SimulatorLine, ...],
        max_search_nodes: int,
    ) -> dict[str, Any]:
        original = self.catalog.original_carton(carton_id)
        ignored_lines = tuple(
            line for line in lines if line.merchant_code in self.zero_space_merchant_codes
        )
        geometry_lines = tuple(
            line for line in lines if line.merchant_code not in self.zero_space_merchant_codes
        )
        request_snapshot = {
            "brandId": brand_id,
            "cartonId": carton_id,
            "lines": [item.to_dict() for item in lines],
            "ignoredZeroSpaceLines": [item.to_dict() for item in ignored_lines],
            "maxSearchNodes": max_search_nodes,
        }
        result = {
            "apiVersion": PACKING_SIMULATOR_API_VERSION,
            "requestId": f"packing-{uuid4()}",
            "catalogVersion": self.catalog_version,
            "algorithmVersion": PACKING_SIMULATOR_ALGORITHM_VERSION,
            "request": request_snapshot,
            "business": {"status": "unknown", "reasons": [], "evidenceIds": []},
            "geometry": {
                "status": "not_run",
                "message": "",
                "containerMm": None,
                "placements": [],
                "searchedNodes": 0,
                "maxSearchNodes": max_search_nodes,
                "elapsedMs": 0.0,
                "occupiedVolumeRatio": None,
                "completenessVerified": False,
                "supportModelWarning": "",
            },
            "evidence": {"level": "none", "summary": ""},
        }

        brand_id = brand_id.strip()
        if original.brand_id != brand_id:
            result["business"] = {
                "status": "brand_mismatch",
                "reasons": [f"产品原箱品牌为 {original.brand_id}，不能用于 {brand_id} 商品。"],
                "evidenceIds": [],
            }
            return result
        if original.inventory_status == InventoryStatus.RETIRED:
            result["business"] = {
                "status": "carton_retired",
                "reasons": ["该产品原箱已停用。"],
                "evidenceIds": [],
            }
            return result
        if original.dimensions is None:
            result["business"] = {
                "status": "missing_carton_dimensions",
                "reasons": ["该产品原箱尚未记录尺寸，不能进入几何模拟。"],
                "evidenceIds": [],
            }
            return result
        if not geometry_lines:
            result["business"] = {
                "status": "original_carton_not_applicable",
                "reasons": ["产品原箱必须对应一个实际占空间的商品。"],
                "evidenceIds": [],
            }
            return result

        quantities: Counter[str] = Counter()
        for line in geometry_lines:
            quantities[line.merchant_code] += line.quantity
        if len(quantities) != 1 or not original.accepts_closed_unit(quantities):
            result["business"] = {
                "status": "original_carton_not_applicable",
                "reasons": [
                    f"该原箱只在单一对应商品且数量为 {original.minimum_shippable_quantity}–{original.capacity} 时可选。"
                ],
                "evidenceIds": [],
            }
            return result

        products = [self.catalog.product(code) for code in quantities]
        if any(product is None for product in products):
            result["business"] = {
                "status": "missing_product_dimensions",
                "reasons": ["对应商品缺少正式尺寸，不能进入几何模拟。"],
                "evidenceIds": [],
            }
            return result
        if {product.brand_id for product in products if product is not None} != {brand_id}:
            result["business"] = {
                "status": "brand_mismatch",
                "reasons": ["商品品牌与产品原箱品牌不一致。"],
                "evidenceIds": [],
            }
            return result

        proxy_carton = CartonSpec(
            carton_id=original.carton_id,
            display_name=original.display_name,
            brand_id=original.brand_id,
            dimensions=original.dimensions,
            dimension_type=original.dimension_type,
            inventory_status=original.inventory_status,
            evidence_source=original.evidence_source,
            usage_policy=CartonUsagePolicy.GENERAL_CANDIDATE,
        )
        packing_lines = tuple(
            PackingLine(code, quantity) for code, quantity in sorted(quantities.items())
        )
        units = units_from_catalog(self.catalog, packing_lines)
        container = self.catalog.usable_carton_dimensions(proxy_carton)
        started = time.perf_counter()
        assessment = assess_carton(
            proxy_carton,
            units,
            container_dimensions=container,
            effective_dimension_type=(
                DimensionType.INNER
                if original.dimension_type == DimensionType.OUTER
                else original.dimension_type
            ),
            dimension_note=(
                "按已确认规则由外尺寸长宽高各减5mm得到可用内径"
                if original.dimension_type == DimensionType.OUTER
                else ""
            ),
            max_search_nodes=max_search_nodes,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        complete = self._verify_found_layout(assessment, packing_lines)
        result["business"] = {
            "status": "experiment_allowed",
            "reasons": ["该产品原箱符合当前单一商品与数量范围，只作为指定容器参与纯算法模拟。"],
            "evidenceIds": [],
        }
        result["geometry"] = self._assessment_geometry_view(
            assessment,
            completeness_verified=complete,
        )
        result["geometry"]["elapsedMs"] = round(elapsed_ms, 3)
        result["evidence"] = {
            "level": "geometry_result",
            "summary": assessment.message,
            "evidenceIds": [],
        }
        return result

    def assess_single_carton(
        self,
        *,
        brand_id: str,
        carton_id: str,
        lines: Iterable[SimulatorLine | Mapping[str, Any]],
        max_search_nodes: int = 100_000,
        use_confirmed_rules: bool = True,
    ) -> dict[str, Any]:
        normalized_lines = tuple(
            item if isinstance(item, SimulatorLine) else SimulatorLine.from_mapping(item)
            for item in lines
        )
        if not normalized_lines:
            raise PackingSimulatorInputError("装箱商品不能为空")
        ignored_lines = tuple(
            line for line in normalized_lines if line.merchant_code in self.zero_space_merchant_codes
        )
        geometry_lines = tuple(
            line for line in normalized_lines if line.merchant_code not in self.zero_space_merchant_codes
        )
        brand_id = brand_id.strip()
        carton_id = carton_id.strip()
        if not brand_id:
            raise PackingSimulatorInputError("品牌不能为空")
        if not carton_id:
            raise PackingSimulatorInputError("纸箱不能为空")

        request_snapshot = {
            "brandId": brand_id,
            "cartonId": carton_id,
            "lines": [item.to_dict() for item in normalized_lines],
            "ignoredZeroSpaceLines": [item.to_dict() for item in ignored_lines],
            "maxSearchNodes": max_search_nodes,
        }
        base_result = {
            "apiVersion": PACKING_SIMULATOR_API_VERSION,
            "requestId": f"packing-{uuid4()}",
            "catalogVersion": self.catalog_version,
            "algorithmVersion": PACKING_SIMULATOR_ALGORITHM_VERSION,
            "request": request_snapshot,
            "business": {
                "status": "unknown",
                "reasons": [],
                "evidenceIds": [],
            },
            "geometry": {
                "status": "not_run",
                "message": "",
                "containerMm": None,
                "placements": [],
                "searchedNodes": 0,
                "maxSearchNodes": max_search_nodes,
                "elapsedMs": 0.0,
                "occupiedVolumeRatio": None,
                "completenessVerified": False,
                "supportModelWarning": (
                    "当前底层求解器仍把完整底面支撑作为搜索硬条件；该假设已记录为待修算法问题，"
                    "因此UNKNOWN不能解释为装不下。"
                ),
            },
            "evidence": {
                "level": "none",
                "summary": "",
            },
        }

        capability = self._capability_for_brand(brand_id)
        if capability["packingStatus"] != "enabled_single_carton":
            base_result["business"] = {
                "status": "capability_not_enabled",
                "reasons": [capability["packingMessage"]],
                "evidenceIds": [],
            }
            base_result["evidence"] = {
                "level": "catalog_only",
                "summary": "资料可展示，但该品牌当前未开放装箱实验。",
            }
            return base_result

        product_specs = []
        missing_codes: list[str] = []
        for line in geometry_lines:
            product = self.catalog.product(line.merchant_code)
            if product is None:
                missing_codes.append(line.merchant_code)
            else:
                product_specs.append(product)
        if missing_codes:
            base_result["business"] = {
                "status": "missing_product_dimensions",
                "reasons": ["缺少正式商品尺寸：" + "、".join(sorted(set(missing_codes)))],
                "evidenceIds": [],
            }
            base_result["evidence"] = {
                "level": "insufficient",
                "summary": "待补资料不能被静默提升为正式几何输入。",
            }
            return base_result

        product_brands = {item.brand_id for item in product_specs}
        if geometry_lines and product_brands != {brand_id}:
            base_result["business"] = {
                "status": "brand_mismatch",
                "reasons": [
                    "商品品牌与实验品牌不一致：" + "、".join(sorted(product_brands))
                ],
                "evidenceIds": [],
            }
            return base_result

        try:
            carton = self.catalog.carton(carton_id)
        except KeyError:
            base_result["business"] = {
                "status": "carton_not_integrated",
                "reasons": ["该箱型目前仅存在于待集成资料或不存在，不能进入正式几何输入。"],
                "evidenceIds": [],
            }
            return base_result

        if carton.brand_id != brand_id:
            base_result["business"] = {
                "status": "brand_mismatch",
                "reasons": [f"纸箱品牌为 {carton.brand_id}，不能用于 {brand_id} 商品。"],
                "evidenceIds": [],
            }
            return base_result
        if carton.inventory_status == InventoryStatus.RETIRED:
            base_result["business"] = {
                "status": "carton_retired",
                "reasons": ["该纸箱已停用。"],
                "evidenceIds": [],
            }
            return base_result
        if carton.usage_policy != CartonUsagePolicy.GENERAL_CANDIDATE:
            base_result["business"] = {
                "status": "carton_scope_restricted",
                "reasons": [f"该纸箱用途策略为 {carton.usage_policy.value}，当前指定单箱实验不自动放行。"],
                "evidenceIds": [],
            }
            return base_result

        if not geometry_lines:
            usable = self.catalog.usable_carton_dimensions(carton)
            base_result["business"] = {
                "status": "experiment_allowed",
                "reasons": ["本次只有说明卡片/雪梨纸类配件，不计装箱体积，默认可随货放入。"],
                "evidenceIds": [],
            }
            base_result["geometry"] = {
                "status": "fits_inner_geometry",
                "message": "无需几何计算：全部商品均为不计体积配件。",
                "containerMm": list(usable.as_tuple()),
                "placements": [],
                "searchedNodes": 0,
                "maxSearchNodes": max_search_nodes,
                "elapsedMs": 0.0,
                "occupiedVolumeRatio": 0.0,
                "completenessVerified": True,
                "supportModelWarning": "",
            }
            base_result["evidence"] = {
                "level": "packing_policy",
                "summary": "说明卡片/雪梨纸按已确认配件规则忽略体积。",
                "evidenceIds": [],
            }
            return base_result

        quantities = Counter()
        for line in geometry_lines:
            quantities[line.merchant_code] += line.quantity

        blocking_rule = None
        if use_confirmed_rules:
            exclusion = next(
                (
                    rule
                    for rule in self.catalog.confirmed_single_package_exclusions
                    if rule.matches(quantities)
                ),
                None,
            )
            quantity_rule = next(
                (
                    rule
                    for rule in self.catalog.confirmed_parcel_quantity_rules
                    if rule.matches_scope(quantities)
                ),
                None,
            )
            blocking_rule = exclusion
            if (
                blocking_rule is None
                and quantity_rule is not None
                and sum(quantities.values()) > quantity_rule.maximum_quantity
                and quantity_rule.blocks_geometry_above_maximum
            ):
                blocking_rule = quantity_rule

        if blocking_rule is not None:
            base_result["business"] = {
                "status": "blocked_by_confirmed_rule",
                "reasons": [blocking_rule.reason],
                "evidenceIds": [blocking_rule.rule_id],
            }
        else:
            base_result["business"] = {
                "status": "experiment_allowed",
                "reasons": [
                    "纯算法模拟：只使用尺寸与候选箱边界，不读取固定箱量或历史包装答案。"
                    if not use_confirmed_rules
                    else "同品牌通用候选箱；几何结果仅用于实验，不自动形成发货授权。"
                ],
                "evidenceIds": [],
            }

        packing_lines = tuple(
            PackingLine(code, quantity) for code, quantity in sorted(quantities.items())
        )
        started = time.perf_counter()
        assessment = assess_catalog_carton(
            self.catalog,
            carton_id,
            packing_lines,
            max_search_nodes=max_search_nodes,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        complete = self._verify_found_layout(assessment, packing_lines)
        base_result["geometry"] = self._assessment_geometry_view(
            assessment,
            completeness_verified=complete,
        )
        base_result["geometry"]["elapsedMs"] = round(elapsed_ms, 3)

        exact_capacity_ids = (
            self._exact_capacity_evidence_ids(carton_id, quantities)
            if use_confirmed_rules
            else []
        )
        if blocking_rule is not None:
            base_result["evidence"] = {
                "level": "confirmed_rule",
                "summary": (
                    "已有明确业务规则阻止这一整组商品作为单包；几何结果仅作为实验对照，"
                    "不能覆盖该规则。"
                ),
                "evidenceIds": [blocking_rule.rule_id],
            }
        elif exact_capacity_ids:
            base_result["evidence"] = {
                "level": "confirmed_capacity",
                "summary": "当前商品数量精确命中已确认箱型容量；几何图作为额外解释证据。",
                "evidenceIds": exact_capacity_ids,
            }
        elif assessment.status == CartonAssessmentStatus.FITS_INNER_GEOMETRY and complete:
            base_result["evidence"] = {
                "level": "geometry_only",
                "summary": "已找到并完整复核指定箱内的几何摆放，但这不等于业务箱规已确认。",
                "evidenceIds": [],
            }
        elif assessment.status == CartonAssessmentStatus.UNKNOWN:
            base_result["evidence"] = {
                "level": "unknown",
                "summary": "当前有界搜索没有形成结论，不能解释为装不下。",
                "evidenceIds": [],
            }
        else:
            base_result["evidence"] = {
                "level": "geometry_result",
                "summary": assessment.message,
                "evidenceIds": [],
            }
        return base_result

    def _assess_auto_single_carton(
        self,
        *,
        brand_id: str,
        lines: tuple[SimulatorLine, ...],
        max_search_nodes: int,
    ) -> dict[str, Any]:
        if not lines:
            raise PackingSimulatorInputError("装箱商品不能为空")
        brand_id = brand_id.strip()
        if not brand_id:
            raise PackingSimulatorInputError("品牌不能为空")

        capability = self._capability_for_brand(brand_id)
        if capability["packingStatus"] != "enabled_single_carton":
            fallback_carton = next(
                (carton for carton in self.catalog.cartons if carton.brand_id == brand_id),
                None,
            )
            if fallback_carton is None:
                raise PackingSimulatorInputError("该品牌当前没有装箱资料")
            result = self.assess_single_carton(
                brand_id=brand_id,
                carton_id=fallback_carton.carton_id,
                lines=lines,
                max_search_nodes=max_search_nodes,
            )
            result["selection"] = {
                "mode": "auto",
                "selectedCartonId": None,
                "selectedCartonName": None,
                "consideredCartonIds": [],
                "message": capability["packingMessage"],
            }
            return result

        brand_cartons = tuple(
            carton
            for carton in self.catalog.cartons
            if carton.brand_id == brand_id
            and carton.inventory_status != InventoryStatus.RETIRED
            and carton.usage_policy == CartonUsagePolicy.GENERAL_CANDIDATE
        )
        if not brand_cartons:
            raise PackingSimulatorInputError("该品牌当前没有可用于自动单箱实验的纸箱")

        quantities: Counter[str] = Counter()
        for line in lines:
            quantities[line.merchant_code] += line.quantity

        ordered = sorted(
            brand_cartons,
            key=lambda carton: (
                self.catalog.usable_carton_dimensions(carton).volume,
                carton.carton_id,
            ),
        )
        considered: list[str] = []
        first_unknown: dict[str, Any] | None = None
        first_failed: dict[str, Any] | None = None
        remaining_nodes = max_search_nodes

        for carton in ordered:
            if remaining_nodes <= 0:
                break
            considered.append(carton.carton_id)
            result = self.assess_single_carton(
                brand_id=brand_id,
                carton_id=carton.carton_id,
                lines=lines,
                max_search_nodes=remaining_nodes,
                use_confirmed_rules=False,
            )
            remaining_nodes = max(
                0,
                remaining_nodes - int(result["geometry"].get("searchedNodes") or 0),
            )
            if result["business"]["status"] == "blocked_by_confirmed_rule":
                result["selection"] = {
                    "mode": "auto",
                    "selectedCartonId": None,
                    "selectedCartonName": None,
                    "consideredCartonIds": considered,
                    "message": "已有业务规则阻止按单箱直接发货，自动选箱未采用任何纸箱。",
                }
                return result
            if result["business"]["status"] != "experiment_allowed":
                result["selection"] = {
                    "mode": "auto",
                    "selectedCartonId": None,
                    "selectedCartonName": None,
                    "consideredCartonIds": considered,
                    "message": "当前输入不能进入自动单箱实验。",
                }
                return result
            if (
                result["geometry"]["status"]
                == CartonAssessmentStatus.FITS_INNER_GEOMETRY.value
                and result["geometry"]["completenessVerified"]
            ):
                result["selection"] = {
                    "mode": "auto",
                    "selectedCartonId": carton.carton_id,
                    "selectedCartonName": carton.display_name,
                    "consideredCartonIds": considered,
                    "message": "系统在当前单箱范围内自动选择了可行纸箱。",
                }
                return result
            if result["geometry"]["status"] == CartonAssessmentStatus.UNKNOWN.value:
                first_unknown = first_unknown or result
            else:
                first_failed = first_failed or result

        result = first_unknown or first_failed
        if result is None:
            raise PackingSimulatorInputError("没有可评估的纸箱")
        result["selection"] = {
            "mode": "auto",
            "selectedCartonId": None,
            "selectedCartonName": None,
            "consideredCartonIds": considered,
            "message": (
                "当前单箱搜索没有得到确定可用纸箱；若存在UNKNOWN，也不能解释为装不下。"
            ),
        }
        return result

    def _product_directory_view(self) -> list[dict[str, Any]]:
        """Read product identity from product-mapping and attach local packing sizes.

        Product-mapping is the master product directory. The packing project only
        contributes dimensions through ``packing-product-dimensions.json``. New
        feature/pending products therefore appear automatically without editing
        this service or duplicating their names here.
        """
        dimension_payload = self._product_dimension_payload
        dimensions_by_key: dict[str, Mapping[str, Any]] = {}
        if isinstance(dimension_payload, Mapping):
            raw_dimensions = dimension_payload.get("products", [])
            if isinstance(raw_dimensions, list):
                for item in raw_dimensions:
                    if not isinstance(item, Mapping):
                        continue
                    for product_key in item.get("productKeys", []):
                        key = str(product_key or "").strip()
                        if key:
                            dimensions_by_key[key] = item

        identities_by_name: dict[str, Mapping[str, Any]] = {}
        identities_path = PRODUCT_MAPPING_DATA_ROOT / "products" / "erp-identities.json"
        if identities_path.is_file():
            try:
                identity_payload = json.loads(identities_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                identity_payload = {}
            if isinstance(identity_payload, Mapping):
                raw_identities = identity_payload.get("products", [])
                if isinstance(raw_identities, list):
                    for item in raw_identities:
                        if not isinstance(item, Mapping):
                            continue
                        full_name = str(item.get("erpName") or "").strip()
                        if full_name:
                            identities_by_name[full_name] = item

        codes_by_identity: dict[tuple[str, str], set[str]] = {}
        single_records: list[tuple[str, str, str, str]] = []

        def normalize_brand(value: object) -> str:
            raw = str(value or "").strip().lower()
            return PRODUCT_MAPPING_BRANDS.get(raw, raw)

        def record_code(brand_id: str, full_name: str, code: str) -> None:
            if brand_id and full_name and code:
                codes_by_identity.setdefault((brand_id, full_name), set()).add(code)

        def short_name_from_sku(sku_name: object, full_name: str) -> str:
            text = str(sku_name or "").split(";", 1)[0].strip()
            text = re.sub(
                r"\s*[×xX*＊]\s*1\s*(?:盒|瓶|包|袋|个|支|件|套)?(?:装)?\s*$",
                "",
                text,
            ).strip()
            return text or full_name

        sku_records_path = PRODUCT_MAPPING_DATA_ROOT / "sku-records.json"
        if sku_records_path.is_file():
            try:
                sku_records = json.loads(sku_records_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                sku_records = {}
            if isinstance(sku_records, Mapping):
                for record in sku_records.values():
                    if not isinstance(record, Mapping):
                        continue
                    brand_id = normalize_brand(record.get("brand"))
                    recognition = record.get("recognition")
                    if not isinstance(recognition, Mapping):
                        continue
                    items = recognition.get("items")
                    if (
                        recognition.get("type") != "单品"
                        or not isinstance(items, list)
                        or len(items) != 1
                        or not isinstance(items[0], Mapping)
                        or items[0].get("qty") != 1
                    ):
                        continue
                    full_name = str(items[0].get("name") or record.get("erpName") or "").strip()
                    code = str(record.get("erpCode") or "").strip()
                    if not brand_id or not full_name:
                        continue
                    record_code(brand_id, full_name, code)
                    single_records.append(
                        (
                            brand_id,
                            short_name_from_sku(record.get("skuName"), full_name),
                            full_name,
                            code,
                        )
                    )

        for sku_map_path in PRODUCT_MAPPING_DATA_ROOT.glob("products/*/sku-map.json"):
            brand_id = normalize_brand(sku_map_path.parent.name)
            try:
                sku_map = json.loads(sku_map_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(sku_map, Mapping):
                continue
            for group in sku_map.values():
                if not isinstance(group, Mapping):
                    continue
                skus = group.get("skus", [])
                if not isinstance(skus, list):
                    continue
                for sku in skus:
                    if not isinstance(sku, Mapping):
                        continue
                    record_code(
                        brand_id,
                        str(sku.get("erpName") or "").strip(),
                        str(sku.get("erpCode") or "").strip(),
                    )

        pending_products: list[tuple[str, Mapping[str, Any]]] = []
        for pending_path in PRODUCT_MAPPING_DATA_ROOT.glob("products/*/pending-products.json"):
            brand_id = normalize_brand(pending_path.parent.name)
            try:
                payload = json.loads(pending_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, Mapping):
                continue
            products = payload.get("products", [])
            if not isinstance(products, list):
                continue
            for item in products:
                if not isinstance(item, Mapping):
                    continue
                full_name = str(item.get("erpName") or "").strip()
                code = str(item.get("currentOuterId") or "").strip()
                record_code(brand_id, full_name, code)
                pending_products.append((brand_id, item))

        rows: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        seen_full_names: set[tuple[str, str]] = set()

        def append_row(
            *,
            brand_id: str,
            short_name: str,
            full_name: str,
            aliases: Iterable[str] = (),
        ) -> None:
            if brand_id not in self.active_packing_brands:
                return
            identity_text = " ".join([short_name, full_name, *aliases]).upper()
            if any(keyword.upper() in identity_text for keyword in self.deprecated_brand_keywords):
                return
            product_key = f"{brand_id}::{short_name}"
            if not brand_id or not short_name or product_key in seen_keys:
                return
            seen_keys.add(product_key)
            if full_name:
                seen_full_names.add((brand_id, full_name))

            identity = identities_by_name.get(full_name)
            formal_short_name = (
                str(identity.get("shortName") or "").strip()
                if identity is not None
                else ""
            ) or short_name
            main_merchant_code = (
                str(identity.get("mainMerchantCode") or "").strip()
                if identity is not None
                else ""
            )
            raw_spec_codes = identity.get("specMerchantCodes", []) if identity is not None else []
            spec_merchant_codes = [
                str(code).strip()
                for code in raw_spec_codes
                if str(code).strip()
            ] if isinstance(raw_spec_codes, list) else []
            codes = set(codes_by_identity.get((brand_id, full_name), set())) if full_name else set()
            if main_merchant_code:
                codes.add(main_merchant_code)
            codes.update(spec_merchant_codes)
            if codes & self.excluded_packing_codes:
                return
            zero_space = product_key in self.zero_space_product_keys or bool(codes & self.zero_space_merchant_codes)
            clean_aliases = [str(value).strip() for value in aliases if str(value).strip()]
            if formal_short_name != short_name and short_name not in clean_aliases:
                clean_aliases.append(short_name)

            dimension_record = dimensions_by_key.get(product_key)
            dimensions = None
            simulation_code = ""
            product_spec_id = ""
            if dimension_record is not None:
                raw_dimensions = dimension_record.get("dimensionsMm")
                if isinstance(raw_dimensions, list) and len(raw_dimensions) == 3:
                    dimensions = [int(value) for value in raw_dimensions]
                simulation_codes = dimension_record.get("merchantCodes", [])
                product_keys = dimension_record.get("productKeys", [])
                if isinstance(simulation_codes, list):
                    clean_simulation_codes = [
                        str(value).strip() for value in simulation_codes if str(value).strip()
                    ]
                    clean_product_keys = [
                        str(value).strip() for value in product_keys if str(value).strip()
                    ] if isinstance(product_keys, list) else []
                    if (
                        product_key in clean_product_keys
                        and len(clean_product_keys) == len(clean_simulation_codes)
                    ):
                        simulation_code = clean_simulation_codes[
                            clean_product_keys.index(product_key)
                        ]
                    elif clean_simulation_codes:
                        simulation_code = clean_simulation_codes[0]
                product_spec_id = str(dimension_record.get("productSpecId") or "").strip()
            rows.append(
                {
                    "productKey": product_key,
                    "brandId": brand_id,
                    "shortName": formal_short_name,
                    "fullName": full_name,
                    "visualLabel": short_name,
                    "aliases": clean_aliases,
                    "mainMerchantCode": main_merchant_code,
                    "specMerchantCodes": spec_merchant_codes,
                    "merchantCodes": sorted(codes),
                    "missingCode": not bool(main_merchant_code or codes),
                    "dimensionsMm": dimensions,
                    "dimensionsRequired": not zero_space,
                    "missingDimensions": dimensions is None and not zero_space,
                    "packingBehavior": "ignored_zero_space" if zero_space else "normal",
                    "simulationCode": simulation_code or (main_merchant_code if zero_space else ""),
                    "productSpecId": product_spec_id,
                }
            )

        for features_path in PRODUCT_MAPPING_DATA_ROOT.glob("products/*/features.json"):
            brand_id = normalize_brand(features_path.parent.name)
            try:
                features = json.loads(features_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(features, Mapping):
                continue
            for source_short_name, metadata in features.items():
                if str(source_short_name).startswith("_") or not isinstance(metadata, Mapping):
                    continue
                short_name = str(source_short_name).strip()
                if short_name == "阻断片":
                    short_name = "糖果2.0"
                full_name = str(metadata.get("erpName") or "").strip()
                raw_aliases = str(metadata.get("别名") or "")
                aliases = [part.strip() for part in raw_aliases.split(",") if part.strip()]
                append_row(
                    brand_id=brand_id,
                    short_name=short_name,
                    full_name=full_name,
                    aliases=aliases,
                )

        for brand_id, item in pending_products:
            full_name = str(item.get("erpName") or "").strip()
            if (brand_id, full_name) in seen_full_names:
                continue
            append_row(
                brand_id=brand_id,
                short_name=str(item.get("shortName") or full_name).strip(),
                full_name=full_name,
            )

        for brand_id, short_name, full_name, _code in single_records:
            if (brand_id, full_name) in seen_full_names:
                continue
            append_row(
                brand_id=brand_id,
                short_name=short_name,
                full_name=full_name,
            )

        return sorted(
            rows,
            key=lambda item: (
                item["brandId"],
                item["shortName"],
                item["fullName"],
            ),
        )

    def _load_raw_catalog(self) -> dict[str, Any]:
        payload = json.loads(self.dimension_catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("包装资料顶层必须是对象")
        return payload

    def _brand_capabilities(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        known = {item.brand_id for item in self.catalog.products} | {
            item.brand_id for item in self.catalog.cartons
        }
        for item in payload.get("pendingMappings", []):
            brand = str(item.get("brandId") or "").strip()
            if brand:
                known.add(brand)
        labels = {"kgos": "KGOS", "yuexi": "悦希"}
        return [
            {
                "brandId": brand,
                "displayName": labels.get(brand, brand),
                **self._capability_for_brand(brand),
            }
            for brand in sorted(known)
        ]

    @staticmethod
    def _capability_for_brand(brand_id: str) -> dict[str, str]:
        if brand_id == "kgos":
            return {
                "catalogStatus": "available",
                "packingStatus": "enabled_single_carton",
                "packingMessage": "已开放单箱实验；纸箱可由系统自动选择，也可手动指定。",
            }
        if brand_id == "yuexi":
            return {
                "catalogStatus": "available_with_pending_records",
                "packingStatus": "catalog_only",
                "packingMessage": "包装资料与未来组合接口已预留；固定组合尚待逐条确认，暂不开放自动装箱。",
            }
        return {
            "catalogStatus": "available",
            "packingStatus": "catalog_only",
            "packingMessage": "当前品牌仅展示资料，尚未开放装箱实验。",
        }

    def _active_carton_view(self, carton) -> dict[str, Any]:
        usable = self.catalog.usable_carton_dimensions(carton)
        return {
            "cartonId": carton.carton_id,
            "displayName": carton.display_name,
            "brandId": carton.brand_id,
            "dimensionsMm": list(carton.dimensions.as_tuple()),
            "usableDimensionsMm": list(usable.as_tuple()),
            "dimensionType": carton.dimension_type.value,
            "inventoryStatus": carton.inventory_status.value,
            "evidenceSource": carton.evidence_source.value,
            "usagePolicy": carton.usage_policy.value,
            "integrationStatus": "active",
            "experimentSelectable": carton.can_be_new_candidate and carton.brand_id == "kgos",
        }

    @staticmethod
    def _product_view(product) -> dict[str, Any]:
        return {
            "productSpecId": product.product_spec_id,
            "displayName": product.display_name,
            "brandId": product.brand_id,
            "merchantCodes": list(product.merchant_codes),
            "dimensionsMm": list(product.dimensions.as_tuple()),
            "dimensionSource": product.dimension_source.value,
            "orientationPolicy": product.orientation_policy.value,
            "stackable": product.stackable,
            "integrationStatus": "active",
        }

    @staticmethod
    def _pending_record_view(item: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(item)
        result["integrationStatus"] = "pending"
        return result

    def _case_has_deprecated_brand(self, case: ConfirmedCase) -> bool:
        for product in case.source_snapshot.products:
            text = " ".join(
                value
                for value in (
                    product.display_name,
                    product.standard_name,
                    product.short_name,
                    product.merchant_code,
                )
                if value
            ).upper()
            if any(keyword.upper() in text for keyword in self.deprecated_brand_keywords):
                return True
        return False

    def _case_summary(self, case: ConfirmedCase) -> dict[str, Any]:
        return {
            "caseId": case.case_id,
            "confirmedAt": case.confirmed_at,
            "orderVersion": case.order_version,
            "systemOrderId": case.source_snapshot.system_order_id,
            "platformOrderNumbers": list(case.source_snapshot.platform_order_numbers),
            "packageCount": len(case.package_plan.packages),
            "totalQuantity": case.package_plan.total_quantity,
            "products": [
                {
                    "sourceProductId": product.source_product_id,
                    "merchantCode": product.merchant_code,
                    "displayName": product.display_name,
                    "standardName": product.standard_name,
                    "shortName": product.short_name,
                    "quantity": product.quantity,
                    "platformOrderNumber": product.platform_order_number,
                }
                for product in case.source_snapshot.products
            ],
        }

    def _case_detail(self, case: ConfirmedCase) -> dict[str, Any]:
        summary = self._case_summary(case)
        product_by_id = {
            item.source_product_id: item for item in case.source_snapshot.products
        }
        summary["savedPackages"] = [
            {
                "packageId": package.package_id,
                "totalQuantity": package.total_quantity,
                "items": [
                    {
                        "sourceProductId": item.source_product_id,
                        "merchantCode": product_by_id[item.source_product_id].merchant_code,
                        "productName": item.product_name,
                        "quantity": item.quantity,
                        "platformOrderNumber": product_by_id[
                            item.source_product_id
                        ].platform_order_number,
                    }
                    for item in package.items
                ],
            }
            for package in case.package_plan.packages
        ]
        return summary

    def _exact_capacity_evidence_ids(
        self,
        carton_id: str,
        quantities: Mapping[str, int],
    ) -> list[str]:
        total = sum(quantities.values())
        codes = set(quantities)
        result: list[str] = []
        for evidence in self.catalog.confirmed_capacities:
            if evidence.carton_id != carton_id or evidence.capacity != total:
                continue
            if evidence.product_spec_id is not None:
                specs = {self.catalog.product(code) for code in codes}
                if specs and all(
                    item is not None and item.product_spec_id == evidence.product_spec_id
                    for item in specs
                ):
                    result.append(carton_id)
                continue
            if not codes <= set(evidence.allowed_merchant_codes):
                continue
            if evidence.mixing_policy == "not_confirmed" and len(codes) != 1:
                continue
            result.append(carton_id)
        return sorted(set(result))

    def _verify_found_layout(
        self,
        assessment: CartonAssessment,
        lines: tuple[PackingLine, ...],
    ) -> bool:
        if assessment.status != CartonAssessmentStatus.FITS_INNER_GEOMETRY:
            return False
        expected_units = units_from_catalog(self.catalog, lines)
        expected_ids = {item.instance_id for item in expected_units}
        placements = tuple(assessment.geometry.placements)
        if len(placements) != len(expected_units):
            return False
        if len({item.instance_id for item in placements}) != len(placements):
            return False
        if {item.instance_id for item in placements} != expected_ids:
            return False
        container = assessment.geometry.container
        for index, item in enumerate(placements):
            if not self._inside(container.as_tuple(), item):
                return False
            if any(self._overlaps(item, other) for other in placements[:index]):
                return False
        return True

    @staticmethod
    def _inside(container: tuple[int, int, int], item: PlacedUnit) -> bool:
        return (
            item.position.x >= 0
            and item.position.y >= 0
            and item.position.z >= 0
            and item.right <= container[0]
            and item.back <= container[1]
            and item.top <= container[2]
        )

    @staticmethod
    def _overlaps(first: PlacedUnit, second: PlacedUnit) -> bool:
        return (
            first.position.x < second.right
            and first.right > second.position.x
            and first.position.y < second.back
            and first.back > second.position.y
            and first.position.z < second.top
            and first.top > second.position.z
        )

    @staticmethod
    def _assessment_geometry_view(
        assessment: CartonAssessment,
        *,
        completeness_verified: bool,
    ) -> dict[str, Any]:
        geometry = assessment.geometry
        return {
            "status": assessment.status.value,
            "message": assessment.message,
            "reason": geometry.reason,
            "containerMm": list(geometry.container.as_tuple()),
            "placements": [
                {
                    "instanceId": item.instance_id,
                    "merchantCode": item.merchant_code,
                    "productSpecId": item.product_spec_id,
                    "displayName": item.display_name,
                    "positionMm": [item.position.x, item.position.y, item.position.z],
                    "dimensionsMm": list(item.dimensions.as_tuple()),
                }
                for item in geometry.placements
            ],
            "searchedNodes": geometry.searched_nodes,
            "maxSearchNodes": geometry.max_search_nodes,
            "occupiedVolumeRatio": assessment.occupied_volume_ratio,
            "completenessVerified": completeness_verified,
            "supportModelWarning": (
                "当前底层求解器仍把完整底面支撑作为搜索硬条件；该假设已记录为待修算法问题，"
                "因此UNKNOWN不能解释为装不下。"
            ),
        }
