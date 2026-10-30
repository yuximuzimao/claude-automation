"""M1 live-adapter contract tests: no real registry, screenshot or CGEvent."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_geometry import WindowFrame
from farm_harvest import HarvestStop, prepare_harvest, run_harvest
from farm_harvest_live import (LiveHarvestAdapter, read_only_harvest_preflight,
                               require_live_window)
from farm_io import WindowHandle


CST = timezone(timedelta(hours=8))
FRAME = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)
HANDLE = WindowHandle(6951, 53086, FRAME)


class FakeCapture:
    capture_id = "fresh-live-capture"
    captured_at_ns = 123456789


class LiveAdapterTests(unittest.TestCase):
    def adapter(self, *, execute=False):
        return LiveHarvestAdapter("qq", {}, {}, Path("/tmp/registry"),
                                  Path("/tmp/click-helper"), execute=execute)

    def test_all_six_blackouts_and_boundaries_use_mac_clock(self):
        for h, m in ((0, 0), (0, 59), (8, 0), (8, 59),
                     (12, 0), (12, 59), (14, 0), (14, 4),
                     (16, 0), (16, 59), (20, 0), (20, 59),
                     (23, 59), (7, 59)):
            with self.subTest(h=h, m=m):
                with self.assertRaises(HarvestStop) as caught:
                    require_live_window(clock=lambda: datetime(2026, 10, 31, h, m, tzinfo=CST))
                self.assertEqual(caught.exception.code, "FARM_OPERATION_TIME_BLOCKED")
        for h, m in ((1, 0), (9, 0), (13, 0), (14, 5),
                     (17, 0), (21, 0), (6, 40)):
            with self.subTest(h=h, m=m):
                require_live_window(clock=lambda: datetime(2026, 10, 31, h, m, tzinfo=CST))

    def test_unknown_local_clock_fails_closed(self):
        with self.assertRaises(HarvestStop) as caught:
            require_live_window(clock=lambda: datetime(2026, 10, 31, 6, 30))
        self.assertEqual(caught.exception.code, "FARM_OPERATION_TIME_UNKNOWN")

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_live_capture_provenance_and_unverified_candidates(self, registry, capture, probe, _clock):
        registry.return_value = HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {
            "hand": {"matched": True, "score": 0.9139, "local_center": [300.0, 900.0]},
            "pickables": [{"placement": "gold_a", "local_center": [250.0, 580.0], "score": 0.6797}],
            "ignored_outside_special_centers": 2,
        }
        adapter = self.adapter()
        obs = adapter.observe()
        self.assertEqual(obs.window_identity, (6951, 53086, "QQ小程序",
                                                "QQ经典农场", 979, 101))
        self.assertEqual(obs.capture_id, "fresh-live-capture")
        self.assertEqual(obs.captured_at_ns, 123456789)
        self.assertEqual(obs.hand, (300.0, 900.0))
        self.assertEqual(obs.special, ())
        self.assertIsNone(obs.occupied_special)
        self.assertIsNone(obs.empty_cells)
        self.assertFalse(obs.calibration_verified)
        self.assertEqual(adapter.last_diagnostics["candidate_special_count"], 1)
        self.assertFalse(adapter.last_diagnostics["can_authorize_clicks"])
        self.assertEqual(registry.call_count, 2)
        with self.assertRaises(HarvestStop) as caught:
            prepare_harvest(obs)
        self.assertEqual(caught.exception.code, "UNKNOWN_OVERLAY")

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_read_only_preflight_stops_without_click(self, registry, capture, probe, _clock):
        registry.return_value = HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {"hand": {"matched": False, "score": -1},
                              "pickables": [], "ignored_outside_special_centers": 0}
        adapter = self.adapter(execute=True)
        with patch.object(adapter, "click_batch", side_effect=AssertionError("Never click")) as click:
            result = read_only_harvest_preflight(adapter)
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["code"], "UNKNOWN_OVERLAY")
            self.assertEqual(result["click_count"], 0)
            click.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_window_changed_during_capture_is_structured_stop(self, registry, capture, probe, _clock):
        registry.side_effect = [HANDLE, replace(HANDLE, window_id=6952)]
        capture.return_value = FakeCapture()
        with self.assertRaises(HarvestStop) as caught:
            self.adapter().observe()
        self.assertEqual(caught.exception.code, "USER_INTERFERENCE")
        probe.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.subprocess.run")
    def test_execute_flag_cannot_bypass_missing_calibration(self, subprocess_run, _clock):
        adapter = self.adapter(execute=True)
        adapter.last_handle = HANDLE
        adapter.last_observation = self._unverified_observation()
        with self.assertRaises(HarvestStop) as caught:
            adapter.click_batch(((300.0, 900.0),))
        self.assertEqual(caught.exception.code, "HARVEST_CALIBRATION_REQUIRED")
        subprocess_run.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.subprocess.run")
    def test_disabled_execute_cannot_send_even_if_observation_marked_verified(self, subprocess_run, _clock):
        adapter = self.adapter(execute=False)
        adapter.last_handle = HANDLE
        obs = self._unverified_observation()
        adapter.last_observation = replace(obs, overlay="none", calibration_verified=True,
                                           occupied_special=frozenset(), empty_cells=(False,) * 24)
        with self.assertRaises(HarvestStop) as caught:
            adapter.click_batch(((300.0, 900.0),))
        self.assertEqual(caught.exception.code, "HARVEST_CALIBRATION_REQUIRED")
        subprocess_run.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_fsm_with_live_observation_stops_before_any_batch(self, registry, capture, probe, _clock):
        registry.return_value = HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {"hand": {"matched": True, "score": 0.95, "local_center": [300, 900]},
                              "pickables": [], "ignored_outside_special_centers": 0}
        adapter = self.adapter(execute=True)
        with patch.object(adapter, "click_batch", side_effect=AssertionError("Must not click")) as click:
            with self.assertRaises(HarvestStop) as caught:
                run_harvest(adapter)
            self.assertEqual(caught.exception.code, "UNKNOWN_OVERLAY")
            click.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.subprocess.run")
    def test_stale_verified_capture_never_reaches_helper(self, subprocess_run, _clock):
        adapter = self.adapter(execute=True)
        adapter.last_handle = HANDLE
        adapter.last_observation = replace(
            self._unverified_observation(), overlay="none",
            calibration_verified=True, occupied_special=frozenset(),
            empty_cells=(False,) * 24,
        )
        with self.assertRaises(HarvestStop) as caught:
            adapter.click_batch(((300.0, 900.0),))
        self.assertEqual(caught.exception.code, "HARVEST_STALE_PRECONDITION")
        subprocess_run.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.capture_window", side_effect=RuntimeError("capture unavailable"))
    @patch("farm_harvest_live.find_farm_window")
    def test_failed_recapture_discards_prior_observation(self, registry, _capture, _clock):
        registry.return_value = HANDLE
        adapter = self.adapter(execute=True)
        adapter.last_handle = HANDLE
        adapter.last_observation = self._unverified_observation()
        with self.assertRaises(RuntimeError):
            adapter.observe()
        self.assertIsNone(adapter.last_observation)
        self.assertIsNone(adapter.last_handle)

    def _unverified_observation(self):
        from farm_harvest import HarvestObservation
        return HarvestObservation(
            overlay="unknown", calibration_verified=False,
            window_identity=(6951, 53086, "QQ小程序", "QQ经典农场", 979, 101),
            window_width=603, window_height=1111, capture_id="x",
            captured_at_ns=100, hand=(300, 900), special=(),
            occupied_special=None, empty_cells=None,
        )


if __name__ == "__main__":
    unittest.main()
