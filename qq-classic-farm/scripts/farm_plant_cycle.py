"""V2 one-call local planting phase.

A phase starts only from a separately verified EMPTY field. From that point the
Runner owns expected occupancy: confirmed special placements are added to a
local set, then one-key planting fills exactly the remaining cells. Exceptions
STOP the phase; there is no automatic crash replay or partial-state recovery.
"""
from __future__ import annotations

from time import monotonic_ns, perf_counter
from typing import Callable, Mapping, Sequence

from farm_plant_ordinary import plant_ordinary_one_key
from farm_plant_special import ALL_CELLS, SpecialPlantStop, plant_one_special
from farm_runner import RunnerStop, preflight_cycle
from seed_order import PickerStateError, consume_confirmed


class PlantPhaseStop(ValueError):
    """Stop with confirmed facts only; caller must resync before another live run."""

    def __init__(self, code: str, message: str, *, completed: list[dict],
                 quantities: Mapping[str, int], occupied: frozenset[tuple[int, int]],
                 action_may_have_been_sent: bool):
        super().__init__(message)
        self.code = code
        self.completed = list(completed)
        self.confirmed_quantities = dict(quantities)
        self.confirmed_occupied = frozenset(occupied)
        self.action_may_have_been_sent = action_may_have_been_sent

    def facts(self) -> dict:
        return {
            "status": "stopped",
            "code": self.code,
            "completed_transactions": list(self.completed),
            "confirmed_quantities": dict(self.confirmed_quantities),
            "confirmed_occupied": [list(cell) for cell in sorted(self.confirmed_occupied)],
            "action_may_have_been_sent": self.action_may_have_been_sent,
            "retry_allowed": False,
        }


def _decode_cells(value: object) -> frozenset[tuple[int, int]]:
    try:
        cells = frozenset(tuple(cell) for cell in value)
    except (TypeError, ValueError):
        return frozenset()
    if not cells.issubset(ALL_CELLS):
        return frozenset()
    return cells


def _placement_cells(platform: str, placement: str, layout: dict) -> frozenset[tuple[int, int]]:
    try:
        rows = layout["platforms"][platform]["safe_special_2x2"]
        matches = [row for row in rows if row["id"] == placement]
        if len(matches) != 1:
            return frozenset()
        return frozenset(tuple(cell) for cell in matches[0]["cells"])
    except (KeyError, TypeError, ValueError):
        return frozenset()


def run_plant_phase(
    adapter, *, platform: str, actions: dict, stable_order: Sequence[str],
    quantities: Mapping[str, int], layout: dict,
    inventory_verified: bool = False,
    clock_ns: Callable[[], int] = monotonic_ns,
) -> dict:
    """Run one deterministic EMPTY -> planted phase with no model round-trips."""
    started = perf_counter()
    completed: list[dict] = []
    current = dict(quantities)
    occupied = frozenset()

    def stop(code: str, message: str, *, sent: bool) -> PlantPhaseStop:
        return PlantPhaseStop(code, message, completed=completed, quantities=current,
                              occupied=occupied, action_may_have_been_sent=sent)

    if not inventory_verified:
        raise stop("INVENTORY_DIRTY", "Live stock must be verified first", sent=False)

    try:
        preflight_cycle(
            {"platforms": {platform: actions}},
            {"platforms": {platform: {"stable_order": list(stable_order)}}},
            {"platforms": {platform: {"quantities": current}}},
            layout,
        )
    except (RunnerStop, PickerStateError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise stop(getattr(exc, "code", "INVALID_PLANT_PLAN"), str(exc), sent=False) from exc

    # One full-field check at phase start only. There is no partial-state recovery.
    try:
        if adapter.require_empty_field() is not True:
            raise SpecialPlantStop("PLANT_FIELD_NOT_EMPTY",
                                   "Planting phase requires a verified EMPTY field")
    except SpecialPlantStop as exc:
        raise stop(exc.code, str(exc), sent=exc.action_may_have_been_sent) from exc
    except Exception as exc:
        raise stop("PLANT_EMPTY_CHECK_UNAVAILABLE",
                   "Cannot verify EMPTY before planting", sent=False) from exc

    for special in actions["special"]:
        for placement in special["placements"]:
            expected = _placement_cells(platform, placement, layout)
            if len(expected) != 4 or expected & occupied:
                raise stop("INVALID_PLACEMENT",
                           "Special placement is invalid or overlaps Runner state", sent=False)
            try:
                result = plant_one_special(
                    adapter, platform=platform, seed=special["seed"],
                    placement=placement, known_occupied=occupied,
                    stable_order=stable_order, quantities=current,
                    layout=layout, clock_ns=clock_ns,
                )
            except SpecialPlantStop as exc:
                raise stop(exc.code, str(exc), sent=exc.action_may_have_been_sent) from exc

            if (result.get("status") != "special_plant_verified"
                or result.get("platform") != platform
                or result.get("seed") != special["seed"]
                or result.get("placement") != placement
                or result.get("persisted") is not False
                or result.get("llm_round_trips") != 0):
                raise stop("INVALID_TRANSACTION_RESULT",
                           "Special result does not match requested transaction", sent=True)

            updated = result.get("quantities_after")
            expected_quantities = consume_confirmed(
                stable_order, current, special["seed"], 1)
            expected_occupied = frozenset(occupied | expected)
            actual_occupied = _decode_cells(result.get("occupied_after"))
            if updated != expected_quantities or actual_occupied != expected_occupied:
                raise stop("INVALID_TRANSACTION_RESULT",
                           "Special result changed unexpected inventory/occupancy", sent=True)

            current = dict(updated)
            occupied = expected_occupied
            completed.append({k: v for k, v in result.items() if k != "quantities_after"})

    ordinary = actions["ordinary"][0]
    try:
        result = plant_ordinary_one_key(
            adapter, platform=platform, seed=ordinary["seed"],
            count=ordinary["count"], known_occupied=occupied,
            stable_order=stable_order, quantities=current, clock_ns=clock_ns,
        )
    except SpecialPlantStop as exc:
        raise stop(exc.code, str(exc), sent=exc.action_may_have_been_sent) from exc

    if (result.get("status") != "ordinary_plant_verified"
        or result.get("platform") != platform
        or result.get("seed") != ordinary["seed"]
        or result.get("count") != ordinary["count"]
        or result.get("persisted") is not False
        or result.get("llm_round_trips") != 0):
        raise stop("INVALID_TRANSACTION_RESULT",
                   "Ordinary result does not match requested transaction", sent=True)

    expected_quantities = consume_confirmed(
        stable_order, current, ordinary["seed"], ordinary["count"])
    actual_occupied = _decode_cells(result.get("occupied_after"))
    if result.get("quantities_after") != expected_quantities or actual_occupied != ALL_CELLS:
        raise stop("INVALID_TRANSACTION_RESULT",
                   "Ordinary result did not produce expected inventory/full occupancy", sent=True)

    current = dict(expected_quantities)
    occupied = ALL_CELLS
    completed.append({k: v for k, v in result.items() if k != "quantities_after"})

    return {
        "status": "plant_phase_verified",
        "platform": platform,
        "completed_transactions": completed,
        "occupied_after": [list(cell) for cell in sorted(occupied)],
        "quantities_after": current,
        "persisted": False,
        "llm_round_trips": 0,
        "phase_duration_ms": round((perf_counter() - started) * 1000, 2),
    }
