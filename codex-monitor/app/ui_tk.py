"""Tkinter MVP UI for Codex Monitor."""

from __future__ import annotations

import json
import math
import time
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from app.aggregate import ProjectTotal, TokenTotals, UsageAggregate
from app.runtime import RefreshRequest

if TYPE_CHECKING:
    import tkinter as tk


BG_WINDOW = "#F4F8FA"
BG_SECTION = "#FBFDFE"
TRANSPARENT_BG = "systemTransparent"
BORDER = "#D7E0E3"
SHADOW = "#DDE7EA"
TEXT_PRIMARY = "#1D1D1F"
TEXT_SECONDARY = "#7D838C"
TEXT_MONO = "#333333"
TEXT_ON_GLASS = "#172326"
TEXT_MUTED_GLASS = "#5F6E73"
TRACK_COLOR = "#B9C7CB"   # subtle track on white glass
COLOR_5H = "#5FD0C5"      # cyan/teal for 5h quota
COLOR_WEEK = "#F2B866"    # warm amber for weekly quota
CAPSULE_HIT_FILL = "#F4F8FA"
CAPSULE_HIT_STIPPLE = "gray25"
WINDOW_ALPHA = 1.0
WINDOW_RADIUS = 41
CARD_RADIUS = 16
STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "state.json"

COLLAPSED_W = 258
COLLAPSED_H = 82
EXPANDED_W = 360
PROJECT_POPOVER_LIMIT = 10
PROJECT_POPOVER_W = 410
PROJECT_POPOVER_ALPHA = 0.96


def _expanded_spacing() -> dict[str, Any]:
    return {
        "side_pad": 16,
        "title_height": 20,
        "quota_pady": (2, 4),
        "project_pady": (6, 0),
        "footer_divider_pady": (0, 0),
        "footer_bar_pady": (0, 0),
        "button_pady": 0,
    }


def _macos_blur_config() -> dict[str, Any]:
    return {
        "material": "popover",
        "material_value": 6,
        "blending_mode": "behindWindow",
        "blending_mode_value": 0,
        "state": "active",
        "state_value": 1,
        "alpha": 0.76,
        "corner_radius": WINDOW_RADIUS,
    }


def _macos_frame_from_tk_geometry(
    *,
    screen_height: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    return (x, screen_height - y - height, width, height)


def _expanded_toolbar_symbols() -> tuple[str, str, str]:
    return ("↺", "↘↖", "×")


def _show_expanded_footer_actions() -> bool:
    return False


def _project_popover_limit() -> int:
    return PROJECT_POPOVER_LIMIT


def _project_popover_uses_native_blur() -> bool:
    return False


def _capsule_hit_options() -> dict[str, str]:
    return {
        "fill": CAPSULE_HIT_FILL,
        "outline": BORDER,
        "stipple": CAPSULE_HIT_STIPPLE,
    }


def _fmt_compact_duration(minutes: int | None) -> str:
    if minutes is None:
        return "--"
    minutes = max(0, int(minutes))
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)
    if days:
        return f"{days}天{hours}小时" if hours else f"{days}天"
    if hours:
        return f"{hours}小时{mins}分" if mins else f"{hours}小时"
    return f"{mins}分"


def format_millions(tokens: int) -> str:
    return f"{tokens / 1_000_000:.2f}M"


def format_percent(percent: float) -> str:
    return f"{percent:.1f}%"


def _fmt_countdown(resets_at: Any, window_minutes: int | None) -> str:
    """Format time remaining until next quota reset."""
    if resets_at is not None:
        try:
            if isinstance(resets_at, str):
                ts = datetime.fromisoformat(resets_at.replace("Z", "+00:00")).timestamp()
            else:
                ts = float(resets_at)
            remaining = max(0.0, ts - time.time())
            h, rem = divmod(int(remaining), 3600)
            m = rem // 60
            return f"{h}h{m}m" if h > 0 else f"{m}m"
        except Exception:
            pass
    if window_minutes:
        h, m = divmod(window_minutes, 60)
        if h and m:
            return f"{h}h{m}m"
        return f"{h}h" if h else f"{m}m"
    return "--"


