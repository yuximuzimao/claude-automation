import tkinter as tk

import pytest

from order_review.case_repository import JsonCaseRepository
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
    snapshot = OrderSnapshot(
        is_expanded=True,
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
    window.refresh()
    root.update()
    yield root, window
    root.destroy()


def test_package_buttons_refresh_visible_state_and_enforce_package_rules(
    rendered_window,
):
    root, window = rendered_window
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
    assert _buttons(window, "修改已保存方案")
    assert not _buttons(window, "单包方案")
    assert window.package_workflow.historical_plan is not None
    _buttons(window, "修改已保存方案")[0].invoke()
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
