from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie
from lib.route_builder import _quest
from lib.world_builder import (
    CHARACTER_PROFILES,
    ITEM,
    QUEST,
    QUEST_FLAG_DAILY,
    QUEST_FLAG_RAID,
    QUEST_FLAG_WEEKLY,
    SPECIAL_REPEATABLE,
    _bit_allowed,
    _ids,
    _objective_entities,
    _parent_zone,
    _parse_zone_metadata,
    _questgiver_entities,
)

REQUIRED_MIN_REP = 19
REQUIRED_MAX_REP = 20
REPUTATION_REWARD = 26


def eligible_for_profile(data: Any, row: Any, race_flag: int, class_flag: int) -> bool:
    """Route-Atlas eligibility: keep one-time event quests; exclude repeatable/daily/raid/profession tasks."""
    if not isinstance(row, dict):
        return False
    zone = row.get(QUEST["zone_or_sort"])
    if not isinstance(zone, int) or zone <= 0:
        return False
    level = row.get(QUEST["required_level"])
    if isinstance(level, int) and level > 80:
        return False
    if not _bit_allowed(row.get(QUEST["required_races"]), race_flag):
        return False
    if not _bit_allowed(row.get(QUEST["required_classes"]), class_flag):
        return False
    if row.get(QUEST["required_skill"]):
        return False

    quest_flags = row.get(QUEST["quest_flags"])
    if isinstance(quest_flags, int) and quest_flags & (
        QUEST_FLAG_RAID | QUEST_FLAG_DAILY | QUEST_FLAG_WEEKLY
    ):
        return False
    special_flags = row.get(QUEST["special_flags"])
    if isinstance(special_flags, int) and special_flags & SPECIAL_REPEATABLE:
        return False

    # NPC-side faction is a hard filter. Item/object starts have no NPC faction here and remain candidates.
    for group_key in ("started_by", "finished_by"):
        npc_ids = _ids(row.get(QUEST[group_key]), 1)
        if not npc_ids:
            continue
        factions: list[Any] = []
        for npc_id in npc_ids:
            npc = data.npcs.get(npc_id)
            if isinstance(npc, dict):
                factions.append(npc.get(13))
        if factions and not any(isinstance(value, str) and "H" in value for value in factions):
            return False
    return True


def slim_entity(entity: dict[str, Any]) -> dict[str, Any]:
    summary = entity.get("coordinate_summary") or {}
    return {
        "kind": entity.get("kind"),
        "id": entity.get("id"),
        "name": entity.get("name"),
        "rep": summary.get("representative"),
    }


