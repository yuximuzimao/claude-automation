from __future__ import annotations

import re

from .models import Product


PLATFORM_ID_RE = re.compile(
    r"平台ID\s*[（(]\s*sku\s*id\s*[）)]\s*[：:]\s*([^\s（(]+)\s*[（(]\s*([^）)]+)\s*[）)]",
    re.IGNORECASE,
)
PLATFORM_ORDER_RE = re.compile(r"平台单号\s*[：:]\s*([A-Za-z0-9_-]+)")


def split_product_title(title: str) -> tuple[str, str]:
    text = _clean(title)
    if not text:
        return "", ""

    closing = text[-1]
    opening = {"）": "（", ")": "("}.get(closing)
    if opening is None:
        return text, ""

    depth = 0
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char == closing:
            depth += 1
        elif char == opening:
            depth -= 1
            if depth == 0:
                standard_name = text[:index].strip()
                short_name = text[index + 1 : -1].strip()
                if standard_name and short_name:
                    return standard_name, short_name
                break
    return text, ""


def parse_platform_ids(line: str) -> tuple[str, str]:
    match = PLATFORM_ID_RE.search(_clean(line))
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2).strip()


def parse_platform_order_number(lines: list[str]) -> str:
    cleaned = [_clean(line) for line in lines if _clean(line)]
    for index, line in enumerate(cleaned):
        match = PLATFORM_ORDER_RE.search(line)
        if match:
            return match.group(1).strip()
        if line.rstrip("：:") == "平台单号" and index + 1 < len(cleaned):
            value = cleaned[index + 1]
            if re.fullmatch(r"[A-Za-z0-9_-]+", value):
                return value
    return ""


def parse_order_product(
    lines: list[str],
    dataset: dict[str, str] | None = None,
    *,
    order_lines: list[str] | None = None,
    platform_order_number: str = "",
    attributes: dict[str, str] | None = None,
    raw_text: str = "",
    source_group_index: int | None = None,
    source_group_key: str = "",
) -> Product:
    dataset = {str(key): str(value) for key, value in (dataset or {}).items()}
    attributes = {str(key): str(value) for key, value in (attributes or {}).items()}
    item_lines = [_clean(line) for line in lines if _clean(line)]
    group_lines = [_clean(line) for line in (order_lines or []) if _clean(line)]

    title = _find_title(item_lines)
    standard_name, short_name = split_product_title(title)
    spu_id, sku_id = _find_platform_ids(item_lines)
    if not spu_id:
        spu_id = _safe_dataset_alias(
            dataset,
            "numiid",
            "numIid",
            "itemId",
            "platformProductId",
        )
    if not sku_id:
        sku_id = _safe_dataset_alias(
            dataset,
            "skuId",
            "skuid",
            "skuID",
            "platformSkuId",
        )

    merchant_code = _find_value(item_lines, "商家编码：")
    main_code = _find_value(item_lines, "主商家编码：")
    if main_code == merchant_code:
        main_code = None

    resolved_platform_order = (
        _clean(platform_order_number)
        or parse_platform_order_number(group_lines)
        or _safe_dataset_alias(dataset, "tid", "platformOrderNumber")
    )

    return Product(
        title=title,
        standard_name=standard_name,
        short_name=short_name,
        quantity=_find_quantity(item_lines),
        merchant_code=merchant_code,
        main_merchant_code=main_code or None,
        platform_spec=_find_value(item_lines, "平台规格："),
        platform_name=_find_value(item_lines, "平台名称："),
        spu_id=spu_id,
        sku_id=sku_id,
        platform_order_number=resolved_platform_order,
        sid=_safe_dataset_alias(dataset, "sid"),
        oid=_safe_dataset_alias(dataset, "oid", "orderId"),
        source_group_index=source_group_index,
        source_group_key=source_group_key,
        item_lines=tuple(item_lines),
        detail_lines=tuple(group_lines),
        raw_lines=tuple(dict.fromkeys([*item_lines, *group_lines])),
        raw_dataset=dataset,
        raw_attributes=attributes,
        raw_text=str(raw_text),
    )


def _safe_dataset_alias(dataset: dict[str, str], *keys: str) -> str:
    lowered = {str(key).lower(): str(value) for key, value in dataset.items()}
    for key in keys:
        value = lowered.get(key.lower(), "").strip()
        if value and value.lower() not in {"undefined", "null", "none"}:
            return value
    return ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _find_title(lines: list[str]) -> str:
    for line in lines:
        if _is_ignored_line(line):
            continue
        if "（" in line and "）" in line:
            return line
    return lines[0] if lines else ""


def _is_ignored_line(line: str) -> bool:
    prefixes = (
        "平台规格：",
        "平台ID",
        "平台名称：",
        "主商家编码：",
        "商家编码：",
        "商品总重量：",
        "单价：",
        "成交金额：",
        "平台实付：",
        "成本：",
        "分销：",
    )
    return line.startswith(prefixes)


def _find_platform_ids(lines: list[str]) -> tuple[str, str]:
    for line in lines:
        parsed = parse_platform_ids(line)
        if parsed != ("", ""):
            return parsed
    return "", ""


def _find_value(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _find_quantity(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if re.fullmatch(r"\d+/", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if re.fullmatch(r"\d+", next_line):
                return int(next_line)
        match = re.fullmatch(r"(\d+)/\s*(\d+)", line)
        if match:
            return int(match.group(2))
    return 0
