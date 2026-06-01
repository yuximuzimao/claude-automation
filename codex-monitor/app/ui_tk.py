"""Tkinter MVP UI for Codex Monitor."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

from app.aggregate import ProjectTotal, TokenTotals, UsageAggregate
from app.runtime import RefreshRequest

if TYPE_CHECKING:
    import tkinter as tk


BG_WINDOW = "#F2F2F7"
BG_SECTION = "#FFFFFF"
BORDER = "#E0E0E5"
TEXT_PRIMARY = "#1D1D1F"
TEXT_SECONDARY = "#8A8A8E"
TEXT_MONO = "#333333"
TRACK_COLOR = "#C8C8CE"   # visible gray track for 0% rings
COLOR_5H = "#007AFF"      # blue for 5h quota
COLOR_WEEK = "#AF52DE"    # purple for weekly quota
STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "state.json"

COLLAPSED_W = 190
COLLAPSED_H = 190
EXPANDED_W = 360


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


def _draw_ring(cv: Any, cx: float, cy: float, r: float, width: float,
               used_pct: float, color: str) -> None:
    """Draw a ring segment with round line-caps."""
    import tkinter as tk

    bbox = (cx - r, cy - r, cx + r, cy + r)
    # cap_r slightly smaller than half-width to avoid visual overshoot
    cap_r = width / 2 - 1

    # Visible gray track (full circle — use 359.99 to avoid tkinter extent=360 blank-render bug)
    cv.create_arc(*bbox, start=90, extent=-359.99, style=tk.ARC, width=width, outline=TRACK_COLOR)

    pct = max(0.0, min(100.0, used_pct))
    if pct < 0.5:
        return

    extent = -pct * 3.6  # negative = clockwise
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
        self._drag_offset = (0, 0)
        self._countdown_after_id: str | None = None
        self._cd_labels: list[Any] = []   # countdown label refs for update
        self.container: Any | None = None
        self.runtime: Any | None = None
        self.fonts = _fonts(root, tkfont)
        root.title("Codex Monitor")
        root.configure(bg=BG_WINDOW)
        # macOS: overrideredirect BEFORE -topmost (order matters)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)
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
        self.container = tk.Frame(self.root, bg=BG_WINDOW)
        self.container.pack(fill="both", expand=True)

        if self.state.collapsed:
            self._build_collapsed()
            self._start_countdown()
        else:
            self._build_expanded()

    def _build_collapsed(self) -> None:
        import tkinter as tk

        W = H = COLLAPSED_W
        self.root.geometry(f"{W}x{H}+{self.state.x}+{self.state.y}")
        self.root.resizable(False, False)

        cv = tk.Canvas(self.container, width=W, height=H, bg=BG_WINDOW, highlightthickness=0)
        cv.pack()

        quota = self.view_model["quota"]
        pct0 = quota[0].get("percent_value") or 0.0   # 5h used %
        pct1 = quota[1].get("percent_value") or 0.0   # weekly used %
        cx = cy = W // 2  # 95

        # ── Rings ─────────────────────────────────────────────────────
        # Outer: 5h (blue), r=61
        _draw_ring(cv, cx, cy, 61, 16, pct0, COLOR_5H)
        # Inner: weekly (purple), r=40
        _draw_ring(cv, cx, cy, 40, 16, pct1, COLOR_WEEK)

        # ── Center text: weekly (top, smaller) + 5h (bottom, larger) ──
        weekly_text = f"{pct1:.0f}%"
        cv.create_text(cx, cy - 14, text=weekly_text,
                       fill=COLOR_WEEK, font=(self.fonts.num_large[0], 16, "bold"),
                       anchor="center")
        fiveh_text = f"{pct0:.0f}%"
        cv.create_text(cx, cy + 13, text=fiveh_text,
                       fill=COLOR_5H, font=(self.fonts.num_xlarge[0], 22, "bold"),
                       anchor="center")

        # ── Corner buttons ─────────────────────────────────────────────
        refresh_lbl = _action_label(self.container, "↺", BG_WINDOW, COLOR_5H,
                                    self.fonts.btn, self._refresh)
        expand_lbl = _action_label(self.container, "⛶", BG_WINDOW, COLOR_WEEK,
                                   self.fonts.btn, self._toggle_collapsed)
        cv.create_window(8, 8, anchor="nw", window=refresh_lbl)
        cv.create_window(W - 8, 8, anchor="ne", window=expand_lbl)

        # ── Bottom countdowns (colored to match rings) ─────────────────
        cd0_lbl = tk.Label(self.container, text="--", bg=BG_WINDOW,
                           fg=COLOR_5H, font=self.fonts.caption)
        cd1_lbl = tk.Label(self.container, text="--", bg=BG_WINDOW,
                           fg=COLOR_WEEK, font=self.fonts.caption)
        cv.create_window(8, H - 8, anchor="sw", window=cd0_lbl)
        cv.create_window(W - 8, H - 8, anchor="se", window=cd1_lbl)
        self._cd_labels = [cd0_lbl, cd1_lbl]

    def _build_expanded(self) -> None:
        import tkinter as tk

        # Set a generous initial height; will be corrected after widgets are built
        self.root.geometry(f"{EXPANDED_W}x900+{self.state.x}+{self.state.y}")
        self.root.resizable(False, False)

        # ── Title bar: drag handle + × close ──────────────────────────
        title_bar = tk.Frame(self.container, bg=BG_WINDOW, height=26)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        close_lbl = tk.Label(title_bar, text="×", bg=BG_WINDOW, fg=TEXT_SECONDARY,
                             font=self.fonts.btn, padx=8, pady=2)
        close_lbl.pack(side="right")
        close_lbl.bind("<Button-1>", lambda e: self._on_close())

        # ── Quota ──────────────────────────────────────────────────────
        self._quota_expanded(self.container, self.view_model["quota"])

        # ── Separator ─────────────────────────────────────────────────
        tk.Frame(self.container, bg=BORDER, height=1).pack(fill="x", padx=16)

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
        self.root.geometry(f"{EXPANDED_W}x{h}+{self.state.x}+{self.state.y}")

    def _quota_expanded(self, parent: "tk.Widget", quota: list[dict[str, Any]]) -> None:
        import tkinter as tk

        outer = tk.Frame(parent, bg=BG_WINDOW)
        outer.pack(fill="x", padx=16, pady=(10, 10))

        colors = [COLOR_5H, COLOR_WEEK]
        for i, item in enumerate(quota):
            color = colors[i]
            pct_val = item.get("percent_value")
            used_pct = pct_val if pct_val is not None else None
            remain_pct = (100.0 - pct_val) if pct_val is not None else None

            cell = tk.Frame(outer, bg=BG_SECTION)
            cell.pack(side="left", fill="x", expand=True,
                      padx=(0, 10 if i == 0 else 0))

            # Label
            tk.Label(cell, text=item["label"], bg=BG_SECTION, fg=color,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10, pady=(8, 0))

            # Large remaining % (centered)
            remain_str = f"{remain_pct:.0f}%" if remain_pct is not None else "—"
            tk.Label(cell, text=remain_str, bg=BG_SECTION, fg=TEXT_MONO,
                     font=(self.fonts.num_xlarge[0], 32, "bold"),
                     anchor="center").pack(fill="x", padx=10)

            # Used % subtitle
            used_str = f"已使用 {used_pct:.0f}%" if used_pct is not None else "待更新"
            tk.Label(cell, text=used_str, bg=BG_SECTION, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10)

            # Countdown
            cd_text = f"↺ {_fmt_countdown(item.get('resets_at'), item.get('window_minutes'))}"
            tk.Label(cell, text=cd_text, bg=BG_SECTION, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="w").pack(anchor="w", padx=10, pady=(0, 8))

    def _projects_expanded(
        self,
        parent: "tk.Widget",
        projects: list[dict[str, Any]],
        month_total: str = "",
        today_total: str = "",
    ) -> None:
        import tkinter as tk

        outer = tk.Frame(parent, bg=BG_WINDOW)
        outer.pack(fill="x", padx=16, pady=(10, 0))

        # Section header
        sec_hdr = tk.Frame(outer, bg=BG_WINDOW)
        sec_hdr.pack(fill="x")
        tk.Label(sec_hdr, text="项目 Top 10", bg=BG_WINDOW, fg=TEXT_PRIMARY,
                 font=self.fonts.title, anchor="w").pack(side="left")
        if month_total or today_total:
            tk.Label(sec_hdr, text=f"30天 {month_total}  今日 {today_total}",
                     bg=BG_WINDOW, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="e").pack(side="right")

        if not projects:
            tk.Label(outer, text="暂无数据", bg=BG_WINDOW, fg=TEXT_SECONDARY,
                     font=self.fonts.label).pack(anchor="w", pady=8)
            tk.Label(outer, text="本地日志估算", bg=BG_WINDOW, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor="e").pack(anchor="e")
            return

        # Grid for aligned columns
        grid = tk.Frame(outer, bg=BG_WINDOW)
        grid.pack(fill="x", pady=(6, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, minsize=64)
        grid.columnconfigure(2, minsize=64)
        grid.columnconfigure(3, minsize=52)

        # Column headers
        for col, (text, anchor) in enumerate([("项目", "w"), ("今日", "e"), ("30天", "e"), ("占比", "e")]):
            tk.Label(grid, text=text, bg=BG_WINDOW, fg=TEXT_SECONDARY,
                     font=self.fonts.caption, anchor=anchor).grid(
                         row=0, column=col, sticky="ew", pady=(2, 4))

        for row_i, project in enumerate(projects, start=1):
            name = tk.Label(grid, text=project["name"], bg=BG_WINDOW, fg=TEXT_PRIMARY,
                            font=self.fonts.label, anchor="w")
            name.grid(row=row_i, column=0, sticky="w", pady=2)
            if project["tooltip"]:
                Tooltip(name, project["tooltip"])
            for col, key in [(1, "today"), (2, "month"), (3, "percent")]:
                tk.Label(grid, text=project[key], bg=BG_WINDOW, fg=TEXT_MONO,
                         font=self.fonts.caption, anchor="e").grid(
                             row=row_i, column=col, sticky="e", pady=2)

        # Note row: "本地日志估算" right-aligned below project rows
        note_row = tk.Frame(outer, bg=BG_WINDOW)
        note_row.pack(fill="x", pady=(4, 0))
        tk.Label(note_row, text="本地日志估算", bg=BG_WINDOW, fg=TEXT_SECONDARY,
                 font=self.fonts.caption, anchor="e").pack(anchor="e")

    def _footer(self, parent: "tk.Widget") -> None:
        import tkinter as tk

        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

        bar = tk.Frame(parent, bg=BG_WINDOW)
        bar.pack(fill="x", padx=16, pady=(8, 10))

        btn_kw = dict(
            bg=BG_WINDOW, fg=TEXT_PRIMARY,
            font=self.fonts.label,
            relief="flat", bd=0,
            padx=14, pady=5,
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
                    text=_fmt_countdown(q.get("resets_at"), q.get("window_minutes"))
                )
        self._countdown_after_id = self.root.after(60000, self._do_countdown)

    # ──────────────────────────────────────────────────────────────────
    # Actions

    def _toggle_collapsed(self) -> None:
        self._cancel_countdown()
        self.state.collapsed = not self.state.collapsed
        save_window_state(self.state, self.state_path)
        if self.container is not None:
            self.container.destroy()
        self._cd_labels = []
        self.container = None
        self._build()

    def _refresh(self) -> None:
        if self.refresh_fn is None:
            return
        import threading

        def _run() -> None:
            updated = self.refresh_fn(RefreshRequest.manual())
            self.root.after(0, lambda: self.apply_aggregate(updated))

        threading.Thread(target=_run, daemon=True).start()

    def apply_aggregate(self, aggregate: UsageAggregate) -> None:
        self._cancel_countdown()
        self.view_model = build_view_model(aggregate)
        if self.container is not None:
            self.container.destroy()
        self._cd_labels = []
        self.container = None
        self._build()

    # ──────────────────────────────────────────────────────────────────
    # Drag

    def _start_drag(self, event: Any) -> None:
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _on_drag(self, event: Any) -> None:
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _end_drag(self, _event: Any) -> None:
        self.state.x = self.root.winfo_x()
        self.state.y = self.root.winfo_y()
        save_window_state(self.state, self.state_path)

    def _on_close(self) -> None:
        self._cancel_countdown()
        self.state.x = self.root.winfo_x()
        self.state.y = self.root.winfo_y()
        save_window_state(self.state, self.state_path)
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
