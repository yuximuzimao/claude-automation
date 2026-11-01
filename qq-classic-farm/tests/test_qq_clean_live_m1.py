"""V2 fixed-grid QQ empty-field checks; all synthetic, no desktop input."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import FarmCapture
from farm_geometry import WindowFrame
from farm_harvest import HarvestStop, prepare_harvest
from farm_harvest_live import LiveHarvestAdapter
from farm_io import WindowHandle
from farm_plant_live import LivePlantAdapter
from farm_plant_special import SpecialPlantStop
from farm_qq_clean import (ALL_CELLS, check_qq_empty_field,
                           observe_qq_preview_cells, qq_special_confirm_point)
from farm_runner import RunnerStop, read_only_empty_check


class QQEmptyFieldV2Tests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        self.qq = self.layout["platforms"]["qq"]
        self.cfg = self.qq["empty_check"]
        self.frame = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)

    def _point(self, cell, offset):
        u, v = cell
        origin = np.asarray(self.qq["origin"], dtype=float)
        u_step = np.asarray(self.qq["u_step"], dtype=float)
        v_step = np.asarray(self.qq["v_step"], dtype=float)
        return np.rint(origin + u*u_step + v*v_step + np.asarray(offset)).astype(int)

    def _paint(self, rgb, x, y, value):
        r = self.cfg["patch_radius"]
        rgb[y-r:y+r+1, x-r:x+r+1] = value

    def image(self, *, occupied=(), ambiguous=(), preview=(), dim=False):
        rgb = np.zeros((1111, 603, 3), dtype=np.uint8)
        purple = np.asarray(self.cfg["soil_prototypes"]["purple"], dtype=np.uint8)
        gold = np.asarray(self.cfg["soil_prototypes"]["gold"], dtype=np.uint8)
        occupied = set(occupied)
        ambiguous = set(ambiguous)
        preview = set(preview)
        for index, cell in enumerate(ALL_CELLS):
            sx, sy = self._point(cell, self.cfg["soil_offset"])
            ox, oy = self._point(cell, self.cfg["occupancy_offset"])
            soil = np.asarray((160, 215, 77), dtype=np.uint8) if cell in preview else (
                purple if index < 5 else gold)
            self._paint(rgb, sx, sy, soil)
            if cell in occupied:
                marker = (120, 90, 45)
            elif cell in ambiguous:
                marker = (150, 150, 150)
            else:
                marker = (220, 190, 120)
            self._paint(rgb, ox, oy, marker)
        return rgb // 2 if dim else rgb

    def shot(self, rgb, *, capture_id="v2", frame=None):
        frame = frame or self.frame
        gray = np.asarray(rgb.mean(axis=2), dtype=np.float32)
        return FarmCapture(frame, gray, capture_id=capture_id,
                           captured_at_ns=123456789, rgb=rgb)

    def test_all_24_empty(self):
        result = check_qq_empty_field(self.shot(self.image()), self.layout)
        self.assertEqual(result.status, "EMPTY")
        self.assertEqual(result.empty_cells, ALL_CELLS)
        self.assertEqual(result.occupied_cells, ())
        self.assertEqual(result.unknown_cells, ())

    def test_one_or_all_occupied_is_not_empty(self):
        for occupied in ({(3, 2)}, set(ALL_CELLS)):
            with self.subTest(count=len(occupied)):
                result = check_qq_empty_field(
                    self.shot(self.image(occupied=occupied)), self.layout)
                self.assertEqual(result.status, "NOT_EMPTY")
                self.assertTrue(set(result.occupied_cells) & occupied)
                self.assertEqual(result.reason, "OCCUPIED_CELL_DETECTED")

    def test_preview_cells_are_exact_2x2_or_unknown(self):
        target = frozenset({(4, 2), (4, 3), (5, 2), (5, 3)})
        self.assertEqual(
            observe_qq_preview_cells(
                self.shot(self.image(preview=target)), self.layout),
            target,
        )
        self.assertEqual(
            observe_qq_preview_cells(self.shot(self.image()), self.layout),
            frozenset(),
        )
        malformed = {(0, 0), (1, 1), (2, 2), (3, 3)}
        self.assertIsNone(
            observe_qq_preview_cells(
                self.shot(self.image(preview=malformed)), self.layout)
        )

    def test_special_confirm_requires_exact_preview_and_green_check_roi(self):
        target = frozenset({(4, 2), (4, 3), (5, 2), (5, 3)})
        rgb = self.image(preview=target)
        self.assertIsNone(
            qq_special_confirm_point(self.shot(rgb.copy()), target, self.layout)
        )

        qq = self.layout["platforms"]["qq"]
        origin = np.asarray(qq["origin"], dtype=float)
        u_step = np.asarray(qq["u_step"], dtype=float)
        v_step = np.asarray(qq["v_step"], dtype=float)
        dx, dy = qq["planting"]["special_confirm_offset_normalized"]
        center = np.mean(
            [origin + u*u_step + v*v_step for u, v in target], axis=0)
        x = round(center[0] + dx * self.frame.width)
        y = round(center[1] + dy * self.frame.height)
        original = rgb.copy()
        rgb[y-38:y+39, x-38:x+39] = (130, 190, 40)
        rgb[y-10:y+10, x-10:x+10] = (245, 245, 220)
        # The synthetic square is larger than the real round button. Restore
        # the 24 tiny soil sampling ROIs so the test isolates confirm-button
        # verification instead of manufacturing extra preview cells.
        for cell in ALL_CELLS:
            sx, sy = self._point(cell, self.cfg["soil_offset"])
            r = self.cfg["patch_radius"]
            rgb[sy-r:sy+r+1, sx-r:sx+r+1] = original[
                sy-r:sy+r+1, sx-r:sx+r+1]

        point = qq_special_confirm_point(self.shot(rgb), target, self.layout)
        self.assertIsNotNone(point)
        self.assertAlmostEqual(point[0], x, delta=1)
        self.assertAlmostEqual(point[1], y, delta=1)
        wrong = frozenset({(0, 0), (0, 1), (1, 0), (1, 1)})
        self.assertIsNone(qq_special_confirm_point(self.shot(rgb), wrong, self.layout))

    def test_dimmed_overlay_is_unknown_not_occupied(self):
        result = check_qq_empty_field(
            self.shot(self.image(dim=True)), self.layout)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.occupied_cells, ())
        self.assertEqual(set(result.unknown_cells), set(ALL_CELLS))

    def test_ambiguous_luminance_is_unknown(self):
        result = check_qq_empty_field(
            self.shot(self.image(ambiguous={(2, 2)})), self.layout)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertIn((2, 2), result.unknown_cells)
        self.assertEqual(result.occupied_cells, ())

    def test_untrusted_capture_and_bad_calibration_are_unknown(self):
        self.assertEqual(
            check_qq_empty_field(self.shot(self.image(), capture_id=""), self.layout).status,
            "UNKNOWN",
        )
        bad = copy.deepcopy(self.layout)
        bad["platforms"]["qq"]["empty_check"]["soil_offset"] = [1]
        self.assertEqual(
            check_qq_empty_field(self.shot(self.image()), bad).status,
            "UNKNOWN",
        )

    def test_window_size_change_is_unknown(self):
        rgb = np.zeros((1111, 602, 3), dtype=np.uint8)
        frame = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 602, 1111)
        result = check_qq_empty_field(self.shot(rgb, frame=frame), self.layout)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(result.reason, "WINDOW_SIZE_CHANGED")

    def test_live_adapters_read_status_but_do_not_unlock_clicks(self):
        handle = WindowHandle(6951, 53086, self.frame)
        shot = self.shot(self.image())

        plant = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                 Path("/tmp/click"), execute=True)
        with patch.object(plant, "_capture", return_value=(handle, shot)):
            view = plant.observe_field()
        self.assertEqual(plant.last_diagnostics["empty_check_status"], "EMPTY")
        self.assertTrue(plant.last_diagnostics["clean_field_verified"])
        self.assertFalse(plant.calibration_verified)
        with self.assertRaises(SpecialPlantStop) as caught:
            plant.open_plot((3, 2))
        self.assertEqual(caught.exception.code, "PLANT_V2_EMPTY_CHECK_REQUIRED")

        harvest = LiveHarvestAdapter("qq", self.layout, {}, Path("/tmp/registry"),
                                     execute=True)
        with (patch("farm_harvest_live.require_live_window"),
              patch("farm_harvest_live.find_farm_window", return_value=handle),
              patch("farm_harvest_live.capture_window", return_value=shot),
              patch("farm_harvest_live.probe_harvest",
                    return_value={"hand": {"matched": False},
                                  "pickables": [], "raw_pickable_candidates": []})):
            obs = harvest.observe()
        self.assertEqual(harvest.last_diagnostics["empty_check_status"], "EMPTY")
        self.assertTrue(harvest.last_diagnostics["clean_field_verified"])
        self.assertFalse(harvest.last_diagnostics["already_clean_verified"])
        with self.assertRaises(HarvestStop):
            prepare_harvest(obs)

    def test_live_adapter_phase_gate_and_target_roi_are_read_only(self):
        handle = WindowHandle(6951, 53086, self.frame)
        empty = self.shot(self.image())
        planted = self.shot(self.image(occupied={(3, 2)}), capture_id="planted")

        plant = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                 Path("/tmp/click"), execute=True)
        with (patch.object(plant, "_capture", return_value=(handle, empty)),
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            self.assertTrue(plant.require_empty_field())
            cg.assert_not_called()

        target = frozenset({(3, 2)})
        with (patch.object(plant, "_capture", return_value=(handle, planted)),
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            self.assertTrue(plant.verify_cells_occupied(target))
            self.assertFalse(plant.verify_cells_occupied(frozenset({(0, 0)})))
            cg.assert_not_called()

        with self.assertRaises(SpecialPlantStop) as caught:
            plant.verify_cells_occupied(frozenset())
        self.assertEqual(caught.exception.code, "INVALID_PLOT_SET")

    def test_runner_check_empty_is_read_only(self):
        handle = WindowHandle(6951, 53086, self.frame)
        shot = self.shot(self.image())
        with (patch("farm_runner.find_farm_window", return_value=handle) as registry,
              patch("farm_runner.capture_window", return_value=shot) as capture):
            result = read_only_empty_check("qq", self.layout, Path("/tmp/registry"))
        self.assertEqual(result["status"], "EMPTY")
        self.assertEqual(result["click_count"], 0)
        self.assertEqual(result["llm_round_trips"], 0)
        self.assertEqual(registry.call_count, 2)
        capture.assert_called_once()

        with self.assertRaises(RunnerStop) as caught:
            read_only_empty_check("wechat", self.layout, Path("/tmp/registry"))
        self.assertEqual(caught.exception.code, "EMPTY_CHECK_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
