"""Fail-closed QQ 24-cell clean-field postcondition, including tiny seedlings."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import FarmCapture
from farm_geometry import WindowFrame
from farm_qq_clean import ALL_CELLS, ATLAS, PATCH_SIZE, observe_qq_clean_cells
from farm_io import WindowHandle
from farm_harvest_live import LiveHarvestAdapter
from farm_plant_live import LivePlantAdapter
from farm_plant_special import SpecialPlantStop


class QQCleanFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        cls.atlas = np.asarray(Image.open(ATLAS).convert("RGB"))
        cls.g = cls.layout["platforms"]["qq"]
        cls.frame = WindowFrame("QQ小程序", "QQ经典农场", 100, 100, 603, 1111)

    def image(self):
        rgb = np.full((1111, 603, 3), 100, dtype=np.uint8)
        g = self.g
        for u, v in ALL_CELLS:
            x = round(g["origin"][0] + u*g["u_step"][0] + v*g["v_step"][0])
            y = round(g["origin"][1] + u*g["u_step"][1] + v*g["v_step"][1])
            rgb[y-9:y+10, x-9:x+10] = self.atlas[
                v*PATCH_SIZE:(v+1)*PATCH_SIZE,
                u*PATCH_SIZE:(u+1)*PATCH_SIZE,
            ]
        return rgb

    def shot(self, rgb, *, capture_id="new", frame=None):
        return FarmCapture(
            frame or self.frame,
            rgb.mean(axis=2).astype(np.float32),
            capture_id=capture_id,
            captured_at_ns=123,
            rgb=rgb,
        )

    def center(self, cell):
        u, v = cell
        return (round(self.g["origin"][0] + u*self.g["u_step"][0] + v*self.g["v_step"][0]),
                round(self.g["origin"][1] + u*self.g["u_step"][1] + v*self.g["v_step"][1]))

    def test_all_24_empty_from_verified_atlas(self):
        self.assertEqual(observe_qq_clean_cells(self.shot(self.image()), self.layout), 24)

    def test_two_by_two_seedling_rejected_on_gold_and_purple(self):
        for cell in ((3, 2), (0, 0)):
            for sprout_color in ((40, 110, 23), (63, 37, 23)):
                with self.subTest(cell=cell, color=sprout_color):
                    rgb = self.image()
                    x, y = self.center(cell)
                    rgb[y:y+2, x:x+2] = sprout_color
                    self.assertIsNone(observe_qq_clean_cells(self.shot(rgb), self.layout))

    def test_off_center_visible_crop_rejected(self):
        rgb = self.image()
        x, y = self.center((4, 2))
        rgb[y+3:y+10, x+3:x+10] = (25, 85, 15)
        self.assertIsNone(observe_qq_clean_cells(self.shot(rgb), self.layout))

    def test_dimmed_overlay_rejected(self):
        rgb = self.image() // 2
        self.assertIsNone(observe_qq_clean_cells(self.shot(rgb), self.layout))

    def test_layout_drift_and_untrusted_capture_rejected(self):
        rgb = self.image()
        self.assertIsNone(observe_qq_clean_cells(self.shot(rgb, capture_id=""), self.layout))
        drift = json.loads(json.dumps(self.layout))
        drift["platforms"]["qq"]["origin"][0] += 4
        self.assertIsNone(observe_qq_clean_cells(self.shot(rgb), drift))
        altered = json.loads(json.dumps(self.layout))
        altered["platforms"]["qq"]["land_grades"]["purple_cells"].remove([1, 1])
        self.assertIsNone(observe_qq_clean_cells(self.shot(rgb), altered))

    def test_live_adapters_keep_overlay_and_clicks_blocked_after_clean_proof(self):
        handle = WindowHandle(6951, 53086, self.frame)
        shot = self.shot(self.image())
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.find_farm_window", return_value=handle),
              patch("farm_plant_live.capture_window", return_value=shot)):
            plant = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                     Path("/tmp/click"), execute=True)
            view = plant.observe_field()
            self.assertEqual(len(view.field_cells), 24)
            self.assertFalse(any(view.field_cells.values()))
            self.assertEqual(view.overlay, "unknown")
            self.assertFalse(plant.calibration_verified)
            with self.assertRaises(SpecialPlantStop):
                plant._send_points(((300, 600),))
        with (patch("farm_harvest_live.require_live_window"),
              patch("farm_harvest_live.find_farm_window", return_value=handle),
              patch("farm_harvest_live.capture_window", return_value=shot),
              patch("farm_harvest_live.probe_harvest",
                    return_value={"hand": {"matched": False},
                                  "pickables": [], "raw_pickable_candidates": []})):
            harvest = LiveHarvestAdapter("qq", self.layout, {},
                                         Path("/tmp/registry"), execute=True)
            obs = harvest.observe()
            self.assertEqual(obs.empty_cells, (True,) * 24)
            self.assertEqual(obs.overlay, "unknown")
            self.assertFalse(obs.calibration_verified)


if __name__ == "__main__":
    unittest.main()
