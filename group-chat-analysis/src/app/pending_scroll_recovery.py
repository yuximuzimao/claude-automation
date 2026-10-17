"""Pure matching helpers for conservative pending-scroll re-anchoring."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence


SAME_VIEW_MAX_DISTANCE = 20
POSITION_TOLERANCE = 0.025


def _normalize_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", "", value).casefold()


def _fingerprint_bits(value: object) -> int | None:
    if not isinstance(value, str) or not value.startswith("dhash512:"):
        return None
    hex_value = value.split(":", 1)[1]
    if len(hex_value) != 128:
        return None
    try:
        return int(hex_value, 16)
    except ValueError:
        return None


def fingerprint_distance(left: Mapping[str, object], right: Mapping[str, object]) -> int | None:
    lhs = _fingerprint_bits(left.get("visual_fingerprint"))
    rhs = _fingerprint_bits(right.get("visual_fingerprint"))
    if lhs is None or rhs is None:
        return None
    return (lhs ^ rhs).bit_count()


def _content_blocks(page: Mapping[str, object]) -> list[tuple[str, float, float]]:
    region = page.get("content_region")
    blocks = page.get("blocks")
    if not isinstance(region, Mapping) or not isinstance(blocks, Sequence):
        return []
    try:
        min_x = float(region["x"])
        min_y = float(region["y"])
        max_x = min_x + float(region["width"])
        max_y = min_y + float(region["height"])
    except (KeyError, TypeError, ValueError):
        return []

    result: list[tuple[str, float, float]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        bbox = block.get("bbox")
        if not isinstance(bbox, Mapping):
            continue
        try:
            mid_x = float(bbox["x"]) + float(bbox["width"]) / 2.0
            mid_y = float(bbox["y"]) + float(bbox["height"]) / 2.0
        except (KeyError, TypeError, ValueError):
            continue
        if not (min_x <= mid_x <= max_x and min_y <= mid_y <= max_y):
            continue
        text = _normalize_text(block.get("text"))
        if len(text) < 2:
            continue
        result.append((text, mid_x, mid_y))
    return result


def raw_pages_same_view(
    probe: Mapping[str, object],
    durable: Mapping[str, object],
    *,
    maximum_distance: int = SAME_VIEW_MAX_DISTANCE,
    position_tolerance: float = POSITION_TOLERANCE,
) -> bool:
    """Return whether a probe conservatively matches one already-durable viewport.

    dHash alone is not unique enough because adjacent QQ history pages overlap.
    Require at least one/two exact normalized OCR strings at approximately the
    same screen position as an additional same-view signal.
    """

    distance = fingerprint_distance(probe, durable)
    if distance is None or distance > maximum_distance:
        return False

    probe_blocks = _content_blocks(probe)
    durable_blocks = _content_blocks(durable)
    if not probe_blocks or not durable_blocks:
        return False

    used: set[int] = set()
    positional_matches = 0
    for text, x, y in probe_blocks:
        best_index: int | None = None
        best_delta: float | None = None
        for index, (other_text, other_x, other_y) in enumerate(durable_blocks):
            if index in used or text != other_text:
                continue
            dx = abs(x - other_x)
            dy = abs(y - other_y)
            if dx > position_tolerance or dy > position_tolerance:
                continue
            delta = dx + dy
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_index = index
        if best_index is not None:
            used.add(best_index)
            positional_matches += 1

    required = 1 if min(len(probe_blocks), len(durable_blocks)) < 4 else 2
    return positional_matches >= required


def matching_durable_indices(
    probe: Mapping[str, object],
    durable_pages: Mapping[int, Mapping[str, object]],
) -> set[int]:
    return {
        index
        for index, page in durable_pages.items()
        if raw_pages_same_view(probe, page)
    }


def unique_rewind_anchor(
    first_probe: Mapping[str, object],
    second_probe: Mapping[str, object],
    durable_pages: Mapping[int, Mapping[str, object]],
) -> int | None:
    """Find a unique consecutive durable sequence after two rewind observations.

    Rewinding moves toward newer messages, so page indices must decrease by one:
    the first probe should match N and the next probe N-1.  Return the current
    (second probe) durable index when exactly one such sequence exists.
    """

    first = matching_durable_indices(first_probe, durable_pages)
    second = matching_durable_indices(second_probe, durable_pages)
    pairs = [(left, right) for left in first for right in second if right == left - 1]
    if len(pairs) != 1:
        return None
    return pairs[0][1]
