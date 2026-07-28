import tkinter as tk
import time
from types import SimpleNamespace

import pytest

from order_review.audit_probe import AuditExecutionState
from order_review.audit_runner import SingleOrderAuditReport
from order_review.case_repository import JsonCaseRepository
from order_review.erp_reader import SequenceOneIdentityProbe
from order_review.models import OrderSnapshot, Product
import order_review.ui as ui


def _walk(widget):
    return [
        item
        for child in widget.winfo_children()
        for item in [child, *_walk(child)]
    ]


def _buttons(window, text: str):
    return [
        item
        for item in _walk(window.content_frame)
        if isinstance(item, tk.Button) and item.cget("text") == text
    ]


def _quantity_entries(window):
    return [
        item
        for item in _walk(window.content_frame)
        if isinstance(item, tk.Entry) and item.cget("width") == 4
    ]


def _micro_controls(window, text: str):
    return [
        item.master
        for item in _walk(window.content_frame)
        if isinstance(item, tk.Label)
        and item.cget("text") == text
        and isinstance(item.master, tk.Frame)
        and int(item.master.cget("height")) == 24
    ]


def _enter_quantity(root, window, value: int):
    entry = _quantity_entries(window)[0]
    entry.delete(0, "end")
    entry.insert(0, str(value))
    draft = window.package_workflow.draft
    source = window.package_workflow.source_snapshot
    package = next(
        item for item in draft.packages if item.package_id == window._active_package_id
    )
    product = next(
        item
        for item in source.products
        if any(
            package_item.source_product_id == item.source_product_id
            for package_item in package.items
        )
        or draft.remaining_quantity(item) > 0
    )
    current = next(
        (
            item.quantity
            for item in package.items
            if item.source_product_id == product.source_product_id
        ),
        0,
    )
    maximum = current + draft.remaining_quantity(product)
    variable = tk.StringVar(master=root, value=str(value))
    window._commit_package_quantity(
        package.package_id,
        product.source_product_id,
        variable,
        maximum,
        current,
    )
    root.update()


@pytest.fixture
def rendered_window(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    monkeypatch.setattr(ui, "get_chrome_window_bounds", lambda: None)
    monkeypatch.setattr(ui, "get_chrome_window_state", lambda: None)
    monkeypatch.setattr(ui, "WINDOW_FOLLOW_INTERVAL_MS", 60_000)
    snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-ORDER-1",
        products=[
            Product(
                title="商品A（简称A）",
                standard_name="商品A",
                short_name="简称A",
                quantity=120,
                merchant_code="CODE-A",
                platform_order_number="ORDER-COPY",
            )
        ],
        raw_payload={"ui": True},
    )
    window = ui.OrderReviewWindow(
        root,
        reader=lambda: snapshot,
        repository=JsonCaseRepository(tmp_path / "cases.json"),
    )
    root.after_cancel(window._follow_browser_job)
    window._follow_browser_job = None
    root.after_cancel(window._order_watch_job)
    window._order_watch_job = None
    window.refresh()
    root.update()
    yield root, window
    if root.winfo_exists():
        window.close()


