from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


PACKAGE_EQUIVALENCE_VERSION = 1
PACKAGE_EQUIVALENCE_KEY_PREFIX = (
    f"package-equivalence-v{PACKAGE_EQUIVALENCE_VERSION}"
)

# 这里只登记用户明确确认过、包装大小完全相同的商品。
# 分组之间绝不互换；正装、体验装/试用装始终是不同分组。
PACKAGE_EQUIVALENCE_GROUPS: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "coffee_regular": MappingProxyType(
            {
                "6977987940138": "美式咖啡（绿）",
                "6979151090014": "生椰拿铁（新包装）",
            }
        ),
        "coffee_trial": MappingProxyType(
            {
                "6979499760068": "美式咖啡（绿）体验装",
                "6978430740022": "生椰拿铁体验装",
            }
        ),
        "black_tea_regular": MappingProxyType(
            {
                "6979499760044": "KGOS黑茶 茉莉味",
                "6979265440002": "KGOS黑茶 普洱味",
            }
        ),
        "black_tea_trial": MappingProxyType(
            {
                "6979499760099": "KGOS黑茶 茉莉味 体验装",
                "6979265440019": "KGOS黑茶 普洱味 体验装",
            }
        ),
        "protein_regular": MappingProxyType(
            {
                "6977987940046": "蛋白粉（牛油果猕猴桃味）正装",
                "6977987940039": "蛋白粉（莓果味）正装",
            }
        ),
        "protein_trial": MappingProxyType(
            {
                "6977987940107": "蛋白粉（牛油果猕猴桃味）三袋体验装",
                "6977987940084": "蛋白粉（莓果味）三袋体验装",
            }
        ),
    }
)

_GROUP_BY_MERCHANT_CODE = MappingProxyType(
    {
        merchant_code: group
        for group, products in PACKAGE_EQUIVALENCE_GROUPS.items()
        for merchant_code in products
    }
)


def package_equivalence_group(
    merchant_code: str,
    main_merchant_code: str | None = None,
) -> str | None:
    """按明确白名单返回等体积包装分组；编码缺失或未知时不猜测。"""
    code = merchant_code.strip() or (main_merchant_code or "").strip()
    return _GROUP_BY_MERCHANT_CODE.get(code)