def _countdown_minutes(resets_at: Any, window_minutes: int | None) -> int | None:
    if resets_at is not None:
        try:
            if isinstance(resets_at, str):
                ts = datetime.fromisoformat(resets_at.replace("Z", "+00:00")).timestamp()
            else:
                ts = float(resets_at)
            return max(0, int((ts - time.time()) // 60))
        except Exception:
            pass
    return int(window_minutes) if window_minutes else None


def _fmt_compact_countdown(resets_at: Any, window_minutes: int | None) -> str:
    return _fmt_compact_duration(_countdown_minutes(resets_at, window_minutes))


def _ring_extent(used_pct: float) -> float | None:
    """Arc extent in degrees (negative = clockwise) for a used percentage.

    Returns None when the slice is too small to draw. The magnitude is capped
    just below 360 because tkinter renders a blank arc when extent hits exactly
    ±360 — without this cap a 100% ring shows as empty (looks "reset to zero").
    """
    pct = max(0.0, min(100.0, used_pct))
    if pct < 0.5:
        return None
    return -min(pct * 3.6, 359.99)  # negative = clockwise


def _draw_ring(cv: Any, cx: float, cy: float, r: float, width: float,
               used_pct: float, color: str) -> None:
    """Draw a ring segment with round line-caps."""
    import tkinter as tk

    bbox = (cx - r, cy - r, cx + r, cy + r)
    # cap_r slightly smaller than half-width to avoid visual overshoot
    cap_r = width / 2 - 1

    # Visible gray track (full circle — use 359.99 to avoid tkinter extent=360 blank-render bug)
    cv.create_arc(*bbox, start=90, extent=-359.99, style=tk.ARC, width=width, outline=TRACK_COLOR)

    extent = _ring_extent(used_pct)
    if extent is None:
        return
    cv.create_arc(*bbox, start=90, extent=extent, style=tk.ARC, width=width, outline=color)

    # Round start cap: always at top (angle 90° on unit circle)
    cap_kw = dict(fill=color, outline=color)
    cv.create_oval(cx - cap_r, cy - r - cap_r, cx + cap_r, cy - r + cap_r, **cap_kw)

    # Round end cap (only if not a full circle)
    if abs(extent) < 359:
        end_rad = math.radians(90.0 + extent)   # extent is negative
        ex = cx + r * math.cos(end_rad)
        ey = cy - r * math.sin(end_rad)
        cv.create_oval(ex - cap_r, ey - cap_r, ex + cap_r, ey + cap_r, **cap_kw)


def _rounded_rect(canvas: Any, x1: int, y1: int, x2: int, y2: int,
                  radius: int, **kwargs: Any) -> Any:
    """Draw a smooth rounded rectangle on a tkinter Canvas."""
    radius = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=18, **kwargs)


def _collapsed_panel_layers(width: int, height: int) -> list[dict[str, Any]]:
    return []


def _configure_transparent_chrome(root: Any) -> str:
    """Use a transparent outer shell when the current Tk build supports it."""
    try:
        root.attributes("-transparent", True)
    except Exception:
        root.configure(bg=BG_WINDOW)
        return BG_WINDOW
    root.configure(bg=TRANSPARENT_BG)
    return TRANSPARENT_BG


def _install_macos_blur(root: Any, *, radius: int = WINDOW_RADIUS) -> bool:
    try:
        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSColor,
            NSMakeRect,
            NSWindow,
            NSWindowBelow,
            NSWindowStyleMaskBorderless,
            NSViewHeightSizable,
            NSViewWidthSizable,
            NSVisualEffectView,
        )
    except Exception:
        return False

    try:
        root.update_idletasks()
        tk_window = _find_tk_window(root)
        if tk_window is None:
            return False
        x, y, width, height = _macos_frame_from_tk_geometry(
            screen_height=root.winfo_screenheight(),
            x=root.winfo_x(),
            y=root.winfo_y(),
            width=max(root.winfo_width(), root.winfo_reqwidth(), 1),
            height=max(root.winfo_height(), root.winfo_reqheight(), 1),
        )
        frame = NSMakeRect(x, y, width, height)

        blur_window = getattr(root, "_codex_blur_window", None)
        blur = getattr(root, "_codex_blur_view", None)
        if blur_window is None or blur is None:
            blur_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            blur_window.setOpaque_(False)
            blur_window.setBackgroundColor_(NSColor.clearColor())
            blur_window.setIgnoresMouseEvents_(True)
            blur_window.setLevel_(tk_window.level())
            blur = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
            blur_window.setContentView_(blur)
            root._codex_blur_window = blur_window
            root._codex_blur_view = blur
        else:
            blur_window.setFrame_display_(frame, True)
            blur.setFrame_(NSMakeRect(0, 0, width, height))

        config = _macos_blur_config()
        blur_window.setAlphaValue_(config["alpha"])
        blur.setMaterial_(config["material_value"])
        blur.setBlendingMode_(config["blending_mode_value"])
        blur.setState_(config["state_value"])
        blur.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        blur.setWantsLayer_(True)

        layer = blur.layer()
        if layer is not None:
            layer.setCornerRadius_(float(radius))
            layer.setMasksToBounds_(True)

        blur_window.orderFrontRegardless()
        root.lift()
        blur_window.orderWindow_relativeTo_(NSWindowBelow, tk_window.windowNumber())
        return True
    except Exception:
        return False


def _find_tk_window(root: Any) -> Any | None:
    from AppKit import NSApplication

    title = root.title()
    for window in NSApplication.sharedApplication().windows():
        try:
            if str(window.title()) == title:
                return window
        except Exception:
            continue
    return None


def _close_macos_blur(root: Any) -> None:
    blur_window = getattr(root, "_codex_blur_window", None)
    if blur_window is None:
        return
    try:
        blur_window.close()
    except Exception:
        pass
    root._codex_blur_window = None
    root._codex_blur_view = None


def _rounded_card_shell_options(background: str) -> dict[str, Any]:
    return {
        "bg": background,
        "width": 1,
        "height": 1,
        "highlightthickness": 0,
        "bd": 0,
    }


