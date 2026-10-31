"""Local QQ picker page/target observation from a fresh farm-window screenshot.

Only verified local UI evidence is returned. Unknown platform, seed icon,
quantity, page indicator, or layout => None / fail-closed. This module never
clicks and never treats historical inventory as visual confirmation.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image

from farm_capture import FarmCapture

ROOT = Path(__file__).resolve().parents[1]
# Target-specific live crops, verified visually on 2026-10-31 QQ.
# Other seeds/platforms stay unknown rather than matching a similar-looking icon.
QQ_TARGET_ICONS = {
    "泡泡棉花糖种子": ROOT / "assets/ui/picker/qq-cotton-candy.png",
    "天山红枫种子": ROOT / "assets/ui/picker/qq-red-maple.png",
}
QQ_SLOT_X = (95, 191, 287, 383, 480)
QQ_PAGE_ROI = (282, 817, 342, 863)
QQ_BADGE_Y = (717, 764)
QQ_ICON_Y = (754, 817)
QQ_RIGHT_ARROW_ROI = (555, 756, 585, 793)
QQ_LEFT_ARROW_ROI = (15, 745, 55, 797)
# 2026-10-31 QQ live screenshot: unchecked one-key toggle inside picker.
# An enabled toggle is NOT calibrated; do not infer True from not matching OFF.
QQ_ONE_KEY_OFF_ROI = (370, 779, 400, 810)
QQ_ONE_KEY_OFF = ROOT / "assets/ui/picker/qq-one-key-off.png"


def _crop(capture: FarmCapture, box: tuple[int, int, int, int]) -> np.ndarray | None:
    if getattr(capture, "rgb", None) is None:
        return None
    h, w = capture.rgb.shape[:2]
    # Coordinates are calibrated against the 603x1111 QQ window only.
    if capture.frame.width < 570 or capture.frame.width > 640:
        return None
    sx, sy = w / 603, h / 1111
    x0, y0, x1, y1 = box
    coords = (round(x0 * sx), round(y0 * sy),
              round(x1 * sx), round(y1 * sy))
    a, b, c, d = coords
    if a < 0 or b < 0 or c > w or d > h or a >= c or b >= d:
        return None
    return capture.rgb[b:d, a:c]


def _read_text(crop: np.ndarray | None, binary: Path | None) -> str | None:
    if crop is None or binary is None or not binary.is_file():
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="farm-picker-ocr-") as tmp:
            path = Path(tmp) / "crop.png"
            Image.fromarray(crop).resize(
                (crop.shape[1] * 8, crop.shape[0] * 8)
            ).save(path)
            result = subprocess.run(
                [str(binary), str(path)], capture_output=True, text=True,
                timeout=8, check=False,
            )
        if result.returncode:
            return None
        rows = json.loads(result.stdout)["observations"]
        if len(rows) != 1 or rows[0].get("confidence", 0) < 0.95:
            return None
        return rows[0].get("text")
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return None


def _correlation(template: np.ndarray, patch: np.ndarray) -> float:
    if template.shape != patch.shape:
        patch = np.asarray(
            Image.fromarray(patch).resize((template.shape[1], template.shape[0])),
            dtype=np.float32,
        )
    else:
        patch = patch.astype(np.float32)
    target = template.astype(np.float32)
    a = (target - target.mean(axis=(0, 1), keepdims=True)).ravel()
    b = (patch - patch.mean(axis=(0, 1), keepdims=True)).ravel()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / denominator) if denominator > 1e-6 else -1.0


def _shift_y(box: tuple[int, int, int, int], dy: int) -> tuple[int, int, int, int]:
    return (box[0], box[1] + dy, box[2], box[3] + dy)


@lru_cache(maxsize=1)
def _off_template() -> np.ndarray | None:
    try:
        return np.asarray(Image.open(QQ_ONE_KEY_OFF).convert("RGB"))
    except (OSError, ValueError):
        return None


def _off_checkbox_score(capture: FarmCapture, offset: int) -> float:
    """Local fixed-control template only; no inference about field occupancy."""
    patch = _crop(capture, _shift_y(QQ_ONE_KEY_OFF_ROI, offset))
    reference = _off_template()
    if patch is None or reference is None:
        return -1.0
    if patch.shape != reference.shape:
        patch = np.asarray(Image.fromarray(patch).resize(
            (reference.shape[1], reference.shape[0])))
    # Compare only the brown square, not the animated grass surrounding it.
    actual = patch[6:26, 6:24].astype(np.int16)
    expected = reference[6:26, 6:24].astype(np.int16)
    per_pixel = np.max(np.abs(actual - expected), axis=2)
    return float(np.mean(per_pixel <= 14))


def _off_checkbox_distance(capture: FarmCapture, offset: int) -> float:
    patch = _crop(capture, _shift_y(QQ_ONE_KEY_OFF_ROI, offset))
    reference = _off_template()
    if patch is None or reference is None:
        return float("inf")
    if patch.shape != reference.shape:
        patch = np.asarray(Image.fromarray(patch).resize(
            (reference.shape[1], reference.shape[0])))
    return float(np.mean(np.abs(patch.astype(np.int16) - reference.astype(np.int16))))


def find_qq_picker_y_shift(capture: FarmCapture, platform: str) -> int | None:
    """Locate QQ picker vertical placement from its verified OFF checkbox.

    The previous picker calibration was at checkbox y=821; clicking another
    plot opens the SAME picker at y=779. Both positions must share one local
    offset for page, badges, icons and arrows. Unknown/checked controls STOP.
    """
    if platform != "qq":
        return None
    candidates = [(offset, _off_checkbox_score(capture, offset))
                  for offset in range(-65, 96)]
    accepted = [(offset, score) for offset, score in candidates if score >= 0.98]
    if not accepted:
        return None
    # The checkbox interior is a solid square (several adjacent y values
    # score 1.0). Use the full control border to disambiguate exact y.
    best_offset = min((offset for offset, _ in accepted),
                      key=lambda offset: _off_checkbox_distance(capture, offset))
    if (_off_checkbox_distance(capture, best_offset) > 12
        or any(abs(offset - best_offset) > 5 for offset, _ in accepted)):
        return None  # Ambiguous or visually changed control.
    return best_offset - 42  # current OFF reference y=779; old base y=821.


def observe_one_key_mode(capture: FarmCapture, platform: str,
                         picker_y_shift: int | None = None) -> bool | None:
    """Only prove QQ picker toggle OFF; an enabled state stays unknown."""
    if platform != "qq":
        return None
    shift = (find_qq_picker_y_shift(capture, platform)
             if picker_y_shift is None else picker_y_shift)
    if shift is None:
        return None
    return False if _off_checkbox_score(capture, shift + 42) >= 0.98 else None


def observe_picker(capture: FarmCapture, platform: str, expected_slot: int,
                   target_seed: str, ocr_binary: Path | None) -> dict:
    """Return page, total, icon, quantity; unknown values never grant selection."""
    unknown = {"page": None, "total_pages": None,
               "target_icon_verified": None, "target_quantity": None,
               "icon_score": None, "one_key_planting": None,
               "picker_y_shift": None}
    if platform != "qq" or type(expected_slot) is not int or not 1 <= expected_slot <= 5:
        return unknown
    # The picker moves vertically with the plot clicked. Prefer an exact
    # bounded OFF-checkbox anchor; fall back to the previously calibrated
    # fixed page ROI only when its page counter independently verifies.
    shift = find_qq_picker_y_shift(capture, platform)
    if shift is None:
        counter = _read_text(_crop(capture, QQ_PAGE_ROI), ocr_binary)
        shift = 0
    else:
        counter = _read_text(_crop(capture, _shift_y(QQ_PAGE_ROI, shift)), ocr_binary)
    if not isinstance(counter, str):
        return unknown
    match = re.fullmatch(r"\s*(\d{1,2})\s*/\s*(\d{1,2})\s*", counter)
    if match is None:
        return unknown
    page, total = map(int, match.groups())
    if not 1 <= page <= total <= 20:
        return unknown
    result = {**unknown, "page": page, "total_pages": total,
              "picker_y_shift": shift,
              "one_key_planting": observe_one_key_mode(capture, platform, shift)}
    template_path = QQ_TARGET_ICONS.get(target_seed)
    if template_path is None or not template_path.is_file():
        return result
    try:
        template = np.asarray(Image.open(template_path).convert("RGB"))
        scores = []
        for x in QQ_SLOT_X:
            patch = _crop(capture, (x - 34, QQ_ICON_Y[0] + shift,
                                    x + 34, QQ_ICON_Y[1] + shift))
            if patch is None:
                return result
            scores.append(_correlation(template, patch))
    except (OSError, ValueError):
        return result
    own = scores[expected_slot - 1]
    other = max(v for i, v in enumerate(scores) if i != expected_slot - 1)
    result["icon_score"] = round(own, 4)
    result["target_icon_verified"] = own >= 0.90 and own - other >= 0.12
    if not result["target_icon_verified"]:
        return result
    x = QQ_SLOT_X[expected_slot - 1]
    badge = _read_text(_crop(capture, (x - 35, QQ_BADGE_Y[0] + shift,
                                      x + 35, QQ_BADGE_Y[1] + shift)), ocr_binary)
    if isinstance(badge, str) and re.fullmatch(r"[1-9]\d{0,3}", badge):
        result["target_quantity"] = int(badge)
    return result


def picker_arrow_verified(capture: FarmCapture, direction: int,
                          picker_y_shift: int = 0) -> bool:
    """Verify the actual QQ page-turn arrow before a bounded navigation batch."""
    if direction not in (-1, 1):
        return False
    patch = _crop(capture, _shift_y(QQ_RIGHT_ARROW_ROI if direction == 1
                                   else QQ_LEFT_ARROW_ROI, picker_y_shift))
    if patch is None:
        return False
    r, g, b = (patch[:, :, i].astype(np.int16) for i in range(3))
    bright = (r > 205) & (g > 170) & (b > 90) & (r > b + 45)
    return int(np.count_nonzero(bright)) >= max(80, patch.shape[0] * patch.shape[1] // 8)


def right_arrow_verified(capture: FarmCapture) -> bool:
    """Compatibility alias for existing right-arrow callers."""
    return picker_arrow_verified(capture, 1)
