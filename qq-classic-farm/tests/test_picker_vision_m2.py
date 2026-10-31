"""QQ live picker ROI verification; synthetic negatives remain fail-closed."""
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
from farm_picker_vision import observe_picker, right_arrow_verified


class PickerVisionTests(unittest.TestCase):
    def capture(self, *, maple_slot: int | None = 1):
        rgb = np.zeros((1111, 603, 3), dtype=np.uint8)
        if maple_slot is not None:
            template = np.asarray(
                Image.open(ROOT / "assets/ui/picker/qq-red-maple.png").convert("RGB")
            )
            x = (95, 191, 287, 383, 480)[maple_slot - 1]
            rgb[754:817, x - 34:x + 34] = template
        frame = WindowFrame("QQ小程序", "QQ经典农场", 979, 101, 603, 1111)
        return FarmCapture(frame, np.zeros((1111, 603), dtype=np.float32), rgb=rgb)

    @patch("farm_picker_vision._read_text", side_effect=["4/7", "18"])
    def test_verified_page_icon_quantity(self, ocr):
        result = observe_picker(self.capture(), "qq", 1, "天山红枫种子", Path("/tmp/ocr"))
        self.assertEqual(result["page"], 4)
        self.assertEqual(result["total_pages"], 7)
        self.assertTrue(result["target_icon_verified"])
        self.assertEqual(result["target_quantity"], 18)
        self.assertEqual(ocr.call_count, 2)

    @patch("farm_picker_vision._read_text", return_value="4/7")
    def test_wrong_slot_never_claims_target(self, ocr):
        result = observe_picker(self.capture(), "qq", 3, "天山红枫种子", Path("/tmp/ocr"))
        self.assertFalse(result["target_icon_verified"])
        self.assertIsNone(result["target_quantity"])
        ocr.assert_called_once()

    @patch("farm_picker_vision._read_text", return_value="9/7")
    def test_invalid_page_is_unknown(self, ocr):
        result = observe_picker(self.capture(), "qq", 1, "天山红枫种子", Path("/tmp/ocr"))
        self.assertIsNone(result["page"])
        self.assertIsNone(result["target_icon_verified"])

    def test_missing_ocr_and_wechat_fail_closed(self):
        self.assertIsNone(observe_picker(self.capture(), "qq", 1,
                                        "天山红枫种子", None)["page"])
        self.assertIsNone(observe_picker(self.capture(), "wechat", 1,
                                        "天山红枫种子", None)["page"])

    def test_arrow_is_independent_of_page_counter(self):
        capture = self.capture(maple_slot=None)
        self.assertFalse(right_arrow_verified(capture))
        capture.rgb[756:793, 555:585] = [250, 220, 100]
        self.assertTrue(right_arrow_verified(capture))


if __name__ == "__main__":
    unittest.main()
