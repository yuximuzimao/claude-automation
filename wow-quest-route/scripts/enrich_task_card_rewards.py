from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.quest_reward_source import load_reward_database, quest_reward_facts
from lib.questie_effective import effective_quest_rows
from lib.questie_source import load_questie
from lib.task_cards import load_task_card, task_card_path, validate_task_card


def _upsert_reward_evidence(card: dict, database, *, questie_version: str | None) -> None:
    evidence_id = "evidence-rewards-azerothcore"
    supports = ["rewards"]
    existing = next((item for item in card.get("evidence", []) if item.get("evidence_id") == evidence_id), None)
    source_ref = (
        "azerothcore/azerothcore-wotlk quest_template sha256="
        f"{database.quest_template_sha256}; item_template sha256={database.item_template_sha256}"
    )
    version_scope = "WotLK 3.3.5 base DB"
    if questie_version:
        source_ref += f" + Questie {questie_version} zhCN item names/xp"
        version_scope += f"; Questie {questie_version}"
    payload = {
        "evidence_id": evidence_id,
        "source_type": "local_db",
        "source_ref": source_ref,
        "observed_at": None,
        "version_scope": version_scope,
        "confidence": "verified",
        "supports_fields": supports,
    }
    if existing is None:
        card.setdefault("evidence", []).append(payload)
    else:
        existing.clear()
        existing.update(payload)


def enrich_task_card_rewards(quest_id: int, *, questie_source: str | None, write: bool) -> dict:
    card = load_task_card(quest_id)
    questie = load_questie(questie_source) if questie_source else None
    effective_row = None
    if questie is not None and questie_source is not None:
        rows, _ = effective_quest_rows(questie, questie_source, {quest_id})
        effective_row = rows.get(quest_id)
    database = load_reward_database()
    rewards = quest_reward_facts(
        database,
        quest_id,
        questie=questie,
        effective_quest_row=effective_row,
    )

    updated = json.loads(json.dumps(card, ensure_ascii=False))
    updated["rewards"] = rewards
    updated.setdefault("coverage", {})["rewards"] = "verified"
    _upsert_reward_evidence(updated, database, questie_version=questie.version if questie else None)
    validate_task_card(updated, expected_task_id=quest_id)

    changed = updated != card
    if write and changed:
        task_card_path(quest_id).write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "task_id": quest_id,
        "changed": changed,
        "write": write,
        "rewards": rewards,
        "source_hashes": {
            "quest_template_sha256": database.quest_template_sha256,
            "item_template_sha256": database.item_template_sha256,
        },
        "questie_version": questie.version if questie else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich one Task Card with exact AzerothCore quest/item reward facts."
    )
    parser.add_argument("task_id", type=int)
    parser.add_argument(
        "--questie-source",
        help="Optional Questie zip/directory used for zhCN reward item names and full quest XP.",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = enrich_task_card_rewards(
        args.task_id,
        questie_source=args.questie_source,
        write=args.write,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
