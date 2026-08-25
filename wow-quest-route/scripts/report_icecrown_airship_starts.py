from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT = ROOT / "data/route-atlas/icecrown-airship-start-audit.json"
ROUTE_STATUSES = {"include_candidate", "include_conditional_route_state", "include_first_run_repeatable_or_calendar"}
AIRSHIP_NPC_IDS = {29795, 30824, 30825, 31261, 32301}


def main() -> None:
    data = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in data.get("tasks", []):
        if task.get("scope_status") not in ROUTE_STATUSES:
            continue
        starts = []
        for entity in task.get("start_entities") or []:
            eid = entity.get("entity_id")
            if eid in AIRSHIP_NPC_IDS:
                starts.append({"entity_id": eid, "name": entity.get("name")})
        if not starts:
            continue
        rows.append({
            "quest_id": int(task["quest_id"]),
            "name": task.get("name"),
            "starts": starts,
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "available_starting_with": task.get("available_starting_with") or [],
            "disabled_by_quest": task.get("disabled_by_quest") or [],
            "is_daily": task.get("is_daily"),
            "is_repeatable": task.get("is_repeatable"),
            "objective_text_zh": task.get("objective_text_zh"),
            "economy": task.get("level_80_economy"),
        })
    rows.sort(key=lambda row: row["quest_id"])
    by_npc = defaultdict(list)
    for row in rows:
        for start in row["starts"]:
            by_npc[str(start["entity_id"])].append(row["quest_id"])
    payload = {"airship_npc_ids": sorted(AIRSHIP_NPC_IDS), "by_npc": dict(by_npc), "tasks": rows}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "task_count": len(rows),
        "tasks": [{"quest_id": row["quest_id"], "name": row["name"], "pre_any": row["pre_any"], "pre_all": row["pre_all"], "starts": row["starts"]} for row in rows],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
