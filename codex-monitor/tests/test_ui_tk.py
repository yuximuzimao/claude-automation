from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from app.aggregate import ProjectTotal, TokenTotals, UsageAggregate
from app.models import CodexQuota, RateLimitWindow
from app.runtime import RefreshRequest
from app.ui_tk import (
    CodexMonitorWindow,
    WindowState,
    _quota_center_text,
    _quota_ring_used_pct,
    _ring_extent,
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


if __name__ == "__main__":
    unittest.main()
