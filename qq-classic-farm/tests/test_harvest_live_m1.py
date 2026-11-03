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
from farm_qq_clean import ALL_CELLS, EmptyFieldCheck


EMPTY_CHECK = EmptyFieldCheck("EMPTY", ALL_CELLS, (), (), "ALL_24_EMPTY")
CST = timezone(timedelta(hours=8))
FRAME = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)
HANDLE = WindowHandle(6951, 53086, FRAME)
WECHAT_FRAME = WindowFrame("微信", "QQ经典农场", 967, 107, 625, 1155)
WECHAT_HANDLE = WindowHandle(14468, 1369, WECHAT_FRAME)
NOT_EMPTY_CHECK = EmptyFieldCheck("NOT_EMPTY", (), ALL_CELLS, (), "OCCUPIED_CELL_DETECTED")
PARTIAL_NOT_EMPTY_CHECK = EmptyFieldCheck(
    "NOT_EMPTY", (), ALL_CELLS[:-1], ALL_CELLS[-1:], "OCCUPIED_CELL_DETECTED"
)


class FakeCapture:
    capture_id = "fresh-live-capture"
    captured_at_ns = 123456789


class LiveAdapterTests(unittest.TestCase):
    def adapter(self, *, execute=False):
        return LiveHarvestAdapter("qq", {}, {}, Path("/tmp/registry"),
                                  Path("/tmp/click-helper"), execute=execute)

    def wechat_adapter(self, *, execute=False, expected_special=None):
        return LiveHarvestAdapter(
            "wechat", {}, {}, Path("/tmp/registry"), Path("/tmp/click-helper"),
            execute=execute, expected_special_placements=expected_special,
        )

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.check_wechat_empty_field", return_value=NOT_EMPTY_CHECK)
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_known_ordinary_wechat_field_authorizes_only_global_hand(
        self, registry, capture, probe, _check, _clock
    ):
        registry.return_value = WECHAT_HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {
            "hand": {"matched": True, "score": 0.988, "local_center": [308.0, 860.0]},
            "raw_pickable_candidates": [
                {"local_center": [357.0, 560.5], "score": 0.58},
                {"local_center": [187.0, 646.5], "score": 0.57},
            ],
            "pickables": [],
        }
        adapter = self.wechat_adapter(expected_special=frozenset())
        obs = adapter.observe()
        self.assertEqual(obs.overlay, "none")
        self.assertTrue(obs.calibration_verified)
        self.assertEqual(obs.occupied_special, frozenset())
        self.assertEqual(obs.special, ())
        self.assertEqual(obs.empty_cells, (False,) * 24)
        self.assertEqual(prepare_harvest(obs), ((308.0, 860.0),))
        self.assertTrue(adapter.last_diagnostics["can_authorize_clicks"])

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.check_wechat_empty_field", return_value=PARTIAL_NOT_EMPTY_CHECK)
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_known_ordinary_wechat_field_with_unknown_cell_stays_fail_closed(
        self, registry, capture, probe, _check, _clock
    ):
        registry.return_value = WECHAT_HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {
            "hand": {"matched": True, "score": 0.99, "local_center": [308.0, 860.0]},
            "raw_pickable_candidates": [],
            "pickables": [],
        }
        obs = self.wechat_adapter(expected_special=frozenset()).observe()
        self.assertFalse(obs.calibration_verified)
        self.assertIsNone(obs.occupied_special)
        with self.assertRaises(HarvestStop):
            prepare_harvest(obs)

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.check_wechat_empty_field", return_value=NOT_EMPTY_CHECK)
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_wechat_field_without_known_special_context_stays_fail_closed(
        self, registry, capture, probe, _check, _clock
    ):
        registry.return_value = WECHAT_HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {
            "hand": {"matched": True, "score": 0.99, "local_center": [308.0, 860.0]},
            "raw_pickable_candidates": [],
            "pickables": [],
        }
        obs = self.wechat_adapter(expected_special=None).observe()
        self.assertFalse(obs.calibration_verified)
        self.assertIsNone(obs.occupied_special)
        with self.assertRaises(HarvestStop):
            prepare_harvest(obs)

    def test_interactive_live_window_has_no_time_blackout(self):
        for h, m in ((0, 0), (8, 30), (12, 35), (14, 2), (16, 30), (20, 30)):
            with self.subTest(h=h, m=m):
                require_live_window(
                    clock=lambda h=h, m=m: datetime(2026, 10, 31, h, m, tzinfo=CST)
                )
        # Clock validation is intentionally deferred with scheduler policy.
        require_live_window(clock=lambda: datetime(2026, 10, 31, 6, 30))

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
    @patch("farm_harvest_live.check_qq_empty_field", return_value=EMPTY_CHECK)
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_v2_empty_check_does_not_authorize_harvest_by_itself(
        self, registry, capture, probe, _check, _clock
    ):
        registry.return_value = HANDLE
        capture.return_value = FakeCapture()
        probe.return_value = {"hand": {"matched": False, "score": 0.2},
                              "raw_pickable_candidates": [], "pickables": []}
        adapter = self.adapter(execute=True)
        with patch.object(adapter, "click_batch", side_effect=AssertionError("Never click")) as click:
            with self.assertRaises(HarvestStop) as caught:
                run_harvest(adapter)
            self.assertEqual(caught.exception.code, "UNKNOWN_OVERLAY")
            self.assertTrue(adapter.last_diagnostics["empty_field_candidate"])
            self.assertTrue(adapter.last_diagnostics["clean_field_verified"])
            self.assertFalse(adapter.last_diagnostics["already_clean_verified"])
            self.assertFalse(adapter.last_diagnostics["can_authorize_clicks"])
            click.assert_not_called()

    @patch("farm_harvest_live.require_live_window")
    @patch("farm_harvest_live.check_qq_empty_field", return_value=EMPTY_CHECK)
    @patch("farm_harvest_live.probe_harvest")
    @patch("farm_harvest_live.capture_window")
    @patch("farm_harvest_live.find_farm_window")
    def test_empty_check_cannot_override_conflicting_crop_controls(
        self, registry, capture, probe, _check, _clock
    ):
        registry.return_value = HANDLE
        capture.return_value = FakeCapture()
        for hand, stars in (
            ({"matched": True, "local_center": [297.0, 826.0]}, []),
            ({"matched": False}, [{"local_center": [340.0, 600.0]}]),
        ):
            probe.return_value = {"hand": hand, "raw_pickable_candidates": stars}
            adapter = self.adapter(execute=True)
            with self.subTest(hand=hand, stars=stars):
                with patch.object(adapter, "click_batch", side_effect=AssertionError("Never click")):
                    with self.assertRaises(HarvestStop) as caught:
                        run_harvest(adapter)
                    self.assertEqual(caught.exception.code, "UNKNOWN_OVERLAY")
                    self.assertFalse(adapter.last_diagnostics["already_clean_verified"])

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
