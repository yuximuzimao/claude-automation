import json

from order_review.audit_dialog import (
    AuditDialogProbe,
    validate_audit_dialog,
)
from order_review.audit_execution import (
    AuditResultProbe,
    validate_audit_result,
)
from order_review.audit_probe import (
    AuditExecutionLogStore,
    AuditExecutionState,
    AuditPreflightReport,
    ProbeCheck,
)
from order_review.audit_runner import (
    build_prepare_audit_menu_trigger_js,
    build_prepare_confirm_js,
    build_prepare_ordinary_audit_item_js,
    build_select_target_order_js,
    click_mouse_at,
    run_single_order_audit,
)
from order_review.erp_reader import snapshot_from_payload
from order_review.package_plan import SourceSnapshot


SYSTEM_ORDER_ID = "SYSTEM-ORDER-1"


def _source() -> SourceSnapshot:
    snapshot = snapshot_from_payload(
        {
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
    )
    return SourceSnapshot.from_order_snapshot(snapshot)


def _preflight(*_args, **_kwargs) -> AuditPreflightReport:
    source = _source()
    return AuditPreflightReport(
        execution_id="preflight-1",
        started_at="2026-07-28T00:00:00Z",
        observed_at="2026-07-28T00:00:01Z",
        target_id="target-1",
        target_system_order_id=SYSTEM_ORDER_ID,
        source_snapshot_id=source.snapshot_id,
        confirmation_reference_id="case-1",
        target_package_count=1,
        state=AuditExecutionState.IDLE,
        preflight_ready=True,
        checks=(),
        raw_probe={},
    )


def _dialog(*_args, **_kwargs):
    return validate_audit_dialog(
        AuditDialogProbe.from_payload(
            {
                "dialogs": [
                    {
                        "title": "提示",
                        "listOption": {
                            "found": True,
                            "selected": True,
                            "value": "1",
                            "text": "处理列表页勾选的订单 已勾选 1 条订单",
                        },
                        "queryOption": {
                            "found": True,
                            "selected": False,
                            "value": "2",
                            "text": "处理查询结果中的订单",
                        },
                        "listSelectedCount": 1,
                        "queryResultCount": None,
                        "confirmButtonCount": 1,
                        "cancelButtonCount": 1,
                    }
                ],
                "selectedRowCount": 1,
                "selectedSystemOrderIds": [SYSTEM_ORDER_ID],
                "footerSelectedCounts": [1],
            }
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
    )


def _success_result(*_args, **_kwargs):
    return validate_audit_result(
        AuditResultProbe.from_payload(
            {
                "targetPresentInDom": False,
                "targetVisibleCount": 0,
                "visibleDialogCount": 0,
                "selectedRowCount": 0,
                "selectedSystemOrderIds": [],
                "footerSelectedCounts": [1],
                "loadingCount": 0,
                "currentSequenceOneSystemOrderId": "NEXT-ORDER",
                "messages": [],
            }
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
    )


def _evaluator_with_selection(footer_counts=(1,)):
    def evaluator(_target_id, js):
        if "ORDER_REVIEW_ACTION:SELECT_TARGET" in js:
            return {
                "ok": True,
                "selectedRowCount": 1,
                "selectedSystemOrderIds": [SYSTEM_ORDER_ID],
                "footerSelectedCounts": list(footer_counts),
            }
        if "ORDER_REVIEW_ACTION:PREPARE_MENU_TRIGGER" in js:
            return {"ok": True, "x": 10, "y": 20}
        if "ORDER_REVIEW_ACTION:PREPARE_ORDINARY_AUDIT" in js:
            return {"ok": True, "x": 30, "y": 40}
        if "ORDER_REVIEW_ACTION:PREPARE_CONFIRM" in js:
            return {"ok": True, "x": 50, "y": 60}
        raise AssertionError("unexpected JavaScript")

    return evaluator


def test_full_single_order_audit_clicks_each_stage_once_and_stops_after_success(tmp_path):
    clicks = []
    progress = []

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        confirmation_reference_id="case-1",
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=_preflight,
        dialog_reader=_dialog,
        result_reader=_success_result,
        progress_callback=lambda state, detail: progress.append((state, detail)),
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.SUCCESS
    assert clicks == [
        ("target-1", 10.0, 20.0),
        ("target-1", 30.0, 40.0),
        ("target-1", 50.0, 60.0),
    ]
    assert progress[-1][0] == AuditExecutionState.SUCCESS
    assert "没有继续处理下一单" in report.render_text()


def test_footer_two_stops_before_opening_audit_menu():
    clicks = []

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=_evaluator_with_selection((2,)),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=_preflight,
        dialog_reader=_dialog,
        result_reader=_success_result,
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.STOPPED
    assert clicks == []
    assert "2" in report.render_text()


def test_preflight_failure_stops_before_any_erp_click():
    clicks = []

    def blocked_preflight(*_args, **_kwargs):
        source = _source()
        return AuditPreflightReport(
            execution_id="preflight-blocked",
            started_at="2026-07-28T00:00:00Z",
            observed_at="2026-07-28T00:00:01Z",
            target_id="target-1",
            target_system_order_id=SYSTEM_ORDER_ID,
            source_snapshot_id=source.snapshot_id,
            confirmation_reference_id="case-1",
            target_package_count=1,
            state=AuditExecutionState.STOPPED,
            preflight_ready=False,
            checks=(
                ProbeCheck(
                    code="TARGET_MISMATCH",
                    label="目标订单",
                    status="blocked",
                    detail="ERP 当前订单与已确认方案不是同一单",
                ),
            ),
            raw_probe={},
        )

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=blocked_preflight,
        dialog_reader=_dialog,
        result_reader=_success_result,
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.STOPPED
    assert clicks == []
    assert "不是同一单" in report.render_text()


def test_wrong_dialog_scope_stops_without_clicking_confirm():
    clicks = []

    def wrong_dialog(*_args, **_kwargs):
        probe = _dialog().probe
        payload = {
            "dialogs": [
                {
                    "title": probe.title,
                    "listOption": {
                        "found": True,
                        "selected": False,
                        "value": "1",
                        "text": "处理列表页勾选的订单",
                    },
                    "queryOption": {
                        "found": True,
                        "selected": True,
                        "value": "2",
                        "text": "处理查询结果中的订单 共查询 757 条订单",
                    },
                    "listSelectedCount": None,
                    "queryResultCount": 757,
                    "confirmButtonCount": 1,
                    "cancelButtonCount": 1,
                }
            ],
            "selectedRowCount": 1,
            "selectedSystemOrderIds": [SYSTEM_ORDER_ID],
            "footerSelectedCounts": [1],
        }
        return validate_audit_dialog(
            AuditDialogProbe.from_payload(payload),
            target_system_order_id=SYSTEM_ORDER_ID,
        )

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=_preflight,
        dialog_reader=wrong_dialog,
        result_reader=_success_result,
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.STOPPED
    assert len(clicks) == 2
    assert "757" in report.render_text()


def test_unknown_result_never_retries_confirm():
    clicks = []

    def unknown_result(*_args, **_kwargs):
        return validate_audit_result(
            AuditResultProbe.from_payload(
                {
                    "targetPresentInDom": True,
                    "targetVisibleCount": 1,
                    "visibleDialogCount": 0,
                    "selectedRowCount": 0,
                    "selectedSystemOrderIds": [],
                    "footerSelectedCounts": [1],
                    "loadingCount": 0,
                    "currentSequenceOneSystemOrderId": SYSTEM_ORDER_ID,
                    "messages": [],
                }
            ),
            target_system_order_id=SYSTEM_ORDER_ID,
        )

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=_preflight,
        dialog_reader=_dialog,
        result_reader=unknown_result,
        sleeper=lambda _seconds: None,
        result_wait_seconds=0,
    )

    assert report.state == AuditExecutionState.UNKNOWN
    assert len(clicks) == 3
    assert "没有重试" in report.render_text()


def test_result_reader_exception_after_confirm_is_unknown_and_never_retries():
    clicks = []

    def broken_result_reader(*_args, **_kwargs):
        raise RuntimeError("结果读取连接中断")

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        preflight_runner=_preflight,
        dialog_reader=_dialog,
        result_reader=broken_result_reader,
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.UNKNOWN
    assert len(clicks) == 3
    assert "结果读取连接中断" in report.render_text()


def test_multi_package_plan_never_reads_or_clicks_erp():
    calls = []

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        target_package_count=2,
        evaluator=lambda *_args: calls.append("eval"),
        mouse_clicker=lambda *_args: calls.append("click"),
        target_finder=lambda: calls.append("target"),
    )

    assert report.state == AuditExecutionState.STOPPED
    assert calls == []


def test_execution_report_is_appended_to_jsonl_log(tmp_path):
    log_store = AuditExecutionLogStore(tmp_path / "audit-executions.jsonl")

    report = run_single_order_audit(
        target_system_order_id=SYSTEM_ORDER_ID,
        expected_source=_source(),
        confirmation_reference_id="case-1",
        target_id="target-1",
        evaluator=_evaluator_with_selection(),
        mouse_clicker=lambda *_args: None,
        preflight_runner=_preflight,
        dialog_reader=_dialog,
        result_reader=_success_result,
        log_store=log_store,
        sleeper=lambda _seconds: None,
    )

    records = [
        json.loads(line)
        for line in log_store.path.read_text(encoding="utf-8").splitlines()
    ]
    assert report.state == AuditExecutionState.SUCCESS
    assert len(records) == 1
    assert records[0]["mode"] == "single_order_audit"
    assert records[0]["executionId"] == report.execution_id
    assert records[0]["targetSystemOrderId"] == SYSTEM_ORDER_ID
    assert records[0]["state"] == "success"
    assert records[0]["steps"][-1]["state"] == "success"


def test_action_scripts_keep_scope_guards_and_only_selection_uses_dom_click():
    select_js = build_select_target_order_js(SYSTEM_ORDER_ID)
    trigger_js = build_prepare_audit_menu_trigger_js(SYSTEM_ORDER_ID)
    ordinary_js = build_prepare_ordinary_audit_item_js(SYSTEM_ORDER_ID)
    confirm_js = build_prepare_confirm_js(SYSTEM_ORDER_ID)

    assert select_js.count(".click()") == 1
    assert "FOOTER_MULTIPLE_ORDERS" in select_js
    assert "batch_force_audit" in trigger_js
    assert "强制审核" in ordinary_js
    assert ".click()" not in trigger_js
    assert ".click()" not in ordinary_js
    assert ".click()" not in confirm_js
    assert "query.checked" in confirm_js
    assert "Number(count[1]) !== 1" in confirm_js


def test_mouse_clicker_dispatches_one_physical_click(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "order_review.audit_runner.cdp.cdp_call",
        lambda target, method, params: calls.append((target, method, params)),
    )

    click_mouse_at("target-1", 12.5, 30.5)

    assert [item[2]["type"] for item in calls] == [
        "mouseMoved",
        "mousePressed",
        "mouseReleased",
    ]
    assert sum(item[2].get("clickCount", 0) == 1 for item in calls) == 2
