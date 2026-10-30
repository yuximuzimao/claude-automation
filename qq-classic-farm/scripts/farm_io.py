"""Read-only registry/capture/probe composition for M1.

Window registry is a *compiled* helper. No Swift interpreter or model call
is involved in this path. Nothing here sends mouse events.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess

from farm_capture import capture_window
from farm_field import FieldStop, probe_field_translation
from farm_geometry import GeometryStop, WindowFrame, validate_farm_window
from farm_harvest import HarvestStop
from farm_vision import probe_harvest


class IOStop(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WindowHandle:
    window_id: int
    pid: int
    frame: WindowFrame


def parse_click_batch_result(stdout: str, returncode: int, expected: int) -> int:
    """Decode CGEvent helper protocol; validation-only is NEVER execution.

    The helper's count means events posted, not game actions confirmed. On
    failure preserve its known partial count for recovery; never replay.
    """
    if type(expected) is not int or not 1 <= expected <= 24:
        raise HarvestStop("INVALID_BATCH", "Invalid expected action count")
    try:
        payload = json.loads(stdout)
        if not isinstance(payload, dict):
            raise ValueError("Expected helper JSON object")
        count = payload["click_count"]
        if type(count) is not int or not 0 <= count <= expected:
            raise ValueError("Invalid helper click count")
    except (ValueError, TypeError, KeyError) as exc:
        raise HarvestStop("HARVEST_PARTIAL_ACTION",
                          "Malformed helper response; posted count unknown") from exc
    if returncode != 0:
        code = payload.get("code")
        if not isinstance(code, str) or not code:
            code = "HARVEST_PARTIAL_ACTION"
        raise HarvestStop(code, "Helper stopped; actions may be partially sent",
                          clicks_sent=count)
    if payload.get("status") != "clicks_sent_unverified" or count != expected:
        raise HarvestStop("HARVEST_PARTIAL_ACTION",
                          "Helper did not confirm the full execution batch",
                          clicks_sent=count)
    return count


def find_farm_window(platform: str, layout: dict, registry_binary: Path) -> WindowHandle:
    if platform not in ("qq", "wechat"):
        raise IOStop("UNKNOWN_PLATFORM", "Unsupported platform")
    try:
        result = subprocess.run(
            [str(registry_binary), "--platform", platform],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise IOStop("WINDOW_REGISTRY_FAILED", str(exc)) from exc
    if result.returncode != 0:
        raise IOStop("WINDOW_REGISTRY_FAILED", result.stderr.strip() or "Registry failed")
    try:
        payload = json.loads(result.stdout)
        if payload["platform"] != platform:
            raise ValueError("Wrong platform in registry response")
        matches = [w for w in payload["windows"] if w["title"] == "QQ经典农场"]
        if len(matches) != 1:
            raise IOStop("WINDOW_NOT_FOUND", f"Expected one farm window, found {len(matches)}")
        w = matches[0]
        frame = WindowFrame(w["owner"], w["title"], w["x"], w["y"], w["width"], w["height"])
        validate_farm_window(frame, platform, layout)
        if type(w["window_id"]) is not int or w["window_id"] <= 0:
            raise ValueError("Invalid window ID")
        if type(w["pid"]) is not int or w["pid"] <= 0:
            raise ValueError("Invalid process ID")
        return WindowHandle(w["window_id"], w["pid"], frame)
    except (IOStop, GeometryStop):
        raise
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise IOStop("WINDOW_REGISTRY_FAILED", str(exc)) from exc


def probe_window_harvest(platform: str, layout: dict, anchors: dict,
                         registry_binary: Path) -> dict:
    handle = find_farm_window(platform, layout, registry_binary)
    capture = capture_window(handle.frame, platform, layout)
    probe = probe_harvest(capture, anchors, platform, layout)
    try:
        field_alignment = probe_field_translation(capture, platform, layout)
    except FieldStop as exc:
        field_alignment = {"status": "unavailable", "code": exc.code,
                           "can_authorize_clicks": False}
    return {
        "status": "read_only_probe",
        "platform": platform,
        "window_id": handle.window_id,
        "pid": handle.pid,
        "frame": {
            "owner": handle.frame.owner, "title": handle.frame.title,
            "x": handle.frame.x, "y": handle.frame.y,
            "width": handle.frame.width, "height": handle.frame.height,
        },
        "harvest": probe,
        "field_alignment": field_alignment,
        "click_count": 0,
        "llm_round_trips": 0,
    }
