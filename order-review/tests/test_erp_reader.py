import pytest

from order_review.erp_reader import (
    SequenceOneIdentityProbe,
    build_expand_order_sequence_js,
    build_expand_sequence_one_js,
    build_order_sequence_view_probe_js,
    build_read_order_sequence_js,
    build_read_sequence_one_js,
    build_sequence_one_identity_probe_js,
    find_erp_toaudit_target,
    read_order_at_sequence,
    read_sequence_one_identity,
    read_sequence_one_order,
    resolve_system_order_id,
    scroll_order_sequence_into_view,
    snapshot_from_payload,
)
from order_review.window_position import ChromeActiveTab


def test_find_erp_target_accepts_active_toaudit_tab_only():
    url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    target_id = find_erp_toaudit_target(
        [{"targetId": "abc", "title": "快麦ERP--待审核订单", "url": url}],
        active_tab=ChromeActiveTab(title="快麦ERP--待审核订单", url=url),
    )

    assert target_id == "abc"


def test_find_erp_target_rejects_order_manage_tab():
    url = "https://erpb.superboss.cc/index.html#/tradeNew/manage/"
    target_id = find_erp_toaudit_target(
        [{"targetId": "abc", "title": "快麦ERP--订单管理", "url": url}],
        active_tab=ChromeActiveTab(title="快麦ERP--订单管理", url=url),
    )

    assert target_id == ""


def test_find_erp_target_does_not_read_background_toaudit_tab():
    toaudit_url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    manage_url = "https://erpb.superboss.cc/index.html#/tradeNew/manage/"
    target_id = find_erp_toaudit_target(
        [
            {"targetId": "toaudit", "title": "快麦ERP--待审核订单", "url": toaudit_url},
            {"targetId": "manage", "title": "快麦ERP--订单管理", "url": manage_url},
        ],
        active_tab=ChromeActiveTab(title="快麦ERP--订单管理", url=manage_url),
    )

    assert target_id == ""


def test_find_erp_target_requires_unique_matching_cdp_page():
    url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    target_id = find_erp_toaudit_target(
        [
            {"targetId": "first", "type": "page", "url": url},
            {"targetId": "second", "type": "page", "url": url},
        ],
        active_tab=ChromeActiveTab(title="快麦ERP--待审核订单", url=url),
    )

    assert target_id == ""


def test_find_erp_target_falls_back_to_accessibility_front_window_title(
    monkeypatch,
):
    url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_active_tab",
        lambda: None,
    )
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_front_window_title",
        lambda: "快麦ERP--待审核订单 - Google Chrome",
    )

    target_id = find_erp_toaudit_target(
        [{"id": "abc", "type": "page", "title": "快麦ERP--待审核订单", "url": url}]
    )

    assert target_id == "abc"


def test_accessibility_fallback_still_requires_unique_front_toaudit_page(
    monkeypatch,
):
    url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_active_tab",
        lambda: None,
    )
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_front_window_title",
        lambda: "快麦ERP--待审核订单 - Google Chrome",
    )

    target_id = find_erp_toaudit_target(
        [
            {"id": "first", "type": "page", "title": "快麦ERP--待审核订单", "url": url},
            {"id": "second", "type": "page", "title": "快麦ERP--待审核订单", "url": url},
        ]
    )

    assert target_id == ""


def test_accessibility_fallback_rejects_background_toaudit_page(monkeypatch):
    url = "https://erpb.superboss.cc/index.html#/trade/toaudit/"
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_active_tab",
        lambda: None,
    )
    monkeypatch.setattr(
        "order_review.erp_reader.get_chrome_front_window_title",
        lambda: "订单管理 - Google Chrome",
    )

    target_id = find_erp_toaudit_target(
        [{"id": "abc", "type": "page", "title": "快麦ERP--待审核订单", "url": url}]
    )

    assert target_id == ""


