from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_lua import seq
from lib.questie_source import load_questie
from scripts.estimate_route_atlas_timing import estimate_foundation_task_service_audit

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
ROUTES_FILE = ROOT / "data" / "route-atlas" / "workbench-routes.json"

# Questie's WotLK item DB does not store rewards on the quest row, but item row field 6
# (`questRewards`) is a reverse index from reward item -> rewarding quest IDs.
# WoW item classes used here as "equippable reward" for the leveling/gold screen:
# 1 container, 2 weapon, 4 armor, 11 quiver.
EQUIPPABLE_ITEM_CLASSES = {1, 2, 4, 11}

BOREAN_FOUNDATION = ROOT / "data" / "route-atlas" / "borean-tundra-task-foundation.json"
BOREAN_TASK_CARD_UNIVERSE = ROOT / "data" / "route-atlas" / "borean-tundra-task-card-universe.json"
DRAGONBLIGHT_FOUNDATION = ROOT / "data" / "route-atlas" / "dragonblight-task-foundation.json"
BOREAN_OUTPUT = ROOT / "data" / "route-atlas" / "borean-tundra-reward-audit.json"
BOREAN_COLLECTION_OUTPUT = ROOT / "data" / "route-atlas" / "borean-tundra-collection-screen.json"
BOREAN_CHAIN_OUTPUT = ROOT / "data" / "route-atlas" / "borean-tundra-chain-screen.json"
BOREAN_PRIORITY_OUTPUT = ROOT / "data" / "route-atlas" / "borean-tundra-removal-priority-screen.json"
BOREAN_TIMING_OUTPUT = ROOT / "data" / "route-atlas" / "borean-tundra-task-timing-screen.json"
BOREAN_ATTRIBUTE_LOCKS = ROOT / "data" / "route-atlas" / "borean-tundra-task-attribute-locks.json"
BOREAN_DECISION_LOCKS = ROOT / "data" / "route-atlas" / "borean-tundra-removal-decision-locks.json"
FIVEBOX_OBS = ROOT / "data" / "observations" / "fivebox-task-types.json"

# Third-pass chain scope is deliberately route-horizon dependent. Borean is the current
# map and Dragonblight is the next confirmed map. No currently known Borean follow-up
# points directly outside these two zones, so this scope does not discard a known branch.
BOREAN_CHAIN_SCOPE_ZONES = {3537: "北风苔原", 65: "龙骨荒野"}

# Same-name variants are resolved to the exact Horde / one-time variant used by the
# current formal Borean route. These are route identity facts only; this script never
# edits route order or task selection.
BOREAN_VARIANT_RESOLUTION = {
    "地狱咆哮的堡垒": 11585,
    "战歌要塞的防御": 11596,
    "侦查虫孔": 11684,
    "猎龙": 11919,  # 11940 is repeatable/daily and is not the formal route task.
    "国王姆嘎姆嘎": 11702,
}

# Direct money means money paid at the character's current leveling level.
# Level-80 XP-to-money compensation is explicitly NOT counted here.
# This first-pass money audit is only required for tasks that Questie proves have no
# equippable reward; tasks with equipment already fail the "no equipment + no money"
# screen and do not need money lookup in this phase.
#
# Sources were cross-checked on 2026-08-17 against WotLK/3.3.5a quest databases and
# WotLK Classic quest-list Money columns. The source families are recorded in output;
# this file intentionally stores only the classification needed for the basic screen.
BOREAN_NO_EQUIPMENT_NO_DIRECT_MONEY = {
    11562, 11565, 11585, 11591, 11596, 11598,
    11606, 11614, 11615, 11618, 11620, 11624, 11625, 11629, 11634, 11636,
    11642, 11643, 11644, 11646, 11651, 11655, 11660, 11662, 11674, 11676,
    11678, 11679, 11686, 11688,
    11702, 11703, 11709, 11711, 11716, 11717, 11719, 11720, 11721, 11724,
    11864, 11865, 11869, 11870, 11871, 11876, 11878, 11888,
    11929, 11930, 11950,
    12471, 12486,
}

BOREAN_NO_EQUIPMENT_WITH_DIRECT_MONEY = {
    11559, 11561, 11563, 11564, 11569, 11571, 11574, 11576, 11582, 11587,
    11590, 11593, 11594,
    11605, 11607, 11609, 11612, 11616, 11617, 11627, 11628, 11630, 11633,
    11635, 11637, 11640, 11641, 11648, 11649, 11654, 11659, 11663, 11671,
    11675, 11680, 11682, 11684, 11685, 11687, 11695,
    11733,
    11866, 11881, 11887, 11890, 11893, 11895, 11896, 11899,
    11900, 11910, 11912, 11918, 11931, 11936, 11941, 11943, 11946, 11951,
    11961, 11967,
}

TRUSTED_MULTI_ITEM_MECHANICS = {
    "multiple_creature_task_item_drops": "drop",
    "task_item_world_object_pickup": "pickup",
    "mixed_object_item_pickup": "pickup",
}
TRUSTED_COUNT_CONFIDENCE = {"exact", "exact_text_order"}

