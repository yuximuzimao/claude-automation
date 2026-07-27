from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .case_repository import JsonCaseRepository
from .erp_reader import read_sequence_one_order
from .models import OrderSnapshot, Product
from .package_plan import PackagePlanValidationError
from .package_workflow import PackagePlanWorkflow
from .recommendations import MATCH_SINGLE_PACKAGE_CAPACITY
from .rules import judge
from .window_position import (
    get_chrome_window_bounds,
    get_chrome_window_state,
    panel_geometry_from_browser_bounds,
)


WINDOW_WIDTH = 360
WINDOW_HEIGHT = 760
WINDOW_GAP = 8
WINDOW_FOLLOW_INTERVAL_MS = 1500
FONT_FAMILY = "Helvetica Neue"
MACOS_THEME = {
    "window_bg": "#f6f7f9",
    "titlebar_bg": "#ffffff",
    "surface": "#ffffff",
    "surface_soft": "#f1f3f6",
    "border": "#d9dde5",
    "divider": "#eceef2",
    "primary_text": "#1d2430",
    "secondary_text": "#4f5968",
    "muted_text": "#6b7482",
    "soft_text": "#9098a5",
    "accent": "#2563eb",
    "accent_pressed": "#1d4ed8",
    "accent_soft": "#eaf0ff",
    "accent_border": "#d9e3fa",
    "success": "#16805d",
    "package": "#7451c7",
    "package_soft": "#f2eefb",
    "warning": "#a45f0a",
    "warning_soft": "#fff6e8",
    "close": "#ff5f57",
    "close_pressed": "#e0443e",
    "refresh_text": "刷新",
    "close_text": "×",
}


@dataclass(frozen=True)
class MetricView:
    value: str
    label: str


@dataclass(frozen=True)
class ProductRowView:
    title: str
    quantity: int


@dataclass(frozen=True)
class OrderGroupView:
    label: str
    kind_count: int
    total_quantity: int
    products: list[ProductRowView]
    platform_order_numbers: tuple[str, ...] = ()
    relation_hint: str = ""


@dataclass(frozen=True)
class PackageView:
    label: str
    kind_count: int
    total_quantity: int
    products: list[ProductRowView]


@dataclass(frozen=True)
class PackagePlanView:
    status: str
    packages: list[PackageView]
    unassigned_kind_count: int
    unassigned_quantity: int
    note: str


@dataclass(frozen=True)
class BackendDetailsView:
    summary: str = ""
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SidebarView:
    status: str
    metrics: list[MetricView]
    aggregate_products: list[ProductRowView]
    order_groups: list[OrderGroupView]
    package_plan: PackagePlanView
    backend_details: BackendDetailsView = field(default_factory=BackendDetailsView)
    footer_note: str = ""


def _empty_package_plan() -> PackagePlanView:
    return PackagePlanView(
        status="未开始",
        packages=[],
        unassigned_kind_count=0,
        unassigned_quantity=0,
        note="",
    )


def _product_display_name(product: Product) -> str:
    return product.short_name or product.standard_name or product.title


def _product_identity(product: Product) -> tuple[str, ...]:
    if product.merchant_code:
        return ("merchant", product.merchant_code)
    if product.sku_id:
        return ("sku", product.sku_id)
    if product.spu_id:
        return ("spu", product.spu_id)
    return ("name", _product_display_name(product))


def _aggregate_products(products: list[Product]) -> list[ProductRowView]:
    totals: OrderedDict[tuple[str, ...], ProductRowView] = OrderedDict()
    for product in products:
        key = _product_identity(product)
        current = totals.get(key)
        if current is None:
            totals[key] = ProductRowView(
                title=_product_display_name(product),
                quantity=product.quantity,
            )
        else:
            totals[key] = ProductRowView(
                title=current.title,
                quantity=current.quantity + product.quantity,
            )
    return list(totals.values())


