"""M1 deterministic harvest phase, with an injectable local I/O adapter.

This module never captures screenshots or posts CGEvents itself. Live wiring is
intentionally absent until special-star offset, occupied 2x2 regions, overlay
recognition, and 24-cell clean-field vision are calibrated on real captures.
The adapter must provide those observations *locally*; no LLM round-trips.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from time import perf_counter, sleep
from typing import Protocol


class HarvestStop(ValueError):
    def __init__(self, code: str, message: str, *, clicks_sent: int = 0):
        super().__init__(message)
        self.code = code
        self.clicks_sent = clicks_sent


@dataclass(frozen=True)
class HarvestObservation:
    # An unknown/known overlay is not silently dismissed: no overlay whitelist yet.
    overlay: str
    calibration_verified: bool
    # Live registry identity + screen origin; must remain unchanged across phase.
    window_identity: tuple[int, int, str, str, float, float]
    window_width: float
    window_height: float
    # From a fresh capture_window() invocation, not derived from screenshot contents.
    capture_id: str
    captured_at_ns: int
    hand: tuple[float, float] | None
    # (placement ID, local x, local y); these are validated special-star points.
    special: tuple[tuple[str, float, float], ...]
    # Occupancy verified independently of star detection, not just legal anchors.
    occupied_special: frozenset[str] | None
    # Each entry means a specific plot is *confirmed empty*. None = unknown.
    empty_cells: tuple[bool, ...] | None


class HarvestAdapter(Protocol):
    def observe(self) -> HarvestObservation: ...
    def click_batch(self, points: tuple[tuple[float, float], ...]) -> int: ...
    def wait(self, seconds: float) -> None: ...


def _point(point: tuple[float, float], obs: HarvestObservation) -> None:
    if (len(point) != 2 or not all(isinstance(v, (int, float)) and
            not isinstance(v, bool) and isfinite(v) for v in point)
        or not 0 <= point[0] < obs.window_width
        or not 0 <= point[1] < obs.window_height):
        raise HarvestStop("CLICK_OUTSIDE_WINDOW", "Invalid window-local action point")


def _clean(obs: HarvestObservation) -> bool:
    if obs.empty_cells is None:
        return False
    if len(obs.empty_cells) != 24 or any(type(v) is not bool for v in obs.empty_cells):
        raise HarvestStop("INVALID_FIELD_OBSERVATION", "Expected 24 verified plot states")
    return all(obs.empty_cells)


def _check_overlay(obs: HarvestObservation) -> None:
    if obs.overlay == "none":
        return
    if obs.overlay == "known":
        raise HarvestStop("KNOWN_OVERLAY_UNHANDLED", "No calibrated overlay dismissal exists")
    raise HarvestStop("UNKNOWN_OVERLAY", "Unknown or invalid overlay observation")


def prepare_harvest(obs: HarvestObservation) -> tuple[tuple[float, float], ...]:
    """Fail-closed phase precheck. Returns a SINGLE ordered batch of local points.

    A clean field requires independent 24-cell proof, never 'no star detected'.
    Geometry alone does not prove occupancy or star calibration.
    """
    _check_overlay(obs)
    if (not isinstance(obs.capture_id, str) or not obs.capture_id
        or type(obs.captured_at_ns) is not int or obs.captured_at_ns <= 0):
        raise HarvestStop("HARVEST_CAPTURE_PROVENANCE_MISSING", "Observation lacks a trusted capture identifier/time")
    if not obs.calibration_verified:
        raise HarvestStop("HARVEST_CALIBRATION_REQUIRED", "Live star/occupancy calibration missing")
    if (not isfinite(obs.window_width) or not isfinite(obs.window_height)
        or obs.window_width <= 0 or obs.window_height <= 0):
        raise HarvestStop("INVALID_WINDOW", "Invalid harvest window dimensions")
    identity = obs.window_identity
    if (len(identity) != 6 or type(identity[0]) is not int or identity[0] <= 0
        or type(identity[1]) is not int or identity[1] <= 0
        or not isinstance(identity[2], str) or not identity[2]
        or identity[3] != "QQ经典农场"
        or not all(isinstance(v, (int, float)) and isfinite(v) for v in identity[4:])):
        raise HarvestStop("INVALID_WINDOW", "Missing or malformed window identity")
    if obs.occupied_special is None:
        raise HarvestStop("SPECIAL_OCCUPANCY_UNKNOWN", "Special occupancy has not been verified")
    if _clean(obs):
        if obs.special or obs.hand is not None or obs.occupied_special:
            raise HarvestStop("HARVEST_STATE_CONFLICT", "Clean field conflicts with crop occupancy or actionable controls")
        return ()
    if obs.hand is None:
        raise HarvestStop("HARVEST_HAND_MISSING", "Field not clean but global harvest control absent")
    _point(obs.hand, obs)
    if len(obs.special) > 6:
        raise HarvestStop("AMBIGUOUS_PICKABLES", "Too many special markers")
    used: set[str] = set()
    actions: list[tuple[float, float]] = []
    for placement, x, y in obs.special:
        if (not isinstance(placement, str) or not placement or placement in used
            or placement not in obs.occupied_special):
            raise HarvestStop("AMBIGUOUS_PICKABLES", "Star not uniquely tied to an occupied special plot")
        used.add(placement)
        _point((x, y), obs)
        actions.append((x, y))
    actions.append(obs.hand)
    return tuple(actions)


def run_harvest(adapter: HarvestAdapter) -> dict:
    """One local phase: precheck -> batch special stars + hand -> wait -> 24-cell verify.

    No automatic retry or speculative overlay click. A partial send must be
    reported as uncertain; the caller must not replay the same batch.
    """
    started = perf_counter()
    obs = adapter.observe()
    actions = prepare_harvest(obs)
    if not actions:
        return {"status": "already_clean", "click_count": 0,
                "llm_round_trips": 0, "phase_duration_ms": round((perf_counter()-started)*1000, 2)}
    try:
        sent = adapter.click_batch(actions)
    except Exception as exc:
        raise HarvestStop("HARVEST_PARTIAL_ACTION",
                          "Batch failed; actual click count is unknown, never retry blindly") from exc
    if type(sent) is not int or sent != len(actions):
        raise HarvestStop("HARVEST_PARTIAL_ACTION",
                          "Batch did not confirm the expected sent-click count",
                          clicks_sent=sent if type(sent) is int and sent >= 0 else 0)
    try:
        adapter.wait(3.0)
        after = adapter.observe()
    except Exception as exc:
        raise HarvestStop("HARVEST_POSTCONDITION_UNAVAILABLE",
                          "Cannot obtain fresh post-click observation; never replay actions",
                          clicks_sent=sent) from exc
    if (not isinstance(after.capture_id, str) or not after.capture_id
        or type(after.captured_at_ns) is not int
        or after.capture_id == obs.capture_id
        or after.captured_at_ns <= obs.captured_at_ns):
        raise HarvestStop("HARVEST_STALE_POSTCONDITION", "Postcondition must use a newer independent screenshot",
                          clicks_sent=sent)
    if (after.window_identity != obs.window_identity or
        after.window_width != obs.window_width or
        after.window_height != obs.window_height):
        raise HarvestStop("USER_INTERFERENCE", "Window identity or bounds changed during harvest",
                          clicks_sent=sent)
    try:
        _check_overlay(after)
    except HarvestStop as exc:
        raise HarvestStop(exc.code, str(exc), clicks_sent=sent) from exc
    if not after.calibration_verified or after.occupied_special is None:
        raise HarvestStop("HARVEST_POSTCONDITION_UNKNOWN", "Postcondition cannot be trusted",
                          clicks_sent=sent)
    if after.empty_cells is None:
        raise HarvestStop("HARVEST_POSTCONDITION_UNKNOWN", "Missing 24-cell empty-state evidence",
                          clicks_sent=sent)
    if not _clean(after):
        raise HarvestStop("HARVEST_FIELD_NOT_CLEAN", "Not all 24 plots are confirmed empty",
                          clicks_sent=sent)
    if after.special or after.hand is not None or after.occupied_special:
        raise HarvestStop("HARVEST_STATE_CONFLICT", "Controls or occupied special plots remain despite clean-field report",
                          clicks_sent=sent)
    return {"status": "clean_field_verified", "click_count": sent,
            "llm_round_trips": 0, "phase_duration_ms": round((perf_counter()-started)*1000, 2)}