# Questie cannot resolve every WotLK item source/count. These overrides come from
# WotLK Classic task-page checks or explicit user field confirmation. They only resolve
# collection facts; they do not imply keep/skip decisions.
BOREAN_COLLECTION_OVERRIDES = {
    11606: {"include": True, "trusted_item_units": 15, "source_modes": ["pickup"], "pattern": "repeated_same_item", "source": "user_field_confirmation_2026-08-18"},
    11906: {"include": True, "trusted_item_units": 15, "source_modes": ["pickup"], "pattern": "repeated_same_item", "source": "user_field_confirmation_2026-08-18"},
    11887: {"include": True, "trusted_item_units": 7, "source_modes": ["pickup"], "pattern": "repeated_same_item", "source": "wowhead_wotlk_11887"},
    11894: {"include": True, "trusted_item_units": 5, "source_modes": ["drop"], "pattern": "repeated_same_item", "source": "wowhead_wotlk_11894"},
    11695: {"include": True, "trusted_item_units": 2, "source_modes": ["pickup"], "pattern": "multiple_distinct_one_each", "source": "wowhead_wotlk_11695"},
    11609: {"include": True, "trusted_item_units": 6, "source_modes": ["pickup"], "pattern": "repeated_same_item", "source": "wowhead_wotlk_11609_ground_objects"},
    11912: {"include": True, "trusted_item_units": 10, "source_modes": ["pickup"], "pattern": "repeated_same_item", "source": "wowhead_wotlk_11912_frostberry_bushes"},
    11559: {"include": False, "reason": "mixed_ground_pickup_or_creature_drop_user_confirmed", "source": "user_field_confirmation_2026-08-18"},
    11640: {"include": True, "trusted_item_units": 3, "source_modes": ["drop"], "pattern": "multiple_distinct_one_each", "source": "wowhead_wotlk_11640"},
    11943: {"include": True, "trusted_item_units": 2, "source_modes": ["drop"], "pattern": "multiple_distinct_one_each", "source": "wowhead_wotlk_11943"},
    11931: {"include": True, "trusted_item_units": 4, "source_modes": ["drop"], "pattern": "repeated_plus_distinct", "source": "wowhead_wotlk_11931"},
    11909: {"include": False, "reason": "single_head_plus_single_manual_interaction", "source": "wowhead_wotlk_11909"},
    11637: {"include": False, "reason": "single_fetish_plus_single_use", "source": "wowhead_wotlk_11637"},
}


def classify_multi_item_collection(task: dict[str, Any]) -> dict[str, Any]:
    """Classify only real multi-item drop/pickup objectives.

    This deliberately excludes direct object interactions, spells/events, single-item
    named drops and single supplied items. Unknown counts/sources are review-only and
    never receive the positive multi-item tag.
    """
    item_objectives = [
        objective for objective in task.get("objectives", [])
        if objective.get("objective_type") == "item"
    ]
    details: list[dict[str, Any]] = []
    trusted_units = 0
    source_modes: set[str] = set()
    review_reasons: list[str] = []

    for objective in item_objectives:
        count = objective.get("required_count")
        mechanic = str(objective.get("mechanic") or "")
        confidence = str(objective.get("count_confidence") or "")
        source_mode = TRUSTED_MULTI_ITEM_MECHANICS.get(mechanic)
        detail = {
            "item_id": objective.get("item_id"),
            "item_name": objective.get("item_name"),
            "required_count": count,
            "mechanic": mechanic,
            "count_confidence": confidence,
            "source_mode": source_mode,
        }
        details.append(detail)

        if not isinstance(count, int) or count <= 0:
            if source_mode or mechanic == "item_source_not_in_questie":
                review_reasons.append(f"unknown_or_invalid_count:{objective.get('item_id')}")
            continue
        if confidence not in TRUSTED_COUNT_CONFIDENCE and count > 1:
            review_reasons.append(f"untrusted_count:{objective.get('item_id')}:{confidence}")
            continue
        if source_mode:
            trusted_units += count
            source_modes.add(source_mode)
        elif count > 1:
            review_reasons.append(f"untrusted_item_source:{objective.get('item_id')}:{mechanic}")

    # A task qualifies when at least two actual item units must be acquired from trusted
    # creature-drop/world-pickup sources. This covers both repeated same-item collection
    # and multiple distinct one-off item objectives, while still excluding a single click.
    qid = int(task["quest_id"])
    override = BOREAN_COLLECTION_OVERRIDES.get(qid)
    override_source = None
    override_reason = None
    pattern = None
    if override:
        override_source = override.get("source")
        if override.get("include"):
            trusted_units = int(override["trusted_item_units"])
            source_modes = set(override["source_modes"])
            pattern = str(override["pattern"])
            review_reasons = []
        else:
            trusted_units = 0
            source_modes = set()
            review_reasons = []
            override_reason = str(override.get("reason") or "manual_exclusion")
    else:
        known_counts = [
            detail["required_count"] for detail in details
            if isinstance(detail.get("required_count"), int) and detail["required_count"] > 0
        ]
        if any(count > 1 for count in known_counts):
            pattern = "repeated_same_item" if len(details) == 1 else "repeated_plus_distinct"
        elif len(known_counts) >= 2 and all(count == 1 for count in known_counts):
            pattern = "multiple_distinct_one_each"

    is_multi_item = trusted_units >= 2
    tags: list[str] = []
    if is_multi_item:
        tags.append("objective:multi_item_drop_or_pickup")
        if source_modes == {"drop"}:
            tags.append("objective:multi_item_drop")
        elif source_modes == {"pickup"}:
            tags.append("objective:multi_item_pickup")
        elif source_modes:
            tags.append("objective:multi_item_mixed_sources")
        if pattern == "multiple_distinct_one_each":
            tags.append("objective:multi_distinct_one_each")
        elif pattern == "repeated_plus_distinct":
            tags.append("objective:multi_repeated_plus_distinct")
        else:
            tags.append("objective:multi_repeated_item_collection")

    return {
        "is_multi_item_drop_or_pickup": is_multi_item,
        "trusted_item_units": trusted_units,
        "source_modes": sorted(source_modes),
        "collection_pattern": pattern,
        "objective_details": details,
        "review_reasons": sorted(set(review_reasons)),
        "manual_override_source": override_source,
        "manual_exclusion_reason": override_reason,
        "tags": tags,
    }


