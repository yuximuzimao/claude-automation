from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
IDS = [13068, 13072, 13073, 13074, 13075, 13076, 13077, 13078, 13079, 13080, 13081, 13082, 13083, 13374]


def index(payload: dict) -> dict[int, dict]:
    return {int(t["quest_id"]): t for t in payload.get("tasks", []) if t.get("quest_id") is not None}


def main() -> None:
    universe = index(json.loads(UNIVERSE.read_text(encoding="utf-8")))
    foundation = index(json.loads(FOUNDATION.read_text(encoding="utf-8")))
    out = {}
    for qid in IDS:
        u = universe.get(qid)
        f = foundation.get(qid)
        out[str(qid)] = {
            "universe": None if not u else {
                "name": u.get("name"),
                "zone_ids": u.get("zone_ids"),
                "map_ids": u.get("map_ids"),
                "pre_any": u.get("pre_any"),
                "pre_all": u.get("pre_all"),
                "parent_active": u.get("parent_active"),
                "available_starting_with": u.get("available_starting_with"),
                "eligibility": u.get("eligibility"),
                "is_daily": u.get("is_daily"),
                "is_repeatable": u.get("is_repeatable"),
                "start_entities": u.get("start_entities"),
                "finish_entities": u.get("finish_entities"),
                "objective_text_zh": u.get("objective_text_zh"),
            },
            "foundation": None if not f else {
                "name": f.get("name"),
                "scope_status": f.get("scope_status"),
                "scope_reasons": f.get("scope_reasons"),
                "pre_any": f.get("pre_any"),
                "pre_all": f.get("pre_all"),
                "parent_active": f.get("parent_active"),
            },
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