def test_package_buttons_refresh_visible_state_and_enforce_package_rules(
    rendered_window,
):
    root, window = rendered_window
    assert window._auto_refresh_enabled is False
    assert window.auto_refresh_button.cget("text") == "自动刷新"
    window.auto_refresh_button.invoke()
    assert window._auto_refresh_enabled is True
    assert window.auto_refresh_button.cget("text") == "停止自动刷新"
    window.auto_refresh_button.invoke()
    assert window._auto_refresh_enabled is False

    notice_widgets = [
        item
        for item in _walk(window.content_frame)
        if isinstance(item, tk.Text)
        and "不会估算包裹数" in item.get("1.0", "end-1c")
    ]
    assert notice_widgets
    assert notice_widgets[0].cget("wrap") == "char"
    assert int(notice_widgets[0].cget("height")) >= 2
    assert any(
        isinstance(item, tk.Label) and item.cget("text") == "建议复核物流"
        for item in _walk(window.content_frame)
    )
    assert all(
        button.cget("fg") != "#ffffff"
        for label in ("单包方案", "拆分包裹")
        for button in _buttons(window, label)
    )

    _buttons(window, "单包方案")[0].invoke()
    root.update()
    assert _buttons(window, "新增下一个包裹")[0].cget("state") == "disabled"
    assert _buttons(window, "确认方案")[0].cget("fg") != "#ffffff"
    assert not _buttons(window, "确定")
    assert all(
        button.cget("fg") != "#ffffff" and int(button.cget("pady")) <= 4
        for button in _walk(window.root)
        if isinstance(button, tk.Button)
    )

    _enter_quantity(root, window, 121)
    assert window.package_workflow.remaining_quantity == 0

    _enter_quantity(root, window, 37)
    assert window.package_workflow.remaining_quantity == 83
    assert _buttons(window, "新增下一个包裹")[0].cget("state") == "normal"
    assert all(control.winfo_width() <= 24 for control in _micro_controls(window, "+"))
    assert all(control.winfo_width() <= 24 for control in _micro_controls(window, "−"))

    _micro_controls(window, "+")[0].event_generate("<Button-1>")
    root.update()
    assert window.package_workflow.remaining_quantity == 82
    _micro_controls(window, "−")[0].event_generate("<Button-1>")
    root.update()
    assert window.package_workflow.remaining_quantity == 83

    _buttons(window, "新增下一个包裹")[0].invoke()
    root.update()
    assert len(window.package_workflow.draft.packages) == 2
    assert len(_quantity_entries(window)) == 1
    assert len(_buttons(window, "编辑")) == 1
    _buttons(window, "删除空包裹")[0].invoke()
    root.update()
    assert len(window.package_workflow.draft.packages) == 1
    assert not _buttons(window, "删除空包裹")

    _buttons(window, "新增下一个包裹")[0].invoke()
    root.update()
    assert len(_quantity_entries(window)) == 1
    assert len(_micro_controls(window, "MAX")) == 1
    _micro_controls(window, "MAX")[0].event_generate("<Button-1>")
    root.update()
    assert window.package_workflow.remaining_quantity == 0

    _buttons(window, "确认方案")[0].invoke()
    root.update()
    assert window.package_workflow.confirmed_case is not None, window._package_feedback
    assert not _buttons(window, "审核前检查")
    assert not _buttons(window, "审核当前订单")
    text_widgets = [
        item
        for item in _walk(window.content_frame)
        if isinstance(item, tk.Text) and "简称A" in item.get("1.0", "end-1c")
    ]

    assert text_widgets
    widget = text_widgets[0]
    widget.tag_add("sel", "1.0", "end-1c")
    window._copy_text_selection(type("CopyEvent", (), {"widget": widget})())
    root.update()

    assert "简称A" in root.clipboard_get()

    window.refresh()
    root.update()
    assert _buttons(window, "修改方案")
    assert not _buttons(window, "单包方案")
    assert window.package_workflow.historical_plan is not None
    _buttons(window, "修改方案")[0].invoke()
    root.update()
    assert window.package_workflow.draft is not None
    assert _buttons(window, "确认方案")

    large_snapshot = OrderSnapshot(
        is_expanded=True,
        products=[
            Product(
                title=f"大型商品{index}",
                standard_name=f"大型商品{index}",
                short_name=f"大型商品{index}",
                quantity=1,
                merchant_code=f"LARGE-{index}",
            )
            for index in range(20)
        ],
        raw_payload={"ui": "large"},
    )
    window.current_snapshot = large_snapshot
    window.package_workflow.load_order(large_snapshot)
    window.package_workflow.start_split()
    source = window.package_workflow.source_snapshot
    first_package_id = window.package_workflow.draft.packages[0].package_id
    window.package_workflow.set_quantity(
        first_package_id, source.products[0].source_product_id, 1
    )
    window.package_workflow.set_quantity(
        first_package_id, source.products[1].source_product_id, 1
    )
    window.package_workflow.add_package()
    for product_index in range(2, 10):
        active_id = window.package_workflow.draft.packages[-1].package_id
        window.package_workflow.set_quantity(
            active_id, source.products[product_index].source_product_id, 1
        )
        window.package_workflow.add_package()
    window._active_package_id = window.package_workflow.draft.packages[-1].package_id
    window._rerender_current_snapshot()
    root.update()

    assert len(window.package_workflow.draft.packages) == 10
    assert len(_buttons(window, "编辑")) == 9
    assert len(_quantity_entries(window)) == 10

    single_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-SINGLE-1",
        products=[
            Product(
                title="单包商品（单包简称）",
                standard_name="单包商品",
                short_name="单包简称",
                quantity=2,
                merchant_code="SINGLE-CODE",
                platform_order_number="SINGLE-PLATFORM-ORDER",
            )
        ],
        raw_payload={"ui": "single-audit-dry-run"},
    )
    window.current_snapshot = single_snapshot
    window.package_workflow.load_order(single_snapshot)
    window.package_workflow.start_single_package()
    window.package_workflow.confirm()
    window._rerender_current_snapshot()
    assert not _buttons(window, "审核前检查")
    audit_buttons = _buttons(window, "审核当前订单")
    assert len(audit_buttons) == 1
    assert audit_buttons[0].cget("state") == "normal"

    calls = []

    def fake_audit_executor(**kwargs):
        calls.append(kwargs)
        kwargs["progress_callback"](
            AuditExecutionState.SELECTING_ORDER,
            "正在勾选当前订单",
        )
        return SingleOrderAuditReport(
            execution_id="audit-ui-1",
            started_at="2026-07-28T00:00:00Z",
            finished_at="2026-07-28T00:00:01Z",
            target_system_order_id="SYSTEM-SINGLE-1",
            source_snapshot_id=kwargs["expected_source"].snapshot_id,
            confirmation_reference_id=kwargs["confirmation_reference_id"],
            state=AuditExecutionState.SUCCESS,
            steps=(),
        )

    window.audit_executor = fake_audit_executor
    audit_buttons[0].invoke()
    for _ in range(20):
        root.update()
        if not window._audit_running:
            break
        time.sleep(0.01)

    assert len(calls) == 1
    assert calls[0]["target_system_order_id"] == "SYSTEM-SINGLE-1"
    assert calls[0]["target_package_count"] == 1
    assert window._audit_running is False
    assert window._audit_completed_system_order_id == "SYSTEM-SINGLE-1"
    assert (
        window._auto_refresh_not_before - window.monotonic()
        <= ui.POST_AUDIT_REFRESH_DELAY_SECONDS
    )
    assert _buttons(window, "审核当前订单")[0].cget("state") == "disabled"

    matched_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-SINGLE-2",
        products=[
            Product(
                title="单包商品（单包简称）",
                standard_name="单包商品",
                short_name="单包简称",
                quantity=2,
                merchant_code="SINGLE-CODE",
                platform_order_number="SINGLE-PLATFORM-ORDER-2",
            )
        ],
        raw_payload={"ui": "exact-history-next"},
    )
    window.current_snapshot = matched_snapshot
    window.package_workflow.load_order(matched_snapshot)
    window._show_package_editor = False
    window._rerender_current_snapshot()
    root.update()

    assert window.package_workflow.auto_adopted_recommendation is True
    assert _buttons(window, "修改方案")
    assert _buttons(window, "审核当前订单")
    assert not _buttons(window, "确认方案")

    combined_calls = []

    def stopped_audit_executor(**kwargs):
        combined_calls.append(kwargs)
        return SingleOrderAuditReport(
            execution_id="audit-combined-1",
            started_at="2026-07-28T00:00:00Z",
            finished_at="2026-07-28T00:00:01Z",
            target_system_order_id="SYSTEM-SINGLE-2",
            source_snapshot_id=kwargs["expected_source"].snapshot_id,
            confirmation_reference_id=kwargs["confirmation_reference_id"],
            state=AuditExecutionState.STOPPED,
            steps=(),
        )

    window.audit_executor = stopped_audit_executor
    _buttons(window, "审核当前订单")[0].invoke()
    for _ in range(20):
        root.update()
        if not window._audit_running:
            break
        time.sleep(0.01)

    assert len(combined_calls) == 1
    assert window.package_workflow.confirmed_plan is not None
    assert window.package_workflow.draft is None


