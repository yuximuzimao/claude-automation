from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
ROUTE = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
OUT = ROOT / "data/route-atlas/icecrown-route-coverage-audit.json"
ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}


def main() -> None:
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    candidates = [
        t for t in foundation.get("tasks", [])
        if t.get("scope_status") in ROUTE_STATUSES
    ]

    name_counts = Counter(str(t.get("name") or "") for t in candidates)
    task_card_ids: set[int] = set()
    route_text_parts: list[str] = []
    for step in route.get("steps", []):
        route_text_parts.append(str(step.get("title") or ""))
        route_text_parts.extend(str(x) for x in (step.get("actions") or []))
        route_text_parts.append(str(step.get("exit") or ""))
        for raw_qid, card in (step.get("task_cards") or {}).items():
            try:
                task_card_ids.add(int(raw_qid))
            except (TypeError, ValueError):
                pass
            route_text_parts.append(str((card or {}).get("name") or ""))
            route_text_parts.append(str((card or {}).get("objective") or ""))
            route_text_parts.append(str((card or {}).get("route_note") or ""))
            route_text_parts.append(str((card or {}).get("fivebox") or ""))
    route_text = "\n".join(route_text_parts)

    rows = []
    covered_ids: set[int] = set()
    unresolved_by_name: dict[str, list[int]] = defaultdict(list)
    for task in candidates:
        qid = int(task["quest_id"])
        name = str(task.get("name") or "")
        if qid in task_card_ids:
            coverage = "covered_by_task_card_id"
            covered_ids.add(qid)
        elif name and f"《{name}》" in route_text and name_counts[name] == 1:
            coverage = "covered_by_unique_quest_name"
            covered_ids.add(qid)
        elif name and f"《{name}》" in route_text:
            coverage = "ambiguous_duplicate_name_reference"
            unresolved_by_name[name].append(qid)
        else:
            coverage = "uncovered"
        rows.append({
            "quest_id": qid,
            "name": name,
            "scope_status": task.get("scope_status"),
            "coverage": coverage,
            "pre_any": task.get("pre_any") or [],
            "pre_all": task.get("pre_all") or [],
            "parent_active": task.get("parent_active") or [],
            "is_daily": bool(task.get("is_daily")),
            "is_repeatable": bool(task.get("is_repeatable")),
        })

    uncovered = [r for r in rows if r["coverage"] not in {"covered_by_task_card_id", "covered_by_unique_quest_name"}]
    result = {
        "candidate_count": len(candidates),
        "route_step_count": len(route.get("steps", [])),
        "covered_count": len(covered_ids),
        "uncovered_count": len(uncovered),
        "covered_by_task_card_id": sum(r["coverage"] == "covered_by_task_card_id" for r in rows),
        "covered_by_unique_quest_name": sum(r["coverage"] == "covered_by_unique_quest_name" for r in rows),
        "ambiguous_duplicate_name_reference_count": sum(r["coverage"] == "ambiguous_duplicate_name_reference" for r in rows),
        "uncovered": uncovered,
        "ambiguous_duplicate_names": {k: v for k, v in sorted(unresolved_by_name.items())},
        "rows": rows,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_count": result["candidate_count"],
        "route_step_count": result["route_step_count"],
        "covered_count": result["covered_count"],
        "uncovered_count": result["uncovered_count"],
        "uncovered": [{"quest_id": r["quest_id"], "name": r["name"], "coverage": r["coverage"]} for r in uncovered],
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