def test_reader_js_targets_sequence_one_and_requires_expanded_row():
    js = build_read_sequence_one_js()

    assert "#/trade/toaudit/" in js
    assert "NOT_TOAUDIT_PAGE" in js
    assert ".module-trade-list-item" in js
    assert "seq(row)==='1'" in js
    assert "module-trade-list-item-open" in js
    assert ".item-snapshot-itemname" in js
    assert "closest('tr.order-temp')" in js
    assert "tr.order-temp" in js
    assert "trade-icon-canmerged" in js
    assert "extractOrderNumbers" in js
    assert "rowDataset" in js
    assert "rowAttributes" in js
    assert "sourceGroupIndex" in js
    assert "scopeDataset" in js
    assert "visibleSystemOrderId" in js


def test_expand_js_only_clicks_sequence_one_left_expand_control():
    js = build_expand_sequence_one_js()

    assert "seq(row)==='1'" in js
    assert '.trade-plus .trade-expand [data-name="trigger_show_orders"]' in js
    assert "trigger.click()" in js
    assert "module-trade-list-item-open" in js
    assert "tr.order-temp, .item-snapshot-itemname" in js


def test_generic_reader_and_expand_scripts_target_requested_sequence():
    read_js = build_read_order_sequence_js(3)
    expand_js = build_expand_order_sequence_js(3)

    assert "seq(row)==='3'" in read_js
    assert "seq(row)==='1'" not in read_js
    assert "SEQ_3_NOT_FOUND" in read_js
    assert "seq(row)==='3'" in expand_js
    assert "seq(row)==='1'" not in expand_js
    assert "trigger.click()" in expand_js


def test_sequence_view_probe_is_read_only_and_scroll_uses_physical_wheel():
    js = build_order_sequence_view_probe_js(3, "ORDER-3")
    probes = iter(
        [
            {
                "ok": True,
                "found": False,
                "mountedSequences": [1, 2],
                "wheelX": 500,
                "wheelY": 400,
            },
            {
                "ok": True,
                "found": True,
                "inViewport": True,
                "systemOrderId": "ORDER-3",
                "mountedSequences": [2, 3, 4],
                "wheelX": 500,
                "wheelY": 400,
            },
        ]
    )
    wheels = []

    result = scroll_order_sequence_into_view(
        3,
        "target-1",
        expected_system_order_id="ORDER-3",
        evaluator=lambda _target_id, _js: next(probes),
        wheel_dispatcher=lambda *args: wheels.append(args),
        sleeper=lambda _seconds: None,
    )

    assert "mountedSequences" in js
    assert "expectedSystemOrderId" in js
    assert ".click(" not in js
    assert result["systemOrderId"] == "ORDER-3"
    assert wheels == [("target-1", 500.0, 400.0, 520.0)]


def test_sequence_view_probe_allows_identity_discovery_but_still_requires_identity():
    js = build_order_sequence_view_probe_js(3, "")

    assert "if (!systemOrderId)" in js
    assert "expectedSystemOrderId && systemOrderId !== expectedSystemOrderId" in js
    assert "if (!expectedSystemOrderId ||" not in js


def test_generic_reader_stops_if_row_identity_changes_after_expand():
    payloads = iter(
        [
            {
                "ok": True,
                "isExpanded": False,
                "rowAttributes": {"uniqueid": "ORDER-2", "sid": "ORDER-2"},
                "visibleSystemOrderId": "ORDER-2",
                "products": [],
            },
            {"ok": True, "expanded": True, "clicked": True},
            {
                "ok": True,
                "isExpanded": True,
                "rowAttributes": {"uniqueid": "CHANGED", "sid": "CHANGED"},
                "visibleSystemOrderId": "CHANGED",
                "products": [],
            },
        ]
    )

    with pytest.raises(RuntimeError, match="展开第 2 行订单后目标发生变化"):
        read_order_at_sequence(
            2,
            "target-1",
            expected_system_order_id="ORDER-2",
            evaluator=lambda _target_id, _js: next(payloads),
        )