def _rounded_card(parent: Any, *, fill: str = TRANSPARENT_BG,
                  radius: int = CARD_RADIUS, pad_x: int = 10,
                  pad_y: int = 8, shell_bg: str = TRANSPARENT_BG) -> tuple[Any, Any]:
    """Return (canvas shell, body frame) with a rounded card background."""
    import tkinter as tk

    shell = tk.Canvas(parent, **_rounded_card_shell_options(shell_bg))
    body = tk.Frame(shell, bg=fill)
    window_id = shell.create_window(pad_x, pad_y, anchor="nw", window=body)

    def redraw(_event: Any | None = None) -> None:
        width = max(shell.winfo_width(), body.winfo_reqwidth() + pad_x * 2)
        height = max(shell.winfo_height(), body.winfo_reqheight() + pad_y * 2)
        shell.delete("card-bg")
        if fill != TRANSPARENT_BG:
            _rounded_rect(shell, 1, 1, width - 2, height - 2, radius,
                          fill=fill, outline=BORDER, tags="card-bg")
            shell.tag_lower("card-bg")
        shell.itemconfigure(window_id, width=max(1, width - pad_x * 2 - 4))

    def sync_size(_event: Any | None = None) -> None:
        shell.configure(height=body.winfo_reqheight() + pad_y * 2 + 4)
        redraw()

    shell._codex_sync_size = sync_size
    shell.bind("<Configure>", redraw)
    body.bind("<Configure>", sync_size)
    return shell, body


def _sync_rounded_card(shell: Any) -> None:
    sync_size = getattr(shell, "_codex_sync_size", None)
    if sync_size is None:
        return
    shell.update_idletasks()
    sync_size()


def build_view_model(aggregate: UsageAggregate) -> dict[str, Any]:
    return {
        "quota": _quota_view(aggregate),
        "today": _totals_view(aggregate.today),
        "month": _totals_view(aggregate.month),
        "projects": [_project_view(project) for project in aggregate.top_projects],
        "last_updated": aggregate.last_updated,
    }


def run_ui(
    aggregate: UsageAggregate,
    refresh_fn: Any | None = None,
    runtime_factory: Any | None = None,
) -> None:
    try:
        import tkinter as tk
        from tkinter import font as tkfont
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "tkinter is not available for this Python. "
            "Use python3.13 main.py --demo or python3.13 main.py --ui."
        ) from exc

    root = tk.Tk(className="CodexMonitor")

    # macOS: suppress Dock icon and app switcher entry for floating-widget style.
    # Works both when launched directly and via .app bundle (LSUIElement only
    # applies when the process is the bundle's main process).
    try:
        import ctypes, ctypes.util
        _appkit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
        _objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        _objc.objc_getClass.restype = ctypes.c_void_p
        _objc.sel_registerName.restype = ctypes.c_void_p
        _objc.objc_msgSend.restype = ctypes.c_void_p
        _objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        NSApplication = _objc.objc_getClass(b"NSApplication")
        sel_shared = _objc.sel_registerName(b"sharedApplication")
        sel_policy = _objc.sel_registerName(b"setActivationPolicy:")
        app = _objc.objc_msgSend(NSApplication, sel_shared)
        _objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        _objc.objc_msgSend(app, sel_policy, 1)  # NSApplicationActivationPolicyAccessory
    except Exception:
        pass

    window = CodexMonitorWindow(
        root,
        build_view_model(aggregate),
        tkfont,
        refresh_fn=refresh_fn,
    )
    if runtime_factory is not None:
        window.runtime = runtime_factory(root, window)
    root.mainloop()


def _totals_view(totals: TokenTotals) -> dict[str, str]:
    return {
        "codex": format_millions(totals.codex_tokens),
        "claude": f"~{format_millions(totals.claude_tokens)}",
        "total": format_millions(totals.total_tokens),
    }


def _project_view(project: ProjectTotal) -> dict[str, Any]:
    return {
        "name": project.display_name or project.project,
        "today": format_millions(project.today_tokens),
        "month": format_millions(project.total_tokens),
        "percent": format_percent(project.month_percent),
        "tooltip": "\n".join(project.sample_cwds),
    }


def _quota_view(aggregate: UsageAggregate) -> list[dict[str, Any]]:
    quota = aggregate.quota
    if quota is None:
        return [
            {"label": "5小时余额", "percent_value": None, "resets_at": None, "window_minutes": 300},
            {"label": "周限额", "percent_value": None, "resets_at": None, "window_minutes": 10080},
        ]
    return [
        _quota_window_view("5小时余额", quota.primary),
        _quota_window_view("周限额", quota.secondary),
    ]


def _quota_window_view(label: str, window: Any) -> dict[str, Any]:
    if window is None or window.used_percent is None:
        return {
            "label": label,
            "percent_value": None,
            "resets_at": None,
            "window_minutes": getattr(window, "window_minutes", None),
        }
    return {
        "label": label,
        "percent_value": float(window.used_percent),
        "resets_at": window.resets_at,
        "window_minutes": window.window_minutes,
    }


def _quota_percent_value(item: dict[str, Any]) -> float | None:
    value = item.get("percent_value")
    return float(value) if value is not None else None


def _quota_center_text(item: dict[str, Any]) -> str:
    value = _quota_percent_value(item)
    return "—" if value is None else f"{value:.0f}%"


def _quota_ring_used_pct(item: dict[str, Any]) -> float:
    value = _quota_percent_value(item)
    return value if value is not None else 0.0


@dataclass(frozen=True)
class Fonts:
    label: tuple[str, int, str]
    value: tuple[str, int, str]
    title: tuple[str, int, str]
    caption: tuple[str, int, str]
    btn: tuple[str, int, str]
    num_large: tuple[str, int, str]
    num_xlarge: tuple[str, int, str]


@dataclass
class WindowState:
    x: int = 80
    y: int = 80
    collapsed: bool = False


def load_window_state(path: Path = STATE_PATH) -> WindowState:
    if not path.exists():
        return WindowState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return WindowState()
    return WindowState(
        x=int(data.get("x", 80)),
        y=int(data.get("y", 80)),
        collapsed=bool(data.get("collapsed", False)),
    )


