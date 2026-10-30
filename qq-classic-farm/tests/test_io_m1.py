"""Read-only window registry composition; all process outputs mocked."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from farm_io import IOStop, find_farm_window
from farm_runner import RunnerStop


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))

    def response(self, windows, platform="qq"):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"platform": platform, "windows": windows}),
            "stderr": "",
        })()

    def qq_window(self, **changes):
        return {
            **{"window_id": 12, "pid": 345, "owner": "QQ小程序",
               "title": "QQ经典农场", "x": 100, "y": 200,
               "width": 603, "height": 1111},
            **changes,
        }

    def test_single_exact_window(self):
        with patch("farm_io.subprocess.run", return_value=self.response([self.qq_window()])) as call:
            found = find_farm_window("qq", self.layout, Path("/tmp/farm_registry"))
        self.assertEqual(found.window_id, 12)
        self.assertEqual(found.pid, 345)
        self.assertEqual(found.frame.screen_point(20, 30), (120, 230))
        self.assertEqual(call.call_args.args[0], ["/tmp/farm_registry", "--platform", "qq"])

    def test_no_window_or_duplicate_window_stops(self):
        for items in ([], [self.qq_window(), self.qq_window(window_id=13)]):
            with patch("farm_io.subprocess.run", return_value=self.response(items)):
                with self.assertRaises(IOStop) as caught:
                    find_farm_window("qq", self.layout, Path("/tmp/farm_registry"))
            self.assertEqual(caught.exception.code, "WINDOW_NOT_FOUND")

    def test_wrong_owner_and_size_fail_closed(self):
        for change, code in (({"owner": "QQ"}, "WRONG_FRONTMOST_APP"),
                             ({"width": 900}, "WINDOW_SIZE_CHANGED")):
            with patch("farm_io.subprocess.run", return_value=self.response([self.qq_window(**change)])):
                with self.assertRaises(ValueError) as caught:
                    find_farm_window("qq", self.layout, Path("/tmp/farm_registry"))
            self.assertEqual(caught.exception.code, code)

    def test_invalid_id_or_wrong_platform_fails(self):
        with patch("farm_io.subprocess.run", return_value=self.response([self.qq_window(pid=0)])):
            with self.assertRaises(IOStop) as caught:
                find_farm_window("qq", self.layout, Path("/tmp/farm_registry"))
        self.assertEqual(caught.exception.code, "WINDOW_REGISTRY_FAILED")
        with patch("farm_io.subprocess.run", return_value=self.response([self.qq_window()], "wechat")):
            with self.assertRaises(IOStop):
                find_farm_window("qq", self.layout, Path("/tmp/farm_registry"))


if __name__ == "__main__":
    unittest.main()
