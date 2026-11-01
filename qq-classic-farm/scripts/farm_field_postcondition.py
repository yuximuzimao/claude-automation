"""Conservative whole-field postcondition against a *separately trusted* empty frame.

A 19x19 soil patch is not proof of an empty plot. Compare the full registered
field, including the space above soil where crop sprites render. An independent
no-input frame marks animation as UNKNOWN rather than silently masking it.
This observer is a postcondition only: it never authorizes clicks, and a clean
result is conditional on a separately verified empty reference.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from farm_capture import FarmCapture
from farm_field import FieldStop, probe_field_translation
from farm_geometry import validate_farm_window


class FieldPostconditionStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FieldPostcondition:
    clean_cells: tuple[tuple[int, int], ...]
    changed_cells: tuple[tuple[int, int], ...]
    unknown_cells: tuple[tuple[int, int], ...]
    clean_field_verified: bool
    capture_ids: tuple[str, str, str]
    status: str = "reference_comparison"
    can_authorize_clicks: bool = False


def compare_empty_field_postcondition(
    empty: FarmCapture, idle: FarmCapture, current: FarmCapture,
    platform: str, layout: dict, *, empty_reference_verified: bool = False,
) -> FieldPostcondition:
    """Compare 24 complete registered regions; uncertainty is never 'empty'.

    The empty reference MUST have independent semantic approval; this function
    cannot bootstrap that approval from its own pixel comparison. All three
    frames must share the same window geometry and distinct ordered provenance.
    A moving decoration makes affected cells unknown, not automatically clean.
    """
    if empty_reference_verified is not True:
        raise FieldPostconditionStop(
            "EMPTY_REFERENCE_UNVERIFIED", "A separately approved clean reference is required")
    shots = (empty, idle, current)
    if (any(s.rgb is None or not s.capture_id
            or type(s.captured_at_ns) is not int or s.captured_at_ns <= 0 for s in shots)
        or len({s.capture_id for s in shots}) != 3
        or not empty.captured_at_ns < idle.captured_at_ns < current.captured_at_ns
        or any(s.frame != empty.frame or s.rgb.shape != empty.rgb.shape for s in shots)):
        raise FieldPostconditionStop(
            "FIELD_POST_CAPTURE_INVALID", "Three ordered captures of one unchanged window required")
    try:
        validate_farm_window(empty.frame, platform, layout)
        alignments = [probe_field_translation(s, platform, layout) for s in shots]
        offsets = [np.asarray(a["offset_local"], dtype=float) for a in alignments]
        if any(np.max(np.abs(offsets[i] - offsets[0])) > 2 for i in (1, 2)):
            raise FieldPostconditionStop("FIELD_POST_ALIGNMENT_DRIFT",
                                         "Live field registration changed")
        cfg = layout["platforms"][platform]
        origin = np.asarray(cfg["origin"], dtype=float) + offsets[0]
        steps = np.asarray((cfg["u_step"], cfg["v_step"]), dtype=float).T
        if abs(np.linalg.det(steps)) < 1:
            raise ValueError("Degenerate field geometry")
        inverse = np.linalg.inv(steps)
    except FieldPostconditionStop:
        raise
    except (FieldStop, ValueError, KeyError, TypeError) as exc:
        raise FieldPostconditionStop("FIELD_POST_ALIGNMENT_UNKNOWN", str(exc)) from exc

    h, w = empty.rgb.shape[:2]
    yy, xx = np.indices((h, w), dtype=float)
    uv = np.einsum(
        "ij,jhw->ihw", inverse,
        np.stack((xx * empty.frame.width / w - origin[0],
                  yy * empty.frame.height / h - origin[1])),
    )
    u, v = uv
    # Exact 24-tile affine footprint. Extra perimeter margins would attribute
    # moving decorations OUTSIDE the farm to edge cells; a crop's planted base
    # must intersect its own tile even if its sprite overflows the border.
    within = (u >= -0.5) & (u <= 5.5) & (v >= -0.5) & (v <= 3.5)
    ui = np.clip(np.floor(u + 0.5).astype(int), 0, 5)
    vi = np.clip(np.floor(v + 0.5).astype(int), 0, 3)
    a, b, c = (s.rgb.astype(np.int16) for s in shots)
    idle_diff = np.max(np.abs(b - a), axis=2)
    current_diff = np.max(np.abs(c - a), axis=2)
    clean, changed, unknown = [], [], []
    for i in range(6):
        for j in range(4):
            region = within & (ui == i) & (vi == j)
            if np.count_nonzero(region) < 100:
                unknown.append((i, j))
                continue
            # No silent animation exclusion: the cell remains unknown if its
            # no-input reference was unstable in the same spatial region.
            unstable = int(np.count_nonzero(region & (idle_diff > 30)))
            difference = int(np.count_nonzero(
                region & (current_diff > 30) & (current_diff > idle_diff + 18)))
            if unstable > 0:
                unknown.append((i, j))
            elif difference >= 4:
                changed.append((i, j))
            elif difference > 0:
                # One pixel of unexplained change is not proof of a crop, but
                # it is also not sufficient evidence for an empty tile.
                unknown.append((i, j))
            else:
                clean.append((i, j))
    return FieldPostcondition(
        clean_cells=tuple(clean), changed_cells=tuple(changed),
        unknown_cells=tuple(unknown),
        clean_field_verified=len(clean) == 24,
        capture_ids=tuple(s.capture_id for s in shots),
    )
