from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Mapping

from .audit_runner import (
    SingleOrderAuditReport,
    run_single_order_audit,
)
from .case_repository import JsonCaseRepository
from .audit_probe import (
    AuditExecutionLogStore,
    default_audit_log_path,
)
from .erp_reader import (
    SequenceOneIdentityProbe,
    read_sequence_one_identity,
    read_sequence_one_order,
    read_sequence_one_order_if_matches,
    read_sequence_one_order_without_expand,
)
from .models import OrderSnapshot, Product
from .memory_diagnostics import MemoryDiagnostics
from .macos_companion import (
    MacOSCompanionWindow,
    companion_should_be_visible,
    get_frontmost_application,
)
from .package_plan import PackagePlanValidationError
from .package_workflow import PackagePlanWorkflow
from .recommendations import (
    MATCH_EXACT_STRUCTURE,
    MATCH_HISTORICAL_PACKAGE_COMPOSITION,
    MATCH_SINGLE_PACKAGE_CAPACITY,
    MATCH_SINGLE_PACKAGE_TOTAL,
)
from .rules import judge
from .split_dry_run import build_split_dry_run
from .split_runner import SplitOrderReport, run_mixed_order_split
from .window_position import (
    ChromeWindowState,
    get_chrome_window_bounds,
    get_chrome_window_state,
    panel_geometry_from_browser_bounds,
)


