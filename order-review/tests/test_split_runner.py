from types import SimpleNamespace

from order_review.audit_dialog import AuditDialogProbe, validate_audit_dialog
from order_review.audit_execution import AuditResultProbe, validate_audit_result
from order_review.audit_probe import AuditExecutionState
from order_review.models import OrderSnapshot, Product
from order_review.package_plan import (
    Package,
    PackageItem,
    PackagePlan,
    SourceSnapshot,
)
from order_review.split_result import SplitResultObservation, SplitResultRow
import order_review.split_runner as split_runner


def _source_and_plan():
    source = SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id="SYSTEM-1",
            order_numbers=["T1", "T2"],
            products=[
                Product(
                    title="商品A",
                    standard_name="商品A",
                    short_name="A",
                    quantity=9,
                    merchant_code="A",
                    platform_order_number="T1",
                    raw_attributes={"data-id": "ID-A"},
                ),
                Product(
                    title="商品B",
                    standard_name="商品B",
                    short_name="B",
                    quantity=2,
                    merchant_code="B",
                    platform_order_number="T2",
                    raw_attributes={"data-id": "ID-B"},
                ),
                Product(
                    title="商品C",
                    standard_name="商品C",
                    short_name="C",
                    quantity=1,
                    merchant_code="C",
                    platform_order_number="T2",
                    raw_attributes={
                        "data-id": "PARENT-ID-B",
                        "data-orderid": "ID-C",
                    },
                ),
            ],
            raw_payload={"split": True},
        )
    )
    products = source.products
    plan = PackagePlan(
        packages=(
            Package(
                "package-1",
                (PackageItem(products[0].source_product_id, "A", 3),),
            ),
            Package(
                "package-2",
                (PackageItem(products[0].source_product_id, "A", 6),),
            ),
            Package(
                "package-3",
                (
                    PackageItem(products[1].source_product_id, "B", 2),
                    PackageItem(products[2].source_product_id, "C", 1),
                ),
            ),
        )
    )
    return source, plan


def _result_source(
    system_order_id: str,
    products: list[tuple[str, str, int]],
) -> SourceSnapshot:
    return SourceSnapshot.from_order_snapshot(
        OrderSnapshot(
            is_expanded=True,
            system_order_id=system_order_id,
            order_numbers=tuple(dict.fromkeys(order for order, _name, _qty in products)),
            products=[
                Product(
                    title=f"商品{name}",
                    standard_name=f"商品{name}",
                    short_name=name,
                    quantity=quantity,
                    merchant_code=name,
                    platform_order_number=order_number,
                )
                for order_number, name, quantity in products
            ],
        )
    )


def _successful_split_result_observation() -> SplitResultObservation:
    return SplitResultObservation(
        loading_count=0,
        visible_dialog_count=0,
        rows=(
            SplitResultRow(1, True, _result_source("RESULT-1", [("T1", "A", 3)])),
            SplitResultRow(2, True, _result_source("RESULT-2", [("T1", "A", 6)])),
            SplitResultRow(
                3,
                True,
                _result_source("RESULT-3", [("T2", "B", 2), ("T2", "C", 1)]),
            ),
            SplitResultRow(4, False, None),
        ),
    )


def _split_audit_dialog(*_args, target_package_count=3, **_kwargs):
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
                            "text": (
                                "处理列表页勾选的订单 "
                                f"已勾选 {target_package_count} 条订单"
                            ),
                        },
                        "queryOption": {
                            "found": True,
                            "selected": False,
                            "value": "2",
                            "text": "处理查询结果中的订单",
                        },
                        "listSelectedCount": target_package_count,
                        "queryResultCount": None,
                        "confirmButtonCount": 1,
                        "cancelButtonCount": 1,
                    }
                ],
                # 前一阶段已逐包核验；弹窗阶段只验证当前提交范围。
                "selectedRowCount": 1,
                "selectedSystemOrderIds": ["VIRTUAL-ROW-ONLY"],
                "footerSelectedCounts": [1],
            }
        ),
        target_system_order_id="SYSTEM-1",
        target_package_count=target_package_count,
    )


def _split_audit_success_result(*_args, target_package_count=3, **_kwargs):
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
        target_system_order_id="SYSTEM-1",
        target_package_count=target_package_count,
    )


def test_package_quantities_follow_source_row_order():
    source, plan = _source_and_plan()

    assert split_runner._package_quantities(source, plan) == [
        [3, 0, 0],
        [6, 0, 0],
        [0, 2, 1],
    ]
    assert split_runner._expected_dialog_rows(source)[2]["id"] == "ID-C"


