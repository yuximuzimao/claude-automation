"""M2 one-special-seed local transaction, with injectable UI I/O.

This is NOT a live click entry point. The adapter must independently verify
window identity, overlay, 2x2 preview and all 24 field cells from local
captures; it must guard Mac operation times before any real input.
Planner chooses seed/placement. Runner only validates and executes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from time import monotonic_ns, perf_counter
from typing import Callable, Mapping, Protocol, Sequence

from farm_plant_picker import PickerAdapter, PickerStop, prepare_picker_target
from seed_order import PickerStateError, compute_picker_position, consume_confirmed

Cell = tuple[int, int]
ALL_CELLS = frozenset((u, v) for u in range(6) for v in range(4))


class SpecialPlantStop(ValueError):
    def __init__(self, code: str, message: str, *, action_may_have_been_sent: bool = False):
        super().__init__(message)
        self.code = code
        self.action_may_have_been_sent = action_may_have_been_sent


@dataclass(frozen=True)
class SpecialPlantView:
    capture_id: str
    captured_at_ns: int
    # (window_id, pid, owner, title, x, y) as with M1.
    window_identity: tuple
    overlay: str
    # All 24 cells must be independently classified before/after planting.
    field_cells: Mapping[Cell, bool] | None
    # Empty set = verified absent, None = unknown; never equate the two.
    preview_cells: frozenset[Cell] | None


class SpecialPlantAdapter(PickerAdapter, Protocol):
    def observe_field(self) -> SpecialPlantView: ...
    def open_plot(self, anchor_cell: Cell) -> None: ...
    def select_seed(self, slot: int) -> None: ...
    def confirm_special(self) -> None: ...


def _check_view(view: SpecialPlantView, *, field_required: bool) -> None:
    if not isinstance(view, SpecialPlantView):
        raise SpecialPlantStop("PLANT_OBSERVATION_UNAVAILABLE", "Invalid local field observation")
    identity = view.window_identity
    if (not isinstance(identity, tuple) or len(identity) != 6
        or type(identity[0]) is not int or identity[0] <= 0
        or type(identity[1]) is not int or identity[1] <= 0
        or not isinstance(identity[2], str) or not identity[2]
        or identity[3] != "QQ经典农场"
        or any(type(x) not in (int, float) or not isfinite(x) for x in identity[4:])):
        raise SpecialPlantStop("PLANT_WINDOW_UNVERIFIED", "Missing verified farm window identity")
    if (not isinstance(view.capture_id, str) or not view.capture_id
        or type(view.captured_at_ns) is not int or view.captured_at_ns <= 0):
        raise SpecialPlantStop("PLANT_CAPTURE_UNVERIFIED", "Missing trusted capture provenance")
    if view.overlay != "none":
        raise SpecialPlantStop("PLANT_OVERLAY", "Unknown or active overlay; do not guess dismissal")
    if view.preview_cells is not None and (
        not isinstance(view.preview_cells, frozenset)
        or not view.preview_cells.issubset(ALL_CELLS)):
        raise SpecialPlantStop("PLANT_PREVIEW_UNVERIFIED", "Malformed 2x2 preview evidence")
    if field_required and (
        view.field_cells is None
        or not isinstance(view.field_cells, Mapping)
        or set(view.field_cells) != ALL_CELLS
        or any(type(v) is not bool for v in view.field_cells.values())):
        raise SpecialPlantStop("PLANT_FIELD_UNVERIFIED", "Missing independent 24-cell classification")


def _fresh(previous: SpecialPlantView, current: SpecialPlantView, after_action_ns: int) -> None:
    try:
        _check_view(current, field_required=False)
    except SpecialPlantStop as exc:
        raise SpecialPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc
    if current.window_identity != previous.window_identity:
        raise SpecialPlantStop("USER_INTERFERENCE", "Farm window identity/position changed",
                               action_may_have_been_sent=True)
    if (current.capture_id == previous.capture_id
        or current.captured_at_ns <= previous.captured_at_ns
        or current.captured_at_ns <= after_action_ns):
        raise SpecialPlantStop("PLANT_STALE_OBSERVATION",
                               "Capture predates completed UI action",
                               action_may_have_been_sent=True)


def _observe(adapter: SpecialPlantAdapter, *, action_sent: bool) -> SpecialPlantView:
    try:
        return adapter.observe_field()
    except Exception as exc:
        raise SpecialPlantStop("PLANT_OBSERVATION_UNAVAILABLE",
                               "Cannot obtain trusted local field observation",
                               action_may_have_been_sent=action_sent) from exc


def _act(call: Callable, *args) -> None:
    try:
        call(*args)
    except Exception as exc:
        raise SpecialPlantStop("PLANT_ACTION_UNCERTAIN",
                               "UI action may have been sent; never retry blindly",
                               action_may_have_been_sent=True) from exc


def _after_action_clock(clock_ns: Callable[[], int]) -> int:
    try:
        value = clock_ns()
    except Exception as exc:
        raise SpecialPlantStop("PLANT_POSTCONDITION_UNAVAILABLE",
                               "Monotonic clock failed after UI action",
                               action_may_have_been_sent=True) from exc
    if type(value) is not int or value <= 0:
        raise SpecialPlantStop("PLANT_POSTCONDITION_UNAVAILABLE",
                               "Invalid monotonic clock after UI action",
                               action_may_have_been_sent=True)
    return value


def plant_one_special(
    adapter: SpecialPlantAdapter, *, platform: str, seed: str, placement: str,
    stable_order: Sequence[str], quantities: Mapping[str, int], layout: dict,
    clock_ns: Callable[[], int] = monotonic_ns,
) -> dict:
    """Verify empty target -> picker -> exact preview -> confirm -> occupied target.

    On any uncertainty STOP. Only a verified postcondition produces an updated
    *copy* of quantities; the caller persists it transactionally afterward.
    """
    started = perf_counter()
    try:
        candidates = layout["platforms"][platform]["safe_special_2x2"]
        matches = [x for x in candidates if x["id"] == placement]
        if len(matches) != 1:
            raise ValueError("Unknown placement")
        item = matches[0]
        target = frozenset(tuple(c) for c in item["cells"])
        anchor = tuple(item["anchor_cell"])
        if (len(target) != 4 or not target.issubset(ALL_CELLS)
            or anchor not in target
            or len({u for u, _ in target}) != 2
            or len({v for _, v in target}) != 2
            or max(u for u, _ in target) - min(u for u, _ in target) != 1
            or max(v for _, v in target) - min(v for _, v in target) != 1):
            raise ValueError("Invalid 2x2 geometry")
    except (KeyError, TypeError, ValueError) as exc:
        raise SpecialPlantStop("INVALID_PLACEMENT", str(exc)) from exc

    # Fail on stale/insufficient inventory BEFORE opening a live picker.
    try:
        compute_picker_position(platform, seed, stable_order, quantities)
        if type(quantities.get(seed, 0)) is not int or quantities[seed] < 1:
            raise PickerStateError("INSUFFICIENT_INVENTORY", "No special seed stock")
    except PickerStateError as exc:
        raise SpecialPlantStop(exc.code, str(exc)) from exc

    before = _observe(adapter, action_sent=False)
    _check_view(before, field_required=True)
    if before.preview_cells != frozenset():
        raise SpecialPlantStop("PLANT_PREVIEW_UNVERIFIED", "A preview is already active or unknown")
    if any(before.field_cells[cell] for cell in target):
        raise SpecialPlantStop("PLANT_TARGET_OCCUPIED", "Target 2x2 is not independently empty")

    _act(adapter.open_plot, anchor)
    try:
        picker = prepare_picker_target(adapter, platform=platform, seed=seed, needed=1,
                                       stable_order=stable_order, quantities=quantities)
    except (PickerStop, PickerStateError) as exc:
        raise SpecialPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc
    _act(adapter.select_seed, picker["position"]["slot"])
    selected_at = _after_action_clock(clock_ns)
    preview = _observe(adapter, action_sent=True)
    _fresh(before, preview, selected_at)
    if preview.preview_cells != target:
        raise SpecialPlantStop("PLANT_PREVIEW_MISMATCH",
                               "Preview must exactly cover planned 2x2; do not confirm",
                               action_may_have_been_sent=True)

    _act(adapter.confirm_special)
    confirmed_at = _after_action_clock(clock_ns)
    after = _observe(adapter, action_sent=True)
    _fresh(preview, after, confirmed_at)
    try:
        _check_view(after, field_required=True)
    except SpecialPlantStop as exc:
        raise SpecialPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc
    if after.preview_cells != frozenset():
        raise SpecialPlantStop("PLANT_CONFIRM_UNVERIFIED",
                               "Preview not independently confirmed closed",
                               action_may_have_been_sent=True)
    if any(after.field_cells[cell] is not (before.field_cells[cell] or cell in target)
           for cell in ALL_CELLS):
        raise SpecialPlantStop("PLANT_POSTCONDITION_MISMATCH",
                               "Target not occupied or other cells changed unexpectedly",
                               action_may_have_been_sent=True)
    updated = consume_confirmed(stable_order, quantities, seed, 1)
    return {
        "status": "special_plant_verified", "platform": platform, "seed": seed,
        "placement": placement, "picker": picker["position"],
        "quantities_after": updated, "persisted": False,
        "llm_round_trips": 0, "phase_duration_ms": round((perf_counter()-started)*1000, 2),
    }
