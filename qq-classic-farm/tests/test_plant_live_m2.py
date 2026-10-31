"""M2 real I/O seam: mock only; zero CGEvent until live calibration exists."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_geometry import WindowFrame
from farm_io import WindowHandle
from farm_plant_live import LivePlantAdapter, read_only_plant_preflight
from farm_plant_special import SpecialPlantStop

FRAME = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)
HANDLE = WindowHandle(6951, 53086, FRAME)


class FakeCapture:
    capture_id = "live-plant-001"
    captured_at_ns = 123456789


class LivePlantTests(unittest.TestCase):
    def adapter(self, execute=False):
        return LivePlantAdapter("qq", {}, Path("/tmp/registry"),
                                Path("/tmp/click"), execute=execute)

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.capture_window", return_value=FakeCapture())
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    def test_live_field_preflight_preserves_unknown_and_never_clicks(self, registry, capture, clock):
        adapter = self.adapter(execute=True)
        with patch("farm_plant_live.subprocess.run", side_effect=AssertionError("No CGEvent")) as cg:
            result = read_only_plant_preflight(adapter)
            view = adapter.last_field
            self.assertEqual(result["code"], "PLANT_OVERLAY")
            self.assertEqual(result["click_count"], 0)
            self.assertEqual(result["llm_round_trips"], 0)
            self.assertEqual(view.window_identity[0], 6951)
            self.assertEqual(view.capture_id, "live-plant-001")
            self.assertIsNone(view.field_cells)
            self.assertIsNone(view.preview_cells)
            self.assertIsNone(view.one_key_planting)
            self.assertFalse(adapter.calibration_verified)
            self.assertEqual(registry.call_count, 2)
            cg.assert_not_called()

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.capture_window", return_value=FakeCapture())
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    def test_live_picker_does_not_invent_page_or_quantity(self, registry, capture, clock):
        adapter = self.adapter()
        view = adapter.observe(2, "萝卜")
        self.assertIsNone(view.page)
        self.assertIsNone(view.target_icon_verified)
        self.assertIsNone(view.target_quantity)
        self.assertFalse(adapter.last_diagnostics["can_authorize_clicks"])

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.subprocess.run", side_effect=AssertionError("No CGEvent"))
    def test_execute_flag_cannot_bypass_calibration(self, cg, clock):
        adapter = self.adapter(execute=True)
        adapter.last_handle = HANDLE
        adapter.last_field = None
        with self.assertRaises(SpecialPlantStop) as caught:
            adapter._send_points(((300, 900),))
        self.assertEqual(caught.exception.code, "PLANT_CALIBRATION_REQUIRED")
        cg.assert_not_called()

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.capture_window", side_effect=RuntimeError("no screenshot"))
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    def test_failed_capture_discards_previous_authority(self, registry, capture, clock):
        adapter = self.adapter(execute=True)
        adapter.last_handle = HANDLE
        adapter.calibration_verified = True
        with self.assertRaises(RuntimeError):
            adapter.observe_field()
        self.assertIsNone(adapter.last_handle)
        self.assertIsNone(adapter.last_field)
        self.assertFalse(adapter.calibration_verified)

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.capture_window", return_value=FakeCapture())
    @patch("farm_plant_live.find_farm_window")
    def test_moved_window_rejected(self, registry, capture, clock):
        registry.side_effect = [HANDLE, replace(HANDLE, window_id=6952)]
        with self.assertRaises(SpecialPlantStop) as caught:
            self.adapter().observe_field()
        self.assertEqual(caught.exception.code, "USER_INTERFERENCE")

    def test_uncalibrated_action_methods_stop(self):
        adapter = self.adapter(execute=True)
        for method, args in ((adapter.open_plot, ((2, 0),)),
                             (adapter.turn_pages, (1, 1)),
                             (adapter.select_seed, (1,)),
                             (adapter.confirm_special, ())):
            with self.subTest(method=method.__name__):
                with self.assertRaises(SpecialPlantStop):
                    method(*args)


if __name__ == "__main__":
    unittest.main()
