"""Read-only M1 farm-grid translation probe using exposed purple soil tiles.

The historical grid formula can shift within a correctly sized farm window.
This diagnostic estimates translation ONLY when every expected purple soil
tile is visible and uniquely associated. It is not an action authorization:
mature crops obscure tiles, and live star/occupancy calibration is pending.
"""
from __future__ import annotations

from math import hypot
import numpy as np
from scipy.ndimage import find_objects, label

from farm_capture import FarmCapture
from farm_geometry import GeometryStop, plot_local_point, validate_farm_window


class FieldStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _expected_purple(platform: str, layout: dict) -> set[tuple[int, int]]:
    cfg = layout["platforms"][platform]
    if "land_grades" in cfg:
        return {tuple(p) for p in cfg["land_grades"]["purple_cells"]}
    return {
        tuple(p)
        for placement in cfg["safe_special_2x2"]
        if placement["grade"] == "purple"
        for p in placement["cells"]
    }


def probe_field_translation(capture: FarmCapture, platform: str, layout: dict) -> dict:
    """Estimate a window-local grid offset; never return clickable plot points."""
    if capture.rgb is None:
        raise FieldStop("FIELD_COLOR_REQUIRED", "RGB capture required for soil alignment")
    try:
        validate_farm_window(capture.frame, platform, layout)
        cells = sorted(_expected_purple(platform, layout))
        if not 4 <= len(cells) <= 12:
            raise ValueError("Expected purple plot set is missing or implausible")
        if any(len(p) != 2 or not all(type(v) is int for v in p) for p in cells):
            raise ValueError("Invalid purple plot coordinates")
        sx = capture.gray.shape[1] / capture.frame.width
        sy = capture.gray.shape[0] / capture.frame.height
        expected = [
            (x * sx, y * sy)
            for x, y in (plot_local_point(platform, u, v, capture.frame, layout)
                         for u, v in cells)
        ]
    except (KeyError, TypeError, ValueError, GeometryStop) as exc:
        raise FieldStop("INVALID_FIELD_GEOMETRY", str(exc)) from exc

    # Purple soil has blue > red > green. Restrict segmentation to the field
    # and allow only bounded displacement from the saved baseline.
    rgb = capture.rgb.astype(np.int16)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mask = (b > r + 8) & (r > g + 15) & (r > 110) & (b > 135)
    xs, ys = zip(*expected)
    x0 = max(0, int(min(xs) - 110 * sx))
    x1 = min(mask.shape[1], int(max(xs) + 110 * sx))
    y0 = max(0, int(min(ys) - 75 * sy))
    y1 = min(mask.shape[0], int(max(ys) + 75 * sy))
    region = mask[y0:y1, x0:x1]
    labels, count = label(region)
    found = []
    for index, slices in enumerate(find_objects(labels), start=1):
        if slices is None:
            continue
        ry, rx = slices
        width, height = rx.stop - rx.start, ry.stop - ry.start
        area = int(np.count_nonzero(labels[slices] == index))
        if (not 35 * sx <= width <= 90 * sx
            or not 19 * sy <= height <= 55 * sy
            or not 400 * sx * sy <= area <= 3300 * sx * sy):
            continue
        yy, xx = np.nonzero(labels[slices] == index)
        found.append((float(x0 + rx.start + xx.mean()),
                      float(y0 + ry.start + yy.mean())))

    tolerance = 3.5 * max(sx, sy)
    solutions = []
    for px, py in expected:
        for ox, oy in found:
            dx, dy = ox - px, oy - py
            if abs(dx) > 100 * sx or abs(dy) > 65 * sy:
                continue
            matched = []
            used = set()
            for ex, ey in expected:
                options = sorted(
                    (hypot((ex + dx) - fx, (ey + dy) - fy), i)
                    for i, (fx, fy) in enumerate(found)
                    if i not in used
                )
                if not options or options[0][0] > tolerance:
                    break
                distance, i = options[0]
                used.add(i)
                matched.append((found[i][0] - ex, found[i][1] - ey, distance))
            if len(matched) != len(expected):
                continue
            shift_x = float(np.median([m[0] for m in matched]))
            shift_y = float(np.median([m[1] for m in matched]))
            rms = float(np.sqrt(np.mean([m[2] ** 2 for m in matched])))
            if rms <= 2.5 * max(sx, sy):
                solutions.append((shift_x, shift_y, rms))
    if not solutions:
        raise FieldStop("FIELD_ALIGNMENT_UNAVAILABLE",
                        "Cannot uniquely align all exposed purple soil tiles")
    solutions.sort(key=lambda s: s[2])
    best = solutions[0]
    if any(hypot(s[0] - best[0], s[1] - best[1]) > 5 * max(sx, sy)
           for s in solutions[1:]):
        raise FieldStop("FIELD_ALIGNMENT_AMBIGUOUS", "Multiple full-grid translations fit")
    return {
        "status": "diagnostic_only",
        "offset_local": [round(best[0] / sx, 2), round(best[1] / sy, 2)],
        "matched_purple_cells": len(expected),
        "rms_logical": round(best[2] / max(sx, sy), 2),
        "can_authorize_clicks": False,
    }