def save_window_state(state: WindowState, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"x": state.x, "y": state.y, "collapsed": state.collapsed}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clamped_window_position(
    root: Any,
    *,
    width: int,
    height: int,
    state: WindowState,
    clamp_y: bool = True,
) -> tuple[int, int]:
    screen_w = max(1, int(root.winfo_screenwidth()))
    screen_h = max(1, int(root.winfo_screenheight()))
    max_x = max(0, screen_w - width)
    max_y = max(0, screen_h - height) if clamp_y else max(0, state.y)
    x = min(max(0, state.x), max_x)
    y = min(max(0, state.y), max_y)
    return x, y


class CodexMonitorWindow:
    def __init__(
        self,
        root: "tk.Tk",
        view_model: dict[str, Any],
        tkfont: Any,
        refresh_fn: Any | None = None,
        state_path: Path = STATE_PATH,
    ) -> None:
        self.root = root
        self.view_model = view_model
        self.refresh_fn = refresh_fn
        self.state_path = state_path
        self.state = load_window_state(self.state_path)
        if not self.state.collapsed:
            self.state.collapsed = True
            save_window_state(self.state, self.state_path)
        self._drag_offset = (0, 0)
        self._press_root: tuple[int, int] | None = None
        self._capsule_dragging = False
        self._countdown_after_id: str | None = None
        self._cd_labels: list[Any] = []   # countdown label refs for update
        self._popover_after_id: str | None = None
        self._project_popover: Any | None = None
        self._popover_pointer_inside = False
        self._capsule_pointer_inside = False
        self._refresh_lock = threading.Lock()
        self._refresh_in_progress = False
        self._queued_refresh: RefreshRequest | None = None
        self.container: Any | None = None
        self.runtime: Any | None = None
        self.fonts = _fonts(root, tkfont)
        root.title("Codex Monitor")
        self.chrome_bg = _configure_transparent_chrome(root)
        # macOS: overrideredirect BEFORE -topmost (order matters)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", WINDOW_ALPHA)
        root.geometry(f"+{self.state.x}+{self.state.y}")
        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)
        root.bind("<ButtonRelease-1>", self._end_drag)
        root.bind("<Escape>", lambda e: self._on_close())
        root.bind("<Command-q>", lambda e: self._on_close())
        # Re-apply topmost after event loop starts (macOS timing fix)
        root.after(150, lambda: root.attributes("-topmost", True))
        self._build()

    # ──────────────────────────────────────────────────────────────────
    # Build

    def _build(self) -> None:
        import tkinter as tk

        self._cd_labels = []
        self.container = tk.Frame(self.root, bg=self._container_bg())
        self.container.pack(fill="both", expand=True)

        self._build_collapsed()
        self._start_countdown()

    def _build_collapsed(self) -> None:
        import tkinter as tk

        W = COLLAPSED_W
        H = COLLAPSED_H
        self._set_window_geometry(W, H)
        self.root.resizable(False, False)

        cv = tk.Canvas(
            self.container,
            width=W,
            height=H,
            bg=self._container_bg(),
            highlightthickness=0,
            bd=0,
        )
        cv.pack()
        self._bind_capsule_pointer(cv)
        _rounded_rect(
            cv,
            2,
            2,
            W - 2,
            H - 2,
            H // 2,
            **_capsule_hit_options(),
            tags=("capsule-hit",),
        )
        for layer in _collapsed_panel_layers(W, H):
            _rounded_rect(
                cv,
                layer["x1"],
                layer["y1"],
                layer["x2"],
                layer["y2"],
                layer["radius"],
                fill=layer["fill"],
                outline=layer["outline"],
            )

        quota = self.view_model["quota"]
        pct0 = _quota_ring_used_pct(quota[0])   # 5h used %
        pct1 = _quota_ring_used_pct(quota[1])   # weekly used %

        left_x = 43
        right_x = W - 43
        center_y = H // 2
        ring_radius = 24
        ring_width = 8
        _draw_ring(cv, left_x, center_y, ring_radius, ring_width, pct0, COLOR_5H)
        _draw_ring(cv, right_x, center_y, ring_radius, ring_width, pct1, COLOR_WEEK)

        cv.create_text(
            left_x,
            center_y - 4,
            text=_quota_center_text(quota[0]).rstrip("%"),
            fill=TEXT_ON_GLASS,
            font=(self.fonts.num_large[0], 17, "bold"),
            anchor="center",
        )
        cv.create_text(
            left_x,
            center_y + 13,
            text="5h",
            fill=COLOR_5H,
            font=(self.fonts.caption[0], 9, "normal"),
            anchor="center",
        )
        cv.create_text(
            right_x,
            center_y - 4,
            text=_quota_center_text(quota[1]).rstrip("%"),
            fill=TEXT_ON_GLASS,
            font=(self.fonts.num_large[0], 17, "bold"),
            anchor="center",
        )
        cv.create_text(
            right_x,
            center_y + 13,
            text="week",
            fill=COLOR_WEEK,
            font=(self.fonts.caption[0], 9, "normal"),
            anchor="center",
        )

        cv.create_line(W // 2 - 40, H // 2, W // 2 + 40, H // 2, fill=BORDER)
        cd0_lbl = tk.Label(
            self.container,
            text="--",
            bg=self._panel_bg(),
            fg=COLOR_5H,
            font=(self.fonts.caption[0], 11, "normal"),
        )
        cd1_lbl = tk.Label(
            self.container,
            text="--",
            bg=self._panel_bg(),
            fg=COLOR_WEEK,
            font=(self.fonts.caption[0], 11, "normal"),
        )
        cv.create_window(W // 2, H // 2 - 13, anchor="center", window=cd0_lbl)
        cv.create_window(W // 2, H // 2 + 14, anchor="center", window=cd1_lbl)
        for widget in (cd0_lbl, cd1_lbl):
            self._bind_capsule_pointer(widget)
        self._cd_labels = [cd0_lbl, cd1_lbl]

    def _build_expanded(self) -> None:
        import tkinter as tk

        # Set a generous initial height; will be corrected after widgets are built
        self._set_window_geometry(EXPANDED_W, 900, clamp_y=False)
        self.root.resizable(False, False)
        spacing = _expanded_spacing()

        # ── Title bar: drag handle + × close ──────────────────────────
        title_bar = tk.Frame(self.container, bg=self._container_bg(), height=spacing["title_height"])
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        refresh_symbol, collapse_symbol, close_symbol = _expanded_toolbar_symbols()
        refresh_lbl = _action_label(title_bar, refresh_symbol, self._panel_bg(), COLOR_5H,
                                    self.fonts.btn, self._refresh)
        collapse_lbl = _action_label(title_bar, collapse_symbol, self._panel_bg(), COLOR_WEEK,
                                     self.fonts.btn, self._toggle_collapsed)
        close_lbl = _action_label(title_bar, close_symbol, self._panel_bg(), TEXT_SECONDARY,
                                  self.fonts.btn, self._on_close)
        refresh_lbl.pack(side="left", padx=(8, 2), pady=1)
        collapse_lbl.pack(side="left", padx=(2, 0), pady=1)
        close_lbl.pack(side="right", padx=(0, 8), pady=1)

        # ── Quota ──────────────────────────────────────────────────────
        self._quota_expanded(self.container, self.view_model["quota"])

        # ── Separator ─────────────────────────────────────────────────
        tk.Frame(self.container, bg=BORDER, height=1).pack(fill="x", padx=spacing["side_pad"])

        # ── Projects ───────────────────────────────────────────────────
        self._projects_expanded(
            self.container,
            self.view_model["projects"],
            month_total=self.view_model["month"]["total"],
            today_total=self.view_model["today"]["total"],
        )

        # ── Footer: text buttons ───────────────────────────────────────
        self._footer(self.container)

        # Shrink window to actual content height (avoids blank space at bottom)
        self.root.update_idletasks()
        h = self.container.winfo_reqheight()
        self._set_window_geometry(EXPANDED_W, h)

    def _container_bg(self) -> str:
        if self.chrome_bg == TRANSPARENT_BG:
            return TRANSPARENT_BG
        return BG_WINDOW

    def _panel_bg(self) -> str:
        if self.chrome_bg == TRANSPARENT_BG:
            return TRANSPARENT_BG
        return BG_SECTION

    def _set_window_geometry(self, width: int, height: int, *, clamp_y: bool = True) -> None:
        x, y = _clamped_window_position(
            self.root,
            width=width,
            height=height,
            state=self.state,
            clamp_y=clamp_y,
        )
        if (x, y) != (self.state.x, self.state.y):
            self.state.x = x
            self.state.y = y
            save_window_state(self.state, self.state_path)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.after(0, lambda: _install_macos_blur(self.root, radius=WINDOW_RADIUS))

    def _quota_expanded(self, parent: "tk.Widget", quota: list[dict[str, Any]]) -> None:
        import tkinter as tk

        spacing = _expanded_spacing()
        bg = self._panel_bg()
        outer = tk.Frame(parent, bg=self._container_bg())
        outer.pack(fill="x", padx=spacing["side_pad"], pady=spacing["quota_pady"])

        colors = [COLOR_5H, COLOR_WEEK]
        for i, item in enumerate(quota):
            color = colors[i]
            pct_val = item.get("percent_value")
            used_pct = pct_val if pct_val is not None else None
            remain_pct = (100.0 - pct_val) if pct_val is not None else None

            cell_shell, cell = _rounded_card(outer)
            cell_shell.pack(side="left", fill="x", expand=True,
                            padx=(0, 10 if i == 0 else 0))

            # Label
            tk.Label(cell, text=item["label"], bg=bg, fg=color,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10, pady=(8, 0))

            # Large remaining % (centered)
            remain_str = f"{remain_pct:.0f}%" if remain_pct is not None else "—"
            tk.Label(cell, text=remain_str, bg=bg, fg=TEXT_MONO,
                     font=(self.fonts.num_xlarge[0], 32, "bold"),
                     anchor="center").pack(fill="x", padx=10)

            # Used % subtitle
            used_str = f"已使用 {used_pct:.0f}%" if used_pct is not None else "待更新"
            tk.Label(cell, text=used_str, bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10)

            # Countdown
            cd_text = f"↺ {_fmt_countdown(item.get('resets_at'), item.get('window_minutes'))}"
            tk.Label(cell, text=cd_text, bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10, pady=(0, 8))
            _sync_rounded_card(cell_shell)

    def _projects_expanded(
        self,
        parent: "tk.Widget",
        projects: list[dict[str, Any]],
        month_total: str = "",
        today_total: str = "",
    ) -> None:
        import tkinter as tk

        spacing = _expanded_spacing()
        bg = self._panel_bg()
        outer_shell, outer = _rounded_card(parent, pad_x=12, pad_y=10)
        outer_shell.pack(fill="x", padx=spacing["side_pad"], pady=spacing["project_pady"])

        # Section header
        sec_hdr = tk.Frame(outer, bg=bg)
        sec_hdr.pack(fill="x")
        tk.Label(sec_hdr, text="项目 Top 10", bg=bg, fg=TEXT_PRIMARY,
                 font=self.fonts.title, anchor="w").pack(side="left")
        if month_total or today_total:
            tk.Label(sec_hdr, text=f"30天 {month_total}  今日 {today_total}",
                     bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="e").pack(side="right")

        if not projects:
            tk.Label(outer, text="暂无数据", bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.label).pack(anchor="w", pady=8)
            tk.Label(outer, text="结合 Claude Code 和 Codex 本地日志估算", bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="e").pack(anchor="e")
            _sync_rounded_card(outer_shell)
            return

        # Grid for aligned columns
        grid = tk.Frame(outer, bg=bg)
        grid.pack(fill="x", pady=(6, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, minsize=64)
        grid.columnconfigure(2, minsize=64)
        grid.columnconfigure(3, minsize=52)

        # Column headers
        for col, (text, anchor) in enumerate([("项目", "w"), ("今日", "e"), ("30天", "e"), ("占比", "e")]):
            tk.Label(grid, text=text, bg=bg, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor=anchor).grid(
                         row=0, column=col, sticky="ew", pady=(2, 4))

        for row_i, project in enumerate(projects, start=1):
            name = tk.Label(grid, text=project["name"], bg=bg, fg=TEXT_PRIMARY,
                            font=self.fonts.label, anchor="w")
            name.grid(row=row_i, column=0, sticky="w", pady=2)
            if project["tooltip"]:
                Tooltip(name, project["tooltip"])
            for col, key in [(1, "today"), (2, "month"), (3, "percent")]:
                tk.Label(grid, text=project[key], bg=bg, fg=TEXT_MONO,
                         font=self.fonts.caption, anchor="e").grid(
                             row=row_i, column=col, sticky="e", pady=2)

        # Note row: "结合 Claude Code 和 Codex 本地日志估算" right-aligned below project rows
        note_row = tk.Frame(outer, bg=bg)
        note_row.pack(fill="x", pady=(4, 0))
        tk.Label(note_row, text="结合 Claude Code 和 Codex 本地日志估算", bg=bg, fg=TEXT_SECONDARY,
                 font=self.fonts.caption, anchor="e").pack(anchor="e")
        _sync_rounded_card(outer_shell)

    def _footer(self, parent: "tk.Widget") -> None:
        if not _show_expanded_footer_actions():
            return
        import tkinter as tk

        spacing = _expanded_spacing()
        tk.Frame(parent, bg=BORDER, height=1).pack(
            fill="x",
            pady=spacing["footer_divider_pady"],
        )

        bar = tk.Frame(parent, bg=BG_WINDOW)
        bar.pack(fill="x", padx=spacing["side_pad"], pady=spacing["footer_bar_pady"])

        btn_kw = dict(
            bg=BG_WINDOW, fg=TEXT_PRIMARY,
            font=self.fonts.label,
            relief="flat", bd=0,
            padx=14, pady=spacing["button_pady"],
            cursor="hand2",
            activebackground=BORDER,
            activeforeground=TEXT_PRIMARY,
        )
        tk.Button(bar, text="刷新", command=self._refresh, **btn_kw).pack(
            side="right", padx=(6, 0))
        tk.Button(bar, text="收起", command=self._toggle_collapsed, **btn_kw).pack(
            side="right")

    # ──────────────────────────────────────────────────────────────────
    # Countdown timer

    def _start_countdown(self) -> None:
        self._cancel_countdown()
        self._do_countdown()

    def _cancel_countdown(self) -> None:
        if self._countdown_after_id is not None:
            try:
                self.root.after_cancel(self._countdown_after_id)
            except Exception:
                pass
            self._countdown_after_id = None

    def _do_countdown(self) -> None:
        quota = self.view_model["quota"]
        pairs = [(0, quota[0]), (1, quota[1])]
        for i, q in pairs:
            if i < len(self._cd_labels) and self._cd_labels[i] is not None:
                self._cd_labels[i].configure(
                    text=_fmt_compact_countdown(q.get("resets_at"), q.get("window_minutes"))
                )
        self._countdown_after_id = self.root.after(60000, self._do_countdown)

    # ──────────────────────────────────────────────────────────────────
    # Hover popover

    def _bind_capsule_pointer(self, widget: Any) -> None:
        widget.bind("<Enter>", self._capsule_enter)
        widget.bind("<Leave>", self._capsule_leave)
        widget.bind("<ButtonPress-1>", self._capsule_press)
        widget.bind("<B1-Motion>", self._capsule_motion)
        widget.bind("<ButtonRelease-1>", self._capsule_release)

    def _capsule_enter(self, _event: Any | None = None) -> None:
        self._capsule_pointer_inside = True

    def _capsule_press(self, event: Any) -> str:
        self._capsule_pointer_inside = True
        self._capsule_dragging = False
        self._press_root = (event.x_root, event.y_root)
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )
        return "break"

    def _capsule_motion(self, event: Any) -> str:
        if self._press_root is None:
            self._capsule_press(event)
        start_x, start_y = self._press_root or (event.x_root, event.y_root)
        if abs(event.x_root - start_x) > 3 or abs(event.y_root - start_y) > 3:
            self._capsule_dragging = True
        if self._capsule_dragging:
            self._on_drag(event)
        return "break"

    def _capsule_release(self, event: Any) -> str:
        if self._capsule_dragging:
            self._end_drag(event)
        else:
            self._capsule_click(event)
        self._press_root = None
        self._capsule_dragging = False
        return "break"

    def _capsule_click(self, _event: Any | None = None) -> None:
        self._capsule_pointer_inside = True
        self._cancel_project_popover_timer()
        self._show_project_popover()

    def _capsule_leave(self, _event: Any | None = None) -> None:
        self._capsule_pointer_inside = False
        self._cancel_project_popover_timer()
        self._defer_maybe_hide_project_popover()

    def _popover_enter(self, _event: Any | None = None) -> None:
        self._popover_pointer_inside = True

    def _popover_leave(self, _event: Any | None = None) -> None:
        self._popover_pointer_inside = False
        self._defer_maybe_hide_project_popover()

    def _cancel_project_popover_timer(self) -> None:
        if self._popover_after_id is None:
            return
        try:
            self.root.after_cancel(self._popover_after_id)
        except Exception:
            pass
        self._popover_after_id = None

    def _defer_maybe_hide_project_popover(self) -> None:
        after = getattr(self.root, "after", None)
        if callable(after):
            after(80, self._maybe_hide_project_popover)
        else:
            self._maybe_hide_project_popover()

    def _maybe_hide_project_popover(self) -> None:
        if self._capsule_pointer_inside or self._popover_pointer_inside:
            return
        self._hide_project_popover()

    def _show_project_popover(self) -> None:
        self._popover_after_id = None
        if not self._capsule_pointer_inside or self._project_popover is not None:
            return

        import tkinter as tk

        popover = tk.Toplevel(self.root)
        popover.title("Codex Monitor Projects")
        popover.overrideredirect(True)
        popover.attributes("-topmost", True)
        popover.attributes("-alpha", PROJECT_POPOVER_ALPHA)
        bg = BG_WINDOW
        popover.configure(bg=bg)
        self._project_popover = popover
        self._popover_pointer_inside = False

        frame = tk.Frame(popover, bg=bg)
        frame.pack(fill="both", expand=True, padx=17, pady=14)
        self._bind_popover_hover(frame)

        header = tk.Frame(frame, bg=bg)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="项目 Top 10",
            bg=bg,
            fg=TEXT_ON_GLASS,
            font=(self.fonts.title[0], 14, "bold"),
            anchor="w",
        ).pack(side="left")
        tk.Label(
            header,
            text=f"30天 {self.view_model['month']['total']} · 今日 {self.view_model['today']['total']}",
            bg=bg,
            fg=TEXT_MUTED_GLASS,
            font=(self.fonts.caption[0], 11, "normal"),
            anchor="e",
        ).pack(side="right")

        grid = tk.Frame(frame, bg=bg)
        grid.pack(fill="x")
        for col, width in [(0, 130), (1, 66), (2, 66), (3, 42)]:
            grid.columnconfigure(col, minsize=width)
        headers = [("项目", "w"), ("今日", "e"), ("30天", "e"), ("占比", "e")]
        for col, (text, anchor) in enumerate(headers):
            tk.Label(
                grid,
                text=text,
                bg=bg,
                fg=TEXT_MUTED_GLASS,
                font=(self.fonts.caption[0], 11, "normal"),
                anchor=anchor,
            ).grid(row=0, column=col, sticky="ew", padx=(0, 10 if col < 3 else 0), pady=(0, 6))

        projects = self.view_model["projects"][:_project_popover_limit()]
        if not projects:
            tk.Label(
                grid,
                text="暂无数据",
                bg=bg,
                fg=TEXT_MUTED_GLASS,
                font=self.fonts.label,
                anchor="w",
            ).grid(row=1, column=0, columnspan=4, sticky="w", pady=8)
        for row_i, project in enumerate(projects, start=1):
            tk.Label(
                grid,
                text=project["name"],
                bg=bg,
                fg=TEXT_ON_GLASS,
                font=(self.fonts.label[0], 12, "normal"),
                anchor="w",
            ).grid(row=row_i, column=0, sticky="ew", padx=(0, 10), pady=2)
            for col, key in [(1, "today"), (2, "month"), (3, "percent")]:
                tk.Label(
                    grid,
                    text=project[key],
                    bg=bg,
                    fg=TEXT_ON_GLASS if key != "percent" else TEXT_MUTED_GLASS,
                    font=(self.fonts.caption[0], 12, "normal"),
                    anchor="e",
                ).grid(row=row_i, column=col, sticky="e", padx=(0, 10 if col < 3 else 0), pady=2)

        tk.Label(
            frame,
            text="结合 Claude Code 和 Codex 本地日志估算",
            bg=bg,
            fg=TEXT_MUTED_GLASS,
            font=(self.fonts.caption[0], 10, "normal"),
            anchor="e",
        ).pack(fill="x", pady=(10, 0))

        popover.update_idletasks()
        height = max(1, popover.winfo_reqheight())
        width = PROJECT_POPOVER_W
        x = self.root.winfo_x()
        y = max(0, self.root.winfo_y() - height - 10)
        popover.geometry(f"{width}x{height}+{x}+{y}")
        popover.bind("<Enter>", self._popover_enter)
        popover.bind("<Leave>", self._popover_leave)
        if _project_popover_uses_native_blur():
            popover.after(0, lambda: _install_macos_blur(popover, radius=26))

    def _bind_popover_hover(self, widget: Any) -> None:
        widget.bind("<Enter>", self._popover_enter)
        widget.bind("<Leave>", self._popover_leave)

    def _hide_project_popover(self) -> None:
        self._cancel_project_popover_timer()
        popover = self._project_popover
        if popover is None:
            return
        self._project_popover = None
        self._popover_pointer_inside = False
        try:
            _close_macos_blur(popover)
            popover.destroy()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # Actions

    def _toggle_collapsed(self) -> None:
        self._cancel_countdown()
        self._hide_project_popover()
        self.state.collapsed = not self.state.collapsed
        save_window_state(self.state, self.state_path)
        if self.container is not None:
            self.container.destroy()
        self._cd_labels = []
        self.container = None
        self._build()

    def _refresh(self) -> None:
        self.refresh_async(RefreshRequest.manual())

    def refresh_async(self, request: RefreshRequest) -> bool:
        if self.refresh_fn is None:
            return False
        self._ensure_refresh_state()

        with self._refresh_lock:
            if self._refresh_in_progress:
                self._queued_refresh = _merge_refresh_requests(self._queued_refresh, request)
                return False
            self._refresh_in_progress = True

        self._start_refresh_thread(request)
        return True

    def _start_refresh_thread(self, request: RefreshRequest) -> None:
        def _run() -> None:
            try:
                updated = self.refresh_fn(request)
            except Exception:
                self.root.after(0, self._finish_refresh)
                return
            self.root.after(0, lambda: self._finish_refresh(updated))

        threading.Thread(target=_run, daemon=True).start()

    def _finish_refresh(self, aggregate: UsageAggregate | None = None) -> None:
        self._ensure_refresh_state()
        if aggregate is not None:
            self.apply_aggregate(aggregate)

        with self._refresh_lock:
            queued = self._queued_refresh
            self._queued_refresh = None
            if queued is None:
                self._refresh_in_progress = False
                return

        self._start_refresh_thread(queued)

    def _ensure_refresh_state(self) -> None:
        if not hasattr(self, "_refresh_lock"):
            self._refresh_lock = threading.Lock()
        if not hasattr(self, "_refresh_in_progress"):
            self._refresh_in_progress = False
        if not hasattr(self, "_queued_refresh"):
            self._queued_refresh = None

    def apply_aggregate(self, aggregate: UsageAggregate) -> None:
        self._cancel_countdown()
        self._hide_project_popover()
        self.view_model = build_view_model(aggregate)
        if self.container is not None:
            self.container.destroy()
        self._cd_labels = []
        self.container = None
        self._build()

    # ──────────────────────────────────────────────────────────────────
    # Drag

    def _start_drag(self, event: Any) -> None:
        self._hide_project_popover()
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _on_drag(self, event: Any) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")
        _install_macos_blur(self.root, radius=WINDOW_RADIUS)

    def _end_drag(self, _event: Any) -> None:
        self.state.x = self.root.winfo_x()
        self.state.y = self.root.winfo_y()
        save_window_state(self.state, self.state_path)

    def _on_close(self) -> None:
        self._cancel_countdown()
        self._hide_project_popover()
        self.state.x = self.root.winfo_x()
        self.state.y = self.root.winfo_y()
        save_window_state(self.state, self.state_path)
        _close_macos_blur(self.root)
        self.root.destroy()


# ──────────────────────────────────────────────────────────────────────
# Helpers


def _action_label(parent: Any, text: str, bg: str, fg: str,
                  font: tuple, command: Any) -> Any:
    """Flat icon label — no hover effect, no cursor change."""
    import tkinter as tk

    lbl = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, padx=4, pady=2)
    lbl.bind("<Button-1>", lambda e: command())
    return lbl


def _merge_refresh_requests(
    existing: RefreshRequest | None,
    incoming: RefreshRequest,
) -> RefreshRequest:
    if existing is None:
        return incoming
    if existing.reason == "manual" or incoming.reason == "manual":
        return RefreshRequest.manual()

    modified_values = [
        value
        for value in (existing.claude_modified_since, incoming.claude_modified_since)
        if value is not None
    ]
    max_file_values = [
        value
        for value in (existing.claude_max_files, incoming.claude_max_files)
        if value is not None
    ]
    return RefreshRequest(
        reason=incoming.reason,
        claude_modified_since=min(modified_values) if modified_values else None,
        claude_max_files=max(max_file_values) if max_file_values else None,
    )


class Tooltip:
    def __init__(self, widget: "tk.Widget", text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: Any | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event: Any) -> None:
        import tkinter as tk

        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#1D1D1F", fg="#FFFFFF",
                 padx=8, pady=4, justify="left").pack()

    def _hide(self, _event: Any) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


def _fonts(root: "tk.Tk", tkfont: Any) -> Fonts:
    families = set(tkfont.families(root))
    sans = "SF Pro Text" if "SF Pro Text" in families else "System"
    mono = "SF Pro Mono" if "SF Pro Mono" in families else "Menlo"
    return Fonts(
        label=(sans, 13, "normal"),
        value=(mono, 15, "normal"),
        title=(sans, 14, "bold"),
        caption=(sans, 12, "normal"),
        btn=(sans, 16, "normal"),
        num_large=(mono, 16, "normal"),
        num_xlarge=(mono, 22, "normal"),
    )
