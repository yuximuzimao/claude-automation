"""Portable replay for registered full-field clean postcondition.

Uses the four real QQ single-radish crop states as negative/positive examples;
no Mac window, input or historical /tmp file is required.
"""
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
from farm_field_postcondition import (
    FieldPostconditionStop, compare_empty_field_postcondition,
)
from farm_geometry import WindowFrame


class RegisteredPostconditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        cls.frame = WindowFrame("QQ小程序", "QQ经典农场", 0, 0, 603, 1111)
        cls.offset = (-9.35, 18.4)
        cfg = cls.layout["platforms"]["qq"]
        cls.center = (
            round(cfg["origin"][0] + 3 * cfg["u_step"][0] + 2 * cfg["v_step"][0] + cls.offset[0]),
            round(cfg["origin"][1] + 3 * cfg["u_step"][1] + 2 * cfg["v_step"][1] + cls.offset[1]),
        )
        cls.images = {
            state: np.asarray(Image.open(ROOT / f"assets/ui/field/qq-radish-gold-registered-{state}.png").convert("RGB"))
            for state in ("empty", "seedling", "mature", "harvested")
        }

    def field(self, state):
        rgb = np.full((1111, 603, 3), 150, dtype=np.uint8)
        x, y = self.center
        rgb[y-55:y+55, x-42:x+43] = self.images[state]
        return rgb

    def shot(self, rgb, n):
        return FarmCapture(
            self.frame, np.mean(rgb, axis=2).astype(np.float32),
            capture_id=f"real-replay-{n}", captured_at_ns=n, rgb=rgb,
        )

    def analyze(self, empty, idle, candidate, approved=True):
        with patch("farm_field_postcondition.probe_field_translation",
                   return_value={"offset_local": list(self.offset)}):
            return compare_empty_field_postcondition(
                self.shot(empty, 1), self.shot(idle, 2), self.shot(candidate, 3),
                "qq", self.layout, empty_reference_verified=approved,
            )

    def test_real_radish_seedling_and_mature_are_not_clean(self):
        base = self.field("empty")
        for state in ("seedling", "mature"):
            with self.subTest(state=state):
                result = self.analyze(base, base.copy(), self.field(state))
                self.assertFalse(result.clean_field_verified)
                self.assertTrue(result.changed_cells)
                self.assertFalse(result.can_authorize_clicks)

    def test_real_harvested_crop_matches_empty(self):
        base = self.field("empty")
        result = self.analyze(base, base.copy(), self.field("harvested"))
        self.assertTrue(result.clean_field_verified)
        self.assertEqual(len(result.clean_cells), 24)
        self.assertFalse(result.unknown_cells)

    def test_crop_outside_center_patch_cannot_be_silently_clean(self):
        base = self.field("empty")
        crop = base.copy()
        x, y = self.center
        crop[y-24:y-14, x+15:x+25] = (20, 90, 15)
        result = self.analyze(base, base.copy(), crop)
        self.assertFalse(result.clean_field_verified)
        self.assertTrue(result.changed_cells)

    def test_two_by_two_seedling_outside_old_center_roi_stops_clean(self):
        base = self.field("empty")
        crop = base.copy()
        x, y = self.center
        crop[y-20:y-18, x+18:x+20] = (15, 55, 20)
        result = self.analyze(base, base.copy(), crop)
        self.assertFalse(result.clean_field_verified)
        self.assertTrue(result.changed_cells or result.unknown_cells)

    def test_animated_decoration_stops_clean_claim(self):
        base = self.field("empty")
        idle = base.copy()
        cfg = self.layout["platforms"]["qq"]
        x = round(cfg["origin"][0] + self.offset[0])
        y = round(cfg["origin"][1] + self.offset[1])
        idle[y-18:y-10, x-10:x+2] = 255
        result = self.analyze(base, idle, base.copy())
        self.assertFalse(result.clean_field_verified)
        self.assertTrue(result.unknown_cells)

    def test_reference_must_be_independently_approved(self):
        base = self.field("empty")
        with self.assertRaises(FieldPostconditionStop) as cm:
            self.analyze(base, base, base, approved=False)
        self.assertEqual(cm.exception.code, "EMPTY_REFERENCE_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