def _task_in_chain_scope(task: dict[str, Any]) -> bool:
    if task.get("is_daily_weekly_monthly_or_repeatable"):
        return False
    if task.get("is_dungeon") or task.get("is_raid_flagged"):
        return False
    status = str(task.get("scope_status") or "")
    if not (status.startswith("include_") or status == "defer_future_level_revisit"):
        return False
    zones = set(task.get("all_route_zones") or []) | set(task.get("start_zones") or []) | set(task.get("turnin_zones") or [])
    return not zones or bool(zones & set(BOREAN_CHAIN_SCOPE_ZONES))


def _build_chain_graph(borean_tasks: list[dict[str, Any]], dragonblight_tasks: list[dict[str, Any]]) -> tuple[dict[int, dict[int, dict[str, Any]]], dict[int, dict[str, Any]]]:
    universe: dict[int, dict[str, Any]] = {}
    for task in borean_tasks + dragonblight_tasks:
        qid = int(task["quest_id"])
        current = universe.get(qid)
        if current is None or (not _task_in_chain_scope(current) and _task_in_chain_scope(task)):
            universe[qid] = task

    edges: dict[int, dict[int, dict[str, Any]]] = {qid: {} for qid in universe}

    def add_edge(source: int, target: int, relation: str, dependency_kind: str | None) -> None:
        if source == target or source not in universe or target not in universe:
            return
        target_task = universe[target]
        if not _task_in_chain_scope(target_task):
            return
        edge = edges.setdefault(source, {}).setdefault(
            target,
            {"relations": set(), "dependency_kinds": set()},
        )
        edge["relations"].add(relation)
        if dependency_kind:
            edge["dependency_kinds"].add(dependency_kind)

    # Forward Questie relationship hints.
    for qid, task in universe.items():
        next_quest = task.get("next_quest")
        if isinstance(next_quest, int):
            add_edge(qid, next_quest, "next_quest", None)
        for child in task.get("child_quests") or []:
            if isinstance(child, int):
                add_edge(qid, child, "child_quest", None)
        breadcrumb_for = task.get("breadcrumb_for")
        if isinstance(breadcrumb_for, int):
            add_edge(qid, breadcrumb_for, "breadcrumb_for", None)
        for breadcrumb in task.get("breadcrumbs") or []:
            if isinstance(breadcrumb, int):
                add_edge(qid, breadcrumb, "breadcrumb", None)

    # Reverse prerequisites are stronger evidence because the downstream quest explicitly
    # names the current quest as an availability dependency.
    for target, task in universe.items():
        for source in task.get("pre_all") or []:
            if isinstance(source, int):
                add_edge(source, target, "pre_all", "mandatory")
        for source in task.get("parent_active") or []:
            if isinstance(source, int):
                add_edge(source, target, "parent_active", "mandatory")
        for source in task.get("available_starting_with") or []:
            if isinstance(source, int):
                add_edge(source, target, "available_starting_with", "mandatory")
        for source in task.get("pre_any") or []:
            if isinstance(source, int):
                add_edge(source, target, "pre_any", "alternative")

    return edges, universe


def classify_in_scope_followup(task: dict[str, Any], edges: dict[int, dict[int, dict[str, Any]]], universe: dict[int, dict[str, Any]]) -> dict[str, Any]:
    qid = int(task["quest_id"])
    followups: list[dict[str, Any]] = []
    has_mandatory = False
    has_alternative = False
    has_dependency_confirmed = False

    for target_id, edge in sorted(edges.get(qid, {}).items()):
        target = universe[target_id]
        zones = sorted(
            (set(target.get("all_route_zones") or []) | set(target.get("start_zones") or []) | set(target.get("turnin_zones") or []))
            & set(BOREAN_CHAIN_SCOPE_ZONES)
        )
        dependency_kinds = sorted(edge["dependency_kinds"])
        has_mandatory = has_mandatory or "mandatory" in dependency_kinds
        has_alternative = has_alternative or "alternative" in dependency_kinds
        has_dependency_confirmed = has_dependency_confirmed or bool(dependency_kinds)
        followups.append(
            {
                "quest_id": target_id,
                "name": target["name"],
                "zones": [{"zone_id": zone, "name": BOREAN_CHAIN_SCOPE_ZONES[zone]} for zone in zones],
                "relations": sorted(edge["relations"]),
                "dependency_kinds": dependency_kinds,
            }
        )

    has_followup = bool(followups)
    tags: list[str] = []
    if has_followup:
        tags.append("chain:has_in_scope_followup")
        if has_dependency_confirmed:
            tags.append("chain:dependency_confirmed_followup")
        else:
            tags.append("chain:explicit_followup_only")
        if has_mandatory:
            tags.append("chain:mandatory_dependency_followup")
        if has_alternative:
            tags.append("chain:alternative_dependency_followup")
    else:
        tags.append("chain:terminal_in_scope")

    return {
        "scope_zone_ids": sorted(BOREAN_CHAIN_SCOPE_ZONES),
        "has_in_scope_followup": has_followup,
        "has_dependency_confirmed_followup": has_dependency_confirmed,
        "has_mandatory_dependency_followup": has_mandatory,
        "has_alternative_dependency_followup": has_alternative,
        "direct_followup_count": len(followups),
        "direct_followups": followups,
        "tags": tags,
    }


