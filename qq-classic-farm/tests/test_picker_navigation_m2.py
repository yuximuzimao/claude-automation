"""Guarded QQ picker page navigation: no seed selection, no blind retry."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_geometry import WindowFrame
from farm_io import WindowHandle
from farm_plant_live import LivePlantAdapter
from farm_plant_special import SpecialPlantStop

FRAME = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)
HANDLE = WindowHandle(6951, 53086, FRAME)


class PickerNavigationTests(unittest.TestCase):
    def adapter(self, execute=True):
        return LivePlantAdapter("qq", {}, Path("/tmp/registry"),
                                Path("/tmp/click"), execute=execute)

    def prime(self, adapter, page=2, y_shift=0):
        adapter.last_handle = HANDLE
        adapter.last_picker = SimpleNamespace(page=page)
        adapter.last_picker_total = 7
        adapter.last_picker_y_shift = y_shift
        adapter.last_picker_capture = SimpleNamespace(captured_at_ns=1_000_000_000)

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.monotonic_ns", return_value=1_500_000_000)
    @patch("farm_plant_live.picker_arrow_verified", return_value=True)
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    @patch("farm_plant_live.subprocess.run")
    def test_bounded_batch_and_invalidates_capture(self, run, registry, arrow, clock, time):
        adapter = self.adapter()
        self.prime(adapter)
        run.return_value = SimpleNamespace(returncode=0,
            stdout=json.dumps({"status": "clicks_sent_unverified", "click_count": 2}))
        adapter.turn_pages(1, 2)
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], "--execute")
        payload = json.loads(kwargs["input"])
        self.assertEqual(len(payload["actions"]), 2)
        self.assertEqual(payload["actions"][0]["x"], 569)
        self.assertEqual(payload["actions"][0]["y"], 771)
        self.assertIsNone(adapter.last_picker)
        self.assertIsNone(adapter.last_handle)

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.monotonic_ns", return_value=1_500_000_000)
    @patch("farm_plant_live.picker_arrow_verified", return_value=True)
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    @patch("farm_plant_live.subprocess.run")
    def test_shifted_picker_moves_arrow_with_verified_local_offset(self, run, registry, arrow, clock, time):
        adapter = self.adapter()
        self.prime(adapter, y_shift=-42)
        initial_capture = adapter.last_picker_capture
        run.return_value = SimpleNamespace(returncode=0,
            stdout=json.dumps({"status": "clicks_sent_unverified", "click_count": 1}))
        adapter.turn_pages(1, 1)
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload["actions"][0]["y"], 729)
        arrow.assert_called_once_with(initial_capture, 1, -42)

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.monotonic_ns", return_value=1_500_000_000)
    @patch("farm_plant_live.picker_arrow_verified", return_value=False)
    @patch("farm_plant_live.subprocess.run")
    def test_missing_arrow_stops_without_input(self, run, arrow, clock, time):
        adapter = self.adapter()
        self.prime(adapter)
        with self.assertRaises(SpecialPlantStop) as caught:
            adapter.turn_pages(-1, 1)
        self.assertEqual(caught.exception.code, "PICKER_ARROW_UNVERIFIED")
        run.assert_not_called()

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.subprocess.run")
    def test_page_bounds_stop_without_input(self, run, time):
        adapter = self.adapter()
        self.prime(adapter, page=7)
        with self.assertRaises(SpecialPlantStop) as caught:
            adapter.turn_pages(1, 1)
        self.assertEqual(caught.exception.code, "PICKER_PAGE_UNKNOWN")
        run.assert_not_called()

    @patch("farm_plant_live.require_live_window")
    @patch("farm_plant_live.monotonic_ns", return_value=1_500_000_000)
    @patch("farm_plant_live.picker_arrow_verified", return_value=True)
    @patch("farm_plant_live.find_farm_window", return_value=HANDLE)
    @patch("farm_plant_live.subprocess.run")
    def test_partial_send_is_uncertain_and_not_replayed(self, run, registry, arrow, clock, time):
        adapter = self.adapter()
        self.prime(adapter)
        run.return_value = SimpleNamespace(returncode=2,
            stdout=json.dumps({"status": "stopped", "code": "WINDOW_OCCLUDED",
                               "click_count": 1}))
        with self.assertRaises(SpecialPlantStop) as caught:
            adapter.turn_pages(1, 2)
        self.assertEqual(caught.exception.code, "PICKER_NAVIGATION_UNCERTAIN")
        self.assertTrue(caught.exception.action_may_have_been_sent)
        self.assertEqual(run.call_count, 1)
        self.assertIsNone(adapter.last_picker)


if __name__ == "__main__":
    unittest.main()
