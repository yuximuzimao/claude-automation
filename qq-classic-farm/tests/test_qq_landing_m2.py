"""QQ M2 controlled-test landing proof: only actual seedling evidence, no I/O."""
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
from farm_io import WindowHandle
from farm_plant_live import LivePlantAdapter
from farm_plant_special import SpecialPlantStop
from farm_qq_clean import ALL_CELLS, ATLAS, PATCH_SIZE
from farm_qq_landing import GOLD_PATCH, PURPLE_PATCH, verify_qq_single_radish_landing


class LandingProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        cls.grid = cls.layout["platforms"]["qq"]
        cls.atlas = np.asarray(Image.open(ATLAS).convert("RGB"))
        cls.frame = WindowFrame("QQ小程序", "QQ经典农场", 100, 100, 603, 1111)

    def center(self, cell):
        u, v = cell
        g = self.grid
        return (round(g["origin"][0] + u*g["u_step"][0] + v*g["v_step"][0]),
                round(g["origin"][1] + u*g["u_step"][1] + v*g["v_step"][1]))

    def empty(self):
        rgb = np.full((1111, 603, 3), 100, dtype=np.uint8)
        for u, v in ALL_CELLS:
            x, y = self.center((u, v))
            rgb[y-9:y+10, x-9:x+10] = self.atlas[
                v*PATCH_SIZE:(v+1)*PATCH_SIZE,
                u*PATCH_SIZE:(u+1)*PATCH_SIZE]
        return rgb

    def add_seedling(self, rgb, cell):
        x, y = self.center(cell)
        purple = cell in {(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)}
        with Image.open(PURPLE_PATCH if purple else GOLD_PATCH) as im:
            patch = np.asarray(im.convert("RGB"))
        if purple:
            rgb[y+11:y+24, x-19:x-3] = patch
        else:
            rgb[y+5:y+27, x-23:x+24] = patch

    def shot(self, rgb, id, ns, frame=None):
        return FarmCapture(frame or self.frame, rgb.mean(axis=2).astype(np.float32),
                           capture_id=id, captured_at_ns=ns, rgb=rgb)

    def test_real_gold_and_purple_seedling_reveal_actual_landing(self):
        for cell in ((2, 2), (0, 0)):
            with self.subTest(cell=cell):
                before = self.empty()
                after = before.copy()
                self.add_seedling(after, cell)
                proof = verify_qq_single_radish_landing(
                    self.shot(before, "before", 100), self.shot(after, "after", 200),
                    self.layout)
                self.assertIsNotNone(proof)
                self.assertEqual(proof.observed_cell, cell)
                self.assertEqual(proof.seed, "白萝卜")

    def test_no_seedling_or_unrelated_change_never_proves_landing(self):
        before = self.empty()
        unchanged = before.copy()
        other = before.copy()
        x, y = self.center((2, 2))
        other[y+13:y+18, x-8:x-3] = (0, 0, 0)
        for after in (unchanged, other, before // 2):
            self.assertIsNone(verify_qq_single_radish_landing(
                self.shot(before, "a", 100), self.shot(after, "b", 200), self.layout))

    def test_multiple_seedlings_stale_or_moved_window_stop(self):
        before = self.empty()
        after = before.copy()
        self.add_seedling(after, (2, 2))
        self.add_seedling(after, (0, 0))
        self.assertIsNone(verify_qq_single_radish_landing(
            self.shot(before, "a", 100), self.shot(after, "b", 200), self.layout))
        after = before.copy()
        self.add_seedling(after, (2, 2))
        for id, ns in (("a", 200), ("b", 100)):
            self.assertIsNone(verify_qq_single_radish_landing(
                self.shot(before, "a", 100), self.shot(after, id, ns), self.layout))
        moved = WindowFrame("QQ小程序", "QQ经典农场", 101, 100, 603, 1111)
        self.assertIsNone(verify_qq_single_radish_landing(
            self.shot(before, "a", 100), self.shot(after, "b", 200, moved),
            self.layout))

    def test_legacy_live_landing_route_is_retired_without_input(self):
        adapter = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                   Path("/tmp/click"), execute=True)
        with patch("farm_plant_live.subprocess.run", side_effect=AssertionError("No click")):
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.capture_landing_baseline()
            self.assertEqual(caught.exception.code, "PLANT_LANDING_METHOD_UNSAFE")
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.verify_landing_since(None, None)
            self.assertEqual(caught.exception.code, "PLANT_LANDING_METHOD_UNSAFE")

    def test_live_three_frame_diagnostic_never_authorizes_clicks(self):
        before = self.empty()
        idle = before.copy()
        after = before.copy()
        x, y = self.center((0, 0))
        # Simulate a sprite inside the independently registered field.
        after[y+14:y+22, x-13:x-5] = (25, 85, 15)
        handle = WindowHandle(6951, 53086, self.frame)
        adapter = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                   Path("/tmp/click"), execute=True)
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.find_farm_window", return_value=handle),
              patch("farm_plant_live.capture_window", side_effect=[
                  self.shot(before, "before", 100),
                  self.shot(idle, "idle", 200),
                  self.shot(after, "after", 300)]),
              patch("farm_plant_live.sleep", return_value=None),
              patch("farm_plant_live.probe_field_translation",
                    return_value={"offset_local": [-9, 18]}),
              patch("farm_plant_live.subprocess.run", side_effect=AssertionError("No click"))):
            h, b, i = adapter.capture_field_delta_control()
            evidence = adapter.verify_field_delta_since(h, b, i)
        self.assertEqual(evidence.status, "diagnostic_only")
        self.assertGreaterEqual(evidence.changed_pixels, 6)
        self.assertFalse(evidence.can_authorize_clicks)
        self.assertFalse(adapter.calibration_verified)
        self.assertFalse(adapter.last_diagnostics["can_authorize_clicks"])


if __name__ == "__main__":
    unittest.main()
