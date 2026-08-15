from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Iterable, Mapping

from .carton_packing import (
    CartonAssessmentStatus,
    PackingLine,
    assess_catalog_carton,
)
from .case_repository import ConfirmedCase, JsonCaseRepository, default_case_path
from .dimension_catalog import (
    DEFAULT_DIMENSION_CATALOG_PATH,
    ConfirmedCapacityEvidence,
    DimensionCatalog,
    FixedPackingRule,
)
from .order_identity import same_order_signature_key
from .package_plan import Package


DEFAULT_AUDIT_SEARCH_NODES = 30_000


class PackageEvidenceStatus(StrEnum):
    DEDICATED_ORIGINAL = "dedicated_original_carton"
    FIXED_PLAN = "fixed_plan"
    CONFIRMED_CAPACITY = "confirmed_capacity"
    CONFIRMED_QUANTITY_RANGE = "confirmed_quantity_range"
    GEOMETRY_OUTER_FIT = "geometry_outer_fit"
    GEOMETRY_INNER_FIT = "geometry_inner_fit"
    SAVED_PLAN_ONLY = "saved_plan_only"
    MISSING_DIMENSIONS = "missing_dimensions"
    SEARCH_INCONCLUSIVE = "search_inconclusive"
    NOT_EXPLAINED = "not_explained_by_current_cartons"
    BUSINESS_LIMIT_EXCEEDED = "business_package_limit_exceeded"
    NO_BRAND_COMPATIBLE_CARTON = "no_brand_compatible_carton"
    CONFIRMED_SINGLE_PACKAGE_EXCLUDED = "confirmed_single_package_excluded"


SUPPORTED_STATUSES = frozenset(
    {
        PackageEvidenceStatus.DEDICATED_ORIGINAL,
        PackageEvidenceStatus.FIXED_PLAN,
        PackageEvidenceStatus.CONFIRMED_CAPACITY,
        PackageEvidenceStatus.CONFIRMED_QUANTITY_RANGE,
        PackageEvidenceStatus.GEOMETRY_OUTER_FIT,
        PackageEvidenceStatus.GEOMETRY_INNER_FIT,
    }
)


@dataclass(frozen=True)
class AuditLine:
    merchant_code: str
    product_name: str
    quantity: int


@dataclass(frozen=True)
class PackageAuditDetail:
    case_id: str
    package_id: str
    status: PackageEvidenceStatus
    total_quantity: int
    evidence_ids: tuple[str, ...] = ()
    missing_products: tuple[tuple[str, str], ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "caseId": self.case_id,
            "packageId": self.package_id,
            "status": self.status.value,
            "totalQuantity": self.total_quantity,
            "evidenceIds": list(self.evidence_ids),
            "missingProducts": [
                {"merchantCode": code, "productName": name}
                for code, name in self.missing_products
            ],
            "note": self.note,
        }


@dataclass(frozen=True)
class OrderAuditDetail:
    case_id: str
    saved_package_count: int
    package_statuses: tuple[PackageEvidenceStatus, ...]
    all_saved_packages_supported: bool
    whole_order_single_status: PackageEvidenceStatus | None = None
    whole_order_single_evidence_ids: tuple[str, ...] = ()

    @property
    def potential_package_count_mismatch(self) -> bool:
        return (
            self.saved_package_count > 1
            and self.whole_order_single_status in SUPPORTED_STATUSES
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "caseId": self.case_id,
            "savedPackageCount": self.saved_package_count,
            "packageStatuses": [item.value for item in self.package_statuses],
            "allSavedPackagesSupported": self.all_saved_packages_supported,
            "wholeOrderSingleStatus": (
                self.whole_order_single_status.value
                if self.whole_order_single_status is not None
                else None
            ),
            "wholeOrderSingleEvidenceIds": list(
                self.whole_order_single_evidence_ids
            ),
            "potentialPackageCountMismatch": self.potential_package_count_mismatch,
        }