def test_generic_reader_waits_after_expand_before_reading_details():
    events = []
    payloads = iter(
        [
            {
                "ok": True,
                "isExpanded": False,
                "rowAttributes": {"uniqueid": "ORDER-2", "sid": "ORDER-2"},
                "visibleSystemOrderId": "ORDER-2",
                "products": [],
            },
            {"ok": True, "expanded": True, "clicked": True},
            {
                "ok": True,
                "isExpanded": True,
                "rowAttributes": {"uniqueid": "ORDER-2", "sid": "ORDER-2"},
                "visibleSystemOrderId": "ORDER-2",
                "products": [],
            },
        ]
    )

    def evaluator(_target_id, _js):
        events.append("read")
        return next(payloads)

    snapshot = read_order_at_sequence(
        2,
        "target-1",
        expected_system_order_id="ORDER-2",
        evaluator=evaluator,
        post_expand_wait_seconds=0.3,
        sleeper=lambda seconds: events.append(("sleep", seconds)),
    )

    assert snapshot.system_order_id == "ORDER-2"
    assert events == ["read", "read", ("sleep", 0.3), "read"]


def test_identity_probe_is_read_only_and_blocks_unsafe_page_states():
    js = build_sequence_one_identity_probe_js()

    assert "seq(row) === '1'" in js
    assert "visibleDialogCount" in js
    assert "selectedRowCount" in js
    assert ".click(" not in js
    assert SequenceOneIdentityProbe("ORDER-1", 0, 0, 0).safe_to_auto_refresh
    assert not SequenceOneIdentityProbe("ORDER-1", 1, 0, 0).safe_to_auto_refresh
    assert not SequenceOneIdentityProbe("ORDER-1", 0, 1, 0).safe_to_auto_refresh
    assert not SequenceOneIdentityProbe("ORDER-1", 0, 0, 1).safe_to_auto_refresh


def test_identity_reader_requires_consistent_system_order_id(monkeypatch):
    monkeypatch.setattr(
        "order_review.erp_reader.cdp.eval_js",
        lambda _target_id, _js: {
            "ok": True,
            "rowAttributes": {"uniqueid": "ORDER-1", "sid": "ORDER-1"},
            "visibleSystemOrderId": "ORDER-1",
            "loadingCount": 0,
            "visibleDialogCount": 0,
            "selectedRowCount": 0,
        },
    )

    probe = read_sequence_one_identity("target-1")

    assert probe.system_order_id == "ORDER-1"
    assert probe.safe_to_auto_refresh


def test_reader_expands_unexpanded_order_then_reads_details(monkeypatch):
    payloads = iter(
        [
            {"ok": True, "isExpanded": False, "products": []},
            {"ok": True, "expanded": True, "clicked": True},
            {"ok": True, "isExpanded": True, "products": []},
        ]
    )
    calls = []

    def fake_eval_js(target_id, js):
        calls.append((target_id, js))
        return next(payloads)

    monkeypatch.setattr("order_review.erp_reader.cdp.eval_js", fake_eval_js)

    snapshot = read_sequence_one_order("target-1")

    assert snapshot.is_expanded is True
    assert len(calls) == 3
    assert calls[1] == ("target-1", build_expand_sequence_one_js())


def test_auto_reader_stops_before_expand_if_order_changed_again(monkeypatch):
    calls = []

    def fake_eval_js(target_id, js):
        calls.append((target_id, js))
        return {
            "ok": True,
            "isExpanded": False,
            "rowAttributes": {"uniqueid": "ORDER-2", "sid": "ORDER-2"},
            "visibleSystemOrderId": "ORDER-2",
            "products": [],
        }

    monkeypatch.setattr("order_review.erp_reader.cdp.eval_js", fake_eval_js)

    with pytest.raises(RuntimeError, match="展开前再次变化"):
        read_sequence_one_order(
            "target-1",
            expected_system_order_id="ORDER-1",
        )

    assert len(calls) == 1


def test_reader_keeps_manual_expand_message_when_expand_control_is_unavailable(
    monkeypatch,
):
    payloads = iter(
        [
            {"ok": True, "isExpanded": False, "products": []},
            {"ok": False, "error": "EXPAND_CONTROL_NOT_FOUND"},
        ]
    )
    monkeypatch.setattr(
        "order_review.erp_reader.cdp.eval_js",
        lambda _target_id, _js: next(payloads),
    )

    snapshot = read_sequence_one_order("target-1")

    assert snapshot.is_expanded is False


