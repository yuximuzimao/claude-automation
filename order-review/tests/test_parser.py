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


def test_parse_product_title_supports_nested_parentheses_in_short_name():
    cases = [
        (
            "甘油二酯咖啡固体饮料（生椰拿铁味） 8g*12 新包装（拿铁（新））",
            "甘油二酯咖啡固体饮料（生椰拿铁味） 8g*12 新包装",
            "拿铁（新）",
        ),
        (
            "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12（美式咖啡（绿））",
            "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12",
            "美式咖啡（绿）",
        ),
        (
            "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*3 体验装（美式咖啡（绿）体验装）",
            "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*3 体验装",
            "美式咖啡（绿）体验装",
        ),
    ]

    for title, expected_name, expected_short in cases:
        assert split_product_title(title) == (expected_name, expected_short)


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


def test_parse_order_product_keeps_item_details_separate_from_order_scope():
    product = parse_order_product(
        [
            "正确商品名称（正确简称）",
            "平台规格：正确规格",
            "平台ID（skuId）： ITEM-1 （SKU-1）",
            "平台名称：正确平台名称",
            "商家编码：MERCHANT-1",
            "2/",
            "2",
        ],
        {"tid": "756863430", "oid": "ERP-INTERNAL-OID"},
        order_lines=[
            "平台单号：",
            "756863430",
            "其他商品名称（错误简称）",
            "平台ID（skuId）： WRONG-ITEM （WRONG-SKU）",
            "商家编码：WRONG-MERCHANT",
            "99/",
            "99",
        ],
    )

    assert product.title == "正确商品名称（正确简称）"
    assert product.short_name == "正确简称"
    assert product.quantity == 2
    assert product.platform_order_number == "756863430"
    assert product.spu_id == "ITEM-1"
    assert product.sku_id == "SKU-1"
    assert product.platform_spec == "正确规格"
    assert product.platform_name == "正确平台名称"
    assert product.merchant_code == "MERCHANT-1"
    assert product.oid == "ERP-INTERNAL-OID"
    assert "其他商品名称（错误简称）" in product.detail_lines


def test_parse_order_product_uses_dataset_sku_alias_when_text_is_missing():
    product = parse_order_product(
        ["商品A（简称A）", "1/", "1"],
        {"numiid": "ITEM-1", "skuId": "SKU-1"},
    )

    assert product.spu_id == "ITEM-1"
    assert product.sku_id == "SKU-1"


def test_parse_order_product_ignores_undefined_dataset_spu():
    product = parse_order_product(
        ["商品A（简称A）", "1/", "1"],
        {"numiid": "undefined"},
    )

    assert product.spu_id == ""


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