def _route_quest_names(route: dict[str, Any]) -> list[str]:
    names: list[str] = []

    def add_from_text(text: Any) -> None:
        for name in re.findall(r"《([^》]+)》", str(text or "")):
            if name not in names:
                names.append(name)

    for point in route.get("points", []):
        if len(point) >= 4:
            add_from_text(point[3])
    for group in route.get("stepGroups", []):
        for key in ("title", "summary", "note", "fivebox_check"):
            add_from_text(group.get(key))
    return names


def _first_logical_step_by_name(route: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    points = route.get("points", [])
    for step_no, group in enumerate(route.get("stepGroups", []), 1):
        start = int(group.get("start", 0))
        end = int(group.get("end", start))
        texts = [group.get("title", ""), group.get("summary", ""), group.get("note", ""), group.get("fivebox_check", "")]
        for point_index in range(max(0, start), min(len(points) - 1, end) + 1):
            point = points[point_index]
            if len(point) >= 4:
                texts.append(point[3])
        for text in texts:
            for name in re.findall(r"《([^》]+)》", str(text or "")):
                result.setdefault(name, step_no)
    return result


def build_borean() -> dict[str, Any]:
    routes = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
    route = routes["borean"]
    foundation = json.loads(BOREAN_FOUNDATION.read_text(encoding="utf-8"))
    tasks = foundation["tasks"]
    by_id = {int(task["quest_id"]): task for task in tasks}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        by_name.setdefault(task["name"], []).append(task)

    route_names = _route_quest_names(route)
    first_step = _first_logical_step_by_name(route)
    ignored_bracket_tokens = [name for name in route_names if name not in by_name and name not in BOREAN_VARIANT_RESOLUTION]

    universe = json.loads(BOREAN_TASK_CARD_UNIVERSE.read_text(encoding="utf-8"))
    universe_ids = [int(qid) for qid in universe.get("quest_ids", [])]
    if len(universe_ids) != len(set(universe_ids)):
        raise RuntimeError("Borean task-card universe contains duplicate quest IDs")
    missing_universe_ids = [qid for qid in universe_ids if qid not in by_id]
    if missing_universe_ids:
        raise RuntimeError(f"Borean task-card universe references missing foundation quests: {missing_universe_ids}")

    # Task cards are frozen independently from the current route. Route optimization may
    # stop selecting a quest, but that must never delete or mutate the quest's base card.
    unique_resolved = [by_id[qid] for qid in universe_ids]

    dragonblight_foundation = json.loads(DRAGONBLIGHT_FOUNDATION.read_text(encoding="utf-8"))
    chain_edges, chain_universe = _build_chain_graph(tasks, dragonblight_foundation["tasks"])
    observations = json.loads(FIVEBOX_OBS.read_text(encoding="utf-8"))

    questie = load_questie(QUESTIE_ZIP)
    reward_items: dict[int, list[dict[str, Any]]] = {int(task["quest_id"]): [] for task in unique_resolved}
    for item_id, row in questie.items.items():
        for qid in seq(row.get(6)):
            if qid not in reward_items:
                continue
            reward_items[qid].append(
                {
                    "item_id": int(item_id),
                    "name": row.get(1),
                    "item_class": row.get(12),
                    "item_subclass": row.get(13),
                    "item_level": row.get(9),
                    "required_level": row.get(10),
                }
            )

    rows: list[dict[str, Any]] = []
    no_equipment_ids: set[int] = set()
    equipment_count = 0
    no_equipment_direct_money = 0
    no_equipment_no_direct_money = 0
    multi_item_count = 0
    multi_item_drop_count = 0
    multi_item_pickup_count = 0
    multi_item_mixed_count = 0
    collection_review_count = 0
    chain_followup_count = 0
    chain_terminal_count = 0
    chain_dependency_confirmed_count = 0
    chain_explicit_only_count = 0
    timing_estimated_count = 0
    timing_unknown_count = 0

    for task in unique_resolved:
        qid = int(task["quest_id"])
        items = reward_items[qid]
        equipment = [item for item in items if item.get("item_class") in EQUIPPABLE_ITEM_CLASSES]
        has_equipment = bool(equipment)
        tags: list[str] = []

        if has_equipment:
            equipment_count += 1
            tags.append("reward:equipment")
            direct_money_status = "not_required_for_basic_filter"
            has_direct_money: bool | None = None
        else:
            no_equipment_ids.add(qid)
            tags.append("reward:no_equipment")
            if qid in BOREAN_NO_EQUIPMENT_WITH_DIRECT_MONEY:
                has_direct_money = True
                direct_money_status = "verified_present"
                no_equipment_direct_money += 1
                tags.append("reward:direct_money")
            elif qid in BOREAN_NO_EQUIPMENT_NO_DIRECT_MONEY:
                has_direct_money = False
                direct_money_status = "verified_absent_at_leveling_level"
                no_equipment_no_direct_money += 1
                tags.extend(["reward:no_direct_money", "reward:no_equipment_or_direct_money"])
            else:
                has_direct_money = None
                direct_money_status = "pending"
                tags.append("reward:money_pending")

        collection = classify_multi_item_collection(task)
        tags.extend(collection["tags"])
        if collection["is_multi_item_drop_or_pickup"]:
            multi_item_count += 1
            if "objective:multi_item_drop" in collection["tags"]:
                multi_item_drop_count += 1
            elif "objective:multi_item_pickup" in collection["tags"]:
                multi_item_pickup_count += 1
            elif "objective:multi_item_mixed_sources" in collection["tags"]:
                multi_item_mixed_count += 1
        if collection["review_reasons"]:
            collection_review_count += 1
            tags.append("objective:collection_review")

        chain = classify_in_scope_followup(task, chain_edges, chain_universe)
        tags.extend(chain["tags"])
        if chain["has_in_scope_followup"]:
            chain_followup_count += 1
            if chain["has_dependency_confirmed_followup"]:
                chain_dependency_confirmed_count += 1
            else:
                chain_explicit_only_count += 1
        else:
            chain_terminal_count += 1

        timing = estimate_foundation_task_service_audit(task, observations)
        if timing["status"] == "estimated":
            timing_estimated_count += 1
            timing["minutes"] = round(float(timing["minutes"]), 2)
            tags.append("timing:estimated")
        else:
            timing_unknown_count += 1
            tags.append("timing:unknown")
        timing["scope"] = "intrinsic_task_service_only_excludes_route_movement_and_hub_handling"

        rows.append(
            {
                "quest_id": qid,
                "name": task["name"],
                "english_name": task.get("english_name"),
                "first_route_step": first_step.get(task["name"]),
                "has_equipment_reward": has_equipment,
                "equipment_rewards": equipment,
                "other_reward_items": [item for item in items if item not in equipment],
                "direct_money_status": direct_money_status,
                "has_direct_money": has_direct_money,
                "max_level_bonus_money": task.get("xp", {}).get("max_level_bonus_money"),
                "collection_screen": collection,
                "chain_screen": chain,
                "timing_screen": timing,
                "tags": tags,
            }
        )

    classified_money = BOREAN_NO_EQUIPMENT_NO_DIRECT_MONEY | BOREAN_NO_EQUIPMENT_WITH_DIRECT_MONEY
    missing_money = sorted(no_equipment_ids - classified_money)
    extra_money = sorted(classified_money - no_equipment_ids)
    overlap = sorted(BOREAN_NO_EQUIPMENT_NO_DIRECT_MONEY & BOREAN_NO_EQUIPMENT_WITH_DIRECT_MONEY)
    if missing_money or extra_money or overlap:
        raise RuntimeError(
            f"Money audit coverage mismatch: missing={missing_money} extra={extra_money} overlap={overlap}"
        )

    if len(unique_resolved) != 163:
        raise RuntimeError(f"Expected 163 locked Borean task-card quests, got {len(unique_resolved)}")
    if equipment_count != 49 or len(no_equipment_ids) != 114:
        raise RuntimeError(
            f"Questie reward split changed: equipment={equipment_count}, no_equipment={len(no_equipment_ids)}"
        )
    if no_equipment_direct_money != 61 or no_equipment_no_direct_money != 53:
        raise RuntimeError(
            "Money split changed: "
            f"direct={no_equipment_direct_money}, none={no_equipment_no_direct_money}"
        )

    collection_candidates = [
        {
            "quest_id": row["quest_id"],
            "name": row["name"],
            "first_route_step": row["first_route_step"],
            "tags": [tag for tag in row["tags"] if tag.startswith("objective:multi_item")],
            "collection_screen": row["collection_screen"],
        }
        for row in rows
        if row["collection_screen"]["is_multi_item_drop_or_pickup"]
    ]
    collection_reviews = [
        {
            "quest_id": row["quest_id"],
            "name": row["name"],
            "first_route_step": row["first_route_step"],
            "collection_screen": row["collection_screen"],
        }
        for row in rows
        if row["collection_screen"]["review_reasons"]
    ]
    world_object_collection_reviews = [
        {
            "quest_id": int(task["quest_id"]),
            "name": task["name"],
            "first_route_step": first_step.get(task["name"]),
            "task_class": task.get("task_class"),
            "task_flags": task.get("task_flags") or [],
            "objective_text_zh": task.get("objective_text_zh"),
            "objectives": [
                objective for objective in task.get("objectives", [])
                if objective.get("objective_type") == "object"
            ],
        }
        for task in unique_resolved
        if task.get("task_class") == "world_object_collection"
    ]

    rows_by_id = {int(row["quest_id"]): row for row in rows}
    priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    priority_pending: list[dict[str, Any]] = []
    priority_candidates: list[dict[str, Any]] = []

    for row in rows:
        collection = row["collection_screen"]
        pattern = collection.get("collection_pattern")
        eligible_pattern = pattern in {"repeated_same_item", "repeated_plus_distinct"}
        source_modes = set(collection.get("source_modes") or [])
        if not collection.get("is_multi_item_drop_or_pickup") or not eligible_pattern:
            continue

        if source_modes not in ({"drop"}, {"pickup"}):
            priority_pending.append({"quest_id": row["quest_id"], "name": row["name"], "reason": "mixed_or_unknown_source"})
            continue

        direct_has_value = bool(row["has_equipment_reward"] is True or row["has_direct_money"] is True)
        descendants_seen: set[int] = set()
        stack = [int(followup["quest_id"]) for followup in row["chain_screen"]["direct_followups"]]
        valuable_followups: list[dict[str, Any]] = []
        unresolved_descendants: set[int] = set()
        while stack:
            target_id = stack.pop()
            if target_id in descendants_seen:
                continue
            descendants_seen.add(target_id)
            target_row = rows_by_id.get(target_id)
            if target_row is None:
                unresolved_descendants.add(target_id)
                continue
            if target_row["has_equipment_reward"] is True or target_row["has_direct_money"] is True:
                valuable_followups.append(
                    {
                        "quest_id": target_id,
                        "name": target_row["name"],
                        "has_equipment_reward": target_row["has_equipment_reward"],
                        "has_direct_money": target_row["has_direct_money"],
                    }
                )
            stack.extend(int(followup["quest_id"]) for followup in target_row["chain_screen"]["direct_followups"])

        has_valuable_followup = bool(valuable_followups)
        # Unknown later-map descendants matter only if no known valuable descendant has
        # already satisfied the user's "at least one valuable follow-up" condition.
        if unresolved_descendants and not has_valuable_followup:
            priority_pending.append(
                {"quest_id": row["quest_id"], "name": row["name"], "reason": "unresolved_followup_reward_value"}
            )
            continue

        # Priority is additive by user rule: worst combination starts at P1. Replacing
        # drop with pickup, adding direct reward value, or adding valuable follow-up each
        # downgrades removal urgency by exactly one level.
        priority = 1
        if source_modes == {"pickup"}:
            priority += 1
        if direct_has_value:
            priority += 1
        if has_valuable_followup:
            priority += 1
        if priority not in priority_counts:
            raise RuntimeError(f"Unexpected removal priority {priority} for quest {row['quest_id']}")

        valuable_followup_count = len(valuable_followups)
        if valuable_followup_count == 0:
            within_priority_tier = "A"
        elif valuable_followup_count == 1:
            within_priority_tier = "B"
        else:
            within_priority_tier = "C"

        decision_tags = [f"removal:priority_{priority}", f"removal:subtier_{within_priority_tier}"]
        if has_valuable_followup:
            decision_tags.append("removal:potential_value_followup")
        if source_modes == {"pickup"}:
            decision_tags.append("removal:pickup_one_level_lower_than_drop")

        decision_screen = {
            "eligible": True,
            "priority": priority,
            "within_priority_tier": within_priority_tier,
            "priority_label": f"P{priority}{within_priority_tier}",
            "collection_source": next(iter(source_modes)),
            "collection_pattern": pattern,
            "direct_has_equipment_or_money_value": direct_has_value,
            "has_valuable_followup": has_valuable_followup,
            "valuable_followup_count": valuable_followup_count,
            "valuable_followup_bucket": "0" if valuable_followup_count == 0 else ("1" if valuable_followup_count == 1 else "2_plus"),
            "valuable_followups": valuable_followups,
            "unresolved_descendant_ids": sorted(unresolved_descendants),
            "task_timing": row["timing_screen"],
            "rule_components": {
                "base_multi_drop_priority": 1,
                "pickup_downgrade": 1 if source_modes == {"pickup"} else 0,
                "direct_reward_downgrade": 1 if direct_has_value else 0,
                "valuable_followup_downgrade": 1 if has_valuable_followup else 0,
                "within_priority_sort": "0 valuable followups > 1 valuable followup > 2+ valuable followups",
            },
            "tags": decision_tags,
        }
        priority_counts[priority] += 1
        priority_candidates.append(
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "first_route_step": row["first_route_step"],
                "priority": priority,
                "within_priority_tier": within_priority_tier,
                "priority_label": f"P{priority}{within_priority_tier}",
                "screen": decision_screen,
            }
        )

    if priority_pending:
        raise RuntimeError(f"Removal priority still has unresolved candidates: {priority_pending}")

    return {
        "schema_version": 1,
        "status": "locked_task_card_base_attributes_no_route_decisions",
        "route_key": "borean",
        "generated_from": {
            "route": str(ROUTES_FILE.relative_to(ROOT)),
            "foundation": str(BOREAN_FOUNDATION.relative_to(ROOT)),
            "questie": "../.ai-bridge/Questie.zip",
        },
        "source_notes": {
            "equipment": "Questie WotLK itemDB reverse index: item row field 6 questRewards; equipment classes 1/2/4/11.",
            "direct_money": "WotLK/3.3.5a quest databases and WotLK Classic quest-list Money column, audited 2026-08-17. Level-80 XP-to-money compensation is not direct leveling money.",
            "collection": "Uses the existing Borean foundation objective classification. Positive tags require real item objectives, trusted drop/pickup mechanics, at least two trusted item units, and trusted count confidence; direct object interactions and single-item objectives are excluded.",
            "chain": "Scope-aware follow-up facts combine forward Questie links and reverse prerequisite dependencies inside the confirmed Borean + Dragonblight route horizon.",
            "timing": "Task-intrinsic service estimates only; route movement and hub handling remain route-layer costs. Unsupported mechanisms are tagged unknown rather than receiving a fake generic fallback.",
            "scope": "This output is task-card/base-data only. Optimization decisions such as keep/skip/removal priority are intentionally excluded.",
        },
        "variant_resolution": BOREAN_VARIANT_RESOLUTION,
        "summary": {
            "task_card_universe_count": len(unique_resolved),
            "equipment_reward_count": equipment_count,
            "no_equipment_reward_count": len(no_equipment_ids),
            "no_equipment_with_direct_money_count": no_equipment_direct_money,
            "no_equipment_no_direct_money_count": no_equipment_no_direct_money,
            "money_pending_count": 0,
            "multi_item_drop_or_pickup_count": multi_item_count,
            "multi_item_drop_count": multi_item_drop_count,
            "multi_item_pickup_count": multi_item_pickup_count,
            "multi_item_mixed_sources_count": multi_item_mixed_count,
            "collection_review_count": collection_review_count,
            "chain_has_in_scope_followup_count": chain_followup_count,
            "chain_terminal_in_scope_count": chain_terminal_count,
            "chain_dependency_confirmed_followup_count": chain_dependency_confirmed_count,
            "chain_explicit_followup_only_count": chain_explicit_only_count,
            "timing_estimated_count": timing_estimated_count,
            "timing_unknown_count": timing_unknown_count,
            "removal_priority_1_count": priority_counts[1],
            "removal_priority_2_count": priority_counts[2],
            "removal_priority_3_count": priority_counts[3],
            "removal_priority_4_count": priority_counts[4],
            "removal_priority_pending_count": len(priority_pending),
        },
        "ignored_bracket_tokens": ignored_bracket_tokens,
        "collection_candidates": collection_candidates,
        "collection_reviews": collection_reviews,
        "world_object_collection_reviews": world_object_collection_reviews,
        "chain_tasks_with_followup": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "first_route_step": row["first_route_step"],
                "chain_screen": row["chain_screen"],
            }
            for row in rows
            if row["chain_screen"]["has_in_scope_followup"]
        ],
        "chain_terminal_tasks": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "first_route_step": row["first_route_step"],
            }
            for row in rows
            if not row["chain_screen"]["has_in_scope_followup"]
        ],
        "removal_priority_candidates": sorted(
            priority_candidates,
            key=lambda item: (item["priority"], item["first_route_step"] or 999, item["quest_id"]),
        ),
        "tasks": rows,
    }


