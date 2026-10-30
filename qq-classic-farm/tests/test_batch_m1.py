"""Compiled CGEvent batch helper contract tests. Only validation mode is invoked."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BatchHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("swiftc"):
            raise unittest.SkipTest("swiftc unavailable")
        cls.folder = tempfile.TemporaryDirectory(prefix="farm-helper-test-")
        cls.binary = Path(cls.folder.name) / "farm_click_batch"
        result = subprocess.run(
            ["swiftc", str(ROOT / "scripts/farm_click_batch.swift"), "-o", str(cls.binary)],
            capture_output=True, text=True, timeout=40,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "folder"):
            cls.folder.cleanup()

    def invoke(self, action):
        payload = {
            "window_id": 123, "pid": 456, "owner": "QQ小程序", "title": "QQ经典农场",
            "frame": {"x": 500, "y": 200, "width": 603, "height": 1111},
            "actions": [action],
        }
        result = subprocess.run(
            [str(self.binary)], input=json.dumps(payload), text=True,
            capture_output=True, timeout=10,
        )
        return result.returncode, json.loads(result.stdout)

    def test_valid_batch_does_not_click(self):
        code, result = self.invoke({"x": 200, "y": 300, "delay_ms": 100})
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "validated_no_click")
        self.assertEqual(result["click_count"], 0)

    def test_outside_window_refused_before_click(self):
        code, result = self.invoke({"x": 603, "y": 300, "delay_ms": 0})
        self.assertEqual(code, 2)
        self.assertEqual(result["code"], "CLICK_OUTSIDE_WINDOW")

    def test_unbounded_delay_refused(self):
        code, result = self.invoke({"x": 200, "y": 300, "delay_ms": 5000})
        self.assertEqual(code, 2)
        self.assertEqual(result["code"], "CLICK_OUTSIDE_WINDOW")


if __name__ == "__main__":
    unittest.main()
