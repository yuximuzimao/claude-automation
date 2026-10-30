"""M1 background scene registration is read-only, including occupied-field replay."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import FarmCapture
from farm_clean_field import CleanFieldStop, compare_clean_reference
from farm_scene import BACKGROUND_ANCHORS, SceneStop, probe_scene_translation
from test_field_alignment_m1 import synthetic

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))


def scene_pair(platform: str, scale: int = 1, *, shift=(-2, 3), obscure=None):
    original = synthetic(platform, scale=scale)
    reference_rgb = original.rgb.copy()
    rng = np.random.default_rng(20261030)
    for x, y in BACKGROUND_ANCHORS[platform]:
        cx, cy = x * scale, y * scale
        w = 32 * scale
        reference_rgb[cy-w:cy+w, cx-w:cx+w] = rng.integers(
            0, 256, (2*w, 2*w, 3), dtype=np.uint8
        )
    reference = FarmCapture(original.frame, np.mean(reference_rgb, axis=2).astype(np.float32),
                            rgb=reference_rgb)
    dx, dy = shift
    current_rgb = np.roll(reference_rgb, (dy * scale, dx * scale), axis=(0, 1))
    # Occupied plots hide all purple soil; reference still has exposed purple.
    purple = np.all(current_rgb == (190, 125, 220), axis=2)
    current_rgb[purple] = (15, 25, 15)
    if obscure is not None:
        x, y = BACKGROUND_ANCHORS[platform][obscure]
        cx, cy = (x + dx) * scale, (y + dy) * scale
        w = 35 * scale
        current_rgb[cy-w:cy+w, cx-w:cx+w] = (20, 20, 20)
    current = FarmCapture(original.frame, np.mean(current_rgb, axis=2).astype(np.float32),
                          rgb=current_rgb)
    return current, reference


class SceneAlignmentTests(unittest.TestCase):
    def test_occupied_field_can_use_read_only_background_reference(self):
        for platform in ("qq", "wechat"):
            for scale in (1, 2):
                with self.subTest(platform=platform, scale=scale):
                    current, reference = scene_pair(platform, scale)
                    result = compare_clean_reference(current, reference, platform, LAYOUT)
                    self.assertEqual(result["cell_count"], 24)
                    self.assertEqual(result["capture_alignment_method"],
                                     "background_reference_inferred")
                    self.assertEqual(result["scene_alignment"]["anchor_count"], 3)
                    self.assertAlmostEqual(result["scene_alignment"]["scene_shift_local"][0],
                                           -2, delta=0.6)
                    self.assertAlmostEqual(result["scene_alignment"]["scene_shift_local"][1],
                                           3, delta=0.6)
                    self.assertIsNone(result["empty_cells"])
                    self.assertFalse(result["can_authorize_clicks"])

    def test_obscured_background_landmark_stops_instead_of_guessing(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                current, reference = scene_pair(platform, obscure=1)
                with self.assertRaises(CleanFieldStop) as caught:
                    compare_clean_reference(current, reference, platform, LAYOUT)
                self.assertEqual(caught.exception.code, "FIELD_ALIGNMENT_UNAVAILABLE")

    def test_inconsistent_background_landmarks_rejected(self):
        current, reference = scene_pair("qq")
        rgb = current.rgb.copy()
        # Move only the first unique landmark without moving the rest.
        x, y = BACKGROUND_ANCHORS["qq"][0]
        w = 32
        src_x, src_y = x - 2, y + 3
        patch = rgb[src_y-w:src_y+w, src_x-w:src_x+w].copy()
        rgb[src_y-w:src_y+w, src_x-w:src_x+w] = (70, 135, 75)
        rgb[src_y-w:src_y+w, src_x-w+16:src_x+w+16] = patch
        altered = FarmCapture(current.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)
        with self.assertRaises(SceneStop) as caught:
            probe_scene_translation(altered, reference, "qq", LAYOUT)
        self.assertEqual(caught.exception.code, "SCENE_ALIGNMENT_AMBIGUOUS")

    def test_reference_scene_cannot_self_authorize_clicks(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                current, reference = scene_pair(platform, shift=(0, 0))
                result = probe_scene_translation(current, reference, platform, LAYOUT)
                self.assertEqual(result["scene_shift_local"], [0.0, 0.0])
                self.assertEqual(result["status"], "diagnostic_only")
                self.assertFalse(result["can_authorize_clicks"])


if __name__ == "__main__":
    unittest.main()
