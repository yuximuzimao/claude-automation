from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from lib.questie_lua import seq
from lib.questie_source import QuestieData, load_questie
from lib.world_builder import (
    BLOOD_ELF_RACE_FLAG,
    PALADIN_CLASS_FLAG,
    QUEST,
    _eligible,
    _ids,
    _parent_zone,
    _parse_zone_metadata,
)


SERVER_QUEST_XP_MULTIPLIER = 2.0
CURRENT_LEVEL = 35
TARGET_LEVEL = 55

# Questie WotLK schema.
Q_START = 2
Q_FINISH = 3
Q_REQUIRED_LEVEL = 4
Q_LEVEL = 5
Q_TRIGGER_END = 9
Q_OBJECTIVES = 10
Q_PRE_GROUP = 12
Q_PRE_SINGLE = 13
Q_ZONE_OR_SORT = 17
Q_FLAGS = 23
Q_SPECIAL_FLAGS = 24
Q_NEXT = 22

NPC_NAME = 1
NPC_MIN_HEALTH = 2
NPC_MAX_HEALTH = 3
NPC_MIN_LEVEL = 4
NPC_MAX_LEVEL = 5
NPC_RANK = 6
NPC_SPAWNS = 7
NPC_WAYPOINTS = 8
NPC_ZONE = 9
NPC_FACTION = 13

OBJECT_NAME = 1
OBJECT_SPAWNS = 4

ITEM_NAME = 1
ITEM_NPC_DROPS = 2
ITEM_OBJECT_DROPS = 3

# The user controls one paladin for combat while four characters follow. These
# are transparent calibration assumptions, not claims about the actual gear.
# Selected-route tasks must later be replaced by real observed values.
DPS_PROFILE = {
    35: (34.0, 44.0, 58.0),
    40: (43.0, 57.0, 75.0),
    45: (57.0, 76.0, 99.0),
    50: (74.0, 98.0, 128.0),
    55: (92.0, 122.0, 158.0),
}

# Approximate full-map diagonal riding time. It is only used to convert exact
# normalized coordinate distance into a transparent first-pass range. Route
# selection retains the raw distance index so this can be replaced later.
ZONE_DIAGONAL_MINUTES_100_MOUNT = {
    1: 9.0, 3: 7.0, 8: 8.0, 10: 8.0, 11: 7.0, 14: 8.0,
    15: 10.0, 16: 10.0, 17: 9.0, 28: 8.5, 33: 12.0, 36: 8.0,
    38: 7.0, 40: 8.0, 44: 7.0, 45: 9.0, 46: 8.0, 47: 9.5,
    51: 6.5, 85: 4.0, 130: 8.0, 139: 10.0, 141: 4.0, 148: 9.0,
    215: 4.0, 267: 7.0, 331: 9.0, 357: 12.5, 361: 10.0, 400: 9.0,
    405: 10.0, 406: 7.0, 440: 11.0, 490: 8.0, 618: 10.5,
    1377: 4.0, 1497: 4.0, 1637: 4.0, 3487: 4.0,
}

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60,
}

ESCORT_PATTERNS = (
    "escort", "accompany", "protect", "lead ", "see .* safely", "keep .* alive",
    "defend .* while", "follow .* to", "help .* escape",
)
USE_PATTERNS = (
    "use ", "using ", "place ", "plant ", "burn ", "light ", "free ",
    "release ", "capture ", "tag ", "summon ", "destroy ", "inspect ",
)

# Current manual state is deliberately separate from the generated facts.
# It only affects status labels, never the objective classification.
KNOWN_CURRENT_ACTIVE = {
    187, 192, 195, 1106, 1107, 1117, 1183, 1362, 5361, 9627,
}
KNOWN_COMPLETED_AFTER_STALE_JOURNEY = {
    1116, 1180, 1181, 1182, 1114, 1152,
}
KNOWN_COMPLETED_OBJECTIVE_NOT_ALL_TURNED_IN = {195}


@dataclass
class Point:
    zone_id: int
    x: float
    y: float


@dataclass
class Entity:
    entity_type: str
    entity_id: int
    name: str
    min_level: int | None = None
    max_level: int | None = None
    min_health: int | None = None
    max_health: int | None = None
    rank: int | None = None
    spawn_count: int = 0
    zones: list[int] | None = None
    representative_by_zone: dict[str, dict[str, float]] | None = None


@dataclass
class Objective:
    objective_type: str
    required_count: int | None
    entity_ids: list[int]
    item_id: int | None
    item_name: str | None
    sources: list[Entity]
    count_confidence: str
    fivebox_mode: str
    mechanic: str
    difficulty_flags: list[str]


@dataclass
class TimeRange:
    optimistic: float
    central: float
    pessimistic: float


@dataclass
class TaskRecord:
    quest_id: int
    name: str
    english_name: str
    status: str
    primary_zone_id: int
    primary_zone: str
    all_route_zones: list[str]
    required_level: int
    quest_level: int
    xp_db_level: int
    xp_db_base: int
    full_xp_through_level: int
    xp_by_completion_level: dict[str, int]
    objective_text_en: str
    objective_text_zh: str
    task_class: str
    objectives: list[Objective]
    start_entities: list[Entity]
    finish_entities: list[Entity]
    pre_single: list[int]
    pre_group: list[int]
    next_quest: int | None
    chain_flags: list[str]
    route_flags: list[str]
    standalone_distance_index: float | None
    standalone_time_components: dict[str, Any]
    standalone_time_at_earliest_level: TimeRange
    earliest_completion_level: int
    xp_at_earliest_completion: int
    xp_per_central_minute_standalone: float | None
    confidence: str
    manual_review_reasons: list[str]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def quest_xp_at_level(data: QuestieData, quest_id: int, player_level: int) -> int:
    row = data.quest_xp.get(quest_id)
    if not isinstance(row, dict):
        return 0
    q_level = row.get(1)
    base_xp = row.get(2)
    if not isinstance(q_level, int) or not isinstance(base_xp, int) or q_level <= 0 or base_xp <= 0:
        return 0
    multiplier = int(clamp(2 * (q_level - player_level) + 20, 1, 10))
    xp = base_xp * multiplier / 10.0
    if xp <= 100:
        xp = 5 * math.floor((xp + 2) / 5)
    elif xp <= 500:
        xp = 10 * math.floor((xp + 5) / 10)
    elif xp <= 1000:
        xp = 25 * math.floor((xp + 12) / 25)
    else:
        xp = 50 * math.floor((xp + 25) / 50)
    return int(math.floor(xp * SERVER_QUEST_XP_MULTIPLIER))


