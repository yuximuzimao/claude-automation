from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/route-atlas/flight-state-audit.json"
CONFIG = ROOT / "data/route-atlas/route-atlas-flight-state-config.json"

# Hub aliases and inherited opened-flight state are route facts, not audit-engine logic.
# The engine consumes the explicit RouteState configuration above.


def point_text(point: list[Any]) -> str:
    return " ".join(str(value or "") for value in point[2:6])


def mentioned_hubs(text: str, aliases: dict[str, tuple[str, ...]]) -> list[str]:
    matches: list[tuple[int, str]] = []
    for canonical, names in aliases.items():
        last = max((text.rfind(alias) for alias in names), default=-1)
        if last >= 0:
            matches.append((last, canonical))
    matches.sort()
    return [canonical for _, canonical in matches]


def opened_hubs_from_text(text: str, aliases: dict[str, tuple[str, ...]]) -> list[str]:
    if "飞行点" not in text or not any(token in text for token in ("开启", "开飞行点", "开点")):
        return []
    return mentioned_hubs(text, aliases)


def flight_destination(point: list[Any], aliases: dict[str, tuple[str, ...]]) -> str | None:
    label = str(point[2] if len(point) > 2 else "")
    if "→" in label:
        arrow_target = label.rsplit("→", 1)[-1]
        hubs = mentioned_hubs(arrow_target, aliases)
        if hubs:
            return hubs[-1]

    text = point_text(point)
    hubs = mentioned_hubs(text, aliases)
    if not hubs:
        return None
    return hubs[-1]


def audit_route(route_key: str, route: dict[str, Any], route_config: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        str(canonical): tuple(str(alias) for alias in names)
        for canonical, names in (route_config.get("hub_aliases") or {}).items()
    }
    opened: set[str] = {str(name) for name in (route_config.get("initial_opened_hubs") or [])}
    flights: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    unknown_destinations: list[dict[str, Any]] = []

    for index, point in enumerate(route.get("points", [])):
        text = point_text(point)
        opened_before = sorted(opened)
        transport = str(point[6] if len(point) > 6 and point[6] else "ride")
        # Transport metadata is authoritative. For legacy rows without taxi metadata, only the
        # step label/action may imply an actual flight; notes about *future* flight availability must not.
        action_text = " ".join(str(value or "") for value in point[2:4])
        is_system_flight = transport == "taxi" or (transport != "crossmap" and any(token in action_text for token in ("系统鸟", "系统航线", "系统飞行")))

        if is_system_flight:
            destination = flight_destination(point, aliases)
            row = {
                "point_index": index,
                "label": point[2] if len(point) > 2 else "",
                "action": point[3] if len(point) > 3 else "",
                "transport": transport,
                "destination_hub": destination,
                "opened_before_arrival": opened_before,
            }
            flights.append(row)
            if destination is None:
                unknown_destinations.append(row)
            elif destination not in opened:
                violations.append(row)

        # Opening a destination on arrival affects only later flight edges, never the edge
        # used to reach this point.
        for hub in opened_hubs_from_text(text, aliases):
            opened.add(hub)

    return {
        "route_key": route_key,
        "flight_count": len(flights),
        "violation_count": len(violations),
        "unknown_destination_count": len(unknown_destinations),
        "flights": flights,
        "violations": violations,
        "unknown_destinations": unknown_destinations,
        "final_opened_flight_points": sorted(opened),
    }


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    route_configs = config.get("routes") or {}
    result = {
        "status": "route_timepoint_flight_state_audit",
        "rule": "A system-flight destination may be used only after that destination flight point has been opened earlier in the route timeline.",
        "routes": {
            key: audit_route(key, routes[key], route_config)
            for key, route_config in route_configs.items()
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        key: {
            "flight_count": row["flight_count"],
            "violation_count": row["violation_count"],
            "unknown_destination_count": row["unknown_destination_count"],
            "violations": [
                {
                    "point_index": item["point_index"],
                    "label": item["label"],
                    "destination_hub": item["destination_hub"],
                    "opened_before_arrival": item["opened_before_arrival"],
                }
                for item in row["violations"]
            ],
        }
        for key, row in result["routes"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if any(row["unknown_destination_count"] for row in result["routes"].values()):
        raise SystemExit("Flight-state audit has unknown flight destinations; add an explicit hub alias before trusting the result.")
    if any(row["violation_count"] for row in result["routes"].values()):
        raise SystemExit("Flight-state audit found a system flight whose destination had not been opened earlier in the route timeline.")


if __name__ == "__main__":
    main()
