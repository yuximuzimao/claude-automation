from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lib.questie_lua import seq
from lib.questie_source import QuestieData, load_questie


# WotLK 3.3.5 level-up requirements. Levels 30-35 are already confirmed by the
# current characters' UI; the remaining values follow the same client curve.
XP_TO_NEXT_LEVEL = {
    30: 38_800,
    31: 41_600,
    32: 44_600,
    33: 48_000,
    34: 51_400,
    35: 55_000,
    36: 58_700,
    37: 62_400,
    38: 66_200,
    39: 70_100,
    40: 74_300,
    41: 78_500,
    42: 82_800,
    43: 87_100,
    44: 91_600,
    45: 96_300,
    46: 101_000,
    47: 105_800,
    48: 110_700,
    49: 115_700,
    50: 120_900,
    51: 126_100,
    52: 131_500,
    53: 137_000,
    54: 142_500,
}

QUEST_XP_MULTIPLIER = 2.0
FIVEBOX_COUNT = 5

# These are modelling parameters, not game constants. They are intentionally
# kept in one place so real session observations can replace them.
DEFAULT_DROP_RATE = 0.50
PERSONAL_LOOT_SECONDS_PER_CORPSE = 9.0
FIXED_OBJECT_SECONDS_PER_CHARACTER = 7.0
NAMED_RESPAWN_WAIT_MINUTES = 2.0
EVENT_OBJECTIVE_MINUTES = 3.0
ACCEPT_TURNIN_BASE_MINUTES = 0.65
ACCEPT_TURNIN_PER_QUEST_MINUTES = 0.16

# Empirical or deliberately conservative overrides. Values are probabilities.
DROP_RATE_OVERRIDES = {
    5803: 0.40,   # Speck of Dream Dust: user observed a slow five-box block.
    5796: 0.45,   # Encrusted Tail Fin: kept conservative until first timed run.
    20519: 0.55,  # Southsea Pirate Hat: many overlapping pirate kills.
}

# Approximate time to cross a zone map diagonal while following a usable route.
# The value includes terrain/path inefficiency. Level 40+ uses a 100% mount;
# earlier blocks use the 60% mount multiplier below.
ZONE_DIAGONAL_MINUTES_AT_100 = {
    33: 12.0,   # Stranglethorn Vale
    357: 12.5,  # Feralas
    440: 11.0,  # Tanaris
    47: 9.5,    # The Hinterlands
    51: 6.5,    # Searing Gorge
    46: 8.0,    # Burning Steppes
    490: 8.0,   # Un'Goro Crater
    16: 10.0,   # Azshara
    361: 10.0,  # Felwood
    618: 10.5,  # Winterspring
    28: 8.5,    # Western Plaguelands
    139: 10.0,  # Eastern Plaguelands
    15: 10.0,   # Dustwallow Marsh
    405: 10.0,  # Desolace
    400: 9.0,   # Thousand Needles
}

ZONE_SLUGS = {
    33: "33-stranglethorn-vale",
    357: "357-feralas",
    440: "440-tanaris",
    47: "47-the-hinterlands",
    51: "51-searing-gorge",
    46: "46-burning-steppes",
    490: "490-un-goro-crater",
    16: "16-azshara",
    361: "361-felwood",
    618: "618-winterspring",
    28: "28-western-plaguelands",
    139: "139-eastern-plaguelands",
    15: "15-dustwallow-marsh",
    405: "405-desolace",
    400: "400-thousand-needles",
}

QUEST_OBJECTIVES = 10
QUEST_REQUIRED_LEVEL = 4
QUEST_LEVEL = 5
NPC_MIN_HEALTH = 2
NPC_MAX_HEALTH = 3
NPC_MIN_LEVEL = 4
NPC_MAX_LEVEL = 5
NPC_SPAWNS = 7
ITEM_NPC_DROPS = 2
ITEM_OBJECT_DROPS = 3
OBJECT_SPAWNS = 4


@dataclass
class ObjectiveEstimate:
    kind: str
    entity_ids: list[int]
    counts: list[int]
    expected_kills: float
    target_level: float | None
    spawn_count: int
    minutes: float
    confidence: str


@dataclass
class QuestEstimate:
    quest_id: int
    name: str
    required_level: int
    quest_level: int
    base_xp: int
    actual_xp: int
    objective_text: str
    objective_types: list[str]
    objective_minutes: float
    xp_per_objective_minute: float | None
    confidence: str
    objectives: list[ObjectiveEstimate]


