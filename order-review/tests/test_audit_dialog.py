import json
from pathlib import Path

from order_review.audit_dialog import (
    AuditDialogProbe,
    build_audit_dialog_probe_js,
    validate_audit_dialog,
)


SYSTEM_ORDER_ID = "SYSTEM-ORDER-1"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "audit_dialog"


def _probe(name: str) -> AuditDialogProbe:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    return AuditDialogProbe.from_payload(payload)


def test_correct_real_dialog_sample_is_ready_but_does_not_submit():
    validation = validate_audit_dialog(
        _probe("correct.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_submit is True
    assert not validation.blockers
    assert "没有点击确定" in validation.render_text()


def test_wrong_query_scope_real_sample_is_blocked_with_affected_count():
    validation = validate_audit_dialog(
        _probe("wrong_query_scope.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_submit is False
    assert any(
        check.code == "QUERY_SCOPE_NOT_SELECTED"
        for check in validation.blockers
    )
    assert validation.render_text() == (
        "已停止：弹窗当前选择“处理查询结果中的订单”，"
        "可能影响当前查询到的 757 条订单。未点击确定。"
    )


def test_dialog_blocks_when_selected_order_is_not_the_target():
    payload = json.loads((FIXTURE_DIR / "correct.json").read_text(encoding="utf-8"))
    payload["selectedSystemOrderIds"] = ["OTHER-ORDER"]

    validation = validate_audit_dialog(
        AuditDialogProbe.from_payload(payload),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_submit is False
    assert any(check.code == "TARGET_SELECTION" for check in validation.blockers)


def test_dialog_blocks_when_counts_or_buttons_are_not_unique():
    payload = json.loads((FIXTURE_DIR / "correct.json").read_text(encoding="utf-8"))
    payload["footerSelectedCounts"] = [1, 2]
    payload["dialogs"][0]["listSelectedCount"] = 2
    payload["dialogs"][0]["confirmButtonCount"] = 2

    validation = validate_audit_dialog(
        AuditDialogProbe.from_payload(payload),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    blocked_codes = {check.code for check in validation.blockers}
    assert {
        "LIST_SELECTED_COUNT",
        "FOOTER_MULTIPLE_ORDER_GUARD",
        "CONFIRM_BUTTON_UNIQUE",
    }.issubset(blocked_codes)


def test_dialog_accepts_missing_or_stale_one_footer_as_non_positive_evidence():
    for footer_counts in ([], [1]):
        payload = json.loads(
            (FIXTURE_DIR / "correct.json").read_text(encoding="utf-8")
        )
        payload["footerSelectedCounts"] = footer_counts

        validation = validate_audit_dialog(
            AuditDialogProbe.from_payload(payload),
            target_system_order_id=SYSTEM_ORDER_ID,
        )

        assert validation.ready_to_submit is True


def test_split_audit_uses_dialog_count_after_prior_result_selection_validation():
    payload = json.loads((FIXTURE_DIR / "correct.json").read_text(encoding="utf-8"))
    payload["dialogs"][0]["listSelectedCount"] = 3
    payload["dialogs"][0]["listOption"]["text"] = (
        "处理列表页勾选的订单 已勾选 3 条订单"
    )
    payload["selectedRowCount"] = 1
    payload["selectedSystemOrderIds"] = ["ONLY-VISIBLE-VIRTUAL-ROW"]
    payload["footerSelectedCounts"] = [1]

    validation = validate_audit_dialog(
        AuditDialogProbe.from_payload(payload),
        target_system_order_id=SYSTEM_ORDER_ID,
        target_package_count=3,
    )

    assert validation.ready_to_submit is True
    assert not validation.blockers
    assert any(
        check.code == "SPLIT_SELECTION_ALREADY_VERIFIED"
        and check.status == "info"
        for check in validation.checks
    )


def test_split_audit_blocks_when_dialog_count_differs_from_package_count():
    validation = validate_audit_dialog(
        _probe("correct.json"),
        target_system_order_id=SYSTEM_ORDER_ID,
        target_package_count=3,
    )

    assert validation.ready_to_submit is False
    assert any(check.code == "LIST_SELECTED_COUNT" for check in validation.blockers)


def test_dialog_blocks_when_more_than_one_dialog_is_visible():
    payload = json.loads((FIXTURE_DIR / "correct.json").read_text(encoding="utf-8"))
    payload["dialogs"].append(payload["dialogs"][0].copy())

    validation = validate_audit_dialog(
        AuditDialogProbe.from_payload(payload),
        target_system_order_id=SYSTEM_ORDER_ID,
    )

    assert validation.ready_to_submit is False
    assert any(check.code == "DIALOG_UNIQUE" for check in validation.blockers)


def test_dialog_probe_js_is_strictly_read_only_and_uses_real_selectors():
    js = build_audit_dialog_probe_js(SYSTEM_ORDER_ID)

    assert "#/trade/toaudit/" in js
    assert "快麦ERP--待审核订单" in js
    assert ".el-message-box__wrapper" in js
    assert ".el-message-box__title" in js
    assert "input.el-radio__original" in js
    assert "处理列表页勾选的订单" in js
    assert "处理查询结果中的订单" in js
    assert ".click(" not in js
    assert ".dispatchEvent(" not in js
    assert "checked =" not in js
