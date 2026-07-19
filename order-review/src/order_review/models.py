from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Product:
    title: str
    standard_name: str
    short_name: str
    quantity: int
    merchant_code: str = ""
    main_merchant_code: str | None = None
    spu_id: str = ""
    sku_id: str = ""


@dataclass(frozen=True)
class OrderSnapshot:
    is_expanded: bool
    products: list[Product] = field(default_factory=list)
    has_can_merge_mark: bool = False
    has_suite_action: bool = False

    @property
    def kind_count(self) -> int:
        return len(self.products)

    @property
    def total_quantity(self) -> int:
        return sum(product.quantity for product in self.products)
