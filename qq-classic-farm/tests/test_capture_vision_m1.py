"""M1 screenshot and in-process vision tests; never access the real desktop."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from farm_capture import CaptureStop, FarmCapture, capture_window, screenshot_rect
from farm_geometry import WindowFrame
from farm_vision import VisionStop, _roi, match_anchor


class CaptureVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))

    def test_retina_image_maps_only_to_window_local(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 900, 200, 100, 100)
        capture = FarmCapture(frame, np.zeros((200, 200), dtype=np.float32))
        self.assertEqual(capture.local_center(40, 80), (20, 40))
        self.assertEqual(frame.screen_point(*capture.local_center(40, 80)), (920, 240))

    def test_mismatched_screenshot_fails_closed(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 0, 0, 100, 100)
        with self.assertRaises(CaptureStop) as caught:
            FarmCapture(frame, np.zeros((200, 350), dtype=np.float32))
        self.assertEqual(caught.exception.code, "SCREENSHOT_FRAME_MISMATCH")
        with self.assertRaises(CaptureStop):
            FarmCapture(frame, np.zeros((175, 175), dtype=np.float32))

    def test_capture_rectangle_uses_logical_bounds(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", -600, 120, 603, 1111)
        self.assertEqual(screenshot_rect(frame), "-600,120,603,1111")
        with self.assertRaises(CaptureStop):
            screenshot_rect(WindowFrame("QQ小程序", "QQ经典农场", 0.5, 0, 603, 1111))

    def test_capture_command_is_read_only_and_checked(self):
        frame = WindowFrame("QQ小程序", "QQ经典农场", 120, 80, 603, 1111)
        def fake_run(argv, **kwargs):
            self.assertEqual(argv[:3], ["/usr/sbin/screencapture", "-x", "-R120,80,603,1111"])
            self.assertEqual(kwargs["timeout"], 15)
            Image.new("L", (1206, 2222)).save(argv[-1])
            return type("Process", (), {"returncode": 0, "stderr": ""})()
        with patch("farm_capture.subprocess.run", side_effect=fake_run) as run:
            cap = capture_window(frame, "qq", self.layout)
        self.assertEqual(cap.gray.shape, (2222, 1206))
        self.assertEqual(run.call_count, 1)

    def test_capture_refuses_unvalidated_window_before_call(self):
        frame = WindowFrame("QQ", "QQ经典农场", 0, 0, 603, 1111)
        with patch("farm_capture.subprocess.run") as run:
            with self.assertRaises(ValueError):
                capture_window(frame, "qq", self.layout)
            run.assert_not_called()

    def test_roi_bounds_are_strict(self):
        self.assertEqual(_roi([0.2, 0.3, 0.5, 0.4], 200, 100), (40, 30, 100, 40))
        for roi in ([0, 0, 1.1, 1], [-0.1, 0, 0.5, 0.5], [0, 0, 0, 0.5]):
            with self.assertRaises(VisionStop):
                _roi(roi, 200, 100)

    def test_retina_anchor_scales_template_before_matching(self):
        from scipy.ndimage import zoom
        rng = np.random.default_rng(77)
        frame = WindowFrame("QQ小程序", "QQ经典农场", 400, 300, 100, 100)
        image = rng.integers(0, 80, size=(200, 200)).astype(np.float32)
        template = rng.integers(120, 255, size=(12, 12)).astype(np.float32)
        retina_template = zoom(template, 2, order=1)
        image[90:114, 80:104] = retina_template
        capture = FarmCapture(frame, image)
        spec = {"roi_normalized": [0.2, 0.2, 0.6, 0.6], "threshold": 0.9}
        hit = match_anchor(capture, spec, [1.0], template_override=template)
        self.assertTrue(hit["matched"])
        self.assertAlmostEqual(hit["local_center"][0], 46.0)
        self.assertAlmostEqual(hit["local_center"][1], 51.0)

    def test_anchor_match_returns_local_not_pixel_or_screen(self):
        rng = np.random.default_rng(42)
        frame = WindowFrame("QQ小程序", "QQ经典农场", 700, 300, 200, 200)
        image = rng.integers(0, 256, size=(200, 200)).astype(np.float32)
        template = rng.integers(0, 256, size=(13, 12)).astype(np.float32)
        image[100:113, 80:92] = template
        capture = FarmCapture(frame, image)
        spec = {"roi_normalized": [0.25, 0.3, 0.5, 0.5], "threshold": 0.9}
        hit = match_anchor(capture, spec, [1.0], template_override=template)
        self.assertTrue(hit["matched"])
        self.assertAlmostEqual(hit["local_center"][0], 86.0)
        self.assertAlmostEqual(hit["local_center"][1], 106.5)
        miss = match_anchor(capture, {**spec, "threshold": 1.1}, [1.0],
                            template_override=template)
        self.assertFalse(miss["matched"])
        self.assertIsNone(miss["local_center"])


if __name__ == "__main__":
    unittest.main()
