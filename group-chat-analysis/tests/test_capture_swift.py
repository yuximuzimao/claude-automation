"""Compile-time and pure deterministic tests for the formal Swift capture adapter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from src.app.swift_sources import (
    CAPTURE_PURE_LIBRARY_SOURCES,
    CAPTURE_STEP_SOURCES,
    HISTORY_DATE_LIBRARY_SOURCES,
    OPEN_HISTORY_SOURCES,
    SELECT_HISTORY_DATE_SOURCES,
)


ROOT = Path(__file__).resolve().parents[1]


class SwiftCaptureTests(unittest.TestCase):
    def test_capture_step_typechecks(self) -> None:
        subprocess.run(
            [
                "swiftc",
                "-typecheck",
                *(str(ROOT / source) for source in CAPTURE_STEP_SOURCES),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_open_history_typechecks(self) -> None:
        subprocess.run(
            [
                "swiftc",
                "-typecheck",
                *(str(ROOT / source) for source in OPEN_HISTORY_SOURCES),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_select_history_date_typechecks(self) -> None:
        subprocess.run(
            [
                "swiftc",
                "-typecheck",
                *(str(ROOT / source) for source in SELECT_HISTORY_DATE_SOURCES),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_history_date_selector_pure_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            binary = Path(tempdir) / "history-date-selector-pure-tests"
            subprocess.run(
                [
                    "swiftc",
                    *(str(ROOT / source) for source in HISTORY_DATE_LIBRARY_SOURCES),
                    str(ROOT / "tests/swift/HistoryDateSelectorPureTests.swift"),
                    "-o",
                    str(binary),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [str(binary)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("HistoryDateSelectorPureTests OK", result.stdout)

    def test_pure_capture_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            binary = Path(tempdir) / "capture-pure-tests"
            subprocess.run(
                [
                    "swiftc",
                    *(str(ROOT / source) for source in CAPTURE_PURE_LIBRARY_SOURCES),
                    str(ROOT / "tests/swift/CapturePureTests.swift"),
                    "-o",
                    str(binary),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                [str(binary)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("CapturePureTests OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