def xp_remaining(level: int, progress: int, target_level: int) -> int:
    if level >= target_level:
        return 0
    total = XP_TO_NEXT_LEVEL[level] - progress
    for current in range(level + 1, target_level):
        total += XP_TO_NEXT_LEVEL[current]
    return total


def level_after_xp(level: int, progress: int, gained: int) -> tuple[int, int]:
    current_level = level
    current_progress = progress + gained
    while current_level in XP_TO_NEXT_LEVEL and current_progress >= XP_TO_NEXT_LEVEL[current_level]:
        current_progress -= XP_TO_NEXT_LEVEL[current_level]
        current_level += 1
    return current_level, current_progress


def _numbers_from_objective(text: str, wanted: int) -> list[int]:
    if wanted <= 0:
        return []
    # Ignore digits embedded in names such as OOX-22/FE. Quest objective text
    # otherwise places required counts in natural reading order.
    values = [
        int(match.group(0))
        for match in re.finditer(r"(?<![A-Za-z0-9-])\d{1,3}(?![A-Za-z0-9-])", text)
    ]
    values = [value for value in values if 0 < value <= 100]
    if len(values) >= wanted:
        return values[:wanted]
    return values + [1] * (wanted - len(values))


def _coords_count(spawns: Any, zone_id: int) -> int:
    if not isinstance(spawns, dict):
        return 0
    return len(seq(spawns.get(zone_id)))


def _npc_level(
    data: QuestieData,
    npc_ids: list[int],
    zone_id: int | None = None,
) -> float | None:
    levels: list[float] = []
    for npc_id in npc_ids:
        row = data.npcs.get(npc_id)
        if not isinstance(row, dict):
            continue
        if zone_id is not None and _coords_count(row.get(NPC_SPAWNS), zone_id) == 0:
            continue
        low = row.get(NPC_MIN_LEVEL)
        high = row.get(NPC_MAX_LEVEL)
        if isinstance(low, int) and isinstance(high, int):
            levels.append((low + high) / 2)
    return sum(levels) / len(levels) if levels else None


def _npc_ids_in_zone(data: QuestieData, npc_ids: list[int], zone_id: int) -> list[int]:
    return [
        npc_id
        for npc_id in npc_ids
        if isinstance(data.npcs.get(npc_id), dict)
        and _coords_count(data.npcs[npc_id].get(NPC_SPAWNS), zone_id) > 0
    ]


def _object_ids_in_zone(data: QuestieData, object_ids: list[int], zone_id: int) -> list[int]:
    return [
        object_id
        for object_id in object_ids
        if isinstance(data.objects.get(object_id), dict)
        and _coords_count(data.objects[object_id].get(OBJECT_SPAWNS), zone_id) > 0
    ]


def _npc_spawn_count(data: QuestieData, npc_ids: list[int], zone_id: int) -> int:
    total = 0
    for npc_id in npc_ids:
        row = data.npcs.get(npc_id)
        if isinstance(row, dict):
            total += _coords_count(row.get(NPC_SPAWNS), zone_id)
    return total


def _kill_seconds(player_level: int, target_level: float | None) -> float:
    if target_level is None:
        return 32.0
    delta = target_level - player_level
    if delta <= -3:
        combat = 17.0
    elif delta <= -2:
        combat = 20.0
    elif delta <= -1:
        combat = 23.0
    elif delta <= 0:
        combat = 27.0
    elif delta <= 1:
        combat = 33.0
    elif delta <= 2:
        combat = 43.0
    elif delta <= 3:
        combat = 58.0
    elif delta <= 4:
        combat = 82.0
    else:
        combat = 120.0
    # Pulling, target switching, short recovery and moving to the next spawn.
    return combat + 8.0


def _expected_shared_kills_for_personal_loot(required: int, drop_rate: float) -> float:
    # All five characters can inspect the same tagged corpse, but each has a
    # separate quest-item outcome. Approximate the slowest of five independent
    # negative-binomial completion times with a normal-order-statistic premium.
    mean = required / drop_rate
    std = math.sqrt(required * (1.0 - drop_rate)) / drop_rate
    return mean + 1.2 * std