def _headless_auto_refresh_window(current_snapshot, clock):
    window = object.__new__(ui.OrderReviewWindow)
    workflow = SimpleNamespace(
        freight_pending=False,
        draft=None,
        recommendation_error="",
        load_order=lambda _snapshot: None,
        clear_order=lambda: None,
    )
    window.current_snapshot = current_snapshot
    window.package_workflow = workflow
    window.monotonic = lambda: clock[0]
    window.reader = lambda: current_snapshot
    window.auto_refresh_reader = lambda _expected: current_snapshot
    window._audit_running = False
    window._auto_refresh_enabled = True
    window._auto_refresh_paused = False
    window._auto_refresh_not_before = 0.0
    window._auto_refresh_same_order_id = ""
    window._auto_refresh_attempted_order_ids = set()
    window._order_watch_generation = 0
    window._order_change_candidate_id = ""
    window._order_change_candidate_count = 0
    window._order_change_candidate_since = 0.0
    window._show_package_editor = False
    window._initial_refresh_job = None
    window._active_package_id = None
    window._package_feedback = ""
    window._audit_feedback = ""
    window._current_view = None
    window._render_view = lambda view: setattr(window, "_current_view", view)
    return window


def test_auto_refresh_waits_for_stable_new_order_and_never_retries_failure():
    assert ui.ORDER_WATCH_INTERVAL_MS == 500
    assert ui.ORDER_CHANGE_STABLE_OBSERVATIONS == 2
    assert ui.ORDER_CHANGE_STABLE_SECONDS == 0.5
    assert ui.POST_AUDIT_REFRESH_DELAY_SECONDS == 0.0
    clock = [100.0]
    current_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-CURRENT-1",
        products=[],
        raw_payload={"ui": "current"},
    )
    window = _headless_auto_refresh_window(current_snapshot, clock)
    next_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-NEXT-1",
        products=[
            Product(
                title="下一单商品（下一单）",
                standard_name="下一单商品",
                short_name="下一单",
                quantity=2,
                merchant_code="NEXT-CODE",
                platform_order_number="NEXT-PLATFORM",
            )
        ],
        raw_payload={"ui": "auto-next"},
    )
    calls = []
    window.auto_refresh_reader = lambda expected: (
        calls.append(expected) or next_snapshot
    )
    safe_next = SequenceOneIdentityProbe(
        system_order_id="SYSTEM-NEXT-1",
        loading_count=0,
        visible_dialog_count=0,
        selected_row_count=0,
    )

    window._auto_refresh_not_before = 100.0
    window._handle_order_identity(safe_next)
    assert calls == []

    clock[0] = 100.49
    window._handle_order_identity(safe_next)
    assert calls == []
    clock[0] = 100.5
    window._handle_order_identity(safe_next)
    assert calls == ["SYSTEM-NEXT-1"]
    assert window.current_snapshot.system_order_id == "SYSTEM-NEXT-1"

    failed_calls = []
    window.current_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-NEXT-1",
        products=next_snapshot.products,
        raw_payload={"ui": "before-failed-next"},
    )
    window.package_workflow.load_order(window.current_snapshot)

    def failed_reader(expected):
        failed_calls.append(expected)
        raise RuntimeError("展开失败")

    window.auto_refresh_reader = failed_reader
    failed_probe = SequenceOneIdentityProbe(
        system_order_id="SYSTEM-NEXT-2",
        loading_count=0,
        visible_dialog_count=0,
        selected_row_count=0,
    )
    window._handle_order_identity(failed_probe)
    clock[0] = 101.0
    window._handle_order_identity(failed_probe)
    window._handle_order_identity(failed_probe)

    assert failed_calls == ["SYSTEM-NEXT-2"]
    assert window._auto_refresh_enabled is False
    assert "不会点击或重试展开" in window._current_view.footer_note


