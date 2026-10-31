"""M2 ordinary one-key planting transaction; injectable local I/O, no live entry point.

Planner chooses seed/count. The runner verifies one-key mode, exactly that
many independently empty cells, the picker target, and the complete 24-cell
postcondition before returning a *non-persisted* inventory copy. It never
chooses substitute seeds or tries to fill missed plots.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns, perf_counter
from typing import Callable, Mapping, Protocol, Sequence

from farm_plant_picker import PickerAdapter, PickerStop, prepare_picker_target
from farm_plant_special import (
    ALL_CELLS, Cell, SpecialPlantStop, SpecialPlantView,
    _act, _after_action_clock, _check_view, _fresh, _observe,
)
from seed_order import PickerStateError, compute_picker_position, consume_confirmed


class OrdinaryPlantStop(SpecialPlantStop):
    pass


@dataclass(frozen=True)
class OrdinaryPlantView(SpecialPlantView):
    # Verified from local UI. None is unknown, never interpreted as enabled.
    one_key_planting: bool | None = None


class OrdinaryPlantAdapter(PickerAdapter, Protocol):
    def observe_field(self) -> OrdinaryPlantView: ...
    def open_plot(self, anchor_cell: Cell) -> None: ...
    def select_seed(self, slot: int) -> None: ...
    def wait(self, seconds: float) -> None: ...


def plant_ordinary_one_key(
    adapter: OrdinaryPlantAdapter, *, platform: str, seed: str, count: int,
    stable_order: Sequence[str], quantities: Mapping[str, int],
    clock_ns: Callable[[], int] = monotonic_ns,
) -> dict:
    """One-key ordinary seed selection fills exactly the verified empty plots.

    No live action is permitted until the adapter independently proves the
    target window, current plot occupancy and enabled one-key mode. The
    adapter itself must enforce Mac local blackout times, focus and occlusion.
    """
    started = perf_counter()
    if type(count) is not int or count <= 0 or count > len(ALL_CELLS):
        raise OrdinaryPlantStop("INVALID_PLANT_COUNT", "Invalid ordinary plot count")
    try:
        compute_picker_position(platform, seed, stable_order, quantities)
        if type(quantities.get(seed, 0)) is not int or quantities[seed] < count:
            raise PickerStateError("INSUFFICIENT_INVENTORY", "Insufficient local stock")
    except PickerStateError as exc:
        raise OrdinaryPlantStop(exc.code, str(exc)) from exc

    before = _observe(adapter, action_sent=False)
    _check_view(before, field_required=True)
    if not isinstance(before, OrdinaryPlantView):
        raise OrdinaryPlantStop("PLANT_OBSERVATION_UNAVAILABLE", "One-key mode not observed")
    if before.preview_cells != frozenset():
        raise OrdinaryPlantStop("PLANT_PREVIEW_UNVERIFIED", "Active/unknown special preview")
    empty = frozenset(cell for cell in ALL_CELLS if not before.field_cells[cell])
    if len(empty) != count:
        raise OrdinaryPlantStop("PLANT_COUNT_MISMATCH",
                                "One-key fills all empty plots, not a subset")
    # Deterministic plot selection is UI routing, not a planting strategy.
    anchor = min(empty)
    _act(adapter.open_plot, anchor)
    try:
        picker = prepare_picker_target(
            adapter, platform=platform, seed=seed, needed=count,
            stable_order=stable_order, quantities=quantities,
        )
    except (PickerStop, PickerStateError) as exc:
        raise OrdinaryPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc
    # Live QQ only displays this toggle after opening the picker. Verify it
    # there, after bounded navigation but BEFORE selecting a seed (which can
    # otherwise plant all empty plots immediately). Never infer it from field UI.
    if picker.get("one_key_planting") is not True:
        raise OrdinaryPlantStop("ONE_KEY_NOT_VERIFIED",
                                "One-key planting must be visibly enabled in the picker",
                                action_may_have_been_sent=True)
    _act(adapter.select_seed, picker["position"]["slot"])
    _act(adapter.wait, 2.0)
    completed_at = _after_action_clock(clock_ns)
    after = _observe(adapter, action_sent=True)
    _fresh(before, after, completed_at)
    try:
        _check_view(after, field_required=True)
    except SpecialPlantStop as exc:
        raise OrdinaryPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc
    if after.preview_cells != frozenset():
        raise OrdinaryPlantStop("PLANT_PREVIEW_UNVERIFIED",
                                "Unexpected preview after ordinary planting",
                                action_may_have_been_sent=True)
    if any(after.field_cells[cell] is not True for cell in ALL_CELLS):
        raise OrdinaryPlantStop("PLANT_POSTCONDITION_MISMATCH",
                                "One-key did not fill all 24 plots",
                                action_may_have_been_sent=True)
    updated = consume_confirmed(stable_order, quantities, seed, count)
    return {
        "status": "ordinary_plant_verified", "platform": platform,
        "seed": seed, "count": count, "anchor_cell": list(anchor),
        "picker": picker["position"], "quantities_after": updated,
        "persisted": False, "llm_round_trips": 0,
        "phase_duration_ms": round((perf_counter() - started) * 1000, 2),
    }
