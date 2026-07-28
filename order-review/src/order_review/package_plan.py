from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

from .models import OrderSnapshot, Product
from .package_equivalence import (
    PACKAGE_EQUIVALENCE_KEY_PREFIX,
    package_equivalence_group,
)


SCHEMA_VERSION = 1


class PackagePlanError(ValueError):
    """包裹方案领域错误。"""


class PackagePlanValidationError(PackagePlanError):
    """方案不满足数量守恒或包裹完整性。"""


class DraftSnapshotMismatchError(PackagePlanError):
    """草稿不属于当前原订单快照。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deep_copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _product_details(product: Product) -> dict[str, Any]:
    return {
        "title": product.title,
        "standardName": product.standard_name,
        "shortName": product.short_name,
        "quantity": product.quantity,
        "merchantCode": product.merchant_code,
        "mainMerchantCode": product.main_merchant_code,
        "platformSpec": product.platform_spec,
        "platformName": product.platform_name,
        "platformProductId": product.spu_id,
        "platformSkuId": product.sku_id,
        "platformOrderNumber": product.platform_order_number,
        "sid": product.sid,
        "oid": product.oid,
        "sourceGroupIndex": product.source_group_index,
        "sourceGroupKey": product.source_group_key,
        "itemLines": list(product.item_lines),
        "detailLines": list(product.detail_lines),
        "rawLines": list(product.raw_lines),
        "rawDataset": _deep_copy_json(product.raw_dataset),
        "rawAttributes": _deep_copy_json(product.raw_attributes),
        "rawText": product.raw_text,
    }


def _group_details(group: Any) -> dict[str, Any]:
    return {
        "index": group.index,
        "key": group.key,
        "orderNumbers": list(group.order_numbers),
        "productIndexes": list(group.product_indexes),
        "dataset": _deep_copy_json(group.dataset),
        "attributes": _deep_copy_json(group.attributes),
        "rawLines": list(group.raw_lines),
        "rawText": group.raw_text,
    }


@dataclass(frozen=True)
class SourceProduct:
    source_product_id: str
    standard_name: str
    short_name: str
    quantity: int
    merchant_code: str = ""
    main_merchant_code: str | None = None
    platform_product_id: str = ""
    platform_sku_id: str = ""
    platform_spec: str = ""
    platform_name: str = ""
    platform_order_number: str = ""
    source_group: str = ""
    _details_json: str = field(default="{}", repr=False)

    @property
    def display_name(self) -> str:
        return self.short_name or self.standard_name or "未命名商品"

    @property
    def details(self) -> dict[str, Any]:
        return json.loads(self._details_json)

    @property
    def match_key(self) -> tuple[str, ...]:
        """用于订单身份和原商品引用的稳定商品身份。"""
        return (
            self.merchant_code,
            self.main_merchant_code or "",
            self.platform_product_id,
            self.platform_sku_id,
            self.standard_name,
            self.platform_spec,
            self.platform_name,
        )

    @property
    def package_match_key(self) -> tuple[str, ...]:
        """用于包裹方案复用的身份；仅对白名单内等体积口味做归组。"""
        group = package_equivalence_group(
            self.merchant_code,
            self.main_merchant_code,
        )
        if group is None:
            return self.match_key
        return (
            PACKAGE_EQUIVALENCE_KEY_PREFIX,
            group,
        )

    def to_dict(self) -> dict[str, Any]:
        result = self.details
        result["sourceProductId"] = self.source_product_id
        result["sourceGroup"] = self.source_group
        return result


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    captured_at: str
    system_order_id: str
    platform_order_numbers: tuple[str, ...]
    products: tuple[SourceProduct, ...]
    _snapshot_json: str = field(repr=False)

    @classmethod
    def from_order_snapshot(
        cls,
        snapshot: OrderSnapshot,
        *,
        captured_at: str | None = None,
    ) -> SourceSnapshot:
        product_payloads = [_product_details(product) for product in snapshot.products]
        source_products: list[SourceProduct] = []
        for index, (product, details) in enumerate(zip(snapshot.products, product_payloads)):
            identity = {"index": index, "details": details}
            source_product_id = f"product-{index + 1}-{_digest(identity)[:12]}"
            source_products.append(
                SourceProduct(
                    source_product_id=source_product_id,
                    standard_name=product.standard_name,
                    short_name=product.short_name,
                    quantity=product.quantity,
                    merchant_code=product.merchant_code,
                    main_merchant_code=product.main_merchant_code,
                    platform_product_id=product.spu_id,
                    platform_sku_id=product.sku_id,
                    platform_spec=product.platform_spec,
                    platform_name=product.platform_name,
                    platform_order_number=product.platform_order_number,
                    source_group=product.source_group_key,
                    _details_json=_canonical_json(details),
                )
            )

        platform_orders = tuple(
            dict.fromkeys(
                value
                for value in (
                    *snapshot.order_numbers,
                    *(product.platform_order_number for product in snapshot.products),
                )
                if value
            )
        )
        immutable_content = {
            "systemOrderId": snapshot.system_order_id,
            "platformOrderNumbers": list(platform_orders),
            "isExpanded": snapshot.is_expanded,
            "hasCanMergeMark": snapshot.has_can_merge_mark,
            "hasSuiteAction": snapshot.has_suite_action,
            "sourceTitle": snapshot.source_title,
            "sourceUrl": snapshot.source_url,
            "rawLines": list(snapshot.raw_lines),
            "rawDataset": _deep_copy_json(snapshot.raw_dataset),
            "rawAttributes": _deep_copy_json(snapshot.raw_attributes),
            "rawText": snapshot.raw_text,
            "groups": [_group_details(group) for group in snapshot.groups],
            "products": [product.to_dict() for product in source_products],
            "rawPayload": _deep_copy_json(snapshot.raw_payload),
        }
        snapshot_id = f"snapshot-{_digest(immutable_content)[:20]}"
        captured_at = captured_at or _utc_now()
        stored = {
            "snapshotId": snapshot_id,
            "capturedAt": captured_at,
            **immutable_content,
        }
        return cls(
            snapshot_id=snapshot_id,
            captured_at=captured_at,
            system_order_id=snapshot.system_order_id,
            platform_order_numbers=platform_orders,
            products=tuple(source_products),
            _snapshot_json=_canonical_json(stored),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SourceSnapshot:
        copied = _deep_copy_json(dict(value))
        products = tuple(
            SourceProduct(
                source_product_id=str(item["sourceProductId"]),
                standard_name=str(item.get("standardName", "")),
                short_name=str(item.get("shortName", "")),
                quantity=int(item.get("quantity", 0)),
                merchant_code=str(item.get("merchantCode", "")),
                main_merchant_code=item.get("mainMerchantCode"),
                platform_product_id=str(item.get("platformProductId", "")),
                platform_sku_id=str(item.get("platformSkuId", "")),
                platform_spec=str(item.get("platformSpec", "")),
                platform_name=str(item.get("platformName", "")),
                platform_order_number=str(item.get("platformOrderNumber", "")),
                source_group=str(item.get("sourceGroup", "")),
                _details_json=_canonical_json(
                    {
                        key: item_value
                        for key, item_value in item.items()
                        if key not in {"sourceProductId", "sourceGroup"}
                    }
                ),
            )
            for item in copied.get("products", [])
        )
        return cls(
            snapshot_id=str(copied["snapshotId"]),
            captured_at=str(copied.get("capturedAt", "")),
            system_order_id=str(copied.get("systemOrderId", "")),
            platform_order_numbers=tuple(copied.get("platformOrderNumbers", [])),
            products=products,
            _snapshot_json=_canonical_json(copied),
        )

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._snapshot_json)

    @property
    def product_by_id(self) -> Mapping[str, SourceProduct]:
        return MappingProxyType({item.source_product_id: item for item in self.products})

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.products)


@dataclass(frozen=True)
class PackageItem:
    source_product_id: str
    product_name: str
    quantity: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceProductId": self.source_product_id,
            "productName": self.product_name,
            "quantity": self.quantity,
        }


@dataclass(frozen=True)
class Package:
    package_id: str
    items: tuple[PackageItem, ...] = ()

    @property
    def total_quantity(self) -> int:
        return sum(item.quantity for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packageId": self.package_id,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class PackagePlan:
    packages: tuple[Package, ...]

    @property
    def total_quantity(self) -> int:
        return sum(package.total_quantity for package in self.packages)

    def to_dict(self) -> dict[str, Any]:
        return {"packages": [package.to_dict() for package in self.packages]}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PackagePlan:
        return cls(
            packages=tuple(
                Package(
                    package_id=str(package["packageId"]),
                    items=tuple(
                        PackageItem(
                            source_product_id=str(item["sourceProductId"]),
                            product_name=str(item.get("productName", "")),
                            quantity=int(item["quantity"]),
                        )
                        for item in package.get("items", [])
                    ),
                )
                for package in value.get("packages", [])
            )
        )


@dataclass(frozen=True)
class PackageDraft:
    snapshot_id: str
    packages: tuple[Package, ...]

    @classmethod
    def single_package(cls, source: SourceSnapshot) -> PackageDraft:
        return cls(
            snapshot_id=source.snapshot_id,
            packages=(
                Package(
                    package_id="package-1",
                    items=tuple(
                        PackageItem(
                            source_product_id=product.source_product_id,
                            product_name=product.display_name,
                            quantity=product.quantity,
                        )
                        for product in source.products
                        if product.quantity > 0
                    ),
                ),
            ),
        )

    @classmethod
    def split(
        cls, source: SourceSnapshot, *, package_count: int = 2
    ) -> PackageDraft:
        if package_count < 1:
            raise PackagePlanValidationError("至少需要一个包裹")
        return cls(
            snapshot_id=source.snapshot_id,
            packages=tuple(
                Package(package_id=f"package-{index + 1}")
                for index in range(package_count)
            ),
        )

    def _replace_package(self, replacement: Package) -> PackageDraft:
        return PackageDraft(
            snapshot_id=self.snapshot_id,
            packages=tuple(
                replacement if package.package_id == replacement.package_id else package
                for package in self.packages
            ),
        )

    def add_package(self) -> PackageDraft:
        used = {
            int(package.package_id.removeprefix("package-"))
            for package in self.packages
            if package.package_id.removeprefix("package-").isdigit()
        }
        next_number = 1
        while next_number in used:
            next_number += 1
        return PackageDraft(
            snapshot_id=self.snapshot_id,
            packages=(*self.packages, Package(f"package-{next_number}")),
        )

    def remove_package(self, package_id: str) -> PackageDraft:
        package = self._find_package(package_id)
        if package.items:
            raise PackagePlanValidationError("只能删除空包裹")
        remaining = tuple(item for item in self.packages if item.package_id != package_id)
        if not remaining:
            raise PackagePlanValidationError("至少需要保留一个包裹")
        return PackageDraft(snapshot_id=self.snapshot_id, packages=remaining)

    def set_quantity(
        self,
        package_id: str,
        source_product_id: str,
        quantity: int,
        *,
        source: SourceSnapshot,
    ) -> PackageDraft:
        if quantity < 0:
            raise PackagePlanValidationError("商品数量不能小于 0")
        package = self._find_package(package_id)
        self._ensure_snapshot(source)
        product = source.product_by_id.get(source_product_id)
        if product is None:
            raise PackagePlanValidationError("包裹商品不属于当前原订单")
        other_quantity = sum(
            item.quantity
            for current in self.packages
            if current.package_id != package_id
            for item in current.items
            if item.source_product_id == source_product_id
        )
        if other_quantity + quantity > product.quantity:
            raise PackagePlanValidationError("分配数量不能超过原订单数量")

        items = tuple(
            item for item in package.items if item.source_product_id != source_product_id
        )
        if quantity > 0:
            items = (
                *items,
                PackageItem(source_product_id, product.display_name, quantity),
            )
        return self._replace_package(Package(package_id, items))

    def allocated_quantity(self, source_product_id: str) -> int:
        return sum(
            item.quantity
            for package in self.packages
            for item in package.items
            if item.source_product_id == source_product_id
        )

    def remaining_quantity(self, source_product: SourceProduct) -> int:
        return source_product.quantity - self.allocated_quantity(
            source_product.source_product_id
        )

    def confirm(self, source: SourceSnapshot) -> PackagePlan:
        self._ensure_snapshot(source)
        if not self.packages:
            raise PackagePlanValidationError("至少需要一个包裹")
        if any(not package.items for package in self.packages):
            raise PackagePlanValidationError("不允许空包裹")
        if any(
            item.quantity <= 0
            for package in self.packages
            for item in package.items
        ):
            raise PackagePlanValidationError("包裹商品数量必须大于 0")
        if any(
            len({item.source_product_id for item in package.items})
            != len(package.items)
            for package in self.packages
        ):
            raise PackagePlanValidationError("同一包裹不能重复记录同一原商品")

        source_ids = source.product_by_id
        unknown = {
            item.source_product_id
            for package in self.packages
            for item in package.items
            if item.source_product_id not in source_ids
        }
        if unknown:
            raise PackagePlanValidationError("包裹中存在不属于当前原订单的商品")

        missing = 0
        for product in source.products:
            allocated = self.allocated_quantity(product.source_product_id)
            if allocated > product.quantity:
                raise PackagePlanValidationError("分配数量不能超过原订单数量")
            missing += product.quantity - allocated
        if missing:
            raise PackagePlanValidationError(f"尚有 {missing} 件商品未分配")
        return PackagePlan(packages=self.packages)

    def _find_package(self, package_id: str) -> Package:
        for package in self.packages:
            if package.package_id == package_id:
                return package
        raise PackagePlanValidationError("包裹不存在")

    def _ensure_snapshot(self, source: SourceSnapshot) -> None:
        if self.snapshot_id != source.snapshot_id:
            raise DraftSnapshotMismatchError("原订单已刷新，当前包裹草稿已失效")
