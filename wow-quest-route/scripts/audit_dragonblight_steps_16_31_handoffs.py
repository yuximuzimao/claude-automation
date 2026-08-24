from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT = ROOT / "data/route-atlas/dragonblight-steps-16-31-handoff-audit.json"
QIDS = {
    11999,12006,12013,12089,12005,12059,12061,12791,12066,12084,12096,12085,
    12106,12102,12126,12104,12111,12117,11958,11960,11959,12009,12028,12030,
    12110,12031,12125,12032,12011,12016,12017,12122,12091,12767,12461,12447,
    12458,12470,12144,12145,12147,12448,12449,12450,12419,12769,12124,12148,
    12435,12372,
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
