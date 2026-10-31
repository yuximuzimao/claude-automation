"""Conservative QQ 24-cell *clean* observation from five real empty-field samples.

This is a postcondition observer, not an occupancy classifier for planting.
Only an exact, same-layout QQ screenshot with all 24 independently matching
empty soil can return 24. Any mismatch returns None; no clicks are authorized.
The tiny center ROI specifically rejects small seedlings missed by coarse RGB
averages. Unknown overlay/window identity is handled by the calling adapter.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from farm_capture import FarmCapture

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "assets/ui/field/qq-empty-atlas.png"
PATCH_RADIUS = 9
PATCH_SIZE = 19
ATLAS_SAMPLES = 5
# These are only valid for the verified 2026-10-31 QQ 6-purple/18-gold grid.
VERIFIED_PURPLE = frozenset({(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1)})
ALL_CELLS = frozenset((u, v) for u in range(6) for v in range(4))


@lru_cache(maxsize=1)
def _atlas() -> np.ndarray | None:
    try:
        with Image.open(ATLAS) as im:
            rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
        return rgb if rgb.shape == (4 * ATLAS_SAMPLES * PATCH_SIZE, 6 * PATCH_SIZE, 3) else None
    except (OSError, ValueError):
        return None


def _patch(image: np.ndarray, x: int, y: int) -> np.ndarray | None:
    r = PATCH_RADIUS
    if x - r < 0 or y - r < 0 or x + r >= image.shape[1] or y + r >= image.shape[0]:
        return None
    return image[y-r:y+r+1, x-r:x+r+1]


def _same_grade_templates(atlas: np.ndarray, purple: bool) -> list[np.ndarray]:
    samples = []
    for sample in range(ATLAS_SAMPLES):
        for u, v in ALL_CELLS:
            if ((u, v) in VERIFIED_PURPLE) != purple:
                continue
            y, x = (v + 4 * sample) * PATCH_SIZE, u * PATCH_SIZE
            samples.append(atlas[y:y+PATCH_SIZE, x:x+PATCH_SIZE])
    return samples


def observe_qq_clean_cells(capture: FarmCapture, layout: dict) -> int | None:
    """Return 24 only if every tile is independently confirmed empty.

    Unknown, occupied, overlay, shifted scene, altered land grades, or a
    single suspicious tiny center sprout all return None (fail closed).
    No inference of partial occupancy is made.
    """
    if (getattr(capture, "rgb", None) is None or not getattr(capture, "capture_id", None)
        or type(capture.captured_at_ns) is not int or capture.captured_at_ns <= 0
        or (capture.frame.width, capture.frame.height) != (603, 1111)
        or capture.rgb.shape != (1111, 603, 3)):
        return None
    try:
        g = layout["platforms"]["qq"]
        purple = frozenset(tuple(x) for x in g["land_grades"]["purple_cells"])
        gold = frozenset(tuple(x) for x in g["land_grades"]["gold_cells"])
        origin, u_step, v_step = g["origin"], g["u_step"], g["v_step"]
        if purple != VERIFIED_PURPLE or purple | gold != ALL_CELLS or purple & gold:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    atlas = _atlas()
    if atlas is None:
        return None
    refs = {True: _same_grade_templates(atlas, True),
            False: _same_grade_templates(atlas, False)}
    for u, v in ALL_CELLS:
        x = round(origin[0] + u*u_step[0] + v*v_step[0])
        y = round(origin[1] + u*u_step[1] + v*v_step[1])
        patch = _patch(capture.rgb, x, y)
        if patch is None:
            return None
        is_purple = (u, v) in purple
        # A 2x2 seedling covers four of the 7x7 central pixels. Requiring
        # <=3 changed pixels on purple and <=1 on gold rejects that sample.
        center_limit = 3 if is_purple else 1
        outer_limit = 0.14 if is_purple else 0.03
        matched = False
        for ref in refs[is_purple]:
            delta = np.max(np.abs(patch.astype(np.int16) - ref.astype(np.int16)), axis=2)
            center = delta[6:13, 6:13]
            if (int(np.count_nonzero(center > 35)) <= center_limit
                and float(np.mean(delta > 25)) <= outer_limit):
                matched = True
                break
        if not matched:
            return None
    return 24
