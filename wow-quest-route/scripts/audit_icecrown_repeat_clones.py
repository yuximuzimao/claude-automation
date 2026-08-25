from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
PAIRS = [
    (13092, 13093),
    (13239, 13261),
    (13264, 13276),
    (13279, 13281),
    (13352, 13353),
    (13356, 13357),
    (13358, 13365),
    (13367, 13368),
    (13313, 13331),
    (13373, 13406),
    (13373, 13376),
]


def normalized_objectives(task: dict) -> list[tuple]:
    rows = []
    for obj in task.get("objectives") or []:
        sources = tuple(sorted((s.get("entity_type"), s.get("entity_id"), s.get("name")) for s in (obj.get("sources") or [])))
        rows.append((obj.get("objective_type"), obj.get("required_count"), obj.get("item_id"), obj.get("item_name"), sources))
    return sorted(rows, key=repr)


def main() -> None:
    payload = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    by_id = {int(t["quest_id"]): t for t in payload.get("tasks", [])}
    out = []
    for first, repeat in PAIRS:
        a = by_id.get(first)
        b = by_id.get(repeat)
        if not a or not b:
            out.append({"first": first, "repeat": repeat, "missing": True})
            continue
        out.append({
            "first": first,
            "first_name": a.get("name"),
            "repeat": repeat,
            "repeat_name": b.get("name"),
            "repeat_is_repeatable": b.get("is_repeatable"),
            "repeat_is_daily": b.get("is_daily"),
            "repeat_pre_any": b.get("pre_any") or [],
            "same_name": a.get("name") == b.get("name"),
            "same_objective_text": (a.get("objective_text_zh") or "").strip() == (b.get("objective_text_zh") or "").strip(),
            "same_objectives": normalized_objectives(a) == normalized_objectives(b),
            "first_objective_text": a.get("objective_text_zh"),
            "repeat_objective_text": b.get("objective_text_zh"),
            "first_objectives": normalized_objectives(a),
            "repeat_objectives": normalized_objectives(b),
            "first_economy": a.get("level_80_economy"),
            "repeat_economy": b.get("level_80_economy"),
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
