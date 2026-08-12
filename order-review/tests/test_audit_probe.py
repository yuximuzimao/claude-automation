import json

from order_review.audit_probe import (
    AuditExecutionLogStore,
    AuditExecutionState,
    build_audit_probe_js,
    run_audit_preflight,
)
from order_review.erp_reader import snapshot_from_payload
from order_review.package_plan import SourceSnapshot


SYSTEM_ORDER_ID = "5945697152129529"


def _order_payload():
    return {
        "ok": True,
        "isExpanded": True,
        "rowAttributes": {
            "uniqueid": SYSTEM_ORDER_ID,
            "sid": SYSTEM_ORDER_ID,
        },
        "visibleSystemOrderId": SYSTEM_ORDER_ID,
        "orderNumbers": ["PLATFORM-ORDER-1"],
        "products": [
            {
                "platformOrderNumber": "PLATFORM-ORDER-1",
                "sourceGroupIndex": 0,
                "sourceGroupKey": "PLATFORM-ORDER-1",
                "dataset": {"numiid": "ITEM-1"},
                "lines": [
                    "商品A（简称A）",
                    "平台ID（skuId）： ITEM-1 （SKU-1）",
                    "商家编码：CODE-A",
                    "1/",
                    "1",
                ],
            }
        ],
    }


def _probe_payload(*, target_row_count=1, with_samples=False):
    target_row = {
        "identity": {
            "resolved": SYSTEM_ORDER_ID,
            "consistent": True,
        },
        "checkboxCount": 1,
        "checkboxVisibleCount": 1,
        "checkboxEnabledCount": 1,
        "checkboxCheckedCount": 0,
        "pendingTextObserved": True,
    }
    return {
        "ok": True,
        "targetRows": [target_row] * target_row_count,
        "selectedRowCount": 0,
        "selectedSystemOrderIds": [],
        "footerSelectedCounts": [],
        "loadingCount": 0,
        "toolbarAuditVisibleCount": 1,
        "menu": {
            "ordinaryAuditCount": 1 if with_samples else 0,
            "forceAuditCount": 1 if with_samples else 0,
        },
        "dialogs": (
            [
                {
                    "listOption": {"found": True, "selected": True},
                    "queryOption": {"found": True, "selected": False},
                }
            ]
            if with_samples
            else []
        ),
        "messages": [],
    }


def _source():
    return SourceSnapshot.from_order_snapshot(snapshot_from_payload(_order_payload()))


def test_audit_probe_js_is_strictly_read_only():
    js = build_audit_probe_js(SYSTEM_ORDER_ID)

    assert SYSTEM_ORDER_ID in js
    assert "#/trade/toaudit/" in js
    assert "快麦ERP--待审核订单" in js
    assert ".module-trade-list-item" in js
    assert 'input.J_Checkbox[data-name="check_select_item"]' in js
    assert ".toolbar-sub_list" in js
    assert 'data-name="batch_audit"' in js
    assert ".click(" not in js
    assert ".dispatchEvent(" not in js
    assert "mouseover" not in js


def test_preflight_passes_without_mixing_in_execution_dialog_state(
    tmp_path,
):
    payloads = iter([_probe_payload(), _order_payload()])
    log_store = AuditExecutionLogStore(tmp_path / "audit.jsonl")
    report = run_audit_preflight(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=lambda _target_id, _js: next(payloads),
        confirmation_reference_id="case-reference-1",
        log_store=log_store,
    )

    assert report.state == AuditExecutionState.IDLE
    assert report.preflight_ready is True
    assert "审核前检查通过" in report.render_text()
    assert "未勾选订单" in report.render_text()

    logged = json.loads(log_store.path.read_text(encoding="utf-8"))
    assert logged["schemaVersion"] == 2
    assert logged["mode"] == "preflight"
    assert "phase2Ready" not in logged
    assert logged["targetSystemOrderId"] == SYSTEM_ORDER_ID
    assert logged["state"] == "idle"
    assert logged["sourceSnapshotId"] == _source().snapshot_id
    assert logged["confirmationReferenceId"] == "case-reference-1"
    assert logged["targetPackageCount"] == 1
    assert "rawProbe" not in logged
    assert [item["state"] for item in logged["stateHistory"]] == [
        "preflight_checking",
        "idle",
    ]


def test_preflight_stops_when_execution_dialog_is_already_open():
    payloads = iter([_probe_payload(with_samples=True), _order_payload()])

    report = run_audit_preflight(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=lambda _target_id, _js: next(payloads),
    )

    assert report.preflight_ready is False
    assert any(check.code == "NO_EXISTING_DIALOG" for check in report.blockers)


def test_dry_run_fails_closed_when_system_order_id_matches_multiple_rows():
    payloads = iter([_probe_payload(target_row_count=2), _order_payload()])

    report = run_audit_preflight(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=lambda _target_id, _js: next(payloads),
    )

    assert report.state == AuditExecutionState.STOPPED
    assert report.preflight_ready is False
    assert any(check.code == "TARGET_ROW_UNIQUE" for check in report.blockers)


def test_dry_run_fails_closed_when_target_row_does_not_prove_pending_state():
    probe = _probe_payload()
    probe["targetRows"][0]["pendingTextObserved"] = False
    payloads = iter([probe, _order_payload()])

    report = run_audit_preflight(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=lambda _target_id, _js: next(payloads),
    )

    assert report.preflight_ready is False
    assert any(check.code == "ORDER_PENDING_STATE" for check in report.blockers)


def test_preflight_treats_footer_as_history_before_checkbox_selection():
    probe = _probe_payload()
    probe["footerSelectedCounts"] = [2]
    payloads = iter([probe, _order_payload()])

    report = run_audit_preflight(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=lambda _target_id, _js: next(payloads),
    )

    assert report.preflight_ready is True
    footer_check = next(
        check
        for check in report.checks
        if check.code == "FOOTER_SELECTION_HISTORY"
    )
    assert footer_check.status == "info"
    assert "不参与放行判定" in footer_check.detail
