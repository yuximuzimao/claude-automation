from __future__ import annotations

from dataclasses import dataclass

from .models import Product


@dataclass(frozen=True)
class Judgment:
    message: str


def judge(
    *,
    is_expanded: bool,
    products: list[Product],
    has_suite_action: bool = False,
) -> Judgment:
    if not is_expanded:
        return Judgment("判断：请先展开订单")
    if has_suite_action or any(product.title.startswith("【套件】") for product in products):
        return Judgment("判断：请先套件转单品")
    if not products:
        return Judgment("判断：待人工确认")
    return Judgment("判断：可进入人工判断")
