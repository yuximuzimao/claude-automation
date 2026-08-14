from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.route_atlas_cpsat import GlobalInstance, _travel_seconds


@dataclass
class InitialSolution:
    status: str
    action_order: list[str]
    total_seconds: float
    travel_seconds: float
    service_seconds: float
    steps: list[dict[str, Any]]


def build_greedy_feasible_order(instance: GlobalInstance) -> InitialSolution:
    """Construct a deterministic feasible order for warm-starting exact solvers.

    This is deliberately a heuristic and MUST NOT be presented as an optimized route. It only
    produces a complete feasible incumbent. Every action is checked against the same hard quest
    prerequisites and exact-cover semantics as the global model.
    """
    inst = instance
    accepted: set[int] = set()
    turned: set[int] = set()
    completed_requirements: set[str] = set()
    chosen_accept: dict[int, str] = {}
    chosen_turnin: dict[int, str] = {}
    triggered_accepts: set[str] = set()
    order: list[str] = []
    steps: list[dict[str, Any]] = []
    current = inst.start_xy
    travel_total = 0.0
    service_total = 0.0

    def prereqs_ready(qid: int) -> bool:
        q = inst.quests[qid]
        if q.pre_all and not all(p in turned for p in q.pre_all):
            return False
        if q.pre_any and not any(p in turned for p in q.pre_any):
            return False
        return True

    def available_actions() -> list[str]:
        result: list[str] = []
        for qid, q in inst.quests.items():
            if qid not in accepted and qid not in turned and prereqs_ready(qid):
                for aid in q.accept_actions:
                    if aid in chosen_accept.values():
                        continue
                    if aid in inst.accept_trigger_actions and aid not in triggered_accepts:
                        continue
                    result.append(aid)
            if qid in accepted and qid not in turned:
                if all(rid in completed_requirements for rid in q.requirement_ids):
                    result.extend(t for t in q.turnin_actions if t not in chosen_turnin.values())

        for aid, action in inst.actions.items():
            if action.kind != "SERVICE":
                continue
            reqs = set(action.requirement_ids)
            if not reqs or reqs & completed_requirements:
                continue
            pre_accept_qids = set(action.pre_accept_quest_ids)
            ordinary_qids = set(action.quest_ids) - pre_accept_qids
            if not all(qid in accepted and qid not in turned for qid in ordinary_qids):
                continue
            if not all(
                qid not in accepted and qid not in turned and prereqs_ready(qid)
                for qid in pre_accept_qids
            ):
                continue
            # The candidate must cover only currently unfinished requirements. Because exact-cover
            # equations select one action per requirement, any overlap with a finished requirement
            # would make this shared candidate unavailable.
            if all(rid not in completed_requirements for rid in reqs):
                result.append(aid)
        return result

    total_needed = len(inst.quests) * 2 + len(inst.requirement_actions)
    guard = 0
    while len(turned) < len(inst.quests):
        guard += 1
        if guard > total_needed * 5 + 100:
            return InitialSolution(
                status="FAILED_GUARD",
                action_order=order,
                total_seconds=travel_total + service_total,
                travel_seconds=travel_total,
                service_seconds=service_total,
                steps=steps,
            )
        available = available_actions()
        if not available:
            return InitialSolution(
                status="FAILED_DEAD_END",
                action_order=order,
                total_seconds=travel_total + service_total,
                travel_seconds=travel_total,
                service_seconds=service_total,
                steps=steps,
            )

        scored: list[tuple[float, float, float, int, str]] = []
        for aid in available:
            action = inst.actions[aid]
            move = _travel_seconds(
                current,
                (action.x, action.y),
                map_width_yards=inst.map_width_yards,
                map_height_yards=inst.map_height_yards,
                speed=inst.travel_speed_yards_per_sec,
            )
            service = float(action.service_seconds)
            # Zero-movement accepts/turn-ins naturally win. For service ties, a shared candidate
            # covering more requirements is preferred because it cannot cost more than doing the
            # same covered streams separately under the current max-service semantics.
            batch = len(action.requirement_ids)
            scored.append((move + service, move, service, -batch, aid))
        _, move, service, _, chosen = min(scored)
        action = inst.actions[chosen]

        travel_total += move
        service_total += service
        order.append(chosen)
        steps.append({
            "action_id": chosen,
            "type": action.kind,
            "name": action.name,
            "quest_ids": list(action.quest_ids),
            "requirement_ids": list(action.requirement_ids),
            "travel_seconds": move,
            "service_seconds": service,
        })
        current = (action.x, action.y)

        if action.kind == "ACCEPT":
            qid = action.quest_ids[0]
            accepted.add(qid)
            chosen_accept[qid] = chosen
        elif action.kind == "SERVICE":
            completed_requirements.update(action.requirement_ids)
            for accept_id, trigger_services in inst.accept_trigger_actions.items():
                if chosen in trigger_services:
                    triggered_accepts.add(accept_id)
        elif action.kind == "TURNIN":
            qid = action.quest_ids[0]
            accepted.discard(qid)
            turned.add(qid)
            chosen_turnin[qid] = chosen
        else:
            raise ValueError(f"Unsupported action kind in initial solver: {action.kind}")

    if len(completed_requirements) != len(inst.requirement_actions):
        return InitialSolution(
            status="FAILED_REQUIREMENT_COVERAGE",
            action_order=order,
            total_seconds=travel_total + service_total,
            travel_seconds=travel_total,
            service_seconds=service_total,
            steps=steps,
        )

    return InitialSolution(
        status="FEASIBLE_HEURISTIC",
        action_order=order,
        total_seconds=travel_total + service_total,
        travel_seconds=travel_total,
        service_seconds=service_total,
        steps=steps,
    )