@dataclass(frozen=True)
class PackingCaseAuditReport:
    case_path: str
    dimension_catalog_path: str
    parcel_order_count: int
    package_count: int
    package_status_counts: Mapping[str, int]
    fully_supported_order_count: int
    potential_single_package_mismatch_count: int
    missing_product_counts: tuple[tuple[str, str, int, int], ...]
    package_details: tuple[PackageAuditDetail, ...]
    order_details: tuple[OrderAuditDetail, ...]

    def to_dict(self, *, include_details: bool = False) -> dict[str, object]:
        result: dict[str, object] = {
            "casePath": self.case_path,
            "dimensionCatalogPath": self.dimension_catalog_path,
            "parcelOrderCount": self.parcel_order_count,
            "packageCount": self.package_count,
            "packageStatusCounts": dict(self.package_status_counts),
            "fullySupportedOrderCount": self.fully_supported_order_count,
            "potentialSinglePackageMismatchCount": (
                self.potential_single_package_mismatch_count
            ),
            "missingProductCounts": [
                {
                    "merchantCode": code,
                    "productName": name,
                    "packageCount": package_count,
                    "quantity": quantity,
                }
                for code, name, package_count, quantity in self.missing_product_counts
            ],
        }
        if include_details:
            result["packageDetails"] = [
                item.to_dict() for item in self.package_details
            ]
            result["orderDetails"] = [item.to_dict() for item in self.order_details]
        return result


