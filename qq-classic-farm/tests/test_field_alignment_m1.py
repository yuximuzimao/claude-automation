"""M1 read-only grid translation tests; synthetic tiles, no game I/O."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import CaptureStop, FarmCapture
from farm_field import FieldStop, _expected_purple, probe_field_translation
from farm_geometry import WindowFrame, plot_local_point


LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))


def synthetic(platform: str, *, shift=(-9, 18), scale=1, missing=False, extra=False):
    width, height = LAYOUT["platforms"][platform]["baseline_window_size"]
    frame = WindowFrame("QQ小程序" if platform == "qq" else "微信",
                        "QQ经典农场", 100, 200, width, height)
    image = Image.new("RGB", (width * scale, height * scale), (70, 135, 75))
    draw = ImageDraw.Draw(image)
    cells = sorted(_expected_purple(platform, LAYOUT))
    for index, (u, v) in enumerate(cells):
        if missing and index == 0:
            continue
        x, y = plot_local_point(platform, u, v, frame, LAYOUT)
        x, y = round((x + shift[0]) * scale), round((y + shift[1]) * scale)
        draw.polygon([(x, y - 18 * scale), (x + 30 * scale, y),
                      (x, y + 18 * scale), (x - 30 * scale, y)],
                     fill=(190, 125, 220))
    if extra:
        # An unrelated purple decorative element must not shift the grid.
        draw.ellipse((95 * scale, 550 * scale, 145 * scale, 585 * scale),
                     fill=(190, 125, 220))
    rgb = np.asarray(image, dtype=np.uint8)
    return FarmCapture(frame, np.mean(rgb, axis=2).astype(np.float32), rgb=rgb)


class FieldAlignmentTests(unittest.TestCase):
    def test_qq_and_wechat_translation_is_diagnostic_only(self):
        for platform, shift in (("qq", (-9, 18)), ("wechat", (-60, 1))):
            with self.subTest(platform=platform):
                result = probe_field_translation(synthetic(platform, shift=shift),
                                                 platform, LAYOUT)
                self.assertEqual(result["status"], "diagnostic_only")
                self.assertFalse(result["can_authorize_clicks"])
                self.assertEqual(result["matched_purple_cells"], 5 if platform == "qq" else 8)
                self.assertAlmostEqual(result["offset_local"][0], shift[0], delta=1)
                self.assertAlmostEqual(result["offset_local"][1], shift[1], delta=1)

    def test_retina_2x_uses_logical_translation(self):
        result = probe_field_translation(synthetic("wechat", shift=(-60, 1), scale=2),
                                         "wechat", LAYOUT)
        self.assertAlmostEqual(result["offset_local"][0], -60, delta=1)
        self.assertAlmostEqual(result["offset_local"][1], 1, delta=1)
        self.assertFalse(result["can_authorize_clicks"])

    def test_decorative_purple_does_not_override_unique_grid(self):
        result = probe_field_translation(synthetic("qq", extra=True), "qq", LAYOUT)
        self.assertEqual(result["matched_purple_cells"], 5)

    def test_partial_or_obscured_grid_fails_closed(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                with self.assertRaises(FieldStop) as caught:
                    probe_field_translation(synthetic(platform, missing=True), platform, LAYOUT)
                self.assertEqual(caught.exception.code, "FIELD_ALIGNMENT_UNAVAILABLE")

    def test_missing_color_is_not_treated_as_calibration(self):
        capture = synthetic("qq")
        capture = FarmCapture(capture.frame, capture.gray)
        with self.assertRaises(FieldStop) as caught:
            probe_field_translation(capture, "qq", LAYOUT)
        self.assertEqual(caught.exception.code, "FIELD_COLOR_REQUIRED")

    def test_bad_rgb_dimensions_are_rejected_at_capture_boundary(self):
        capture = synthetic("qq")
        with self.assertRaises(CaptureStop) as caught:
            FarmCapture(capture.frame, capture.gray, rgb=capture.rgb[:, :-1])
        self.assertEqual(caught.exception.code, "INVALID_SCREENSHOT")


if __name__ == "__main__":
    unittest.main()
