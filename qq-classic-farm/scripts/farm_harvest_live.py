"""M1 real local I/O adapter; read-only until independent field calibration exists.

This is the seam between the existing harvest FSM and macOS registry, capture,
vision and compiled CGEvent batch helper. A detected star is NOT proof of an
occupied special plot. Current live observations deliberately remain untrusted,
so neither this adapter nor the FSM can send clicks from them.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
from time import monotonic_ns, sleep
from typing import Callable

from farm_capture import capture_window
from farm_geometry import WindowFrame
from farm_harvest import HarvestObservation, HarvestStop, prepare_harvest
from farm_io import WindowHandle, find_farm_window, parse_click_batch_result
from farm_vision import probe_harvest


# Mac local clock, not the automation server timezone. End is exclusive.
BLACKOUTS = ((0, 60), (480, 540), (720, 780), (840, 845),
             (960, 1020), (1200, 1260))


def require_live_window(*, clock: Callable[[], datetime] = lambda: datetime.now().astimezone(),
                        margin_minutes: int = 2) -> None:
    """No live farm observation or input during business automation windows."""
    try:
        now = clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Local offset-aware Mac clock required")
        minute = now.hour * 60 + now.minute
        if any(any(start <= (minute + offset) % 1440 < end
                   for offset in range(margin_minutes + 1))
               for start, end in BLACKOUTS):
            raise HarvestStop("FARM_OPERATION_TIME_BLOCKED",
                              "Mac local clock is inside/too close to a prohibited interval")
    except HarvestStop:
        raise
    except Exception as exc:
        raise HarvestStop("FARM_OPERATION_TIME_UNKNOWN",
                          "Cannot verify Mac local operation time") from exc


def _identity(handle: WindowHandle) -> tuple[int, int, str, str, float, float]:
    f = handle.frame
    return (handle.window_id, handle.pid, f.owner, f.title, f.x, f.y)


def _same_handle(a: WindowHandle, b: WindowHandle) -> bool:
    return _identity(a) == _identity(b) and a.frame == b.frame


class LiveHarvestAdapter:
    """One local phase I/O, with no LLM calls and no automatic window activation.

    execute=False is the default; execute=True alone is never sufficient:
    independently verified overlay, star offset, special occupancy and 24-cell
    empty states must be supplied by a future calibrated observer.
    """

    def __init__(self, platform: str, layout: dict, anchors: dict,
                 registry_binary: Path, click_binary: Path | None = None,
                 *, execute: bool = False):
        self.platform = platform
        self.layout = layout
        self.anchors = anchors
        self.registry_binary = Path(registry_binary)
        self.click_binary = Path(click_binary) if click_binary is not None else None
        self.execute = execute
        self.last_observation: HarvestObservation | None = None
        self.last_handle: WindowHandle | None = None
        self.last_diagnostics: dict = {}

    def observe(self) -> HarvestObservation:
        # A failed recapture invalidates the previous observation, not just the
        # current attempt; no stale authorization may survive a capture error.
        self.last_observation = None
        self.last_handle = None
        self.last_diagnostics = {}
        require_live_window()
        handle = find_farm_window(self.platform, self.layout, self.registry_binary)
        capture = capture_window(handle.frame, self.platform, self.layout)
        # A screenshot of an old window after movement cannot be paired with a
        # fresh registry identity, even when its dimensions still match.
        again = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(handle, again):
            raise HarvestStop("USER_INTERFERENCE", "Window changed during capture")
        probe = probe_harvest(capture, self.anchors, self.platform, self.layout)
        hand = probe.get("hand", {})
        point = tuple(hand["local_center"]) if hand.get("matched") else None
        # The current detector produces *candidate* stars, not independently
        # verified 2x2 crop occupancy. Never promote them to click targets.
        self.last_diagnostics = {
            "hand_detected": point is not None,
            "hand_score": hand.get("score"),
            "candidate_special_count": len(probe.get("raw_pickable_candidates",
                                                      probe.get("pickables", []))),
            "candidate_special": probe.get("raw_pickable_candidates",
                                           probe.get("pickables", [])),
            "legacy_safe_placement_matches": probe.get("pickables", []),
            "ignored_outside_special_centers": probe.get("ignored_outside_special_centers"),
            "overlay": "unknown",
            "calibration_verified": False,
            "occupied_special": None,
            "empty_cells": None,
            "can_authorize_clicks": False,
        }
        obs = HarvestObservation(
            overlay="unknown", calibration_verified=False,
            window_identity=_identity(handle),
            window_width=handle.frame.width, window_height=handle.frame.height,
            capture_id=capture.capture_id or "",
            captured_at_ns=capture.captured_at_ns or 0,
            hand=point, special=(), occupied_special=None, empty_cells=None,
        )
        self.last_handle = handle
        self.last_observation = obs
        return obs

    def click_batch(self, points: tuple[tuple[float, float], ...]) -> int:
        require_live_window()
        obs, handle = self.last_observation, self.last_handle
        if obs is None or handle is None:
            raise HarvestStop("HARVEST_PRECONDITION_MISSING", "Observe before any click batch")
        # No permissive fallback: the existing real observer always reports
        # unverified, even if execute=True is requested by a caller.
        if (not self.execute or not obs.calibration_verified or
            obs.overlay != "none" or obs.occupied_special is None or
            obs.empty_cells is None):
            raise HarvestStop("HARVEST_CALIBRATION_REQUIRED",
                              "Live calibration and explicit execution are both required")
        age_ns = monotonic_ns() - obs.captured_at_ns
        if not 0 <= age_ns <= 2_000_000_000:
            raise HarvestStop("HARVEST_STALE_PRECONDITION",
                              "Click authorization requires a fresh live observation")
        if self.click_binary is None:
            raise HarvestStop("CGEVENT_HELPER_MISSING", "Compiled batch helper not configured")
        if tuple(points) != prepare_harvest(obs):
            raise HarvestStop("HARVEST_STATE_DRIFT", "Batch differs from verified observation")
        current = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(handle, current):
            raise HarvestStop("USER_INTERFERENCE", "Window changed before batch")
        f: WindowFrame = current.frame
        batch = {
            "window_id": current.window_id, "pid": current.pid,
            "owner": f.owner, "title": f.title,
            "frame": {"x": f.x, "y": f.y, "width": f.width, "height": f.height},
            "actions": [{"x": x, "y": y, "delay_ms": 100} for x, y in points],
        }
        try:
            proc = subprocess.run([str(self.click_binary), "--execute"],
                                  input=json.dumps(batch), text=True,
                                  capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HarvestStop("HARVEST_PARTIAL_ACTION",
                              "Batch helper failed; posted count unknown, do not retry") from exc
        return parse_click_batch_result(proc.stdout, proc.returncode, len(points))

    def wait(self, seconds: float) -> None:
        if not 0 <= seconds <= 5:
            raise HarvestStop("INVALID_WAIT", "Unsupported harvest wait")
        require_live_window()
        sleep(seconds)


def read_only_harvest_preflight(adapter: LiveHarvestAdapter) -> dict:
    """Real screenshot -> HarvestObservation -> FSM precheck; ALWAYS zero clicks."""
    obs = adapter.observe()
    result = {
        "platform": adapter.platform, "click_count": 0, "llm_round_trips": 0,
        "window_id": obs.window_identity[0],
        "capture_id": obs.capture_id,
        "diagnostics": adapter.last_diagnostics,
    }
    try:
        actions = prepare_harvest(obs)
    except HarvestStop as exc:
        return {"status": "stopped", "code": exc.code, "message": str(exc), **result}
    # A future calibrated observation may pass; preflight still never executes.
    return {"status": "read_only_ready", "planned_click_count": len(actions), **result}
