from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie

CANDIDATE = ROOT / "data/routes/horde/blood-elf/39-55-eastern-kingdoms-candidate.json"
FOUNDATION = ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json"
QUESTIE = ROOT / "_sandbox/sources/Questie-v11.32.3.zip"
OUTPUT = ROOT / "data/routes/horde/blood-elf/39-55-a-route-task-details.json"


def zone_points(entity: dict[str, Any], zone_id: str | None) -> list[dict[str, Any]]:
    reps = entity.get("representative_by_zone") or {}
    if zone_id and zone_id in reps:
        row = reps[zone_id]
        return [{"zone_id": int(zone_id), "x": row.get("x"), "y": row.get("y"), "spawn_count": row.get("spawn_count")}]
    points = []
    for key, row in reps.items():
        points.append({"zone_id": int(key), "x": row.get("x"), "y": row.get("y"), "spawn_count": row.get("spawn_count")})
    return points


def raw_name(questie: Any, quest_id: int) -> str:
    quest = questie.quests.get(quest_id) or {}
    value = quest.get(1)
    return str(value or f"Quest {quest_id}")


def main() -> None:
    route = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    task_by_id = {int(row["quest_id"]): row for row in foundation["tasks"]}
    questie = load_questie(QUESTIE)

    blocks = []
    for block in route["blocks"]:
        task_rows = []
        for selected in block["tasks"]:
            quest_id = int(selected["quest_id"])
            task = task_by_id.get(quest_id)
            if not task:
                raw = questie.quests.get(quest_id) or {}
                task_rows.append(
                    {
                        **selected,
                        "name_en": raw_name(questie, quest_id),
                        "required_level": raw.get(4),
                        "quest_level": raw.get(5),
                        "objective_text_en": (raw.get(8) or {}).get(1),
                        "pre_single": list((raw.get(13) or {}).values()) if isinstance(raw.get(13), dict) else [],
                        "next_quest": raw.get(22),
                        "start_entities": [],
                        "finish_entities": [],
                        "objectives": [],
                    }
                )
                continue

            primary_zone_id = str(task.get("primary_zone_id")) if task.get("primary_zone_id") is not None else None
            starts = [
                {
                    "name": entity.get("name"),
                    "entity_type": entity.get("entity_type"),
                    "points": zone_points(entity, primary_zone_id),
                }
                for entity in task.get("start_entities", [])
            ]
            finishes = [
                {
                    "name": entity.get("name"),
                    "entity_type": entity.get("entity_type"),
                    "points": zone_points(entity, primary_zone_id),
                }
                for entity in task.get("finish_entities", [])
            ]
            objectives = []
            for obj in task.get("objectives", []):
                sources = []
                for src in obj.get("sources", []):
                    sources.append(
                        {
                            "name": src.get("name"),
                            "entity_type": src.get("entity_type"),
                            "spawn_count": src.get("spawn_count"),
                            "points": zone_points(src, primary_zone_id),
                        }
                    )
                objectives.append(
                    {
                        "objective_type": obj.get("objective_type"),
                        "required_count": obj.get("required_count"),
                        "mechanic": obj.get("mechanic"),
                        "sources": sources,
                    }
                )

            task_rows.append(
                {
                    **selected,
                    "name_en": task.get("name_en") or raw_name(questie, quest_id),
                    "primary_zone": task.get("primary_zone"),
                    "primary_zone_id": task.get("primary_zone_id"),
                    "required_level": task.get("required_level"),
                    "quest_level": task.get("quest_level"),
                    "objective_text_zh": task.get("objective_text_zh"),
                    "objective_text_en": task.get("objective_text_en"),
                    "task_class": task.get("task_class"),
                    "pre_single": task.get("pre_single", []),
                    "pre_group": task.get("pre_group", []),
                    "next_quest": task.get("next_quest"),
                    "start_entities": starts,
                    "finish_entities": finishes,
                    "objectives": objectives,
                }
            )
        blocks.append({"block": block["block"], "tasks": task_rows})

    output = {
        "schema_version": 1,
        "source_candidate": str(CANDIDATE.relative_to(ROOT)),
        "questie_version": "11.32.3",
        "blocks": blocks,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} with {sum(len(b['tasks']) for b in blocks)} tasks")


if __name__ == "__main__":
    main()
