"""WeChat V2 fixed-grid empty-field checks; synthetic only, no desktop input."""
from __future__ import annotations

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
from farm_io import WindowHandle
from farm_plant_live import LivePlantAdapter
from farm_plant_special import SpecialPlantStop
from farm_qq_clean import ALL_CELLS, check_wechat_empty_field
from farm_runner import read_only_empty_check


class WeChatEmptyFieldV2Tests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        self.cfg = self.layout["platforms"]["wechat"]["empty_check"]
        self.wechat = self.layout["platforms"]["wechat"]
        self.purple = {
            (0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)
        }

    def frame(self, width=625):
        return WindowFrame("微信", "QQ经典农场", 50, 80, width, 1155)

    def _point(self, cell, offset, width):
        u, v = cell
        scale = np.asarray([width, 1155], dtype=float)
        origin = np.asarray(self.wechat["normalized_origin"], dtype=float)
        u_step = np.asarray(self.wechat["normalized_u_step"], dtype=float)
        v_step = np.asarray(self.wechat["normalized_v_step"], dtype=float)
        off = np.asarray(offset, dtype=float)
        return np.rint(
            (origin + u*u_step + v*v_step + off) * scale
        ).astype(int)

    def _paint(self, rgb, point, value):
        x, y = point
        r = self.cfg["patch_radius"]
        rgb[y-r:y+r+1, x-r:x+r+1] = value

    def image(self, width=625, *, occupied=(), ambiguous=()):
        rgb = np.zeros((1155, width, 3), dtype=np.uint8)
        occupied = set(occupied)
        ambiguous = set(ambiguous)
        for cell in ALL_CELLS:
            grade = "purple" if cell in self.purple else "gold"
            soil = self.cfg["soil_prototypes"][grade]
            self._paint(
                rgb,
                self._point(cell, self.cfg["soil_offset_normalized"], width),
                (120, 120, 120) if cell in ambiguous else soil,
            )
            self._paint(
                rgb,
                self._point(cell, self.cfg["occupancy_offset_normalized"], width),
                ((145, 145, 145) if cell in ambiguous
                 else (60, 60, 60) if cell in occupied
                 else (190, 190, 190)),
            )
        return rgb

    def shot(self, rgb, *, capture_id="wechat-v2"):
        h, w = rgb.shape[:2]
        return FarmCapture(
            self.frame(w),
            np.asarray(rgb.mean(axis=2), dtype=np.float32),
            capture_id=capture_id,
            captured_at_ns=123456789,
            rgb=rgb,
        )

    def test_empty_accepts_both_verified_widths(self):
        for width in (625, 627):
            with self.subTest(width=width):
                result = check_wechat_empty_field(
                    self.shot(self.image(width)), self.layout)
                self.assertEqual(result.status, "EMPTY")
                self.assertEqual(set(result.empty_cells), set(ALL_CELLS))
                self.assertEqual(result.unknown_cells, ())

    def test_all_seedlings_are_not_empty(self):
        result = check_wechat_empty_field(
            self.shot(self.image(625, occupied=ALL_CELLS)), self.layout)
        self.assertEqual(result.status, "NOT_EMPTY")
        self.assertEqual(set(result.occupied_cells), set(ALL_CELLS))
        self.assertEqual(result.unknown_cells, ())

    def test_ambiguous_cell_is_unknown_not_empty(self):
        target = {(0, 0)}
        result = check_wechat_empty_field(
            self.shot(self.image(625, ambiguous=target)), self.layout)
        self.assertEqual(result.status, "UNKNOWN")
        self.assertEqual(set(result.unknown_cells), target)
        self.assertEqual(result.occupied_cells, ())

    def test_untrusted_or_wrong_size_is_unknown(self):
        rgb = self.image(625)
        self.assertEqual(
            check_wechat_empty_field(
                self.shot(rgb, capture_id=""), self.layout).status,
            "UNKNOWN",
        )
        wrong = np.zeros((1155, 624, 3), dtype=np.uint8)
        frame = WindowFrame("微信", "QQ经典农场", 0, 0, 624, 1155)
        shot = FarmCapture(
            frame, wrong.mean(axis=2).astype(np.float32),
            capture_id="wrong", captured_at_ns=1, rgb=wrong,
        )
        self.assertEqual(
            check_wechat_empty_field(shot, self.layout).reason,
            "WINDOW_SIZE_CHANGED",
        )

    def test_runner_check_empty_supports_wechat_read_only(self):
        shot = self.shot(self.image(625))
        handle = WindowHandle(99, 88, shot.frame)
        with (patch("farm_runner.find_farm_window", return_value=handle) as registry,
              patch("farm_runner.capture_window", return_value=shot) as capture):
            result = read_only_empty_check(
                "wechat", self.layout, Path("/tmp/registry"))
        self.assertEqual(result["status"], "EMPTY")
        self.assertEqual(result["click_count"], 0)
        self.assertEqual(registry.call_count, 2)
        capture.assert_called_once()

    def test_live_empty_gate_is_read_only_and_does_not_unlock_wechat_actions(self):
        empty = self.shot(self.image(625))
        planted = self.shot(self.image(625, occupied=ALL_CELLS), capture_id="planted")
        handle = WindowHandle(99, 88, empty.frame)
        adapter = LivePlantAdapter(
            "wechat", self.layout, Path("/tmp/registry"),
            Path("/tmp/click"), execute=True)

        with (patch.object(adapter, "_capture", return_value=(handle, empty)),
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            self.assertTrue(adapter.require_empty_field())
            cg.assert_not_called()

        with (patch.object(adapter, "_capture", return_value=(handle, planted)),
              patch("farm_plant_live.subprocess.run",
                    side_effect=AssertionError("No CGEvent")) as cg):
            self.assertTrue(adapter.verify_cells_occupied(
                frozenset({(3, 2)})))
            cg.assert_not_called()

        with patch("farm_plant_live.subprocess.run",
                   side_effect=AssertionError("No CGEvent")) as cg:
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.open_plot((3, 2))
            self.assertEqual(caught.exception.code, "PLANT_PHASE_UNAUTHORIZED")
            cg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
