from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import TypeAlias

from .package_plan import SourceProduct, SourceSnapshot


ProductKey: TypeAlias = tuple[str, ...]
ProductQuantity: TypeAlias = tuple[ProductKey, int]
ProductGroupSignature: TypeAlias = tuple[ProductQuantity, ...]
SameOrderSignature: TypeAlias = tuple[tuple[str, ProductGroupSignature], ...]
OrderStructureSignature: TypeAlias = tuple[ProductGroupSignature, ...]
TotalProductSignature: TypeAlias = ProductGroupSignature


def product_key(product: SourceProduct) -> ProductKey:
    """返回不依赖页面行位置的结构化商品身份。"""
    return product.match_key


def same_order_signature(source: SourceSnapshot) -> SameOrderSignature | None:
    """平台子订单号及其商品明细；缺少可靠单号时不猜测同一订单。"""
    fallback_order = _single_snapshot_order(source)
    grouped: defaultdict[str, defaultdict[ProductKey, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for product in source.products:
        order_number = product.platform_order_number.strip() or fallback_order
        if not order_number:
            return None
        grouped[order_number][product_key(product)] += product.quantity
    return tuple(
        sorted(
            (order_number, _product_totals_signature(totals))
            for order_number, totals in grouped.items()
        )
    )


def order_structure_signature(source: SourceSnapshot) -> OrderStructureSignature:
    """忽略平台单号具体值，但保留各平台子订单的商品构成多重集合。"""
    fallback_order = _single_snapshot_order(source)
    grouped: defaultdict[str, defaultdict[ProductKey, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for product in source.products:
        group_key = (
            product.platform_order_number.strip()
            or fallback_order
            or product.source_group.strip()
            or "__ungrouped__"
        )
        grouped[group_key][product_key(product)] += product.quantity
    return tuple(sorted(_product_totals_signature(totals) for totals in grouped.values()))


def total_product_signature(source: SourceSnapshot) -> TotalProductSignature:
    """忽略平台子订单结构，汇总整个待处理订单的商品身份和数量。"""
    totals: defaultdict[ProductKey, int] = defaultdict(int)
    for product in source.products:
        totals[product_key(product)] += product.quantity
    return _product_totals_signature(totals)


def signature_key(value: object) -> str:
    """生成可持久化、可稳定比较的规范 JSON。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def signature_digest(value: object, *, length: int = 20) -> str:
    return hashlib.sha256(signature_key(value).encode("utf-8")).hexdigest()[:length]


def same_order_signature_key(source: SourceSnapshot) -> str | None:
    signature = same_order_signature(source)
    return signature_key(signature) if signature is not None else None


def order_structure_signature_key(source: SourceSnapshot) -> str:
    return signature_key(order_structure_signature(source))


def total_product_signature_key(source: SourceSnapshot) -> str:
    return signature_key(total_product_signature(source))


def _single_snapshot_order(source: SourceSnapshot) -> str:
    values = tuple(dict.fromkeys(item.strip() for item in source.platform_order_numbers if item.strip()))
    return values[0] if len(values) == 1 else ""


def _product_totals_signature(
    totals: dict[ProductKey, int] | defaultdict[ProductKey, int],
) -> ProductGroupSignature:
    return tuple(sorted((key, quantity) for key, quantity in totals.items()))
