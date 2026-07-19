from __future__ import annotations

import re

from .models import Product


PLATFORM_ID_RE = re.compile(r"平台ID（skuId）：\s*(\S+)\s*（([^）]+)）")


def split_product_title(title: str) -> tuple[str, str]:
    text = _clean(title)
    match = re.search(r"（([^（）]+)）\s*$", text)
    if not match:
        return text, ""
    standard_name = text[: match.start()].strip()
    short_name = match.group(1).strip()
    return standard_name, short_name


def parse_platform_ids(line: str) -> tuple[str, str]:
    match = PLATFORM_ID_RE.search(_clean(line))
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2).strip()


def parse_order_product(lines: list[str], dataset: dict[str, str] | None = None) -> Product:
    dataset = dataset or {}
    cleaned = [_clean(line) for line in lines if _clean(line)]
    title = _find_title(cleaned)
    standard_name, short_name = split_product_title(title)
    spu_id, sku_id = _find_platform_ids(cleaned)
    if not spu_id:
        spu_id = dataset.get("numiid", "")
    merchant_code = _find_value(cleaned, "商家编码：")
    main_code = _find_value(cleaned, "主商家编码：")
    if main_code == merchant_code:
        main_code = None
    return Product(
        title=title,
        standard_name=standard_name,
        short_name=short_name,
        quantity=_find_quantity(cleaned),
        merchant_code=merchant_code,
        main_merchant_code=main_code or None,
        spu_id=spu_id,
        sku_id=sku_id,
    )


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