class _PackingEvidenceResolver:
    def __init__(
        self,
        catalog: DimensionCatalog,
        *,
        max_search_nodes: int,
    ) -> None:
        self.catalog = catalog
        self.max_search_nodes = max_search_nodes
        self._geometry_cache: dict[
            tuple[tuple[tuple[str, int], ...], str],
            CartonAssessmentStatus,
        ] = {}

    def resolve(
        self,
        *,
        case_id: str,
        package_id: str,
        lines: Iterable[AuditLine],
    ) -> PackageAuditDetail:
        aggregated = _aggregate_lines(lines)
        total_quantity = sum(item.quantity for item in aggregated)

        fixed_rule = next(
            (
                rule
                for rule in self.catalog.fixed_packing_rules
                if _matches_fixed_rule(aggregated, rule)
            ),
            None,
        )
        if fixed_rule is not None:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.FIXED_PLAN,
                total_quantity=total_quantity,
                evidence_ids=(fixed_rule.rule_id, fixed_rule.carton_id),
                note="命中人工确认的固定礼盒拆分规则",
            )

        exclusion = next(
            (
                rule
                for item in aggregated
                for rule in (
                    self.catalog.geometry_exclusion_for_name(item.product_name),
                )
                if rule is not None
            ),
            None,
        )
        if exclusion is not None:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.SAVED_PLAN_ONLY,
                total_quantity=total_quantity,
                evidence_ids=(exclusion.rule_id,),
                note=exclusion.reason,
            )

        quantities: Counter[str] = Counter()
        for item in aggregated:
            if item.merchant_code:
                quantities[item.merchant_code] += item.quantity
        if quantities and sum(quantities.values()) == total_quantity:
            single_package_exclusion = next(
                (
                    item
                    for item in self.catalog.confirmed_single_package_exclusions
                    if item.matches(quantities)
                ),
                None,
            )
            if single_package_exclusion is not None:
                return PackageAuditDetail(
                    case_id=case_id,
                    package_id=package_id,
                    status=(
                        PackageEvidenceStatus.CONFIRMED_SINGLE_PACKAGE_EXCLUDED
                    ),
                    total_quantity=total_quantity,
                    evidence_ids=(single_package_exclusion.rule_id,),
                    note=single_package_exclusion.reason,
                )

            original = next(
                (
                    item
                    for item in self.catalog.dedicated_original_cartons
                    if item.accepts_closed_unit(quantities)
                ),
                None,
            )
            if original is not None:
                quantity_range = (
                    f"{original.minimum_shippable_quantity}–{original.capacity}件"
                    if original.minimum_shippable_quantity != original.capacity
                    else f"{original.capacity}件"
                )
                return PackageAuditDetail(
                    case_id=case_id,
                    package_id=package_id,
                    status=PackageEvidenceStatus.DEDICATED_ORIGINAL,
                    total_quantity=total_quantity,
                    evidence_ids=(original.carton_id,),
                    note=(
                        f"命中专用原箱可发数量 {quantity_range}，"
                        "其他品类不得混入"
                    ),
                )

            quantity_rule = next(
                (
                    item
                    for item in self.catalog.confirmed_parcel_quantity_rules
                    if item.matches_scope(quantities)
                ),
                None,
            )
            if quantity_rule is not None:
                if quantity_rule.accepts(quantities):
                    return PackageAuditDetail(
                        case_id=case_id,
                        package_id=package_id,
                        status=PackageEvidenceStatus.CONFIRMED_QUANTITY_RANGE,
                        total_quantity=total_quantity,
                        evidence_ids=(quantity_rule.rule_id,),
                        note=quantity_rule.reason,
                    )
                if (
                    total_quantity > quantity_rule.maximum_quantity
                    and quantity_rule.blocks_geometry_above_maximum
                ):
                    return PackageAuditDetail(
                        case_id=case_id,
                        package_id=package_id,
                        status=PackageEvidenceStatus.BUSINESS_LIMIT_EXCEEDED,
                        total_quantity=total_quantity,
                        evidence_ids=(quantity_rule.rule_id,),
                        note=(
                            f"超过已确认的单包上限"
                            f"{quantity_rule.maximum_quantity}件；纯几何结果不放行"
                        ),
                    )

        capacity = next(
            (
                item
                for item in self.catalog.confirmed_capacities
                if _matches_confirmed_capacity(aggregated, item, self.catalog)
            ),
            None,
        )
        if capacity is not None:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.CONFIRMED_CAPACITY,
                total_quantity=total_quantity,
                evidence_ids=(capacity.carton_id,),
                note="命中用户确认的实际箱型容量",
            )

        missing = tuple(
            sorted(
                {
                    (item.merchant_code, item.product_name)
                    for item in aggregated
                    if self.catalog.product(item.merchant_code) is None
                }
            )
        )
        if missing:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.MISSING_DIMENSIONS,
                total_quantity=total_quantity,
                missing_products=missing,
                note="至少一个商品缺少最终发货包装尺寸",
            )

        quantities_by_code: Counter[str] = Counter()
        for item in aggregated:
            quantities_by_code[item.merchant_code] += item.quantity
        packing_lines = tuple(
            PackingLine(code, quantity)
            for code, quantity in sorted(quantities_by_code.items())
        )
        fit_outer: list[str] = []
        fit_inner: list[str] = []
        inconclusive = False
        candidate_cartons = self.catalog.candidate_cartons_for_codes(
            quantities_by_code
        )
        if not candidate_cartons:
            brand_ids = sorted(
                {
                    product.brand_id
                    for code in quantities_by_code
                    for product in (self.catalog.product(code),)
                    if product is not None
                }
            )
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.NO_BRAND_COMPATIBLE_CARTON,
                total_quantity=total_quantity,
                note=(
                    "没有同品牌且允许通用计算的纸箱；商品品牌："
                    + "、".join(brand_ids)
                ),
            )
        for carton in candidate_cartons:
            status = self._geometry_status(carton.carton_id, packing_lines)
            if status == CartonAssessmentStatus.FITS_INNER_GEOMETRY:
                fit_inner.append(carton.carton_id)
            elif status == CartonAssessmentStatus.FITS_OUTER_BOUND_ONLY:
                fit_outer.append(carton.carton_id)
            elif status == CartonAssessmentStatus.UNKNOWN:
                inconclusive = True

        fit_inner.sort(key=self._carton_volume_key)
        fit_outer.sort(key=self._carton_volume_key)

        if fit_inner:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.GEOMETRY_INNER_FIT,
                total_quantity=total_quantity,
                evidence_ids=tuple(fit_inner),
                note="按纸箱内尺寸找到可验证摆放",
            )
        if fit_outer:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.GEOMETRY_OUTER_FIT,
                total_quantity=total_quantity,
                evidence_ids=tuple(fit_outer),
                note="按外尺寸找到理论摆放，仍需实际容量或内尺寸复核",
            )
        if inconclusive:
            return PackageAuditDetail(
                case_id=case_id,
                package_id=package_id,
                status=PackageEvidenceStatus.SEARCH_INCONCLUSIVE,
                total_quantity=total_quantity,
                note="当前有界搜索未找到摆放，不能证明装不下",
            )
        return PackageAuditDetail(
            case_id=case_id,
            package_id=package_id,
            status=PackageEvidenceStatus.NOT_EXPLAINED,
            total_quantity=total_quantity,
            note="现有纸箱必要条件均失败；可能缺少历史箱型或尺寸证据",
        )

    def _geometry_status(
        self,
        carton_id: str,
        lines: tuple[PackingLine, ...],
    ) -> CartonAssessmentStatus:
        signature = tuple(sorted((item.merchant_code, item.quantity) for item in lines))
        key = (signature, carton_id)
        cached = self._geometry_cache.get(key)
        if cached is not None:
            return cached
        assessment = assess_catalog_carton(
            self.catalog,
            carton_id,
            lines,
            max_search_nodes=self.max_search_nodes,
        )
        self._geometry_cache[key] = assessment.status
        return assessment.status

    def _carton_volume_key(self, carton_id: str) -> tuple[int, str]:
        carton = self.catalog.carton(carton_id)
        return (carton.dimensions.volume, carton_id)


