import json
from pathlib import Path

from order_review.audit_execution import (
    AuditResultProbe,
    SingleOrderSelectionProbe,
    build_audit_result_probe_js,
    validate_audit_result,
    validate_single_order_selection,
)
from order_review.audit_probe import AuditExecutionState


SYSTEM_ORDER_ID = "SYSTEM-ORDER-1"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "audit_result"


def _result_probe(name: str) -> AuditResultProbe:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return AuditResultProbe.from_payload(payload)


def test_selection_uses_real_checkbox_as_primary_evidence_and_accepts_stale_one():
    validation = validate_single_order_selection(
        SingleOrderSelectionProbe(
            selected_row_count=1,
            selected_system_order_ids=(SYSTEM_ORDER_ID,),
            footer_selected_counts=(1,),
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_open_audit_menu is True


def test_selection_blocks_footer_two_as_reverse_safety_guard():
    validation = validate_single_order_selection(
        SingleOrderSelectionProbe(
            selected_row_count=1,
            selected_system_order_ids=(SYSTEM_ORDER_ID,),
            footer_selected_counts=(2,),
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_open_audit_menu is False
    assert any(
        check.code == "FOOTER_MULTIPLE_ORDER_GUARD"
        for check in validation.blockers
    )


def test_selection_blocks_wrong_target_even_when_footer_is_one():
    validation = validate_single_order_selection(
        SingleOrderSelectionProbe(
            selected_row_count=1,
            selected_system_order_ids=("OTHER-ORDER",),
            footer_selected_counts=(1,),
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_open_audit_menu is False
    assert any(check.code == "TARGET_SELECTION" for check in validation.blockers)


def test_single_order_rules_refuse_multi_package_plan():
    validation = validate_single_order_selection(
        SingleOrderSelectionProbe(
            selected_row_count=1,
            selected_system_order_ids=(SYSTEM_ORDER_ID,),
            footer_selected_counts=(1,),
        ),
        target_system_order_id=SYSTEM_ORDER_ID,
        target_package_count=2,
    )

    assert validation.ready_to_open_audit_menu is False
    assert any(
        check.code == "SINGLE_PACKAGE_ORDER_SCOPE"
        for check in validation.blockers
    )


def test_result_succeeds_when_target_disappears_even_if_footer_stays_one():
    validation = validate_audit_result(
        _result_probe("success_with_stale_footer.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.state == AuditExecutionState.SUCCESS
    assert validation.successful is True
    assert "底部汇总可能残留" in validation.render_text()


def test_split_audit_result_accepts_multi_package_scope_after_dialog_proof():
    validation = validate_audit_result(
        _result_probe("success_with_stale_footer.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
        target_package_count=3,
    )

    assert validation.state == AuditExecutionState.SUCCESS
    assert "审核弹窗确认的 3 条订单" in validation.render_text()


def test_result_is_unknown_when_target_still_exists_and_never_retries():
    validation = validate_audit_result(
        _result_probe("unknown_target_still_present.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.state == AuditExecutionState.UNKNOWN
    assert validation.successful is False
    assert "不会重试" in validation.render_text()


def test_result_failure_message_prevents_success():
    payload = json.loads(
        (FIXTURE_DIR / "success_with_stale_footer.json").read_text(encoding="utf-8")
    )
    payload["messages"] = ["审核失败，请稍后重试"]

    validation = validate_audit_result(
        AuditResultProbe.from_payload(payload),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.state == AuditExecutionState.STOPPED
    assert validation.successful is False
    assert any(check.code == "FAILURE_MESSAGE" for check in validation.blockers)
    assert "审核已停止" in validation.render_text()


def test_incomplete_result_payload_never_becomes_success():
    validation = validate_audit_result(
        AuditResultProbe.from_payload({"targetPresentInDom": False}),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.state == AuditExecutionState.UNKNOWN
    assert validation.successful is False
    assert any(
        check.code == "RESULT_PROBE_COMPLETE"
        for check in validation.blockers
    )


def test_result_probe_js_is_strictly_read_only():
    js = build_audit_result_probe_js(SYSTEM_ORDER_ID)

    assert SYSTEM_ORDER_ID in js
    assert "#/trade/toaudit/" in js
    assert ".module-trade-list-item" in js
    assert ".el-message-box__wrapper" in js
    assert ".click(" not in js
    assert ".dispatchEvent(" not in js
    assert "mouseover" not in js
