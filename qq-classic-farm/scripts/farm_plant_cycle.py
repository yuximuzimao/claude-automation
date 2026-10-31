"""M2 one-call local planting phase: special transactions followed by ordinary fill.

This is composition, NOT a live UI entry point. A future verified local adapter
supplies the observations and CGEvents. The Planner owns seed/count/placement;
the phase never substitutes seeds, guesses a slot, or persists stale inventory.
"""
from __future__ import annotations

from time import monotonic_ns, perf_counter
from typing import Callable, Mapping, Sequence

from farm_plant_ordinary import plant_ordinary_one_key
from farm_plant_special import SpecialPlantStop, plant_one_special
from farm_runner import RunnerStop, preflight_cycle
from seed_order import PickerStateError, consume_confirmed


class PlantPhaseStop(ValueError):
    """Failure with confirmed-only recovery facts; no implicit action retry."""

    def __init__(self, code: str, message: str, *, completed: list[dict],
                 quantities: Mapping[str, int], action_may_have_been_sent: bool):
        super().__init__(message)
        self.code = code
        self.completed = list(completed)
        self.confirmed_quantities = dict(quantities)
        self.action_may_have_been_sent = action_may_have_been_sent

    def recovery(self) -> dict:
        return {
            "status": "stopped", "code": self.code,
            "completed_transactions": list(self.completed),
            "confirmed_quantities": dict(self.confirmed_quantities),
            "action_may_have_been_sent": self.action_may_have_been_sent,
            "persisted": False, "retry_allowed": False,
        }


def run_plant_phase(
    adapter, *, platform: str, actions: dict, stable_order: Sequence[str],
    quantities: Mapping[str, int], layout: dict,
    inventory_verified: bool = False,
    clock_ns: Callable[[], int] = monotonic_ns,
    checkpoint: Callable[[list[dict], dict[str, int]], None] | None = None,
    before_transaction: Callable[[dict, list[dict], dict[str, int]], None] | None = None,
) -> dict:
    """Execute a prevalidated local M2 phase; never touch real UI by itself.

    `checkpoint` is called after every independently verified transaction.
    The eventual live runner MUST supply a durable recovery-log writer before
    permitting real clicks. It is optional only for isolated offline mocks.
    """
    started = perf_counter()
    completed: list[dict] = []
    current = dict(quantities)
    if not inventory_verified:
        raise PlantPhaseStop("INVENTORY_DIRTY", "Live stock must be verified first",
                             completed=completed, quantities=current,
                             action_may_have_been_sent=False)
    try:
        # Reuse M0 validation rather than duplicating placement, stock and
        # whole-field count rules in M2.
        preflight_cycle(
            {"platforms": {platform: actions}},
            {"platforms": {platform: {"stable_order": list(stable_order)}}},
            {"platforms": {platform: {"quantities": current}}},
            layout,
        )
    except (RunnerStop, PickerStateError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise PlantPhaseStop(
            getattr(exc, "code", "INVALID_PLANT_PLAN"), str(exc),
            completed=completed, quantities=current,
            action_may_have_been_sent=False,
        ) from exc

    def verified(result: dict, *, seed: str, used: int, status: str) -> None:
        nonlocal current
        if (result.get("status") != status or result.get("platform") != platform
            or result.get("seed") != seed):
            raise PlantPhaseStop("INVALID_TRANSACTION_RESULT",
                                 "Verified result does not match requested transaction",
                                 completed=completed, quantities=current,
                                 action_may_have_been_sent=True)
        if result.get("persisted") is not False or result.get("llm_round_trips") != 0:
            raise PlantPhaseStop("INVALID_TRANSACTION_RESULT",
                                 "Only unpersisted local verified transactions are accepted",
                                 completed=completed, quantities=current,
                                 action_may_have_been_sent=True)
        updated = result.get("quantities_after")
        if not isinstance(updated, dict) or updated != consume_confirmed(
            stable_order, current, seed, used
        ):
            raise PlantPhaseStop("INVALID_TRANSACTION_RESULT",
                                 "Confirmed inventory differs from exact requested consumption",
                                 completed=completed, quantities=current,
                                 action_may_have_been_sent=True)
        current = dict(updated)
        event = {key: value for key, value in result.items() if key != "quantities_after"}
        completed.append(event)
        if checkpoint is not None:
            try:
                checkpoint(list(completed), dict(current))
            except Exception as exc:
                raise PlantPhaseStop("RECOVERY_CHECKPOINT_FAILED",
                                     "Verified game action; recovery write failed; stop",
                                     completed=completed, quantities=current,
                                     action_may_have_been_sent=True) from exc

    def begin(transaction: dict) -> None:
        if before_transaction is None:
            return
        try:
            before_transaction(dict(transaction), list(completed), dict(current))
        except Exception as exc:
            raise PlantPhaseStop(
                "RECOVERY_PREACTION_FAILED",
                "Cannot durably mark transaction before game input; no new action sent",
                completed=completed, quantities=current,
                action_may_have_been_sent=False,
            ) from exc

    for special in actions["special"]:
        for placement in special["placements"]:
            begin({"kind": "special", "seed": special["seed"], "placement": placement})
            try:
                result = plant_one_special(
                    adapter, platform=platform, seed=special["seed"],
                    placement=placement, stable_order=stable_order,
                    quantities=current, layout=layout, clock_ns=clock_ns,
                )
            except SpecialPlantStop as exc:
                raise PlantPhaseStop(
                    exc.code, str(exc), completed=completed, quantities=current,
                    action_may_have_been_sent=exc.action_may_have_been_sent,
                ) from exc
            verified(result, seed=special["seed"], used=1,
                     status="special_plant_verified")

    ordinary = actions["ordinary"][0]
    begin({"kind": "ordinary", "seed": ordinary["seed"], "count": ordinary["count"]})
    try:
        result = plant_ordinary_one_key(
            adapter, platform=platform, seed=ordinary["seed"],
            count=ordinary["count"], stable_order=stable_order,
            quantities=current, clock_ns=clock_ns,
        )
    except SpecialPlantStop as exc:
        raise PlantPhaseStop(
            exc.code, str(exc), completed=completed, quantities=current,
            action_may_have_been_sent=exc.action_may_have_been_sent,
        ) from exc
    verified(result, seed=ordinary["seed"], used=ordinary["count"],
             status="ordinary_plant_verified")
    return {
        "status": "plant_phase_verified", "platform": platform,
        "completed_transactions": completed,
        "quantities_after": current, "persisted": False,
        "llm_round_trips": 0,
        "phase_duration_ms": round((perf_counter() - started) * 1000, 2),
    }