def item_start_sources(data: Any, row: dict[Any, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item_id in _ids(row.get(QUEST["started_by"]), 3):
        item = data.items.get(item_id)
        raw_name = item.get(ITEM["name"], f"Item {item_id}") if isinstance(item, dict) else f"Item {item_id}"
        result.append(
            {
                "id": item_id,
                "name": data.local_name(data.item_names, item_id, raw_name),
            }
        )
    return result


def add_index(
    index: dict[str, dict[str, Any]],
    entity: dict[str, Any],
    quest_id: int,
) -> None:
    key = f"{entity.get('kind')}:{entity.get('id')}"
    entry = index.setdefault(
        key,
        {
            "kind": entity.get("kind"),
            "id": entity.get("id"),
            "name": entity.get("name"),
            "rep": entity.get("rep"),
            "quest_ids": [],
        },
    )
    if quest_id not in entry["quest_ids"]:
        entry["quest_ids"].append(quest_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a compact Route Atlas task universe for one zone.")
    parser.add_argument("--zone-id", type=int, required=True)
    parser.add_argument(
        "--questie-source",
        default=str(ROOT.parent / ".ai-bridge" / "Questie.zip"),
    )
    parser.add_argument("--profile", choices=tuple(CHARACTER_PROFILES), default="paladin")
    parser.add_argument("--start-level", type=int, default=68)
    parser.add_argument("--max-required-level", type=int, default=80)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.questie_source).expanduser().resolve()
    data = load_questie(source)
    meta = _parse_zone_metadata(source)
    profile = CHARACTER_PROFILES[args.profile]
    race_flag = int(profile["race_flag"])
    class_flag = int(profile["class_flag"])

    zone_name = meta["names"].get(args.zone_id, f"Zone {args.zone_id}")
    zone_name_zh = meta["zh"].get(zone_name, zone_name)

    raw_rows: list[tuple[int, dict[Any, Any], int, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]] = []
    for quest_id, row in data.quests.items():
        if not isinstance(quest_id, int) or not eligible_for_profile(data, row, race_flag, class_flag):
            continue
        required_level = row.get(QUEST["required_level"])
        if isinstance(required_level, int) and required_level > args.max_required_level:
            continue
        assigned_zone = _parent_zone(int(row[QUEST["zone_or_sort"]]), meta["parents"])
        accept = [slim_entity(e) for e in _questgiver_entities(data, row.get(QUEST["started_by"]), args.zone_id)]
        objective = [slim_entity(e) for e in _objective_entities(data, row, args.zone_id)]
        turnin = [slim_entity(e) for e in _questgiver_entities(data, row.get(QUEST["finished_by"]), args.zone_id)]
        if assigned_zone != args.zone_id and not (accept or objective or turnin):
            continue
        raw_rows.append((quest_id, row, assigned_zone, accept, objective, turnin))

    included_ids = {quest_id for quest_id, *_ in raw_rows}
    tasks: list[dict[str, Any]] = []
    accept_hubs: dict[str, dict[str, Any]] = {}
    turnin_hubs: dict[str, dict[str, Any]] = {}
    target_entities: dict[str, dict[str, Any]] = {}

    for quest_id, row, assigned_zone, accept, objective, turnin in raw_rows:
        quest = _quest(data, quest_id)
        required_level = quest.get("required_level")
        quest_level = quest.get("quest_level")
        effective_required = required_level if isinstance(required_level, int) and required_level > 0 else quest_level
        pre_single = [int(v) for v in quest.get("pre_single", []) if isinstance(v, int)]
        pre_group = [int(v) for v in quest.get("pre_group", []) if isinstance(v, int)]
        external_prereqs = sorted({abs(v) for v in pre_single + pre_group if abs(v) not in included_ids})
        task = {
            "quest_id": quest_id,
            "name": quest.get("name"),
            "required_level": required_level,
            "quest_level": quest_level,
            "last_full_xp_level": quest_level + 5 if isinstance(quest_level, int) and quest_level > 0 else None,
            "level_ready_at_start": isinstance(effective_required, int) and effective_required <= args.start_level,
            "assigned_zone_id": assigned_zone,
            "touches_zone": {
                "assigned": assigned_zone == args.zone_id,
                "accept": bool(accept),
                "objective": bool(objective),
                "turnin": bool(turnin),
            },
            "pre_single": pre_single,
            "pre_group": pre_group,
            "external_prereqs": external_prereqs,
            "next_quest": quest.get("next_quest"),
            "required_min_rep": row.get(REQUIRED_MIN_REP),
            "required_max_rep": row.get(REQUIRED_MAX_REP),
            "reputation_reward": row.get(REPUTATION_REWARD),
            "quest_flags": row.get(QUEST["quest_flags"]),
            "special_flags": row.get(QUEST["special_flags"]),
            "item_starts": item_start_sources(data, row),
            "accept": accept,
            "objective": objective,
            "turnin": turnin,
        }
        tasks.append(task)
        for entity in accept:
            add_index(accept_hubs, entity, quest_id)
        for entity in turnin:
            add_index(turnin_hubs, entity, quest_id)
        for entity in objective:
            add_index(target_entities, entity, quest_id)

    tasks.sort(
        key=lambda task: (
            task["required_level"] if isinstance(task["required_level"], int) else 999,
            task["quest_level"] if isinstance(task["quest_level"], int) else 999,
            task["quest_id"],
        )
    )
    for index in (accept_hubs, turnin_hubs, target_entities):
        for entry in index.values():
            entry["quest_ids"] = sorted(entry["quest_ids"])

    roots_at_start = [
        task["quest_id"]
        for task in tasks
        if task["level_ready_at_start"]
        and not task["pre_single"]
        and not task["pre_group"]
        and not task["required_min_rep"]
        and not task["required_max_rep"]
    ]
    payload = {
        "status": "raw_recall_only_superseded_by_effective_foundation",
        "authority_note": "This compact export does not apply Questie wotlkQuestFixes and must not drive Route Atlas ordering. Use borean-tundra-task-foundation.json for Borean planning.",
        "zone": {"id": args.zone_id, "name_en": zone_name, "name_zh": zone_name_zh},
        "profile": args.profile,
        "start_level": args.start_level,
        "source": {"questie_version": data.version, "source_sha256": data.source_sha256},
        "stats": {
            "task_count": len(tasks),
            "level_ready_at_start": sum(1 for task in tasks if task["level_ready_at_start"]),
            "root_level_ready_at_start": len(roots_at_start),
            "accept_hub_count": len(accept_hubs),
            "turnin_hub_count": len(turnin_hubs),
            "target_entity_count": len(target_entities),
        },
        "root_level_ready_quest_ids": roots_at_start,
        "accept_hubs": sorted(accept_hubs.values(), key=lambda entry: (entry["name"] or "", str(entry["id"]))),
        "turnin_hubs": sorted(turnin_hubs.values(), key=lambda entry: (entry["name"] or "", str(entry["id"]))),
        "target_entities": sorted(
            target_entities.values(),
            key=lambda entry: (-len(entry["quest_ids"]), entry["name"] or "", str(entry["id"])),
        ),
        "tasks": tasks,
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "zone": zone_name_zh,
                "stats": payload["stats"],
                "questie_version": data.version,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
