"""QQ V2 fixed-grid empty-field checker.

This is intentionally narrow. It assumes the verified QQ farm window size and
fixed 4x6 grid, then samples two tiny ROIs per plot:

- soil ROI: confirms the point still looks like QQ purple/gold land;
- occupancy ROI: distinguishes bright empty soil from the dark planted marker.

It does not identify crop species, infer partial transaction history, or align
the whole field. Any ambiguous cell is UNKNOWN. One positively occupied cell
is enough to prove the field is NOT_EMPTY.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np

from farm_capture import FarmCapture


Cell = tuple[int, int]
ALL_CELLS = tuple((u, v) for u in range(6) for v in range(4))


@dataclass(frozen=True)
class EmptyFieldCheck:
    status: str
    empty_cells: tuple[Cell, ...]
    occupied_cells: tuple[Cell, ...]
    unknown_cells: tuple[Cell, ...]
    reason: str


def _unknown(reason: str) -> EmptyFieldCheck:
    return EmptyFieldCheck(
        status="UNKNOWN",
        empty_cells=(),
        occupied_cells=(),
        unknown_cells=ALL_CELLS,
        reason=reason,
    )


def _patch(rgb: np.ndarray, x: int, y: int, radius: int) -> np.ndarray | None:
    if (x - radius < 0 or y - radius < 0
        or x + radius >= rgb.shape[1] or y + radius >= rgb.shape[0]):
        return None
    return rgb[y-radius:y+radius+1, x-radius:x+radius+1]


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    delta = a.astype(np.float64) - b.astype(np.float64)
    return sqrt(float(np.dot(delta, delta)))


def check_qq_empty_field(capture: FarmCapture, layout: dict) -> EmptyFieldCheck:
    """Return EMPTY, NOT_EMPTY, or UNKNOWN for the calibrated QQ 4x6 field."""
    rgb = getattr(capture, "rgb", None)
    if (rgb is None or rgb.dtype != np.uint8
        or not getattr(capture, "capture_id", None)
        or type(capture.captured_at_ns) is not int or capture.captured_at_ns <= 0):
        return _unknown("UNTRUSTED_CAPTURE")

    try:
        qq = layout["platforms"]["qq"]
        cfg = qq["empty_check"]
        expected_size = tuple(cfg["verified_window_size"])
        if expected_size != tuple(qq["baseline_window_size"]):
            return _unknown("CALIBRATION_SIZE_MISMATCH")
        width, height = expected_size
        if ((capture.frame.width, capture.frame.height) != expected_size
            or rgb.shape != (height, width, 3)):
            return _unknown("WINDOW_SIZE_CHANGED")

        origin = np.asarray(qq["origin"], dtype=np.float64)
        u_step = np.asarray(qq["u_step"], dtype=np.float64)
        v_step = np.asarray(qq["v_step"], dtype=np.float64)
        soil_offset = np.asarray(cfg["soil_offset"], dtype=np.float64)
        occupancy_offset = np.asarray(cfg["occupancy_offset"], dtype=np.float64)
        if any(x.shape != (2,) for x in (origin, u_step, v_step, soil_offset, occupancy_offset)):
            return _unknown("INVALID_CALIBRATION")

        radius = cfg["patch_radius"]
        prototypes = {
            name: np.asarray(value, dtype=np.float64)
            for name, value in cfg["soil_prototypes"].items()
        }
        if (type(radius) is not int or not 1 <= radius <= 8
            or set(prototypes) != {"purple", "gold"}
            or any(value.shape != (3,) for value in prototypes.values())):
            return _unknown("INVALID_CALIBRATION")

        empty_soil_max = float(cfg["empty_soil_max_distance"])
        occupied_soil_max = float(cfg["occupied_soil_max_distance"])
        occupied_lum_max = float(cfg["occupied_luminance_max"])
        empty_lum_min = float(cfg["empty_luminance_min"])
        if not (0 < empty_soil_max < occupied_soil_max
                and occupied_lum_max < empty_lum_min):
            return _unknown("INVALID_CALIBRATION")
    except (KeyError, TypeError, ValueError):
        return _unknown("INVALID_CALIBRATION")

    empty: list[Cell] = []
    occupied: list[Cell] = []
    unknown: list[Cell] = []

    for cell in ALL_CELLS:
        u, v = cell
        base = origin + u * u_step + v * v_step

        sx, sy = np.rint(base + soil_offset).astype(int)
        ox, oy = np.rint(base + occupancy_offset).astype(int)
        soil_patch = _patch(rgb, int(sx), int(sy), radius)
        occupancy_patch = _patch(rgb, int(ox), int(oy), radius)
        if soil_patch is None or occupancy_patch is None:
            unknown.append(cell)
            continue

        soil_rgb = np.median(soil_patch.reshape(-1, 3), axis=0)
        soil_distance = min(_distance(soil_rgb, value) for value in prototypes.values())
        occupancy_luminance = float(np.mean(occupancy_patch))

        if soil_distance <= occupied_soil_max and occupancy_luminance < occupied_lum_max:
            occupied.append(cell)
        elif soil_distance <= empty_soil_max and occupancy_luminance > empty_lum_min:
            empty.append(cell)
        else:
            unknown.append(cell)

    if occupied:
        return EmptyFieldCheck(
            status="NOT_EMPTY",
            empty_cells=tuple(empty),
            occupied_cells=tuple(occupied),
            unknown_cells=tuple(unknown),
            reason="OCCUPIED_CELL_DETECTED",
        )
    if unknown:
        return EmptyFieldCheck(
            status="UNKNOWN",
            empty_cells=tuple(empty),
            occupied_cells=(),
            unknown_cells=tuple(unknown),
            reason="CELL_UNCERTAIN",
        )
    if len(empty) != len(ALL_CELLS):
        return _unknown("INCOMPLETE_FIELD")
    return EmptyFieldCheck(
        status="EMPTY",
        empty_cells=tuple(empty),
        occupied_cells=(),
        unknown_cells=(),
        reason="ALL_24_EMPTY",
    )
