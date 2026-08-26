from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
ICECROWN_OVERRIDES = ROOT / "data/route-atlas/icecrown-task-overrides.json"
OUT = ROOT / "data/route-atlas/cold-weather-flying-gate-audit.json"

# Current no-Cold-Weather-Flying master-axis zones where the K3 loaner is intended to provide
# physical flight capability. A cold-weather gate means the NPC checks the learned skill itself,
# so the loaner cannot satisfy that quest's availability condition.
ROUTE_ZONES = {67: "风暴峭壁", 210: "冰冠冰川", 3711: "索拉查盆地", 4395: "达拉然"}

# Some mandatory chains temporarily leave the Northrend universe. 12548《源生石像》
# sends the player through the Sholazar waygate into Un'Goro, where 12547《激活符文》
# is mandatory before 12797《界门的回程》 becomes available. Because 12547 is outside
# the Northrend task universe, normal dependency recursion cannot see this bridge.
# Verified against the WotLK quest chain; once 12548 is blocked, 12797 is blocked too,
# and ordinary recursion then blocks its Sholazar descendants such as 12546《力挽狂澜》.
EXTERNAL_DEPENDENCY_BRIDGES = {
    12797: {
        "blocked_if": 12548,
        "via": [12547],
        "basis": "12548 -> Un'Goro 12547 -> 12797 -> Sholazar",
    },
}


def dependency_blocked(task: dict[str, Any], blocked: set[int]) -> bool:
    pre_any = {int(qid) for qid in (task.get("pre_any") or [])}
    pre_all = {int(qid) for qid in (task.get("pre_all") or [])}
    parent = {int(qid) for qid in (task.get("parent_active") or [])}
    if pre_all & blocked or parent & blocked:
        return True
    return bool(pre_any and pre_any <= blocked)


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    tasks = {int(task["quest_id"]): dict(task) for task in universe.get("tasks", [])}
    overrides = json.loads(ICECROWN_OVERRIDES.read_text(encoding="utf-8"))
    for qid_text, override in (overrides.get("verified_hidden_dependencies") or {}).items():
        qid = int(qid_text)
        task = tasks.get(qid)
        if not task:
            continue
        for field in ("pre_any", "pre_all", "parent_active"):
            if field not in override:
                continue
            merged = [int(x) for x in (task.get(field) or [])]
            for dep in override.get(field) or []:
                dep = int(dep)
                if dep not in merged:
                    merged.append(dep)
            task[field] = merged
        task["verified_hidden_dependency"] = override

    direct = {
        qid
        for qid, task in tasks.items()
        if task.get("assigned_zone_id") in ROUTE_ZONES and task.get("cold_weather_flying_gate")
    }
    horde_direct = {
        qid
        for qid in direct
        if tasks[qid].get("race_allowed") and tasks[qid].get("npc_faction_allowed") and tasks[qid].get("class_allowed")
    }

    blocked = set(horde_direct)
    external_bridge_blocks: list[dict[str, Any]] = []
    changed = True
    while changed:
        changed = False
        for downstream, bridge in EXTERNAL_DEPENDENCY_BRIDGES.items():
            upstream = int(bridge["blocked_if"])
            if upstream in blocked and downstream in tasks and downstream not in blocked:
                blocked.add(downstream)
                external_bridge_blocks.append({
                    "quest_id": downstream,
                    "name": tasks[downstream].get("name"),
                    "blocked_if": upstream,
                    "via": [int(x) for x in bridge.get("via", [])],
                    "basis": bridge.get("basis"),
                })
                changed = True
        for qid, task in tasks.items():
            if qid in blocked or task.get("assigned_zone_id") not in ROUTE_ZONES:
                continue
            if not task.get("race_allowed") or not task.get("npc_faction_allowed") or not task.get("class_allowed"):
                continue
            if dependency_blocked(task, blocked):
                blocked.add(qid)
                changed = True

    def row(qid: int, reason: str) -> dict[str, Any]:
        task = tasks[qid]
        return {
            "quest_id": qid,
            "name": task.get("name"),
            "zone_id": task.get("assigned_zone_id"),
            "zone_name": ROUTE_ZONES.get(task.get("assigned_zone_id")),
            "required_level": task.get("required_level"),
            "quest_level": task.get("quest_level"),
            "required_spell": task.get("required_spell"),
            "cold_weather_flying_gate_source": task.get("cold_weather_flying_gate_source"),
            "reason": reason,
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
        }

    payload = {
        "status": "current_no_cold_weather_flying_route_policy",
        "policy": {
            "learn_cold_weather_flying": False,
            "loaner_mount_zones": [67, 210, 3711],
            "rule": "exclude learned-skill gates; keep quests that merely need physical flight because the K3 loaner can satisfy travel",
        },
        "all_direct_gate_ids": sorted(direct),
        "horde_paladin_direct_gate_ids": sorted(horde_direct),
        "horde_paladin_blocked_ids_with_exclusive_descendants": sorted(blocked),
        "external_dependency_bridge_blocks": external_bridge_blocks,
        "direct_gates": [row(qid, "direct_cold_weather_flying_gate") for qid in sorted(horde_direct)],
        "dependency_blocked": [
            row(qid, "exclusive_dependency_on_cold_weather_flying_blocked_chain")
            for qid in sorted(blocked - horde_direct)
        ],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "all_direct": sorted(direct),
        "horde_direct": sorted(horde_direct),
        "blocked_total": len(blocked),
        "blocked_by_zone": {
            ROUTE_ZONES[zid]: sum(1 for qid in blocked if tasks[qid].get("assigned_zone_id") == zid)
            for zid in ROUTE_ZONES
        },
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