def test_passive_reader_never_clicks_expand(monkeypatch):
    calls = []
    payload = {
        "ok": True,
        "isExpanded": False,
        "rowAttributes": {"uniqueid": "ORDER-1", "sid": "ORDER-1"},
        "visibleSystemOrderId": "ORDER-1",
        "products": [],
    }

    def fake_eval_js(target_id, js):
        calls.append((target_id, js))
        return payload

    monkeypatch.setattr("order_review.erp_reader.cdp.eval_js", fake_eval_js)

    snapshot = read_sequence_one_order(
        "target-1",
        expected_system_order_id="ORDER-1",
        expand_if_needed=False,
    )

    assert snapshot.system_order_id == "ORDER-1"
    assert snapshot.is_expanded is False
    assert len(calls) == 1
    assert calls[0][1] == build_read_sequence_one_js()


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


def test_snapshot_preserves_order_groups_identifiers_and_raw_payload():
    payload = {
        "ok": True,
        "title": "快麦ERP--待审核订单",
        "url": "https://erpa.superboss.cc/index.html#/trade/toaudit/",
        "isExpanded": True,
        "orderNumbers": ["ORDER-10001"],
        "rowText": "订单号：ORDER-10001\n商品明细",
        "rowLines": ["订单号：ORDER-10001", "商品明细"],
        "rowDataset": {"tid": "TID-ORDER"},
        "rowAttributes": {"class": "module-trade-list-item"},
        "groups": [
            {
                "index": 0,
                "key": "756863430",
                "platformOrderNumber": "756863430",
                "orderNumbers": ["756863430"],
                "productIndexes": [0],
                "dataset": {"tid": "756863430", "sid": "SID-1"},
                "attributes": {"class": "order-temp"},
                "lines": ["平台单号：", "756863430"],
                "rawText": "平台单号：\n756863430",
            }
        ],
        "products": [
            {
                "sourceGroupIndex": 0,
                "sourceGroupKey": "756863430",
                "platformOrderNumber": "756863430",
                "dataset": {
                    "tid": "756863430",
                    "sid": "SID-1",
                    "oid": "OID-1",
                    "numiid": "PLATFORM-ITEM-1",
                },
                "attributes": {"data-oid": "OID-1"},
                "lines": [
                    "商品A（简称A）",
                    "平台ID（skuId）： PLATFORM-ITEM-1 （PLATFORM-SKU-1）",
                    "商家编码：MERCHANT-1",
                    "1/",
                    "1",
                ],
                "rawText": "商品A（简称A）\n平台ID（skuId）： PLATFORM-ITEM-1 （PLATFORM-SKU-1）",
            }
        ],
    }

    snapshot = snapshot_from_payload(payload)
    product = snapshot.products[0]

    assert snapshot.order_numbers == ("ORDER-10001",)
    assert snapshot.source_title == "快麦ERP--待审核订单"
    assert snapshot.raw_dataset == {"tid": "TID-ORDER"}
    assert snapshot.raw_payload["groups"][0]["key"] == "756863430"
    assert snapshot.groups[0].order_numbers == ("756863430",)
    assert snapshot.groups[0].product_indexes == (0,)
    assert product.source_group_index == 0
    assert product.source_group_key == "756863430"
    assert product.platform_order_number == "756863430"
    assert product.sid == "SID-1"
    assert product.oid == "OID-1"
    assert product.spu_id == "PLATFORM-ITEM-1"
    assert product.sku_id == "PLATFORM-SKU-1"
    assert product.raw_dataset["numiid"] == "PLATFORM-ITEM-1"
    assert "平台ID" in product.raw_text


def test_system_order_id_requires_uniqueid_sid_and_visible_text_to_agree():
    payload = {
        "rowAttributes": {
            "uniqueid": "5945697152129529",
            "sid": "5945697152129529",
        },
        "visibleSystemOrderId": "5945697152129529",
    }

    assert resolve_system_order_id(payload) == "5945697152129529"
    assert snapshot_from_payload(
        {"ok": True, "isExpanded": False, **payload}
    ).system_order_id == "5945697152129529"

    payload["visibleSystemOrderId"] = "DIFFERENT"
    assert resolve_system_order_id(payload) == ""