def _raw_objectives(row: dict[Any, Any]) -> dict[str, list[int]]:
    result = {"kill": [], "object": [], "item": [], "event": []}
    objectives = row.get(QUEST_OBJECTIVES)
    if not isinstance(objectives, dict):
        return result
    for entry in seq(objectives.get(1)):
        values = seq(entry)
        if values and isinstance(values[0], int):
            result["kill"].append(values[0])
    for entry in seq(objectives.get(2)):
        values = seq(entry)
        if values and isinstance(values[0], int):
            result["object"].append(values[0])
    for entry in seq(objectives.get(3)):
        values = seq(entry)
        if values and isinstance(values[0], int):
            result["item"].append(values[0])
    for entry in seq(objectives.get(5)):
        values = seq(entry)
        if values:
            result["event"].append(1)
    if row.get(9):
        result["event"].append(1)
    return result


def estimate_quest(
    data: QuestieData,
    quest: dict[str, Any],
    zone_id: int,
    player_level: int,
) -> QuestEstimate:
    quest_id = int(quest["quest_id"])
    row = data.quests.get(quest_id)
    if not isinstance(row, dict):
        raise KeyError(f"Quest {quest_id} missing from Questie database")
    name = str(quest["name"])
    objective_text = str(quest.get("objective_text") or "")
    raw = _raw_objectives(row)
    total_slots = sum(len(values) for values in raw.values())
    parsed_counts = _numbers_from_objective(objective_text, total_slots)
    count_index = 0
    estimates: list[ObjectiveEstimate] = []

    kill_ids = raw["kill"]
    if kill_ids:
        counts = parsed_counts[count_index : count_index + len(kill_ids)]
        count_index += len(kill_ids)
        zone_kill_ids = _npc_ids_in_zone(data, kill_ids, zone_id)
        target_level = _npc_level(data, zone_kill_ids, zone_id)
        kills = float(sum(counts))
        spawn_count = _npc_spawn_count(data, zone_kill_ids, zone_id)
        minutes = kills * _kill_seconds(player_level, target_level) / 60.0
        if kills <= 1 and spawn_count <= 1:
            minutes += NAMED_RESPAWN_WAIT_MINUTES
        estimates.append(
            ObjectiveEstimate(
                kind="kill_shared",
                entity_ids=zone_kill_ids,
                counts=counts,
                expected_kills=kills,
                target_level=target_level,
                spawn_count=spawn_count,
                minutes=minutes,
                confidence="medium" if counts else "low",
            )
        )

    object_ids = raw["object"]
    if object_ids:
        counts = parsed_counts[count_index : count_index + len(object_ids)]
        count_index += len(object_ids)
        spawn_count = 0
        for object_id in object_ids:
            object_row = data.objects.get(object_id)
            if isinstance(object_row, dict):
                spawn_count += _coords_count(object_row.get(OBJECT_SPAWNS), zone_id)
        clicks = sum(counts) * FIVEBOX_COUNT
        minutes = clicks * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0
        if spawn_count <= 1 and clicks > FIVEBOX_COUNT:
            minutes += 1.5
        estimates.append(
            ObjectiveEstimate(
                kind="object_personal",
                entity_ids=object_ids,
                counts=counts,
                expected_kills=0.0,
                target_level=None,
                spawn_count=spawn_count,
                minutes=minutes,
                confidence="medium",
            )
        )

    item_ids = raw["item"]
    if item_ids:
        counts = parsed_counts[count_index : count_index + len(item_ids)]
        count_index += len(item_ids)
        total_minutes = 0.0
        total_expected_kills = 0.0
        source_ids: list[int] = []
        target_levels: list[float] = []
        spawn_count = 0
        for item_id, required in zip(item_ids, counts, strict=False):
            item_row = data.items.get(item_id)
            if not isinstance(item_row, dict):
                continue
            npc_ids = [int(value) for value in seq(item_row.get(ITEM_NPC_DROPS)) if isinstance(value, int)]
            object_sources = [
                int(value) for value in seq(item_row.get(ITEM_OBJECT_DROPS)) if isinstance(value, int)
            ]
            zone_npc_ids = _npc_ids_in_zone(data, npc_ids, zone_id)
            zone_object_sources = _object_ids_in_zone(data, object_sources, zone_id)
            if zone_npc_ids:
                source_ids.extend(zone_npc_ids)
                level = _npc_level(data, zone_npc_ids, zone_id)
                if level is not None:
                    target_levels.append(level)
                spawn_count += _npc_spawn_count(data, zone_npc_ids, zone_id)
                drop_rate = DROP_RATE_OVERRIDES.get(item_id, DEFAULT_DROP_RATE)
                expected_kills = _expected_shared_kills_for_personal_loot(required, drop_rate)
                total_expected_kills += expected_kills
                total_minutes += expected_kills * (
                    _kill_seconds(player_level, level) + PERSONAL_LOOT_SECONDS_PER_CORPSE
                ) / 60.0
            elif zone_object_sources:
                source_ids.extend(zone_object_sources)
                for object_id in zone_object_sources:
                    object_row = data.objects.get(object_id)
                    if isinstance(object_row, dict):
                        spawn_count += _coords_count(object_row.get(OBJECT_SPAWNS), zone_id)
                total_minutes += required * FIVEBOX_COUNT * FIXED_OBJECT_SECONDS_PER_CHARACTER / 60.0
            else:
                total_minutes += max(2.0, required * 0.5)
        estimates.append(
            ObjectiveEstimate(
                kind="loot_personal",
                entity_ids=source_ids,
                counts=counts,
                expected_kills=total_expected_kills,
                target_level=(sum(target_levels) / len(target_levels) if target_levels else None),
                spawn_count=spawn_count,
                minutes=total_minutes,
                confidence="low",  # Drop rates must be replaced by server evidence.
            )
        )

    if raw["event"]:
        count = max(1, len(raw["event"]))
        estimates.append(
            ObjectiveEstimate(
                kind="event_or_use",
                entity_ids=[],
                counts=[count],
                expected_kills=0.0,
                target_level=None,
                spawn_count=0,
                minutes=count * EVENT_OBJECTIVE_MINUTES,
                confidence="low",
            )
        )

    objective_minutes = sum(item.minutes for item in estimates)
    base_xp = int((data.quest_xp.get(quest_id) or {}).get(2) or 0)
    actual_xp = int(round(base_xp * QUEST_XP_MULTIPLIER))
    xp_rate = actual_xp / objective_minutes if objective_minutes > 0 and actual_xp else None
    confidence = "low" if any(item.confidence == "low" for item in estimates) else "medium"
    if not estimates:
        confidence = "high"  # Pure hand-in/travel quest; route cost is handled separately.
    return QuestEstimate(
        quest_id=quest_id,
        name=name,
        required_level=int(quest.get("required_level") or 0),
        quest_level=int(quest.get("quest_level") or 0),
        base_xp=base_xp,
        actual_xp=actual_xp,
        objective_text=objective_text,
        objective_types=[item.kind for item in estimates] or ["travel_or_turnin"],
        objective_minutes=round(objective_minutes, 2),
        xp_per_objective_minute=(round(xp_rate, 1) if xp_rate is not None else None),
        confidence=confidence,
        objectives=estimates,
    )