WINDOW_WIDTH = 360
WINDOW_HEIGHT = 760
WINDOW_GAP = 8
WINDOW_FOLLOW_INTERVAL_MS = 1500
WINDOW_FOLLOW_RESULT_POLL_MS = 100
COMPANION_VISIBILITY_INTERVAL_MS = 100
ORDER_WATCH_INTERVAL_MS = 500
ORDER_CHANGE_STABLE_OBSERVATIONS = 2
ORDER_CHANGE_STABLE_SECONDS = 0.5
POST_AUDIT_REFRESH_DELAY_SECONDS = 0.0
FONT_FAMILY = "Helvetica Neue"
FONT_SCALE_FACTOR = 1.1
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
        passive_reader: Callable[[], OrderSnapshot] = (
            read_sequence_one_order_without_expand
        ),
        repository: JsonCaseRepository | None = None,
        audit_executor: Callable[..., SingleOrderAuditReport] = run_single_order_audit,
        split_executor: Callable[..., SplitOrderReport] = run_mixed_order_split,
        order_identity_reader: Callable[[], SequenceOneIdentityProbe] = (
            read_sequence_one_identity
        ),
        auto_refresh_reader: Callable[[str], OrderSnapshot] = (
            read_sequence_one_order_if_matches
        ),
        monotonic: Callable[[], float] = time.monotonic,
        memory_diagnostics: MemoryDiagnostics | None = None,
    ) -> None:
        self.root = root
        self.reader = reader
        self.passive_reader = passive_reader
        current_scaling = float(self.root.tk.call("tk", "scaling"))
        self.root.tk.call("tk", "scaling", current_scaling * FONT_SCALE_FACTOR)
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
        self.audit_executor = audit_executor
        self.split_executor = split_executor
        self.order_identity_reader = order_identity_reader
        self.auto_refresh_reader = auto_refresh_reader
        self.monotonic = monotonic
        self.memory_diagnostics = memory_diagnostics
        self.audit_log_store = AuditExecutionLogStore(
            default_audit_log_path(self.package_workflow.repository.path)
        )
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._package_feedback = ""
        self._audit_feedback = ""
        self._audit_running = False
        self._audit_progress = ""
        self._audit_completed_system_order_id = ""
        self._split_completed_system_order_id = ""
        self._audit_thread: threading.Thread | None = None
        self._audit_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._audit_poll_job: str | None = None
        self._show_package_editor = False
        self._order_watch_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._order_watch_thread: threading.Thread | None = None
        self._order_watch_job: str | None = None
        self._order_watch_generation = 0
        self._order_change_candidate_id = ""
        self._order_change_candidate_count = 0
        self._order_change_candidate_since = 0.0
        self._auto_refresh_not_before = 0.0
        self._auto_refresh_enabled = False
        self._auto_refresh_paused = False
        self._auto_refresh_same_order_id = ""
        self._auto_refresh_attempted_order_ids: set[str] = set()
        self._active_package_id: str | None = None
        self._quantity_commit_jobs: dict[tuple[str, str], str] = {}
        self._last_browser_bounds: tuple[int, int, int, int] | None = None
        self._browser_minimized = False
        self._browser_was_hidden: bool | None = None
        self._native_companion = MacOSCompanionWindow("审单悬浮窗")
        self._browser_state_events: queue.Queue[ChromeWindowState | None] = (
            queue.Queue()
        )
        self._browser_state_thread: threading.Thread | None = None
        self._follow_browser_job: str | None = None
        self._companion_visibility_job: str | None = None
        self._build()
        self._initial_refresh_job: str | None = self.root.after(
            300, self._run_initial_refresh
        )
        self._follow_browser_job = self.root.after(
            WINDOW_FOLLOW_INTERVAL_MS,
            self._follow_browser_window,
        )
        self._companion_visibility_job = self.root.after(
            0,
            self._sync_companion_visibility,
        )
        self._order_watch_job = self.root.after(
            ORDER_WATCH_INTERVAL_MS,
            self._poll_order_watch,
        )
        if self.memory_diagnostics is not None:
            self.memory_diagnostics.runtime_counters = self._memory_runtime_counters
            self.memory_diagnostics.record_startup(self.root)

    def _initial_geometry(self) -> str:
        bounds = get_chrome_window_bounds()
        if bounds is None:
            return f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+20+120"
        return panel_geometry_from_browser_bounds(
            bounds,
            panel_width=WINDOW_WIDTH,
            gap=WINDOW_GAP,
        )

    def _follow_browser_window(self) -> None:
        if not self.root.winfo_exists():
            self._follow_browser_job = None
            return
        try:
            state = self._browser_state_events.get_nowait()
        except queue.Empty:
            state = None
        else:
            self._browser_state_thread = None
            if state is not None:
                self._browser_minimized = state.minimized
                if state.bounds != self._last_browser_bounds:
                    self.root.geometry(
                        panel_geometry_from_browser_bounds(
                            state.bounds,
                            panel_width=WINDOW_WIDTH,
                            gap=WINDOW_GAP,
                        )
                    )
                    self._last_browser_bounds = state.bounds
                self._sync_companion_visibility(schedule_next=False)
            self._follow_browser_job = self.root.after(
                WINDOW_FOLLOW_INTERVAL_MS,
                self._follow_browser_window,
            )
            return
        if self._browser_state_thread is None:
            self._browser_state_thread = threading.Thread(
                target=self._read_browser_window_state,
                name="order-review-browser-window-state",
                daemon=True,
            )
            self._browser_state_thread.start()
        self._follow_browser_job = self.root.after(
            WINDOW_FOLLOW_RESULT_POLL_MS,
            self._follow_browser_window,
        )

    def _read_browser_window_state(self) -> None:
        self._browser_state_events.put(get_chrome_window_state())

    def _set_companion_visible(self, visible: bool) -> None:
        hidden = not visible
        if self._browser_was_hidden is hidden:
            return
        if not self._native_companion.set_visible(visible):
            if visible:
                self.root.deiconify()
            else:
                self.root.withdraw()
        self._browser_was_hidden = hidden

    def _sync_companion_visibility(self, *, schedule_next: bool = True) -> None:
        if not self.root.winfo_exists():
            self._companion_visibility_job = None
            return
        frontmost = get_frontmost_application()
        if frontmost is not None:
            self._set_companion_visible(
                not self._browser_minimized
                and companion_should_be_visible(
                    frontmost,
                    companion_process_id=os.getpid(),
                )
            )
        if schedule_next:
            self._companion_visibility_job = self.root.after(
                COMPANION_VISIBILITY_INTERVAL_MS,
                self._sync_companion_visibility,
            )

    def _poll_order_watch(self) -> None:
        self._order_watch_job = None
        if not self.root.winfo_exists():
            return
        while True:
            try:
                event, payload = self._order_watch_events.get_nowait()
            except queue.Empty:
                break
            self._order_watch_thread = None
            if event == "identity" and isinstance(payload, tuple):
                generation, probe = payload
                if (
                    generation == self._order_watch_generation
                    and isinstance(probe, SequenceOneIdentityProbe)
                ):
                    self._handle_order_identity(probe)
            elif event == "error" and isinstance(payload, tuple):
                generation, _detail = payload
                if generation != self._order_watch_generation:
                    continue
                self._reset_order_change_candidate()

        if self._can_poll_order_identity() and self._order_watch_thread is None:
            generation = self._order_watch_generation

            def worker() -> None:
                try:
                    probe = self.order_identity_reader()
                    self._order_watch_events.put(
                        ("identity", (generation, probe))
                    )
                except Exception as exc:
                    self._order_watch_events.put(
                        ("error", (generation, str(exc)))
                    )

            self._order_watch_thread = threading.Thread(
                target=worker,
                name="order-review-identity-watch",
                daemon=True,
            )
            self._order_watch_thread.start()

        self._order_watch_job = self.root.after(
            ORDER_WATCH_INTERVAL_MS,
            self._poll_order_watch,
        )

    def _can_poll_order_identity(self) -> bool:
        if (
            not self._auto_refresh_enabled
            or self._audit_running
            or self._auto_refresh_paused
            or self.monotonic() < self._auto_refresh_not_before
            or self.package_workflow.freight_pending
        ):
            return False
        if self.package_workflow.draft is not None:
            return (
                not self._show_package_editor
                and self._compact_reliable_plan() is not None
            )
        return True

    def _handle_order_identity(self, probe: SequenceOneIdentityProbe) -> None:
        if not self._can_poll_order_identity() or not probe.safe_to_auto_refresh:
            self._reset_order_change_candidate()
            return
        current_system_order_id = (
            self.current_snapshot.system_order_id
            if self.current_snapshot is not None
            else ""
        )
        observed = probe.system_order_id
        same_order_refresh_allowed = (
            observed == self._auto_refresh_same_order_id
        )
        if (
            not observed
            or (
                observed == current_system_order_id
                and not same_order_refresh_allowed
            )
            or observed in self._auto_refresh_attempted_order_ids
        ):
            self._reset_order_change_candidate()
            return
        if observed == self._order_change_candidate_id:
            self._order_change_candidate_count += 1
        else:
            self._order_change_candidate_id = observed
            self._order_change_candidate_count = 1
            self._order_change_candidate_since = self.monotonic()
        if (
            self._order_change_candidate_count < ORDER_CHANGE_STABLE_OBSERVATIONS
            or self.monotonic() - self._order_change_candidate_since
            < ORDER_CHANGE_STABLE_SECONDS
        ):
            return

        self._auto_refresh_attempted_order_ids.add(observed)
        self._auto_refresh_same_order_id = ""
        self._reset_order_change_candidate()
        self.refresh(
            automatic=True,
            expected_system_order_id=observed,
        )

    def _reset_order_change_candidate(self) -> None:
        self._order_change_candidate_id = ""
        self._order_change_candidate_count = 0
        self._order_change_candidate_since = 0.0

    def _toggle_auto_refresh(self) -> None:
        self._set_auto_refresh_enabled(not self._auto_refresh_enabled)

    def _set_auto_refresh_enabled(self, enabled: bool) -> None:
        self._auto_refresh_enabled = enabled
        self._auto_refresh_paused = False
        self._order_watch_generation += 1
        self._auto_refresh_attempted_order_ids.clear()
        self._reset_order_change_candidate()
        current = self.current_snapshot
        self._auto_refresh_same_order_id = (
            current.system_order_id
            if enabled
            and current is not None
            and not current.is_expanded
            else ""
        )
        if hasattr(self, "auto_refresh_button"):
            self.auto_refresh_button.configure(
                text="停止自动刷新" if enabled else "自动刷新",
                bg=(
                    MACOS_THEME["accent_soft"]
                    if enabled
                    else MACOS_THEME["surface_soft"]
                ),
                fg=(
                    MACOS_THEME["accent"]
                    if enabled
                    else MACOS_THEME["secondary_text"]
                ),
            )

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

        self.refresh_button = tk.Button(
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
        )
        self.refresh_button.pack(side="right", padx=(6, 12), pady=8)
        self.auto_refresh_button = tk.Button(
            header,
            text="自动刷新",
            command=self._toggle_auto_refresh,
            bg=MACOS_THEME["surface_soft"],
            fg=MACOS_THEME["secondary_text"],
            activebackground=MACOS_THEME["accent_border"],
            activeforeground=MACOS_THEME["primary_text"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=7,
            pady=2,
            font=(FONT_FAMILY, 9, "bold"),
            cursor="hand2",
        )
        self.auto_refresh_button.pack(side="right", pady=8)

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
        self.refresh(passive=True)

    def refresh(
        self,
        *,
        automatic: bool = False,
        passive: bool = False,
        expected_system_order_id: str = "",
    ) -> None:
        if self._audit_running:
            self._audit_feedback = "审核正在进行，完成前不会刷新或切换订单。"
            self._rerender_current_snapshot()
            return
        if not automatic:
            self._order_watch_generation += 1
            self._auto_refresh_paused = False
            self._auto_refresh_not_before = 0.0
            self._auto_refresh_attempted_order_ids.clear()
            self._reset_order_change_candidate()
        elif (
            not expected_system_order_id
            or self.monotonic() < self._auto_refresh_not_before
        ):
            return
        if self._initial_refresh_job is not None:
            try:
                self.root.after_cancel(self._initial_refresh_job)
            except tk.TclError:
                pass
            self._initial_refresh_job = None
        try:
            snapshot = (
                self.auto_refresh_reader(expected_system_order_id)
                if automatic
                else (self.passive_reader() if passive else self.reader())
            )
            self.current_snapshot = snapshot
            self.package_workflow.load_order(snapshot)
            self._active_package_id = None
            self._show_package_editor = False
            self._package_feedback = self.package_workflow.recommendation_error
            self._audit_feedback = ""
            self._auto_refresh_paused = False
            self._reset_order_change_candidate()
            self._render_view(build_sidebar_view(snapshot))
            memory_diagnostics = getattr(self, "memory_diagnostics", None)
            if memory_diagnostics is not None:
                memory_diagnostics.record_refresh(self.root)
        except Exception as exc:
            self.current_snapshot = None
            self.package_workflow.clear_order()
            self._active_package_id = None
            self._show_package_editor = False
            self._package_feedback = ""
            self._audit_feedback = ""
            self._auto_refresh_paused = True
            if self._auto_refresh_enabled:
                self._set_auto_refresh_enabled(False)
            self._reset_order_change_candidate()
            detail = str(exc)
            if automatic:
                detail = (
                    f"自动读取已停止：{detail}。"
                    "后台不会点击或重试展开；需要时请手动点击刷新。"
                )
            self._render_view(
                SidebarView(
                    status="判断：读取失败",
                    metrics=[],
                    aggregate_products=[],
                    order_groups=[],
                    package_plan=_empty_package_plan(),
                    footer_note=detail,
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
            scroll_offset = self._capture_scroll_offset()
            self._render_view(self._current_view, reset_scroll=False)
            self._restore_scroll_offset(scroll_offset)

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
        entry.bind("<Button-1>", lambda event: self._focus_widget(event.widget))
        entry.bind("<Command-c>", lambda event: event.widget.event_generate("<<Copy>>"))
        entry.bind("<Control-c>", lambda event: event.widget.event_generate("<<Copy>>"))
        entry.bind("<Command-a>", self._select_all_entry)
        entry.bind("<Control-a>", self._select_all_entry)
        entry.bind(
            "<Control-Button-1>",
            lambda event: self._show_copy_menu(event.widget, event),
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
            insertwidth=0,
        )
        widget.insert("1.0", text)
        widget.bind("<Button-1>", lambda event: self._focus_widget(event.widget))
        widget.bind("<Command-c>", self._copy_text_selection)
        widget.bind("<Control-c>", self._copy_text_selection)
        widget.bind("<Command-a>", self._select_all_text)
        widget.bind("<Control-a>", self._select_all_text)
        widget.bind("<Key>", lambda _event: "break")
        widget.bind("<<Paste>>", lambda _event: "break")
        widget.bind("<<Cut>>", lambda _event: "break")
        widget.bind(
            "<Control-Button-1>",
            lambda event: self._show_copy_menu(event.widget, event),
        )
        widget.bind("<Button-2>", lambda event: self._show_copy_menu(event.widget, event))
        widget.bind("<Button-3>", lambda event: self._show_copy_menu(event.widget, event))
        return widget

    def _copy_text_selection(self, event: tk.Event) -> str:
        widget = event.widget
        try:
            selected = widget.get("sel.first", "sel.last")
        except tk.TclError:
            selected = widget.get("1.0", "end-1c")
        self._copy_value(selected)
        return "break"

    def _copy_value(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _focus_widget(self, widget: tk.Misc) -> None:
        try:
            self.root.focus_force()
            widget.focus_force()
        except tk.TclError:
            pass

    def _select_all_text(self, event: tk.Event) -> str:
        widget = event.widget
        widget.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _select_all_entry(self, event: tk.Event) -> str:
        event.widget.selection_range(0, "end")
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
        self._action_button(
            header,
            "复制单号",
            lambda value=order_title: self._copy_value(value),
            compact=True,
        ).pack(side="right", padx=(3, 7), pady=5)
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

        compact_reliable_plan = self._compact_reliable_plan()
        status = "待选择"
        if workflow.freight_pending:
            status = "待确认物流"
        elif workflow.direct_single_item_plan is not None:
            status = "单件直审"
        elif compact_reliable_plan is not None and not self._show_package_editor:
            status = "已有历史方案"
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

        if workflow.direct_single_item_plan is not None:
            self._render_readonly_package_plan(workflow.direct_single_item_plan)
            self._render_package_notice(
                workflow.load_notice
                or "总数量为 1，可直接审核；本单不会保存方案。",
                tone="success",
            )
            self._render_single_order_audit(workflow.direct_single_item_plan)
            return

        if workflow.draft is not None:
            if compact_reliable_plan is not None and not self._show_package_editor:
                self._render_readonly_package_plan(compact_reliable_plan)
                self._render_package_notice(
                    workflow.load_notice or "已找到可靠的历史方案。",
                    tone="success",
                )
                if len(compact_reliable_plan.packages) == 1:
                    self._render_single_order_audit(
                        compact_reliable_plan,
                        edit_command=self._open_current_draft_editor,
                    )
                else:
                    self._render_split_dry_run(compact_reliable_plan)
                    self._action_button(
                        self.content_frame,
                        "修改方案",
                        lambda: self._package_action(
                            self._open_current_draft_editor
                        ),
                        accented=True,
                        enabled=not self._audit_running,
                    ).pack(fill="x", pady=(0, 8))
                return
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
            if len(workflow.historical_plan.packages) == 1:
                self._render_single_order_audit(
                    workflow.historical_plan,
                    edit_command=lambda: self._package_action(
                        self._edit_historical_plan
                    ),
                )
            else:
                self._render_split_dry_run(workflow.historical_plan)
                self._action_button(
                    self.content_frame,
                    "修改方案",
                    lambda: self._package_action(self._edit_historical_plan),
                    accented=True,
                    enabled=not self._audit_running,
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
            if len(workflow.confirmed_plan.packages) == 1:
                self._render_single_order_audit(workflow.confirmed_plan)
            else:
                self._render_split_dry_run(workflow.confirmed_plan)
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

    def _compact_reliable_plan(self):
        workflow = self.package_workflow
        source = workflow.source_snapshot
        draft = workflow.draft
        candidate = workflow.selected_recommendation
        if (
            source is None
            or draft is None
            or candidate is None
            or not workflow.auto_adopted_recommendation
            or candidate.match_type
            not in {
                MATCH_EXACT_STRUCTURE,
                MATCH_SINGLE_PACKAGE_TOTAL,
                MATCH_HISTORICAL_PACKAGE_COMPOSITION,
            }
        ):
            return None
        try:
            plan = draft.confirm(source)
        except PackagePlanValidationError:
            return None
        return plan

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

    def _render_single_order_audit(
        self,
        plan,
        *,
        edit_command: Callable[[], None] | None = None,
    ) -> None:
        if len(plan.packages) != 1:
            return
        source = self.package_workflow.source_snapshot
        if source is None:
            return
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["surface"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            padx=9,
            pady=9,
        )
        card.pack(fill="x", pady=(0, 8))
        tk.Label(
            card,
            text="单订单审核",
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(fill="x")
        target_text = source.system_order_id or "未识别"
        status_text = "等待开始"
        status_color = MACOS_THEME["muted_text"]
        if self._audit_running:
            status_text = self._audit_progress or "正在准备审核"
            status_color = MACOS_THEME["warning"]
        elif self._audit_completed_system_order_id == source.system_order_id:
            status_text = "本单审核成功"
            status_color = MACOS_THEME["success"]
        tk.Label(
            card,
            text=status_text,
            bg=MACOS_THEME["surface"],
            fg=status_color,
            font=(FONT_FAMILY, 8, "bold"),
            anchor="e",
        ).place(relx=1.0, x=-1, y=0, anchor="ne")
        self._selectable_text(
            card,
            f"目标订单：{target_text}",
            background=MACOS_THEME["surface"],
            foreground=MACOS_THEME["secondary_text"],
            font=(FONT_FAMILY, 9),
            wrap_chars=40,
        ).pack(fill="x", pady=(5, 7))
        actions = tk.Frame(card, bg=MACOS_THEME["surface"])
        actions.pack(fill="x")
        if edit_command is not None:
            self._action_button(
                actions,
                "修改方案",
                edit_command,
                accented=True,
                compact=True,
                enabled=not self._audit_running,
            ).pack(side="left", padx=(0, 8))
        can_audit = bool(source.system_order_id) and not self._audit_running and (
            self._audit_completed_system_order_id != source.system_order_id
        )
        self._action_button(
            actions,
            "审核当前订单",
            lambda: self._start_single_order_audit(plan),
            danger=True,
            enabled=can_audit,
        ).pack(
            side="right" if edit_command is not None else "top",
            fill="x",
            expand=edit_command is not None,
        )
        action_note = "点击后自动检查，只处理当前 1 单，不会保存方案或继续下一单。"
        tk.Label(
            card,
            text=action_note,
            bg=MACOS_THEME["surface"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(6, 0))
        if not source.system_order_id:
            self._render_package_notice(
                "当前订单缺少可靠的系统订单号，无法开始审核。",
                tone="warning",
            )
        elif self._audit_feedback:
            tone = "info"
            if "成功" in self._audit_feedback:
                tone = "success"
            elif "停止" in self._audit_feedback or "不确定" in self._audit_feedback:
                tone = "warning"
            self._render_package_notice(self._audit_feedback, tone=tone)

    def _render_split_dry_run(
        self,
        plan,
    ) -> None:
        source = self.package_workflow.source_snapshot
        if source is None or len(plan.packages) < 2:
            return
        report = build_split_dry_run(source, plan)
        card = tk.Frame(
            self.content_frame,
            bg=MACOS_THEME["warning_soft"],
            highlightbackground="#ead8b9",
            highlightthickness=1,
            padx=9,
            pady=9,
        )
        card.pack(fill="x", pady=(0, 8))
        header = tk.Frame(card, bg=MACOS_THEME["warning_soft"])
        header.pack(fill="x")
        tk.Label(
            header,
            text="订单拆分",
            bg=MACOS_THEME["warning_soft"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).pack(side="left")
        status_text = "等待开始"
        status_color = MACOS_THEME["muted_text"]
        if self._audit_running:
            status_text = self._audit_progress or "正在准备拆分"
            status_color = MACOS_THEME["warning"]
        elif self._split_completed_system_order_id == source.system_order_id:
            status_text = "本单拆分并审核成功"
            status_color = MACOS_THEME["success"]
        tk.Label(
            header,
            text=status_text,
            bg=MACOS_THEME["warning_soft"],
            fg=status_color,
            font=(FONT_FAMILY, 8, "bold"),
            anchor="e",
        ).pack(side="right")
        package_lines = "\n".join(report.package_lines)
        self._selectable_text(
            card,
            (
                f"目标订单：{source.system_order_id or '未识别'}\n"
                f"目标包裹：{len(plan.packages)} 个\n"
                f"{package_lines}\n"
                f"数量核对：{plan.total_quantity} / {source.total_quantity} 件"
            ),
            background=MACOS_THEME["warning_soft"],
            foreground=MACOS_THEME["secondary_text"],
            font=(FONT_FAMILY, 9),
            wrap_chars=38,
        ).pack(fill="x", pady=(6, 0))
        can_split = (
            report.local_plan_valid
            and bool(source.system_order_id)
            and not self._audit_running
            and self._split_completed_system_order_id != source.system_order_id
        )
        self._action_button(
            card,
            "拆分并审核当前订单",
            lambda: self._start_mixed_order_split(plan),
            danger=True,
            enabled=can_split,
        ).pack(fill="x", pady=(8, 0))
        tk.Label(
            card,
            text=(
                "点击后连续完成当前订单拆分，并在审核弹窗显示的"
                "已勾选数量等于目标包裹数时继续审核。"
            ),
            bg=MACOS_THEME["warning_soft"],
            fg=MACOS_THEME["muted_text"],
            font=(FONT_FAMILY, 8),
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(6, 0))
        if self._audit_feedback:
            tone = "info"
            if "成功" in self._audit_feedback:
                tone = "success"
            elif "停止" in self._audit_feedback or "不确定" in self._audit_feedback:
                tone = "warning"
            self._render_package_notice(self._audit_feedback, tone=tone)

    def _start_single_order_audit(
        self,
        plan,
    ) -> None:
        if self._audit_running:
            return
        source = self.package_workflow.source_snapshot
        if source is None:
            self._audit_feedback = "当前没有已确认的订单方案，无法开始审核。"
            self._rerender_current_snapshot()
            return
        if len(plan.packages) != 1:
            self._audit_feedback = "当前不是单包方案，不能使用单订单审核。"
            self._rerender_current_snapshot()
            return
        if not source.system_order_id:
            self._audit_feedback = "当前订单缺少可靠系统订单号，无法开始审核。"
            self._rerender_current_snapshot()
            return
        self._audit_running = True
        self._order_watch_generation += 1
        self._audit_progress = "正在自动检查"
        self._audit_feedback = f"审核进行中：{self._audit_progress}。"
        self._auto_refresh_paused = False
        self._reset_order_change_candidate()
        self._rerender_current_snapshot()

        def progress(state, detail) -> None:
            self._audit_events.put(("progress", (state, detail)))

        def worker() -> None:
            try:
                worker_plan = plan
                report = self.audit_executor(
                    target_system_order_id=source.system_order_id,
                    expected_source=source,
                    confirmation_reference_id=(
                        self._confirmation_reference_id()
                    ),
                    target_package_count=len(worker_plan.packages),
                    progress_callback=progress,
                    log_store=self.audit_log_store,
                )
                self._audit_events.put(("finished", report))
            except Exception as exc:
                self._audit_events.put(("error", str(exc)))

        self._audit_thread = threading.Thread(
            target=worker,
            name="order-review-audit",
            daemon=True,
        )
        self._audit_thread.start()
        if self._audit_poll_job is None:
            self._audit_poll_job = self.root.after(50, self._drain_audit_events)

    def _start_mixed_order_split(
        self,
        plan,
    ) -> None:
        if self._audit_running:
            return
        source = self.package_workflow.source_snapshot
        if source is None:
            self._audit_feedback = "当前没有已确认的订单方案，无法开始拆分。"
            self._rerender_current_snapshot()
            return
        if len(plan.packages) < 2:
            self._audit_feedback = "当前不是多包方案，不能执行订单拆分。"
            self._rerender_current_snapshot()
            return
        report = build_split_dry_run(source, plan)
        if not report.local_plan_valid:
            self._audit_feedback = (
                f"当前方案无法拆分：{'；'.join(report.blocked_reasons)}。"
            )
            self._rerender_current_snapshot()
            return
        if not source.system_order_id:
            self._audit_feedback = "当前订单缺少可靠系统订单号，无法开始拆分。"
            self._rerender_current_snapshot()
            return
        self._audit_running = True
        self._order_watch_generation += 1
        self._audit_progress = "正在自动检查"
        self._audit_feedback = (
            f"拆分并审核进行中：{self._audit_progress}。"
        )
        self._reset_order_change_candidate()
        self._rerender_current_snapshot()

        def progress(state, detail) -> None:
            self._audit_events.put(("split_progress", (state, detail)))

        def worker() -> None:
            try:
                worker_plan = plan
                split_report = self.split_executor(
                    target_system_order_id=source.system_order_id,
                    expected_source=source,
                    plan=worker_plan,
                    confirmation_reference_id=(
                        self._confirmation_reference_id()
                    ),
                    progress_callback=progress,
                    log_store=self.audit_log_store,
                )
                self._audit_events.put(("split_finished", split_report))
            except Exception as exc:
                self._audit_events.put(("split_error", str(exc)))

        self._audit_thread = threading.Thread(
            target=worker,
            name="order-review-split",
            daemon=True,
        )
        self._audit_thread.start()
        if self._audit_poll_job is None:
            self._audit_poll_job = self.root.after(50, self._drain_audit_events)

    def _confirmation_reference_id(self) -> str:
        if self.package_workflow.confirmed_case is not None:
            return self.package_workflow.confirmed_case.case_id
        if self.package_workflow.historical_case is not None:
            return self.package_workflow.historical_case.case_id
        candidate = self.package_workflow.selected_recommendation
        if candidate is not None and candidate.source_case_ids:
            return candidate.source_case_ids[0]
        return ""

    def _drain_audit_events(self) -> None:
        self._audit_poll_job = None
        rerender = False
        while True:
            try:
                event, payload = self._audit_events.get_nowait()
            except queue.Empty:
                break
            if event == "progress":
                _state, detail = payload
                self._audit_progress = str(detail)
                self._audit_feedback = f"审核进行中：{detail}"
                rerender = True
            elif event == "split_progress":
                _state, detail = payload
                self._audit_progress = str(detail)
                self._audit_feedback = f"拆分并审核进行中：{detail}"
                rerender = True
            elif event == "finished":
                report = payload
                self._audit_running = False
                self._audit_thread = None
                self._audit_progress = ""
                self._audit_feedback = report.render_text()
                if report.successful:
                    self._audit_completed_system_order_id = (
                        report.target_system_order_id
                    )
                    self._auto_refresh_not_before = (
                        self.monotonic() + POST_AUDIT_REFRESH_DELAY_SECONDS
                    )
                    self._auto_refresh_paused = False
                    if self._auto_refresh_enabled:
                        self._audit_feedback = (
                            f"审核成功：订单 {report.target_system_order_id} "
                            "已离开待审核列表。正在快速确认新订单状态；"
                            "确认稳定后会自动刷新下一单。"
                        )
                    else:
                        self._audit_feedback = (
                            f"审核成功：订单 {report.target_system_order_id} "
                            "已离开待审核列表。自动刷新未开启，请手动刷新下一单。"
                        )
                else:
                    self._set_auto_refresh_enabled(False)
                self._reset_order_change_candidate()
                rerender = True
            elif event == "split_finished":
                report = payload
                self._audit_running = False
                self._audit_thread = None
                self._audit_progress = ""
                self._audit_feedback = report.render_text()
                if report.successful:
                    self._split_completed_system_order_id = (
                        report.target_system_order_id
                    )
                    self._auto_refresh_not_before = (
                        self.monotonic() + POST_AUDIT_REFRESH_DELAY_SECONDS
                    )
                    self._auto_refresh_paused = False
                    if self._auto_refresh_enabled:
                        self._audit_feedback = (
                            f"拆分并审核成功：订单 {report.target_system_order_id} "
                            "已离开待审核列表。正在快速确认新订单状态；"
                            "确认稳定后会自动刷新下一单。"
                        )
                else:
                    self._set_auto_refresh_enabled(False)
                self._reset_order_change_candidate()
                rerender = True
            elif event == "error":
                self._audit_running = False
                self._audit_thread = None
                self._audit_progress = ""
                self._set_auto_refresh_enabled(False)
                self._reset_order_change_candidate()
                self._audit_feedback = (
                    f"审核已停止：{payload}。没有继续执行后续动作。"
                )
                rerender = True
            elif event == "split_error":
                self._audit_running = False
                self._audit_thread = None
                self._audit_progress = ""
                self._set_auto_refresh_enabled(False)
                self._reset_order_change_candidate()
                self._audit_feedback = (
                    f"拆分并审核已停止：{payload}。没有重试提交。"
                )
                rerender = True
        if rerender:
            self._rerender_current_snapshot()
        if self._audit_running or not self._audit_events.empty():
            self._audit_poll_job = self.root.after(50, self._drain_audit_events)

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
        if result.advisory_note:
            self._render_package_notice(result.advisory_note, tone="warning")
        if not result.candidates:
            return
        has_capacity_candidate = any(
            candidate.match_type == MATCH_SINGLE_PACKAGE_CAPACITY
            for candidate in result.candidates
        )
        has_composition_candidate = any(
            candidate.match_type == MATCH_HISTORICAL_PACKAGE_COMPOSITION
            for candidate in result.candidates
        )
        if result.conflict:
            self._render_package_notice(
                (
                    "历史包裹可以形成多种最少包裹组合，请人工比较后选择；"
                    "系统不会自动采用。"
                    if has_composition_candidate
                    else "历史中存在不同拆分方案，请人工比较后选择；系统不会自动采用。"
                ),
                tone="warning",
            )
        elif has_composition_candidate:
            self._render_package_notice(
                "找到可精确覆盖本单数量的历史包裹组合；"
                "每个包裹均原样来自已确认案例，请核对后采用。",
                tone="info",
            )
        elif has_capacity_candidate:
            self._render_package_notice(
                "找到较大数量曾单包的历史参考；纸箱规格可能不连续，"
                "请核对当前箱型后再决定是否采用。",
                tone="warning",
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
                text=(
                    f"组合候选 {candidate_index} · {len(candidate.packages)} 个包裹"
                    if candidate.match_type
                    == MATCH_HISTORICAL_PACKAGE_COMPOSITION
                    else f"候选 {candidate_index} · {len(candidate.packages)} 个包裹"
                ),
                bg=MACOS_THEME["surface"],
                fg=MACOS_THEME["primary_text"],
                font=(FONT_FAMILY, 10, "bold"),
            ).pack(side="left")
            tk.Label(
                header,
                text=(
                    f"历史包裹证据 {candidate.usage_count} 条"
                    if candidate.match_type
                    == MATCH_HISTORICAL_PACKAGE_COMPOSITION
                    else f"历史使用 {candidate.usage_count} 次"
                ),
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
            "新增包裹",
            lambda: self._package_action(self._add_next_package),
            compact=True,
            enabled=can_add_next,
        ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        self._action_button(
            actions,
            "恢复初始",
            lambda: self._package_action(self._reset_package_plan),
            compact=True,
        ).pack(side="left", fill="x", expand=True, padx=2)
        self._action_button(
            actions,
            "保存方案",
            lambda: self._package_action(self._confirm_package_plan),
            primary=True,
            compact=True,
        ).pack(side="left", fill="x", expand=True, padx=(2, 0))
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
            "MIN",
            lambda: self._package_action(
                lambda: self._set_package_quantity(
                    package_id, product.source_product_id, 0
                )
            ),
            enabled=current > 0,
            width=34,
        ).pack(side="left", padx=(0, 2))
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
            "<Button-1>",
            lambda event: self._focus_widget(event.widget),
        )
        quantity_entry.bind(
            "<FocusIn>",
            lambda event: self.root.after_idle(
                lambda widget=event.widget: (
                    widget.selection_range(0, "end")
                    if widget.winfo_exists()
                    else None
                )
            ),
        )
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
            "<FocusOut>",
            lambda _event: self._commit_package_quantity(
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
        remaining_quantity = self.package_workflow.remaining_quantity
        auto_fill_note = ""
        if remaining_quantity > 0:
            moved, target_package_id, created = (
                self.package_workflow.move_remaining_to_final_package()
            )
            self._active_package_id = target_package_id
            auto_fill_note = (
                f"保存时已将剩余 {moved} 件自动生成最后一个包裹。"
                if created
                else f"保存时已将剩余 {moved} 件归入最后一个空包裹。"
            )
        self.package_workflow.confirm()
        self.package_workflow.confirmation_note = (
            f"{auto_fill_note}{self.package_workflow.confirmation_note}"
        )
        self._package_feedback = self.package_workflow.confirmation_note
        self._audit_feedback = ""

    def _confirm_freight(self) -> None:
        self.package_workflow.confirm_freight()
        self._package_feedback = self.package_workflow.confirmation_note

    def _open_current_draft_editor(self) -> None:
        draft = self.package_workflow.draft
        if draft is None:
            raise PackagePlanValidationError("当前没有可修改的包裹方案")
        self._show_package_editor = True
        self._active_package_id = draft.packages[0].package_id

    def _edit_historical_plan(self) -> None:
        self.package_workflow.edit_historical_plan()
        self._show_package_editor = True
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_single_package(self) -> None:
        self.package_workflow.start_single_package()
        self._show_package_editor = True
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_split(self) -> None:
        self.package_workflow.start_split()
        self._show_package_editor = True
        self._active_package_id = self.package_workflow.draft.packages[0].package_id

    def _start_freight(self) -> None:
        self.package_workflow.start_freight()
        self._show_package_editor = False
        self._active_package_id = None

    def _adopt_recommendation(self, recommendation_id: str) -> None:
        self.package_workflow.adopt_recommendation(recommendation_id)
        self._show_package_editor = True
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

    def _fill_current_package_with_remaining(self) -> None:
        if self._active_package_id is None:
            raise PackagePlanValidationError("当前没有正在编辑的包裹")
        before = self.package_workflow.remaining_quantity
        self.package_workflow.fill_package_with_remaining(self._active_package_id)
        moved = before - self.package_workflow.remaining_quantity
        self._package_feedback = (
            f"已将剩余 {moved} 件商品全部放入当前包裹"
            if moved
            else "当前没有待分配商品"
        )

    def _reset_package_plan(self) -> None:
        self.package_workflow.reset()
        package_ids = [
            package.package_id for package in self.package_workflow.draft.packages
        ]
        if self._active_package_id not in package_ids:
            self._active_package_id = package_ids[0]

    def _cancel_package_plan(self) -> None:
        self.package_workflow.cancel()
        self._show_package_editor = False
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
        if self._audit_running:
            self._audit_feedback = "审核正在进行，完成前不能修改包裹方案。"
            self._rerender_current_snapshot()
            return
        self._package_feedback = ""
        try:
            action()
        except Exception as exc:
            self._package_feedback = str(exc)
        self._rerender_current_snapshot()

    def _rerender_current_snapshot(self) -> None:
        if self.current_snapshot is None:
            return
        scroll_offset = self._capture_scroll_offset()
        self._render_view(build_sidebar_view(self.current_snapshot), reset_scroll=False)
        self._restore_scroll_offset(scroll_offset)

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
            padx=3 if compact else 6,
            pady=1 if compact else 3,
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
            font=(FONT_FAMILY, 7 if text in {"MIN", "MAX"} else 11, "bold"),
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

    def _capture_scroll_offset(self) -> float:
        """保存浮窗内容区顶部的绝对像素位置，避免重绘时按百分比跳动。"""
        self.root.update_idletasks()
        return max(0.0, float(self.canvas.canvasy(0)))

    def _restore_scroll_offset(self, offset: float) -> None:
        self.root.update_idletasks()
        bounds = self.canvas.bbox("all")
        if bounds is None:
            self.canvas.yview_moveto(0)
            return
        top = float(bounds[1])
        height = max(1.0, float(bounds[3] - bounds[1]))
        self.canvas.configure(scrollregion=bounds)
        fraction = max(0.0, min(1.0, (offset - top) / height))
        self.canvas.yview_moveto(fraction)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _memory_runtime_counters(self) -> Mapping[str, int]:
        return {
            "auditEventQueueSize": self._audit_events.qsize(),
            "orderWatchEventQueueSize": self._order_watch_events.qsize(),
            "quantityCommitJobCount": len(self._quantity_commit_jobs),
            "auditThreadAlive": int(
                self._audit_thread is not None and self._audit_thread.is_alive()
            ),
            "orderWatchThreadAlive": int(
                self._order_watch_thread is not None
                and self._order_watch_thread.is_alive()
            ),
        }

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
        if self._audit_running:
            self._audit_feedback = "审核正在进行，完成前不能关闭悬浮窗。"
            self._rerender_current_snapshot()
            return
        if self._audit_poll_job is not None:
            try:
                self.root.after_cancel(self._audit_poll_job)
            except tk.TclError:
                pass
            self._audit_poll_job = None
        if self._follow_browser_job is not None:
            try:
                self.root.after_cancel(self._follow_browser_job)
            except tk.TclError:
                pass
            self._follow_browser_job = None
        if self._companion_visibility_job is not None:
            try:
                self.root.after_cancel(self._companion_visibility_job)
            except tk.TclError:
                pass
            self._companion_visibility_job = None
        if self._order_watch_job is not None:
            try:
                self.root.after_cancel(self._order_watch_job)
            except tk.TclError:
                pass
            self._order_watch_job = None
        self.package_workflow.close()
        self.root.destroy()


def run_app(memory_diagnostics: MemoryDiagnostics | None = None) -> None:
    root = tk.Tk()
    OrderReviewWindow(root, memory_diagnostics=memory_diagnostics)
    root.mainloop()
