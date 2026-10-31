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

    def test_live_adapter_returns_only_observed_landing_and_never_clicks(self):
        before = self.empty()
        after = before.copy()
        self.add_seedling(after, (2, 2))
        handle = WindowHandle(6951, 53086, self.frame)
        adapter = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                   Path("/tmp/click"), execute=True)
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.find_farm_window", return_value=handle),
              patch("farm_plant_live.capture_window", side_effect=[
                  self.shot(before, "before", 100), self.shot(after, "after", 200)]),
              patch("farm_plant_live.subprocess.run", side_effect=AssertionError("No click"))):
            baseline_handle, baseline_shot = adapter.capture_landing_baseline()
            proof = adapter.verify_landing_since(baseline_handle, baseline_shot)
        self.assertEqual(proof.observed_cell, (2, 2))
        self.assertFalse(adapter.last_diagnostics["can_authorize_clicks"])
        self.assertFalse(adapter.last_diagnostics["inventory_updated"])
        self.assertFalse(adapter.calibration_verified)

    def test_live_adapter_unknown_result_stops_without_action(self):
        before = self.empty()
        handle = WindowHandle(6951, 53086, self.frame)
        adapter = LivePlantAdapter("qq", self.layout, Path("/tmp/registry"),
                                   execute=True)
        with (patch("farm_plant_live.require_live_window"),
              patch("farm_plant_live.find_farm_window", return_value=handle),
              patch("farm_plant_live.capture_window", side_effect=[
                  self.shot(before, "before", 100), self.shot(before, "after", 200)])):
            baseline_handle, baseline_shot = adapter.capture_landing_baseline()
            with self.assertRaises(SpecialPlantStop) as caught:
                adapter.verify_landing_since(baseline_handle, baseline_shot)
        self.assertEqual(caught.exception.code, "PLANT_LANDING_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
