"""M0 deterministic farm Runner: safe, side-effect-free dry-run only.

No game interaction is implemented. 'run-next' intentionally returns STOP until
M1/M2 I/O, image verification, and postconditions have been tested.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

from seed_order import (
    PAGE_SIZE,
    PLATFORMS,
    PickerStateError,
    compute_picker_position,
    compute_visible_order,
    consume_confirmed,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORDER = ROOT / "data/seed-order.json"
DEFAULT_STATE = ROOT / "data/farm-state.json"
DEFAULT_LAYOUT = ROOT / "data/ui-layout.json"
EXAMPLE_PLAN = ROOT / "examples/run-plan.sample.json"


class RunnerStop(Exception):
    def __init__(self, code: str, message: str, **details: object):
        super().__init__(message)
        self.code = code
        self.details = details

    def as_dict(self) -> dict:
        return {"status": "stopped", "code": self.code, "message": str(self), **self.details}


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RunnerStop("INVALID_DATA", f"Expected JSON object: {path}")
    return value


def save_state_atomic(path: Path, state: dict) -> None:
    """Durable replacement for future confirmed-only commits, never used in dry-run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dirfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _keys(obj: object, required: set[str], allowed: set[str], where: str) -> None:
    if not isinstance(obj, dict):
        raise RunnerStop("INVALID_PLAN", f"{where} must be an object")
    missing = required - obj.keys()
    extra = obj.keys() - allowed
    if missing or extra:
        raise RunnerStop(
            "INVALID_PLAN", f"{where}: missing={sorted(missing)} unexpected={sorted(extra)}"
        )


def validate_plan(plan: dict) -> dict:
    """Strictly separate strategy from UI-derived page/slot/coordinates."""
    _keys(plan, {"schema_version", "plan_id", "revision", "cycles"},
          {"schema_version", "plan_id", "revision", "cycles"}, "plan")
    if plan["schema_version"] != 1 or type(plan["revision"]) is not int or plan["revision"] < 1:
        raise RunnerStop("INVALID_PLAN", "Unsupported plan schema or revision")
    if not isinstance(plan["plan_id"], str) or not plan["plan_id"]:
        raise RunnerStop("INVALID_PLAN", "plan_id is required")
    cycles = plan["cycles"]
    if not isinstance(cycles, list) or not cycles:
        raise RunnerStop("INVALID_PLAN", "cycles must be nonempty")
    ids: set[str] = set()
    for cycle in cycles:
        _keys(cycle, {"cycle_id", "status", "maturity_target", "platforms"},
              {"cycle_id", "status", "maturity_target", "platforms"}, "cycle")
        if not isinstance(cycle["cycle_id"], str) or not cycle["cycle_id"] or cycle["cycle_id"] in ids:
            raise RunnerStop("INVALID_PLAN", "cycle_id missing or duplicated")
        ids.add(cycle["cycle_id"])
        if cycle["status"] not in ("pending", "running", "complete", "error"):
            raise RunnerStop("INVALID_PLAN", "Unknown cycle status")
        if not isinstance(cycle["maturity_target"], str):
            raise RunnerStop("INVALID_PLAN", "maturity_target must be a string")
        platforms = cycle["platforms"]
        if not isinstance(platforms, dict) or not platforms or set(platforms) - set(PLATFORMS):
            raise RunnerStop("INVALID_PLAN", "Unsupported platforms")
        for platform, actions in platforms.items():
            _keys(actions, {"special", "ordinary"}, {"special", "ordinary"}, platform)
            if not isinstance(actions["special"], list) or not isinstance(actions["ordinary"], list):
                raise RunnerStop("INVALID_PLAN", "special/ordinary must be lists")
            if len(actions["ordinary"]) != 1:
                raise RunnerStop("INVALID_PLAN", "MVP supports exactly one ordinary one-key seed")
            for special in actions["special"]:
                _keys(special, {"seed", "placements"}, {"seed", "placements"}, "special")
                if not isinstance(special["seed"], str) or not special["seed"]:
                    raise RunnerStop("INVALID_PLAN", "special seed missing")
                if (not isinstance(special["placements"], list)
                    or not special["placements"]
                    or any(not isinstance(p, str) for p in special["placements"])):
                    raise RunnerStop("INVALID_PLAN", "special placements invalid")
            for ordinary in actions["ordinary"]:
                _keys(ordinary, {"seed", "count"}, {"seed", "count"}, "ordinary")
                if not isinstance(ordinary["seed"], str) or not ordinary["seed"]:
                    raise RunnerStop("INVALID_PLAN", "ordinary seed missing")
                if type(ordinary["count"]) is not int or ordinary["count"] <= 0:
                    raise RunnerStop("INVALID_PLAN", "ordinary count must be positive integer")
    return plan


