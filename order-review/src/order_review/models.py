from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Product:
    title: str
    standard_name: str
    short_name: str
    quantity: int
    merchant_code: str = ""
    main_merchant_code: str | None = None
    platform_spec: str = ""
    platform_name: str = ""
    spu_id: str = ""
    sku_id: str = ""
    platform_order_number: str = ""
    sid: str = ""
    oid: str = ""
    source_group_index: int | None = None
    source_group_key: str = ""
    item_lines: tuple[str, ...] = ()
    detail_lines: tuple[str, ...] = ()
    raw_lines: tuple[str, ...] = ()
    raw_dataset: dict[str, str] = field(default_factory=dict)
    raw_attributes: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""


@dataclass(frozen=True)
class OrderDetailGroup:
    index: int
    key: str
    order_numbers: tuple[str, ...] = ()
    product_indexes: tuple[int, ...] = ()
    dataset: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    raw_lines: tuple[str, ...] = ()
    raw_text: str = ""


@dataclass(frozen=True)
class OrderSnapshot:
    is_expanded: bool
    system_order_id: str = ""
    products: list[Product] = field(default_factory=list)
    groups: list[OrderDetailGroup] = field(default_factory=list)
    order_numbers: tuple[str, ...] = ()
    has_can_merge_mark: bool = False
    has_suite_action: bool = False
    source_title: str = ""
    source_url: str = ""
    raw_lines: tuple[str, ...] = ()
    raw_dataset: dict[str, str] = field(default_factory=dict)
    raw_attributes: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def kind_count(self) -> int:
        return len(self.products)

    @property
    def total_quantity(self) -> int:
        return sum(product.quantity for product in self.products)
