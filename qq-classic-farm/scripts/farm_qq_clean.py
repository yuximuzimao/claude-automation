"""V2 fixed-grid empty-field checks for QQ and WeChat.

Both paths are intentionally narrow: fixed 4x6 geometry plus a few tiny
platform-specific ROIs. They do not identify crop species or reconstruct a
general scene. Any ambiguous cell is UNKNOWN; one positively occupied cell is
enough to prove NOT_EMPTY.
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


def observe_qq_preview_cells(
    capture: FarmCapture, layout: dict
) -> frozenset[Cell] | None:
    """Return the exact 2x2 green preview, empty set, or None if ambiguous.

    The game paints preview tiles green. V2 samples the same tiny soil ROI used
    by the empty checker and only asks whether G exceeds both R/B by a
    calibrated margin. It never identifies a crop species.
    """
    rgb = getattr(capture, "rgb", None)
    if (rgb is None or rgb.dtype != np.uint8
        or not getattr(capture, "capture_id", None)
        or type(capture.captured_at_ns) is not int or capture.captured_at_ns <= 0):
        return None
    try:
        qq = layout["platforms"]["qq"]
        empty_cfg = qq["empty_check"]
        plant_cfg = qq["planting"]
        width, height = empty_cfg["verified_window_size"]
        if ((capture.frame.width, capture.frame.height) != (width, height)
            or rgb.shape != (height, width, 3)):
            return None
        origin = np.asarray(qq["origin"], dtype=np.float64)
        u_step = np.asarray(qq["u_step"], dtype=np.float64)
        v_step = np.asarray(qq["v_step"], dtype=np.float64)
        preview_offset = np.asarray(plant_cfg["preview_offset"], dtype=np.float64)
        radius = int(plant_cfg["preview_patch_radius"])
        margin_min = float(plant_cfg["preview_green_margin_min"])
        if (preview_offset.shape != (2,) or not 1 <= radius <= 8 or margin_min <= 0):
            return None
    except (KeyError, TypeError, ValueError):
        return None

    preview: set[Cell] = set()
    for cell in ALL_CELLS:
        u, v = cell
        base = origin + u * u_step + v * v_step
        x, y = np.rint(base + preview_offset).astype(int)
        patch = _patch(rgb, int(x), int(y), radius)
        if patch is None:
            return None
        med = np.median(patch.reshape(-1, 3), axis=0)
        if float(med[1] - max(med[0], med[2])) >= margin_min:
            preview.add(cell)

    if not preview:
        return frozenset()
    if len(preview) != 4:
        return None
    us = {u for u, _ in preview}
    vs = {v for _, v in preview}
    if (len(us) != 2 or len(vs) != 2
        or max(us) - min(us) != 1 or max(vs) - min(vs) != 1):
        return None
    expected = {(u, v) for u in us for v in vs}
    return frozenset(preview) if preview == expected else None


def qq_special_confirm_point(
    capture: FarmCapture, target: frozenset[Cell], layout: dict
) -> tuple[float, float] | None:
    """Return verified local confirm-button point for one exact 2x2 preview."""
    if (not isinstance(target, frozenset) or len(target) != 4
        or not target.issubset(ALL_CELLS)):
        return None
    if observe_qq_preview_cells(capture, layout) != target:
        return None
    us = {u for u, _ in target}
    vs = {v for _, v in target}
    if (len(us) != 2 or len(vs) != 2
        or max(us) - min(us) != 1 or max(vs) - min(vs) != 1):
        return None

    try:
        qq = layout["platforms"]["qq"]
        cfg = qq["planting"]
        origin = np.asarray(qq["origin"], dtype=np.float64)
        u_step = np.asarray(qq["u_step"], dtype=np.float64)
        v_step = np.asarray(qq["v_step"], dtype=np.float64)
        dx, dy = map(float, cfg["special_confirm_offset_normalized"])
        radius = int(cfg["special_confirm_radius"])
        lime_min = int(cfg["special_confirm_lime_min"])
        white_min = int(cfg["special_confirm_white_min"])
        if not 20 <= radius <= 60 or lime_min <= 0 or white_min <= 0:
            return None
    except (KeyError, TypeError, ValueError):
        return None

    points = np.asarray(
        [origin + u*u_step + v*v_step for u, v in target],
        dtype=np.float64,
    )
    center = points.mean(axis=0)
    x = float(center[0] + dx * capture.frame.width)
    y = float(center[1] + dy * capture.frame.height)
    xi, yi = map(int, np.rint((x, y)))
    patch = _patch(capture.rgb, xi, yi, radius)
    if patch is None or patch.shape != (2*radius+1, 2*radius+1, 3):
        return None

    rgb = patch.astype(np.int16)
    r, g, b = (rgb[:, :, i] for i in range(3))
    lime = ((g > 145) & (r > 80) & (r < 210) & (b < 90)
            & (g > r * 1.15) & (g > b * 2.0))
    white = (r > 210) & (g > 210) & (b > 185)
    if int(np.count_nonzero(lime)) < lime_min:
        return None
    if int(np.count_nonzero(white)) < white_min:
        return None
    return x, y


def check_wechat_empty_field(capture: FarmCapture, layout: dict) -> EmptyFieldCheck:
    """Return EMPTY, NOT_EMPTY, or UNKNOWN for the calibrated WeChat field."""
    rgb = getattr(capture, "rgb", None)
    if (rgb is None or rgb.dtype != np.uint8
        or not getattr(capture, "capture_id", None)
        or type(capture.captured_at_ns) is not int or capture.captured_at_ns <= 0):
        return _unknown("UNTRUSTED_CAPTURE")

    try:
        wechat = layout["platforms"]["wechat"]
        cfg = wechat["empty_check"]
        width = int(round(capture.frame.width))
        height = int(round(capture.frame.height))
        min_width, max_width = map(int, cfg["verified_window_width_range"])
        expected_height = int(cfg["verified_window_height"])
        if (not min_width <= width <= max_width or height != expected_height
            or rgb.shape != (height, width, 3)):
            return _unknown("WINDOW_SIZE_CHANGED")

        origin = np.asarray(wechat["normalized_origin"], dtype=np.float64)
        u_step = np.asarray(wechat["normalized_u_step"], dtype=np.float64)
        v_step = np.asarray(wechat["normalized_v_step"], dtype=np.float64)
        soil_offset = np.asarray(cfg["soil_offset_normalized"], dtype=np.float64)
        occupancy_probes = [
            (
                str(row["id"]),
                np.asarray(row["offset_normalized"], dtype=np.float64),
                float(row["occupied_luminance_max"]),
            )
            for row in cfg["occupancy_probes"]
        ]
        if any(x.shape != (2,) for x in (origin, u_step, v_step, soil_offset)):
            return _unknown("INVALID_CALIBRATION")
        if (not occupancy_probes
            or len({probe_id for probe_id, _, _ in occupancy_probes}) != len(occupancy_probes)
            or any(not probe_id or offset.shape != (2,)
                   for probe_id, offset, _ in occupancy_probes)):
            return _unknown("INVALID_CALIBRATION")

        radius = cfg["patch_radius"]
        soil_prototypes = {
            name: np.asarray(value, dtype=np.float64)
            for name, value in cfg["soil_prototypes"].items()
        }
        if (type(radius) is not int or not 1 <= radius <= 8
            or set(soil_prototypes) != {"purple", "gold"}
            or any(value.shape != (3,) for value in soil_prototypes.values())):
            return _unknown("INVALID_CALIBRATION")

        empty_soil_max = float(cfg["empty_soil_max_distance"])
        occupied_soil_max = float(cfg["occupied_soil_max_distance"])
        empty_lum_min = float(cfg["empty_luminance_min"])
        if not (0 < empty_soil_max < occupied_soil_max
                and all(0 < occupied_lum_max < empty_lum_min
                        for _, _, occupied_lum_max in occupancy_probes)):
            return _unknown("INVALID_CALIBRATION")
    except (KeyError, TypeError, ValueError):
        return _unknown("INVALID_CALIBRATION")

    scale = np.asarray([width, height], dtype=np.float64)
    empty: list[Cell] = []
    occupied: list[Cell] = []
    unknown: list[Cell] = []

    for cell in ALL_CELLS:
        u, v = cell
        base = (origin + u * u_step + v * v_step) * scale

        soil_point = np.rint(base + soil_offset * scale).astype(int)
        soil_patch = _patch(rgb, int(soil_point[0]), int(soil_point[1]), radius)
        occupancy_patches = []
        for probe_id, occupancy_offset, occupied_lum_max in occupancy_probes:
            point = np.rint(base + occupancy_offset * scale).astype(int)
            patch = _patch(rgb, int(point[0]), int(point[1]), radius)
            occupancy_patches.append((probe_id, occupied_lum_max, patch))
        if soil_patch is None or any(patch is None for _, _, patch in occupancy_patches):
            unknown.append(cell)
            continue

        soil_rgb = np.median(soil_patch.reshape(-1, 3), axis=0)
        distances = {
            name: _distance(soil_rgb, prototype)
            for name, prototype in soil_prototypes.items()
        }
        grade = min(distances, key=distances.get)
        soil_distance = distances[grade]
        occupancy_luminances = [
            (
                probe_id,
                occupied_lum_max,
                float(np.median(patch.astype(np.float64).mean(axis=2))),
            )
            for probe_id, occupied_lum_max, patch in occupancy_patches
        ]

        if (soil_distance <= occupied_soil_max
            and any(luminance < occupied_lum_max
                    for _, occupied_lum_max, luminance in occupancy_luminances)):
            occupied.append(cell)
        elif (soil_distance <= empty_soil_max
              and all(luminance > empty_lum_min
                      for _, _, luminance in occupancy_luminances)):
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
        if any(x.shape != (2,) for x in (
            origin, u_step, v_step, soil_offset, occupancy_offset
        )):
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
