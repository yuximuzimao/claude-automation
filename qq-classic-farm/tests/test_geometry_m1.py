"""M1 geometry tests with synthetic windows; no screenshots or mouse events."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from farm_geometry import GeometryStop, WindowFrame, plot_local_point, validate_farm_window


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))

    def test_qq_baseline_and_moved_window(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 800, 100, 603, 1111)
        validate_farm_window(frame, "qq", self.layout)
        x, y = plot_local_point("qq", 0, 0, frame, self.layout)
        self.assertAlmostEqual(x, 351.8319, delta=0.01)
        self.assertAlmostEqual(y, 566.2033, delta=0.01)
        self.assertEqual(frame.screen_point(100, 200), (900, 300))
        moved = WindowFrame("QQ小程序", "QQ经典农场", 10, 500, 603, 1111)
        self.assertEqual(moved.screen_point(x, y), (10 + x, 500 + y))

    def test_retina_pixel_to_local_then_screen(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 120, 40, 603, 1111)
        self.assertEqual(frame.pixel_to_local(400, 600, 1206, 2222), (200, 300))
        self.assertEqual(frame.pixel_to_screen(400, 600, 1206, 2222), (320, 340))

    def test_wechat_grid_and_special_anchor(self):
        frame = WindowFrame("微信", "QQ经典农场", 0, 0, 625, 1155)
        validate_farm_window(frame, "wechat", self.layout)
        anchor = self.layout["platforms"]["wechat"]["safe_special_2x2"][0]
        x, y = plot_local_point("wechat", *anchor["anchor_cell"], frame, self.layout)
        self.assertGreater(x, 0)
        self.assertLess(x, frame.width)
        self.assertGreater(y, 0)
        self.assertLess(y, frame.height)

    def test_mismatched_image_frame_stops(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 0, 0, 603, 1111)
        with self.assertRaises(GeometryStop) as caught:
            frame.pixel_to_local(100, 100, 2560, 1440)
        self.assertEqual(caught.exception.code, "SCREENSHOT_FRAME_MISMATCH")

    def test_wrong_owner_or_size_stops(self):
        wrong_owner = WindowFrame("QQ", "QQ经典农场", 0, 0, 603, 1111)
        with self.assertRaises(GeometryStop) as caught:
            validate_farm_window(wrong_owner, "qq", self.layout)
        self.assertEqual(caught.exception.code, "WRONG_FRONTMOST_APP")
        resized = WindowFrame("QQ小程序", "QQ经典农场", 0, 0, 900, 1111)
        with self.assertRaises(GeometryStop) as caught:
            validate_farm_window(resized, "qq", self.layout)
        self.assertEqual(caught.exception.code, "WINDOW_SIZE_CHANGED")

    def test_outside_and_invalid_points_stop(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 0, 0, 603, 1111)
        with self.assertRaises(GeometryStop):
            frame.screen_point(603, 0)
        with self.assertRaises(GeometryStop):
            frame.pixel_to_local(1206, 0, 1206, 2222)
        with self.assertRaises(GeometryStop):
            plot_local_point("qq", 6, 0, frame, self.layout)
        with self.assertRaises(GeometryStop):
            WindowFrame("QQ小程序", "QQ经典农场", 0, 0, -1, 1111)


if __name__ == "__main__":
    unittest.main()
