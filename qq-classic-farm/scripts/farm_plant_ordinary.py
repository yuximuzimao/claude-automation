"""V2 ordinary one-key planting transaction.

The Runner already knows which cells are occupied by confirmed special
placements. One-key planting is allowed only when the planned ordinary count
equals the remaining cells. Postcondition checks only those planned remaining
cell ROIs; no 24-cell semantic reconstruction is performed.
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
    # Kept only for diagnostic compatibility; picker state is authoritative.
    one_key_planting: bool | None = None


class OrdinaryPlantAdapter(PickerAdapter, Protocol):
    def observe_field(self) -> OrdinaryPlantView: ...
    def open_plot(self, anchor_cell: Cell) -> None: ...
    def select_seed(self, slot: int) -> None: ...
    def wait(self, seconds: float) -> None: ...
    def verify_cells_occupied(self, cells: frozenset[Cell]) -> bool | None: ...


def plant_ordinary_one_key(
    adapter: OrdinaryPlantAdapter, *, platform: str, seed: str, count: int,
    known_occupied: frozenset[Cell], stable_order: Sequence[str],
    quantities: Mapping[str, int],
    clock_ns: Callable[[], int] = monotonic_ns,
) -> dict:
    """Fill exactly the remaining planned cells with one verified picker slot."""
    started = perf_counter()
    if type(count) is not int or count <= 0 or count > len(ALL_CELLS):
        raise OrdinaryPlantStop("INVALID_PLANT_COUNT", "Invalid ordinary plot count")
    if (not isinstance(known_occupied, frozenset)
        or not known_occupied.issubset(ALL_CELLS)):
        raise OrdinaryPlantStop("PLANT_STATE_INVALID", "Invalid Runner occupied-cell state")

    remaining = frozenset(ALL_CELLS - known_occupied)
    if len(remaining) != count:
        raise OrdinaryPlantStop(
            "PLANT_COUNT_MISMATCH",
            "One-key planting count must equal Runner-known remaining cells",
        )

    try:
        compute_picker_position(platform, seed, stable_order, quantities)
        if type(quantities.get(seed, 0)) is not int or quantities[seed] < count:
            raise PickerStateError("INSUFFICIENT_INVENTORY", "Insufficient local stock")
    except PickerStateError as exc:
        raise OrdinaryPlantStop(exc.code, str(exc)) from exc

    before = _observe(adapter, action_sent=False)
    _check_view(before)
    if not isinstance(before, OrdinaryPlantView):
        raise OrdinaryPlantStop("PLANT_OBSERVATION_UNAVAILABLE", "Invalid ordinary field view")
    if before.preview_cells != frozenset():
        raise OrdinaryPlantStop("PLANT_PREVIEW_UNVERIFIED",
                                "Active/unknown special preview before ordinary planting")

    # Deterministic UI routing only. Strategy already determined the remaining set.
    anchor = min(remaining)
    _act(adapter.open_plot, anchor)
    try:
        picker = prepare_picker_target(
            adapter, platform=platform, seed=seed, needed=count,
            stable_order=stable_order, quantities=quantities,
        )
    except (PickerStop, PickerStateError) as exc:
        raise OrdinaryPlantStop(exc.code, str(exc), action_may_have_been_sent=True) from exc

    if picker.get("one_key_planting") is not True:
        raise OrdinaryPlantStop("ONE_KEY_NOT_VERIFIED",
                                "One-key planting must be visibly enabled in picker",
                                action_may_have_been_sent=True)

    arm = getattr(adapter, "arm_ordinary_selection", None)
    if arm is not None:
        _act(arm, count, seed)

    # Critical invariant: click exactly the slot that prepare_picker_target verified.
    _act(adapter.select_seed, picker["position"]["slot"])
    _act(adapter.wait, 2.0)
    completed_at = _after_action_clock(clock_ns)

    after = _observe(adapter, action_sent=True)
    _fresh(before, after, completed_at)
    if not isinstance(after, OrdinaryPlantView):
        raise OrdinaryPlantStop("PLANT_OBSERVATION_UNAVAILABLE",
                                "Invalid ordinary postcondition view",
                                action_may_have_been_sent=True)
    if after.preview_cells != frozenset():
        raise OrdinaryPlantStop("PLANT_PREVIEW_UNVERIFIED",
                                "Unexpected preview after ordinary planting",
                                action_may_have_been_sent=True)

    try:
        occupied_verified = adapter.verify_cells_occupied(remaining)
    except Exception as exc:
        raise OrdinaryPlantStop("PLANT_POSTCONDITION_UNAVAILABLE",
                                "Cannot verify planned ordinary target ROIs",
                                action_may_have_been_sent=True) from exc
    if occupied_verified is not True:
        raise OrdinaryPlantStop("PLANT_POSTCONDITION_MISMATCH",
                                "Planned ordinary target ROIs are not all occupied",
                                action_may_have_been_sent=True)

    updated = consume_confirmed(stable_order, quantities, seed, count)
    return {
        "status": "ordinary_plant_verified", "platform": platform,
        "seed": seed, "count": count, "anchor_cell": list(anchor),
        "picker": picker["position"],
        "occupied_after": [list(cell) for cell in sorted(ALL_CELLS)],
        "quantities_after": updated,
        "persisted": False, "llm_round_trips": 0,
        "phase_duration_ms": round((perf_counter() - started) * 1000, 2),
    }
