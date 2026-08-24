from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT = ROOT / "data/route-atlas/dragonblight-steps-32-51-handoff-audit.json"
QIDS = {
    12072,12127,12132,12136,12140,12148,12149,12150,12151,12188,
    12200,12205,12206,12209,12211,12214,12218,12221,12224,12230,
    12232,12234,12239,12240,12243,12245,12252,12254,12260,12261,
    12262,12263,12264,12265,12266,12267,12271,12273,12274,12283,
    12285,12303,12304,12447,12454,12456,12458,12459,12470,12487,
    12488,12496,12497,12498,12500,12542,12545,12789,13242,
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
