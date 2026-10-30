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
from pickable_locator import locate_pickables

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


def _special_centers(capture: FarmCapture, platform: str, layout: dict) -> dict[str, tuple[float, float]]:
    """Known, nonoverlapping 2x2 plot centers in WINDOW-LOCAL logical units.

    These are geometric *candidates*, not proof that a special crop currently
    occupies the area. Live occupancy and the star offset still need calibration.
    """
    from farm_geometry import GeometryStop, plot_local_point, validate_farm_window

    try:
        validate_farm_window(capture.frame, platform, layout)
        placements = layout["platforms"][platform]["safe_special_2x2"]
        if not placements:
            raise ValueError("No calibrated special placements")
        centers: dict[str, tuple[float, float]] = {}
        used: set[tuple[int, int]] = set()
        for placement in placements:
            name = placement["id"]
            cells = [tuple(cell) for cell in placement["cells"]]
            if (not isinstance(name, str) or not name or name in centers
                or len(cells) != 4 or len(set(cells)) != 4
                or any(cell in used for cell in cells)):
                raise ValueError("Invalid or overlapping 2x2 placement")
            us, vs = {u for u, _ in cells}, {v for _, v in cells}
            if len(us) != 2 or len(vs) != 2 or max(us) - min(us) != 1 or max(vs) - min(vs) != 1:
                raise ValueError("Placement cells do not form a 2x2")
            points = [plot_local_point(platform, u, v, capture.frame, layout) for u, v in cells]
            centers[name] = (
                sum(x for x, _ in points) / 4,
                sum(y for _, y in points) / 4,
            )
            used.update(cells)
        return centers
    except (KeyError, TypeError, ValueError, GeometryStop) as exc:
        raise VisionStop("INVALID_SPECIAL_GEOMETRY", str(exc)) from exc


def _filter_special_pickables(
    capture: FarmCapture, platform: str, layout: dict, detected: dict,
    *, radius_logical: float = 14.0,
) -> tuple[list[dict], int]:
    """Fail closed on ambiguous candidates; never click a raw template match.

    At baseline the nearest *individual* plot center is only ~21 logical
    pixels from a diamond-shaped 2x2 centroid (not ~32). Keep this provisional
    14px gate narrower to avoid accepting a single-plot-center marker. A star
    offset may still collide with this region: only live occupancy calibration
    can make a candidate actionable; this probe NEVER authorizes clicks.
    """
    if not np.isfinite(radius_logical) or not 0 < radius_logical <= 14:
        raise VisionStop("INVALID_SPECIAL_GEOMETRY", "Invalid pickable association radius")
    from farm_geometry import GeometryStop

    centers = _special_centers(capture, platform, layout)
    if not isinstance(detected, dict) or not isinstance(detected.get("items"), list):
        raise VisionStop("INVALID_PICKABLE_CANDIDATE", "Missing marker candidate list")
    accepted: list[dict] = []
    used: set[str] = set()
    ignored = 0
    for item in detected["items"]:
        try:
            if (not isinstance(item, dict)
                or not 0 <= float(item["score"]) <= 1):
                raise ValueError("Invalid marker confidence")
            point = capture.local_center(item["center_x"], item["center_y"])
            matches = [
                (name, (point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2)
                for name, center in centers.items()
                if (point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2 <= radius_logical ** 2
            ]
        except (KeyError, TypeError, ValueError, GeometryStop) as exc:
            raise VisionStop("INVALID_PICKABLE_CANDIDATE", str(exc)) from exc
        if not matches:
            ignored += 1
            continue
        if len(matches) != 1 or matches[0][0] in used:
            raise VisionStop("AMBIGUOUS_PICKABLES", "Multiple stars or placements overlap a special crop")
        name = matches[0][0]
        used.add(name)
        accepted.append({"placement": name, "local_center": list(point), "score": item["score"]})
    if len(accepted) > len(centers):
        raise VisionStop("AMBIGUOUS_PICKABLES", "More special markers than calibrated placements")
    return accepted, ignored


def probe_harvest(capture: FarmCapture, anchors_cfg: dict, platform: str, layout: dict) -> dict:
    """Read-only probe; geometry filtering is NOT live special-crop verification."""
    cfg = anchors_cfg["anchors"]["onekey_harvest"]
    hand = match_anchor(capture, cfg, anchors_cfg["matching"]["default_scales"])
    pixel_scale = capture.gray.shape[1] / capture.frame.width
    detected = locate_pickables(
        capture.gray,
        scales=[s * pixel_scale for s in (0.9, 0.95, 1.0, 1.05, 1.1)],
        dedupe_radius=30.0 * pixel_scale,
    )
    pickables, ignored = _filter_special_pickables(capture, platform, layout, detected)
    return {
        "hand": hand,
        "pickables": pickables,
        "ignored_outside_special_centers": ignored,
        "can_start_harvest": False,
        "requires_live_star_offset_and_occupancy_calibration": True,
        "needs_overlay_and_field_postcondition": True,
    }