def _attribute_lock_payload(payload: dict[str, Any]) -> dict[str, Any]:
    locked_tasks: list[dict[str, Any]] = []
    for row in payload["tasks"]:
        locked_tasks.append(
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "locked_tags": sorted(
                    tag for tag in row["tags"]
                    if tag.startswith(("reward:", "objective:", "chain:", "timing:"))
                ),
                "reward": {
                    "has_equipment_reward": row["has_equipment_reward"],
                    "has_direct_money": row["has_direct_money"],
                    "direct_money_status": row["direct_money_status"],
                    "max_level_bonus_money": row["max_level_bonus_money"],
                },
                "collection": {
                    "is_multi_item_drop_or_pickup": row["collection_screen"]["is_multi_item_drop_or_pickup"],
                    "trusted_item_units": row["collection_screen"]["trusted_item_units"],
                    "source_modes": row["collection_screen"]["source_modes"],
                    "collection_pattern": row["collection_screen"]["collection_pattern"],
                },
                "chain": {
                    "scope_zone_ids": row["chain_screen"]["scope_zone_ids"],
                    "has_in_scope_followup": row["chain_screen"]["has_in_scope_followup"],
                    "has_dependency_confirmed_followup": row["chain_screen"]["has_dependency_confirmed_followup"],
                    "direct_followup_ids": [item["quest_id"] for item in row["chain_screen"]["direct_followups"]],
                },
                "timing": {
                    "status": row["timing_screen"]["status"],
                    "minutes": row["timing_screen"]["minutes"],
                    "basis": row["timing_screen"]["basis"],
                    "scope": row["timing_screen"]["scope"],
                },
            }
        )
    return {
        "schema_version": 1,
        "status": "LOCKED_TASK_ATTRIBUTES",
        "lock_policy": "Do not modify a locked task attribute unless the underlying fact is confirmed wrong and the user explicitly approves the correction. Scripts must fail on drift instead of refreshing this file.",
        "route_key": "borean",
        "chain_scope": [
            {"zone_id": zone_id, "name": BOREAN_CHAIN_SCOPE_ZONES[zone_id]}
            for zone_id in sorted(BOREAN_CHAIN_SCOPE_ZONES)
        ],
        "tasks": locked_tasks,
    }