def interpolate_profile(level: int) -> tuple[float, float, float]:
    keys = sorted(DPS_PROFILE)
    if level <= keys[0]:
        return DPS_PROFILE[keys[0]]
    if level >= keys[-1]:
        return DPS_PROFILE[keys[-1]]
    lower = max(key for key in keys if key <= level)
    upper = min(key for key in keys if key >= level)
    if lower == upper:
        return DPS_PROFILE[lower]
    ratio = (level - lower) / (upper - lower)
    return tuple(
        DPS_PROFILE[lower][index]
        + ratio * (DPS_PROFILE[upper][index] - DPS_PROFILE[lower][index])
        for index in range(3)
    )


def ordered_numeric_mentions(text: str) -> list[int]:
    mentions: list[tuple[int, int]] = []
    for match in re.finditer(r"(?<![A-Za-z0-9-])\d{1,3}(?![A-Za-z0-9-])", text):
        value = int(match.group(0))
        if 1 <= value <= 100:
            mentions.append((match.start(), value))
    lower = text.lower()
    for word, value in NUMBER_WORDS.items():
        for match in re.finditer(rf"\b{word}\b", lower):
            mentions.append((match.start(), value))
    mentions.sort()
    return [value for _, value in mentions]


def objective_counts(text: str, slot_count: int) -> tuple[list[int | None], str]:
    if slot_count == 0:
        return [], "exact"
    values = ordered_numeric_mentions(text)
    if len(values) == slot_count:
        return values, "exact_text_order"
    if len(values) > slot_count:
        return values[-slot_count:], "ambiguous_extra_numbers"
    if len(values) == 0 and slot_count == 1:
        return [1], "implicit_single"
    return values + [None] * (slot_count - len(values)), "missing_counts"


def points_from_spawns(spawns: Any) -> list[Point]:
    points: list[Point] = []
    if not isinstance(spawns, dict):
        return points
    for zone_id, raw_points in spawns.items():
        if not isinstance(zone_id, int):
            continue
        for raw in seq(raw_points):
            values = seq(raw)
            if len(values) >= 2 and all(isinstance(value, (int, float)) for value in values[:2]):
                points.append(Point(zone_id, float(values[0]), float(values[1])))
    return points


def entity_name(data: QuestieData, entity_type: str, entity_id: int, fallback: str) -> str:
    if entity_type == "npc":
        return data.local_name(data.npc_names, entity_id, fallback)
    if entity_type == "object":
        return data.local_name(data.object_names, entity_id, fallback)
    return data.local_name(data.item_names, entity_id, fallback)


def summarize_points(points: list[Point]) -> tuple[list[int], dict[str, dict[str, float]]]:
    by_zone: dict[int, list[Point]] = defaultdict(list)
    for point in points:
        by_zone[point.zone_id].append(point)
    reps: dict[str, dict[str, float]] = {}
    for zone_id, zone_points in by_zone.items():
        reps[str(zone_id)] = {
            "x": round(float(median(point.x for point in zone_points)), 2),
            "y": round(float(median(point.y for point in zone_points)), 2),
            "spawn_count": len(zone_points),
            "min_x": round(min(point.x for point in zone_points), 2),
            "max_x": round(max(point.x for point in zone_points), 2),
            "min_y": round(min(point.y for point in zone_points), 2),
            "max_y": round(max(point.y for point in zone_points), 2),
        }
    return sorted(by_zone), reps


def make_npc_entity(data: QuestieData, npc_id: int) -> Entity | None:
    row = data.npcs.get(npc_id)
    if not isinstance(row, dict):
        return None
    raw_name = str(row.get(NPC_NAME) or f"NPC {npc_id}")
    points = points_from_spawns(row.get(NPC_SPAWNS))
    zones, reps = summarize_points(points)
    return Entity(
        entity_type="npc",
        entity_id=npc_id,
        name=entity_name(data, "npc", npc_id, raw_name),
        min_level=row.get(NPC_MIN_LEVEL) if isinstance(row.get(NPC_MIN_LEVEL), int) else None,
        max_level=row.get(NPC_MAX_LEVEL) if isinstance(row.get(NPC_MAX_LEVEL), int) else None,
        min_health=row.get(NPC_MIN_HEALTH) if isinstance(row.get(NPC_MIN_HEALTH), int) else None,
        max_health=row.get(NPC_MAX_HEALTH) if isinstance(row.get(NPC_MAX_HEALTH), int) else None,
        rank=row.get(NPC_RANK) if isinstance(row.get(NPC_RANK), int) else None,
        spawn_count=len(points),
        zones=zones,
        representative_by_zone=reps,
    )


def make_object_entity(data: QuestieData, object_id: int) -> Entity | None:
    row = data.objects.get(object_id)
    if not isinstance(row, dict):
        return None
    raw_name = str(row.get(OBJECT_NAME) or f"Object {object_id}")
    points = points_from_spawns(row.get(OBJECT_SPAWNS))
    zones, reps = summarize_points(points)
    return Entity(
        entity_type="object",
        entity_id=object_id,
        name=entity_name(data, "object", object_id, raw_name),
        spawn_count=len(points),
        zones=zones,
        representative_by_zone=reps,
    )


