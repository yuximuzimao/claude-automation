"""Read-only QQ single white-radish landing proof for controlled M2 calibration.

The existing 24-cell empty-field verifier is the authority for the before
frame and for every *other* cell after planting. This narrow observer never
chooses a planting coordinate, sends input, or authorizes ordinary/special
planting. It only identifies one newly occupied cell from two independent
real captures, using actual gold/purple white-radish seedling patches.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from farm_capture import FarmCapture
from farm_qq_clean import ALL_CELLS, ROOT, VERIFIED_PURPLE, observe_qq_clean_cells

GOLD_PATCH = ROOT / "assets/ui/field/qq-white-radish-seedling-negative.png"
PURPLE_PATCH = ROOT / "assets/ui/field/qq-purple-white-radish-seedling-negative.png"


@dataclass(frozen=True)
class LandingProof:
    observed_cell: tuple[int, int]
    capture_before: str
    capture_after: str
    # This is an observed result, NOT a verified safe future click coordinate.
    seed: str = "白萝卜"


@lru_cache(maxsize=2)
def _seedling_template(purple: bool) -> np.ndarray:
    with Image.open(PURPLE_PATCH if purple else GOLD_PATCH) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _roi(rgb: np.ndarray, x: int, y: int, purple: bool):
    if purple:
        return rgb[y+11:y+24, x-19:x-3], (slice(y+11, y+24), slice(x-19, x-3))
    return rgb[y+5:y+27, x-23:x+24], (slice(y+5, y+27), slice(x-23, x+24))


def _looks_like_known_seedling(patch: np.ndarray, purple: bool) -> bool:
    template = _seedling_template(purple)
    if patch.shape != template.shape:
        return False
    # Exact real reference is accepted. Color/animation drift must remain
    # small; an arbitrary dark UI decoration cannot stand in for a seedling.
    delta = np.max(np.abs(patch.astype(np.int16) - template.astype(np.int16)), axis=2)
    if float(np.mean(delta <= 28)) < 0.84 or float(np.median(delta)) > 10:
        return False
    if purple:
        return int(np.count_nonzero(np.all(patch < 90, axis=2))) >= 4
    dark = ((patch[:, :, 0] < 115) & (patch[:, :, 1] < 95)
            & (patch[:, :, 2] < 85))
    return int(np.count_nonzero(dark)) >= 4


def verify_qq_single_radish_landing(
    before: FarmCapture, after: FarmCapture, layout: dict,
) -> LandingProof | None:
    """Prove exactly one known seedling appeared in an otherwise empty field.

    No result for unknown overlays, untrusted/stale captures, more than one
    changed cell, other crops, scene drift, or missing screenshot provenance.
    Captures must come from the same unchanged window, after must be newer.
    """
    if (not before.capture_id or not after.capture_id
        or before.capture_id == after.capture_id
        or type(before.captured_at_ns) is not int
        or type(after.captured_at_ns) is not int
        or after.captured_at_ns <= before.captured_at_ns
        or before.frame != after.frame
        or before.rgb is None or after.rgb is None
        or observe_qq_clean_cells(before, layout) != 24
        or observe_qq_clean_cells(after, layout) == 24):
        return None
    if before.rgb.shape != (1111, 603, 3) or after.rgb.shape != before.rgb.shape:
        return None
    try:
        grid = layout["platforms"]["qq"]
        origin, u_step, v_step = grid["origin"], grid["u_step"], grid["v_step"]
        if frozenset(map(tuple, grid["land_grades"]["purple_cells"])) != VERIFIED_PURPLE:
            return None
    except (KeyError, TypeError, ValueError):
        return None

    matches = []
    for u, v in sorted(ALL_CELLS):
        x = round(origin[0] + u*u_step[0] + v*v_step[0])
        y = round(origin[1] + u*u_step[1] + v*v_step[1])
        purple = (u, v) in VERIFIED_PURPLE
        patch, roi = _roi(after.rgb, x, y, purple)
        if _looks_like_known_seedling(patch, purple):
            # Replacing *only* the candidate seedling ROI with the known
            # before-frame soil must restore a verified 24-cell empty field.
            # This rejects unrelated changes/overlays and extra seedlings.
            repaired = after.rgb.copy()
            repaired[roi] = before.rgb[roi]
            repaired_shot = FarmCapture(
                after.frame, after.gray, capture_id=after.capture_id,
                captured_at_ns=after.captured_at_ns, rgb=repaired,
            )
            if observe_qq_clean_cells(repaired_shot, layout) == 24:
                matches.append((u, v))
    if len(matches) != 1:
        return None
    return LandingProof(matches[0], before.capture_id, after.capture_id)