def build_packing_case_audit(
    cases: Iterable[ConfirmedCase],
    catalog: DimensionCatalog,
    *,
    case_path: str = "",
    dimension_catalog_path: str = "",
    max_search_nodes: int = DEFAULT_AUDIT_SEARCH_NODES,
) -> PackingCaseAuditReport:
    latest_cases = [item for item in _latest_case_per_order(cases) if not item.is_freight]
    resolver = _PackingEvidenceResolver(
        catalog,
        max_search_nodes=max_search_nodes,
    )
    package_details: list[PackageAuditDetail] = []
    order_details: list[OrderAuditDetail] = []
    missing_package_counts: Counter[tuple[str, str]] = Counter()
    missing_quantities: Counter[tuple[str, str]] = Counter()

    for case in latest_cases:
        current_details: list[PackageAuditDetail] = []
        for package in case.package_plan.packages:
            lines = _package_lines(case, package)
            detail = resolver.resolve(
                case_id=case.case_id,
                package_id=package.package_id,
                lines=lines,
            )
            current_details.append(detail)
            package_details.append(detail)
            for code, name in detail.missing_products:
                missing_package_counts[(code, name)] += 1
                missing_quantities[(code, name)] += sum(
                    item.quantity
                    for item in lines
                    if item.merchant_code == code and item.product_name == name
                )

        whole_order_single: PackageAuditDetail | None = None
        if len(case.package_plan.packages) > 1:
            whole_order_single = resolver.resolve(
                case_id=case.case_id,
                package_id="whole-order-single-check",
                lines=_order_lines(case),
            )
        statuses = tuple(item.status for item in current_details)
        order_details.append(
            OrderAuditDetail(
                case_id=case.case_id,
                saved_package_count=len(case.package_plan.packages),
                package_statuses=statuses,
                all_saved_packages_supported=all(
                    item in SUPPORTED_STATUSES for item in statuses
                ),
                whole_order_single_status=(
                    whole_order_single.status if whole_order_single else None
                ),
                whole_order_single_evidence_ids=(
                    whole_order_single.evidence_ids if whole_order_single else ()
                ),
            )
        )

    status_counts = Counter(item.status.value for item in package_details)
    missing = tuple(
        (
            code,
            name,
            package_count,
            missing_quantities[(code, name)],
        )
        for (code, name), package_count in sorted(
            missing_package_counts.items(),
            key=lambda item: (-item[1], item[0][1], item[0][0]),
        )
    )
    return PackingCaseAuditReport(
        case_path=case_path,
        dimension_catalog_path=dimension_catalog_path,
        parcel_order_count=len(latest_cases),
        package_count=len(package_details),
        package_status_counts=dict(sorted(status_counts.items())),
        fully_supported_order_count=sum(
            item.all_saved_packages_supported for item in order_details
        ),
        potential_single_package_mismatch_count=sum(
            item.potential_package_count_mismatch for item in order_details
        ),
        missing_product_counts=missing,
        package_details=tuple(package_details),
        order_details=tuple(order_details),
    )


