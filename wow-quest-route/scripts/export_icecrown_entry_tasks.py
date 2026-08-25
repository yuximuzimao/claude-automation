from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT = ROOT / "data/route-atlas/icecrown-entry-tasks.json"

QUEST_IDS = [
    12806, 12807, 12810, 12813, 12814, 12815, 12838, 12839, 12840, 12847, 12852,
    12891, 12892, 12893, 12897, 12899,
    13008, 13036, 13039, 13040, 13044, 13045, 13070, 13086,
    13068, 13072, 13073, 13074, 13075, 13076, 13077, 13078, 13079, 13080, 13081, 13082, 13083,
    13104, 13110, 13118, 13122, 13125, 13130, 13135, 13139, 13141, 13157,
    13224, 13227, 13228, 13293, 13302, 13330, 13340,
    12938, 12939, 12943, 12949, 12951, 12955, 12982, 12992, 12995, 12999,
    13042, 13043, 13059, 13069, 13071, 13084, 13085, 13091, 13092, 13106, 13121,
    13133, 13137, 13142, 13213, 13214, 13215, 13216, 13217, 13218, 13219,
    13117, 13119, 13120, 13134, 13136, 13138, 13140, 13229,
    13258, 13259, 13262, 13263, 13271, 13275, 13282,
    13230, 13237, 13238, 13239, 13260, 13264, 13277, 13278, 13279, 13351, 13379,
    13283, 13301, 13302, 13304, 13305, 13308, 13310, 13330, 13236,
    13348, 13349, 13359, 13360, 13361, 13362, 13363, 13364,
    13152, 13211, 13144, 13212, 13220, 13235,
    13373, 13376, 13352, 13354, 13355, 13356, 13358, 13366, 13367,
    13306, 13307, 13312, 13313, 13329, 13316, 13328,
    13168, 13169, 13170, 13171, 13172, 13174, 13155, 13143, 13145, 13146, 13147, 13160, 13161, 13162, 13163, 13164,
]


def entity_rows(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entity in entities:
        rep = (entity.get("representative_by_zone") or {}).get("210") or {}
        rows.append({
            "entity_type": entity.get("entity_type"),
            "entity_id": entity.get("entity_id"),
            "name": entity.get("name"),
            "x": rep.get("x"),
            "y": rep.get("y"),
            "spawn_count": rep.get("spawn_count"),
        })
    return rows


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    by_id = {int(task["quest_id"]): task for task in foundation.get("tasks", [])}
    rows = []
    for qid in QUEST_IDS:
        task = by_id.get(qid)
        if not task:
            rows.append({"quest_id": qid, "missing": True})
            continue
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "scope_status": task.get("scope_status"),
            "scope_reasons": task.get("scope_reasons"),
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "next_quest": task.get("next_quest"),
            "child_quests": task.get("child_quests") or [],
            "available_starting_with": task.get("available_starting_with") or [],
            "disabled_by_quest": task.get("disabled_by_quest") or [],
            "objective_text_zh": task.get("objective_text_zh"),
            "task_class": task.get("task_class"),
            "task_flags": task.get("task_flags"),
            "objective_review": task.get("objective_review"),
            "objectives": [
                {
                    "objective_type": obj.get("objective_type"),
                    "required_count": obj.get("required_count"),
                    "item_id": obj.get("item_id"),
                    "item_name": obj.get("item_name"),
                    "sources": [
                        {
                            "entity_type": src.get("entity_type"),
                            "entity_id": src.get("entity_id"),
                            "name": src.get("name"),
                            "zones": src.get("zones"),
                            "representative": (src.get("representative_by_zone") or {}).get("210"),
                        }
                        for src in (obj.get("sources") or [])
                    ],
                }
                for obj in (task.get("objectives") or [])
            ],
            "start_entities": entity_rows(task.get("start_entities") or []),
            "finish_entities": entity_rows(task.get("finish_entities") or []),
            "level_80_economy": task.get("level_80_economy"),
            "intrinsic_service_time": task.get("intrinsic_service_time"),
        })
    OUT.write_text(json.dumps({"tasks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(OUT.relative_to(ROOT)),
        "tasks": [
            {
                "quest_id": row.get("quest_id"),
                "name": row.get("name"),
                "pre_any": row.get("pre_any"),
                "pre_all": row.get("pre_all"),
                "next_quest": row.get("next_quest"),
                "starts": row.get("start_entities"),
                "finishes": row.get("finish_entities"),
            }
            for row in rows
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