def make_item_entity(data: QuestieData, item_id: int) -> Entity | None:
    row = data.items.get(item_id)
    if not isinstance(row, dict):
        return None
    raw_name = str(row.get(ITEM_NAME) or f"Item {item_id}")
    return Entity(
        entity_type="item",
        entity_id=item_id,
        name=entity_name(data, "item", item_id, raw_name),
        spawn_count=0,
        zones=[],
        representative_by_zone={},
    )


def entities_for_start_finish(data: QuestieData, group: Any) -> list[Entity]:
    result: list[Entity] = []
    for npc_id in _ids(group, 1):
        if entity := make_npc_entity(data, npc_id):
            result.append(entity)
    for object_id in _ids(group, 2):
        if entity := make_object_entity(data, object_id):
            result.append(entity)
    for item_id in _ids(group, 3):
        if entity := make_item_entity(data, item_id):
            result.append(entity)
    return result


def raw_objective_ids(row: dict[Any, Any]) -> dict[str, list[int]]:
    result = {"kill": [], "object": [], "item": [], "reputation": [], "event": []}
    raw = row.get(Q_OBJECTIVES)
    if not isinstance(raw, dict):
        return result
    mapping = {1: "kill", 2: "object", 3: "item", 4: "reputation"}
    for key, label in mapping.items():
        for entry in seq(raw.get(key)):
            values = seq(entry)
            if values and isinstance(values[0], int):
                result[label].append(int(values[0]))
    for entry in seq(raw.get(5)):
        values = seq(entry)
        if values:
            first = values[0]
            if isinstance(first, dict):
                for npc_id in seq(first):
                    if isinstance(npc_id, int):
                        result["event"].append(int(npc_id))
            else:
                result["event"].append(0)
    if row.get(Q_TRIGGER_END):
        result["event"].append(0)
    return result


def entity_in_zone(entity: Entity, zone_id: int) -> bool:
    return bool(entity.zones and zone_id in entity.zones)


def average_npc_level(entities: Iterable[Entity], zone_id: int | None = None) -> float | None:
    values: list[float] = []
    for entity in entities:
        if entity.entity_type != "npc":
            continue
        if zone_id is not None and not entity_in_zone(entity, zone_id):
            continue
        if entity.min_level is not None and entity.max_level is not None:
            values.append((entity.min_level + entity.max_level) / 2)
    return mean(values) if values else None


def average_npc_health(entities: Iterable[Entity], zone_id: int | None = None) -> float | None:
    values: list[float] = []
    for entity in entities:
        if entity.entity_type != "npc":
            continue
        if zone_id is not None and not entity_in_zone(entity, zone_id):
            continue
        if entity.min_health is not None and entity.max_health is not None:
            values.append((entity.min_health + entity.max_health) / 2)
    return mean(values) if values else None


def npc_rank_flags(entities: Iterable[Entity]) -> list[str]:
    flags: set[str] = set()
    for entity in entities:
        if entity.entity_type != "npc" or entity.rank is None:
            continue
        if entity.rank == 1:
            flags.add("elite")
        elif entity.rank == 2:
            flags.add("rare_elite")
        elif entity.rank == 4:
            flags.add("rare")
        elif entity.rank == 3:
            flags.add("boss")
    return sorted(flags)


def source_entities_for_item(data: QuestieData, item_id: int) -> tuple[list[Entity], list[Entity]]:
    row = data.items.get(item_id)
    if not isinstance(row, dict):
        return [], []
    npcs = [entity for npc_id in seq(row.get(ITEM_NPC_DROPS)) if isinstance(npc_id, int)
            if (entity := make_npc_entity(data, int(npc_id))) is not None]
    objects = [entity for object_id in seq(row.get(ITEM_OBJECT_DROPS)) if isinstance(object_id, int)
               if (entity := make_object_entity(data, int(object_id))) is not None]
    return npcs, objects


