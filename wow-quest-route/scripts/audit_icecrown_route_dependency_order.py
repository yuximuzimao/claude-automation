from __future__ import annotations

import json
import re
from pathlib import Path

from icecrown_route_task_index import build_route_task_index

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
ROUTE = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
OUT = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}
VERB_RE = re.compile(r"接|交|做|完成")
TASK_RE = re.compile(r"《([^》]+)》")


def parse_action_ops(route: dict, by_id: dict[int, dict]) -> tuple[list[dict], list[str]]:
    name_to_qid: dict[str, int] = {}
    duplicate_names: set[str] = set()
    for qid, task in by_id.items():
        name = str(task.get("name") or "")
        if name in name_to_qid and name_to_qid[name] != qid:
            duplicate_names.add(name)
        elif name:
            name_to_qid[name] = qid
    for name in duplicate_names:
        name_to_qid.pop(name, None)

    ops: list[dict] = []
    ordinal = 0
    for step in route.get("steps", []):
        step_no = int(step["step"])
        for line_index, line in enumerate(step.get("actions") or []):
            text = str(line)
            verbs = [(match.start(), match.group(0)) for match in VERB_RE.finditer(text)]
            for task_match in TASK_RE.finditer(text):
                qid = name_to_qid.get(task_match.group(1))
                prior = [item for item in verbs if item[0] < task_match.start()]
                if qid is None or not prior:
                    continue
                ops.append({
                    "ordinal": ordinal,
                    "step": step_no,
                    "line": line_index,
                    "verb": prior[-1][1],
                    "quest_id": qid,
                    "name": task_match.group(1),
                    "text": text,
                })
                ordinal += 1
    return ops, sorted(duplicate_names)


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    tasks = [
        task for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    ]
    by_id = {int(task["quest_id"]): task for task in tasks}
    steps = route.get("steps", [])
    route_index = build_route_task_index(tasks, route)
    first_step = route_index["first_step"]
    mention_steps = route_index["mention_steps"]
    missing_mentions = route_index["missing_mentions"]

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

    ops, duplicate_names = parse_action_ops(route, by_id)
    accepts: dict[int, list[dict]] = {qid: [] for qid in by_id}
    turns: dict[int, list[dict]] = {qid: [] for qid in by_id}
    for op in ops:
        if op["verb"] == "接":
            accepts[op["quest_id"]].append(op)
        elif op["verb"] == "交":
            turns[op["quest_id"]].append(op)

    exact_violations: list[dict] = []
    for qid, task in by_id.items():
        if not accepts[qid]:
            continue
        accept = accepts[qid][0]
        accept_ordinal = int(accept["ordinal"])
        parent_active = {
            int(dep) for dep in (task.get("parent_active") or [])
            if int(dep) in by_id
        }
        pre_any = [
            int(dep) for dep in (task.get("pre_any") or [])
            if int(dep) in by_id and int(dep) not in parent_active
        ]
        pre_all = [
            int(dep) for dep in (task.get("pre_all") or [])
            if int(dep) in by_id and int(dep) not in parent_active
        ]

        if pre_any and not any(turns[dep] and int(turns[dep][0]["ordinal"]) < accept_ordinal for dep in pre_any):
            exact_violations.append({
                "quest_id": qid,
                "name": task.get("name"),
                "kind": "pre_any_not_turned_in_before_accept",
                "dependency_ids": pre_any,
                "accept": accept,
            })
        missing_all = [
            dep for dep in pre_all
            if not turns[dep] or int(turns[dep][0]["ordinal"]) >= accept_ordinal
        ]
        if missing_all:
            exact_violations.append({
                "quest_id": qid,
                "name": task.get("name"),
                "kind": "pre_all_not_turned_in_before_accept",
                "dependency_ids": missing_all,
                "accept": accept,
            })
        for dep in sorted(parent_active):
            parent_accept = accepts[dep][0] if accepts[dep] else None
            parent_turn = turns[dep][0] if turns[dep] else None
            if parent_accept is None or int(parent_accept["ordinal"]) >= accept_ordinal:
                exact_violations.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "kind": "parent_not_active_before_accept",
                    "dependency_id": dep,
                    "accept": accept,
                })
            elif parent_turn is not None and int(parent_turn["ordinal"]) < accept_ordinal:
                exact_violations.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "kind": "parent_already_turned_in_before_accept",
                    "dependency_id": dep,
                    "accept": accept,
                })

    result = {
        "status": "PASS" if not missing_mentions and not violations and not exact_violations and not duplicate_names else "FAIL",
        "candidate_count": len(by_id),
        "route_step_count": len(steps),
        "mentioned_candidate_count": len(first_step),
        "missing_mention_count": len(missing_mentions),
        "parsed_action_operation_count": len(ops),
        "duplicate_task_names": duplicate_names,
        "step_dependency_order_violation_count": len(violations),
        "exact_dependency_order_violation_count": len(exact_violations),
        "dependency_order_violation_count": len(violations) + len(exact_violations),
        "missing_mentions": missing_mentions,
        "violations": violations,
        "exact_violations": exact_violations,
        "first_step_by_quest_id": {str(qid): first_step[qid] for qid in sorted(first_step)},
        "mention_steps_by_quest_id": {str(qid): mention_steps[qid] for qid in sorted(mention_steps)},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "route_step_count": result["route_step_count"],
        "mentioned_candidate_count": result["mentioned_candidate_count"],
        "missing_mention_count": result["missing_mention_count"],
        "parsed_action_operation_count": result["parsed_action_operation_count"],
        "dependency_order_violation_count": result["dependency_order_violation_count"],
        "step_violations": violations,
        "exact_violations": exact_violations,
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
