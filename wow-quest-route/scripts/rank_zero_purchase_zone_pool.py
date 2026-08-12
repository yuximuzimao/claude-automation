from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json"

# These classes are not automatically selected, but they are eligible under the
# user's current five-box interaction model without requiring auction purchases.
BASELINE_CLASSES = {
    "travel_dialogue_or_turnin",
    "multi_target_shared_kill",
    "shared_kill",
    "single_named_kill",
    "single_named_drop",
    "escort_or_defense",
}

EXCLUDED_FLAGS = {
    "dungeon_objective_source",
}


def max_objective_count(task: dict) -> int:
    values = [int(obj.get("required_count") or 1) for obj in task.get("objectives", [])]
    return max(values, default=1)


def total_object_interactions(task: dict) -> int:
    return sum(
        int(obj.get("required_count") or 1)
        for obj in task.get("objectives", [])
        if any(src.get("entity_type") == "object" for src in obj.get("sources", []))
    )


def eligible(task: dict) -> tuple[bool, str]:
    flags = set(task.get("route_flags") or [])
    if flags & EXCLUDED_FLAGS:
        return False, "dungeon"
    if (task.get("required_level") or 99) > 54:
        return False, "too_high"
    cls = task.get("task_class")
    if cls in BASELINE_CLASSES:
        return True, "baseline"
    if cls == "world_object_item_collection":
        # Low-count fixed objects are acceptable; high-count collections remain
        # conditional because five characters multiply the serial interactions.
        count = total_object_interactions(task)
        return (count <= 5, "low_count_object" if count <= 5 else "high_count_object")
    if cls == "mixed_objectives":
        return (max_objective_count(task) <= 5, "low_count_mixed")
    if cls in {"single_creature_drop", "multi_creature_personal_drop", "mixed_with_personal_item"}:
        # Low-count item objectives remain candidates. Drop probability and route
        # overlap are reviewed separately; this script does not call them proven.
        return (max_objective_count(task) <= 5, "low_count_personal")
    if cls == "item_source_not_in_questie":
        return False, "unknown_source"
    return False, "other"


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    zones: dict[str, list[dict]] = defaultdict(list)
    for task in payload["tasks"]:
        ok, reason = eligible(task)
        if not ok:
            continue
        zone = task.get("primary_zone") or "unknown"
        # Use the best full-XP reward still available in the 39-54 band. This is
        # a zone-pool discovery metric, not a final route reward calculation.
        xp_values = [
            int(value)
            for level, value in (task.get("xp_by_completion_level") or {}).items()
            if 39 <= int(level) <= 54
        ]
        xp = max(xp_values, default=0)
        if xp <= 0:
            continue
        central = (task.get("azerothcore_adjusted_standalone_time") or {}).get("central")
        if central is None:
            central = (task.get("standalone_time_at_earliest_level") or {}).get("central") or 999.0
        zones[zone].append(
            {
                "quest_id": task["quest_id"],
                "name": task.get("name"),
                "xp": xp,
                "central_minutes_static": round(float(central), 2),
                "class": task.get("task_class"),
                "eligibility_reason": reason,
                "pre_single": task.get("pre_single", []),
                "pre_group": task.get("pre_group", []),
            }
        )

    summary = []
    for zone, tasks in zones.items():
        summary.append(
            {
                "zone": zone,
                "eligible_task_count": len(tasks),
                "eligible_xp_pool": sum(task["xp"] for task in tasks),
                "top_tasks": sorted(tasks, key=lambda row: row["xp"], reverse=True)[:20],
            }
        )
    summary.sort(key=lambda row: row["eligible_xp_pool"], reverse=True)

    output = {
        "schema_version": 1,
        "purpose": "discover zero-purchase five-box zone alternatives independent of the single-character video route",
        "warning": "The pool includes prerequisite-dependent and mutually exclusive tasks. It ranks investigation targets, not executable routes.",
        "zones": summary,
    }
    path = ROOT / "data/routes/horde/blood-elf/39-55-zero-purchase-zone-pool.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in summary[:20]:
        print(f"{row['zone']}: {row['eligible_xp_pool']} XP / {row['eligible_task_count']} eligible tasks")


if __name__ == "__main__":
    main()
