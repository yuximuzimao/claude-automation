from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/route-atlas/objective-anchor-audit.json"

ROUTE_FOUNDATIONS: dict[str, tuple[Path, int]] = {
    "storm": (ROOT / "data/route-atlas/storm-peaks-task-foundation.json", 67),
}

DO_RE = re.compile(r"做《([^》]+)》")
WARN_DISTANCE = 5.0
FAIL_DISTANCE = 8.0


def objective_sources(objective: dict[str, Any], zone_id: int) -> list[tuple[float, float, str]]:
    rows: list[tuple[float, float, str]] = []
    for source in objective.get("sources") or []:
        rep = (source.get("representative_by_zone") or {}).get(str(zone_id)) or {}
        if rep.get("x") is None or rep.get("y") is None:
            continue
        rows.append((float(rep["x"]), float(rep["y"]), str(source.get("name") or "")))
    return rows


def audit_route(route_key: str, route: dict[str, Any], foundation_path: Path, zone_id: int) -> dict[str, Any]:
    foundation = json.loads(foundation_path.read_text(encoding="utf-8"))
    tasks_by_name = {
        str(task["name"]): task
        for task in foundation.get("tasks", [])
        if str(task.get("scope_status") or "").startswith("include")
    }

    execution_points: dict[str, list[tuple[float, float, int, str]]] = {}
    for index, point in enumerate(route.get("points", [])):
        action = str(point[3] if len(point) > 3 else "")
        for task_name in DO_RE.findall(action):
            execution_points.setdefault(task_name, []).append(
                (float(point[0]), float(point[1]), index, str(point[2]))
            )

    rows: list[dict[str, Any]] = []
    for task_name, points in execution_points.items():
        task = tasks_by_name.get(task_name)
        if not task:
            continue
        for objective_index, objective in enumerate(task.get("objectives") or [], start=1):
            sources = objective_sources(objective, zone_id)
            if not sources:
                continue
            candidates: list[tuple[float, int, str, str, float, float]] = []
            for px, py, point_index, point_title in points:
                for sx, sy, source_name in sources:
                    candidates.append(
                        (
                            math.hypot(px - sx, py - sy),
                            point_index,
                            point_title,
                            source_name,
                            sx,
                            sy,
                        )
                    )
            distance, point_index, point_title, source_name, source_x, source_y = min(candidates)
            status = "pass"
            if distance > FAIL_DISTANCE:
                status = "fail"
            elif distance > WARN_DISTANCE:
                status = "review"
            rows.append(
                {
                    "quest_id": int(task["quest_id"]),
                    "quest_name": task_name,
                    "objective_index": objective_index,
                    "objective_type": objective.get("objective_type"),
                    "required_count": objective.get("required_count"),
                    "nearest_route_point_index": point_index,
                    "nearest_route_point_title": point_title,
                    "nearest_source_name": source_name,
                    "nearest_source_x": source_x,
                    "nearest_source_y": source_y,
                    "distance": round(distance, 2),
                    "status": status,
                }
            )

    failures = [row for row in rows if row["status"] == "fail"]
    reviews = [row for row in rows if row["status"] == "review"]
    return {
        "route_key": route_key,
        "zone_id": zone_id,
        "warn_distance": WARN_DISTANCE,
        "fail_distance": FAIL_DISTANCE,
        "objective_rows": len(rows),
        "failure_count": len(failures),
        "review_count": len(reviews),
        "failures": failures,
        "reviews": reviews,
    }


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    result = {
        "status": "objective_anchor_distance_audit",
        "rule": "Every geolocatable objective must be near at least one route point where that quest is executed. Distances >8 are hard failures; >5 require manual review.",
        "routes": {},
    }
    for route_key, (foundation_path, zone_id) in ROUTE_FOUNDATIONS.items():
        result["routes"][route_key] = audit_route(
            route_key,
            routes[route_key],
            foundation_path,
            zone_id,
        )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: {
            "objective_rows": row["objective_rows"],
            "failure_count": row["failure_count"],
            "review_count": row["review_count"],
            "failures": row["failures"],
            "reviews": row["reviews"],
        }
        for key, row in result["routes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["failure_count"] for row in result["routes"].values()):
        raise SystemExit("Objective-anchor audit found route execution points too far from their quest objectives.")


if __name__ == "__main__":
    main()
