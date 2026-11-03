"""V2 special-crop transaction.

The Runner owns expected state. It does not reconstruct a 24-cell semantic map
after each click. One phase starts from a separately verified EMPTY field,
tracks confirmed placements locally, and validates only the UI/ROIs expected
to change for this transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from time import monotonic_ns, perf_counter
from typing import Callable, Mapping, Protocol, Sequence

from farm_plant_picker import PickerAdapter, PickerStop, PickerView, prepare_picker_target
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
    # (window_id, pid, owner, title, x, y)
    window_identity: tuple
    overlay: str
    # Empty set = verified no preview. None = unknown.
    preview_cells: frozenset[Cell] | None


class SpecialPlantAdapter(PickerAdapter, Protocol):
    def observe_field(self) -> SpecialPlantView: ...
    def open_plot(self, anchor_cell: Cell) -> None: ...
    def select_seed(self, slot: int) -> None: ...
    def confirm_special(self) -> None: ...
    def wait(self, seconds: float) -> None: ...
    def verify_cells_occupied(self, cells: frozenset[Cell]) -> bool | None: ...


def _check_view(view: SpecialPlantView) -> None:
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
        raise SpecialPlantStop("PLANT_PREVIEW_UNVERIFIED", "Malformed preview evidence")


def _fresh(previous: SpecialPlantView, current: SpecialPlantView, after_action_ns: int) -> None:
    try:
        _check_view(current)
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
        view = adapter.observe_field()
    except Exception as exc:
        raise SpecialPlantStop("PLANT_OBSERVATION_UNAVAILABLE",
                               "Cannot obtain trusted local field observation",
                               action_may_have_been_sent=action_sent) from exc
    if not isinstance(view, SpecialPlantView):
        raise SpecialPlantStop("PLANT_OBSERVATION_UNAVAILABLE",
                               "Invalid local field observation",
                               action_may_have_been_sent=action_sent)
    return view


def _act(call: Callable, *args) -> None:
    try:
        call(*args)
    except SpecialPlantStop:
        raise
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


def _placement(platform: str, placement: str, layout: dict) -> tuple[Cell, frozenset[Cell]]:
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
        return anchor, target
    except (KeyError, TypeError, ValueError) as exc:
        raise SpecialPlantStop("INVALID_PLACEMENT", str(exc)) from exc


def plant_one_special(
    adapter: SpecialPlantAdapter, *, platform: str, seed: str, placement: str,
    known_occupied: frozenset[Cell], stable_order: Sequence[str],
    quantities: Mapping[str, int], layout: dict,
    clock_ns: Callable[[], int] = monotonic_ns,
) -> dict:
    """Plant one planned 2x2 crop and return the Runner's updated known state."""
    started = perf_counter()
    anchor, target = _placement(platform, placement, layout)

    if (not isinstance(known_occupied, frozenset)
        or not known_occupied.issubset(ALL_CELLS)):
        raise SpecialPlantStop("PLANT_STATE_INVALID", "Invalid Runner occupied-cell state")
    if target & known_occupied:
        raise SpecialPlantStop("PLANT_TARGET_OCCUPIED", "Planned 2x2 overlaps known placement")

    try:
        compute_picker_position(platform, seed, stable_order, quantities)
        if type(quantities.get(seed, 0)) is not int or quantities[seed] < 1:
            raise PickerStateError("INSUFFICIENT_INVENTORY", "No special seed stock")
    except PickerStateError as exc:
        raise SpecialPlantStop(exc.code, str(exc)) from exc

    before = _observe(adapter, action_sent=False)
    _check_view(before)
    if before.preview_cells != frozenset():
        raise SpecialPlantStop("PLANT_PREVIEW_UNVERIFIED",
                               "A preview is already active or unknown")

    _act(adapter.open_plot, anchor)
    try:
        picker = prepare_picker_target(
            adapter, platform=platform, seed=seed, needed=1,
            stable_order=stable_order, quantities=quantities,
        )
    except (PickerStop, PickerStateError) as exc:
        raise SpecialPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc

    # Special crops require an explicitly verified OFF one-key mode. A live
    # adapter may safely turn a verified ON checkbox OFF and then re-observe
    # the same target; absence/unknown state never counts as OFF.
    if picker.get("one_key_planting") is not False:
        ensure_mode = getattr(adapter, "ensure_one_key_mode", None)
        if ensure_mode is None:
            raise SpecialPlantStop(
                "ONE_KEY_NOT_VERIFIED",
                "Special planting requires a verified OFF one-key mode",
                action_may_have_been_sent=True,
            )
        try:
            refreshed = ensure_mode(False)
        except SpecialPlantStop:
            raise
        except Exception as exc:
            raise SpecialPlantStop(
                "ONE_KEY_ACTION_UNCERTAIN",
                "Cannot verify one-key OFF after picker action",
                action_may_have_been_sent=True,
            ) from exc
        if (not isinstance(refreshed, PickerView)
            or refreshed.one_key_planting is not False
            or refreshed.target_icon_verified is not True
            or type(refreshed.target_quantity) is not int
            or refreshed.target_quantity < 1
            or refreshed.page != picker["position"]["page"]):
            raise SpecialPlantStop(
                "ONE_KEY_NOT_VERIFIED",
                "Picker target must remain verified after switching one-key OFF",
                action_may_have_been_sent=True,
            )
        picker["one_key_planting"] = False
        picker["visible_quantity"] = refreshed.target_quantity

    # Critical invariant: only click the slot just verified for this exact seed.
    # Live adapters additionally bind this picker session to special/OFF mode.
    arm_special = getattr(adapter, "arm_special_selection", None)
    if arm_special is not None:
        _act(arm_special, seed)
    _act(adapter.select_seed, picker["position"]["slot"])
    selected_at = _after_action_clock(clock_ns)
    preview = _observe(adapter, action_sent=True)
    _fresh(before, preview, selected_at)
    if preview.preview_cells != target:
        raise SpecialPlantStop("PLANT_PREVIEW_MISMATCH",
                               "Preview must exactly cover planned 2x2; do not confirm",
                               action_may_have_been_sent=True)

    _act(adapter.confirm_special)
    _act(adapter.wait, 0.5)
    confirmed_at = _after_action_clock(clock_ns)
    after = _observe(adapter, action_sent=True)
    _fresh(preview, after, confirmed_at)
    if after.preview_cells != frozenset():
        raise SpecialPlantStop("PLANT_CONFIRM_UNVERIFIED",
                               "Preview did not close after confirmation",
                               action_may_have_been_sent=True)
    try:
        occupied_verified = adapter.verify_cells_occupied(target)
    except Exception as exc:
        raise SpecialPlantStop("PLANT_POSTCONDITION_UNAVAILABLE",
                               "Cannot verify planned 2x2 target ROIs",
                               action_may_have_been_sent=True) from exc
    if occupied_verified is not True:
        raise SpecialPlantStop("PLANT_POSTCONDITION_MISMATCH",
                               "Planned 2x2 target ROIs are not confirmed occupied",
                               action_may_have_been_sent=True)

    occupied_after = frozenset(known_occupied | target)
    updated = consume_confirmed(stable_order, quantities, seed, 1)
    return {
        "status": "special_plant_verified", "platform": platform, "seed": seed,
        "placement": placement, "picker": picker["position"],
        "occupied_after": [list(cell) for cell in sorted(occupied_after)],
        "quantities_after": updated, "persisted": False,
        "llm_round_trips": 0,
        "phase_duration_ms": round((perf_counter() - started) * 1000, 2),
    }
