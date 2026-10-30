"""Read-only M1 per-plot comparison against a separately labeled clean-field image.

This is an *evidence collector*, not a classifier or click permission.
The reference must be a known clean capture of the same platform/canvas and
must independently align on exposed purple soil. An occupied current field may
use a read-only scene-background shift estimate; this is NOT independent field
calibration. No crop states are inferred until real negative/positive replay
calibrates false positives.
"""
from __future__ import annotations

import numpy as np

from farm_capture import FarmCapture
from farm_field import FieldStop, probe_field_translation
from farm_geometry import GeometryStop, plot_local_point, validate_farm_window
from farm_scene import SceneStop, probe_scene_translation


class CleanFieldStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def compare_clean_reference(
    capture: FarmCapture, reference: FarmCapture, platform: str, layout: dict,
    *, half_width: int = 13, half_height: int = 6,
) -> dict:
    """Return 24 plot-local color differences, never confirmed empty booleans.

    The center patch is deliberately small enough not to overlap a neighboring
    diamond cell. It is NOT proof of an empty plot: small crops can leave the
    center similar to soil, and animations can alter an otherwise empty tile.
    """
    try:
        validate_farm_window(capture.frame, platform, layout)
        validate_farm_window(reference.frame, platform, layout)
        if capture.rgb is None or reference.rgb is None:
            raise CleanFieldStop("FIELD_COLOR_REQUIRED", "Both RGB captures are required")
        if capture.rgb.shape != reference.rgb.shape:
            raise CleanFieldStop("FIELD_REFERENCE_MISMATCH", "Reference and capture pixel dimensions differ")
        if (not isinstance(half_width, int) or isinstance(half_width, bool)
            or not isinstance(half_height, int) or isinstance(half_height, bool)
            or not 3 <= half_width <= 15 or not 3 <= half_height <= 8):
            raise CleanFieldStop("INVALID_FIELD_PATCH", "Unsafe per-plot patch size")
        # The reference must independently align on exposed purple soil. An
        # occupied current field may use only a read-only, three-landmark scene
        # estimate; neither route is permitted to authorize clicks.
        reference_alignment = probe_field_translation(reference, platform, layout)
        scene_alignment = None
        alignment_method = "exposed_purple_soil"
        try:
            current_alignment = probe_field_translation(capture, platform, layout)
        except FieldStop as field_exc:
            # An occupied field can hide every purple soil tile. Estimate only
            # a diagnostic scene-relative offset from independent background
            # landmarks, never an actionable plot calibration.
            try:
                scene_alignment = probe_scene_translation(capture, reference, platform, layout)
            except SceneStop as exc:
                raise CleanFieldStop(field_exc.code, f"{field_exc}; scene fallback: {exc}") from exc
            sx_local, sy_local = scene_alignment["scene_shift_local"]
            rx_local, ry_local = reference_alignment["offset_local"]
            current_alignment = {
                "status": "diagnostic_only",
                "offset_local": [round(rx_local + sx_local, 2),
                                 round(ry_local + sy_local, 2)],
                "can_authorize_clicks": False,
            }
            alignment_method = "background_reference_inferred"
        if (current_alignment["status"] != "diagnostic_only"
            or reference_alignment["status"] != "diagnostic_only"):
            raise CleanFieldStop("FIELD_ALIGNMENT_UNAVAILABLE", "Untrusted field alignment")
    except (FieldStop, GeometryStop) as exc:
        raise CleanFieldStop(exc.code, str(exc)) from exc
    except CleanFieldStop:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise CleanFieldStop("INVALID_FIELD_GEOMETRY", str(exc)) from exc

    height, width = capture.rgb.shape[:2]
    sx = width / capture.frame.width
    sy = height / capture.frame.height
    rsx = width / reference.frame.width
    rsy = height / reference.frame.height
    if abs(sx - rsx) > 0.02 or abs(sy - rsy) > 0.02:
        raise CleanFieldStop("FIELD_REFERENCE_MISMATCH", "Reference and live logical scales differ")

    def patch(img: np.ndarray, x: float, y: float) -> np.ndarray:
        px, py = round(x * sx), round(y * sy)
        rx, ry = round(half_width * sx), round(half_height * sy)
        if px - rx < 0 or py - ry < 0 or px + rx >= width or py + ry >= height:
            raise CleanFieldStop("FIELD_PATCH_OUTSIDE_IMAGE", "Plot patch exceeds screenshot")
        return img[py-ry:py+ry+1, px-rx:px+rx+1].astype(np.int16)

    patches = []
    for u in range(6):
        for v in range(4):
            x, y = plot_local_point(platform, u, v, capture.frame, layout)
            rx, ry = plot_local_point(platform, u, v, reference.frame, layout)
            dx, dy = current_alignment["offset_local"]
            rdx, rdy = reference_alignment["offset_local"]
            a = patch(capture.rgb, x + dx, y + dy)
            b = patch(reference.rgb, rx + rdx, ry + rdy)
            if a.shape != b.shape:
                raise CleanFieldStop("FIELD_REFERENCE_MISMATCH", "Plot patch dimensions differ")
            patches.append(([u, v], a, b))

    # Robust *diagnostic* additive color correction: estimate a per-channel
    # offset from the median difference within each cell, then take the median
    # across 24 cells. One changed/occupied cell cannot determine the offset.
    # This does NOT compensate for spatially varying animation, color clipping,
    # or prove that any individual cell is empty.
    per_cell_offsets = np.array([np.median(a - b, axis=(0, 1))
                                 for _, a, b in patches], dtype=np.float64)
    global_offset = np.median(per_cell_offsets, axis=0)
    result = []
    for cell, a, b in patches:
        delta = np.abs(a - b)
        residual = np.abs(a.astype(np.float64) - b - global_offset)
        result.append({
            "cell": cell,
            "mean_abs_rgb": round(float(delta.mean()), 2),
            "fraction_channels_delta_gt_40": round(float(np.mean(delta > 40)), 4),
            "mean_abs_rgb_after_global_offset": round(float(residual.mean()), 2),
            "median_abs_rgb_after_global_offset": round(float(np.median(residual)), 2),
            "p90_abs_rgb_after_global_offset": round(float(np.percentile(residual, 90)), 2),
            "fraction_residual_channels_gt_40": round(float(np.mean(residual > 40)), 4),
        })
    return {
        "status": "diagnostic_only",
        "platform": platform,
        "cells": result,
        "cell_count": len(result),
        "color_normalization": "per_channel_median_additive_diagnostic_only",
        "global_rgb_offset": [round(float(x), 2) for x in global_offset],
        "reference_alignment": reference_alignment["offset_local"],
        "capture_alignment": current_alignment["offset_local"],
        "capture_alignment_method": alignment_method,
        "scene_alignment": scene_alignment,
        "empty_cells": None,
        "can_authorize_clicks": False,
        "requires_labeled_real_clean_and_occupied_replay": True,
    }