def _decision_lock_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "LOCKED_OPTIMIZATION_DECISIONS",
        "lock_policy": "Removal priority labels are derived optimization decisions, not task-card facts. Do not modify them unless the decision rule or an upstream locked fact is confirmed wrong and the user explicitly approves the correction.",
        "route_key": "borean",
        "rule": {
            "eligible_collection_patterns": ["repeated_same_item", "repeated_plus_distinct"],
            "excluded_collection_pattern": "multiple_distinct_one_each",
            "base_priority": "P1 = multi-item drop + no equipment/direct-money value + no valuable in-scope follow-up",
            "downgrade_one_level_each": [
                "pickup instead of drop",
                "current task has equipment or direct-money value",
                "at least one in-scope downstream task has equipment or direct-money value",
            ],
            "within_priority_tier": {
                "A": "0 valuable downstream tasks; highest removal urgency inside the same P level",
                "B": "exactly 1 valuable downstream task",
                "C": "2 or more valuable downstream tasks; lowest removal urgency inside the same P level",
            },
        },
        "candidates": [
            {
                "quest_id": item["quest_id"],
                "name": item["name"],
                "priority": item["priority"],
                "within_priority_tier": item["within_priority_tier"],
                "priority_label": item["priority_label"],
                "collection_source": item["screen"]["collection_source"],
                "direct_has_equipment_or_money_value": item["screen"]["direct_has_equipment_or_money_value"],
                "valuable_followup_count": item["screen"]["valuable_followup_count"],
                "valuable_followup_bucket": item["screen"]["valuable_followup_bucket"],
                "valuable_followup_ids": [row["quest_id"] for row in item["screen"]["valuable_followups"]],
            }
            for item in sorted(payload["removal_priority_candidates"], key=lambda row: row["quest_id"])
        ],
    }


