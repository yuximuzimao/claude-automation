from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .quest_reward_source import batch_quest_reward_facts, load_reward_database
from .questie_effective import QUEST_FLAGS, QUEST_KEYS, effective_quest_rows
from .questie_lua import seq
from .questie_source import QuestieData, load_questie

HORDE_MASK = 690
ALLIANCE_MASK = 1101
RACE_BITS = {
    1: "human",
    2: "orc",
    4: "dwarf",
    8: "night_elf",
    16: "undead",
    32: "tauren",
    64: "gnome",
    128: "troll",
    512: "blood_elf",
    1024: "draenei",
}
CLASS_BITS = {
    1: "warrior",
    2: "paladin",
    4: "hunter",
    8: "rogue",
    16: "priest",
    32: "death_knight",
    64: "shaman",
    128: "mage",
    256: "warlock",
    1024: "druid",
}
ID_SCALAR_KEYS = {
    "quest_id",
    "task_id",
    "next_quest",
    "next_quest_id",
    "parent_quest",
    "parent_quest_id",
    "breadcrumb_for_quest_id",
}
ID_LIST_KEYS = {
    "quest_ids",
    "task_ids",
    "qids",
    "pre_any",
    "pre_all",
    "pre_single",
    "pre_group",
    "parent_active",
    "exclusive_with",
    "exclusive_to",
    "child_quests",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _localized_name(table: dict[Any, Any], entity_id: int) -> str | None:
    value = table.get(entity_id)
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get(1), str):
        return value[1]
    return None


def _localized_objective(data: QuestieData, quest_id: int) -> str:
    value = data.quest_names.get(quest_id)
    if not isinstance(value, dict):
        return ""
    return " / ".join(str(item) for item in seq(value.get(2)) if isinstance(item, str))


def _english_objective(row: dict[Any, Any]) -> str:
    return " / ".join(str(item) for item in seq(row.get(QUEST_KEYS["objectivesText"])) if isinstance(item, str))


def _entity_ids(group: Any, bucket: int) -> list[int]:
    if not isinstance(group, dict):
        return []
    values = group.get(bucket)
    result: list[int] = []
    for entry in seq(values):
        if isinstance(entry, int):
            result.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get(1), int):
            result.append(int(entry[1]))
    return result


