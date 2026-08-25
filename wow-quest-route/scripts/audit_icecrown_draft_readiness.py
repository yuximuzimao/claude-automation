from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
ROUTE = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
DEPENDENCY_AUDIT = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
OUT = ROOT / "data/route-atlas/icecrown-draft-readiness-audit.json"
ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}


def has_xy(rep: Any) -> bool:
    return isinstance(rep, dict) and isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float))


def has_objective_anchor(task: dict[str, Any]) -> bool:
    for objective in task.get("objectives") or []:
        for source in objective.get("sources") or []:
            if any(has_xy(rep) for rep in (source.get("representative_by_zone") or {}).values()):
                return True
    for extra in task.get("extra_objectives") or []:
        if any((extra.get("coordinates_by_zone") or {}).values()):
            return True
        for source in extra.get("references") or []:
            if any(has_xy(rep) for rep in (source.get("representative_by_zone") or {}).values()):
                return True
    return False


def route_cards_by_qid(route: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for step in route.get("steps", []):
        for raw_qid, card in (step.get("task_cards") or {}).items():
            try:
                qid = int(raw_qid)
            except (TypeError, ValueError):
                continue
            result.setdefault(qid, []).append({"step": int(step["step"]), **(card or {})})
    return result


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    dependency = json.loads(DEPENDENCY_AUDIT.read_text(encoding="utf-8"))
    first_step = {int(qid): int(step) for qid, step in (dependency.get("first_step_by_quest_id") or {}).items()}
    cards = route_cards_by_qid(route)
    steps_by_number = {int(step["step"]): step for step in route.get("steps", [])}

    tasks = [task for task in foundation.get("tasks", []) if task.get("scope_status") in ROUTE_STATUSES]
    by_id = {int(task["quest_id"]): task for task in tasks}
    rows: list[dict[str, Any]] = []

    for qid in sorted(by_id):
        task = by_id[qid]
        risks: list[str] = []
        service = task.get("intrinsic_service_time") or {}
        if service.get("status") != "estimated" or not isinstance(service.get("minutes"), (int, float)):
            risks.append("unknown_service_time")
        if task.get("objective_review") and not task.get("objective_review_resolution"):
            risks.append("objective_mechanic_review")
        objectives = task.get("objectives") or []
        extra_objectives = task.get("extra_objectives") or []
        if (objectives or extra_objectives) and not has_objective_anchor(task) and not task.get("manual_spatial_resolution"):
            risks.append("missing_objective_anchor")

        route_cards = cards.get(qid, [])
        fivebox_checks = [
            str(card.get("fivebox") or "")
            for card in route_cards
            if "待实测" in str(card.get("fivebox") or "")
        ]
        if fivebox_checks:
            risks.append("fivebox_live_check")

        econ = task.get("level_80_economy") or {}
        if (
            int(econ.get("xp_bonus_money_copper") or 0) == 0
            and int(econ.get("equipment_reward_count") or 0) == 0
            and int(econ.get("other_reward_item_count") or 0) == 0
            and int(econ.get("direct_money_copper") or 0) == 0
        ):
            risks.append("economy_reward_review")

        rows.append(
            {
                "quest_id": qid,
                "name": task.get("name"),
                "first_step": first_step.get(qid),
                "step_title": (steps_by_number.get(first_step.get(qid, -1)) or {}).get("title"),
                "risks": risks,
                "risk_count": len(risks),
                "objective_review": task.get("objective_review") or [],
                "service": service,
                "route_card_steps": [card["step"] for card in route_cards],
                "fivebox_checks": fivebox_checks,
                "scope_origin": task.get("scope_origin"),
            }
        )

    step_rows: list[dict[str, Any]] = []
    for step_no in sorted(steps_by_number):
        quest_rows = [row for row in rows if row.get("first_step") == step_no]
        risk_counter = Counter(risk for row in quest_rows for risk in row["risks"])
        risky = [row for row in quest_rows if row["risks"]]
        step_rows.append(
            {
                "step": step_no,
                "title": steps_by_number[step_no].get("title"),
                "quest_count": len(quest_rows),
                "risky_quest_count": len(risky),
                "risk_count": sum(row["risk_count"] for row in risky),
                "risk_types": dict(sorted(risk_counter.items())),
                "risky_quests": [
                    {"quest_id": row["quest_id"], "name": row["name"], "risks": row["risks"]}
                    for row in risky
                ],
            }
        )

    risk_counts = Counter(risk for row in rows for risk in row["risks"])
    priority_steps = sorted(
        [step for step in step_rows if step["risk_count"] > 0],
        key=lambda step: (-step["risk_count"], -step["risky_quest_count"], step["step"]),
    )
    result = {
        "candidate_count": len(rows),
        "route_step_count": len(step_rows),
        "risky_candidate_count": sum(bool(row["risks"]) for row in rows),
        "risk_counts": dict(sorted(risk_counts.items())),
        "priority_steps": priority_steps,
        "steps": step_rows,
        "tasks": rows,
        "note": "Readiness flags are review triggers, not proof that a route step is wrong. Clear them with task facts, route notes, source verification or live five-box evidence before formal publication.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "route_step_count": result["route_step_count"],
                "risky_candidate_count": result["risky_candidate_count"],
                "risk_counts": result["risk_counts"],
                "top_priority_steps": [
                    {
                        "step": step["step"],
                        "title": step["title"],
                        "risk_count": step["risk_count"],
                        "risky_quest_count": step["risky_quest_count"],
                        "risk_types": step["risk_types"],
                    }
                    for step in priority_steps[:10]
                ],
                "output": str(OUT.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