def _verify_or_create_lock(path: Path, lock_payload: dict[str, Any], *, allow_approved_refresh: bool, label: str) -> str:
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != lock_payload:
            if not allow_approved_refresh:
                raise RuntimeError(
                    f"Locked Borean {label} drifted. Do not overwrite the lock file. "
                    "First identify the incorrect fact/rule, then obtain explicit user approval before correcting it."
                )
            path.write_text(json.dumps(lock_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return "refreshed_with_explicit_approval"
        return "verified"
    path.write_text(json.dumps(lock_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "created"


def _base_output_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip route/optimization decisions from the task-card/base-data output."""
    base_tasks = [
        {key: value for key, value in row.items() if key != "first_route_step"}
        for row in payload["tasks"]
    ]
    return {
        **{
            key: value
            for key, value in payload.items()
            if key not in {"summary", "removal_priority_candidates", "tasks"}
        },
        "summary": {
            key: value for key, value in payload["summary"].items()
            if not key.startswith("removal_priority_")
        },
        "tasks": base_tasks,
    }


def main() -> None:
    route_key = sys.argv[1] if len(sys.argv) > 1 else "borean"
    approved_lock_migration = "--approved-lock-migration" in sys.argv[2:]
    if route_key != "borean":
        raise SystemExit("Only borean is wired in this first reusable pass. Add the next map's foundation + money audit before use.")
    payload = build_borean()
    attribute_lock_state = _verify_or_create_lock(
        BOREAN_ATTRIBUTE_LOCKS,
        _attribute_lock_payload(payload),
        allow_approved_refresh=approved_lock_migration,
        label="task attributes",
    )
    decision_lock_state = _verify_or_create_lock(
        BOREAN_DECISION_LOCKS,
        _decision_lock_payload(payload),
        allow_approved_refresh=approved_lock_migration,
        label="optimization decisions",
    )

    base_payload = _base_output_payload(payload)
    BOREAN_OUTPUT.write_text(json.dumps(base_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    collection_payload = {
        "status": "second_pass_collection_screen_only_not_route_decision",
        "summary": {
            key: value for key, value in payload["summary"].items()
            if key.startswith("multi_item_") or key == "collection_review_count"
        },
        "candidates": payload["collection_candidates"],
        "reviews": payload["collection_reviews"],
        "world_object_collection_reviews": payload["world_object_collection_reviews"],
    }
    BOREAN_COLLECTION_OUTPUT.write_text(
        json.dumps(collection_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    chain_payload = {
        "status": "third_pass_chain_property_screen_locked_scope",
        "scope": [
            {"zone_id": zone_id, "name": BOREAN_CHAIN_SCOPE_ZONES[zone_id]}
            for zone_id in sorted(BOREAN_CHAIN_SCOPE_ZONES)
        ],
        "summary": {
            key: value for key, value in payload["summary"].items()
            if key.startswith("chain_")
        },
        "with_followup": payload["chain_tasks_with_followup"],
        "terminal_in_scope": payload["chain_terminal_tasks"],
    }
    BOREAN_CHAIN_OUTPUT.write_text(
        json.dumps(chain_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    priority_payload = {
        "status": "fourth_pass_locked_removal_priority_labels_not_task_card_data",
        "rule": {
            "eligible_collection_patterns": ["repeated_same_item", "repeated_plus_distinct"],
            "excluded_collection_pattern": "multiple_distinct_one_each",
            "base": "multi-item drop + no equipment/direct-money value + no valuable in-scope follow-up = P1",
            "downgrade_one_level_each": [
                "pickup instead of drop",
                "current task has equipment or direct-money value",
                "at least one in-scope downstream task has equipment or direct-money value",
            ],
            "within_priority_tier": {
                "A": "0 valuable downstream tasks; highest removal urgency inside same P",
                "B": "exactly 1 valuable downstream task",
                "C": "2 or more valuable downstream tasks; lowest removal urgency inside same P",
            },
        },
        "summary": {
            key: value for key, value in payload["summary"].items()
            if key.startswith("removal_priority_")
        },
        "candidates": sorted(
            payload["removal_priority_candidates"],
            key=lambda item: (item["priority"], item["within_priority_tier"], item["first_route_step"] or 999, item["quest_id"]),
        ),
    }
    BOREAN_PRIORITY_OUTPUT.write_text(
        json.dumps(priority_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    timing_payload = {
        "status": "fifth_pass_task_intrinsic_timing_facts_not_route_decisions",
        "scope": "Task-intrinsic service time only. Route movement, hub accept/turn-in handling, and route re-optimization effects are excluded and must be recalculated after any real route change.",
        "summary": {
            "task_card_universe_count": payload["summary"]["task_card_universe_count"],
            "timing_estimated_count": payload["summary"]["timing_estimated_count"],
            "timing_unknown_count": payload["summary"]["timing_unknown_count"],
        },
        "tasks": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "first_route_step": row["first_route_step"],
                "timing": row["timing_screen"],
            }
            for row in payload["tasks"]
        ],
        "unknown_tasks": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "first_route_step": row["first_route_step"],
                "basis": row["timing_screen"]["basis"],
            }
            for row in payload["tasks"]
            if row["timing_screen"]["status"] == "unknown"
        ],
    }
    BOREAN_TIMING_OUTPUT.write_text(
        json.dumps(timing_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print("attribute locks", attribute_lock_state, BOREAN_ATTRIBUTE_LOCKS.relative_to(ROOT))
    print("decision locks", decision_lock_state, BOREAN_DECISION_LOCKS.relative_to(ROOT))
    print("wrote", BOREAN_OUTPUT.relative_to(ROOT))
    print("wrote", BOREAN_COLLECTION_OUTPUT.relative_to(ROOT))
    print("wrote", BOREAN_CHAIN_OUTPUT.relative_to(ROOT))
    print("wrote", BOREAN_PRIORITY_OUTPUT.relative_to(ROOT))
    print("wrote", BOREAN_TIMING_OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