def test_auto_refresh_does_not_start_while_page_is_selected_or_loading():
    window = _headless_auto_refresh_window(
        OrderSnapshot(
            is_expanded=True,
            system_order_id="SYSTEM-CURRENT",
            products=[],
            raw_payload={"ui": "unsafe-probe-current"},
        ),
        [100.0],
    )
    calls = []
    window.auto_refresh_reader = lambda expected: calls.append(expected)
    unsafe_probes = (
        SequenceOneIdentityProbe("SYSTEM-NEXT", 1, 0, 0),
        SequenceOneIdentityProbe("SYSTEM-NEXT", 0, 1, 0),
        SequenceOneIdentityProbe("SYSTEM-NEXT", 0, 0, 1),
    )

    for probe in unsafe_probes:
        window._handle_order_identity(probe)
        window._handle_order_identity(probe)

    assert calls == []


def test_auto_refresh_never_retries_same_unexpanded_order():
    current_snapshot = OrderSnapshot(
        is_expanded=True,
        system_order_id="SYSTEM-CURRENT",
        products=[],
        raw_payload={"ui": "before-unexpanded-next"},
    )
    clock = [100.0]
    window = _headless_auto_refresh_window(current_snapshot, clock)
    collapsed_next = OrderSnapshot(
        is_expanded=False,
        system_order_id="SYSTEM-COLLAPSED-NEXT",
        products=[],
        raw_payload={"ui": "collapsed-next"},
    )
    calls = []
    window.auto_refresh_reader = lambda expected: (
        calls.append(expected) or collapsed_next
    )
    probe = SequenceOneIdentityProbe(
        system_order_id="SYSTEM-COLLAPSED-NEXT",
        loading_count=0,
        visible_dialog_count=0,
        selected_row_count=0,
    )

    window._handle_order_identity(probe)
    clock[0] = 100.5
    window._handle_order_identity(probe)
    window._handle_order_identity(probe)
    window._handle_order_identity(probe)

    assert calls == ["SYSTEM-COLLAPSED-NEXT"]
    assert window.current_snapshot.is_expanded is False


def test_manual_mode_and_stop_button_prevent_background_refresh():
    window = _headless_auto_refresh_window(
        OrderSnapshot(
            is_expanded=True,
            system_order_id="SYSTEM-CURRENT",
            products=[],
            raw_payload={"ui": "manual-mode"},
        ),
        [100.0],
    )
    calls = []
    window.auto_refresh_reader = lambda expected: calls.append(expected)
    probe = SequenceOneIdentityProbe(
        system_order_id="SYSTEM-NEXT",
        loading_count=0,
        visible_dialog_count=0,
        selected_row_count=0,
    )

    window._set_auto_refresh_enabled(False)
    window._handle_order_identity(probe)
    window._handle_order_identity(probe)

    assert window._auto_refresh_enabled is False
    assert calls == []