def _unique_nonempty(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _platform_orders_are_consecutive(order_numbers: tuple[str, ...]) -> bool:
    if len(order_numbers) < 2 or not all(number.isdigit() for number in order_numbers):
        return False
    numeric = sorted({int(number) for number in order_numbers})
    return len(numeric) == len(order_numbers) and all(
        right - left == 1 for left, right in zip(numeric, numeric[1:])
    )


def _build_order_groups(snapshot: OrderSnapshot) -> list[OrderGroupView]:
    products = snapshot.products
    if not products:
        return []

    if snapshot.groups:
        result: list[OrderGroupView] = []
        referenced_indexes: set[int] = set()
        for group_position, group in enumerate(snapshot.groups, start=1):
            indexes = [
                index
                for index in group.product_indexes
                if 0 <= index < len(products)
            ]
            if not indexes:
                indexes = [
                    index
                    for index, product in enumerate(products)
                    if product.source_group_index == group.index
                ]
            group_products = [products[index] for index in indexes]
            if not group_products:
                continue
            referenced_indexes.update(indexes)
            aggregate = _aggregate_products(group_products)
            platform_order_numbers = _unique_nonempty(
                [
                    *group.order_numbers,
                    *(product.platform_order_number for product in group_products),
                ]
            )
            result.append(
                OrderGroupView(
                    label=f"订单 {group_position}",
                    kind_count=len(aggregate),
                    total_quantity=sum(product.quantity for product in group_products),
                    products=[
                        ProductRowView(
                            title=_product_display_name(product),
                            quantity=product.quantity,
                        )
                        for product in group_products
                    ],
                    platform_order_numbers=platform_order_numbers,
                    relation_hint=(
                        "合并订单" if len(snapshot.groups) > 1 else ""
                    ),
                )
            )

        ungrouped = [
            product
            for index, product in enumerate(products)
            if index not in referenced_indexes
        ]
        if ungrouped:
            aggregate = _aggregate_products(ungrouped)
            result.append(
                OrderGroupView(
                    label="未分组商品",
                    kind_count=len(aggregate),
                    total_quantity=sum(product.quantity for product in ungrouped),
                    products=[
                        ProductRowView(
                            title=_product_display_name(product),
                            quantity=product.quantity,
                        )
                        for product in ungrouped
                    ],
                    platform_order_numbers=_unique_nonempty(
                        [product.platform_order_number for product in ungrouped]
                    ),
                )
            )
        if result:
            return result

    aggregate = _aggregate_products(products)
    platform_order_numbers = _unique_nonempty(
        [product.platform_order_number for product in products]
    )
    relation_parts: list[str] = []
    if len(platform_order_numbers) > 1:
        relation_parts.append("同一 ERP 订单组")
    if _platform_orders_are_consecutive(platform_order_numbers):
        relation_parts.append("平台单号连续")

    return [
        OrderGroupView(
            label="当前订单组",
            kind_count=len(aggregate),
            total_quantity=sum(product.quantity for product in products),
            products=[
                ProductRowView(
                    title=_product_display_name(product),
                    quantity=product.quantity,
                )
                for product in products
            ],
            platform_order_numbers=platform_order_numbers,
            relation_hint=" · ".join(relation_parts),
        )
    ]


def _compact_fields(values: dict[str, str]) -> str:
    return " · ".join(f"{key}={value}" for key, value in values.items() if value)


def _build_backend_details(snapshot: OrderSnapshot) -> BackendDetailsView:
    lines: list[str] = []
    for index, product in enumerate(snapshot.products, start=1):
        lines.append(f"{index}. {_product_display_name(product)} ×{product.quantity}")
        lines.append(f"   平台单号：{product.platform_order_number or '未读取到'}")
        lines.append(f"   平台商品 ID：{product.spu_id or '未读取到'}")
        lines.append(f"   平台 SKU ID：{product.sku_id or '未读取到'}")
        if product.platform_spec:
            lines.append(f"   平台规格：{product.platform_spec}")
        if product.platform_name:
            lines.append(f"   平台名称：{product.platform_name}")
        lines.append(f"   商家编码：{product.merchant_code or '未读取到'}")
        if product.main_merchant_code:
            lines.append(f"   主商家编码：{product.main_merchant_code}")

    return BackendDetailsView(
        summary=f"{len(snapshot.products)} 条商品明细",
        lines=lines,
    )


def format_sidebar_lines(snapshot: OrderSnapshot) -> list[str]:
    view = build_sidebar_view(snapshot)
    lines = [view.status]
    if view.metrics:
        lines.append(" / ".join(f"{metric.value} {metric.label}" for metric in view.metrics))
    if view.aggregate_products:
        lines.append("商品总量")
        lines.extend(
            f"{product.title} x{product.quantity}" for product in view.aggregate_products
        )
    for group in view.order_groups:
        lines.append(f"{group.label}：{group.kind_count} 种 / {group.total_quantity} 件")
        lines.extend(f"{product.title} x{product.quantity}" for product in group.products)
    plan = view.package_plan
    if plan.status:
        lines.append(f"包裹方案：{plan.status}")
    if plan.packages:
        for package in plan.packages:
            lines.append(
                f"{package.label}：{package.kind_count} 种 / {package.total_quantity} 件"
            )
            lines.extend(
                f"{product.title} x{product.quantity}" for product in package.products
            )
    elif plan.unassigned_kind_count or plan.unassigned_quantity:
        lines.append(
            f"待分配：{plan.unassigned_kind_count} 种 / {plan.unassigned_quantity} 件"
        )
    if plan.note:
        lines.append(plan.note)
    if view.footer_note:
        lines.append(view.footer_note)
    return lines


def build_sidebar_view(snapshot: OrderSnapshot) -> SidebarView:
    judgment = judge(
        is_expanded=snapshot.is_expanded,
        products=snapshot.products,
        has_suite_action=snapshot.has_suite_action,
    )
    if not snapshot.is_expanded:
        return SidebarView(
            status=judgment.message,
            metrics=[],
            aggregate_products=[],
            order_groups=[],
            package_plan=_empty_package_plan(),
            backend_details=_build_backend_details(snapshot),
        )

    aggregate_products = _aggregate_products(snapshot.products)
    order_groups = _build_order_groups(snapshot)
    footer_parts = [
        f"可合单标记：{'有' if snapshot.has_can_merge_mark else '无'}",
        "编码仅供后台匹配，不在人工界面展示",
    ]
    return SidebarView(
        status=judgment.message,
        metrics=[
            MetricView(str(len(order_groups)), "订单组"),
            MetricView(str(len(aggregate_products)), "商品种类"),
            MetricView(str(snapshot.total_quantity), "商品总件数"),
        ],
        aggregate_products=aggregate_products,
        order_groups=order_groups,
        package_plan=PackagePlanView(
            status="待计算",
            packages=[],
            unassigned_kind_count=len(aggregate_products),
            unassigned_quantity=snapshot.total_quantity,
            note="尚未接入拆包算法；当前仅表示所有商品待分配，不代表整单可按一个包裹发出。",
        ),
        backend_details=_build_backend_details(snapshot),
        footer_note=" · ".join(footer_parts),
    )


class OrderReviewWindow:
    def __init__(
        self,
        root: tk.Tk,
        reader: Callable[[], OrderSnapshot] = read_sequence_one_order,
        repository: JsonCaseRepository | None = None,
    ) -> None:
        self.root = root
        self.reader = reader
        self.root.title("审单悬浮窗")
        self.root.geometry(self._initial_geometry())
        self.root.resizable(False, True)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", False)
        self._drag_offset = (0, 0)
        self._aggregate_expanded = False
        self._orders_expanded = True
        self._backend_expanded = False
        self._current_view: SidebarView | None = None
        self.current_snapshot: OrderSnapshot | None = None
        self.package_workflow = PackagePlanWorkflow(repository)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._package_feedback = ""
        self._active_package_id: str | None = None
        self._quantity_commit_jobs: dict[tuple[str, str], str] = {}
        self._last_browser_bounds: tuple[int, int, int, int] | None = None
        self._browser_was_minimized: bool | None = None
        self._build()
        self._initial_refresh_job: str | None = self.root.after(
            300, self._run_initial_refresh
        )
        self.root.after(WINDOW_FOLLOW_INTERVAL_MS, self._follow_browser_window)

    def _initial_geometry(self) -> str:
        bounds = get_chrome_window_bounds()
        if bounds is None:
            return f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+20+120"
        return panel_geometry_from_browser_bounds(
            bounds,
            panel_width=WINDOW_WIDTH,
            panel_height=WINDOW_HEIGHT,
            gap=WINDOW_GAP,
        )

    def _follow_browser_window(self) -> None:
        if not self.root.winfo_exists():
            return
        state = get_chrome_window_state()
        if state is None or state.minimized:
            if state is not None and self._browser_was_minimized is not True:
                self.root.withdraw()
            if state is not None:
                self._browser_was_minimized = True
        else:
            became_visible = self._browser_was_minimized is True
            bounds_changed = state.bounds != self._last_browser_bounds
            if became_visible:
                self.root.deiconify()
            if became_visible or bounds_changed:
                self.root.geometry(
                    panel_geometry_from_browser_bounds(
                        state.bounds,
                        panel_width=WINDOW_WIDTH,
                        panel_height=WINDOW_HEIGHT,
                        gap=WINDOW_GAP,
                    )
                )
            self._last_browser_bounds = state.bounds
            self._browser_was_minimized = False
        self.root.after(WINDOW_FOLLOW_INTERVAL_MS, self._follow_browser_window)

    def _build(self) -> None:
        self.root.configure(bg=MACOS_THEME["window_bg"])
        self._build_header()
        self._build_overview()
        self._build_scroll_area()
        self._render_view(
            SidebarView(
                status="判断：点击刷新读取当前 1 号订单",
                metrics=[],
                aggregate_products=[],
                order_groups=[],
                package_plan=_empty_package_plan(),
                footer_note="等待读取 ERP 当前序号 1 订单",
            )
        )

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=MACOS_THEME["titlebar_bg"], height=46)
        header.pack(fill="x")
        header.pack_propagate(False)
        header.bind("<ButtonPress-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        close_btn = tk.Label(
            header,
            text=MACOS_THEME["close_text"],
            bg=MACOS_THEME["close"],
            fg="#7a1f1b",
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
            width=2,
            height=1,
        )
        close_btn.bind("<Button-1>", lambda _event: self.close())
        close_btn.bind(
            "<Enter>",
            lambda _event: close_btn.configure(
                bg=MACOS_THEME["close_pressed"], fg="#ffffff"
            ),
        )
        close_btn.bind(
            "<Leave>",
            lambda _event: close_btn.configure(
                bg=MACOS_THEME["close"], fg="#7a1f1b"
            ),
        )
        close_btn.pack(side="left", padx=(12, 8), pady=12)

        tk.Label(
            header,
            text="审单 · 订单结构",
            bg=MACOS_THEME["titlebar_bg"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 13, "bold"),
            anchor="w",
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            header,
            text=MACOS_THEME["refresh_text"],
            command=self.refresh,
            bg=MACOS_THEME["accent_soft"],
            fg=MACOS_THEME["primary_text"],
            activebackground=MACOS_THEME["accent_border"],
            activeforeground=MACOS_THEME["primary_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=7,
            pady=2,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=12, pady=8)

    def _build_overview(self) -> None:
        self.overview = tk.Frame(
            self.root,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
        )
        self.overview.pack(fill="x")

        self.status = tk.StringVar(value="")
        status_row = tk.Frame(self.overview, bg=MACOS_THEME["surface"])
        status_row.pack(fill="x", padx=12, pady=(10, 7))
        tk.Label(
            status_row,
            text="●",
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["success"],
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left", padx=(0, 6))
        self._selectable_entry(
            status_row,
            variable=self.status,
            background=MACOS_THEME["surface"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 12, "bold"),
        ).pack(side="left", fill="x", expand=True)

        self.metrics_frame = tk.Frame(self.overview, bg=MACOS_THEME["surface"])
        self.metrics_frame.pack(fill="x", padx=10, pady=(0, 8))

    def _build_scroll_area(self) -> None:
        frame = tk.Frame(self.root, bg=MACOS_THEME["window_bg"])
        frame.pack(fill="both", expand=True, padx=9, pady=(8, 8))
        self.canvas = tk.Canvas(
            frame,
            bg=MACOS_THEME["window_bg"],
            highlightthickness=0,
        )
        self.content_frame = tk.Frame(self.canvas, bg=MACOS_THEME["window_bg"])
        self.content_window = self.canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        scrollbar = ttk.Scrollbar(frame, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.content_frame.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_canvas_width)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _run_initial_refresh(self) -> None:
        self._initial_refresh_job = None
        self.refresh()

    def refresh(self) -> None:
        if self._initial_refresh_job is not None:
            try:
                self.root.after_cancel(self._initial_refresh_job)
            except tk.TclError:
                pass
            self._initial_refresh_job = None
        try:
            snapshot = self.reader()
            self.current_snapshot = snapshot
            self.package_workflow.load_order(snapshot)
            self._active_package_id = None
            self._package_feedback = self.package_workflow.recommendation_error
            self._render_view(build_sidebar_view(snapshot))
        except Exception as exc:
            self.current_snapshot = None
            self.package_workflow.clear_order()
            self._active_package_id = None
            self._package_feedback = ""
            self._render_view(
                SidebarView(
                    status="判断：读取失败",
                    metrics=[],
                    aggregate_products=[],
                    order_groups=[],
                    package_plan=_empty_package_plan(),
                    footer_note=str(exc),
                )
            )

    def _render_lines(self, lines: list[str]) -> None:
        self._render_view(
            SidebarView(
                status=lines[0] if lines else "判断：待人工确认",
                metrics=[],
                aggregate_products=[],
                order_groups=[],
                package_plan=_empty_package_plan(),
                footer_note="\n".join(lines[1:]),
            )
        )

    def _render_view(self, view: SidebarView, *, reset_scroll: bool = True) -> None:
        self._cancel_quantity_commit_jobs()
        self._current_view = view
        self.status.set(view.status)
        self._render_metrics(view.metrics)

        for child in self.content_frame.winfo_children():
            child.destroy()

        if view.aggregate_products:
            aggregate_quantity = sum(product.quantity for product in view.aggregate_products)
            self._render_collapsible_section_label(
                "商品总量",
                f"{len(view.aggregate_products)} 种 · {aggregate_quantity} 件",
                expanded=self._aggregate_expanded,
                command=lambda: self._toggle_section("aggregate"),
            )
            if self._aggregate_expanded:
                self._render_product_card(
                    products=view.aggregate_products,
                    background=MACOS_THEME["accent_soft"],
                    border=MACOS_THEME["accent_border"],
                    quantity_color=MACOS_THEME["accent"],
                )

        if view.order_groups:
            order_kind_count = sum(group.kind_count for group in view.order_groups)
            order_quantity = sum(group.total_quantity for group in view.order_groups)
            self._render_collapsible_section_label(
                "按订单查看",
                f"{len(view.order_groups)} 组 · {order_kind_count} 种 · {order_quantity} 件",
                expanded=self._orders_expanded,
                command=lambda: self._toggle_section("orders"),
            )
            if self._orders_expanded:
                for index, group in enumerate(view.order_groups):
                    self._render_order_group(index, group)

        if view.package_plan.status:
            self._render_package_workspace(view.package_plan)

        if view.backend_details.summary:
            self._render_collapsible_section_label(
                "后台明细",
                view.backend_details.summary,
                expanded=self._backend_expanded,
                command=lambda: self._toggle_section("backend"),
            )
            if self._backend_expanded:
                self._render_backend_details(view.backend_details)

        if view.footer_note:
            self._selectable_text(
                self.content_frame,
                view.footer_note,
                background=MACOS_THEME["window_bg"],
                foreground=MACOS_THEME["muted_text"],
                font=(FONT_FAMILY, 9),
                wrap_chars=42,
            ).pack(fill="x", padx=4, pady=(4, 8))

        if reset_scroll:
            self.canvas.yview_moveto(0)

    def _toggle_section(self, section: str) -> None:
        if section == "aggregate":
            self._aggregate_expanded = not self._aggregate_expanded
        elif section == "orders":
            self._orders_expanded = not self._orders_expanded
        elif section == "backend":
            self._backend_expanded = not self._backend_expanded
        if self._current_view is not None:
            scroll_position = self.canvas.yview()[0]
            self._render_view(self._current_view, reset_scroll=False)
            self.root.update_idletasks()
            self.canvas.yview_moveto(scroll_position)

    def _render_metrics(self, metrics: list[MetricView]) -> None:
        for child in self.metrics_frame.winfo_children():
            child.destroy()
        if not metrics:
            self.metrics_frame.pack_forget()
            return
        self.metrics_frame.pack(fill="x", padx=10, pady=(0, 8))
        for index, metric in enumerate(metrics):
            card = tk.Frame(
                self.metrics_frame,
                bg=MACOS_THEME["surface_soft"],
                padx=7,
                pady=6,
            )
            card.grid(row=0, column=index, sticky="nsew", padx=2)
            self.metrics_frame.grid_columnconfigure(index, weight=1)
            tk.Label(
                card,
                text=metric.value,
                bg=MACOS_THEME["surface_soft"],
                fg=MACOS_THEME["primary_text"],
                font=(FONT_FAMILY, 15, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                card,
                text=metric.label,
                bg=MACOS_THEME["surface_soft"],
                fg=MACOS_THEME["muted_text"],
                font=(FONT_FAMILY, 9),
                anchor="w",
            ).pack(fill="x", pady=(2, 0))

    def _render_collapsible_section_label(
        self,
        title: str,
        hint: str,
        *,
        expanded: bool,
        command: Callable[[], None],
    ) -> None:
        row = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            cursor="hand2",
        )
        row.pack(fill="x", pady=(1, 7))
        chevron = tk.Label(
            row,
            text="▾" if expanded else "▸",
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["accent"],
            font=(FONT_FAMILY, 11, "bold"),
            width=2,
            cursor="hand2",
        )
        chevron.pack(side="left", padx=(7, 2), pady=7)
        title_label = tk.Label(
            row,
            text=title,
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
            cursor="hand2",
        )
        title_label.pack(side="left", fill="x", expand=True, pady=7)
        hint_label = tk.Label(
            row,
            text=hint,
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 9),
            anchor="e",
            cursor="hand2",
        )
        hint_label.pack(side="right", padx=(5, 9), pady=7)
        for widget in (row, chevron, title_label, hint_label):
            widget.bind("<Button-1>", lambda _event, callback=command: callback())

    def _selectable_entry(
        self,
        parent: tk.Misc,
        *,
        variable: tk.StringVar,
        background: str,
        fg: str,
        font: tuple,
    ) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            state="readonly",
            readonlybackground=background,
            fg=fg,
            font=font,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            takefocus=True,
            cursor="xterm",
        )
        entry.bind("<Button-2>", lambda event: self._show_copy_menu(event.widget, event))
        entry.bind("<Button-3>", lambda event: self._show_copy_menu(event.widget, event))
        return entry

    def _selectable_text(
        self,
        parent: tk.Misc,
        text: str,
        *,
        background: str,
        foreground: str,
        font: tuple,
        wrap_chars: int = 32,
        height: int | None = None,
        wrap_mode: str = "word",
    ) -> tk.Text:
        if height is None:
            height = sum(
                max(1, (len(line) + wrap_chars - 1) // wrap_chars)
                for line in (text.splitlines() or [""])
            )
        widget = tk.Text(
            parent,
            height=max(1, height),
            width=1,
            wrap=wrap_mode,
            bg=background,
            fg=foreground,
            font=font,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="xterm",
            takefocus=True,
            exportselection=False,
            selectbackground=MACOS_THEME["accent_border"],
            selectforeground=MACOS_THEME["primary_text"],
        )
        widget.insert("1.0", text)
        widget.configure(state="disabled")
        widget.bind("<Button-1>", lambda event: event.widget.focus_set())
        widget.bind("<Command-c>", self._copy_text_selection)
        widget.bind("<Control-c>", self._copy_text_selection)
        widget.bind("<Command-a>", self._select_all_text)
        widget.bind("<Control-a>", self._select_all_text)
        widget.bind("<Button-2>", lambda event: self._show_copy_menu(event.widget, event))
        widget.bind("<Button-3>", lambda event: self._show_copy_menu(event.widget, event))
        return widget

    def _copy_text_selection(self, event: tk.Event) -> str:
        widget = event.widget
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        return "break"

    def _select_all_text(self, event: tk.Event) -> str:
        widget = event.widget
        widget.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _show_copy_menu(self, widget: tk.Misc, event: tk.Event) -> str:
        menu = tk.Menu(self.root, tearoff=False)
        if isinstance(widget, tk.Text):
            menu.add_command(
                label="复制所选内容",
                command=lambda: self._copy_text_selection(
                    type("CopyEvent", (), {"widget": widget})()
                ),
            )
            menu.add_command(
                label="全选",
                command=lambda: widget.tag_add("sel", "1.0", "end-1c"),
            )
        elif isinstance(widget, tk.Entry):
            menu.add_command(label="复制", command=lambda: widget.event_generate("<<Copy>>"))
            menu.add_command(label="全选", command=lambda: widget.selection_range(0, "end"))
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _render_backend_details(self, details: BackendDetailsView) -> None:
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface_soft"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            padx=9,
            pady=7,
        )
        card.pack(fill="x", pady=(0, 9))
        if not details.lines:
            tk.Label(
                card,
                text="当前仅读取到订单行基础信息。展开订单后会同步商品与分组明细。",
                bg=MACOS_THEME["surface_soft"],
                fg=MACOS_THEME["muted_text"],
                font=(FONT_FAMILY, 9),
                anchor="w",
                justify="left",
                wraplength=295,
            ).pack(fill="x")
            return
        self._selectable_text(
            card,
            "\n".join(details.lines),
            background=MACOS_THEME["surface_soft"],
            foreground=MACOS_THEME["secondary_text"],
            font=(FONT_FAMILY, 9),
            wrap_chars=38,
        ).pack(fill="x")

    def _render_product_card(
        self,
        *,
        products: list[ProductRowView],
        background: str,
        border: str,
        quantity_color: str,
    ) -> None:
        card = tk.Frame(
            self.content_frame,
            bg=background,
            highlightbackground=border,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 9))
        self._render_product_rows(
            card,
            products,
            background=background,
            quantity_color=quantity_color,
        )

    def _render_product_rows(
        self,
        parent: tk.Misc,
        products: list[ProductRowView],
        *,
        background: str,
        quantity_color: str,
    ) -> None:
        for product_index, product in enumerate(products):
            row = tk.Frame(parent, bg=background)
            row.pack(fill="x")
            self._selectable_text(
                row,
                product.title,
                background=background,
                foreground=MACOS_THEME["primary_text"],
                font=(FONT_FAMILY, 11),
                wrap_chars=28,
            ).pack(side="left", fill="x", expand=True, padx=(11, 5), pady=7)
            tk.Label(
                row,
                text=f"×{product.quantity}",
                bg=background,
                fg=quantity_color,
                font=(FONT_FAMILY, 14, "bold"),
                anchor="e",
                width=4,
            ).pack(side="right", padx=(0, 9), pady=6)
            if product_index < len(products) - 1:
                tk.Frame(parent, bg=MACOS_THEME["divider"], height=1).pack(
                    fill="x", padx=(10, 0)
                )

    def _render_order_group(self, index: int, group: OrderGroupView) -> None:
        outer = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
        )
        outer.pack(fill="x", pady=(0, 8))

        rail = tk.Frame(outer, bg=MACOS_THEME["accent"], width=3)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        body = tk.Frame(outer, bg=MACOS_THEME["surface"])
        body.pack(side="left", fill="both", expand=True)

        header = tk.Frame(body, bg="#fbfbfc")
        header.pack(fill="x")
        marker = chr(ord("A") + index) if index < 26 else str(index + 1)
        tk.Label(
            header,
            text=marker,
            bg=MACOS_THEME["accent"],
            fg="#ffffff",
            font=(FONT_FAMILY, 9, "bold"),
            width=2,
            pady=2,
        ).pack(side="left", padx=(9, 6), pady=6)
        order_title = (
            "、".join(group.platform_order_numbers)
            if group.platform_order_numbers
            else group.label
        )
        self._selectable_text(
            header,
            order_title,
            background="#fbfbfc",
            foreground=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 11, "bold"),
            wrap_chars=24,
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            header,
            text=f"{group.kind_count} 种 · {group.total_quantity} 件",
            bg="#fbfbfc",
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 9),
            anchor="e",
        ).pack(side="right", padx=9)
        if group.relation_hint:
            tk.Label(
                header,
                text=group.relation_hint,
                bg=MACOS_THEME["accent_border"],
                fg=MACOS_THEME["accent"],
                font=(FONT_FAMILY, 8, "bold"),
                padx=6,
                pady=2,
            ).pack(side="right", padx=(3, 0), pady=6)

        self._render_product_rows(
            body,
            group.products,
            background=MACOS_THEME["surface"],
            quantity_color=MACOS_THEME["primary_text"],
        )

    def _render_package_workspace(self, placeholder: PackagePlanView) -> None:
        workflow = self.package_workflow
        source = workflow.source_snapshot
        if source is None or not source.products:
            self._render_package_plan_placeholder(placeholder)
            return

        status = "待选择"
        if workflow.freight_pending:
            status = "待确认物流"
        elif workflow.draft is not None:
            status = "编辑中"
        elif workflow.historical_case is not None and workflow.historical_case.is_freight:
            status = "已保存物流"
        elif workflow.confirmed_case is not None and workflow.confirmed_case.is_freight:
            status = "已确认物流"
        elif workflow.historical_plan is not None:
            status = "已保存方案"
        elif workflow.confirmed_plan is not None:
            status = "已确认"
        elif workflow.freight_reminder is not None:
            status = "建议复核物流"
        self._render_package_heading(status)

        if workflow.freight_pending:
            self._render_freight_confirmation()
            return

        if workflow.draft is not None:
            self._render_package_draft()
            return

        if workflow.historical_case is not None and workflow.historical_case.is_freight:
            self._render_saved_freight(workflow.historical_case)
            return

        if workflow.historical_plan is not None and workflow.historical_case is not None:
            self._render_readonly_package_plan(workflow.historical_plan)
            historical = workflow.historical_case
            self._render_package_notice(
                workflow.load_notice
                or (
                    "该订单已经保存过包裹方案。"
                    f"案例编号：{historical.case_id.removeprefix('case-')[:8]}。"
                ),
                tone="success",
            )
            self._action_button(
                self.content_frame,
                "修改已保存方案",
                lambda: self._package_action(self._edit_historical_plan),
                accented=True,
            ).pack(fill="x", pady=(0, 8))
            return

        if workflow.confirmed_case is not None and workflow.confirmed_case.is_freight:
            self._render_saved_freight(workflow.confirmed_case)
            return

        if workflow.confirmed_plan is not None:
            self._render_readonly_package_plan(workflow.confirmed_plan)
            self._render_package_notice(
                f"{workflow.confirmation_note} 未操作 ERP。",
                tone="success",
            )
            return

        if workflow.freight_reminder is not None:
            self._render_package_notice(
                workflow.freight_reminder.message,
                tone="warning",
            )
        self._render_recommendations()
        self._render_package_entry_actions()
        if self._package_feedback:
            self._render_package_notice(self._package_feedback, tone="warning")

    def _render_readonly_package_plan(self, plan) -> None:
        source = self.package_workflow.source_snapshot
        names = (
            {item.source_product_id: item.display_name for item in source.products}
            if source is not None
            else {}
        )
        for index, package in enumerate(plan.packages):
            products = [
                ProductRowView(
                    title=names.get(item.source_product_id, item.product_name),
                    quantity=item.quantity,
                )
                for item in package.items
            ]
            self._render_package(
                index,
                PackageView(
                    label=f"包裹 {index + 1}",
                    kind_count=len(products),
                    total_quantity=sum(item.quantity for item in products),
                    products=products,
                ),
            )

    def _render_freight_confirmation(self) -> None:
        source = self.package_workflow.source_snapshot
        if source is None:
            return
        kind_count = len({product.match_key for product in source.products})
        self._render_package_notice(
            (
                f"当前订单共 {source.total_quantity} 件、{kind_count} 种商品。"
                "确认后将保存为“物流发货”，不参与普通单包推荐，也不会操作 ERP。"
            ),
            tone="warning",
        )
        actions = tk.Frame(self.content_frame, bg=MACOS_THEME["window_bg"])
        actions.pack(fill="x", pady=(0, 8))
        self._action_button(
            actions,
            "取消",
            lambda: self._package_action(self._cancel_package_plan),
            compact=True,
        ).pack(side="left")
        self._action_button(
            actions,
            "确认物流发货",
            lambda: self._package_action(self._confirm_freight),
            primary=True,
        ).pack(side="right")

    def _render_saved_freight(self, case) -> None:
        band = case.decision.estimated_package_band
        band_text = f" · 人工估计 {band} 个快递包裹" if band else ""
        self._render_package_notice(
            (
                f"该订单已标记为物流发货{band_text}。"
                "不会参与普通单包推荐，ERP 物流操作尚未执行。"
            ),
            tone="success",
        )

    def _render_package_heading(self, status: str) -> None:
        label_row = tk.Frame(self.content_frame, bg=MACOS_THEME["window_bg"])
        label_row.pack(fill="x", padx=3, pady=(4, 7))
        tk.Label(
            label_row,
            text="包裹方案",
            bg=MACOS_THEME["window_bg"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(side="left")
        tk.Label(
            label_row,
            text=status,
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["package"],
            font=(FONT_FAMILY, 9, "bold"),
            padx=7,
            pady=2,
        ).pack(side="right")

    def _render_package_plan_placeholder(self, plan: PackagePlanView) -> None:
        self._render_package_heading(plan.status)
        if plan.packages:
            for index, package in enumerate(plan.packages):
                self._render_package(index, package)
        else:
            empty = tk.Frame(
                self.content_frame,
                bg=MACOS_THEME["warning_soft"],
                highlightbackground="#ead8b9",
                highlightthickness=1,
                padx=10,
                pady=9,
            )
            empty.pack(fill="x", pady=(0, 8))
            tk.Label(
                empty,
                text="尚未生成拆分方案",
                bg=MACOS_THEME["warning_soft"],
                fg=MACOS_THEME["primary_text"],
                font=(FONT_FAMILY, 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                empty,
                text=(
                    f"{plan.unassigned_kind_count} 种商品 · "
                    f"{plan.unassigned_quantity} 件待分配"
                ),
                bg=MACOS_THEME["warning_soft"],
                fg=MACOS_THEME["warning"],
                font=(FONT_FAMILY, 11, "bold"),
                anchor="w",
            ).pack(fill="x", pady=(5, 0))
            if plan.note:
                self._selectable_text(
                    empty,
                    plan.note,
                    background=MACOS_THEME["warning_soft"],
                    foreground=MACOS_THEME["secondary_text"],
                    font=(FONT_FAMILY, 9),
                    wrap_chars=40,
                ).pack(fill="x", pady=(5, 0))

    def _render_recommendations(self) -> None:
        result = self.package_workflow.recommendations
        if not result.candidates:
            return
        has_capacity_candidate = any(
            candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY
            for candidate in result.candidates
        )
        if result.conflict:
            self._render_package_notice(
                "历史中存在不同拆分方案，请人工比较后选择；系统不会自动采用。",
                tone="warning",
            )
        elif has_capacity_candidate:
            self._render_package_notice(
                "找到数量不超过历史已确认容量的单包案例；请核对差异后决定是否采用。",
                tone="info",
            )
        else:
            self._render_package_notice(
                "找到完全相同商品组合的历史方案，可采用后再确认。",
                tone="info",
            )

        for candidate_index, candidate in enumerate(result.candidates, start=1):
            card = tk.Frame(
                self.content_frame,
                bg=MACOS_THEME["surface"],
                highlightbackground=MACOS_THEME["border"],
                highlightthickness=1,
                padx=9,
                pady=8,
            )
            card.pack(fill="x", pady=(0, 8))
            header = tk.Frame(card, bg=MACOS_THEME["surface"])
            header.pack(fill="x")
            tk.Label(
                header,
                text=f"候选 {candidate_index} · {len(candidate.packages)} 个包裹",
                bg=MACOS_THEME["surface"],
                fg=MACOS_THEME["primary_text"],
                font=(FONT_FAMILY, 10, "bold"),
            ).pack(side="left")
            tk.Label(
                header,
                text=f"历史使用 {candidate.usage_count} 次",
                bg=MACOS_THEME["surface"],
                fg=MACOS_THEME["package"],
                font=(FONT_FAMILY, 9, "bold"),
            ).pack(side="right")

            for package_index, package in enumerate(candidate.packages, start=1):
                summary = " + ".join(
                    f"{item.product_name} ×{item.quantity}" for item in package.items
                )
                self._selectable_text(
                    card,
                    f"包裹 {package_index}：{summary}",
                    background=MACOS_THEME["surface"],
                    foreground=MACOS_THEME["secondary_text"],
                    font=(FONT_FAMILY, 9),
                    wrap_chars=38,
                ).pack(fill="x", pady=(5, 0))
            if candidate.quantity_note:
                self._selectable_text(
                    card,
                    candidate.quantity_note,
                    background=MACOS_THEME["surface"],
                    foreground=MACOS_THEME["warning"],
                    font=(FONT_FAMILY, 9),
                    wrap_chars=40,
                ).pack(fill="x", pady=(6, 0))
            source_labels = "、".join(
                case_id.removeprefix("case-")[:8]
                for case_id in candidate.source_case_ids
            )
            self._selectable_text(
                card,
                f"来源案例：{source_labels} · 推荐算法 v{candidate.algorithm_version}",
                background=MACOS_THEME["surface"],
                foreground=MACOS_THEME["muted_text"],
                font=(FONT_FAMILY, 8),
                wrap_chars=42,
            ).pack(fill="x", pady=(6, 5))
            self._action_button(
                card,
                "采用此方案",
                lambda recommendation_id=candidate.recommendation_id: self._package_action(
                    lambda: self._adopt_recommendation(recommendation_id)
                ),
                primary=True,
            ).pack(fill="x")

    def _render_package_entry_actions(self) -> None:
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["package_soft"],
            highlightbackground="#ded4f1",
            highlightthickness=1,
            padx=9,
            pady=9,
        )
        card.pack(fill="x", pady=(0, 8))
        tk.Label(
            card,
            text="创建人工方案",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 7))
        row = tk.Frame(card, bg=MACOS_THEME["package_soft"])
        row.pack(fill="x")
        self._action_button(
            row,
            "单包方案",
            lambda: self._package_action(self._start_single_package),
            accented=True,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._action_button(
            row,
            "拆分包裹",
            lambda: self._package_action(self._start_split),
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        self._action_button(
            card,
            "物流发货",
            lambda: self._package_action(self._start_freight),
            danger=True,
        ).pack(fill="x", pady=(8, 0))
        tk.Label(
            card,
            text="仅创建本地决策记录，不会审核、拆单或修改 ERP。",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(7, 0))

    def _render_package_draft(self) -> None:
        workflow = self.package_workflow
        source = workflow.source_snapshot
        draft = workflow.draft
        if source is None or draft is None:
            return

        package_ids = {package.package_id for package in draft.packages}
        if self._active_package_id not in package_ids:
            self._active_package_id = draft.packages[-1].package_id

        remaining_total = workflow.remaining_quantity
        remaining_kinds = sum(
            1 for item in source.products if draft.remaining_quantity(item) > 0
        )
        self._render_unassigned_pool(remaining_kinds, remaining_total)

        for package_index, package in enumerate(draft.packages, start=1):
            if package.package_id == self._active_package_id:
                self._render_active_package_editor(
                    package_index, package, source, draft
                )
            else:
                self._render_collapsed_draft_package(package_index, package)

        actions = tk.Frame(self.content_frame, bg=MACOS_THEME["window_bg"])
        actions.pack(fill="x", pady=(0, 5))
        active_package = next(
            (
                package
                for package in draft.packages
                if package.package_id == self._active_package_id
            ),
            None,
        )
        can_add_next = (
            workflow.can_add_package
            and active_package is not None
            and bool(active_package.items)
        )
        self._action_button(
            actions,
            "新增下一个包裹",
            lambda: self._package_action(self._add_next_package),
            compact=True,
            enabled=can_add_next,
        ).pack(side="left", padx=(0, 4))
        self._action_button(
            actions,
            "恢复初始方案",
            lambda: self._package_action(self._reset_package_plan),
            compact=True,
        ).pack(side="left", padx=4)
        self._action_button(
            actions,
            "取消",
            lambda: self._package_action(self._cancel_package_plan),
            compact=True,
        ).pack(side="left", padx=4)
        self._action_button(
            actions,
            "确认方案",
            lambda: self._package_action(self._confirm_package_plan),
            primary=True,
            compact=True,
        ).pack(side="right")
        if workflow.can_add_package and active_package is not None and not active_package.items:
            tk.Label(
                self.content_frame,
                text="先给当前包裹分配商品，再新增下一个包裹。",
                bg=MACOS_THEME["window_bg"],
                fg=MACOS_THEME["muted_text"],
                font=(FONT_FAMILY, 8),
                anchor="w",
                justify="left",
                wraplength=300,
            ).pack(fill="x", padx=3, pady=(0, 6))
        if workflow.load_notice:
            self._render_package_notice(workflow.load_notice, tone="info")
        if self._package_feedback:
            self._render_package_notice(self._package_feedback, tone="warning")

    def _render_collapsed_draft_package(self, package_index: int, package) -> None:
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            padx=9,
            pady=7,
        )
        card.pack(fill="x", pady=(0, 6))
        header = tk.Frame(card, bg=MACOS_THEME["surface"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"包裹 {package_index}",
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="left")
        self._action_button(
            header,
            "编辑",
            lambda package_id=package.package_id: self._activate_package(package_id),
            compact=True,
        ).pack(side="right")
        tk.Label(
            header,
            text=f"{len(package.items)} 种 · {package.total_quantity} 件",
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 8),
        ).pack(side="right", padx=7)
        summary = " · ".join(
            f"{item.product_name} ×{item.quantity}" for item in package.items
        ) or "尚未分配"
        self._selectable_text(
            card,
            summary,
            background=MACOS_THEME["surface"],
            foreground=MACOS_THEME["secondary_text"],
            font=(FONT_FAMILY, 8),
            wrap_chars=42,
        ).pack(fill="x", pady=(5, 0))

    def _render_active_package_editor(
        self, package_index: int, package, source, draft
    ) -> None:
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["package"],
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 8))
        header = tk.Frame(card, bg=MACOS_THEME["package_soft"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"包裹 {package_index}",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
        ).pack(side="left", padx=9, pady=6)
        tk.Label(
            header,
            text="正在编辑",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["package"],
            font=(FONT_FAMILY, 8, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=f"{package.total_quantity} 件",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["package"],
            font=(FONT_FAMILY, 9, "bold"),
        ).pack(side="right", padx=8)
        if not package.items and len(draft.packages) > 1:
            self._action_button(
                header,
                "删除空包裹",
                lambda package_id=package.package_id: self._package_action(
                    lambda: self._delete_package(package_id)
                ),
                compact=True,
                danger=True,
            ).pack(side="right", padx=4, pady=3)

        quantities = {item.source_product_id: item.quantity for item in package.items}
        candidates = [
            product
            for product in source.products
            if quantities.get(product.source_product_id, 0) > 0
            or draft.remaining_quantity(product) > 0
        ]
        for product_index, product in enumerate(candidates):
            if product_index:
                tk.Frame(card, bg=MACOS_THEME["divider"], height=1).pack(
                    fill="x", padx=9
                )
            current = quantities.get(product.source_product_id, 0)
            maximum = current + draft.remaining_quantity(product)
            self._render_package_quantity_row(
                card, package.package_id, product, current, maximum
            )

    def _render_package_quantity_row(
        self, parent: tk.Misc, package_id: str, product, current: int, maximum: int
    ) -> None:
        row = tk.Frame(parent, bg=MACOS_THEME["surface"])
        row.pack(fill="x", padx=9, pady=6)
        product_info = tk.Frame(row, bg=MACOS_THEME["surface"])
        product_info.pack(side="left", fill="x", expand=True)
        self._selectable_text(
            product_info,
            product.display_name,
            background=MACOS_THEME["surface"],
            foreground=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 9, "bold"),
            wrap_chars=15,
        ).pack(fill="x")
        self._selectable_text(
            product_info,
            f"本包 {current} · 最多 {maximum}",
            background=MACOS_THEME["surface"],
            foreground=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 8),
            height=1,
        ).pack(fill="x", pady=(2, 0))

        self._micro_button(
            row,
            "−",
            lambda: self._package_action(
                lambda: self._set_package_quantity(
                    package_id, product.source_product_id, current - 1
                )
            ),
            enabled=current > 0,
        ).pack(side="left", padx=2)
        quantity_var = tk.StringVar(value=str(current))
        quantity_entry = tk.Entry(
            row,
            textvariable=quantity_var,
            bg="#ffffff",
            fg=MACOS_THEME["primary_text"],
            insertbackground=MACOS_THEME["primary_text"],
            selectbackground=MACOS_THEME["accent_border"],
            selectforeground=MACOS_THEME["primary_text"],
            justify="center",
            width=4,
            font=(FONT_FAMILY, 10, "bold"),
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
        )
        quantity_entry.pack(side="left", padx=2, ipady=1)
        quantity_entry.bind(
            "<KeyRelease>",
            lambda _event: self._schedule_quantity_commit(
                package_id,
                product.source_product_id,
                quantity_var,
                maximum,
                current,
            ),
        )
        quantity_entry.bind(
            "<Return>",
            lambda _event: self._commit_package_quantity(
                package_id,
                product.source_product_id,
                quantity_var,
                maximum,
                current,
            ),
        )
        self._micro_button(
            row,
            "+",
            lambda: self._package_action(
                lambda: self._set_package_quantity(
                    package_id, product.source_product_id, current + 1
                )
            ),
            enabled=current < maximum,
        ).pack(side="left", padx=2)
        self._micro_button(
            row,
            "MAX",
            lambda: self._package_action(
                lambda: self._set_package_quantity(
                    package_id, product.source_product_id, maximum
                )
            ),
            enabled=current < maximum,
            width=34,
        ).pack(side="left", padx=(2, 0))

    def _confirm_package_plan(self) -> None:
        self.package_workflow.confirm()
        self._package_feedback = self.package_workflow.confirmation_note

    def _confirm_freight(self) -> None:
        self.package_workflow.confirm_freight()
        self._package_feedback = self.package_workflow.confirmation_note

    def _edit_historical_plan(self) -> None:
        self.package_workflow.edit_historical_plan()
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_single_package(self) -> None:
        self.package_workflow.start_single_package()
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_split(self) -> None:
        self.package_workflow.start_split()
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_freight(self) -> None:
        self.package_workflow.start_freight()
        self._active_package_id = None

    def _adopt_recommendation(self, recommendation_id: str) -> None:
        self.package_workflow.adopt_recommendation(recommendation_id)
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _activate_package(self, package_id: str) -> None:
        self._active_package_id = package_id
        self._package_feedback = ""
        self._rerender_current_snapshot()

    def _add_next_package(self) -> None:
        self.package_workflow.add_package()
        self._active_package_id = self.package_workflow.draft.packages[-1].package_id

    def _delete_package(self, package_id: str) -> None:
        self.package_workflow.remove_package(package_id)
        self._active_package_id = self.package_workflow.draft.packages[-1].package_id

    def _reset_package_plan(self) -> None:
        self.package_workflow.reset()
        package_ids = [
            package.package_id for package in self.package_workflow.draft.packages
        ]
        if self._active_package_id not in package_ids:
            self._active_package_id = package_ids[0]

    def _cancel_package_plan(self) -> None:
        self.package_workflow.cancel()
        self._active_package_id = None

    def _set_package_quantity(
        self, package_id: str, source_product_id: str, quantity: int
    ) -> None:
        source = self.package_workflow.source_snapshot
        draft = self.package_workflow.draft
        previous = 0
        product_name = "商品"
        if source is not None:
            product = source.product_by_id.get(source_product_id)
            if product is not None:
                product_name = product.display_name
        if draft is not None:
            package = next(
                (item for item in draft.packages if item.package_id == package_id),
                None,
            )
            if package is not None:
                previous = next(
                    (
                        item.quantity
                        for item in package.items
                        if item.source_product_id == source_product_id
                    ),
                    0,
                )
        self.package_workflow.set_quantity(package_id, source_product_id, quantity)
        difference = abs(quantity - previous)
        if difference == 0:
            self._package_feedback = f"{product_name}：数量未变化"
            return
        action = "已退回待分配区" if quantity < previous else "已放入当前包裹"
        self._package_feedback = f"{product_name}：{action} {difference} 件"

    def _commit_package_quantity(
        self,
        package_id: str,
        source_product_id: str,
        variable: tk.StringVar,
        maximum: int,
        current: int,
    ) -> str:
        def apply() -> None:
            raw_value = variable.get().strip()
            if not raw_value:
                return
            if not raw_value.isdigit():
                raise PackagePlanValidationError(
                    f"请输入 0 到 {maximum} 之间的整数"
                )
            quantity = int(raw_value)
            if quantity > maximum:
                raise PackagePlanValidationError(
                    f"当前包裹最多可设置为 {maximum} 件"
                )
            if quantity == current:
                return
            self._set_package_quantity(package_id, source_product_id, quantity)

        self._package_action(apply)
        return "break"

    def _schedule_quantity_commit(
        self,
        package_id: str,
        source_product_id: str,
        variable: tk.StringVar,
        maximum: int,
        current: int,
    ) -> None:
        key = (package_id, source_product_id)
        previous_job = self._quantity_commit_jobs.pop(key, None)
        if previous_job is not None:
            try:
                self.root.after_cancel(previous_job)
            except tk.TclError:
                pass

        def commit() -> None:
            self._quantity_commit_jobs.pop(key, None)
            self._commit_package_quantity(
                package_id,
                source_product_id,
                variable,
                maximum,
                current,
            )

        self._quantity_commit_jobs[key] = self.root.after(450, commit)

    def _cancel_quantity_commit_jobs(self) -> None:
        for job_id in self._quantity_commit_jobs.values():
            try:
                self.root.after_cancel(job_id)
            except tk.TclError:
                pass
        self._quantity_commit_jobs.clear()

    def _package_action(self, action: Callable[[], None]) -> None:
        self._package_feedback = ""
        try:
            action()
        except Exception as exc:
            self._package_feedback = str(exc)
        self._rerender_current_snapshot()

    def _rerender_current_snapshot(self) -> None:
        if self.current_snapshot is None:
            return
        scroll_position = self.canvas.yview()[0]
        self._render_view(build_sidebar_view(self.current_snapshot), reset_scroll=False)
        self.root.update_idletasks()
        self.canvas.yview_moveto(scroll_position)

    def _render_unassigned_pool(self, kind_count: int, quantity: int) -> None:
        has_remaining = quantity > 0
        background = MACOS_THEME["warning_soft"] if has_remaining else "#eaf7f1"
        accent = MACOS_THEME["warning"] if has_remaining else MACOS_THEME["success"]
        card = tk.Frame(
            self.content_frame,
            bg=background,
            highlightbackground=accent,
            highlightthickness=1,
            padx=10,
            pady=9,
        )
        card.pack(fill="x", pady=(0, 8))
        tk.Label(
            card,
            text="待分配库存",
            bg=background,
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(side="left")
        tk.Label(
            card,
            text=(
                f"{kind_count} 种 · {quantity} 件"
                if has_remaining
                else "已全部分配"
            ),
            bg=background,
            fg=accent,
            font=(FONT_FAMILY, 11, "bold"),
            anchor="e",
        ).pack(side="right")

    def _render_package_notice(self, text: str, *, tone: str) -> None:
        palette = {
            "success": ("#eaf7f1", MACOS_THEME["success"]),
            "warning": (MACOS_THEME["warning_soft"], MACOS_THEME["warning"]),
            "info": (MACOS_THEME["package_soft"], MACOS_THEME["package"]),
        }
        background, foreground = palette[tone]
        self._selectable_text(
            self.content_frame,
            text,
            background=background,
            foreground=foreground,
            font=(FONT_FAMILY, 9),
            wrap_chars=28,
            wrap_mode="char",
        ).pack(fill="x", padx=9, pady=(7, 8))

    def _action_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        primary: bool = False,
        accented: bool = False,
        danger: bool = False,
        compact: bool = False,
        enabled: bool = True,
    ) -> tk.Button:
        if primary:
            background = "#ded5f1"
            foreground = "#2f2540"
            active_background = "#cec1e8"
            active_foreground = "#21182f"
        elif danger:
            background = "#f8e9e7"
            foreground = "#72342f"
            active_background = "#f0d8d5"
            active_foreground = "#5c2723"
        elif accented:
            background = "#e8e2f4"
            foreground = MACOS_THEME["primary_text"]
            active_background = "#d9cfed"
            active_foreground = MACOS_THEME["primary_text"]
        else:
            background = "#eef1f5"
            foreground = MACOS_THEME["primary_text"]
            active_background = "#e0e5eb"
            active_foreground = MACOS_THEME["primary_text"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=active_background,
            activeforeground=active_foreground,
            disabledforeground=MACOS_THEME["soft_text"],
            state="normal" if enabled else "disabled",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            font=(FONT_FAMILY, 8 if compact else 9, "bold"),
            padx=5 if compact else 7,
            pady=2 if compact else 4,
            cursor="hand2" if enabled else "arrow",
        )

    def _micro_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        enabled: bool,
        width: int = 24,
    ) -> tk.Frame:
        background = MACOS_THEME["surface_soft"] if enabled else "#f5f6f8"
        foreground = (
            MACOS_THEME["primary_text"] if enabled else MACOS_THEME["soft_text"]
        )
        control = tk.Frame(
            parent,
            width=width,
            height=24,
            bg=background,
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            cursor="hand2" if enabled else "arrow",
        )
        control.pack_propagate(False)
        label = tk.Label(
            control,
            text=text,
            bg=background,
            fg=foreground,
            font=(FONT_FAMILY, 7 if text == "MAX" else 11, "bold"),
            cursor="hand2" if enabled else "arrow",
        )
        label.pack(fill="both", expand=True)
        if enabled:
            def invoke(_event: tk.Event | None = None) -> None:
                command()

            def enter(_event: tk.Event) -> None:
                control.configure(bg="#e3e7ed")
                label.configure(bg="#e3e7ed")

            def leave(_event: tk.Event) -> None:
                control.configure(bg=background)
                label.configure(bg=background)

            for widget in (control, label):
                widget.bind("<Button-1>", invoke)
                widget.bind("<Enter>", enter)
                widget.bind("<Leave>", leave)
        return control

    def _render_package(self, index: int, package: PackageView) -> None:
        outer = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
        )
        outer.pack(fill="x", pady=(0, 8))

        rail = tk.Frame(outer, bg=MACOS_THEME["package"], width=3)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        body = tk.Frame(outer, bg=MACOS_THEME["surface"])
        body.pack(side="left", fill="both", expand=True)
        header = tk.Frame(body, bg=MACOS_THEME["package_soft"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=str(index + 1),
            bg=MACOS_THEME["package"],
            fg="#ffffff",
            font=(FONT_FAMILY, 9, "bold"),
            width=2,
            pady=2,
        ).pack(side="left", padx=(9, 6), pady=6)
        tk.Label(
            header,
            text=package.label,
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 11, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            header,
            text=f"{package.kind_count} 种 · {package.total_quantity} 件",
            bg=MACOS_THEME["package_soft"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 9),
            anchor="e",
        ).pack(side="right", padx=9)
        self._render_product_rows(
            body,
            package.products,
            background=MACOS_THEME["surface"],
            quantity_color=MACOS_THEME["package"],
        )

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_canvas_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.content_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _on_drag(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def close(self) -> None:
        self.package_workflow.close()
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    OrderReviewWindow(root)
    root.mainloop()
