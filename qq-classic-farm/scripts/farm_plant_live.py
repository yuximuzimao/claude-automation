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
from farm_picker_vision import observe_picker, picker_arrow_verified
from farm_qq_clean import check_qq_empty_field, observe_qq_preview_cells
from farm_plant_special import Cell, SpecialPlantStop


QQ_CONFIRMED_ORDINARY_SEEDS = frozenset({"天山红枫种子"})


class LivePlantAdapter:
    """Real registry/capture + fail-closed M2 adapter, with gated CGEvent transport.

    execute=True does NOT grant permission to plant. QQ picker page/icon/badge,
    a bounded vertical offset and the unchecked one-key control have limited
    real calibration; field occupancy, preview, overlay and enabled one-key
    mode remain unknown. A QQ all-empty postcondition is now observable, but
    it cannot authorize clicks while overlay/preview/inventory are unknown.
    """

    def __init__(self, platform: str, layout: dict, registry_binary: Path,
                 click_binary: Path | None = None, *, execute: bool = False,
                 ocr_binary: Path | None = None):
        if platform not in ("qq", "wechat"):
            raise SpecialPlantStop("UNKNOWN_PLATFORM", "Unsupported farm platform")
        self.platform = platform
        self.layout = layout
        self.registry_binary = Path(registry_binary)
        self.click_binary = Path(click_binary) if click_binary is not None else None
        self.execute = execute
        self.ocr_binary = Path(ocr_binary) if ocr_binary is not None else None
        self.last_handle: WindowHandle | None = None
        self.last_field: OrdinaryPlantView | None = None
        self.last_field_capture = None
        self.last_picker: PickerView | None = None
        self.last_picker_expected_slot: int | None = None
        self.last_picker_target_seed: str | None = None
        self.last_picker_capture = None
        self.last_picker_total: int | None = None
        self.last_picker_y_shift: int | None = None
        self.last_diagnostics: dict = {}
        # Only a verified open_plot may arm a later picker seed selection.
        # This survives picker captures/page turns but not a new field probe.
        self.pending_picker_origin: tuple | None = None
        self.pending_empty_count: int | None = None
        self.pending_ordinary_seed: str | None = None
        # Never set by the current uncalibrated observer.
        self.calibration_verified = False

    def require_empty_field(self) -> bool:
        """Read-only V2 phase-start gate; never sends UI input."""
        handle, shot = self._capture()
        if self.platform != "qq":
            raise SpecialPlantStop("EMPTY_CHECK_UNSUPPORTED",
                                   "V2 live EMPTY check currently calibrated only for QQ")
        check = check_qq_empty_field(shot, self.layout)
        self.last_diagnostics = {
            "platform": self.platform,
            "window_id": handle.window_id,
            "empty_check_status": check.status,
            "empty_check_reason": check.reason,
            "empty_cells": len(check.empty_cells),
            "occupied_cells": len(check.occupied_cells),
            "unknown_cells": len(check.unknown_cells),
            "can_authorize_clicks": False,
        }
        if check.status == "UNKNOWN":
            raise SpecialPlantStop("PLANT_FIELD_UNKNOWN",
                                   "QQ field cannot be classified as EMPTY/NOT_EMPTY")
        return check.status == "EMPTY"

    def verify_cells_occupied(self, cells: frozenset[Cell]) -> bool | None:
        """Read-only targeted ROI postcondition for Runner-planned cells."""
        if (not isinstance(cells, frozenset) or not cells
            or any(type(cell) is not tuple or len(cell) != 2
                   or any(type(v) is not int for v in cell)
                   or not (0 <= cell[0] < 6 and 0 <= cell[1] < 4)
                   for cell in cells)):
            raise SpecialPlantStop("INVALID_PLOT_SET", "Invalid planned cell set")
        handle, shot = self._capture()
        if self.platform != "qq":
            return None
        check = check_qq_empty_field(shot, self.layout)
        occupied = frozenset(check.occupied_cells)
        unknown = frozenset(check.unknown_cells)
        self.last_diagnostics = {
            "platform": self.platform,
            "window_id": handle.window_id,
            "empty_check_status": check.status,
            "verify_cells": [list(cell) for cell in sorted(cells)],
            "occupied_cells": [list(cell) for cell in sorted(occupied)],
            "unknown_cells": [list(cell) for cell in sorted(unknown)],
            "can_authorize_clicks": False,
        }
        if cells & unknown:
            return None
        return cells.issubset(occupied)

    def _capture(self):
        # Clear stale authority before touching the live registry.
        self.last_handle = None
        self.last_field = None
        self.last_field_capture = None
        self.last_picker = None
        self.last_picker_expected_slot = None
        self.last_picker_target_seed = None
        self.last_picker_capture = None
        self.last_picker_total = None
        self.last_picker_y_shift = None
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
        self.pending_picker_origin = None
        self.pending_empty_count = None
        self.pending_ordinary_seed = None
        handle, shot = self._capture()
        empty_check = (check_qq_empty_field(shot, self.layout)
                       if self.platform == "qq" else None)
        preview_cells = (observe_qq_preview_cells(shot, self.layout)
                         if self.platform == "qq" else None)
        view = OrdinaryPlantView(
            capture_id=shot.capture_id or "",
            captured_at_ns=shot.captured_at_ns or 0,
            window_identity=_identity(handle),
            overlay="unknown",
            preview_cells=preview_cells,
            one_key_planting=None,
        )
        self.last_field = view
        self.last_field_capture = shot
        self.last_diagnostics = {
            "platform": self.platform,
            "window_id": handle.window_id,
            "frame": {
                "width": handle.frame.width, "height": handle.frame.height,
                "x": handle.frame.x, "y": handle.frame.y,
            },
            "overlay": "unknown",
            "empty_check_status": empty_check.status if empty_check is not None else "UNKNOWN",
            "empty_check_reason": empty_check.reason if empty_check is not None else "UNSUPPORTED_PLATFORM",
            "empty_cells": len(empty_check.empty_cells) if empty_check is not None else 0,
            "occupied_cells": len(empty_check.occupied_cells) if empty_check is not None else 0,
            "unknown_cells": len(empty_check.unknown_cells) if empty_check is not None else 24,
            "clean_field_verified": empty_check is not None and empty_check.status == "EMPTY",
            "preview_cells": ([list(cell) for cell in sorted(preview_cells)]
                              if isinstance(preview_cells, frozenset) else None),
            "preview": ("none" if preview_cells == frozenset()
                        else "verified" if isinstance(preview_cells, frozenset)
                        else "unknown"),
            "one_key_planting": "unknown",
            "calibration_verified": False,
            "can_authorize_clicks": False,
        }
        return view

    def observe(self, expected_slot: int, target_seed: str) -> PickerView:
        # Fresh real screenshot; no historical page/slot or quantity is trusted.
        handle, shot = self._capture()
        if (self.pending_picker_origin is not None
            and _identity(handle) != self.pending_picker_origin):
            self.pending_picker_origin = None
            self.pending_empty_count = None
            self.pending_ordinary_seed = None
        evidence = observe_picker(shot, self.platform, expected_slot,
                                  target_seed, self.ocr_binary)
        if evidence.get("one_key_confirmation_pending") is True:
            raise SpecialPlantStop(
                "ONE_KEY_CONFIRMATION_PENDING",
                "QQ one-key enable requires confirmation; do not infer ON or select a seed",
            )
        view = PickerView(page=evidence["page"],
                          target_icon_verified=evidence["target_icon_verified"],
                          target_quantity=evidence["target_quantity"],
                          one_key_planting=evidence["one_key_planting"])
        self.last_picker = view
        self.last_picker_expected_slot = expected_slot
        self.last_picker_target_seed = target_seed
        self.last_picker_capture = shot
        self.last_picker_total = evidence["total_pages"]
        self.last_picker_y_shift = evidence["picker_y_shift"]
        self.last_diagnostics = {
            "platform": self.platform,
            "picker_page": view.page,
            "picker_total_pages": evidence["total_pages"],
            "picker_y_shift": evidence["picker_y_shift"],
            "target_seed": target_seed,
            "expected_slot": expected_slot,
            "target_icon_verified": view.target_icon_verified,
            "target_quantity": view.target_quantity,
            "one_key_planting": view.one_key_planting,
            "icon_score": evidence["icon_score"],
            "can_authorize_planting": False,
            "can_authorize_clicks": False,
        }
        return view

    def open_plot(self, anchor_cell: Cell) -> None:
        """V2 placeholder until the fixed-grid empty checker authorizes a plot.

        V1 used full-field semantic proof plus runtime soil registration here.
        That path is retired. V2-1 will provide a platform-specific EMPTY check
        and calibrated fixed grid before this method sends any input.
        """
        if (type(anchor_cell) is not tuple or len(anchor_cell) != 2
            or any(type(v) is not int for v in anchor_cell)
            or not (0 <= anchor_cell[0] < 6 and 0 <= anchor_cell[1] < 4)):
            raise SpecialPlantStop("INVALID_PLOT", "Invalid plot cell")
        raise SpecialPlantStop(
            "PLANT_V2_EMPTY_CHECK_REQUIRED",
            "Fixed-grid V2 empty-field calibration is required before opening a plot",
        )

    def turn_pages(self, direction: int, count: int) -> None:
        """Only QQ verified bounded arrow navigation; never selects a seed."""
        require_live_window()
        view, shot, handle = self.last_picker, self.last_picker_capture, self.last_handle
        if not self.execute or self.click_binary is None:
            raise SpecialPlantStop("PICKER_EXECUTION_DISABLED", "Real picker navigation not enabled")
        if self.platform != "qq" or direction not in (-1, 1):
            raise SpecialPlantStop("PICKER_DIRECTION_UNVERIFIED",
                                   "Only QQ verified arrow navigation is available")
        if (view is None or shot is None or handle is None
            or type(view.page) is not int or type(self.last_picker_total) is not int
            or type(self.last_picker_y_shift) is not int
            or not -100 <= self.last_picker_y_shift <= 100
            or type(count) is not int or not 1 <= count <= 7
            or not 1 <= view.page + direction * count <= self.last_picker_total):
            raise SpecialPlantStop("PICKER_PAGE_UNKNOWN", "Cannot safely bound picker turns")
        if not 0 <= monotonic_ns() - shot.captured_at_ns <= 2_000_000_000:
            raise SpecialPlantStop("PICKER_STALE_PRECONDITION", "Picker capture older than 2 seconds")
        if not picker_arrow_verified(shot, direction, self.last_picker_y_shift):
            raise SpecialPlantStop("PICKER_ARROW_UNVERIFIED", "Requested arrow not visually confirmed")
        current = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(handle, current):
            raise SpecialPlantStop("USER_INTERFERENCE", "Farm window changed before navigation")
        f = handle.frame
        batch = {
            "window_id": handle.window_id, "pid": handle.pid,
            "owner": f.owner, "title": f.title,
            "frame": {"x": f.x, "y": f.y, "width": f.width, "height": f.height},
            "actions": [{"x": (569 if direction == 1 else 31) * f.width / 603,
                         "y": (771 + self.last_picker_y_shift) * f.height / 1111,
                         "delay_ms": 450} for _ in range(count)],
        }
        try:
            result = subprocess.run(
                [str(self.click_binary), "--execute"], input=json.dumps(batch),
                text=True, capture_output=True, timeout=30, check=False,
            )
            parse_click_batch_result(result.stdout, result.returncode, count)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise SpecialPlantStop("PICKER_NAVIGATION_UNCERTAIN",
                                   "Page turns may be partial; do not retry",
                                   action_may_have_been_sent=True) from exc
        finally:
            # A sent batch can never reuse the pre-navigation screenshot.
            self.last_handle = None
            self.last_picker = None
            self.last_picker_expected_slot = None
            self.last_picker_target_seed = None
            self.last_picker_capture = None
            self.last_picker_total = None
            self.last_picker_y_shift = None

    def arm_ordinary_selection(self, count: int, seed: str) -> None:
        """Bind verified ordinary transaction intent to this exact picker target."""
        self.pending_ordinary_seed = None
        if (type(count) is not int or count != self.pending_empty_count
            or self.platform != "qq" or not isinstance(seed, str) or not seed
            or seed not in QQ_CONFIRMED_ORDINARY_SEEDS
            or seed != self.last_picker_target_seed
            or self.last_picker is None or self.last_picker.one_key_planting is not True
            or self.last_picker.target_icon_verified is not True
            or type(self.last_picker.target_quantity) is not int
            or self.last_picker.target_quantity < count
            or self.last_handle is None
            or self.pending_picker_origin != _identity(self.last_handle)):
            raise SpecialPlantStop("PLANT_SELECTION_UNVERIFIED",
                                   "Ordinary plan must match verified picker and all empty plots")
        self.pending_ordinary_seed = seed

    def select_seed(self, slot: int) -> None:
        """Select an ordinary seed only from a verified ON-mode picker session.

        Selecting in ON mode immediately plants every empty plot. An OFF-mode
        picker is deliberately not supported here: special preview and
        single-plot semantics have not been independently calibrated.
        """
        require_live_window()
        view, shot, handle = self.last_picker, self.last_picker_capture, self.last_handle
        empty_count = self.pending_empty_count
        if (not self.execute or self.click_binary is None or self.platform != "qq"
            or view is None or shot is None or handle is None
            or self.pending_picker_origin != _identity(handle)
            or type(empty_count) is not int or not 1 <= empty_count <= 24
            or type(slot) is not int or not 1 <= slot <= 5
            or slot != self.last_picker_expected_slot
            or not self.pending_ordinary_seed
            or self.pending_ordinary_seed != self.last_picker_target_seed
            or type(self.last_picker_y_shift) is not int
            or not -100 <= self.last_picker_y_shift <= 100
            or type(view.page) is not int or view.target_icon_verified is not True
            or type(view.target_quantity) is not int
            or view.target_quantity < empty_count
            or view.one_key_planting is not True):
            raise SpecialPlantStop("PLANT_SELECTION_UNVERIFIED",
                                   "Verified ON picker, seed, stock and originating empty plots required")
        if not 0 <= monotonic_ns() - shot.captured_at_ns <= 2_000_000_000:
            raise SpecialPlantStop("PICKER_STALE_PRECONDITION", "Picker screenshot older than 2 seconds")
        current = find_farm_window(self.platform, self.layout, self.registry_binary)
        if not _same_handle(handle, current):
            raise SpecialPlantStop("USER_INTERFERENCE", "Farm window changed before seed selection")
        from farm_picker_vision import QQ_SLOT_X
        f = handle.frame
        batch = {
            "window_id": handle.window_id, "pid": handle.pid,
            "owner": f.owner, "title": f.title,
            "frame": {"x": f.x, "y": f.y, "width": f.width, "height": f.height},
            "actions": [{"x": QQ_SLOT_X[slot - 1] * f.width / 603,
                         "y": (785 + self.last_picker_y_shift) * f.height / 1111,
                         "delay_ms": 100}],
        }
        # Consume authority before the irreversible action, even on timeout.
        self.pending_picker_origin = None
        self.pending_empty_count = None
        self.pending_ordinary_seed = None
        self.last_picker = None
        self.last_picker_expected_slot = None
        self.last_picker_target_seed = None
        self.last_picker_capture = None
        self.last_handle = None
        try:
            result = subprocess.run(
                [str(self.click_binary), "--execute"], input=json.dumps(batch),
                text=True, capture_output=True, timeout=30, check=False,
            )
            parse_click_batch_result(result.stdout, result.returncode, 1)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise SpecialPlantStop("PLANT_ACTION_UNCERTAIN",
                                   "Seed selection may have planted; never retry",
                                   action_may_have_been_sent=True) from exc

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
        "message": ("QQ 24-cell clean evidence is read-only; overlay, preview and "
                    "planting controls still require calibration"),
        "platform": adapter.platform, "window_id": view.window_identity[0],
        "capture_id": view.capture_id, "diagnostics": adapter.last_diagnostics,
        "click_count": 0, "llm_round_trips": 0,
    }
