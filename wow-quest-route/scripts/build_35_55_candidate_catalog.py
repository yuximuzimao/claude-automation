from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from lib.questie_lua import seq
from scripts.analyze_questie_journey import event_timestamp, normalize_event, parse_saved_variables


CURRENT_LEVEL = 35
MANUAL_COMPLETED = {
    201,       # 调查营地
    1115, 1116,
    1154, 6627,
    1180, 1181, 1182,
}
MANUAL_ACTIVE = {
    187, 192, 195, 1106, 1107, 1117, 1183, 1362, 5361, 9627,
}
OBJECTIVE_COMPLETE_PENDING_TURNIN = {195}


def latest_journey_states(path: Path) -> tuple[dict[int, str], int]:
    config = parse_saved_variables(path)
    candidates: list[tuple[int, list[dict[str, Any]]]] = []
    char_table = config.get("char")
    if isinstance(char_table, dict):
        for entry in char_table.values():
            if not isinstance(entry, dict):
                continue
            events = [normalize_event(value, index) for index, value in enumerate(seq(entry.get("journey")), 1)]
            if events:
                candidates.append((max(event_timestamp(event) or 0 for event in events), events))
    if not candidates:
        return {}, 0
    timestamp, events = max(candidates, key=lambda value: value[0])
    states: dict[int, str] = {}
    for event in events:
        quest_id = event.get("quest_id")
        event_type = event.get("event")
        if isinstance(quest_id, int) and isinstance(event_type, str):
            states[quest_id] = event_type
    return states, timestamp


def prerequisite_status(task: dict[str, Any], completed: set[int]) -> tuple[bool, list[int], list[int]]:
    pre_group = [int(value) for value in task.get("pre_group", [])]
    pre_single = [int(value) for value in task.get("pre_single", [])]
    missing_group = [value for value in pre_group if value not in completed]
    single_ok = not pre_single or any(value in completed for value in pre_single)
    missing_single = [] if single_ok else pre_single
    return not missing_group and single_ok, missing_group, missing_single


def task_state(task: dict[str, Any], completed: set[int], active: set[int]) -> tuple[str, list[int], list[int]]:
    quest_id = int(task["quest_id"])
    if quest_id in OBJECTIVE_COMPLETE_PENDING_TURNIN:
        return "objective_complete_pending_turnin", [], []
    if quest_id in completed:
        return "completed", [], []
    if quest_id in active:
        return "active", [], []
    prerequisites_ok, missing_group, missing_single = prerequisite_status(task, completed)
    if int(task["required_level"]) > CURRENT_LEVEL:
        return "future_level", missing_group, missing_single
    if prerequisites_ok:
        start_types = {entity.get("entity_type") for entity in task.get("start_entities", [])}
        if start_types and start_types <= {"item", "object"}:
            return "available_at_35_conditional_trigger", [], []
        return "available_at_35", [], []
    return "level_met_but_prerequisite_locked", missing_group, missing_single


def objective_summary(task: dict[str, Any]) -> str:
    parts: list[str] = []
    for objective in task.get("objectives", []):
        sources: list[str] = []
        for source in objective.get("sources", []):
            rates = [
                value.get("probability_percent")
                for value in source.get("loot_evidence", [])
                if value.get("probability_percent") is not None
            ]
            suffix = f"@{max(rates):g}%" if rates else ""
            sources.append(f"{source.get('name')}#{source.get('entity_id')}{suffix}")
        parts.append(
            f"{objective.get('objective_type')}/{objective.get('mechanic')}/"
            f"x{objective.get('required_count')}/"
            + "|".join(sources[:8])
        )
    return "; ".join(parts)


def task_row(task: dict[str, Any]) -> dict[str, Any]:
    adjusted = task.get("azerothcore_adjusted_standalone_time") or task["standalone_time_at_earliest_level"]
    row: dict[str, Any] = {
        "quest_id": task["quest_id"],
        "name": task["name"],
        "state": task["candidate_state"],
        "zone": task["primary_zone"],
        "required_level": task["required_level"],
        "quest_level": task["quest_level"],
        "earliest_completion_level": task["earliest_completion_level"],
        "task_class": task["task_class"],
        "objective_summary": objective_summary(task),
        "time_optimistic_min": adjusted["optimistic"],
        "time_central_min": adjusted["central"],
        "time_pessimistic_min": adjusted["pessimistic"],
        "distance_index": task.get("standalone_distance_index"),
        "missing_group_prerequisites": ",".join(map(str, task.get("missing_group_prerequisites", []))),
        "missing_single_prerequisites": ",".join(map(str, task.get("missing_single_prerequisites", []))),
        "next_quest": task.get("next_quest") or "",
        "route_flags": ",".join(task.get("route_flags", [])),
        "confidence": task.get("confidence"),
    }
    for level in range(35, 55):
        row[f"xp_at_{level}"] = task["xp_by_completion_level"][str(level)]
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Create current and future 35-55 quest candidate catalogs")
    parser.add_argument("--foundation", default="data/routes/horde/blood-elf/35-55-task-foundation-enriched.json")
    parser.add_argument("--journey", default="../.ai-bridge/Questie.lua")
    parser.add_argument("--all-json", default="data/routes/horde/blood-elf/35-55-candidates.json")
    parser.add_argument("--all-csv", default="data/routes/horde/blood-elf/35-55-candidates.csv")
    parser.add_argument("--available-csv", default="data/routes/horde/blood-elf/35-current-available-tasks.csv")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / args.foundation).read_text(encoding="utf-8"))
    journey_states, journey_timestamp = latest_journey_states((root / args.journey).resolve())
    completed = {quest_id for quest_id, state in journey_states.items() if state == "Complete"} | MANUAL_COMPLETED
    active = MANUAL_ACTIVE

    tasks: list[dict[str, Any]] = []
    for task in payload["tasks"]:
        state, missing_group, missing_single = task_state(task, completed, active)
        task["candidate_state"] = state
        task["missing_group_prerequisites"] = missing_group
        task["missing_single_prerequisites"] = missing_single
        task["remaining_35_55_candidate"] = (
            state != "completed"
            and (int(task["quest_level"]) >= 35 or int(task["quest_id"]) in active)
        )
        tasks.append(task)

    remaining = [task for task in tasks if task["remaining_35_55_candidate"]]
    available = [
        task for task in remaining
        if task["candidate_state"] in {
            "active", "objective_complete_pending_turnin", "available_at_35",
            "available_at_35_conditional_trigger",
        }
    ]

    output_payload = {
        "schema_version": 1,
        "source_foundation": args.foundation,
        "journey_timestamp": journey_timestamp,
        "journey_is_stale_after_level_33": True,
        "manual_completed_after_journey": sorted(MANUAL_COMPLETED),
        "manual_active": sorted(active),
        "completed_count": len(completed),
        "remaining_candidate_count": len(remaining),
        "available_at_35_count": len(available),
        "state_counts": Counter(task["candidate_state"] for task in tasks),
        "tasks": tasks,
    }
    output_json = root / args.all_json
    output_json.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = [task_row(task) for task in remaining]
    output_csv = root / args.all_csv
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    available_rows = [task_row(task) for task in available]
    available_csv = root / args.available_csv
    with available_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(available_rows[0]))
        writer.writeheader()
        writer.writerows(available_rows)

    print(json.dumps({
        "remaining_candidates": len(remaining),
        "available_at_35": len(available),
        "states": Counter(task["candidate_state"] for task in tasks),
        "all_json": str(output_json.relative_to(root)),
        "all_csv": str(output_csv.relative_to(root)),
        "available_csv": str(available_csv.relative_to(root)),
    }, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
