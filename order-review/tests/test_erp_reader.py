from order_review.erp_reader import (
    build_read_sequence_one_js,
    find_erp_toaudit_target,
    snapshot_from_payload,
)


def test_find_erp_target_accepts_new_order_manage_route():
    target_id = find_erp_toaudit_target(
        [
            {
                "targetId": "abc",
                "title": "快麦ERP--订单管理",
                "url": "https://erpb.superboss.cc/index.html#/tradeNew/manage/",
            }
        ]
    )

    assert target_id == "abc"


def test_reader_js_targets_sequence_one_and_requires_expanded_row():
    js = build_read_sequence_one_js()

    assert ".module-trade-list-item" in js
    assert "seq(row)==='1'" in js
    assert "module-trade-list-item-open" in js
    assert "tr.order-temp" in js
    assert "trade-icon-canmerged" in js


def test_snapshot_from_unexpanded_payload_has_no_products():
    snapshot = snapshot_from_payload({"ok": True, "isExpanded": False, "products": []})

    assert snapshot.is_expanded is False
    assert snapshot.products == []


def test_snapshot_from_payload_parses_product_rows():
    payload = {
        "ok": True,
        "isExpanded": True,
        "hasCanMergeMark": True,
        "hasSuiteAction": False,
        "products": [
            {
                "dataset": {"numiid": "kgoshcml-cx"},
                "lines": [
                    "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）",
                    "平台ID（skuId）： kgoshcml-cx （130292082）",
                    "主商家编码： 6979499760044",
                    "商家编码：6979499760044",
                    "7/",
                    "7",
                ],
            }
        ],
    }

    snapshot = snapshot_from_payload(payload)

    assert snapshot.is_expanded is True
    assert snapshot.has_can_merge_mark is True
    assert snapshot.has_suite_action is False
    assert snapshot.products[0].short_name == "KGOS黑茶 茉莉味"
    assert snapshot.products[0].quantity == 7
