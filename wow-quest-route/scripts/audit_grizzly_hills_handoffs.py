from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
OUT = ROOT / "data/route-atlas/grizzly-hills-handoff-audit.json"


def compact_entity(entity: dict) -> dict:
    return {
        "name": entity.get("name"),
        "entity_type": entity.get("entity_type"),
        "entity_id": entity.get("entity_id"),
        "representative_by_zone": entity.get("representative_by_zone"),
    }


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in payload.get("tasks", []):
        rows.append({
            "quest_id": int(task.get("quest_id") or 0),
            "name": task.get("name"),
            "scope_status": task.get("scope_status"),
            "start_entities": [compact_entity(x) for x in task.get("start_entities", [])],
            "finish_entities": [compact_entity(x) for x in task.get("finish_entities", [])],
            "pre_any": task.get("pre_any", []),
            "pre_all": task.get("pre_all", []),
            "parent_active": task.get("parent_active", []),
            "next_quest": task.get("next_quest"),
        })
    rows.sort(key=lambda x: x["quest_id"])
    OUT.write_text(json.dumps({"row_count": len(rows), "tasks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