def test_added_package_verification_uses_remaining_and_disabled_input_state():
    source, plan = _source_and_plan()
    expected_rows = split_runner._expected_dialog_rows(source)
    quantities = split_runner._package_quantities(source, plan)[0]
    remaining = [
        row["quantity"] - quantity
        for row, quantity in zip(expected_rows, quantities)
    ]

    script = split_runner.build_verify_added_package_js(
        "SYSTEM-1",
        77,
        expected_rows,
        remaining,
        [quantities],
    )

    assert "remaining[index] === 0 ? input.disabled" in script
    assert "String(input.value) === '0' && !input.disabled" in script


def test_next_package_accepts_rows_exhausted_by_previous_package():
    source, plan = _source_and_plan()
    expected_rows = split_runner._expected_dialog_rows(source)
    quantities = split_runner._package_quantities(source, plan)[2]
    remaining = [0, 2, 1]

    fill_script = split_runner.build_fill_split_package_js(
        "SYSTEM-1",
        77,
        expected_rows,
        quantities,
        remaining,
        [[6, 0, 0], [3, 0, 0]],
    )
    add_script = split_runner.build_prepare_add_split_package_js(
        "SYSTEM-1",
        77,
        expected_rows,
        quantities,
        remaining,
        [[6, 0, 0], [3, 0, 0]],
    )

    assert "Number(inputExpected[index] || 0) === 0 && input.disabled" in fill_script
    assert "quantities[index] === 0 && input.disabled" in add_script
    assert "remaining[index] === 0 ?" in fill_script
    assert "remaining[index] === 0 ?" in add_script
    assert "JSON.stringify(actual) !== JSON.stringify(quantities)" not in fill_script
    assert "JSON.stringify(actual) !== JSON.stringify(quantities)" not in add_script


def test_split_runner_executes_one_continuous_protected_flow(monkeypatch):
    source, plan = _source_and_plan()
    evaluations = []
    clicks = []
    moves = []
    sleeps = []
    split_result_reads = []

    def evaluator(_target_id, js):
        evaluations.append(js)
        if "__orderReviewSplitNetwork =" in js:
            return {"ok": True}
        if "ORDER_REVIEW_ACTION:SELECT_TARGET" in js:
            return {
                "ok": True,
                "selectedRowCount": 1,
                "selectedSystemOrderIds": ["SYSTEM-1"],
                # 多包拆分只认真实复选框，不使用可能延迟的底部历史计数。
                "footerSelectedCounts": [99],
            }
        if "TASKBAR_NOT_UNIQUE" in js:
            return {"ok": True, "x": 10, "y": 20}
        if "MIXED_ITEM_NOT_UNIQUE" in js:
            return {"ok": True, "x": 20, "y": 30}
        if "DIALOG_NOT_READY" in js:
            return {"ok": True, "componentUid": 77}
        if "PACKAGE_QUANTITY_INVALID" in js:
            return {"ok": True}
        if "INPUT_DOM_MISMATCH" in js:
            return {"ok": True, "x": 30, "y": 40}
        if (
            "PACKAGE_CARD_COUNT_CHANGED" in js
            and "MAIN_CONFIRM_NOT_READY" not in js
        ):
            return {"ok": True}
        if "MAIN_CONFIRM_NOT_READY" in js:
            return {"ok": True, "x": 40, "y": 50}
        if "CONFIRM_TEXT_CHANGED" in js:
            return {"ok": True, "x": 50, "y": 60}
        if "RESULT_NOT_READY" in js:
            return {
                "ok": True,
                "status": 200,
                "result": 1,
                # ERP 的真实成功响应可能同时返回 success=false；
                # 是否成功以顶层 result 和准确新增数量为准。
                "splitSuccess": False,
                "increaseSplitCount": 2,
            }
        if "ORDER_REVIEW_ACTION:PREPARE_SPLIT_AUDIT_MENU" in js:
            return {"ok": True, "x": 60, "y": 70}
        if "ORDER_REVIEW_ACTION:PREPARE_SPLIT_ORDINARY_AUDIT" in js:
            return {"ok": True, "x": 70, "y": 80}
        if "ORDER_REVIEW_ACTION:PREPARE_SPLIT_AUDIT_CONFIRM" in js:
            return {"ok": True, "x": 80, "y": 90}
        raise AssertionError("出现未预期的页面脚本")

    preflight = SimpleNamespace(preflight_ready=True, blockers=())

    def split_result_reader(target_count, target_id, *, evaluator):
        split_result_reads.append((target_count, target_id, evaluator))
        return _successful_split_result_observation()

    report = split_runner.run_mixed_order_split(
        target_system_order_id="SYSTEM-1",
        expected_source=source,
        plan=plan,
        target_id="target-1",
        evaluator=evaluator,
        mouse_clicker=lambda target, x, y: clicks.append((target, x, y)),
        mouse_mover=lambda target, x, y: moves.append((target, x, y)),
        preflight_runner=lambda **_kwargs: preflight,
        split_result_reader=split_result_reader,
        audit_dialog_reader=_split_audit_dialog,
        audit_result_reader=_split_audit_success_result,
        sleeper=lambda seconds: sleeps.append(seconds),
    )

    assert report.state == AuditExecutionState.SUCCESS
    assert split_result_reads == [(3, "target-1", evaluator)]
    assert moves == [("target-1", 10.0, 20.0)]
    assert clicks == [
        ("target-1", 20.0, 30.0),
        ("target-1", 30.0, 40.0),
        ("target-1", 40.0, 50.0),
        ("target-1", 50.0, 60.0),
        ("target-1", 60.0, 70.0),
        ("target-1", 70.0, 80.0),
        ("target-1", 80.0, 90.0),
    ]
    assert sum("PACKAGE_QUANTITY_INVALID" in js for js in evaluations) == 2
    assert sum("INPUT_DOM_MISMATCH" in js for js in evaluations) == 1
    assert sum("FINAL_PACKAGE_MISMATCH" in js for js in evaluations) == 1
    fill_scripts = [
        js for js in evaluations if "PACKAGE_QUANTITY_INVALID" in js
    ]
    assert all("buttons[0].click()" not in js for js in fill_scripts)
    assert sleeps.count(split_runner.SPLIT_ACTION_PAUSE_SECONDS) == 11
    assert report.split_completed is True
    assert report.render_text().startswith("拆分并审核成功")


