"""M2 live farm I/O seam. Read-only until independent UI calibration is verified.

The offline picker/special/ordinary/cycle state machines already exist. This
adapter supplies fresh real window provenance without treating a screenshot,
plot geometry, or a missing overlay detector as proof that planting is safe.
No LLM calls and no implicit window activation occur in the normal path.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
from time import monotonic_ns, sleep

from farm_capture import capture_window
from farm_harvest_live import _identity, _same_handle, require_live_window
from farm_io import WindowHandle, find_farm_window, parse_click_batch_result
from farm_plant_ordinary import OrdinaryPlantView
from farm_plant_picker import PickerView
from farm_plant_special import Cell, SpecialPlantStop


class LivePlantAdapter:
    """Real registry/capture + fail-closed M2 adapter, with gated CGEvent transport.

    execute=True does NOT grant permission to click. The current real observer
    deliberately cannot verify overlay, 24 cells, preview, picker page/icon/
    quantity or one-key mode. Only future independent, live visual calibration
    may produce an authorized observation; tests cannot be treated as that proof.
    """

    def __init__(self, platform: str, layout: dict, registry_binary: Path,
                 click_binary: Path | None = None, *, execute: bool = False):
        if platform not in ("qq", "wechat"):
            raise SpecialPlantStop("UNKNOWN_PLATFORM", "Unsupported farm platform")
        self.platform = platform
        self.layout = layout
        self.registry_binary = Path(registry_binary)
        self.click_binary = Path(click_binary) if click_binary is not None else None
        self.execute = execute
        self.last_handle: WindowHandle | None = None
        self.last_field: OrdinaryPlantView | None = None
        self.last_picker: PickerView | None = None
        self.last_diagnostics: dict = {}
        # Never set by the current uncalibrated observer.
        self.calibration_verified = False

    def _capture(self):
        # Clear stale authority before touching the live registry.
        self.last_handle = None
        self.last_field = None
        self.last_picker = None
        self.calibration_verified = False
        self.last_diagnostics = {}
        require_live_window()
        before = find_farm_window(self.platform, self.layout, self.registry_binary)
        shot = capture_window(before.frame, self.platform, self.layout)
        after = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(before, after):
            raise SpecialPlantStop("USER_INTERFERENCE", "Farm window changed during capture")
        self.last_handle = before
        return before, shot

    def observe_field(self) -> OrdinaryPlantView:
        handle, shot = self._capture()
        view = OrdinaryPlantView(
            capture_id=shot.capture_id or "",
            captured_at_ns=shot.captured_at_ns or 0,
            window_identity=_identity(handle),
            overlay="unknown",
            field_cells=None,
            preview_cells=None,
            one_key_planting=None,
        )
        self.last_field = view
        self.last_diagnostics = {
            "platform": self.platform,
            "window_id": handle.window_id,
            "frame": {
                "width": handle.frame.width, "height": handle.frame.height,
                "x": handle.frame.x, "y": handle.frame.y,
            },
            "overlay": "unknown",
            "field_cells_verified": 0,
            "preview": "unknown",
            "one_key_planting": "unknown",
            "calibration_verified": False,
            "can_authorize_clicks": False,
        }
        return view

    def observe(self, expected_slot: int, target_seed: str) -> PickerView:
        # The real picker page and badge cannot yet be read. Re-capture rather
        # than return a cached observation after a potential UI transition.
        self._capture()
        view = PickerView(page=None, target_icon_verified=None, target_quantity=None)
        self.last_picker = view
        self.last_diagnostics = {
            "platform": self.platform,
            "picker_page": "unknown",
            "target_seed": target_seed,
            "expected_slot": expected_slot,
            "target_icon_verified": None,
            "target_quantity": None,
            "can_authorize_clicks": False,
        }
        return view

    def _send_points(self, points: tuple[tuple[float, float], ...]) -> None:
        """Transport for a future calibrated observer; never authorizes itself."""
        require_live_window()
        field, handle = self.last_field, self.last_handle
        if (not self.execute or not self.calibration_verified
            or field is None or handle is None or field.overlay != "none"
            or field.field_cells is None or len(field.field_cells) != 24
            or field.preview_cells is None):
            raise SpecialPlantStop("PLANT_CALIBRATION_REQUIRED",
                                   "Live field, overlay and preview are not independently verified")
        if not field.capture_id or type(field.captured_at_ns) is not int:
            raise SpecialPlantStop("PLANT_CAPTURE_UNVERIFIED", "No live screenshot provenance")
        age = monotonic_ns() - field.captured_at_ns
        if not 0 <= age <= 2_000_000_000:
            raise SpecialPlantStop("PLANT_STALE_PRECONDITION", "Live capture is older than 2 seconds")
        if self.click_binary is None:
            raise SpecialPlantStop("CGEVENT_HELPER_MISSING", "Compiled click helper not configured")
        if not 1 <= len(points) <= 24:
            raise SpecialPlantStop("INVALID_BATCH", "Expected 1-24 verified local click points")
        frame = handle.frame
        if any(not 0 <= x < frame.width or not 0 <= y < frame.height for x, y in points):
            raise SpecialPlantStop("CLICK_OUTSIDE_WINDOW", "Invalid window-local click coordinate")
        current = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(handle, current):
            raise SpecialPlantStop("USER_INTERFERENCE", "Farm window moved before input")
        payload = {
            "window_id": handle.window_id, "pid": handle.pid,
            "owner": frame.owner, "title": frame.title,
            "frame": {"x": frame.x, "y": frame.y,
                      "width": frame.width, "height": frame.height},
            "actions": [{"x": x, "y": y, "delay_ms": 100} for x, y in points],
        }
        # Swift independently rechecks local clock, frontmost app, window
        # identity, and occlusion before *each* CGEvent. A partial send is STOP.
        try:
            proc = subprocess.run(
                [str(self.click_binary), "--execute"], input=json.dumps(payload),
                text=True, capture_output=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SpecialPlantStop("PLANT_ACTION_UNCERTAIN",
                                   "CGEvent outcome unknown; never retry") from exc
        try:
            parse_click_batch_result(proc.stdout, proc.returncode, len(points))
        except Exception as exc:
            raise SpecialPlantStop(getattr(exc, "code", "PLANT_ACTION_UNCERTAIN"),
                                   "CGEvent outcome uncertain; never retry") from exc
        finally:
            self.last_handle = None
            self.last_field = None
            self.last_picker = None
            self.calibration_verified = False

    def open_plot(self, anchor_cell: Cell) -> None:
        # Existing M0 grid is not a substitute for a live alignment check.
        raise SpecialPlantStop("PLANT_ALIGNMENT_UNVERIFIED",
                               "Live plot alignment and occupancy are not calibrated")

    def turn_pages(self, direction: int, count: int) -> None:
        raise SpecialPlantStop("PICKER_PAGE_UNKNOWN",
                               "Live page indicator and page-turn controls are not calibrated")

    def select_seed(self, slot: int) -> None:
        raise SpecialPlantStop("STATE_DRIFT",
                               "Live seed icon and quantity are not verified")

    def confirm_special(self) -> None:
        raise SpecialPlantStop("PLANT_PREVIEW_UNVERIFIED",
                               "Live 2x2 preview and confirm control are not verified")

    def wait(self, seconds: float) -> None:
        if not 0 <= seconds <= 5:
            raise SpecialPlantStop("INVALID_WAIT", "Unsupported planting wait")
        require_live_window()
        sleep(seconds)


def read_only_plant_preflight(adapter: LivePlantAdapter) -> dict:
    """One real screenshot, no UI input, never claims planting readiness."""
    view = adapter.observe_field()
    return {
        "status": "stopped", "code": "PLANT_OVERLAY",
        "message": "Overlay, 24-cell occupancy, preview and picker require live calibration",
        "platform": adapter.platform, "window_id": view.window_identity[0],
        "capture_id": view.capture_id, "diagnostics": adapter.last_diagnostics,
        "click_count": 0, "llm_round_trips": 0,
    }
