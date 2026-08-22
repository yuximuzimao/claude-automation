from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OUT = ROOT / "data/route-atlas/cold-weather-flying-gate-audit.json"

# Current no-Cold-Weather-Flying master-axis zones where the K3 loaner is intended to provide
# physical flight capability. A cold-weather gate means the NPC checks the learned skill itself,
# so the loaner cannot satisfy that quest's availability condition.
ROUTE_ZONES = {67: "风暴峭壁", 210: "冰冠冰川", 3711: "索拉查盆地", 4395: "达拉然"}


def dependency_blocked(task: dict[str, Any], blocked: set[int]) -> bool:
    pre_any = {int(qid) for qid in (task.get("pre_any") or [])}
    pre_all = {int(qid) for qid in (task.get("pre_all") or [])}
    parent = {int(qid) for qid in (task.get("parent_active") or [])}
    if pre_all & blocked or parent & blocked:
        return True
    return bool(pre_any and pre_any <= blocked)


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    tasks = {int(task["quest_id"]): task for task in universe.get("tasks", [])}

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
    changed = True
    while changed:
        changed = False
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