def test_split_result_poll_waits_until_first_n_selected_rows_are_ready():
    source, plan = _source_and_plan()
    clock = [0.0]
    observations = iter(
        [
            SplitResultObservation(
                loading_count=1,
                visible_dialog_count=0,
                rows=(SplitResultRow(1, True, None),),
            ),
            _successful_split_result_observation(),
        ]
    )
    read_count = []

    def reader(_target_count, _target_id, *, evaluator):
        read_count.append(evaluator)
        return next(observations)

    validation = split_runner._poll_split_result_validation(
        "target-1",
        source,
        plan,
        reader,
        split_runner.validate_split_result,
        lambda _target_id, _js: None,
        1.0,
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        lambda: clock[0],
    )

    assert validation.verified
    assert len(read_count) == 2


def test_split_result_detail_mismatch_is_definitive_and_not_retried():
    source, plan = _source_and_plan()
    observation = _successful_split_result_observation()
    wrong = SplitResultObservation(
        loading_count=0,
        visible_dialog_count=0,
        rows=(
            SplitResultRow(1, True, _result_source("RESULT-1", [("T1", "A", 4)])),
            SplitResultRow(2, True, _result_source("RESULT-2", [("T1", "A", 5)])),
            observation.rows[2],
            observation.rows[3],
        ),
    )
    read_count = []

    def reader(_target_count, _target_id, *, evaluator):
        read_count.append(evaluator)
        return wrong

    validation = split_runner._poll_split_result_validation(
        "target-1",
        source,
        plan,
        reader,
        split_runner.validate_split_result,
        lambda _target_id, _js: None,
        1.0,
        lambda _seconds: None,
        lambda: 0.0,
    )

    assert not validation.verified
    assert len(read_count) == 1
    assert any(
        check.code == "PACKAGE_MULTISET_MATCH" and not check.passed
        for check in validation.checks
    )


def test_split_result_missing_identity_after_stable_first_n_is_not_retried():
    source, plan = _source_and_plan()
    incomplete = SplitResultObservation(
        loading_count=0,
        visible_dialog_count=0,
        rows=(
            SplitResultRow(1, True, None),
            SplitResultRow(2, True, None),
            SplitResultRow(3, True, None),
        ),
    )
    read_count = []

    def reader(_target_count, _target_id, *, evaluator):
        read_count.append(evaluator)
        return incomplete

    validation = split_runner._poll_split_result_validation(
        "target-1",
        source,
        plan,
        reader,
        split_runner.validate_split_result,
        lambda _target_id, _js: None,
        1.0,
        lambda _seconds: None,
        lambda: 0.0,
    )

    assert not validation.verified
    assert len(read_count) == 1
    assert any(
        check.code == "RESULT_SYSTEM_IDS_PRESENT" and not check.passed
        for check in validation.checks
    )


