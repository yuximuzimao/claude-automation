"""Read-only M1 scene registration against a labeled clean reference.

Match three separated *background* landmarks outside the crop grid. This can
estimate a candidate field translation when crops obscure all purple soil.
It is only diagnostic: matching a scene does NOT prove plot occupancy or
authorize CGEvent actions.
"""
from __future__ import annotations

from math import hypot
import numpy as np

from anchor_locator import normalized_cross_correlation
from farm_capture import FarmCapture
from farm_geometry import GeometryStop, validate_farm_window


class SceneStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# Baseline logical centers on stable roads/landscape, away from field and HUD.
# These are provisional replay landmarks, NOT click coordinates.
BACKGROUND_ANCHORS = {
    "qq": ((400, 440), (470, 850), (100, 650)),
    "wechat": ((400, 450), (480, 870), (130, 800)),
}


def probe_scene_translation(
    capture: FarmCapture, reference: FarmCapture, platform: str, layout: dict,
) -> dict:
    """Estimate current-vs-reference scene shift from 3 agreeing static ROIs.

    Both images must have the same pixel dimensions and nearly identical
    logical canvas dimensions. Low confidence or inconsistent matches STOP.
    """
    try:
        validate_farm_window(capture.frame, platform, layout)
        validate_farm_window(reference.frame, platform, layout)
        if capture.gray.shape != reference.gray.shape:
            raise SceneStop("SCENE_REFERENCE_MISMATCH", "Screenshot dimensions differ")
        if (abs(capture.frame.width - reference.frame.width) > 1
            or abs(capture.frame.height - reference.frame.height) > 1):
            raise SceneStop("SCENE_REFERENCE_MISMATCH", "Logical canvas dimensions differ")
        baseline_w, baseline_h = layout["platforms"][platform]["baseline_window_size"]
        anchors = BACKGROUND_ANCHORS[platform]
    except (KeyError, TypeError, GeometryStop) as exc:
        raise SceneStop("INVALID_SCENE_GEOMETRY", str(exc)) from exc

    height, width = reference.gray.shape
    px_per_logical = width / reference.frame.width
    py_per_logical = height / reference.frame.height
    half_w = round(32 * px_per_logical)
    half_h = round(32 * py_per_logical)
    search_x = round(95 * px_per_logical)
    search_y = round(70 * py_per_logical)
    shifts = []
    scores = []
    for ax, ay in anchors:
        cx = round(ax / baseline_w * width)
        cy = round(ay / baseline_h * height)
        left, top = cx - half_w, cy - half_h
        right, bottom = cx + half_w, cy + half_h
        x0, y0 = max(0, left - search_x), max(0, top - search_y)
        x1, y1 = min(width, right + search_x), min(height, bottom + search_y)
        if min(left, top) < 0 or right >= width or bottom >= height:
            raise SceneStop("INVALID_SCENE_GEOMETRY", "Background anchor outside canvas")
        template = reference.gray[top:bottom, left:right]
        region = capture.gray[y0:y1, x0:x1]
        matched = normalized_cross_correlation(region, template)
        if matched is None:
            raise SceneStop("SCENE_ALIGNMENT_UNAVAILABLE", "Background template has no texture")
        iy, ix = np.unravel_index(np.argmax(matched), matched.shape)
        score = float(matched[iy, ix])
        if not np.isfinite(score) or score < 0.94:
            raise SceneStop("SCENE_ALIGNMENT_UNAVAILABLE", "Background landmark confidence too low")
        shifts.append(((x0 + ix - left) / px_per_logical,
                       (y0 + iy - top) / py_per_logical))
        scores.append(score)

    shift_x = float(np.median([x for x, _ in shifts]))
    shift_y = float(np.median([y for _, y in shifts]))
    if any(hypot(x - shift_x, y - shift_y) > 2.5 for x, y in shifts):
        raise SceneStop("SCENE_ALIGNMENT_AMBIGUOUS", "Background landmarks disagree")
    return {
        "status": "diagnostic_only",
        "method": "three_background_landmarks",
        "scene_shift_local": [round(shift_x, 2), round(shift_y, 2)],
        "minimum_anchor_score": round(min(scores), 4),
        "anchor_count": len(scores),
        "can_authorize_clicks": False,
    }
