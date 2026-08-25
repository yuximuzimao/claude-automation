from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
ROUTE = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
OUT = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}


def step_text(step: dict) -> str:
    parts = [str(step.get("title") or ""), str(step.get("exit") or "")]
    parts.extend(str(value) for value in (step.get("actions") or []))
    for card in (step.get("task_cards") or {}).values():
        if not isinstance(card, dict):
            continue
        parts.extend(
            str(card.get(key) or "")
            for key in ("name", "objective", "route_note", "fivebox")
        )
    return "\n".join(parts)


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    tasks = [
        task for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    ]
    by_id = {int(task["quest_id"]): task for task in tasks}
    name_counts = Counter(str(task.get("name") or "") for task in tasks)

    steps = route.get("steps", [])
    text_by_step = {int(step["step"]): step_text(step) for step in steps}
    first_step: dict[int, int] = {}
    mention_steps: dict[int, list[int]] = {}

    for qid, task in by_id.items():
        name = str(task.get("name") or "")
        explicit_card_steps = [
            int(step["step"])
            for step in steps
            if str(qid) in (step.get("task_cards") or {})
        ]
        named_steps = []
        if name and name_counts[name] == 1:
            token = f"《{name}》"
            named_steps = [step_no for step_no, text in text_by_step.items() if token in text]
        all_steps = sorted(set(explicit_card_steps + named_steps))
        mention_steps[qid] = all_steps
        if all_steps:
            first_step[qid] = all_steps[0]

    missing_mentions = [
        {"quest_id": qid, "name": by_id[qid].get("name")}
        for qid in sorted(by_id)
        if qid not in first_step
    ]

    violations: list[dict] = []
    for qid in sorted(by_id):
        if qid not in first_step:
            continue
        task = by_id[qid]
        mandatory = set(int(value) for value in (task.get("pre_all") or []))
        mandatory |= set(int(value) for value in (task.get("parent_active") or []))
        pre_any = [int(value) for value in (task.get("pre_any") or [])]
        if len(pre_any) == 1:
            mandatory.add(pre_any[0])

        for dep in sorted(mandatory):
            if dep not in by_id or dep not in first_step:
                continue
            if first_step[dep] > first_step[qid]:
                violations.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "first_step": first_step[qid],
                    "dependency_id": dep,
                    "dependency_name": by_id[dep].get("name"),
                    "dependency_first_step": first_step[dep],
                    "kind": "mandatory_dependency_appears_later",
                })

        if len(pre_any) > 1:
            local_alternatives = [dep for dep in pre_any if dep in by_id and dep in first_step]
            if local_alternatives and all(first_step[dep] > first_step[qid] for dep in local_alternatives):
                violations.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "first_step": first_step[qid],
                    "dependency_ids": local_alternatives,
                    "dependency_steps": {str(dep): first_step[dep] for dep in local_alternatives},
                    "kind": "all_local_pre_any_alternatives_appear_later",
                })

    result = {
        "candidate_count": len(by_id),
        "route_step_count": len(steps),
        "mentioned_candidate_count": len(first_step),
        "missing_mention_count": len(missing_mentions),
        "dependency_order_violation_count": len(violations),
        "missing_mentions": missing_mentions,
        "violations": violations,
        "first_step_by_quest_id": {str(qid): first_step[qid] for qid in sorted(first_step)},
        "mention_steps_by_quest_id": {str(qid): mention_steps[qid] for qid in sorted(mention_steps)},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_count": result["candidate_count"],
        "route_step_count": result["route_step_count"],
        "mentioned_candidate_count": result["mentioned_candidate_count"],
        "missing_mention_count": result["missing_mention_count"],
        "dependency_order_violation_count": result["dependency_order_violation_count"],
        "violations": violations,
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