def _package_lines(case: ConfirmedCase, package: Package) -> tuple[AuditLine, ...]:
    products = case.source_snapshot.product_by_id
    return tuple(
        AuditLine(
            merchant_code=(
                product.merchant_code or product.main_merchant_code or ""
            ).strip(),
            product_name=product.standard_name or product.display_name,
            quantity=item.quantity,
        )
        for item in package.items
        for product in (products[item.source_product_id],)
    )


def _order_lines(case: ConfirmedCase) -> tuple[AuditLine, ...]:
    return tuple(
        AuditLine(
            merchant_code=(
                product.merchant_code or product.main_merchant_code or ""
            ).strip(),
            product_name=product.standard_name or product.display_name,
            quantity=product.quantity,
        )
        for product in case.source_snapshot.products
    )


def _aggregate_lines(lines: Iterable[AuditLine]) -> tuple[AuditLine, ...]:
    quantities: dict[tuple[str, str], int] = {}
    for item in lines:
        key = (item.merchant_code.strip(), item.product_name)
        quantities[key] = quantities.get(key, 0) + item.quantity
    return tuple(
        AuditLine(code, name, quantity)
        for (code, name), quantity in sorted(quantities.items())
        if quantity > 0
    )


def _matches_fixed_rule(
    lines: tuple[AuditLine, ...],
    rule: FixedPackingRule,
) -> bool:
    actual: Counter[str] = Counter()
    for item in lines:
        actual[item.merchant_code] += item.quantity
    for bundle_count in range(
        rule.minimum_bundles_per_carton,
        rule.maximum_bundles_per_carton + 1,
    ):
        expected: Counter[str] = Counter()
        for item in rule.bundle_items:
            expected[item.merchant_code] += item.quantity * bundle_count
        if actual == expected:
            return True
    return False


def _matches_confirmed_capacity(
    lines: tuple[AuditLine, ...],
    evidence: ConfirmedCapacityEvidence,
    catalog: DimensionCatalog,
) -> bool:
    if sum(item.quantity for item in lines) != evidence.capacity:
        return False
    codes = {item.merchant_code for item in lines}
    if evidence.product_spec_id is not None:
        specs = {catalog.product(code) for code in codes}
        return bool(specs) and all(
            item is not None and item.product_spec_id == evidence.product_spec_id
            for item in specs
        )
    allowed = set(evidence.allowed_merchant_codes)
    if not codes or not codes <= allowed:
        return False
    if evidence.mixing_policy == "not_confirmed" and len(codes) != 1:
        return False
    return True


def _latest_case_per_order(cases: Iterable[ConfirmedCase]) -> list[ConfirmedCase]:
    latest: dict[str, ConfirmedCase] = {}
    for case in cases:
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
    return sorted(latest.values(), key=lambda item: (item.confirmed_at, item.case_id))


def main() -> int:
    parser = argparse.ArgumentParser(description="只读审计历史包裹的尺寸与箱型证据")
    parser.add_argument("--cases", default=str(default_case_path()))
    parser.add_argument(
        "--dimensions",
        default=str(DEFAULT_DIMENSION_CATALOG_PATH),
    )
    parser.add_argument("--details", action="store_true")
    parser.add_argument(
        "--max-search-nodes",
        type=int,
        default=DEFAULT_AUDIT_SEARCH_NODES,
    )
    args = parser.parse_args()
    case_path = Path(args.cases)
    dimension_path = Path(args.dimensions)
    report = build_packing_case_audit(
        JsonCaseRepository(case_path).list_cases(),
        DimensionCatalog.load(dimension_path),
        case_path=str(case_path),
        dimension_catalog_path=str(dimension_path),
        max_search_nodes=args.max_search_nodes,
    )
    print(
        json.dumps(
            report.to_dict(include_details=args.details),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
