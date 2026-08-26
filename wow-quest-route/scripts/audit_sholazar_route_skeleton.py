from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
OUT = ROOT / "data/route-atlas/sholazar-route-skeleton-audit.json"
ZONE_ID = 3711


def rep(entity: dict) -> tuple[float | None, float | None]:
    row = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
    return row.get("x"), row.get("y")


def anchors(entities: list[dict]) -> list[dict]:
    out = []
    for entity in entities or []:
        x, y = rep(entity)
        out.append({
            "name": entity.get("name"),
            "entity_id": entity.get("entity_id"),
            "x": x,
            "y": y,
        })
    return out


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    formal_ids = {int(q) for q in foundation.get("formal_task_ids", [])}
    rows = []
    for task in foundation.get("tasks", []):
        qid = int(task["quest_id"])
        if qid not in formal_ids:
            continue
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "next_quest": task.get("next_quest"),
            "scope_status": task.get("scope_status"),
            "start": anchors(task.get("start_entities") or []),
            "finish": anchors(task.get("finish_entities") or []),
            "objective_text_zh": task.get("objective_text_zh"),
            "fivebox_check": task.get("fivebox_check") or "",
            "mechanism_note": task.get("route_mechanism_note") or "",
        })

    # Pure spatial audit aid: coarse geographic bins for accept/turn-in anchors. This does not order quests.
    bins = {
        "west_nesingwary": [],
        "center_rivers_heart": [],
        "north_west": [],
        "north_center": [],
        "east": [],
        "south_west": [],
        "south_east": [],
        "unanchored": [],
    }
    for row in rows:
        points = [p for p in row["start"] + row["finish"] if isinstance(p.get("x"), (int, float)) and isinstance(p.get("y"), (int, float))]
        if not points:
            bins["unanchored"].append(row["quest_id"])
            continue
        x = sum(float(p["x"]) for p in points) / len(points)
        y = sum(float(p["y"]) for p in points) / len(points)
        if x < 40 and 48 <= y <= 70:
            key = "west_nesingwary"
        elif 40 <= x <= 60 and 50 <= y <= 72:
            key = "center_rivers_heart"
        elif x < 42 and y < 48:
            key = "north_west"
        elif 42 <= x <= 65 and y < 50:
            key = "north_center"
        elif x > 65 and y < 70:
            key = "east"
        elif x < 45 and y > 70:
            key = "south_west"
        else:
            key = "south_east"
        bins[key].append(row["quest_id"])

    payload = {
        "status": "spatial_audit_only_not_route_order",
        "formal_task_count": len(rows),
        "formal_task_ids": sorted(formal_ids),
        "coarse_bins": bins,
        "tasks": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "formal": len(rows),
        "bin_counts": {k: len(v) for k, v in bins.items()},
        "unanchored_ids": bins["unanchored"],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
