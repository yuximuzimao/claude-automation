"""Compile-time and pure deterministic tests for the formal Swift capture adapter."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SOURCES = [
    ROOT / "src/capture/CaptureModels.swift",
    ROOT / "src/capture/VisualFingerprint.swift",
    ROOT / "src/capture/ContentRegion.swift",
    ROOT / "src/capture/WindowPreparation.swift",
    ROOT / "src/capture/ChangeDetector.swift",
    ROOT / "src/capture/QQHistoryCapture.swift",
    ROOT / "src/capture/RawPageWriter.swift",
    ROOT / "src/capture/ConversationSwitcher.swift",
]


class SwiftCaptureTests(unittest.TestCase):
    def test_capture_step_typechecks(self) -> None:
        subprocess.run(
            [
                "swiftc",
                "-typecheck",
                *map(str, CAPTURE_SOURCES),
                str(ROOT / "src/app/capture-step.swift"),
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
                str(ROOT / "src/capture/CaptureModels.swift"),
                str(ROOT / "src/capture/ConversationSwitcher.swift"),
                str(ROOT / "src/app/open-history.swift"),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_pure_capture_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            binary = Path(tempdir) / "capture-pure-tests"
            subprocess.run(
                [
                    "swiftc",
                    str(ROOT / "src/capture/CaptureModels.swift"),
                    str(ROOT / "src/capture/VisualFingerprint.swift"),
                    str(ROOT / "src/capture/ContentRegion.swift"),
                    str(ROOT / "src/capture/ChangeDetector.swift"),
                    str(ROOT / "src/capture/QQHistoryCapture.swift"),
                    str(ROOT / "src/capture/RawPageWriter.swift"),
                    str(ROOT / "src/capture/ConversationSwitcher.swift"),
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
