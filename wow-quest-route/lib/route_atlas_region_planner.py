from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.route_atlas_cpsat import GlobalInstance, _travel_seconds


@dataclass
class RegionPlan:
    status: str
    action_order: list[str]
    total_seconds: float
    travel_seconds: float
    service_seconds: float
    region_visits: list[str]
    steps: list[dict[str, Any]]


def zangarmarsh_region(x: float, y: float) -> str:
    """Coarse first-run regions; intentionally macro, not terrain/pathfinding precision."""
    if x >= 72 and y >= 70:
        return "东南暗泽/孢子人营救区"
    if x >= 72 and y < 47:
        return "东北枯萎沼泽/沼牙区"
    if x >= 72:
        return "东部双营地"
    if x < 35 and y < 35:
        return "西北匕潭/安葛洛什区"
    if x < 25 and y >= 55:
        return "西南孢殖林/孢子村"
    if x < 38 and y >= 35:
        return "西部萨布拉金周边"
    if x < 58 and y >= 55:
        return "中西部蛮沼/博哈姆区"
    if x < 58:
        return "中北部湖西岸/泥爪区"
    if y < 50:
        return "中东北血鳞/蒸汽泵区"
    return "中东泻湖/蒸汽泵区"


def build_region_first_feasible_order(instance: GlobalInstance) -> RegionPlan:
    """First-run macro planner.

    It deliberately ignores fine-grained interleaving. At a visited macro region it repeatedly
    performs every currently legal local action before choosing the next region. The next region
    is selected by nearest available action. This is a heuristic for a smooth validation route,
    not an optimality proof.
    """
    inst = instance
    accepted: set[int] = set()
    turned: set[int] = set()
    completed: set[str] = set()
    used_accepts: set[str] = set()
    used_turnins: set[str] = set()
    triggered_accepts: set[str] = set()
    order: list[str] = []
    steps: list[dict[str, Any]] = []
    current = inst.start_xy
    current_region = zangarmarsh_region(*current)
    region_visits = [current_region]
    travel_total = 0.0
    service_total = 0.0

    def prereqs_ready(qid: int) -> bool:
        q = inst.quests[qid]
        if q.pre_all and not all(v in turned for v in q.pre_all):
            return False
        if q.pre_any and not any(v in turned for v in q.pre_any):
            return False
        return True

    def available() -> list[str]:
        out: list[str] = []
        for qid, q in inst.quests.items():
            if qid not in accepted and qid not in turned and prereqs_ready(qid):
                for aid in q.accept_actions:
                    if aid in used_accepts:
                        continue
                    if aid in inst.accept_trigger_actions and aid not in triggered_accepts:
                        continue
                    out.append(aid)
            if qid in accepted and qid not in turned and all(r in completed for r in q.requirement_ids):
                out.extend(t for t in q.turnin_actions if t not in used_turnins)
        for aid, action in inst.actions.items():
            if action.kind != "SERVICE":
                continue
            reqs = set(action.requirement_ids)
            if not reqs or reqs & completed:
                continue
            pre_q = set(action.pre_accept_quest_ids)
            normal_q = set(action.quest_ids) - pre_q
            if not all(q in accepted and q not in turned for q in normal_q):
                continue
            if not all(q not in accepted and q not in turned and prereqs_ready(q) for q in pre_q):
                continue
            if all(r not in completed for r in reqs):
                out.append(aid)
        return out

    def move_seconds(aid: str) -> float:
        action = inst.actions[aid]
        return _travel_seconds(
            current,
            (action.x, action.y),
            map_width_yards=inst.map_width_yards,
            map_height_yards=inst.map_height_yards,
            speed=inst.travel_speed_yards_per_sec,
        )

    guard = 0
    while len(turned) < len(inst.quests):
        guard += 1
        if guard > 5000:
            return RegionPlan("FAILED_GUARD", order, travel_total + service_total, travel_total, service_total, region_visits, steps)
        ready = available()
        if not ready:
            return RegionPlan("FAILED_DEAD_END", order, travel_total + service_total, travel_total, service_total, region_visits, steps)

        local = [aid for aid in ready if zangarmarsh_region(inst.actions[aid].x, inst.actions[aid].y) == current_region]
        if local:
            # Same-region actions: nearest first; at the same point prefer the widest shared service.
            chosen = min(
                local,
                key=lambda aid: (
                    move_seconds(aid) + float(inst.actions[aid].service_seconds) / max(1, len(inst.actions[aid].requirement_ids)),
                    move_seconds(aid),
                    -len(inst.actions[aid].requirement_ids),
                    aid,
                ),
            )
        else:
            # Leave the region only when there is no currently legal local closure left.
            chosen = min(
                ready,
                key=lambda aid: (
                    move_seconds(aid) + float(inst.actions[aid].service_seconds) / max(1, len(inst.actions[aid].requirement_ids)),
                    move_seconds(aid),
                    -len(inst.actions[aid].requirement_ids),
                    aid,
                ),
            )
            next_region = zangarmarsh_region(inst.actions[chosen].x, inst.actions[chosen].y)
            if next_region != current_region:
                current_region = next_region
                region_visits.append(current_region)

        action = inst.actions[chosen]
        move = move_seconds(chosen)
        travel_total += move
        service_total += float(action.service_seconds)
        current = (action.x, action.y)
        order.append(chosen)
        steps.append({
            "action_id": chosen,
            "type": action.kind,
            "name": action.name,
            "quest_ids": list(action.quest_ids),
            "requirement_ids": list(action.requirement_ids),
            "region": current_region,
            "x": action.x,
            "y": action.y,
            "travel_seconds": move,
            "service_seconds": float(action.service_seconds),
        })

        if action.kind == "ACCEPT":
            qid = action.quest_ids[0]
            accepted.add(qid)
            used_accepts.add(chosen)
        elif action.kind == "SERVICE":
            completed.update(action.requirement_ids)
            for accept_id, trigger_services in inst.accept_trigger_actions.items():
                if chosen in trigger_services:
                    triggered_accepts.add(accept_id)
        elif action.kind == "TURNIN":
            qid = action.quest_ids[0]
            accepted.discard(qid)
            turned.add(qid)
            used_turnins.add(chosen)

    return RegionPlan(
        "FEASIBLE_REGION_HEURISTIC",
        order,
        travel_total + service_total,
        travel_total,
        service_total,
        region_visits,
        steps,
    )
