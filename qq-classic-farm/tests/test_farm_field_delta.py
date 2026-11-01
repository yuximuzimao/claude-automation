"""Whole-field radish calibration evidence: no-input control and off-center changes."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import FarmCapture
from farm_field_delta import analyze_field_delta, FieldDeltaStop
from farm_geometry import WindowFrame


class FieldDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        cls.frame = WindowFrame("QQ小程序", "QQ经典农场", 10, 20, 603, 1111)
        cls.cfg = cls.layout["platforms"]["qq"]

    def shot(self, rgb, name, t):
        return FarmCapture(self.frame, rgb.mean(axis=2).astype(np.float32),
                           capture_id=name, captured_at_ns=t, rgb=rgb)

    def test_change_outside_old_center_roi_is_visible(self):
        base = np.full((1111, 603, 3), 180, dtype=np.uint8)
        idle = base.copy()
        after = base.copy()
        ox, oy = self.cfg["origin"]
        x, y = round(ox), round(oy)
        # Off-center top-right of a nominal soil diamond: missed by the
        # historical 19x19 center and below-center sentinel.
        after[y-21:y-15, x+13:x+21] = (25, 85, 15)
        evidence = analyze_field_delta(self.shot(base, "before", 10),
                                       self.shot(idle, "idle", 20),
                                       self.shot(after, "after", 30),
                                       "qq", self.layout)
        self.assertGreaterEqual(evidence.changed_pixels, 6)
        self.assertFalse(evidence.can_authorize_clicks)
        self.assertEqual(evidence.status, "diagnostic_only")

    def test_sprite_spill_can_be_attributed_to_neighbor(self):
        base = np.full((1111, 603, 3), 180, dtype=np.uint8)
        after = base.copy()
        cfg = self.cfg
        x = round(cfg["origin"][0] + 3*cfg["u_step"][0] + 2*cfg["v_step"][0])
        y = round(cfg["origin"][1] + 3*cfg["u_step"][1] + 2*cfg["v_step"][1])
        # A visual sprite drawn above its own nominal (3,2) center can fall
        # in the nearest-cell area of (2,2); the diagnostic must not call
        # this a confirmed planting coordinate or occupancy.
        after[y-21:y-15, x+13:x+21] = (25, 85, 15)
        evidence = analyze_field_delta(self.shot(base, "before", 10),
                                       self.shot(base.copy(), "idle", 20),
                                       self.shot(after, "after", 30),
                                       "qq", self.layout)
        self.assertIn((2, 2), evidence.candidate_cells)
        self.assertFalse(evidence.can_authorize_clicks)

    def test_idle_animation_is_not_landing_evidence(self):
        base = np.full((1111, 603, 3), 180, dtype=np.uint8)
        idle = base.copy()
        after = base.copy()
        x, y = round(self.cfg["origin"][0]), round(self.cfg["origin"][1])
        idle[y-15:y-5, x:x+10] = (70, 80, 90)
        after[y-15:y-5, x:x+10] = (70, 80, 90)
        with self.assertRaises(FieldDeltaStop) as ctx:
            analyze_field_delta(self.shot(base, "before", 10),
                                self.shot(idle, "idle", 20),
                                self.shot(after, "after", 30),
                                "qq", self.layout)
        self.assertEqual(ctx.exception.code, "FIELD_DELTA_INCONCLUSIVE")

    def test_rejects_stale_and_window_movement(self):
        base = np.full((1111, 603, 3), 180, dtype=np.uint8)
        before = self.shot(base, "before", 10)
        idle = self.shot(base, "idle", 20)
        with self.assertRaises(FieldDeltaStop) as ctx:
            analyze_field_delta(before, idle, self.shot(base, "idle", 30),
                                "qq", self.layout)
        self.assertEqual(ctx.exception.code, "FIELD_DELTA_CAPTURE_INVALID")
        moved = FarmCapture(WindowFrame("QQ小程序", "QQ经典农场", 11, 20, 603, 1111),
                            before.gray, capture_id="after", captured_at_ns=30,
                            rgb=base)
        with self.assertRaises(FieldDeltaStop):
            analyze_field_delta(before, idle, moved, "qq", self.layout)


if __name__ == "__main__":
    unittest.main()