def _entity_group(data: QuestieData, group: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for npc_id in _entity_ids(group, 1):
        result.append({"kind": "npc", "id": npc_id, "name_zhcn": _localized_name(data.npc_names, npc_id)})
    for object_id in _entity_ids(group, 2):
        result.append({"kind": "object", "id": object_id, "name_zhcn": _localized_name(data.object_names, object_id)})
    for item_id in _entity_ids(group, 3):
        result.append({"kind": "item", "id": item_id, "name_zhcn": _localized_name(data.item_names, item_id)})
    return result


def faction_from_race_mask(mask: Any) -> str:
    if not isinstance(mask, int) or mask == 0:
        return "both"
    has_horde = bool(mask & HORDE_MASK)
    has_alliance = bool(mask & ALLIANCE_MASK)
    if has_horde and not has_alliance:
        return "horde"
    if has_alliance and not has_horde:
        return "alliance"
    if has_horde and has_alliance:
        return "both"
    return "unknown"


def names_from_mask(mask: Any, bits: dict[int, str], all_mask: int | None = None) -> list[str]:
    if not isinstance(mask, int) or mask == 0 or (all_mask is not None and mask == all_mask):
        return []
    return [name for bit, name in bits.items() if mask & bit]


def repeatability_from_flags(row: dict[Any, Any]) -> str:
    qflags = int(row.get(QUEST_KEYS["questFlags"]) or 0)
    sflags = int(row.get(QUEST_KEYS["specialFlags"]) or 0)
    if qflags & QUEST_FLAGS["DAILY"]:
        return "daily"
    if sflags & 1 or qflags & (QUEST_FLAGS["WEEKLY"] | QUEST_FLAGS["MONTHLY"]):
        return "repeatable"
    return "once"


def normalize_questie_task(data: QuestieData, quest_id: int, row: dict[Any, Any]) -> dict[str, Any]:
    parent = row.get(QUEST_KEYS["parentQuest"])
    required_spell = row.get(QUEST_KEYS["requiredSpell"])
    hidden: list[dict[str, Any]] = []
    if isinstance(required_spell, int) and required_spell:
        hidden.append({"kind": "questie_required_spell", "summary": f"requiredSpell={required_spell}"})
    for key in ("requiredMaxLevel", "availableUntilCompleted", "availableStartingWith", "disabledByQuest", "requiredRanks"):
        raw = row.get(QUEST_KEYS[key])
        if raw not in (None, 0, {}, []):
            hidden.append({"kind": f"questie_{key}", "summary": json.dumps(_jsonable(raw), ensure_ascii=False)})

    min_rep = row.get(QUEST_KEYS["requiredMinRep"])
    max_rep = row.get(QUEST_KEYS["requiredMaxRep"])
    reputation = None
    if min_rep not in (None, {}, []) or max_rep not in (None, {}, []):
        reputation = {"min": _jsonable(min_rep), "max": _jsonable(max_rep)}

    objective_zh = _localized_objective(data, quest_id)
    objective_en = _english_objective(row)
    return {
        "task_id": quest_id,
        "name_zhcn": _localized_name(data.quest_names, quest_id) or str(row.get(QUEST_KEYS["name"]) or f"Quest {quest_id}"),
        "name_en": row.get(QUEST_KEYS["name"]),
        "faction": faction_from_race_mask(row.get(QUEST_KEYS["requiredRaces"])),
        "repeatability": repeatability_from_flags(row),
        "quest_level": row.get(QUEST_KEYS["questLevel"]),
        "min_level": row.get(QUEST_KEYS["requiredLevel"]),
        "pre_any": [int(value) for value in seq(row.get(QUEST_KEYS["preQuestSingle"])) if isinstance(value, int)],
        "pre_all": [int(value) for value in seq(row.get(QUEST_KEYS["preQuestGroup"])) if isinstance(value, int)],
        "parent_active": [int(parent)] if isinstance(parent, int) and parent > 0 else [],
        "exclusive_with": [int(value) for value in seq(row.get(QUEST_KEYS["exclusiveTo"])) if isinstance(value, int)],
        "required_reputation": reputation,
        "required_class": names_from_mask(row.get(QUEST_KEYS["requiredClasses"]), CLASS_BITS, 1535),
        "required_race": names_from_mask(row.get(QUEST_KEYS["requiredRaces"]), RACE_BITS),
        "required_skill_raw": _jsonable(row.get(QUEST_KEYS["requiredSkill"])),
        "hidden_requirements": hidden,
        "objective_zh": objective_zh,
        "objective_en": objective_en,
        "start_entities": _entity_group(data, row.get(QUEST_KEYS["startedBy"])),
        "finish_entities": _entity_group(data, row.get(QUEST_KEYS["finishedBy"])),
        "next_quest": row.get(QUEST_KEYS["nextQuestInChain"]),
        "zone_or_sort": row.get(QUEST_KEYS["zoneOrSort"]),
        "quest_flags": int(row.get(QUEST_KEYS["questFlags"]) or 0),
        "special_flags": int(row.get(QUEST_KEYS["specialFlags"]) or 0),
        "raw_effective_row": _jsonable(row),
    }


def collect_project_task_ids(root: Path) -> set[int]:
    ids: set[int] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ID_SCALAR_KEYS and isinstance(item, int) and 0 < item < 20_000:
                    ids.add(item)
                elif key in ID_LIST_KEYS and isinstance(item, list):
                    ids.update(int(x) for x in item if isinstance(x, int) and 0 < x < 20_000)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for path in sorted((root / "data").rglob("*.json")):
        if "_sandbox" in path.parts:
            continue
        try:
            walk(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    fivebox_path = root / "data/observations/fivebox-task-types.json"
    if fivebox_path.exists():
        payload = json.loads(fivebox_path.read_text(encoding="utf-8"))
        for key in payload.get("tasks", {}):
            if str(key).isdigit():
                value = int(key)
                if 0 < value < 20_000:
                    ids.add(value)
    return ids


def _route_zone_id(route: dict[str, Any]) -> int | None:
    image = route.get("image")
    if not isinstance(image, str):
        return None
    match = re.search(r"(?:^|/)(\d+)-", image)
    return int(match.group(1)) if match else None


def _candidate_catalogs(root: Path) -> dict[int, dict[str, set[int]]]:
    result: dict[int, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for base in (root / "data/routes/world-candidate", root / "data/routes/world-candidate-dk"):
        if not base.exists():
            continue
        for path in base.glob("*/route.json"):
            match = re.match(r"(\d+)-", path.parent.name)
            if not match:
                continue
            zone_id = int(match.group(1))
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for row in payload.get("quest_catalog", []):
                if not isinstance(row, dict):
                    continue
                quest_id = row.get("quest_id")
                name = row.get("name")
                if isinstance(quest_id, int) and isinstance(name, str) and name:
                    result[zone_id][name].add(quest_id)
    return result


def collect_structured_records(root: Path, target_ids: set[int]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    skip: set[Path] = set()

    def walk(value: Any, path: Path, pointer: str) -> None:
        if isinstance(value, dict):
            direct: set[int] = set()
            for key in ("quest_id", "task_id"):
                item = value.get(key)
                if isinstance(item, int) and item in target_ids:
                    direct.add(item)
            for task_id in direct:
                result[task_id].append({"source": str(path.relative_to(root)), "pointer": pointer or "/", "record": value})
            for key, item in value.items():
                walk(item, path, f"{pointer}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path, f"{pointer}/{index}")

    for path in sorted((root / "data").rglob("*.json")):
        if path in skip or "_sandbox" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        walk(payload, path, "")
    return dict(result)


def build_index(root: Path, questie_source: Path, sqlite_path: Path) -> dict[str, Any]:
    root = root.resolve()
    questie_source = questie_source.resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    project_ids = collect_project_task_ids(root)
    data = load_questie(questie_source)
    effective_rows, correction_audit = effective_quest_rows(data, questie_source, project_ids)
    normalized = {qid: normalize_questie_task(data, qid, row) for qid, row in effective_rows.items()}

    reward_db = load_reward_database()
    rewards, reward_audit = batch_quest_reward_facts(
        reward_db,
        project_ids,
        questie=data,
        effective_quest_rows=effective_rows,
    )

    formal_ids = {
        int(path.stem)
        for path in (root / "data/task-cards").glob("*.json")
        if path.name != "schema.json" and path.stem.isdigit()
    }

    structured_records = collect_structured_records(root, project_ids)

    existing_cards: dict[int, dict[str, Any]] = {}
    for path in (root / "data/task-cards").glob("*.json"):
        if path.name != "schema.json" and path.stem.isdigit():
            existing_cards[int(path.stem)] = json.loads(path.read_text(encoding="utf-8"))

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("DROP TABLE IF EXISTS meta")
        conn.execute("DROP TABLE IF EXISTS tasks")
        conn.execute("DROP TABLE IF EXISTS unresolved_workbench")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE tasks (task_id INTEGER PRIMARY KEY, is_formal_target INTEGER NOT NULL, payload_json TEXT NOT NULL)")

        for task_id in sorted(project_ids):
            payload = {
                "task_id": task_id,
                "is_formal_target": task_id in formal_ids,
                "questie": normalized.get(task_id),
                "questie_correction_fields": correction_audit.get("changed_fields", {}).get(str(task_id), []),
                "questie_correction_error": correction_audit.get("parse_failures", {}).get(str(task_id)),
                "rewards": rewards.get(task_id),
                "structured_records": structured_records.get(task_id, []),
                "existing_task_card": existing_cards.get(task_id),
            }
            conn.execute(
                "INSERT INTO tasks(task_id, is_formal_target, payload_json) VALUES (?, ?, ?)",
                (task_id, 1 if task_id in formal_ids else 0, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
            )
        source_meta = {
            "questie_version": data.version,
            "questie_sha256": data.source_sha256,
            "quest_template_sha256": reward_db.quest_template_sha256,
            "item_template_sha256": reward_db.item_template_sha256,
            "project_task_id_count": len(project_ids),
            "formal_target_count": len(formal_ids),
            "reward_audit": reward_audit,
            "questie_correction_audit": correction_audit,
        }
        for key, value in source_meta.items():
            conn.execute("INSERT INTO meta(key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False, separators=(",", ":"))))
        conn.commit()

    return {
        "sqlite_path": str(sqlite_path),
        "sqlite_bytes": sqlite_path.stat().st_size,
        "project_task_id_count": len(project_ids),
        "formal_target_count": len(formal_ids),
        "questie_present_count": len(effective_rows),
        "reward_audit": reward_audit,
        "questie_correction_parse_failures": correction_audit.get("failed_block_count", 0),
    }


def load_index_task(sqlite_path: Path, task_id: int) -> dict[str, Any]:
    with sqlite3.connect(sqlite_path) as conn:
        row = conn.execute("SELECT payload_json FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(task_id)
    return json.loads(row[0])


def iter_formal_targets(sqlite_path: Path) -> Iterable[dict[str, Any]]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT payload_json FROM tasks WHERE is_formal_target = 1 ORDER BY task_id").fetchall()
    for row in rows:
        yield json.loads(row[0])
