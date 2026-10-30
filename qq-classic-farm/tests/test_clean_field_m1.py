"""Read-only M1 clean-field comparison tests; no game I/O or click permission."""
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
from farm_geometry import WindowFrame, plot_local_point
from test_field_alignment_m1 import synthetic

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))


def with_crop(capture: FarmCapture, platform: str, *, cell=(3, 3)) -> FarmCapture:
    rgb = capture.rgb.copy()
    x, y = plot_local_point(platform, *cell, capture.frame, LAYOUT)
    # Synthetic test fixtures use (-9,+18) alignment.
    x, y = round(x - 9), round(y + 18)
    rgb[y-8:y+9, x-16:x+17] = (10, 20, 10)
    return FarmCapture(capture.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)


class CleanFieldDiagnosticTests(unittest.TestCase):
    def test_identical_reference_reports_24_numeric_diagnostics_not_empty_flags(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                ref = synthetic(platform)
                result = compare_clean_reference(ref, ref, platform, LAYOUT)
                self.assertEqual(result["status"], "diagnostic_only")
                self.assertEqual(result["cell_count"], 24)
                self.assertEqual(len(result["cells"]), 24)
                self.assertIsNone(result["empty_cells"])
                self.assertFalse(result["can_authorize_clicks"])
                self.assertTrue(all(c["mean_abs_rgb"] == 0 for c in result["cells"]))
                self.assertTrue(all(c["fraction_pixels_all_rgb_within_12"] == 1
                                    and c["fraction_pixels_all_rgb_within_24"] == 1
                                    for c in result["cells"]))

    def test_independent_alignment_handles_shift_and_retina(self):
        for platform in ("qq", "wechat"):
            for scale in (1, 2):
                with self.subTest(platform=platform, scale=scale):
                    reference = synthetic(platform, shift=(-9, 18), scale=scale)
                    current = synthetic(platform, shift=(-12, 20), scale=scale)
                    result = compare_clean_reference(current, reference, platform, LAYOUT)
                    self.assertEqual(result["cell_count"], 24)
                    self.assertLess(max(c["mean_abs_rgb"] for c in result["cells"]), 12)
                    self.assertFalse(result["can_authorize_clicks"])

    def test_same_pixels_with_slightly_different_logical_frames_stay_aligned(self):
        # A window registry can report a 1-point size difference even when the
        # screenshot has identical pixel dimensions. Each image needs its own
        # pixel/logical scale; reusing the current scale shifts reference ROIs.
        for platform in ("qq", "wechat"):
            for scale in (1, 2):
                with self.subTest(platform=platform, scale=scale):
                    base = synthetic(platform, scale=scale)
                    # Add fine-grained texture within each measured center ROI;
                    # uniform synthetic soil would hide a one-pixel ROI shift.
                    rgb = base.rgb.copy()
                    for u in range(6):
                        for v in range(4):
                            x, y = plot_local_point(platform, u, v, base.frame, LAYOUT)
                            cx, cy = round((x - 9) * scale), round((y + 18) * scale)
                            for py in range(cy - 8 * scale, cy + 9 * scale):
                                for px in range(cx - 16 * scale, cx + 17 * scale):
                                    if tuple(rgb[py, px]) == (190, 125, 220):
                                        rgb[py, px] = (190, 125, 220) if (px + py) % 2 else (200, 135, 230)
                                    else:
                                        rgb[py, px] = (70, 135, 75) if (px + py) % 2 else (85, 150, 90)
                    current = FarmCapture(base.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)
                    frame = current.frame
                    reference_frame = WindowFrame(frame.owner, frame.title, frame.x, frame.y,
                                                  frame.width + 1, frame.height + 1)
                    reference = FarmCapture(reference_frame, current.gray, rgb=current.rgb)
                    result = compare_clean_reference(current, reference, platform, LAYOUT)
                    self.assertEqual(result["cell_count"], 24)
                    self.assertEqual(max(c["mean_abs_rgb"] for c in result["cells"]), 0)
                    self.assertFalse(result["can_authorize_clicks"])

    def test_changed_gold_plot_produces_difference_but_not_occupancy_claim(self):
        reference = synthetic("qq")
        current = with_crop(reference, "qq")
        result = compare_clean_reference(current, reference, "qq", LAYOUT)
        by_cell = {tuple(c["cell"]): c for c in result["cells"]}
        self.assertGreater(by_cell[(3, 3)]["mean_abs_rgb"], 40)
        self.assertIsNone(result["empty_cells"])

    def test_clean_field_with_global_tint_must_not_be_called_occupied(self):
        reference = synthetic("qq")
        rgb = np.clip(reference.rgb.astype(np.int16) + 20, 0, 255).astype(np.uint8)
        current = FarmCapture(reference.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)
        result = compare_clean_reference(current, reference, "qq", LAYOUT)
        self.assertTrue(all(c["mean_abs_rgb"] > 10 for c in result["cells"]))
        self.assertIsNone(result["empty_cells"])
        self.assertFalse(result["can_authorize_clicks"])

    def test_global_rgb_tint_is_removed_as_diagnostic_not_empty_proof(self):
        for platform in ("qq", "wechat"):
            for scale in (1, 2):
                with self.subTest(platform=platform, scale=scale):
                    reference = synthetic(platform, scale=scale)
                    tint = np.array([12, -8, 20], dtype=np.int16)
                    rgb = np.clip(reference.rgb.astype(np.int16) + tint, 0, 255).astype(np.uint8)
                    current = FarmCapture(reference.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)
                    result = compare_clean_reference(current, reference, platform, LAYOUT)
                    self.assertEqual(result["global_rgb_offset"], [12.0, -8.0, 20.0])
                    self.assertTrue(all(c["mean_abs_rgb_after_global_offset"] == 0
                                        for c in result["cells"]))
                    self.assertIsNone(result["empty_cells"])
                    self.assertFalse(result["can_authorize_clicks"])

    def test_local_crop_remains_distinct_after_global_tint_correction(self):
        reference = synthetic("qq")
        tinted = np.clip(reference.rgb.astype(np.int16) + 15, 0, 255).astype(np.uint8)
        current = FarmCapture(reference.frame, np.mean(tinted, axis=2).astype(np.float32), rgb=tinted)
        current = with_crop(current, "qq", cell=(3, 3))
        result = compare_clean_reference(current, reference, "qq", LAYOUT)
        by_cell = {tuple(c["cell"]): c for c in result["cells"]}
        self.assertEqual(result["global_rgb_offset"], [15.0, 15.0, 15.0])
        self.assertGreater(by_cell[(3, 3)]["mean_abs_rgb_after_global_offset"], 30)
        self.assertGreater(by_cell[(3, 3)]["median_abs_rgb_after_global_offset"], 30)
        self.assertGreaterEqual(by_cell[(3, 3)]["p90_abs_rgb_after_global_offset"],
                                by_cell[(3, 3)]["median_abs_rgb_after_global_offset"])
        self.assertLess(max(c["mean_abs_rgb_after_global_offset"] for c in result["cells"]
                            if c["cell"] != [3, 3]), 1)
        self.assertLess(by_cell[(3, 3)]["fraction_pixels_all_rgb_within_12"], 0.1)
        self.assertTrue(all(c["fraction_pixels_all_rgb_within_12"] == 1
                            for c in result["cells"] if c["cell"] != [3, 3]))
        self.assertIsNone(result["empty_cells"])
        self.assertFalse(result["can_authorize_clicks"])

    def test_local_animated_highlights_leave_partial_pixel_agreement(self):
        reference = synthetic("qq")
        rgb = reference.rgb.copy()
        x, y = plot_local_point("qq", 3, 3, reference.frame, LAYOUT)
        x, y = round(x - 9), round(y + 18)
        # Change a band within the measured center patch; the other rows stay
        # unchanged. Mean/P90 can rise without the entire cell changing.
        rgb[y-6:y-2, x-13:x+14] = (5, 15, 5)
        current = FarmCapture(reference.frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)
        result = compare_clean_reference(current, reference, "qq", LAYOUT)
        by_cell = {tuple(c["cell"]): c for c in result["cells"]}
        self.assertGreater(by_cell[(3, 3)]["mean_abs_rgb_after_global_offset"], 10)
        self.assertGreater(by_cell[(3, 3)]["fraction_pixels_all_rgb_within_12"], 0.6)
        self.assertLess(by_cell[(3, 3)]["fraction_pixels_all_rgb_within_12"], 0.8)
        self.assertIsNone(result["empty_cells"])
        self.assertFalse(result["can_authorize_clicks"])

    def test_missing_purple_or_reference_color_fails_closed(self):
        reference = synthetic("qq")
        missing = synthetic("qq", missing=True)
        with self.assertRaises(CleanFieldStop) as caught:
            compare_clean_reference(missing, reference, "qq", LAYOUT)
        self.assertEqual(caught.exception.code, "FIELD_ALIGNMENT_UNAVAILABLE")
        no_rgb = FarmCapture(reference.frame, reference.gray)
        with self.assertRaises(CleanFieldStop) as caught:
            compare_clean_reference(reference, no_rgb, "qq", LAYOUT)
        self.assertEqual(caught.exception.code, "FIELD_COLOR_REQUIRED")

    def test_wrong_reference_and_unsafe_patch_rejected(self):
        qq = synthetic("qq")
        wechat = synthetic("wechat")
        with self.assertRaises(CleanFieldStop) as caught:
            compare_clean_reference(qq, wechat, "qq", LAYOUT)
        self.assertIn(caught.exception.code, ("FIELD_REFERENCE_MISMATCH", "WRONG_FRONTMOST_APP"))
        with self.assertRaises(CleanFieldStop) as caught:
            compare_clean_reference(qq, qq, "qq", LAYOUT, half_width=99)
        self.assertEqual(caught.exception.code, "INVALID_FIELD_PATCH")


if __name__ == "__main__":
    unittest.main()