def _layout_cells(platform: str, actions: dict, layout: dict) -> int:
    config = layout["platforms"][platform]
    permitted = {x["id"]: x for x in config["safe_special_2x2"]}
    occupied: set[tuple[int, int]] = set()
    used_placements: set[str] = set()
    for item in actions["special"]:
        for placement in item["placements"]:
            if placement not in permitted or placement in used_placements:
                raise RunnerStop("INVALID_PLACEMENT", f"{platform}: invalid/duplicate {placement}")
            used_placements.add(placement)
            cells = [tuple(c) for c in permitted[placement]["cells"]]
            if len(cells) != 4 or any(c in occupied for c in cells):
                raise RunnerStop("INVALID_PLACEMENT", f"{platform}: overlap/invalid 2x2 {placement}")
            occupied.update(cells)
    total = layout["grid_model"]["cell_count"]
    ordinary_count = actions["ordinary"][0]["count"]
    if ordinary_count != total - len(occupied):
        raise RunnerStop(
            "INVALID_PLACEMENT",
            f"{platform}: {len(occupied)} special cells + {ordinary_count} ordinary != {total}",
        )
    return total


def preflight_cycle(cycle: dict, order: dict, state: dict, layout: dict) -> None:
    """Validate *all* platforms before any future real action starts."""
    for platform, actions in cycle["platforms"].items():
        _layout_cells(platform, actions, layout)
        quantities = state["platforms"][platform]["quantities"]
        stable = order["platforms"][platform]["stable_order"]
        visible = compute_visible_order(stable, quantities)
        required: dict[str, int] = {}
        for item in actions["special"]:
            required[item["seed"]] = required.get(item["seed"], 0) + len(item["placements"])
        for item in actions["ordinary"]:
            required[item["seed"]] = required.get(item["seed"], 0) + item["count"]
        for seed, count in required.items():
            if seed not in visible or quantities[seed] < count:
                raise PickerStateError(
                    "INSUFFICIENT_INVENTORY",
                    f"{platform}: {seed} requires {count}, have {quantities.get(seed, 0)}",
                )


def dry_run(plan: dict, order: dict, state: dict, layout: dict) -> dict:
    started = perf_counter()
    validate_plan(plan)
    if order.get("schema_version") != 1 or state.get("schema_version") != 1:
        raise RunnerStop("INVALID_DATA", "Unsupported order/state schema")
    if order.get("page_size") != PAGE_SIZE:
        raise RunnerStop("INVALID_DATA", "Unexpected picker page size")
    pending = next((x for x in plan["cycles"] if x["status"] == "pending"), None)
    if pending is None:
        raise RunnerStop("NO_PENDING_CYCLE", "No pending cycle")
    preflight_cycle(pending, order, state, layout)
    state_copy = copy.deepcopy(state)
    events = []
    warnings = []
    for platform, actions in pending["platforms"].items():
        start = perf_counter()
        total = _layout_cells(platform, actions, layout)
        platform_state = state_copy["platforms"][platform]
        quantities = platform_state["quantities"]
        stable = order["platforms"][platform]["stable_order"]
        if platform_state.get("inventory_dirty"):
            warnings.append(f"{platform}: inventory_dirty=true; simulation only, live run forbidden")
        for item in actions["special"]:
            for placement in item["placements"]:
                position = compute_picker_position(platform, item["seed"], stable, quantities)
                quantities = consume_confirmed(stable, quantities, item["seed"], 1)
                events.append({
                    "phase": "PLANT_SPECIAL", "platform": platform,
                    "seed": item["seed"], "placement": placement,
                    "picker": position.as_dict(), "simulated_quantity_after": quantities[item["seed"]],
                })
        for item in actions["ordinary"]:
            position = compute_picker_position(platform, item["seed"], stable, quantities)
            quantities = consume_confirmed(stable, quantities, item["seed"], item["count"])
            events.append({
                "phase": "PLANT_ORDINARY", "platform": platform,
                "seed": item["seed"], "count": item["count"],
                "picker": position.as_dict(), "simulated_quantity_after": quantities[item["seed"]],
            })
        platform_state["quantities"] = quantities
        events.append({
            "phase": "DRY_RUN_POSTCONDITION", "platform": platform,
            "expected_occupied_cells": total, "duration_ms": round((perf_counter() - start) * 1000, 2),
        })
    return {
        "status": "dry_run_ok", "plan_id": plan["plan_id"], "plan_revision": plan["revision"],
        "cycle_id": pending["cycle_id"], "warnings": warnings, "events": events,
        "simulated_quantities": {
            platform: state_copy["platforms"][platform]["quantities"]
            for platform in pending["platforms"]
        },
        "metrics": {
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "llm_round_trips": 0, "click_count": 0, "screenshot_count": 0,
            "fallback_count": 0, "local_vision_count": 0,
        },
        "persisted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Farm Runner M0; dry-run only, never clicks")
    parser.add_argument("command", choices=("dry-run", "run-next"))
    parser.add_argument("--plan", type=Path, default=EXAMPLE_PLAN)
    parser.add_argument("--order", type=Path, default=DEFAULT_ORDER)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    args = parser.parse_args()
    try:
        if args.command == "run-next":
            raise RunnerStop("RUNNER_NOT_READY", "M1/M2 not implemented; refusing real UI actions")
        result = dry_run(load_json(args.plan), load_json(args.order),
                         load_json(args.state), load_json(args.layout))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RunnerStop, PickerStateError) as exc:
        if isinstance(exc, RunnerStop):
            result = exc.as_dict()
        else:
            result = {"status": "stopped", "code": exc.code, "message": str(exc)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "stopped", "code": "INVALID_DATA",
                          "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
