from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT = ROOT / "data/route-atlas/icecrown-vanguard-chain-trace.json"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}
START = 13104
TARGET = 13224


def main() -> None:
    data = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    tasks = [t for t in data.get("tasks", []) if t.get("scope_status") in ROUTE_STATUSES]
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

    queue = deque([START])
    parent: dict[int, int | None] = {START: None}
    while queue:
        qid = queue.popleft()
        if qid == TARGET:
            break
        for nxt in sorted(children.get(qid, [])):
            if nxt not in parent:
                parent[nxt] = qid
                queue.append(nxt)

    path: list[int] = []
    if TARGET in parent:
        cur: int | None = TARGET
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()

    relevant = set(path)
    # Include direct side branches from the path so we can see tasks that should be bundled geographically.
    for qid in path:
        relevant |= children.get(qid, set())
        task = by_id.get(qid) or {}
        relevant |= set(int(x) for x in (task.get("pre_any") or []) if int(x) in by_id)
        relevant |= set(int(x) for x in (task.get("pre_all") or []) if int(x) in by_id)

    rows = []
    for qid in sorted(relevant):
        task = by_id[qid]
        def ents(key: str):
            out = []
            for e in task.get(key) or []:
                rep = (e.get("representative_by_zone") or {}).get("210") or {}
                out.append({
                    "name": e.get("name"),
                    "entity_id": e.get("entity_id"),
                    "entity_type": e.get("entity_type"),
                    "x": rep.get("x"),
                    "y": rep.get("y"),
                })
            return out
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "on_shortest_path": qid in path,
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "next_quest": task.get("next_quest"),
            "child_quests": task.get("child_quests") or [],
            "objective_text_zh": task.get("objective_text_zh"),
            "task_class": task.get("task_class"),
            "task_flags": task.get("task_flags"),
            "objective_review": task.get("objective_review"),
            "objectives": [
                {
                    "objective_type": o.get("objective_type"),
                    "required_count": o.get("required_count"),
                    "item_id": o.get("item_id"),
                    "item_name": o.get("item_name"),
                    "sources": [
                        {
                            "name": s.get("name"),
                            "entity_type": s.get("entity_type"),
                            "entity_id": s.get("entity_id"),
                            "rep": (s.get("representative_by_zone") or {}).get("210"),
                        }
                        for s in (o.get("sources") or [])
                    ],
                }
                for o in (task.get("objectives") or [])
            ],
            "start_entities": ents("start_entities"),
            "finish_entities": ents("finish_entities"),
            "economy": task.get("level_80_economy"),
            "service": task.get("intrinsic_service_time"),
        })

    payload = {"start": START, "target": TARGET, "path": path, "rows": rows}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "path": [{"quest_id": qid, "name": by_id[qid].get("name")} for qid in path],
        "side_rows": [{"quest_id": row["quest_id"], "name": row["name"]} for row in rows if not row["on_shortest_path"]],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