def classify_objectives(
    data: QuestieData,
    row: dict[Any, Any],
    primary_zone_id: int,
    objective_text: str,
) -> tuple[list[Objective], list[str]]:
    raw = raw_objective_ids(row)
    slot_order: list[tuple[str, int]] = []
    for label in ("kill", "object", "item", "reputation", "event"):
        slot_order.extend((label, entity_id) for entity_id in raw[label])
    counts, count_confidence = objective_counts(objective_text, len(slot_order))
    result: list[Objective] = []
    review: list[str] = []
    if count_confidence not in {"exact", "exact_text_order", "implicit_single"}:
        review.append(f"objective_count:{count_confidence}")

    for index, (label, entity_id) in enumerate(slot_order):
        count = counts[index] if index < len(counts) else None
        flags: list[str] = []
        if label == "kill":
            sources = [make_npc_entity(data, entity_id)]
            sources = [source for source in sources if source is not None]
            zone_sources = [source for source in sources if entity_in_zone(source, primary_zone_id)]
            chosen = zone_sources or sources
            flags.extend(npc_rank_flags(chosen))
            spawn_count = sum(source.spawn_count for source in chosen)
            if count == 1 and spawn_count <= 5:
                mechanic = "single_named_or_rare_kill"
            elif flags:
                mechanic = "elite_or_boss_shared_kills"
            else:
                mechanic = "regular_shared_kills"
            result.append(Objective(
                objective_type="kill",
                required_count=count,
                entity_ids=[entity_id],
                item_id=None,
                item_name=None,
                sources=chosen,
                count_confidence=count_confidence,
                fivebox_mode="kill_progress_shared_expected",
                mechanic=mechanic,
                difficulty_flags=flags,
            ))
        elif label == "object":
            source = make_object_entity(data, entity_id)
            chosen = [source] if source else []
            spawn_count = source.spawn_count if source else 0
            mechanic = "single_fixed_object" if count == 1 and spawn_count <= 5 else "multiple_world_objects"
            result.append(Objective(
                objective_type="object",
                required_count=count,
                entity_ids=[entity_id],
                item_id=None,
                item_name=None,
                sources=chosen,
                count_confidence=count_confidence,
                fivebox_mode="object_interaction_per_character_expected",
                mechanic=mechanic,
                difficulty_flags=[],
            ))
        elif label == "item":
            item_row = data.items.get(entity_id)
            raw_name = str(item_row.get(ITEM_NAME) if isinstance(item_row, dict) else f"Item {entity_id}")
            item_name = entity_name(data, "item", entity_id, raw_name)
            npc_sources, object_sources = source_entities_for_item(data, entity_id)
            zone_npcs = [source for source in npc_sources if entity_in_zone(source, primary_zone_id)]
            zone_objects = [source for source in object_sources if entity_in_zone(source, primary_zone_id)]
            chosen_npcs = zone_npcs or npc_sources
            chosen_objects = zone_objects or object_sources
            flags.extend(npc_rank_flags(chosen_npcs))
            if chosen_objects and not chosen_npcs:
                mechanic = "task_item_world_object_pickup"
                fivebox = "item_pickup_per_character_expected"
                sources = chosen_objects
            elif chosen_npcs:
                spawn_count = sum(source.spawn_count for source in chosen_npcs)
                if count == 1 and len(chosen_npcs) == 1 and (spawn_count <= 5 or flags):
                    mechanic = "single_named_creature_task_item"
                elif count == 1:
                    mechanic = "single_regular_creature_task_item"
                else:
                    mechanic = "multiple_creature_task_item_drops"
                fivebox = "personal_loot_roll_per_character_expected"
                sources = chosen_npcs
            elif chosen_objects:
                mechanic = "mixed_object_item_pickup"
                fivebox = "item_pickup_per_character_expected"
                sources = chosen_objects
            else:
                mechanic = "item_source_not_in_questie"
                fivebox = "unknown_or_supplied_item"
                sources = []
                review.append(f"item_source_missing:{entity_id}")
            result.append(Objective(
                objective_type="item",
                required_count=count,
                entity_ids=[source.entity_id for source in sources],
                item_id=entity_id,
                item_name=item_name,
                sources=sources,
                count_confidence=count_confidence,
                fivebox_mode=fivebox,
                mechanic=mechanic,
                difficulty_flags=flags,
            ))
        elif label == "event":
            sources: list[Entity] = []
            if entity_id:
                if source := make_npc_entity(data, entity_id):
                    sources.append(source)
            result.append(Objective(
                objective_type="event",
                required_count=count or 1,
                entity_ids=[entity_id] if entity_id else [],
                item_id=None,
                item_name=None,
                sources=sources,
                count_confidence=count_confidence,
                fivebox_mode="event_or_use_per_character_unknown",
                mechanic="spell_use_area_trigger_or_scripted_event",
                difficulty_flags=[],
            ))
            review.append("scripted_event_mechanic")
        else:
            result.append(Objective(
                objective_type=label,
                required_count=count,
                entity_ids=[entity_id],
                item_id=None,
                item_name=None,
                sources=[],
                count_confidence=count_confidence,
                fivebox_mode="unknown",
                mechanic="reputation_or_special_objective",
                difficulty_flags=[],
            ))
            review.append(f"special_objective:{label}")
    return result, sorted(set(review))


