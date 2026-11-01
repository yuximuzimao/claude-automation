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
    frame = FRAME


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

    def test_picker_confirmation_modal_is_structured_stop_not_enabled_mode(self):
        adapter = self.adapter(execute=True)
        evidence = {"one_key_confirmation_pending": True}
        with (patch.object(adapter, "_capture", return_value=(HANDLE, FakeCapture())),
              patch("farm_plant_live.observe_picker", return_value=evidence),
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.observe(3, "泡泡棉花糖种子")
            self.assertEqual(caught.exception.code, "ONE_KEY_CONFIRMATION_PENDING")
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

    def test_open_plot_waits_for_v2_empty_checker(self):
        adapter = self.adapter(execute=True)
        with patch("farm_plant_live.subprocess.run",
                   side_effect=AssertionError("No CGEvent")) as cg:
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((3, 2))
            self.assertEqual(caught.exception.code, "PLANT_V2_EMPTY_CHECK_REQUIRED")
            cg.assert_not_called()

            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((6, 0))
            self.assertEqual(caught.exception.code, "INVALID_PLOT")
            cg.assert_not_called()

    @patch("farm_plant_live.require_live_window")
    def test_uncalibrated_action_methods_stop(self, clock):
        # The test targets uncalibrated action rejection, not the Mac clock;
        # it must run identically inside/outside the real-operation blackout.
        adapter = self.adapter(execute=True)
        for method, args in ((adapter.open_plot, ((2, 0),)),
                             (adapter.turn_pages, (1, 1)),
                             (adapter.select_seed, (1,)),
                             (adapter.confirm_special, ())):
            with self.subTest(method=method.__name__):
                with self.assertRaises(SpecialPlantStop):
                    method(*args)

    def test_verified_ordinary_on_picker_selection_is_single_gated_cgevent(self):
        import json
        from types import SimpleNamespace
        from farm_plant_picker import PickerView
        from farm_harvest_live import _identity

        adapter = self.adapter(execute=True)
        adapter.pending_picker_origin = _identity(HANDLE)
        adapter.pending_empty_count = 2
        adapter.last_handle = HANDLE
        adapter.last_picker_capture = FakeCapture()
        adapter.last_picker_expected_slot = 3
        adapter.last_picker_target_seed = "天山红枫种子"
        adapter.last_picker = PickerView(page=1, target_icon_verified=True,
                                         target_quantity=21, one_key_planting=True)
        adapter.arm_ordinary_selection(2, "天山红枫种子")
        adapter.last_picker_y_shift = 21
        response = SimpleNamespace(returncode=0, stdout=json.dumps({
            "status": "clicks_sent_unverified", "click_count": 1,
        }))
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.monotonic_ns", return_value=FakeCapture.captured_at_ns + 10),
              patch("farm_plant_live.find_farm_window", return_value=HANDLE),
              patch("farm_plant_live.subprocess.run", return_value=response) as cg):
            adapter.select_seed(3)
            payload = json.loads(cg.call_args.kwargs["input"])
            self.assertEqual(payload["window_id"], HANDLE.window_id)
            self.assertEqual(len(payload["actions"]), 1)
            self.assertAlmostEqual(payload["actions"][0]["x"], 287)
            self.assertAlmostEqual(payload["actions"][0]["y"], 806)
            self.assertIsNone(adapter.pending_picker_origin)
            self.assertIsNone(adapter.last_picker)
            with self.assertRaises(SpecialPlantStop):
                adapter.select_seed(3)
            self.assertEqual(cg.call_count, 1)

    def test_picker_selection_never_sends_without_verified_on_origin_and_stock(self):
        from farm_plant_picker import PickerView
        from farm_harvest_live import _identity
        adapter = self.adapter(execute=True)
        adapter.pending_picker_origin = _identity(HANDLE)
        adapter.pending_empty_count = 4
        adapter.last_handle = HANDLE
        adapter.last_picker_capture = FakeCapture()
        adapter.last_picker_expected_slot = 3
        adapter.last_picker_target_seed = "天山红枫种子"
        adapter.pending_ordinary_seed = "天山红枫种子"
        adapter.last_picker_y_shift = 21
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.subprocess.run") as cg):
            for mode, qty, slot in [(False, 21, 3), (None, 21, 3),
                                    (True, 3, 3), (True, 21, 0), (True, 21, 4)]:
                adapter.last_picker = PickerView(page=1, target_icon_verified=True,
                                                 target_quantity=qty, one_key_planting=mode)
                with self.assertRaises(SpecialPlantStop) as caught:
                    adapter.select_seed(slot)
                self.assertEqual(caught.exception.code, "PLANT_SELECTION_UNVERIFIED")
            adapter.pending_picker_origin = None
            adapter.last_picker = PickerView(page=1, target_icon_verified=True,
                                             target_quantity=21, one_key_planting=True)
            with self.assertRaises(SpecialPlantStop):
                adapter.select_seed(3)
            cg.assert_not_called()

    def test_ordinary_intent_cannot_be_armed_for_special_or_wrong_count(self):
        from farm_plant_picker import PickerView
        from farm_harvest_live import _identity
        adapter = self.adapter(execute=True)
        adapter.pending_picker_origin = _identity(HANDLE)
        adapter.pending_empty_count = 4
        adapter.last_handle = HANDLE
        adapter.last_picker_target_seed = "泡泡棉花糖种子"
        adapter.last_picker = PickerView(page=1, target_icon_verified=True,
                                         target_quantity=21, one_key_planting=True)
        with patch("farm_plant_live.subprocess.run") as cg:
            for count, seed in ((4, "天山红枫种子"), (3, "泡泡棉花糖种子"),
                                (4, "泡泡棉花糖种子")):
                with self.assertRaises(SpecialPlantStop):
                    adapter.arm_ordinary_selection(count, seed)
            self.assertIsNone(adapter.pending_ordinary_seed)
            cg.assert_not_called()

    def test_picker_selection_partial_result_is_uncertain_and_not_replayed(self):
        from types import SimpleNamespace
        from farm_plant_picker import PickerView
        from farm_harvest_live import _identity
        adapter = self.adapter(execute=True)
        adapter.pending_picker_origin = _identity(HANDLE)
        adapter.pending_empty_count = 2
        adapter.last_handle = HANDLE
        adapter.last_picker_capture = FakeCapture()
        adapter.last_picker_expected_slot = 3
        adapter.last_picker_target_seed = "天山红枫种子"
        adapter.last_picker = PickerView(page=1, target_icon_verified=True,
                                         target_quantity=21, one_key_planting=True)
        adapter.arm_ordinary_selection(2, "天山红枫种子")
        adapter.last_picker_y_shift = 21
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.monotonic_ns", return_value=FakeCapture.captured_at_ns + 10),
              patch("farm_plant_live.find_farm_window", return_value=HANDLE),
              patch("farm_plant_live.subprocess.run", return_value=SimpleNamespace(
                  returncode=2, stdout='{"status":"stopped","click_count":0}')) as cg):
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.select_seed(3)
            self.assertEqual(caught.exception.code, "PLANT_ACTION_UNCERTAIN")
            self.assertTrue(caught.exception.action_may_have_been_sent)
            self.assertIsNone(adapter.pending_picker_origin)
            with self.assertRaises(SpecialPlantStop):
                adapter.select_seed(3)
            self.assertEqual(cg.call_count, 1)


if __name__ == "__main__":
    unittest.main()