def test_split_runner_stops_when_erp_returns_business_failure(monkeypatch):
    source, plan = _source_and_plan()

    def evaluator(_target_id, js):
        if "__orderReviewSplitNetwork =" in js:
            return {"ok": True}
        if "ORDER_REVIEW_ACTION:SELECT_TARGET" in js:
            return {
                "ok": True,
                "selectedRowCount": 1,
                "selectedSystemOrderIds": ["SYSTEM-1"],
            }
        if "TASKBAR_NOT_UNIQUE" in js:
            return {"ok": True, "x": 10, "y": 20}
        if "MIXED_ITEM_NOT_UNIQUE" in js:
            return {"ok": True, "x": 20, "y": 30}
        if "DIALOG_NOT_READY" in js:
            return {"ok": True, "componentUid": 77}
        if "PACKAGE_QUANTITY_INVALID" in js:
            return {"ok": True}
        if "INPUT_DOM_MISMATCH" in js:
            return {"ok": True, "x": 30, "y": 40}
        if "PACKAGE_CARD_COUNT_CHANGED" in js and "MAIN_CONFIRM_NOT_READY" not in js:
            return {"ok": True}
        if "MAIN_CONFIRM_NOT_READY" in js:
            return {"ok": True, "x": 40, "y": 50}
        if "CONFIRM_TEXT_CHANGED" in js:
            return {"ok": True, "x": 50, "y": 60}
        if "RESULT_NOT_READY" in js:
            return {
                "ok": True,
                "status": 200,
                "result": 0,
                "splitSuccess": None,
                "increaseSplitCount": 0,
            }
        raise AssertionError("出现未预期的页面脚本")

    report = split_runner.run_mixed_order_split(
        target_system_order_id="SYSTEM-1",
        expected_source=source,
        plan=plan,
        target_id="target-1",
        evaluator=evaluator,
        mouse_clicker=lambda *_args: None,
        mouse_mover=lambda *_args: None,
        preflight_runner=lambda **_kwargs: SimpleNamespace(
            preflight_ready=True,
            blockers=(),
        ),
        sleeper=lambda _seconds: None,
    )

    assert report.state == AuditExecutionState.STOPPED
    assert "increaseSplitCount=0/2" in report.render_text()


def test_network_success_uses_observed_mix_split_response_shape():
    assert split_runner._network_confirms_split(
        {
            "status": 200,
            "result": 1,
            "splitSuccess": None,
            "increaseSplitCount": 4,
        },
        4,
    )
    assert split_runner._network_confirms_split(
        {
            "status": 200,
            "result": 1,
            "splitSuccess": False,
            "increaseSplitCount": 4,
        },
        4,
    )
    assert not split_runner._network_confirms_split(
        {
            "status": 200,
            "result": 1,
            "splitSuccess": None,
            "increaseSplitCount": 3,
        },
        4,
    )


def test_network_observer_keeps_missing_split_success_as_unknown():
    script = split_runner.build_install_network_observer_js("split-1")

    assert (
        "typeof split.success === 'boolean' ? split.success : null"
        in script
    )


def test_split_audit_actions_recheck_exact_package_selection_before_dialog():
    trigger = split_runner.build_prepare_split_audit_menu_trigger_js(3)
    ordinary = split_runner.build_prepare_split_ordinary_audit_item_js(3)
    confirm = split_runner.build_prepare_split_audit_confirm_js(
        "SYSTEM-1",
        3,
    )

    assert "var expectedCount = 3" in trigger
    assert "selected.length !== expectedCount" in trigger
    assert "SPLIT_SELECTION_CHANGED" in trigger
    assert "TARGET_SELECTION_CHANGED" not in trigger
    assert "FOOTER_MULTIPLE_ORDERS" not in trigger
    assert "batch_audit" in ordinary
    assert "batch_force_audit" in ordinary
    assert "var expectedCount = 3" in ordinary
    assert "selected.length !== expectedCount" in ordinary
    assert "SPLIT_SELECTION_CHANGED" in ordinary
    assert "var expectedCount = 3" in confirm
    assert "Number(count[1]) !== expectedCount" in confirm
    assert ".click()" not in trigger
    assert ".click()" not in ordinary
    assert ".click()" not in confirm
