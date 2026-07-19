from order_review.models import Product
from order_review.rules import judge


def test_unexpanded_order_blocks_reading():
    assert judge(is_expanded=False, products=[]).message == "判断：请先展开订单"


def test_suite_detail_blocks_review():
    product = Product(
        title="【套件】咖啡",
        standard_name="咖啡",
        short_name="咖啡",
        quantity=1,
    )

    assert judge(is_expanded=True, products=[product], has_suite_action=True).message == "判断：请先套件转单品"


def test_normal_product_can_enter_manual_review():
    product = Product(
        title="KGOS灵芝金花黑茶固体饮料（KGOS黑茶 茉莉味）",
        standard_name="KGOS灵芝金花黑茶固体饮料",
        short_name="KGOS黑茶 茉莉味",
        quantity=7,
    )

    assert judge(is_expanded=True, products=[product]).message == "判断：可进入人工判断"


def test_no_product_after_expansion_needs_manual_confirmation():
    assert judge(is_expanded=True, products=[]).message == "判断：待人工确认"
