from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .erp_reader import read_sequence_one_order
from .models import OrderSnapshot, Product
from .rules import judge
from .window_position import get_chrome_window_bounds, panel_geometry_from_browser_bounds


WINDOW_WIDTH = 360
WINDOW_HEIGHT = 760
WINDOW_GAP = 8
FONT_FAMILY = "Helvetica Neue"
DETAIL_COLLAPSED_TEXT = "展开详情"
DETAIL_EXPANDED_TEXT = "隐藏详情"
MACOS_THEME = {
    "window_bg": "#f5f5f7",
    "titlebar_bg": "#f5f5f7",
    "card_bg": "#ffffff",
    "border": "#d1d1d6",
    "primary_text": "#1d1d1f",
    "secondary_text": "#515154",
    "muted_text": "#6e6e73",
    "accent": "#007aff",
    "accent_pressed": "#0066d6",
    "close": "#ff5f57",
    "close_pressed": "#e0443e",
    "refresh_text": "刷新",
    "close_text": "×",
}


@dataclass(frozen=True)
class ProductCardView:
    title: str
    details: list[str]


@dataclass(frozen=True)
class SidebarView:
    status: str
    summary_lines: list[str]
    product_cards: list[ProductCardView]


def format_sidebar_lines(snapshot: OrderSnapshot) -> list[str]:
    view = build_sidebar_view(snapshot)
    lines = [view.status]
    lines.extend(view.summary_lines)
    for card in view.product_cards:
        lines.append(card.title)
        lines.extend(card.details)
    return lines


def build_sidebar_view(snapshot: OrderSnapshot) -> SidebarView:
    judgment = judge(
        is_expanded=snapshot.is_expanded,
        products=snapshot.products,
        has_suite_action=snapshot.has_suite_action,
    )
    if not snapshot.is_expanded:
        return SidebarView(status=judgment.message, summary_lines=[], product_cards=[])

    return SidebarView(
        status=judgment.message,
        summary_lines=[
        f"{snapshot.kind_count} 种 / {snapshot.total_quantity} 件",
        f"可合单标记：{'有' if snapshot.has_can_merge_mark else '无'}",
        ],
        product_cards=[_build_product_card(product) for product in snapshot.products],
    )


def _build_product_card(product: Product) -> ProductCardView:
    lines = _format_product_lines(product)
    return ProductCardView(title=lines[0], details=lines[1:])


def _format_product_lines(product: Product) -> list[str]:
    lines = [
        f"{product.short_name or product.standard_name} x{product.quantity}",
    ]
    if product.standard_name and product.standard_name != product.short_name:
        lines.append(product.standard_name)
    if product.main_merchant_code:
        lines.append(f"主商家编码：{product.main_merchant_code}")
        lines.append(f"商家编码：{product.merchant_code}")
    elif product.merchant_code:
        lines.append(f"编码：{product.merchant_code}")
    if product.spu_id:
        lines.append(f"SPU：{product.spu_id}")
    if product.sku_id:
        lines.append(f"SKU：{product.sku_id}")
    return lines


