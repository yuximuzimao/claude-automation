from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_35_55_task_foundation import quest_xp_at_level
from lib.questie_source import load_questie


def main() -> None:
    parser = argparse.ArgumentParser(description="Print compact task evidence for selected quest IDs.")
    parser.add_argument("quest_ids", nargs="+", type=int)
    parser.add_argument("--level", type=int, default=54)
    args = parser.parse_args()

    payload = json.loads(
        (ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json").read_text(
            encoding="utf-8"
        )
    )
    by_id = {int(row["quest_id"]): row for row in payload["tasks"]}
    questie = load_questie(ROOT / "_sandbox/sources/Questie-v11.32.3.zip")

    rows = []
    for quest_id in args.quest_ids:
        task = by_id.get(quest_id)
        row = {
            "quest_id": quest_id,
            "xp_at_level": quest_xp_at_level(questie, quest_id, args.level),
        }
        if task:
            row.update(
                {
                    "name": task.get("name"),
                    "zone": task.get("primary_zone"),
                    "required_level": task.get("required_level"),
                    "quest_level": task.get("quest_level"),
                    "objective_text_zh": task.get("objective_text_zh"),
                    "task_class": task.get("task_class"),
                    "pre_single": task.get("pre_single", []),
                    "pre_group": task.get("pre_group", []),
                    "next_quest": task.get("next_quest"),
                    "reference_time": task.get("azerothcore_adjusted_standalone_time"),
                    "review": task.get("manual_review_reasons", []),
                }
            )
        else:
            row["name"] = "Questie fallback"
        rows.append(row)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
