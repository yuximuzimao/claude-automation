from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
FOUNDATION = ROOT / "data/route-atlas/borean-tundra-task-foundation.json"
OUT = ROOT / "data/route-atlas/borean-amber-bogorok-corridor-audit.json"
ZONE_ID = 3537
AMBER_POINT_INDEX = 169
BOGOROK_POINT_INDEX = 170
CORRIDOR_BUFFER_MAP_PERCENT = 6.0
ENDPOINT_RADIUS_MAP_PERCENT = 3.0


def distance_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    if denom <= 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy)


def route_first_point_by_quest_name(route: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, point in enumerate(route.get("points", [])):
        text = " ".join(str(value or "") for value in point[2:6])
        for name in re.findall(r"《([^》]+)》", text):
            result.setdefault(name, index)
    return result


def quest_state_before_point(route: dict[str, Any], end_exclusive: int) -> tuple[set[str], set[str]]:
    accepted: set[str] = set()
    completed: set[str] = set()
    for point in route.get("points", [])[:end_exclusive]:
        text = " ".join(str(value or "") for value in point[2:6])
        accepted.update(re.findall(r"接《([^》]+)》", text))
        completed.update(re.findall(r"交《([^》]+)》", text))
    return accepted, completed


def start_locations(task: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entity in task.get("start_entities") or []:
        rep = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID))
        if not isinstance(rep, dict):
            continue
        x, y = rep.get("x"), rep.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        result.append({
            "entity_type": entity.get("entity_type"),
            "entity_id": entity.get("entity_id"),
            "entity_name": entity.get("name"),
            "x": float(x),
            "y": float(y),
        })
    return result


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["borean"]
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    first_point = route_first_point_by_quest_name(route)
    accepted_before, completed_before = quest_state_before_point(route, AMBER_POINT_INDEX)
    by_id = {int(task["quest_id"]): task for task in foundation.get("tasks", [])}

    amber = route["points"][AMBER_POINT_INDEX]
    bogorok = route["points"][BOGOROK_POINT_INDEX]
    ax, ay = float(amber[0]), float(amber[1])
    bx, by = float(bogorok[0]), float(bogorok[1])

    corridor: list[dict[str, Any]] = []
    for task in foundation.get("tasks", []):
        if not task.get("is_primary_candidate"):
            continue
        status = str(task.get("scope_status") or "")
        if not (status.startswith("include_") or status == "defer_future_level_revisit"):
            continue
        for loc in start_locations(task):
            distance = distance_to_segment(loc["x"], loc["y"], ax, ay, bx, by)
            if distance > CORRIDOR_BUFFER_MAP_PERCENT:
                continue
            endpoint_distance = math.hypot(loc["x"] - bx, loc["y"] - by)
            route_point = first_point.get(str(task.get("name") or ""))
            pre_all = [int(qid) for qid in task.get("pre_all") or [] if isinstance(qid, int)]
            pre_any = [int(qid) for qid in task.get("pre_any") or [] if isinstance(qid, int)]
            parent_active = [int(qid) for qid in task.get("parent_active") or [] if isinstance(qid, int)]
            available_starting_with = [int(qid) for qid in task.get("available_starting_with") or [] if isinstance(qid, int)]

            def dep_rows(ids: list[int]) -> list[dict[str, Any]]:
                result: list[dict[str, Any]] = []
                for qid in ids:
                    dep = by_id.get(qid, {})
                    dep_name = str(dep.get("name") or qid)
                    result.append({
                        "quest_id": qid,
                        "name": dep_name,
                        "accepted_before_corridor": dep_name in accepted_before,
                        "completed_before_corridor": dep_name in completed_before,
                    })
                return result

            pre_all_rows = dep_rows(pre_all)
            pre_any_rows = dep_rows(pre_any)
            parent_active_rows = dep_rows(parent_active)
            starting_rows = dep_rows(available_starting_with)
            mandatory_completed = all(row["completed_before_corridor"] for row in pre_all_rows)
            any_completed = not pre_any_rows or any(row["completed_before_corridor"] for row in pre_any_rows)
            parent_active_ready = all(
                row["accepted_before_corridor"] and not row["completed_before_corridor"]
                for row in parent_active_rows
            )
            starting_ready = all(row["completed_before_corridor"] for row in starting_rows)
            prerequisite_evidence_ready = mandatory_completed and any_completed and parent_active_ready and starting_ready

            corridor.append({
                "quest_id": int(task["quest_id"]),
                "name": task["name"],
                "scope_status": status,
                "required_level": task.get("required_level"),
                "quest_level": task.get("quest_level"),
                "start": loc,
                "distance_to_direct_corridor": round(distance, 2),
                "distance_to_bogorok_endpoint": round(endpoint_distance, 2),
                "at_bogorok_endpoint": endpoint_distance <= ENDPOINT_RADIUS_MAP_PERCENT,
                "first_route_point": route_point,
                "already_routed_before_corridor": route_point is not None and route_point < AMBER_POINT_INDEX,
                "routed_at_or_after_corridor": route_point is not None and route_point >= AMBER_POINT_INDEX,
                "prerequisite_evidence_ready": prerequisite_evidence_ready,
                "dependencies": {
                    "pre_all": pre_all_rows,
                    "pre_any": pre_any_rows,
                    "parent_active": parent_active_rows,
                    "available_starting_with": starting_rows,
                },
            })

    corridor.sort(key=lambda row: (row["distance_to_direct_corridor"], row["quest_id"]))
    interior = [row for row in corridor if not row["at_bogorok_endpoint"]]
    scheduled_later_interior = [row for row in interior if row["routed_at_or_after_corridor"]]
    outstanding_interior = [
        row for row in interior
        if row["first_route_point"] is None and row["prerequisite_evidence_ready"]
    ]
    endpoint = [row for row in corridor if row["at_bogorok_endpoint"]]

    result = {
        "status": "amber_ledge_to_bogorok_forced_ground_corridor_audit",
        "route_key": "borean",
        "segment": {
            "from_point": AMBER_POINT_INDEX,
            "from_label": amber[2],
            "from": {"x": ax, "y": ay},
            "to_point": BOGOROK_POINT_INDEX,
            "to_label": bogorok[2],
            "to": {"x": bx, "y": by},
            "buffer_map_percent": CORRIDOR_BUFFER_MAP_PERCENT,
            "endpoint_radius_map_percent": ENDPOINT_RADIUS_MAP_PERCENT,
        },
        "interpretation": "Quest-giver/object starts near the straight route edge are screened. Bogorok endpoint tasks are separated from true in-between opportunities; tasks already routed before this segment are not new pickups.",
        "interior_candidates": interior,
        "scheduled_later_interior_candidates": scheduled_later_interior,
        "outstanding_interior_candidates": outstanding_interior,
        "bogorok_endpoint_candidates": endpoint,
        "summary": {
            "corridor_task_starts": len(corridor),
            "interior_task_starts": len(interior),
            "scheduled_later_interior_task_starts": len(scheduled_later_interior),
            "outstanding_interior_task_starts": len(outstanding_interior),
            "bogorok_endpoint_task_starts": len(endpoint),
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "summary": result["summary"],
        "outstanding_interior": [
            {"quest_id": row["quest_id"], "name": row["name"], "start": row["start"], "distance": row["distance_to_direct_corridor"]}
            for row in outstanding_interior
        ],
        "endpoint": [
            {"quest_id": row["quest_id"], "name": row["name"], "first_route_point": row["first_route_point"]}
            for row in endpoint
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
