"""Read-only macOS farm-window capture; screenshot pixels never escape as click coordinates.

Capture uses the *current* validated window bounds. It does not activate apps,
send input, or fall back to an unbounded/full-screen screenshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from time import monotonic_ns
from uuid import uuid4

import numpy as np
from PIL import Image

from farm_geometry import WindowFrame, GeometryStop, validate_farm_window


class CaptureStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FarmCapture:
    frame: WindowFrame
    gray: np.ndarray
    # Only capture_window() supplies provenance; synthetic/test captures default to untrusted.
    capture_id: str | None = None
    captured_at_ns: int | None = None

    def __post_init__(self):
        if self.gray.ndim != 2 or self.gray.size == 0:
            raise CaptureStop("INVALID_SCREENSHOT", "Expected a nonempty grayscale image")
        h, w = self.gray.shape
        # Reject a clipped crop, full-screen image, or anisotropic scaling.
        sx, sy = w / self.frame.width, h / self.frame.height
        if not 0.95 <= sx <= 4.0 or abs(sx - sy) > 0.04 * max(sx, sy):
            raise CaptureStop("SCREENSHOT_FRAME_MISMATCH", "Capture does not match window bounds")
        if min(abs(sx - n) for n in (1, 2, 3, 4)) > 0.04:
            raise CaptureStop("SCREENSHOT_FRAME_MISMATCH", "Unexpected screenshot pixel scale")

    def local_center(self, pixel_x: float, pixel_y: float) -> tuple[float, float]:
        h, w = self.gray.shape
        return self.frame.pixel_to_local(pixel_x, pixel_y, w, h)


def screenshot_rect(frame: WindowFrame) -> str:
    """screencapture -R expects global logical points, not Retina pixels."""
    values = (frame.x, frame.y, frame.width, frame.height)
    if any(abs(v - round(v)) > 0.01 for v in values):
        raise CaptureStop("INVALID_WINDOW", "Nonintegral bounds require recalibration")
    return ",".join(str(round(v)) for v in values)


def capture_window(
    frame: WindowFrame, platform: str, layout: dict,
    *, screencapture: str = "/usr/sbin/screencapture",
) -> FarmCapture:
    """One process per screenshot, not per click. Always validate before capture."""
    validate_farm_window(frame, platform, layout)
    rect = screenshot_rect(frame)
    with tempfile.TemporaryDirectory(prefix="farm-capture-") as folder:
        output = Path(folder) / "window.png"
        try:
            proc = subprocess.run(
                [screencapture, "-x", "-R" + rect, str(output)],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise CaptureStop("SCREENSHOT_FAILED", str(exc)) from exc
        if proc.returncode != 0 or not output.is_file():
            raise CaptureStop("SCREENSHOT_FAILED", proc.stderr.strip() or "No screenshot")
        try:
            with Image.open(output) as im:
                gray = np.asarray(im.convert("L"), dtype=np.float32)
        except (OSError, ValueError) as exc:
            raise CaptureStop("INVALID_SCREENSHOT", str(exc)) from exc
    return FarmCapture(frame, gray, capture_id=uuid4().hex, captured_at_ns=monotonic_ns())
