from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_PARAMETER_PATH = ROOT / "data/timing/task-parameters.json"
QUEST_SOURCE_PATH = ROOT / "data/timing/quest-source-inputs.json"
FIVEBOX_TYPES_PATH = ROOT / "data/observations/fivebox-task-types.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_task_row(node: Any, task_id: int) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if node.get("quest_id") == task_id or node.get("task_id") == task_id:
            return node
        for value in node.values():
            found = _find_task_row(value, task_id)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_task_row(value, task_id)
            if found is not None:
                return found
    return None


def _objective_task_ids(profile: dict[str, Any], selected_steps: set[str]) -> list[int]:
    action_by_id = {str(row["action_id"]): row for row in profile.get("actions") or []}
    task_ids: list[int] = []
    for step in profile.get("step_groups") or []:
        step_id = str(step["step_id"])
        if selected_steps and step_id not in selected_steps:
            continue
        for action_id in step.get("action_ids") or []:
            action = action_by_id.get(str(action_id)) or {}
            if action.get("kind") != "objective" or action.get("task_id") is None:
                continue
            task_id = int(action["task_id"])
            if task_id not in task_ids:
                task_ids.append(task_id)
    return task_ids


def _fixed_rule_from_timing(
    task_id: int,
    timing: dict[str, Any],
    *,
    source_ref: str,
    source_kind: str,
) -> tuple[str | None, dict[str, Any] | None, str]:
    if timing.get("status") != "estimated" or not isinstance(timing.get("minutes"), (int, float)):
        return None, None, f"{source_kind}_intrinsic_service_unavailable"
    seconds = float(timing["minutes"]) * 60.0
    basis = str(timing.get("basis") or "unknown")
    params = {
        "inputs": {"fixed_service_seconds": seconds},
        "source_refs": [f"{source_ref}#task_id={task_id}; basis={basis}"],
    }
    if isinstance(timing.get("range_minutes"), list):
        params["provisional_range_minutes"] = timing["range_minutes"]
    return "fixed-service-seconds", params, f"{source_kind}_fixed:{basis}"


def _fixed_rule(
    task_id: int,
    foundation_row: dict[str, Any] | None,
    *,
    foundation_ref: str | None,
    timing_screen_row: dict[str, Any] | None = None,
    timing_screen_ref: str | None = None,
) -> tuple[str | None, dict[str, Any] | None, str]:
    if isinstance(foundation_row, dict):
        result = _fixed_rule_from_timing(
            task_id,
            foundation_row.get("intrinsic_service_time") or {},
            source_ref=foundation_ref or "foundation",
            source_kind="foundation",
        )
        if result[0] is not None:
            return result
    if isinstance(timing_screen_row, dict):
        return _fixed_rule_from_timing(
            task_id,
            timing_screen_row.get("timing") or timing_screen_row,
            source_ref=timing_screen_ref or "timing-screen",
            source_kind="timing_screen",
        )
    return None, None, "task_intrinsic_service_unavailable"


