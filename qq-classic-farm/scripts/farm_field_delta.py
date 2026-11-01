"""Whole-field, three-frame change evidence for a controlled single-radish experiment.

This is deliberately NOT an empty-field or planting-success classifier. It
replaces tiny-center-only *diagnosis* with complete affine tile coverage, and
requires a no-input control frame to distinguish ordinary animation. A sprite
can render across tile boundaries, so tile attribution remains unverified.
No input is sent and no click/occupancy authorization is returned.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from farm_capture import FarmCapture
from farm_geometry import validate_farm_window


@dataclass(frozen=True)
class FieldDelta:
    changed_pixels: int
    assigned_cells: tuple[tuple[int, int, int], ...]
    candidate_cells: tuple[tuple[int, int], ...]
    capture_ids: tuple[str, str, str]
    status: str = "diagnostic_only"
    can_authorize_clicks: bool = False
    registration_offset_local: tuple[float, float] | None = None


class FieldDeltaStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def analyze_field_delta(
    before: FarmCapture, idle: FarmCapture, after: FarmCapture,
    platform: str, layout: dict,
    *, registration_offset_local: tuple[float, float] | None = None,
) -> FieldDelta:
    """Find scene changes over all 24 diamond areas, with an idle control.

    The three captures must be from the same unmoved window, in time order.
    No-input idle controls must be captured before any deliberate test click.
    The caller must independently verify scene alignment and absence of overlays;
    this diagnostic cannot prove crop identity, actual landing cell or emptiness.
    """
    shots = (before, idle, after)
    if (any(not s.capture_id or type(s.captured_at_ns) is not int
            or s.captured_at_ns <= 0 or s.rgb is None for s in shots)
        or len({s.capture_id for s in shots}) != 3
        or not before.captured_at_ns < idle.captured_at_ns < after.captured_at_ns
        or any(s.frame != before.frame or s.rgb.shape != before.rgb.shape
               for s in shots)):
        raise FieldDeltaStop("FIELD_DELTA_CAPTURE_INVALID",
                             "Three ordered, distinct captures of one unchanged window required")
    try:
        validate_farm_window(before.frame, platform, layout)
        cfg = layout["platforms"][platform]
        origin = np.asarray(cfg["origin"], dtype=float)
        if registration_offset_local is not None:
            offset = np.asarray(registration_offset_local, dtype=float)
            if offset.shape != (2,) or not np.all(np.isfinite(offset)):
                raise ValueError("Invalid live field registration offset")
            origin = origin + offset
        steps = np.asarray((cfg["u_step"], cfg["v_step"]), dtype=float).T
        if abs(np.linalg.det(steps)) < 1:
            raise ValueError("Degenerate grid")
        inverse = np.linalg.inv(steps)
    except (KeyError, TypeError, ValueError) as exc:
        raise FieldDeltaStop("FIELD_DELTA_GEOMETRY_INVALID", str(exc)) from exc

    h, w, _ = before.rgb.shape
    sy = h / before.frame.height
    sx = w / before.frame.width
    yy, xx = np.indices((h, w), dtype=float)
    delta = np.stack((xx / sx - origin[0], yy / sy - origin[1]), axis=0)
    uv = np.einsum("ij,jhw->ihw", inverse, delta)
    u, v = uv[0], uv[1]

    # Cover complete diamonds plus a small margin for sprites extending past
    # their soil. Pixels are attributed by nearest *nominal* tile, not proof of
    # crop ownership; neighboring sprite spill can shift this attribution.
    field = (u >= -0.9) & (u <= 5.9) & (v >= -0.9) & (v <= 3.9)
    a = before.rgb.astype(np.int16)
    b = idle.rgb.astype(np.int16)
    c = after.rgb.astype(np.int16)
    idle_delta = np.max(np.abs(b - a), axis=2)
    after_delta = np.max(np.abs(c - a), axis=2)
    changed = field & (after_delta >= 30) & (after_delta > idle_delta + 18)
    # A tiny isolated difference is not actionable even as a candidate.
    count = int(np.count_nonzero(changed))
    if count < 6:
        raise FieldDeltaStop("FIELD_DELTA_INCONCLUSIVE",
                             "No change above the no-input animation control")

    ui = np.clip(np.floor(u + 0.5).astype(int), 0, 5)
    vi = np.clip(np.floor(v + 0.5).astype(int), 0, 3)
    assigned = []
    for i in range(6):
        for j in range(4):
            n = int(np.count_nonzero(changed & (ui == i) & (vi == j)))
            if n >= 6:
                assigned.append((i, j, n))

    # The margin and sprite overlap mean even one nominal changed tile is not
    # enough to infer the clicked or occupied cell.
    return FieldDelta(
        changed_pixels=count,
        assigned_cells=tuple(assigned),
        candidate_cells=tuple((i, j) for i, j, _ in assigned),
        capture_ids=tuple(s.capture_id for s in shots),
        registration_offset_local=(
            tuple(float(v) for v in registration_offset_local)
            if registration_offset_local is not None else None
        ),
    )
