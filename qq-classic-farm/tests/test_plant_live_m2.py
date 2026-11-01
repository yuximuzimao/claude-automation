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

    def test_registered_postcondition_is_read_only_and_keeps_unknown(self):
        from farm_field_postcondition import FieldPostcondition
        adapter = self.adapter(execute=True)
        result = FieldPostcondition(
            clean_cells=tuple((u, v) for u in range(6) for v in range(4)
                              if (u, v) not in ((0, 0), (0, 1))),
            changed_cells=(), unknown_cells=((0, 0), (0, 1)),
            clean_field_verified=False, capture_ids=("empty", "idle", "post"),
        )
        with (patch.object(adapter, "_capture", return_value=(HANDLE, FakeCapture())),
              patch("farm_plant_live.compare_empty_field_postcondition",
                    return_value=result) as compare,
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            observed = adapter.verify_clean_field_against_reference(
                HANDLE, FakeCapture(), FakeCapture(), empty_reference_verified=True)
            self.assertIs(observed, result)
            self.assertEqual(adapter.last_diagnostics["unknown_cells"], [[0, 0], [0, 1]])
            self.assertFalse(adapter.last_diagnostics["clean_field_verified"])
            self.assertFalse(adapter.calibration_verified)
            self.assertTrue(compare.call_args.kwargs["empty_reference_verified"])
            cg.assert_not_called()

    def test_open_plot_uses_registered_cell_only_after_independent_field_verification(self):
        import json
        from farm_plant_ordinary import OrdinaryPlantView
        from farm_plant_special import ALL_CELLS

        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        adapter = LivePlantAdapter("qq", layout, Path("/tmp/registry"),
                                   Path("/tmp/click"), execute=True)
        field = {cell: False for cell in ALL_CELLS}
        adapter.last_handle = HANDLE
        adapter.last_field_capture = FakeCapture()
        adapter.last_field = OrdinaryPlantView(
            capture_id="live-plant-001", captured_at_ns=123456789,
            window_identity=(HANDLE.window_id, HANDLE.pid, FRAME.owner,
                             FRAME.title, FRAME.x, FRAME.y),
            overlay="none", field_cells=field, preview_cells=frozenset(),
            one_key_planting=None,
        )
        with patch.object(adapter, "_send_points") as send, patch(
            "farm_plant_live.probe_field_translation",
            return_value={"status": "diagnostic_only", "matched_purple_cells": 5,
                          "offset_local": [-9.3497, 18.4735]},
        ) as register:
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((3, 2))
            self.assertEqual(caught.exception.code, "PLANT_CALIBRATION_REQUIRED")
            send.assert_not_called()
            register.assert_not_called()

            adapter.calibration_verified = True  # mock independent semantic verifier
            field[(3, 2)] = True
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((3, 2))
            self.assertEqual(caught.exception.code, "PLANT_TARGET_OCCUPIED")
            send.assert_not_called()

            field[(3, 2)] = False
            adapter.open_plot((3, 2))
            ((x, y),), = send.call_args.args
            self.assertAlmostEqual(x, 301.52, delta=0.1)
            self.assertAlmostEqual(y, 689.09, delta=0.1)
            self.assertEqual(register.call_count, 1)

            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((6, 0))
            self.assertEqual(caught.exception.code, "INVALID_PLOT")
            self.assertEqual(send.call_count, 1)

    def test_open_plot_rejects_missing_registration_without_cgevent(self):
        import json
        from farm_plant_ordinary import OrdinaryPlantView
        from farm_plant_special import ALL_CELLS
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        adapter = LivePlantAdapter("qq", layout, Path("/tmp/registry"),
                                   Path("/tmp/click"), execute=True)
        adapter.last_handle = HANDLE
        adapter.last_field_capture = FakeCapture()
        adapter.last_field = OrdinaryPlantView(
            capture_id="live-plant-001", captured_at_ns=123456789,
            window_identity=(HANDLE.window_id, HANDLE.pid, FRAME.owner,
                             FRAME.title, FRAME.x, FRAME.y),
            overlay="none", field_cells={cell: False for cell in ALL_CELLS},
            preview_cells=frozenset(),
        )
        adapter.calibration_verified = True
        with patch("farm_plant_live.probe_field_translation",
                   side_effect=ValueError("ambiguous")), patch.object(
            adapter, "_send_points", side_effect=AssertionError("no CGEvent")
        ) as send:
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((3, 2))
            self.assertEqual(caught.exception.code, "PLANT_ALIGNMENT_UNVERIFIED")
            send.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