def _choose_rule(
    task_id: int,
    card: dict[str, Any],
    foundation_row: dict[str, Any] | None,
    quest_row: dict[str, Any],
    legacy_type: str,
    *,
    foundation_ref: str | None,
    timing_screen_row: dict[str, Any] | None = None,
    timing_screen_ref: str | None = None,
) -> tuple[str | None, dict[str, Any] | None, str]:
    foundation_row = foundation_row or {}
    task_class = str(foundation_row.get("task_class") or "")
    intrinsic = foundation_row.get("intrinsic_service_time") or {}
    basis = str(intrinsic.get("basis") or "")
    fivebox_status = str(((card.get("fivebox") or {}).get("status") or "")).strip()
    inputs = quest_row.get("inputs") or {}

    if fivebox_status == "pending":
        return None, None, "pending_fivebox_mechanism"

    # Preserve reviewed/manual task-intrinsic calibrations exactly. They are already
    # isolated from route movement and hub handling, so they survive step splits safely.
    if basis.startswith("manual_pre_route:"):
        return _fixed_rule(
            task_id,
            foundation_row,
            foundation_ref=foundation_ref,
            timing_screen_row=timing_screen_row,
            timing_screen_ref=timing_screen_ref,
        )

    if task_class == "travel_dialogue_or_turnin":
        return "zero-independent-service", None, "foundation_travel_or_dialogue_zero_service"

    if legacy_type in {"quest_item_use_personal_confirmed", "npc_interaction_group_shared_confirmed"}:
        params = {
            "inputs": {"interaction_count": 1},
            "source_refs": [
                f"data/observations/fivebox-task-types.json#tasks.{task_id}; legacy_type={legacy_type}"
            ],
        }
        return "fixed-object-interaction", params, f"live_interaction_type:{legacy_type}"

    if task_class in {"shared_kill", "multi_target_shared_kill"} and isinstance(inputs.get("kill_count"), int):
        if fivebox_status == "shared":
            return "shared-kill-count", None, "structured_shared_kill_count"
        if fivebox_status == "not_shared":
            return "personal-kill-count", None, "structured_personal_kill_count"

    if task_class == "single_named_kill" and isinstance(inputs.get("kill_count"), int):
        if fivebox_status == "not_shared":
            return "personal-kill-count", None, "structured_personal_named_kill"
        if fivebox_status in {"pending", "special"}:
            return None, None, f"fivebox_status_{fivebox_status}_needs_review"
        # Named targets carry pull/script/interaction overhead not represented by the
        # generic 15-second trash-kill calibration. Preserve the old isolated service.
        return _fixed_rule(
            task_id,
            foundation_row,
            foundation_ref=foundation_ref,
            timing_screen_row=timing_screen_row,
            timing_screen_ref=timing_screen_ref,
        )

    if task_class in {"world_object_collection", "world_object_item_collection", "fixed_object_interaction"}:
        if isinstance(inputs.get("interaction_count"), int) and fivebox_status in {
            "shared",
            "not_shared",
            "sequential_loot",
        }:
            return "fixed-object-interaction", None, "structured_fixed_object_interaction"

    if task_class in {"multi_creature_personal_drop", "single_creature_drop"}:
        intrinsic_available = intrinsic.get("status") == "estimated" and isinstance(intrinsic.get("minutes"), (int, float))
        if (
            intrinsic_available
            and isinstance(inputs.get("required_count"), int)
            and isinstance(inputs.get("drop_rate"), (int, float))
            and fivebox_status in {"shared", "not_shared", "sequential_loot"}
        ):
            return "personal-drop-count", None, "structured_personal_drop"

    objective_types = {str(row.get("objective_type")) for row in quest_row.get("objectives") or []}
    if isinstance(inputs.get("interaction_count"), int) and fivebox_status in {
        "shared",
        "not_shared",
        "sequential_loot",
    } and objective_types and objective_types <= {"object", "item"}:
        return "fixed-object-interaction", None, "quest_source_fixed_object_interaction"

    suspicious_kill_type = any(
        token in legacy_type
        for token in (
            "vehicle",
            "script",
            "event",
            "interaction",
            "item_use",
            "object",
            "capture",
            "rescue",
            "escort",
            "summon",
            "dialogue",
            "transport",
            "phase",
            "loot",
            "collection",
        )
    )
    if (
        isinstance(inputs.get("kill_count"), int)
        and int(inputs["kill_count"]) > 1
        and objective_types == {"kill"}
        and not suspicious_kill_type
    ):
        if fivebox_status == "shared":
            return "shared-kill-count", None, "quest_source_shared_multi_kill"
        if fivebox_status == "not_shared":
            return "personal-kill-count", None, "quest_source_personal_multi_kill"

    # Composite/script/single-target tasks without a trustworthy typed decomposition
    # keep their already-isolated per-task center as a migration input. This is
    # deliberately task-level, never a step-total residual.
    if fivebox_status not in {"pending"}:
        return _fixed_rule(
            task_id,
            foundation_row,
            foundation_ref=foundation_ref,
            timing_screen_row=timing_screen_row,
            timing_screen_ref=timing_screen_ref,
        )
    return None, None, "pending_fivebox_mechanism"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate Route Timing from legacy/current task foundation into Task Card timing_rule_ref "
            "and versioned task parameters. Dry-run by default."
        )
    )
    parser.add_argument("profile_id")
    parser.add_argument("--foundation", type=Path)
    parser.add_argument("--timing-screen", type=Path, help="Optional per-task intrinsic timing fallback.")
    parser.add_argument("--step", action="append", default=[], help="Only migrate objective tasks in these step ids.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    profile_path = ROOT / "data/route-profiles" / f"{args.profile_id}.json"
    profile = _load(profile_path)
    foundation_path = None
    foundation = None
    if args.foundation is not None:
        foundation_path = args.foundation if args.foundation.is_absolute() else ROOT / args.foundation
        foundation = _load(foundation_path)
    timing_screen_path = None
    timing_screen = None
    if args.timing_screen is not None:
        timing_screen_path = args.timing_screen if args.timing_screen.is_absolute() else ROOT / args.timing_screen
        timing_screen = _load(timing_screen_path)
    quest_source = _load(QUEST_SOURCE_PATH)
    fivebox_types = _load(FIVEBOX_TYPES_PATH)
    task_parameters = _load(TASK_PARAMETER_PATH)
    selected_steps = {str(value) for value in args.step}
    task_ids = _objective_task_ids(profile, selected_steps)

    results = []
    task_parameter_rows = task_parameters.setdefault("tasks", {})
    for task_id in task_ids:
        card_path = ROOT / "data/task-cards" / f"{task_id}.json"
        if not card_path.exists():
            results.append({"task_id": task_id, "status": "missing_task_card"})
            continue
        card = _load(card_path)
        existing_rule = card.get("timing_rule_ref")
        fivebox_status = str(((card.get("fivebox") or {}).get("status") or "")).strip()
        if existing_rule and fivebox_status == "pending":
            results.append({"task_id": task_id, "status": "pending_rule_cleared", "rule": existing_rule})
            if args.write:
                card["timing_rule_ref"] = None
                _write(card_path, card)
            continue
        if existing_rule:
            results.append({"task_id": task_id, "status": "kept_existing", "rule": existing_rule})
            continue
        foundation_row = _find_task_row(foundation, task_id) if foundation is not None else None
        timing_screen_row = _find_task_row(timing_screen, task_id) if timing_screen is not None else None
        quest_row = (quest_source.get("tasks") or {}).get(str(task_id)) or {}
        legacy_row = ((fivebox_types.get("tasks") or fivebox_types).get(str(task_id)) or {})
        rule_ref, params, reason = _choose_rule(
            task_id,
            card,
            foundation_row,
            quest_row,
            str(legacy_row.get("type") or ""),
            foundation_ref=str(foundation_path.relative_to(ROOT)) if foundation_path is not None else None,
            timing_screen_row=timing_screen_row,
            timing_screen_ref=(
                str(timing_screen_path.relative_to(ROOT)) if timing_screen_path is not None else None
            ),
        )
        if rule_ref is None:
            results.append({"task_id": task_id, "status": "review_required", "reason": reason})
            continue

        results.append({"task_id": task_id, "status": "migrate", "rule": rule_ref, "reason": reason})
        if not args.write:
            continue
        card["timing_rule_ref"] = rule_ref
        _write(card_path, card)
        if params is not None:
            existing_params = task_parameter_rows.get(str(task_id)) or {}
            merged_inputs = dict(existing_params.get("inputs") or {})
            merged_inputs.update(params.get("inputs") or {})
            source_refs = list(existing_params.get("source_refs") or [])
            for source_ref in params.get("source_refs") or []:
                if source_ref not in source_refs:
                    source_refs.append(source_ref)
            merged = dict(existing_params)
            merged["inputs"] = merged_inputs
            merged["source_refs"] = source_refs
            if "provisional_range_minutes" in params:
                merged["provisional_range_minutes"] = params["provisional_range_minutes"]
            task_parameter_rows[str(task_id)] = merged

    if args.write:
        _write(TASK_PARAMETER_PATH, task_parameters)

    print(
        json.dumps(
            {
                "profile_id": args.profile_id,
                "selected_steps": sorted(selected_steps),
                "write": args.write,
                "counts": {
                    key: sum(1 for row in results if row["status"] == key)
                    for key in sorted({row["status"] for row in results})
                },
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