def _step_anchor(step: dict[str, Any]) -> tuple[float, float] | None:
    anchor = step.get("anchor_details") or {}
    representative = anchor.get("representative")
    if not isinstance(representative, dict):
        return None
    x = representative.get("x")
    y = representative.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def _travel_minutes(
    origin: tuple[float, float] | None,
    destination: tuple[float, float] | None,
    zone_id: int,
    player_level: int,
) -> float:
    if origin is None or destination is None:
        return 0.0
    dx = (destination[0] - origin[0]) / 100.0
    dy = (destination[1] - origin[1]) / 100.0
    normalized = math.hypot(dx, dy)
    diagonal = ZONE_DIAGONAL_MINUTES_AT_100.get(zone_id, 9.0)
    mount_multiplier = 1.25 if player_level < 40 else 1.0
    return normalized * diagonal * mount_multiplier


def estimate_zone(
    root: Path,
    data: QuestieData,
    zone_id: int,
    player_level: int,
    required_level_cap: int,
) -> dict[str, Any]:
    slug = ZONE_SLUGS[zone_id]
    route_path = root / "data" / "routes" / "world-candidate" / slug / "route.json"
    route = json.loads(route_path.read_text(encoding="utf-8"))
    selected_catalog = {
        int(quest["quest_id"]): quest
        for quest in route["quest_catalog"]
        if int(quest.get("required_level") or 0) <= required_level_cap
    }
    estimates = {
        quest_id: estimate_quest(data, quest, zone_id, player_level)
        for quest_id, quest in selected_catalog.items()
    }

    selected_ids = set(estimates)
    travel_minutes = 0.0
    interaction_minutes = 0.0
    objective_minutes = 0.0
    previous_anchor: tuple[float, float] | None = None
    objective_counted: set[int] = set()
    selected_step_count = 0

    for step in route["steps"]:
        quest_ids = [int(value) for value in step.get("quest_ids", []) if int(value) in selected_ids]
        if not quest_ids:
            continue
        selected_step_count += 1
        anchor = _step_anchor(step)
        travel_minutes += _travel_minutes(previous_anchor, anchor, zone_id, player_level)
        if anchor is not None:
            previous_anchor = anchor
        action = step.get("action")
        if action in {"接取", "交付"}:
            interaction_minutes += (
                ACCEPT_TURNIN_BASE_MINUTES
                + ACCEPT_TURNIN_PER_QUEST_MINUTES * len(quest_ids)
            )
        elif action == "完成目标":
            for quest_id in quest_ids:
                if quest_id not in objective_counted:
                    objective_minutes += estimates[quest_id].objective_minutes
                    objective_counted.add(quest_id)

    actual_xp = sum(item.actual_xp for item in estimates.values())
    base_xp = sum(item.base_xp for item in estimates.values())
    total_minutes = travel_minutes + interaction_minutes + objective_minutes
    return {
        "zone_id": zone_id,
        "zone": route["zone"],
        "player_level_assumption": player_level,
        "required_level_cap": required_level_cap,
        "quest_count": len(estimates),
        "selected_step_count": selected_step_count,
        "base_quest_xp": base_xp,
        "actual_quest_xp": actual_xp,
        "travel_minutes": round(travel_minutes, 1),
        "interaction_minutes": round(interaction_minutes, 1),
        "objective_minutes": round(objective_minutes, 1),
        "total_minutes_point_estimate": round(total_minutes, 1),
        "total_minutes_range": [round(total_minutes * 0.75), round(total_minutes * 1.45)],
        "quest_xp_per_minute": round(actual_xp / total_minutes, 1) if total_minutes > 0 else None,
        "quests": [asdict(item) for item in estimates.values()],
        "limitations": [
            "Questie does not contain server drop percentages; personal-loot tasks use conservative defaults.",
            "Travel uses normalized map coordinates and a configurable zone-crossing calibration.",
            "Dungeon, mutually exclusive and unmet external-prerequisite tasks still require manual exclusion.",
            "Kill XP is deliberately excluded; route guarantees therefore remain conservative.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a quantified five-box 35-55 quest cost model")
    parser.add_argument("--questie", default="_sandbox/sources/Questie-v11.32.3.zip")
    parser.add_argument("--output", default="data/routes/horde/blood-elf/35-55-cost-model.json")
    parser.add_argument("--current-level", type=int, default=35)
    parser.add_argument("--current-xp", type=int, default=425)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    data = load_questie(root / args.questie)
    zone_plan = [
        (357, 38, 45),
        (440, 42, 48),
        (47, 46, 48),
        (51, 48, 48),
        (490, 49, 52),
        (361, 51, 55),
        (28, 51, 55),
        (139, 52, 55),
        (618, 52, 55),
    ]
    zones = [
        estimate_zone(root, data, zone_id, player_level, cap)
        for zone_id, player_level, cap in zone_plan
    ]
    payload = {
        "schema_version": 1,
        "questie_version": data.version,
        "quest_xp_multiplier": QUEST_XP_MULTIPLIER,
        "current": {
            "level": args.current_level,
            "xp": args.current_xp,
            "xp_to_55": xp_remaining(args.current_level, args.current_xp, 55),
        },
        "mandatory_sections_recovered_from_context": [
            "菲拉斯",
            "加基森/塔纳利斯",
        ],
        "zones": zones,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output.relative_to(root)),
        "xp_to_55": payload["current"]["xp_to_55"],
        "zones": [
            {
                "zone": zone["zone"],
                "quests": zone["quest_count"],
                "xp": zone["actual_quest_xp"],
                "minutes": zone["total_minutes_point_estimate"],
                "xp_per_minute": zone["quest_xp_per_minute"],
            }
            for zone in zones
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