class OrderReviewWindow:
    def __init__(
        self,
        root: tk.Tk,
        reader: Callable[[], OrderSnapshot] = read_sequence_one_order,
    ) -> None:
        self.root = root
        self.reader = reader
        self.root.title("审单悬浮窗")
        self.root.geometry(self._initial_geometry())
        self.root.resizable(False, True)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self._drag_offset = (0, 0)
        self._build()
        self.root.after(300, self.refresh)

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

    def _build(self) -> None:
        self.root.configure(bg=MACOS_THEME["window_bg"])
        header = tk.Frame(self.root, bg=MACOS_THEME["titlebar_bg"], height=44)
        header.pack(fill="x")
        header.bind("<ButtonPress-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)
        close_btn = tk.Label(
            header,
            text=MACOS_THEME["close_text"],
            bg=MACOS_THEME["close"],
            fg="#7a1f1b",
            font=(FONT_FAMILY, 10, "bold"),
            cursor="hand2",
            width=2,
            height=1,
        )
        close_btn.bind("<Button-1>", lambda _event: self.root.destroy())
        close_btn.bind("<Enter>", lambda _event: close_btn.configure(bg=MACOS_THEME["close_pressed"], fg="#ffffff"))
        close_btn.bind("<Leave>", lambda _event: close_btn.configure(bg=MACOS_THEME["close"], fg="#7a1f1b"))
        close_btn.pack(side="left", padx=(12, 8), pady=12)
        tk.Label(
            header,
            text="审单",
            bg=MACOS_THEME["titlebar_bg"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w",
        ).pack(side="left", padx=12)
        tk.Button(
            header,
            text=MACOS_THEME["refresh_text"],
            command=self.refresh,
            bg=MACOS_THEME["accent"],
            fg="#ffffff",
            activebackground=MACOS_THEME["accent_pressed"],
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=5,
            font=(FONT_FAMILY, 13, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=12, pady=8)

        self.status = tk.StringVar(value="判断：点击读取当前 1 号订单")
        self.summary = tk.StringVar(value="")
        tk.Label(
            self.root,
            textvariable=self.status,
            bg=MACOS_THEME["window_bg"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 16, "bold"),
            anchor="w",
            justify="left",
            wraplength=WINDOW_WIDTH - 24,
        ).pack(fill="x", padx=12, pady=(12, 8))
        tk.Label(
            self.root,
            textvariable=self.summary,
            bg=MACOS_THEME["window_bg"],
            fg=MACOS_THEME["secondary_text"],
            font=(FONT_FAMILY, 14),
            anchor="w",
            justify="left",
            wraplength=WINDOW_WIDTH - 24,
        ).pack(fill="x", padx=12, pady=(0, 10))

        frame = tk.Frame(self.root, bg=MACOS_THEME["window_bg"])
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.canvas = tk.Canvas(frame, bg=MACOS_THEME["window_bg"], highlightthickness=0)
        self.cards_frame = tk.Frame(self.canvas, bg=MACOS_THEME["window_bg"])
        self.cards_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        scrollbar = ttk.Scrollbar(frame, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.cards_frame.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_canvas_width)
        self._render_view(SidebarView("判断：点击读取当前 1 号订单", ["等待读取 ERP 当前序号 1 订单"], []))

    def refresh(self) -> None:
        try:
            snapshot = self.reader()
            self._render_view(build_sidebar_view(snapshot))
        except Exception as exc:
            self._render_view(SidebarView("判断：读取失败", [str(exc)], []))

    def _render_lines(self, lines: list[str]) -> None:
        self._render_view(
            SidebarView(
                status=lines[0] if lines else "判断：待人工确认",
                summary_lines=lines[1:] if len(lines) > 1 else lines,
                product_cards=[],
            )
        )

    def _render_view(self, view: SidebarView) -> None:
        self.status.set(view.status)
        self.summary.set("\n".join(view.summary_lines))
        for child in self.cards_frame.winfo_children():
            child.destroy()
        if not view.product_cards:
            return
        for index, card in enumerate(view.product_cards, start=1):
            self._render_product_card(index, card)

    def _render_product_card(self, index: int, card: ProductCardView) -> None:
        outer = tk.Frame(
            self.cards_frame,
            bg=MACOS_THEME["card_bg"],
            highlightbackground=MACOS_THEME["border"],
            highlightthickness=1,
            padx=10,
            pady=9,
        )
        outer.pack(fill="x", pady=(0, 10))
        top = tk.Frame(outer, bg=MACOS_THEME["card_bg"])
        top.pack(fill="x")
        tk.Label(
            top,
            text=f"{index}. {card.title}",
            bg=MACOS_THEME["card_bg"],
            fg=MACOS_THEME["primary_text"],
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w",
            justify="left",
            wraplength=WINDOW_WIDTH - 116,
        ).pack(side="left", fill="x", expand=True)
        if not card.details:
            return
        detail_frame = tk.Frame(outer, bg=MACOS_THEME["card_bg"])
        button = tk.Button(
            top,
            text=DETAIL_COLLAPSED_TEXT,
            bg=MACOS_THEME["card_bg"],
            fg=MACOS_THEME["accent"],
            activebackground=MACOS_THEME["card_bg"],
            activeforeground=MACOS_THEME["accent_pressed"],
            relief="flat",
            padx=0,
            pady=0,
            font=(FONT_FAMILY, 12, "bold"),
            cursor="hand2",
        )
        button.pack(side="right", padx=(8, 0))
        for detail in card.details:
            tk.Label(
                detail_frame,
                text=detail,
                bg=MACOS_THEME["card_bg"],
                fg=MACOS_THEME["secondary_text"],
                font=(FONT_FAMILY, 13),
                anchor="w",
                justify="left",
                wraplength=WINDOW_WIDTH - 56,
            ).pack(fill="x", pady=(5, 0))

        def toggle_details() -> None:
            if detail_frame.winfo_ismapped():
                detail_frame.pack_forget()
                button.configure(text=DETAIL_COLLAPSED_TEXT)
            else:
                detail_frame.pack(fill="x", pady=(6, 0))
                button.configure(text=DETAIL_EXPANDED_TEXT)

        button.configure(command=toggle_details)

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_canvas_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.cards_window, width=event.width)

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_drag(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")


def run_app() -> None:
    root = tk.Tk()
    OrderReviewWindow(root)
    root.mainloop()
