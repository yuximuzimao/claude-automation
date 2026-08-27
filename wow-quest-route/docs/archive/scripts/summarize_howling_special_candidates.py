from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/howling-fjord-task-foundation.json"
OUT = ROOT / "data/route-atlas/howling-fjord-special-candidates.json"


def main() -> None:
    data = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in data.get("tasks", []):
        service = task.get("intrinsic_service_time") or {}
        mechanic_note = task.get("route_mechanism_note")
        if service.get("status") != "estimated" or mechanic_note:
            rows.append({
                "quest_id": int(task["quest_id"]),
                "name": task.get("name"),
                "task_class": task.get("task_class"),
                "service": service,
                "route_mechanism_note": mechanic_note,
                "objectives": [
                    {
                        "objective_type": obj.get("objective_type"),
                        "required_count": obj.get("required_count"),
                        "item_id": obj.get("item_id"),
                        "description": obj.get("description"),
                    }
                    for obj in (task.get("objectives") or [])
                ],
            })
    OUT.write_text(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "count": len(rows),
        "rows": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "task_class": row["task_class"],
                "service_status": row["service"].get("status"),
                "route_mechanism_note": row["route_mechanism_note"],
            }
            for row in rows
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
