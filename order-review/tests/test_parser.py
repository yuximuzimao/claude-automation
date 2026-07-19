from order_review.parser import (
    parse_order_product,
    parse_platform_ids,
    split_product_title,
)


SAMPLE_PRODUCT_LINES = [
    "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）",
    "平台规格： 茉莉花味黑茶 买6送1，到手7盒;KGOS",
    "平台ID（skuId）： kgoshcml-cx （130292082）",
    "平台名称： 茉莉花味 灵芝金花黑茶固体饮料21g（1gx21）",
    "主商家编码： 6979499760044",
    "商家编码：6979499760044",
    "商品总重量：0 kg 单品体积：0.0 cm³",
    "单价：0.000 折后单价：92.694 折扣率：0.000 成本单价：0.000",
    "7/",
    "7",
    "成交金额：648.860",
]


def test_parse_product_title_splits_last_parentheses():
    name, short = split_product_title("KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）")

    assert name == "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21"
    assert short == "KGOS黑茶 茉莉味"


def test_parse_platform_ids_distinguishes_spu_and_sku():
    assert parse_platform_ids("平台ID（skuId）： kgoshcml-cx （130292082）") == (
        "kgoshcml-cx",
        "130292082",
    )


def test_parse_order_product_ignores_invalid_fields_and_keeps_quantity():
    product = parse_order_product(SAMPLE_PRODUCT_LINES, {"numiid": "kgoshcml-cx"})

    assert product.title == "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）"
    assert product.standard_name == "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21"
    assert product.short_name == "KGOS黑茶 茉莉味"
    assert product.quantity == 7
    assert product.spu_id == "kgoshcml-cx"
    assert product.sku_id == "130292082"
    assert product.merchant_code == "6979499760044"
    assert product.main_merchant_code is None


def test_parse_order_product_keeps_distinct_main_code_when_different():
    lines = [
        "商品A（简称A）",
        "平台ID（skuId）： spu-1 （sku-1）",
        "主商家编码： MAIN-001",
        "商家编码：MERCHANT-002",
        "3/",
        "3",
    ]

    product = parse_order_product(lines, {"numiid": "spu-1"})

    assert product.merchant_code == "MERCHANT-002"
    assert product.main_merchant_code == "MAIN-001"
    assert product.quantity == 3
