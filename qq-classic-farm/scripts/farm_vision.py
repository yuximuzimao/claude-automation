"""In-process, read-only M1 farm vision.

All coordinates returned by this module are WINDOW-LOCAL LOGICAL points.
Raw screenshot pixel positions are private to the vision implementation.
No external Python process and no CGEvent are used here.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from anchor_locator import load_gray, normalized_cross_correlation, scaled
from farm_capture import FarmCapture

ROOT = Path(__file__).resolve().parents[1]


class VisionStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@lru_cache(maxsize=24)
def _template(path: str) -> np.ndarray:
    return load_gray(path)


def _roi(spec: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    if (len(spec) != 4 or any(not isinstance(v, (float, int)) for v in spec)
        or any(not np.isfinite(v) for v in spec)):
        raise VisionStop("INVALID_ROI", "Malformed normalized ROI")
    x, y, w, h = spec
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.00001 or y + h > 1.00001:
        raise VisionStop("INVALID_ROI", "ROI must lie inside capture")
    x0, y0 = round(x * width), round(y * height)
    x1, y1 = round((x + w) * width), round((y + h) * height)
    if x1 <= x0 or y1 <= y0:
        raise VisionStop("INVALID_ROI", "ROI collapsed")
    return x0, y0, x1 - x0, y1 - y0


def match_anchor(
    capture: FarmCapture, spec: dict, scales: list[float],
    *, template_override: np.ndarray | None = None,
) -> dict:
    """Best local match only; below-threshold matches are NEVER actionable."""
    height, width = capture.gray.shape
    x, y, w, h = _roi(spec["roi_normalized"], width, height)
    crop = capture.gray[y:y+h, x:x+w]
    template = (template_override if template_override is not None
                else _template(str(ROOT / spec["template"])))
    best = None
    # Templates are calibrated at baseline logical (1x) resolution; Retina crops
    # can be 2x, so match at the capture pixel density rather than guessing.
    pixel_scale = width / capture.frame.width
    for factor in scales:
        if not 0.5 <= factor <= 2:
            raise VisionStop("INVALID_SCALE", "Unsupported template scale")
        candidate = scaled(template, factor * pixel_scale)
        scores = normalized_cross_correlation(crop, candidate)
        if scores is None:
            continue
        iy, ix = np.unravel_index(np.argmax(scores), scores.shape)
        score = float(scores[iy, ix])
        if best is None or score > best["score"]:
            best = {
                "score": score, "scale": factor,
                "pixel_center": (x + ix + candidate.shape[1] / 2,
                                 y + iy + candidate.shape[0] / 2),
            }
    if best is None:
        return {"matched": False, "score": -1.0, "local_center": None}
    threshold = spec.get("threshold", 0.82)
    if best["score"] < threshold:
        return {"matched": False, "score": best["score"], "local_center": None}
    local = capture.local_center(*best["pixel_center"])
    return {"matched": True, "score": best["score"], "local_center": list(local)}
