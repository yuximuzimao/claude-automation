from __future__ import annotations

import tempfile
import threading
import time
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app.aggregate import ProjectTotal, TokenTotals, UsageAggregate
from app.models import CodexQuota, RateLimitWindow
from app.runtime import RefreshRequest
from app.ui_tk import (
    BG_WINDOW,
    COLLAPSED_H,
    COLLAPSED_W,
    COLOR_5H,
    COLOR_WEEK,
    CodexMonitorWindow,
    TEXT_ON_GLASS,
    TRANSPARENT_BG,
    WindowState,
    _collapsed_panel_layers,
    _capsule_hit_options,
    _clamped_window_position,
    _configure_transparent_chrome,
    _configure_visible_app_identity,
    _expanded_spacing,
    _expanded_toolbar_symbols,
    _fmt_compact_duration,
    _macos_frame_from_tk_geometry,
    _macos_blur_config,
    _project_popover_uses_native_blur,
    _project_popover_limit,
    _quota_center_text,
    _quota_ring_used_pct,
    _ring_extent,
    _rounded_card_shell_options,
    _show_expanded_footer_actions,
    _sync_rounded_card,
    build_view_model,
    format_millions,
    load_window_state,
    save_window_state,
)


class TkUiTests(unittest.TestCase):
    def test_format_millions_keeps_m_unit(self) -> None:
        self.assertEqual(format_millions(1_240_000), "1.24M")
        self.assertEqual(format_millions(90_000), "0.09M")
        self.assertEqual(format_millions(0), "0.00M")

    def test_view_model_keeps_tooltip_cwds_for_top_projects(self) -> None:
        aggregate = UsageAggregate(
            today=TokenTotals(codex_tokens=1_000_000, claude_tokens=250_000),
            month=TokenTotals(codex_tokens=3_000_000, claude_tokens=750_000),
            top_projects=(
                ProjectTotal(
                    project="chat",
                    display_name="主工作区",
                    codex_tokens=1_000_000,
                    today_codex_tokens=300_000,
                    month_percent=26.7,
                    sample_cwds=("/Users/chat",),
                ),
            ),
            quota=CodexQuota(
                primary=RateLimitWindow(used_percent=42.0, window_minutes=300),
                secondary=RateLimitWindow(used_percent=11.0, window_minutes=10080),
                timestamp="2026-06-01T13:00:00+08:00",
            ),
            last_updated="2026-06-01T13:00:00+08:00",
        )

        view_model = build_view_model(aggregate)

        self.assertEqual(view_model["today"]["codex"], "1.00M")
        self.assertEqual(view_model["today"]["claude"], "~0.25M")
        self.assertEqual(view_model["month"]["total"], "3.75M")
        self.assertEqual(view_model["quota"][0]["label"], "5小时余额")
        self.assertEqual(view_model["quota"][0]["percent_value"], 42.0)
        self.assertEqual(view_model["quota"][1]["label"], "周限额")
        self.assertEqual(view_model["quota"][1]["percent_value"], 11.0)
        self.assertEqual(view_model["projects"][0]["name"], "主工作区")
        self.assertEqual(view_model["projects"][0]["today"], "0.30M")
        self.assertEqual(view_model["projects"][0]["month"], "1.00M")
        self.assertEqual(view_model["projects"][0]["percent"], "26.7%")
        self.assertEqual(view_model["projects"][0]["tooltip"], "/Users/chat")
        self.assertNotIn("event_types", view_model)

    def test_view_model_marks_missing_quota_percent_as_unknown(self) -> None:
        aggregate = UsageAggregate(
            today=TokenTotals(),
            month=TokenTotals(),
            top_projects=(),
            quota=None,
            last_updated="2026-06-01T13:00:00+08:00",
        )

        view_model = build_view_model(aggregate)

        self.assertIsNone(view_model["quota"][0]["percent_value"])
        self.assertIsNone(view_model["quota"][1]["percent_value"])
        self.assertEqual(_quota_center_text(view_model["quota"][0]), "—")
        self.assertEqual(_quota_ring_used_pct(view_model["quota"][0]), 0.0)

    def test_quota_center_text_distinguishes_unknown_from_real_zero(self) -> None:
        self.assertEqual(_quota_center_text({"percent_value": None}), "—")
        self.assertEqual(_quota_center_text({"percent_value": 0.0}), "0%")
        self.assertEqual(_quota_center_text({"percent_value": 42.4}), "42%")

    def test_ring_extent_full_never_hits_360(self) -> None:
        # tkinter renders a blank arc at exactly ±360, which made a 100% ring
        # look empty ("reset to zero"). Extent must stay strictly inside ±360.
        extent = _ring_extent(100.0)
        self.assertIsNotNone(extent)
        self.assertLess(abs(extent), 360.0)
        self.assertAlmostEqual(extent, -359.99)
        # Over-100% input is clamped, still safe.
        self.assertAlmostEqual(_ring_extent(150.0), -359.99)

    def test_ring_extent_partial_and_too_small(self) -> None:
        self.assertAlmostEqual(_ring_extent(50.0), -180.0)
        self.assertIsNone(_ring_extent(0.0))
        self.assertIsNone(_ring_extent(0.4))

    def test_collapsed_capsule_matches_dock_height_target(self) -> None:
        self.assertEqual(COLLAPSED_W, 258)
        self.assertEqual(COLLAPSED_H, 82)

    def test_compact_duration_uses_chinese_units(self) -> None:
        self.assertEqual(_fmt_compact_duration(172), "2小时52分")
        self.assertEqual(_fmt_compact_duration(9600), "6天16小时")
        self.assertEqual(_fmt_compact_duration(45), "45分")
        self.assertEqual(_fmt_compact_duration(None), "--")

    def test_project_popover_contract(self) -> None:
        self.assertEqual(_project_popover_limit(), 10)
        self.assertFalse(_project_popover_uses_native_blur())

    def test_white_frost_palette_uses_dark_text_and_status_colors(self) -> None:
        self.assertEqual(TEXT_ON_GLASS, "#172326")
        self.assertEqual(COLOR_5H, "#5FD0C5")
        self.assertEqual(COLOR_WEEK, "#F2B866")

    def test_capsule_hit_layer_uses_textured_fill_not_solid_black(self) -> None:
        options = _capsule_hit_options()

        self.assertEqual(options["stipple"], "gray25")
        self.assertNotEqual(options["fill"], "#0B1416")
        self.assertEqual(options["fill"], "#F4F8FA")

    def test_rounded_card_shell_overrides_tk_canvas_default_size(self) -> None:
        options = _rounded_card_shell_options(BG_WINDOW)

        self.assertEqual(options["bg"], BG_WINDOW)
        self.assertEqual(options["width"], 1)
        self.assertEqual(options["height"], 1)
        self.assertEqual(options["highlightthickness"], 0)
        self.assertEqual(options["bd"], 0)

    def test_sync_rounded_card_runs_attached_size_callback(self) -> None:
        class FakeShell:
            def __init__(self) -> None:
                self.updated = False
                self.synced = False
                self._codex_sync_size = self.sync

            def update_idletasks(self) -> None:
                self.updated = True

            def sync(self) -> None:
                self.synced = True

        shell = FakeShell()

        _sync_rounded_card(shell)

        self.assertTrue(shell.updated)
        self.assertTrue(shell.synced)

    def test_expanded_spacing_keeps_content_close_to_window_edges(self) -> None:
        spacing = _expanded_spacing()

        top_gap = spacing["title_height"] + spacing["quota_pady"][0]
        bottom_gap = (
            spacing["footer_divider_pady"][0]
            + spacing["footer_bar_pady"][0]
            + spacing["button_pady"] * 2
            + spacing["footer_bar_pady"][1]
        )

        self.assertLessEqual(top_gap, 22)
        self.assertLessEqual(bottom_gap, 26)

    def test_collapsed_panel_uses_single_visible_layer(self) -> None:
        layers = _collapsed_panel_layers(258, 82)

        self.assertEqual(layers, [])

    def test_macos_blur_config_uses_native_rounded_backdrop(self) -> None:
        config = _macos_blur_config()

        self.assertEqual(config["material"], "popover")
        self.assertEqual(config["material_value"], 6)
        self.assertEqual(config["blending_mode"], "behindWindow")
        self.assertEqual(config["state"], "active")
        self.assertGreater(config["alpha"], 0.7)
        self.assertEqual(config["corner_radius"], 41)

    def test_macos_frame_converts_tk_top_left_to_cocoa_bottom_left(self) -> None:
        self.assertEqual(
            _macos_frame_from_tk_geometry(screen_height=1000, x=300, y=220, width=260, height=150),
            (300, 630, 260, 150),
        )

    def test_expanded_toolbar_symbols_use_refresh_collapse_and_close(self) -> None:
        self.assertEqual(_expanded_toolbar_symbols(), ("↺", "↘↖", "×"))

    def test_expanded_footer_text_actions_are_hidden(self) -> None:
        self.assertFalse(_show_expanded_footer_actions())

    def test_transparent_chrome_uses_system_transparent_when_supported(self) -> None:
        class FakeRoot:
            def __init__(self) -> None:
                self.configured: list[dict[str, str]] = []
                self.attributes_calls: list[tuple[str, bool]] = []

            def attributes(self, name: str, value: bool) -> None:
                self.attributes_calls.append((name, value))

            def configure(self, **kwargs: str) -> None:
                self.configured.append(kwargs)

        root = FakeRoot()

        self.assertEqual(_configure_transparent_chrome(root), TRANSPARENT_BG)
        self.assertEqual(root.attributes_calls, [("-transparent", True)])
        self.assertEqual(root.configured, [{"bg": TRANSPARENT_BG}])

    def test_transparent_chrome_falls_back_to_window_background(self) -> None:
        class FakeRoot:
            def __init__(self) -> None:
                self.configured: list[dict[str, str]] = []

            def attributes(self, _name: str, _value: bool) -> None:
                raise RuntimeError("unsupported")

            def configure(self, **kwargs: str) -> None:
                self.configured.append(kwargs)

        root = FakeRoot()

        self.assertEqual(_configure_transparent_chrome(root), BG_WINDOW)
        self.assertEqual(root.configured, [{"bg": BG_WINDOW}])

    def test_visible_app_identity_configures_regular_policy_and_icon(self) -> None:
        calls: list[str] = []

        class FakeApp:
            def setActivationPolicy_(self, value: int) -> None:
                calls.append(f"policy:{value}")

            def activateIgnoringOtherApps_(self, value: bool) -> None:
                calls.append(f"activate:{value}")

            def setApplicationIconImage_(self, _image: object) -> None:
                calls.append("icon")

        class FakeNSApplication:
            @staticmethod
            def sharedApplication() -> FakeApp:
                return FakeApp()

        class FakeNSProcessInfo:
            @staticmethod
            def processInfo() -> "FakeNSProcessInfo":
                return FakeNSProcessInfo()

            def setProcessName_(self, name: str) -> None:
                calls.append(f"name:{name}")

        class FakeNSImage:
            @classmethod
            def alloc(cls) -> "FakeNSImage":
                return cls()

            def initWithContentsOfFile_(self, path: str) -> object:
                calls.append(f"image:{Path(path).name}")
                return object()

        fake_appkit = types.SimpleNamespace(
            NSApplication=FakeNSApplication,
            NSApplicationActivationPolicyRegular=0,
            NSImage=FakeNSImage,
            NSProcessInfo=FakeNSProcessInfo,
        )

        with (
            patch.dict(sys.modules, {"AppKit": fake_appkit}),
            patch("app.ui_tk.Path.exists", return_value=True),
        ):
            self.assertTrue(_configure_visible_app_identity())

        self.assertIn("policy:0", calls)
        self.assertIn("activate:True", calls)
        self.assertIn("name:Codex Monitor", calls)
        self.assertIn("image:CodexMonitor.icns", calls)
        self.assertIn("icon", calls)

    def test_clamped_window_position_keeps_expanded_window_visible(self) -> None:
        class FakeRoot:
            def winfo_screenwidth(self) -> int:
                return 2560

            def winfo_screenheight(self) -> int:
                return 1440

        state = WindowState(x=2324, y=604, collapsed=False)

        self.assertEqual(
            _clamped_window_position(FakeRoot(), width=360, height=500, state=state),
            (2200, 604),
        )

    def test_clamped_window_position_keeps_top_left_non_negative(self) -> None:
        class FakeRoot:
            def winfo_screenwidth(self) -> int:
                return 2560

            def winfo_screenheight(self) -> int:
                return 1440

        state = WindowState(x=-20, y=-10, collapsed=False)

        self.assertEqual(
            _clamped_window_position(FakeRoot(), width=360, height=500, state=state),
            (0, 0),
        )

    def test_window_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            save_window_state(WindowState(x=123, y=456, collapsed=True), path)
            state = load_window_state(path)
            self.assertEqual(state.x, 123)
            self.assertEqual(state.y, 456)
            self.assertTrue(state.collapsed)

    def test_window_state_fallback_on_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            path.write_text("{broken", encoding="utf-8")
            state = load_window_state(path)
            self.assertEqual(state.x, 80)
            self.assertEqual(state.y, 80)
            self.assertFalse(state.collapsed)

    def test_refresh_calls_refresh_fn_and_applies_aggregate(self) -> None:
        aggregate = UsageAggregate(
            today=TokenTotals(codex_tokens=10, claude_tokens=0),
            month=TokenTotals(codex_tokens=10, claude_tokens=0),
            top_projects=(),
            quota=None,
            last_updated="old",
        )
        updated = UsageAggregate(
            today=TokenTotals(codex_tokens=20, claude_tokens=0),
            month=TokenTotals(codex_tokens=20, claude_tokens=0),
            top_projects=(),
            quota=None,
            last_updated="new",
        )

        window = object.__new__(CodexMonitorWindow)
        requests: list[RefreshRequest] = []
        window.refresh_fn = lambda request: requests.append(request) or updated
        window.view_model = build_view_model(aggregate)
        applied: list[UsageAggregate] = []
        window.apply_aggregate = lambda agg: applied.append(agg)
        # root.after(0, fn) must fire fn immediately in test (no event loop)
        window.root = type("FakeRoot", (), {"after": staticmethod(lambda _ms, fn: fn())})()
        window._refresh()
        import time as _time; _time.sleep(0.1)  # let daemon thread complete
        self.assertEqual(requests, [RefreshRequest.manual()])
        self.assertEqual(applied, [updated])

    def test_refresh_async_coalesces_requests_while_running(self) -> None:
        aggregate = UsageAggregate(
            today=TokenTotals(codex_tokens=10, claude_tokens=0),
            month=TokenTotals(codex_tokens=10, claude_tokens=0),
            top_projects=(),
            quota=None,
            last_updated="old",
        )
        updated = UsageAggregate(
            today=TokenTotals(codex_tokens=20, claude_tokens=0),
            month=TokenTotals(codex_tokens=20, claude_tokens=0),
            top_projects=(),
            quota=None,
            last_updated="new",
        )

        first_started = threading.Event()
        release_first = threading.Event()
        requests: list[RefreshRequest] = []

        def refresh_fn(request: RefreshRequest) -> UsageAggregate:
            requests.append(request)
            if len(requests) == 1:
                first_started.set()
                release_first.wait(timeout=1)
            return updated

        window = object.__new__(CodexMonitorWindow)
        window.refresh_fn = refresh_fn
        window.view_model = build_view_model(aggregate)
        applied: list[UsageAggregate] = []
        window.apply_aggregate = lambda agg: applied.append(agg)
        window.root = type("FakeRoot", (), {"after": staticmethod(lambda _ms, fn: fn())})()

        first = RefreshRequest(reason="watcher", claude_modified_since=100.0, claude_max_files=50)
        second = RefreshRequest(reason="watcher", claude_modified_since=90.0, claude_max_files=200)
        self.assertTrue(window.refresh_async(first))
        self.assertTrue(first_started.wait(timeout=1))
        self.assertFalse(window.refresh_async(second))
        release_first.set()

        deadline = time.time() + 1
        while len(requests) < 2 and time.time() < deadline:
            time.sleep(0.01)

        self.assertEqual(requests, [
            first,
            RefreshRequest(reason="watcher", claude_modified_since=90.0, claude_max_files=200),
        ])
        self.assertEqual(applied, [updated, updated])

    def test_capsule_click_shows_project_popover_immediately(self) -> None:
        window = object.__new__(CodexMonitorWindow)
        calls: list[str] = []
        window._show_project_popover = lambda: calls.append("show")
        window._popover_after_id = None
        window._capsule_pointer_inside = False

        window._capsule_click()

        self.assertTrue(window._capsule_pointer_inside)
        self.assertEqual(calls, ["show"])

    def test_collapsed_countdown_is_canvas_text_not_embedded_labels(self) -> None:
        class FakeCanvas:
            instances: list["FakeCanvas"] = []

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                self.text_items: list[dict[str, object]] = []
                self.window_items: list[dict[str, object]] = []
                FakeCanvas.instances.append(self)

            def pack(self) -> None:
                return None

            def bind(self, *_args: object) -> None:
                return None

            def create_polygon(self, *_args: object, **_kwargs: object) -> int:
                return 1

            def create_arc(self, *_args: object, **_kwargs: object) -> int:
                return 2

            def create_oval(self, *_args: object, **_kwargs: object) -> int:
                return 3

            def create_line(self, *_args: object, **_kwargs: object) -> int:
                return 4

            def create_text(self, *_args: object, **kwargs: object) -> int:
                self.text_items.append(kwargs)
                return 100 + len(self.text_items)

            def create_window(self, *_args: object, **kwargs: object) -> int:
                self.window_items.append(kwargs)
                return 200 + len(self.window_items)

        class FakeLabel:
            instances: list["FakeLabel"] = []

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                FakeLabel.instances.append(self)

            def bind(self, *_args: object) -> None:
                return None

        fake_tk = types.SimpleNamespace(Canvas=FakeCanvas, Label=FakeLabel, ARC="arc")
        window = object.__new__(CodexMonitorWindow)
        window.root = type("FakeRoot", (), {
            "resizable": lambda *_args: None,
            "geometry": lambda *_args: None,
            "after": lambda *_args: None,
            "winfo_screenwidth": lambda _self: 2560,
            "winfo_screenheight": lambda _self: 1440,
        })()
        window.container = object()
        window.state = WindowState()
        window.state_path = Path("/tmp/nonexistent-codex-monitor-state.json")
        window.chrome_bg = BG_WINDOW
        window.fonts = type("Fonts", (), {
            "num_large": ("Helvetica", 17, "bold"),
            "caption": ("Helvetica", 11, "normal"),
        })()
        window.view_model = {
            "quota": [
                {"percent_value": 42.0, "resets_at": None, "window_minutes": 300},
                {"percent_value": 11.0, "resets_at": None, "window_minutes": 10080},
            ]
        }
        window._bind_capsule_pointer = lambda _widget: None

        with patch.dict(sys.modules, {"tkinter": fake_tk}):
            window._build_collapsed()

        canvas = FakeCanvas.instances[0]
        self.assertEqual(FakeLabel.instances, [])
        self.assertEqual(canvas.window_items, [])
        self.assertEqual(len(window._cd_text_items), 2)
        self.assertTrue({"5小时", "7天"}.issubset({item["text"] for item in canvas.text_items}))

    def test_countdown_updates_canvas_text_items(self) -> None:
        class FakeCanvas:
            def __init__(self) -> None:
                self.updates: list[tuple[int, dict[str, str]]] = []

            def itemconfigure(self, item_id: int, **kwargs: str) -> None:
                self.updates.append((item_id, kwargs))

        canvas = FakeCanvas()
        window = object.__new__(CodexMonitorWindow)
        window.root = type("FakeRoot", (), {"after": lambda _self, _ms, _fn: "after-1"})()
        window.view_model = {
            "quota": [
                {"resets_at": None, "window_minutes": 172},
                {"resets_at": None, "window_minutes": 9600},
            ]
        }
        window._countdown_after_id = None
        window._cd_text_items = [(canvas, 10), (canvas, 11)]

        window._do_countdown()

        self.assertEqual(
            canvas.updates,
            [
                (10, {"text": "2小时52分"}),
                (11, {"text": "6天16小时"}),
            ],
        )

    def test_capsule_leave_cancels_pending_project_popover(self) -> None:
        class FakeRoot:
            def __init__(self) -> None:
                self.cancelled: list[str] = []

            def after_cancel(self, after_id: str) -> None:
                self.cancelled.append(after_id)

        window = object.__new__(CodexMonitorWindow)
        window.root = FakeRoot()
        window._popover_after_id = "after-1"
        window._capsule_pointer_inside = True
        window._popover_pointer_inside = False
        window._project_popover = None

        window._capsule_leave()

        self.assertFalse(window._capsule_pointer_inside)
        self.assertIsNone(window._popover_after_id)
        self.assertEqual(window.root.cancelled, ["after-1"])


if __name__ == "__main__":
    unittest.main()
