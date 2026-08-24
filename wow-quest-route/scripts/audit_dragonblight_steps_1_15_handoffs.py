from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT = ROOT / "data/route-atlas/dragonblight-steps-1-15-handoff-audit.json"

QIDS = {
    11930,11977,11978,11980,11983,12008,12033,12034,12488,12036,12039,12056,12089,12091,12100,
    12040,12041,12053,12048,12101,12102,12063,12064,12057,12069,12140,12071,12115,12125,12126,12127,
    12072,12144,12469,12044,12045,12043,12046,12047,12049,12050,12052,12112,12075,12076,12079,12077,
    12080,12078,
}


def compact_entity(entity: dict) -> dict:
    return {
        "name": entity.get("name"),
        "entity_type": entity.get("entity_type"),
        "entity_id": entity.get("entity_id"),
        "representative_by_zone": entity.get("representative_by_zone"),
    }


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    rows = []
    for task in payload.get("tasks", []):
        qid = int(task.get("quest_id") or 0)
        if qid not in QIDS:
            continue
        rows.append({
            "quest_id": qid,
            "name": task.get("name"),
            "start_entities": [compact_entity(x) for x in task.get("start_entities", [])],
            "finish_entities": [compact_entity(x) for x in task.get("finish_entities", [])],
            "pre_any": task.get("pre_any", []),
            "pre_all": task.get("pre_all", []),
            "parent_active": task.get("parent_active", []),
            "next_quest": task.get("next_quest"),
        })
    rows.sort(key=lambda x: x["quest_id"])
    found = {row["quest_id"] for row in rows}
    result = {"row_count": len(rows), "missing_qids": sorted(QIDS - found), "tasks": rows}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "missing": sorted(QIDS - found), "output": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
