from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT = ROOT / "data/route-atlas/icecrown-deaths-rise-trace.json"
ROUTE_STATUSES = {"include_candidate", "include_conditional_route_state", "include_first_run_repeatable_or_calendar"}
ROOT_ID = 12806
MAX_DEPTH = 14


def rep(entity: dict) -> dict:
    r = (entity.get("representative_by_zone") or {}).get("210") or {}
    return {"name": entity.get("name"), "entity_type": entity.get("entity_type"), "entity_id": entity.get("entity_id"), "x": r.get("x"), "y": r.get("y")}


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = [t for t in payload.get("tasks", []) if t.get("scope_status") in ROUTE_STATUSES]
    by_id = {int(t["quest_id"]): t for t in tasks}
    children: dict[int, set[int]] = defaultdict(set)
    for qid, task in by_id.items():
        deps = set(int(x) for x in (task.get("pre_any") or []))
        deps |= set(int(x) for x in (task.get("pre_all") or []))
        deps |= set(int(x) for x in (task.get("parent_active") or []))
        for dep in deps:
            if dep in by_id:
                children[dep].add(qid)
        nq = task.get("next_quest")
        if isinstance(nq, int) and nq in by_id:
            children[qid].add(nq)

    depth = {ROOT_ID: 0}
    queue = deque([ROOT_ID])
    while queue:
        qid = queue.popleft()
        if depth[qid] >= MAX_DEPTH:
            continue
        for nxt in sorted(children.get(qid, [])):
            if nxt not in depth:
                depth[nxt] = depth[qid] + 1
                queue.append(nxt)

    rows = []
    for qid in sorted(depth, key=lambda q: (depth[q], q)):
        task = by_id[qid]
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "depth": depth[qid],
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "next_quest": task.get("next_quest"),
            "child_quests": task.get("child_quests") or [],
            "is_daily": task.get("is_daily"),
            "is_repeatable": task.get("is_repeatable"),
            "objective_text_zh": task.get("objective_text_zh"),
            "task_class": task.get("task_class"),
            "task_flags": task.get("task_flags"),
            "objective_review": task.get("objective_review"),
            "starts": [rep(e) for e in (task.get("start_entities") or [])],
            "finishes": [rep(e) for e in (task.get("finish_entities") or [])],
            "objectives": [
                {
                    "objective_type": o.get("objective_type"),
                    "required_count": o.get("required_count"),
                    "item_id": o.get("item_id"),
                    "item_name": o.get("item_name"),
                    "sources": [{"name": s.get("name"), "entity_type": s.get("entity_type"), "entity_id": s.get("entity_id"), "rep": (s.get("representative_by_zone") or {}).get("210")} for s in (o.get("sources") or [])],
                }
                for o in (task.get("objectives") or [])
            ],
            "economy": task.get("level_80_economy"),
            "service": task.get("intrinsic_service_time"),
        })

    result = {"root": ROOT_ID, "rows": rows}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "count": len(rows),
        "by_depth": {str(d): [{"quest_id": r["quest_id"], "name": r["name"]} for r in rows if r["depth"] == d] for d in sorted(set(r["depth"] for r in rows))},
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