def classify_task(objectives: list[Objective], text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    flags: list[str] = []
    if any(re.search(pattern, lower) for pattern in ESCORT_PATTERNS):
        flags.append("escort_or_defense_text")
    if any(re.search(pattern, lower) for pattern in USE_PATTERNS):
        flags.append("active_item_or_spell_use")
    if not objectives:
        return "travel_dialogue_or_turnin", flags
    mechanics = {objective.mechanic for objective in objectives}
    if len(objectives) == 1:
        mechanic = objectives[0].mechanic
        mapping = {
            "regular_shared_kills": "shared_kill",
            "single_named_or_rare_kill": "single_named_kill",
            "elite_or_boss_shared_kills": "elite_or_boss_kill",
            "single_fixed_object": "fixed_object_interaction",
            "multiple_world_objects": "world_object_collection",
            "task_item_world_object_pickup": "world_object_item_collection",
            "single_named_creature_task_item": "single_named_drop",
            "single_regular_creature_task_item": "single_creature_drop",
            "multiple_creature_task_item_drops": "multi_creature_personal_drop",
            "spell_use_area_trigger_or_scripted_event": "scripted_use_or_event",
        }
        return mapping.get(mechanic, mechanic), flags
    if mechanics <= {"regular_shared_kills", "single_named_or_rare_kill", "elite_or_boss_shared_kills"}:
        return "multi_target_shared_kill", flags
    if any("task_item" in mechanic or "drop" in mechanic for mechanic in mechanics):
        return "mixed_with_personal_item", flags
    return "mixed_objectives", flags


def route_catalog(root: Path) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    quests: dict[int, dict[str, Any]] = {}
    zone_names: dict[int, str] = {}
    for path in root.glob("data/routes/world-candidate/*/route.json"):
        route = json.loads(path.read_text(encoding="utf-8"))
        zone_id = int(route["map_area_id"])
        zone_name = str(route["zone"])
        zone_names[zone_id] = zone_name
        step_anchors: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for step in route.get("steps", []):
            phase = {"接取": "accept", "完成目标": "objective", "交付": "turnin"}.get(step.get("action"))
            if not phase:
                continue
            anchor = step.get("anchor_details") or {}
            representative = anchor.get("representative")
            for quest_id in step.get("quest_ids", []):
                if isinstance(quest_id, int) and isinstance(representative, dict):
                    step_anchors[quest_id][phase].append({
                        "zone_id": zone_id,
                        "zone": zone_name,
                        "x": representative.get("x"),
                        "y": representative.get("y"),
                    })
        for quest in route.get("quest_catalog", []):
            quest_id = int(quest["quest_id"])
            record = quests.setdefault(quest_id, {"catalog": quest, "zones": [], "anchors": defaultdict(list)})
            record["zones"].append({"zone_id": zone_id, "zone": zone_name})
            for phase, values in step_anchors.get(quest_id, {}).items():
                record["anchors"][phase].extend(values)
    return quests, zone_names


def point_distance(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    if a.get("zone_id") != b.get("zone_id"):
        return None
    if not all(isinstance(a.get(key), (int, float)) and isinstance(b.get(key), (int, float)) for key in ("x", "y")):
        return None
    return math.hypot(float(a["x"]) - float(b["x"]), float(a["y"]) - float(b["y"]))


def standalone_distance_index(anchors: dict[str, list[dict[str, Any]]]) -> tuple[float | None, bool]:
    accept = anchors.get("accept", [])
    objective = anchors.get("objective", [])
    turnin = anchors.get("turnin", [])
    candidates: list[tuple[float, bool]] = []
    for start in accept or objective or turnin:
        for target in objective or turnin:
            first = point_distance(start, target)
            if first is None:
                continue
            if turnin:
                for finish in turnin:
                    second = point_distance(target, finish)
                    if second is not None:
                        candidates.append((first + second, False))
            else:
                candidates.append((first, False))
    if candidates:
        return min(candidates, key=lambda item: item[0])
    all_zones = {point.get("zone_id") for values in anchors.values() for point in values}
    return None, len(all_zones) > 1


def level_penalty(target_level: float | None, player_level: int) -> tuple[float, float, float]:
    if target_level is None:
        return 1.0, 1.0, 1.0
    delta = target_level - player_level
    if delta <= 0:
        return 1.0, 1.0, 1.05
    if delta <= 1:
        return 1.05, 1.12, 1.25
    if delta <= 2:
        return 1.12, 1.32, 1.65
    if delta <= 3:
        return 1.25, 1.70, 2.30
    if delta <= 4:
        return 1.45, 2.35, 3.40
    return 1.80, 3.50, 6.00


def kills_for_personal_drops(count: int, probability: float, characters: int = 5) -> float:
    if probability >= 0.999:
        return float(count)
    expected = count / probability
    std = math.sqrt(count * (1 - probability)) / probability
    slowest_character_premium = 1.20 * std if characters >= 5 else 0.80 * std
    return expected + slowest_character_premium


def npc_objective_time(
    objective: Objective,
    player_level: int,
    primary_zone_id: int,
) -> TimeRange:
    count = objective.required_count or 1
    sources = [source for source in objective.sources if source.entity_type == "npc"]
    zone_sources = [source for source in sources if entity_in_zone(source, primary_zone_id)] or sources
    if objective.objective_type == "item" and len(zone_sources) > 1:
        # Item sources are alternatives, not simultaneous targets. Prefer a
        # source that is currently hittable, then density, then lower level.
        feasible = [
            source for source in zone_sources
            if source.min_level is not None and source.min_level <= player_level + 2
        ] or zone_sources
        zone_sources = [max(
            feasible,
            key=lambda source: (
                source.spawn_count,
                -float(source.min_level or 99),
                -float(source.max_health or 0),
            ),
        )]
    target_level = average_npc_level(zone_sources)
    target_health = average_npc_health(zone_sources)
    if target_health is None:
        target_health = max(250.0, (target_level or player_level) ** 2 * 1.0)
    dps_low, dps_central, dps_high = interpolate_profile(player_level)
    penalty_low, penalty_central, penalty_high = level_penalty(target_level, player_level)

    # DPS tuple is pessimistic, central, optimistic by value; invert for time.
    seconds_per_kill_optimistic = target_health / dps_high * penalty_low + 6.0
    seconds_per_kill_central = target_health / dps_central * penalty_central + 9.0
    seconds_per_kill_pessimistic = target_health / dps_low * penalty_high + 14.0

    if objective.objective_type == "kill":
        kills_low = kills_central = kills_high = float(count)
    elif objective.mechanic == "single_named_creature_task_item":
        kills_low, kills_central, kills_high = 1.0, 1.0, 2.0
    else:
        # Do not claim a drop rate. These are explicit scenario bounds.
        kills_low = kills_for_personal_drops(count, 1.00)
        kills_central = kills_for_personal_drops(count, 0.50)
        kills_high = kills_for_personal_drops(count, 0.25)

    loot_seconds_low = 0.0 if objective.objective_type == "kill" else kills_low * 4.0 * 5
    loot_seconds_central = 0.0 if objective.objective_type == "kill" else kills_central * 7.0 * 5
    loot_seconds_high = 0.0 if objective.objective_type == "kill" else kills_high * 10.0 * 5

    result = TimeRange(
        optimistic=(kills_low * seconds_per_kill_optimistic + loot_seconds_low) / 60.0,
        central=(kills_central * seconds_per_kill_central + loot_seconds_central) / 60.0,
        pessimistic=(kills_high * seconds_per_kill_pessimistic + loot_seconds_high) / 60.0,
    )
    if any(flag in objective.difficulty_flags for flag in ("elite", "rare_elite", "boss")):
        result.central += 1.5
        result.pessimistic += 5.0
    return result


def object_objective_time(objective: Objective) -> TimeRange:
    count = objective.required_count or 1
    interactions = count * 5
    source_spawn_count = sum(source.spawn_count for source in objective.sources)
    movement_factor = 1.0 + (0.4 if source_spawn_count <= 3 and count > 1 else 0.0)
    return TimeRange(
        optimistic=interactions * 5.0 / 60.0,
        central=interactions * 8.0 * movement_factor / 60.0,
        pessimistic=interactions * 13.0 * movement_factor / 60.0 + (3.0 if count > 1 else 1.0),
    )


def objective_time(objective: Objective, player_level: int, zone_id: int) -> TimeRange:
    if objective.objective_type == "kill":
        return npc_objective_time(objective, player_level, zone_id)
    if objective.objective_type == "item":
        if any(source.entity_type == "npc" for source in objective.sources):
            return npc_objective_time(objective, player_level, zone_id)
        if any(source.entity_type == "object" for source in objective.sources):
            return object_objective_time(objective)
        count = objective.required_count or 1
        return TimeRange(max(1.0, count * 0.5), max(2.0, count * 1.0), max(5.0, count * 2.0))
    if objective.objective_type == "object":
        return object_objective_time(objective)
    if objective.objective_type == "event":
        count = objective.required_count or 1
        return TimeRange(count * 0.7, count * 1.5, count * 4.0)
    return TimeRange(2.0, 5.0, 12.0)


def add_ranges(*ranges: TimeRange) -> TimeRange:
    return TimeRange(
        optimistic=sum(value.optimistic for value in ranges),
        central=sum(value.central for value in ranges),
        pessimistic=sum(value.pessimistic for value in ranges),
    )


def travel_time(distance_index: float | None, zone_id: int, player_level: int, cross_zone: bool) -> TimeRange:
    if cross_zone:
        return TimeRange(8.0, 18.0, 35.0)
    if distance_index is None:
        return TimeRange(1.0, 3.0, 8.0)
    diagonal = ZONE_DIAGONAL_MINUTES_100_MOUNT.get(zone_id)
    if diagonal is None:
        return TimeRange(distance_index * 0.07, distance_index * 0.12, distance_index * 0.20)
    mount_factor = 1.25 if player_level < 40 else 1.0
    normalized = distance_index / math.sqrt(100 ** 2 + 100 ** 2)
    central = normalized * diagonal * mount_factor
    return TimeRange(central * 0.75, central, central * 1.55)


def interaction_time(objectives: list[Objective], task_class: str) -> TimeRange:
    # Five accepts and five turn-ins. The optimizer later amortizes this when
    # multiple quests share the same NPC. Escort execution is a separate
    # component and must not be counted here.
    return TimeRange(0.9, 1.4, 2.4)


def entity_zones(entities: Iterable[Entity]) -> set[int]:
    return {zone for entity in entities for zone in (entity.zones or [])}


def candidate_tasks(
    root: Path,
    data: QuestieData,
    source: Path,
    route_meta: dict[int, dict[str, Any]],
    zone_names: dict[int, str],
) -> list[TaskRecord]:
    meta = _parse_zone_metadata(source)
    records: list[TaskRecord] = []
    for quest_id, row in data.quests.items():
        if not isinstance(quest_id, int) or not isinstance(row, dict):
            continue
        if not _eligible(data, row, BLOOD_ELF_RACE_FLAG, PALADIN_CLASS_FLAG):
            continue
        required_level = int(row.get(Q_REQUIRED_LEVEL) or 0)
        quest_level = int(row.get(Q_LEVEL) or 0)
        xp_row = data.quest_xp.get(quest_id)
        xp_db_level = int(xp_row.get(1) or 0) if isinstance(xp_row, dict) else 0
        xp_db_base = int(xp_row.get(2) or 0) if isinstance(xp_row, dict) else 0
        if required_level > 54:
            continue
        level_for_band = xp_db_level or quest_level
        if not (30 <= level_for_band <= 60 or quest_id in KNOWN_CURRENT_ACTIVE):
            continue

        raw_zone = row.get(Q_ZONE_OR_SORT)
        if not isinstance(raw_zone, int):
            continue
        primary_zone_id = _parent_zone(raw_zone, meta["parents"])
        if primary_zone_id in meta["dungeons"]:
            continue
        zone_name_en = meta["names"].get(primary_zone_id, f"Zone {primary_zone_id}")
        primary_zone = meta["zh"].get(zone_name_en, zone_names.get(primary_zone_id, zone_name_en))

        english_name = str(row.get(1) or f"Quest {quest_id}")
        name = data.local_name(data.quest_names, quest_id, english_name)
        objective_text_en = ""
        raw_description = row.get(8)
        if isinstance(raw_description, dict) and isinstance(raw_description.get(1), str):
            objective_text_en = raw_description[1]
        catalog = route_meta.get(quest_id, {}).get("catalog", {})
        objective_text_zh = str(catalog.get("objective_text") or "")

        objectives, review = classify_objectives(data, row, primary_zone_id, objective_text_en)
        task_class, text_flags = classify_task(objectives, objective_text_en)
        if "escort_or_defense_text" in text_flags:
            task_class = "escort_or_defense"

        start_entities = entities_for_start_finish(data, row.get(Q_START))
        finish_entities = entities_for_start_finish(data, row.get(Q_FINISH))
        pre_single = [int(value) for value in seq(row.get(Q_PRE_SINGLE)) if isinstance(value, int)]
        pre_group = [int(value) for value in seq(row.get(Q_PRE_GROUP)) if isinstance(value, int)]
        next_quest = row.get(Q_NEXT) if isinstance(row.get(Q_NEXT), int) else None

        chain_flags: list[str] = []
        if pre_single:
            chain_flags.append("has_any_of_prerequisites")
        if pre_group:
            chain_flags.append("has_all_prerequisites")
        if next_quest:
            chain_flags.append("has_direct_followup")

        route_entry = route_meta.get(quest_id, {})
        all_route_zones = sorted({zone["zone"] for zone in route_entry.get("zones", [])})
        anchors = route_entry.get("anchors", {})
        distance_index, cross_zone = standalone_distance_index(anchors)

        all_objective_sources = [source for objective in objectives for source in objective.sources]
        objective_source_zones = entity_zones(all_objective_sources)
        start_zones = entity_zones(start_entities)
        finish_zones = entity_zones(finish_entities)
        route_flags: list[str] = []
        if cross_zone or len(start_zones | objective_source_zones | finish_zones) > 1:
            route_flags.append("cross_zone_or_multi_zone")
        if not route_entry:
            route_flags.append("automatic_route_candidate_missing")
            review.append("not_in_world_candidate_union")
        if not start_entities:
            route_flags.append("non_npc_start_or_missing_start")
        if not finish_entities:
            route_flags.append("non_npc_finish_or_missing_finish")
        if any(entity.zones and any(zone in meta["dungeons"] for zone in entity.zones) for entity in all_objective_sources):
            route_flags.append("dungeon_objective_source")
        if any(flag in text_flags for flag in ("escort_or_defense_text", "active_item_or_spell_use")):
            route_flags.extend(text_flags)
        if any(objective.mechanic == "multiple_creature_task_item_drops" for objective in objectives):
            route_flags.append("drop_rate_required")
            review.append("server_drop_rate_needed")
        if any(objective.mechanic == "task_item_world_object_pickup" for objective in objectives):
            route_flags.append("object_respawn_and_multi_click_unknown")
        if any(objective.difficulty_flags for objective in objectives):
            route_flags.append("elite_or_rare_target")

        earliest_level = max(CURRENT_LEVEL, required_level if required_level > 0 else 1)
        # Do not assume a character can efficiently fight targets 5+ levels up.
        # Multiple item sources are alternatives, so use the lowest viable
        # source level for that objective rather than averaging every source.
        target_levels: list[float] = []
        for objective in objectives:
            levels = [
                (source.min_level + source.max_level) / 2
                for source in objective.sources
                if source.entity_type == "npc"
                and source.min_level is not None
                and source.max_level is not None
                and (not source.zones or primary_zone_id in source.zones)
            ]
            if not levels:
                continue
            target_levels.append(min(levels) if objective.objective_type == "item" else mean(levels))
        if target_levels:
            earliest_level = max(earliest_level, min(54, math.floor(max(target_levels) - 2)))
        earliest_level = min(54, max(CURRENT_LEVEL, earliest_level))

        objective_ranges = [objective_time(objective, earliest_level, primary_zone_id) for objective in objectives]
        base_objective_time = add_ranges(*objective_ranges) if objective_ranges else TimeRange(0.0, 0.0, 0.0)
        travel = travel_time(distance_index, primary_zone_id, earliest_level, "cross_zone_or_multi_zone" in route_flags)
        interactions = interaction_time(objectives, task_class)
        escort_extra = TimeRange(4.0, 9.0, 20.0) if task_class == "escort_or_defense" else TimeRange(0.0, 0.0, 0.0)
        standalone = add_ranges(base_objective_time, travel, interactions, escort_extra)
        time_components = {
            "objectives": [
                {
                    "objective_index": index,
                    "objective_type": objective.objective_type,
                    "mechanic": objective.mechanic,
                    "time": asdict(objective_ranges[index]),
                }
                for index, objective in enumerate(objectives)
            ],
            "travel": asdict(travel),
            "interactions": asdict(interactions),
            "escort_or_defense": asdict(escort_extra),
        }
        standalone = TimeRange(
            round(standalone.optimistic, 2),
            round(standalone.central, 2),
            round(standalone.pessimistic, 2),
        )

        xp_by_level = {str(level): quest_xp_at_level(data, quest_id, level) for level in range(35, 55)}
        xp_earliest = xp_by_level.get(str(earliest_level), 0)
        rate = round(xp_earliest / standalone.central, 1) if standalone.central > 0 and xp_earliest > 0 else None

        if quest_id in KNOWN_COMPLETED_OBJECTIVE_NOT_ALL_TURNED_IN:
            status = "objective_complete_turnin_not_synced"
        elif quest_id in KNOWN_CURRENT_ACTIVE:
            status = "known_active_or_recently_active"
        elif quest_id in KNOWN_COMPLETED_AFTER_STALE_JOURNEY:
            status = "known_completed"
        elif required_level <= CURRENT_LEVEL:
            status = "available_by_level_subject_to_prerequisites"
        else:
            status = "future_level_band"

        confidence = "medium"
        if not objectives or task_class in {"shared_kill", "single_named_kill", "fixed_object_interaction"}:
            confidence = "medium_high"
        if review or any(flag in route_flags for flag in (
            "drop_rate_required", "object_respawn_and_multi_click_unknown",
            "cross_zone_or_multi_zone", "dungeon_objective_source",
            "automatic_route_candidate_missing",
        )):
            confidence = "low_until_manual_review"

        records.append(TaskRecord(
            quest_id=quest_id,
            name=name,
            english_name=english_name,
            status=status,
            primary_zone_id=primary_zone_id,
            primary_zone=primary_zone,
            all_route_zones=all_route_zones,
            required_level=required_level,
            quest_level=quest_level,
            xp_db_level=xp_db_level,
            xp_db_base=xp_db_base,
            full_xp_through_level=xp_db_level + 5 if xp_db_level > 0 else 0,
            xp_by_completion_level=xp_by_level,
            objective_text_en=objective_text_en,
            objective_text_zh=objective_text_zh,
            task_class=task_class,
            objectives=objectives,
            start_entities=start_entities,
            finish_entities=finish_entities,
            pre_single=pre_single,
            pre_group=pre_group,
            next_quest=next_quest,
            chain_flags=chain_flags,
            route_flags=sorted(set(route_flags)),
            standalone_distance_index=round(distance_index, 2) if distance_index is not None else None,
            standalone_time_components=time_components,
            standalone_time_at_earliest_level=standalone,
            earliest_completion_level=earliest_level,
            xp_at_earliest_completion=xp_earliest,
            xp_per_central_minute_standalone=rate,
            confidence=confidence,
            manual_review_reasons=sorted(set(review)),
        ))
    return sorted(records, key=lambda record: (record.earliest_completion_level, record.primary_zone, record.quest_id))


def csv_row(record: TaskRecord) -> dict[str, Any]:
    objective_summary = "; ".join(
        f"{objective.objective_type}:{objective.mechanic}:count={objective.required_count}:"
        f"sources={','.join(source.name for source in objective.sources[:4])}"
        for objective in record.objectives
    )
    return {
        "quest_id": record.quest_id,
        "name": record.name,
        "status": record.status,
        "zone": record.primary_zone,
        "required_level": record.required_level,
        "quest_level": record.quest_level,
        "xp_db_level": record.xp_db_level,
        "xp_db_base": record.xp_db_base,
        "earliest_completion_level": record.earliest_completion_level,
        "xp_at_earliest_completion": record.xp_at_earliest_completion,
        "task_class": record.task_class,
        "objectives": objective_summary,
        "time_optimistic_min": record.standalone_time_at_earliest_level.optimistic,
        "time_central_min": record.standalone_time_at_earliest_level.central,
        "time_pessimistic_min": record.standalone_time_at_earliest_level.pessimistic,
        "xp_per_central_minute": record.xp_per_central_minute_standalone,
        "distance_index": record.standalone_distance_index,
        "pre_single": ",".join(map(str, record.pre_single)),
        "pre_group": ",".join(map(str, record.pre_group)),
        "next_quest": record.next_quest or "",
        "route_flags": ",".join(record.route_flags),
        "confidence": record.confidence,
        "manual_review": ",".join(record.manual_review_reasons),
    }


def write_review_report(records: list[TaskRecord], path: Path) -> None:
    available = [record for record in records if record.required_level <= CURRENT_LEVEL]
    future = [record for record in records if record.required_level > CURRENT_LEVEL]
    class_counts = Counter(record.task_class for record in records)
    zone_counts = Counter(record.primary_zone for record in records)
    review_counts = Counter(reason for record in records for reason in record.manual_review_reasons)
    lines = [
        "# 35—55任务基础表生成审计",
        "",
        f"- 全候选任务：{len(records)}。",
        f"- 35级按等级可接候选（仍受前置限制）：{len(available)}。",
        f"- 36—54级后续候选：{len(future)}。",
        "- 每个任务均保存35—54各交付等级的精确任务经验；不是用任务中位数或等级平均经验推断。",
        "- 时间是逐任务结构估算：NPC血量/等级、目标数量、五开共享/个人模式、坐标距离、接交操作。未知掉率保存三种情景，不伪装为服务器实测值。",
        "",
        "## 类型数量",
        "",
    ]
    for name, count in class_counts.most_common():
        lines.append(f"- `{name}`：{count}")
    lines.extend(["", "## 地图数量", ""])
    for name, count in zone_counts.most_common():
        lines.append(f"- {name}：{count}")
    lines.extend(["", "## 人工复核队列", ""])
    for reason, count in review_counts.most_common():
        lines.append(f"- `{reason}`：{count}")
    lines.extend(["", "## 当前不能直接用于最终路线的原因", ""])
    lines.extend([
        "1. 怪物掉落率不在Questie客户端数据库中；被选入最终路线的个人掉落任务必须查外部3.3.5数据库或本服实跑。",
        "2. 固定物体是否五号可连续点击、点击后是否消失，需要逐任务验证。",
        "3. 任务独立时间包含独立接交和独立跑路；任务块合并时必须去重，不能把独立分钟直接相加。",
        "4. 跨地图飞行、船和飞艇要在任务块层加入实测交通边，不能藏进单任务默认值。",
        "5. 当前Questie人物历程文件只更新到33级，35级后的最终任务状态以CURRENT和用户现场记录为准。",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a per-quest 35-55 five-box task foundation")
    parser.add_argument("--questie", default="_sandbox/sources/Questie-v11.32.3.zip")
    parser.add_argument("--json", default="data/routes/horde/blood-elf/35-55-task-foundation.json")
    parser.add_argument("--csv", default="data/routes/horde/blood-elf/35-55-task-foundation.csv")
    parser.add_argument("--review", default="docs/archive/analysis/2026-08-04-35-55-task-foundation-review.md")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = (root / args.questie).resolve()
    data = load_questie(source)
    route_meta, zone_names = route_catalog(root)
    records = candidate_tasks(root, data, source, route_meta, zone_names)

    output_json = root / args.json
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "questie_version": data.version,
        "questie_sha256": data.source_sha256,
        "server_quest_xp_multiplier": SERVER_QUEST_XP_MULTIPLIER,
        "current_level": CURRENT_LEVEL,
        "target_level": TARGET_LEVEL,
        "method": {
            "xp": "Questie WotLK QuestXP exact level-adjustment and rounding, then verified server x2 multiplier",
            "time": "per-quest structural range; selected route requires manual drop/object/transport verification",
            "personal_drop_scenarios": {"optimistic": 1.0, "central_unverified": 0.5, "pessimistic": 0.25},
            "combat": "one active paladin; NPC health and level with explicit DPS profile",
        },
        "task_count": len(records),
        "available_at_35_by_level_count": sum(record.required_level <= CURRENT_LEVEL for record in records),
        "tasks": [asdict(record) for record in records],
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output_csv = root / args.csv
    rows = [csv_row(record) for record in records]
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["quest_id"])
        writer.writeheader()
        writer.writerows(rows)

    review_path = root / args.review
    review_path.parent.mkdir(parents=True, exist_ok=True)
    write_review_report(records, review_path)

    print(json.dumps({
        "task_count": len(records),
        "available_at_35_by_level": sum(record.required_level <= CURRENT_LEVEL for record in records),
        "manual_review_count": sum(bool(record.manual_review_reasons) for record in records),
        "json": str(output_json.relative_to(root)),
        "csv": str(output_csv.relative_to(root)),
        "review": str(review_path.relative_to(root)),
        "classes": Counter(record.task_class for record in records).most_common(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
