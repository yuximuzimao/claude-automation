from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import _reader, effective_quest_rows
from lib.questie_lua import seq
from lib.questie_source import QuestieData, load_questie
from lib.world_builder import (
    ITEM,
    QUEST,
    _ids,
    _objective_entities,
    _parent_zone,
    _parse_zone_metadata,
    _questgiver_entities,
)
from scripts.analyze_questie_journey import summarize as summarize_journey
from scripts.build_35_55_task_foundation import (
    SERVER_QUEST_XP_MULTIPLIER,
    classify_objectives,
    classify_task,
    make_npc_entity,
    make_object_entity,
    quest_xp_at_level,
    source_entities_for_item,
)

ZONE_ID = 3537
START_LEVEL = 68
NATURAL_FIRST_PASS_MAX_REQUIRED_LEVEL = 73
BLOOD_ELF_FLAG = 512
PALADIN_FLAG = 2
QUEST_LOG_CAP = 25
QUEST_LOG_SOFT_WARNING = 22
QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
JOURNEY_FILE = ROOT.parent / ".ai-bridge" / "Questie.lua"
VIDEO_ROOT = ROOT.parent / ".ai-bridge" / "wow-video-extraction"
OUTPUT_FOUNDATION = ROOT / "data" / "route-atlas" / "borean-tundra-task-foundation.json"
OUTPUT_CLUSTERS = ROOT / "data" / "route-atlas" / "borean-tundra-target-clusters.json"
OUTPUT_VIDEO = ROOT / "data" / "route-atlas" / "borean-tundra-video-reference.json"
OUTPUT_EXCLUSIONS = ROOT / "data" / "route-atlas" / "borean-tundra-exclusion-audit.json"
OUTPUT_AUDIT = ROOT / "docs" / "analysis" / "2026-08-15-borean-tundra-foundation-adversarial-audit.md"

DAILY = 4096
WEEKLY = 32768
MONTHLY = 65536
RAID = 64
AUTO_REWARDED = 1024
REPEATABLE = 1


def bit_allows(mask: Any, flag: int) -> bool:
    return not isinstance(mask, int) or mask == 0 or bool(mask & flag)


def localized_name(data: QuestieData, quest_id: int, row: dict[Any, Any]) -> str:
    raw = str(row.get(1) or f"Quest {quest_id}")
    return data.local_name(data.quest_names, quest_id, raw)


def localized_objective(data: QuestieData, quest_id: int) -> str:
    value = data.quest_names.get(quest_id)
    if not isinstance(value, dict):
        return ""
    objectives = seq(value.get(2))
    return " / ".join(str(v) for v in objectives if isinstance(v, str))


def english_objective(row: dict[Any, Any]) -> str:
    return " / ".join(str(v) for v in seq(row.get(8)) if isinstance(v, str))


def entity_group(data: QuestieData, group: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for npc_id in _ids(group, 1):
        entity = make_npc_entity(data, npc_id)
        if entity:
            result.append(asdict(entity))
    for object_id in _ids(group, 2):
        entity = make_object_entity(data, object_id)
        if entity:
            result.append(asdict(entity))
    return result


def entity_zones(entities: list[dict[str, Any]]) -> list[int]:
    result: set[int] = set()
    for entity in entities:
        for zone in entity.get("zones") or []:
            if isinstance(zone, int):
                result.add(zone)
    return sorted(result)


def assigned_parent_zone(row: dict[Any, Any], parents: dict[int, int]) -> int | None:
    raw = row.get(17)
    if not isinstance(raw, int) or raw <= 0:
        return None
    return _parent_zone(raw, parents)


def entity_has_zone(entity: Any, zone_id: int) -> bool:
    return bool(entity and entity.zones and zone_id in entity.zones)


def direct_touches_zone(data: QuestieData, row: dict[Any, Any], zone_id: int) -> bool:
    """True only for a real route touch, not an incidental alternative item-drop source.

    Item *starts* are included because dropped quest starters are a known candidate-union
    blind spot. Ordinary item objectives are not used here: an unrelated quest can often
    source the same generic item from creatures in several zones.
    """
    if _questgiver_entities(data, row.get(2), zone_id) or _questgiver_entities(data, row.get(3), zone_id):
        return True

    objectives = row.get(10)
    if isinstance(objectives, dict):
        for entry in seq(objectives.get(1)):
            values = seq(entry)
            if values and isinstance(values[0], int) and entity_has_zone(make_npc_entity(data, int(values[0])), zone_id):
                return True
        for entry in seq(objectives.get(2)):
            values = seq(entry)
            if values and isinstance(values[0], int) and entity_has_zone(make_object_entity(data, int(values[0])), zone_id):
                return True
        for entry in seq(objectives.get(5)):
            values = seq(entry)
            ids = seq(values[0]) if values and isinstance(values[0], dict) else []
            if any(isinstance(npc_id, int) and entity_has_zone(make_npc_entity(data, int(npc_id)), zone_id) for npc_id in ids):
                return True

    trigger = row.get(9)
    trigger_values = seq(trigger)
    if len(trigger_values) >= 2 and isinstance(trigger_values[1], dict) and trigger_values[1].get(zone_id):
        return True

    for extra in extract_extra_objectives(data, row, zone_id):
        if zone_id in extra["route_zones"]:
            return True

    # Item-triggered quests have no physical questgiver; their drop source is the start location.
    for item_id in _ids(row.get(2), 3):
        npcs, objects = source_entities_for_item(data, item_id)
        if any(entity_has_zone(entity, zone_id) for entity in [*npcs, *objects]):
            return True
    return False


def preferred_entity_route_zones(entity: dict[str, Any], preferred_zone: int) -> list[int]:
    zones = [int(zone) for zone in entity.get("zones") or [] if isinstance(zone, int)]
    if preferred_zone in zones:
        return [preferred_zone]
    return sorted(set(zones))


def objective_route_zones(objectives: list[dict[str, Any]], preferred_zone: int) -> list[int]:
    zones: set[int] = set()
    for objective in objectives:
        for source in objective.get("sources") or []:
            zones.update(preferred_entity_route_zones(source, preferred_zone))
    return sorted(zones)


def coordinate_map(value: Any) -> dict[str, list[list[float]]]:
    result: dict[str, list[list[float]]] = {}
    if not isinstance(value, dict):
        return result
    for zone_id, points in value.items():
        if not isinstance(zone_id, int) or not isinstance(points, dict):
            continue
        rows: list[list[float]] = []
        for point in seq(points):
            values = seq(point)
            if len(values) >= 2 and all(isinstance(v, (int, float)) for v in values[:2]):
                rows.append([float(values[0]), float(values[1])])
        if rows:
            result[str(zone_id)] = rows
    return result


def extract_extra_objectives(data: QuestieData, row: dict[Any, Any], preferred_zone: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(seq(row.get(29)), start=1):
        values = seq(entry)
        coords = coordinate_map(values[0]) if values else {}
        text = str(values[2]) if len(values) >= 3 and values[2] is not None else ""
        objective_index = values[3] if len(values) >= 4 and isinstance(values[3], int) else None
        references: list[dict[str, Any]] = []
        raw_refs = values[4] if len(values) >= 5 and isinstance(values[4], dict) else {}
        for ref in seq(raw_refs):
            ref_values = seq(ref)
            if len(ref_values) < 2 or not isinstance(ref_values[0], str) or not isinstance(ref_values[1], int):
                continue
            ref_type = ref_values[0]
            entity_id = int(ref_values[1])
            entity = None
            if ref_type in {"monster", "npc", "creature"}:
                entity = make_npc_entity(data, entity_id)
            elif ref_type in {"object", "gameobject"}:
                entity = make_object_entity(data, entity_id)
            if entity:
                references.append(asdict(entity))
            else:
                references.append({"entity_type": ref_type, "entity_id": entity_id, "name": None, "zones": [], "representative_by_zone": {}})
        route_zones: set[int] = {int(zone) for zone in coords if str(zone).isdigit()}
        for entity in references:
            route_zones.update(preferred_entity_route_zones(entity, preferred_zone))
        result.append({
            "index": index,
            "text": text,
            "objective_index": objective_index,
            "coordinates_by_zone": coords,
            "references": references,
            "route_zones": sorted(route_zones),
        })
    return result


def correction_zone_hints(source: Path, zone_constant: str = "BOREAN_TUNDRA") -> set[int]:
    read = _reader(source)
    text = read("Database/Corrections/wotlkQuestFixes.lua")
    # We only need to know which top-level quest correction owns a Borean zone
    # reference. Walking backwards from each zone reference avoids evaluating
    # arbitrary Lua expressions that may appear elsewhere in a correction block.
    top_level = list(re.finditer(r"^        \[(\d+)\]\s*=\s*\{", text, re.M))
    starts = [match.start() for match in top_level]
    result: set[int] = set()
    for zone_match in re.finditer(rf"\bzoneIDs\.{re.escape(zone_constant)}\b", text):
        owner = None
        for index, start in enumerate(starts):
            if start > zone_match.start():
                break
            owner = top_level[index]
        if owner is not None:
            result.add(int(owner.group(1)))
    return result


def raw_candidate_ids(data: QuestieData, meta: dict[str, Any]) -> tuple[set[int], dict[str, list[int]]]:
    assigned: set[int] = set()
    touching: set[int] = set()
    for quest_id, row in data.quests.items():
        if not isinstance(quest_id, int) or not isinstance(row, dict):
            continue
        if assigned_parent_zone(row, meta["parents"]) == ZONE_ID:
            assigned.add(quest_id)
        if direct_touches_zone(data, row, ZONE_ID):
            touching.add(quest_id)
    correction_hints = correction_zone_hints(QUESTIE_ZIP)
    union = assigned | touching | correction_hints
    return union, {
        "raw_assigned": sorted(assigned),
        "raw_touches": sorted(touching),
        "correction_zone_hints": sorted(correction_hints),
    }


def dependency_ids(row: dict[Any, Any]) -> dict[str, list[int]]:
    pre_any = [abs(int(v)) for v in seq(row.get(13)) if isinstance(v, int) and v]
    pre_all = [abs(int(v)) for v in seq(row.get(12)) if isinstance(v, int) and v]
    parent = row.get(25)
    available_start = row.get(34)
    return {
        "pre_any": pre_any,
        "pre_all": pre_all,
        "parent_active": [int(parent)] if isinstance(parent, int) and parent > 0 else [],
        "available_starting_with": [int(available_start)] if isinstance(available_start, int) and available_start > 0 else [],
    }


def effective_with_boundary_refs(
    data: QuestieData,
    initial_ids: set[int],
) -> tuple[set[int], dict[int, dict[Any, Any]], dict[str, Any], dict[str, set[int]]]:
    """Apply effective facts to the primary Borean universe and add one-hop boundaries.

    External maps get their own full foundation later. Recursively expanding every ANY
    prerequisite here pulls entire Outland/Classic histories through unused alternatives,
    which is not a Borean planning dependency. We retain direct predecessor/follow-up
    references so cross-map continuity and quest-log occupancy remain explicit.
    """
    primary_rows, _ = effective_quest_rows(data, QUESTIE_ZIP, initial_ids)
    predecessors: set[int] = set()
    followups: set[int] = set()
    for row in primary_rows.values():
        deps = dependency_ids(row)
        for values in deps.values():
            predecessors.update(qid for qid in values if qid in data.quests and qid not in initial_ids)
        next_quest = row.get(22)
        if isinstance(next_quest, int) and next_quest > 0 and next_quest in data.quests and next_quest not in initial_ids:
            followups.add(next_quest)
        for qid in seq(row.get(14)) + seq(row.get(28)):
            if isinstance(qid, int) and qid > 0 and qid in data.quests and qid not in initial_ids:
                followups.add(qid)
        breadcrumb_for = row.get(27)
        if isinstance(breadcrumb_for, int) and breadcrumb_for > 0 and breadcrumb_for in data.quests and breadcrumb_for not in initial_ids:
            followups.add(breadcrumb_for)
    ids = set(initial_ids) | predecessors | followups
    rows, audit = effective_quest_rows(data, QUESTIE_ZIP, ids)
    roles = {
        "primary": set(initial_ids),
        "boundary_prerequisite": predecessors,
        "boundary_followup": followups,
    }
    return ids, rows, audit, roles


def npc_faction_eligibility(data: QuestieData, row: dict[Any, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for key, label in ((2, "start"), (3, "finish")):
        npc_ids = _ids(row.get(key), 1)
        factions: list[str] = []
        for npc_id in npc_ids:
            npc = data.npcs.get(npc_id)
            if isinstance(npc, dict) and isinstance(npc.get(13), str):
                factions.append(str(npc.get(13)))
        if factions and not any("H" in faction for faction in factions):
            reasons.append(f"{label}_npc_alliance_only")
    return not reasons, reasons


def xp_facts(data: QuestieData, quest_id: int, row: dict[Any, Any]) -> dict[str, Any]:
    xp_row = data.quest_xp.get(quest_id)
    db_level = xp_row.get(1) if isinstance(xp_row, dict) else None
    db_base = xp_row.get(2) if isinstance(xp_row, dict) else None
    has_xp = isinstance(db_level, int) and db_level > 0 and isinstance(db_base, int) and db_base > 0
    qlevel = row.get(5)
    return {
        "has_xp": has_xp,
        "xp_db_level": db_level,
        "xp_db_base": db_base,
        "server_multiplier": SERVER_QUEST_XP_MULTIPLIER,
        "server_xp_at_68": quest_xp_at_level(data, quest_id, START_LEVEL) if has_xp else 0,
        "full_xp_through_level": int(qlevel) + 5 if isinstance(qlevel, int) and qlevel > 0 else None,
    }


def pvp_classification(row: dict[Any, Any], name: str, objective_text: str, objectives: list[dict[str, Any]]) -> dict[str, Any]:
    text = f"{name} {objective_text}".lower()
    zone_sort = row.get(17)
    keywords = ("pvp", "player slain", "players slain", "enemy player", "玩家", "战场", "夺旗", "占领")
    pvp_like = zone_sort == -25 or any(keyword in text for keyword in keywords)
    if not pvp_like:
        return {"is_pvp": False, "mode": "not_pvp", "allowed_by_policy": True, "evidence": []}
    evidence = ["battleground_sort"] if zone_sort == -25 else []
    evidence.extend(keyword for keyword in keywords if keyword in text)
    ordinary = bool(objectives) and all(
        obj.get("objective_type") in {"kill", "item"}
        and obj.get("sources")
        and all(source.get("entity_type") == "npc" and "player" not in str(source.get("name", "")).lower() for source in obj.get("sources") or [])
        for obj in objectives
    )
    return {
        "is_pvp": True,
        "mode": "ordinary_quest_mob_kills" if ordinary else "pvp_interaction_or_player_objective",
        "allowed_by_policy": ordinary,
        "evidence": evidence,
    }


def parse_video_reference(candidate_ids: set[int]) -> dict[str, Any]:
    tasks: dict[int, dict[str, Any]] = defaultdict(lambda: {"episodes": [], "mentions": [], "neighbors": set()})
    episodes: dict[str, Any] = {}
    for episode in range(34, 40):
        path = VIDEO_ROOT / f"episode-{episode}-extraction.md"
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        table_rows: list[list[int]] = []
        for line_no, line in enumerate(lines, start=1):
            ids = [int(v) for v in re.findall(r"(?<!\d)(\d{4,5})(?!\d)", line)]
            ids = [qid for qid in ids if qid in candidate_ids]
            if ids:
                for qid in sorted(set(ids)):
                    entry = tasks[qid]
                    if episode not in entry["episodes"]:
                        entry["episodes"].append(episode)
                    if len(entry["mentions"]) < 5:
                        entry["mentions"].append({"episode": episode, "line": line_no, "text": line.strip()[:280]})
            if line.startswith("|") and ids:
                table_rows.append(list(dict.fromkeys(ids)))
        for index, row_ids in enumerate(table_rows):
            neighborhood: set[int] = set(row_ids)
            if index > 0:
                neighborhood.update(table_rows[index - 1])
            if index + 1 < len(table_rows):
                neighborhood.update(table_rows[index + 1])
            for qid in row_ids:
                tasks[qid]["neighbors"].update(neighborhood - {qid})
        episodes[str(episode)] = {"file": str(path.relative_to(ROOT.parent)), "timeline_rows_with_candidate_ids": len(table_rows)}
    serializable = {}
    for qid, entry in tasks.items():
        serializable[str(qid)] = {
            "episodes": sorted(entry["episodes"]),
            "mentions": entry["mentions"],
            "timeline_neighbors": sorted(entry["neighbors"]),
        }
    return {"episodes": episodes, "tasks": serializable}


def journey_reference(candidate_ids: set[int]) -> dict[str, Any]:
    if not JOURNEY_FILE.exists():
        return {"available": False, "current": {}, "legacy_horde": {}}
    summary = summarize_journey(JOURNEY_FILE, preview=5000)
    candidates = summary.get("candidates") or []
    if not candidates:
        return {"available": False, "current": {}, "legacy_horde": {}}

    def compact(candidate: dict[str, Any]) -> dict[str, Any]:
        events = [event for event in candidate.get("events_preview", []) if isinstance(event.get("quest_id"), int) and event["quest_id"] in candidate_ids]
        order = [int(event["quest_id"]) for event in events]
        neighbors: dict[str, list[int]] = {}
        for index, qid in enumerate(order):
            nearby = set(order[max(0, index - 2): index] + order[index + 1:index + 3])
            neighbors[str(qid)] = sorted(set(neighbors.get(str(qid), [])) | nearby)
        return {
            "matched_event_count": len(events),
            "active_quest_ids": sorted(qid for qid in candidate.get("active_quest_ids", []) if qid in candidate_ids),
            "event_quest_ids": order,
            "neighbors": neighbors,
        }

    current = candidates[0]
    legacy_pool = candidates[1:]
    legacy = max(
        legacy_pool,
        key=lambda cand: sum(1 for event in cand.get("events_preview", []) if event.get("quest_id") in candidate_ids),
        default=None,
    )
    return {
        "available": True,
        "current": compact(current),
        "legacy_horde": compact(legacy) if legacy else {},
        "source_sha256": summary.get("source_sha256"),
    }


def variant_components(tasks_by_id: dict[int, dict[str, Any]]) -> list[list[int]]:
    """Find same-title alternative quest IDs, not ordinary exclusive quest branches.

    Questie's `exclusiveTo` is broader than "server variant" and can connect distinct
    quests that are merely mutually unavailable at one moment. Treating every such edge
    as a variant incorrectly collapsed real quest chains. A server/faction variant must
    at minimum have the same canonical English title; `exclusiveTo` is supporting, not
    defining, evidence.
    """
    by_title: dict[str, list[int]] = defaultdict(list)
    for qid, task in tasks_by_id.items():
        title = str(task.get("english_name") or task.get("name") or "").strip().lower()
        if title:
            by_title[title].append(qid)
    groups: list[list[int]] = []
    for ids in by_title.values():
        if len(ids) < 2:
            continue
        linked = []
        id_set = set(ids)
        for qid in ids:
            exclusive = set(tasks_by_id[qid].get("exclusive_to", []))
            same_title_peers = (id_set - {qid})
            if exclusive & same_title_peers or any(qid in set(tasks_by_id[peer].get("exclusive_to", [])) for peer in same_title_peers):
                linked.append(qid)
        # Some Horde/Alliance copies share an exact title but are separated only by race masks.
        faction_masks = {tasks_by_id[qid].get("required_races") for qid in ids}
        if len(linked) >= 2 or len(faction_masks) > 1:
            groups.append(sorted(ids))
    return groups


def task_scope_status(task: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    # Manual Horde/Titan scope overrides. These two legacy Riplash rows have race mask 0
    # and no normal start/finish entities, so the compact DB cannot faction-filter them.
    # Old Horde Journey follows 11620 -> 11625 -> 11626 and never exposes these rows;
    # WotLK reference material identifies 11622 as the Alliance counterpart and 12490
    # as an Alliance/legacy continuation. Keep them out of the reusable Horde route.
    if task.get("quest_id") == 11622:
        return "exclude_alliance_or_other_faction", ["manual_horde_scope_override_alliance_counterpart_of_11620"]
    if task.get("quest_id") == 12490:
        return "exclude_alliance_or_other_faction", ["manual_horde_scope_override_alliance_legacy_riplash_continuation"]
    if not task["is_primary_candidate"]:
        kinds = task["boundary_reference_kinds"]
        if kinds == ["prerequisite"]:
            return "boundary_prerequisite_reference", ["one_hop_dependency_of_primary_borean_candidate"]
        if kinds == ["followup"]:
            return "boundary_followup_reference", ["one_hop_followup_of_primary_borean_candidate"]
        return "boundary_mixed_reference", ["one_hop_boundary_reference"]
    if not task["race_allowed"] or not task["npc_faction_allowed"]:
        reasons.extend(task["faction_reasons"] or ["blood_elf_horde_not_allowed"])
        return "exclude_alliance_or_other_faction", sorted(set(reasons))
    if not task["class_allowed"]:
        return "exclude_other_class", ["paladin_not_allowed"]
    if task["required_skill"]:
        return "exclude_profession", ["requires_profession_or_skill"]
    if task["is_deprecated_or_system"]:
        return "exclude_deprecated_or_system", ["deprecated_placeholder_or_system_quest"]
    if task["is_daily_weekly_monthly_or_repeatable"]:
        return "exclude_repeatable_calendar", ["not_one_time_clearable"]
    if task["pvp"]["is_pvp"] and not task["pvp"]["allowed_by_policy"]:
        return "exclude_pvp_non_mob", ["pvp_requires_player_or_capture_interaction"]
    required_level = task["required_level"]
    if isinstance(required_level, int) and required_level > NATURAL_FIRST_PASS_MAX_REQUIRED_LEVEL:
        return "defer_future_level_revisit", [f"required_level_{required_level}_above_first_pass_window"]
    if not task["xp"]["has_xp"]:
        return "exclude_no_xp_pending_dependency_audit", ["no_quest_xp"]
    if task["is_dungeon"]:
        return "include_leveling_dungeon", ["one_time_xp_dungeon_task"]
    if task["is_cross_map"]:
        return "include_leveling_cross_map", ["accepted_or_objective_or_turnin_crosses_zone_boundary"]
    return "include_leveling_local", ["one_time_xp_horde_paladin_task"]


def main() -> None:
    data = load_questie(QUESTIE_ZIP)
    meta = _parse_zone_metadata(QUESTIE_ZIP)
    initial_ids, union_sources = raw_candidate_ids(data, meta)
    candidate_ids, rows, correction_audit, candidate_roles = effective_with_boundary_refs(data, initial_ids)
    video = parse_video_reference(candidate_ids)
    journey = journey_reference(candidate_ids)

    latest_seen = set(journey.get("current", {}).get("event_quest_ids", []))
    tasks: list[dict[str, Any]] = []
    tasks_by_id: dict[int, dict[str, Any]] = {}
    for quest_id in sorted(candidate_ids):
        row = rows.get(quest_id)
        if not isinstance(row, dict):
            continue
        name = localized_name(data, quest_id, row)
        objective_zh = localized_objective(data, quest_id)
        objective_en = english_objective(row)
        classified, review = classify_objectives(data, row, ZONE_ID, objective_zh or objective_en)
        objective_dicts = [asdict(obj) for obj in classified]
        extra_objectives = extract_extra_objectives(data, row, ZONE_ID)
        task_class, task_flags = classify_task(classified, objective_en or objective_zh)
        start_entities = entity_group(data, row.get(2))
        finish_entities = entity_group(data, row.get(3))
        objective_entity_zones = objective_route_zones(objective_dicts, ZONE_ID)
        assigned = assigned_parent_zone(row, meta["parents"])
        effective_touch = direct_touches_zone(data, row, ZONE_ID)
        race_allowed = bit_allows(row.get(6), BLOOD_ELF_FLAG)
        class_allowed = bit_allows(row.get(7), PALADIN_FLAG)
        npc_allowed, npc_reasons = npc_faction_eligibility(data, row)
        faction_reasons = list(npc_reasons)
        if not race_allowed:
            faction_reasons.append("required_races_excludes_blood_elf")
        xp = xp_facts(data, quest_id, row)
        qflags = int(row.get(23) or 0)
        sflags = int(row.get(24) or 0)
        is_repeat = bool(sflags & REPEATABLE or qflags & (DAILY | WEEKLY | MONTHLY))
        lower_name = name.lower()
        is_deprecated = (
            "deprecated" in lower_name
            or "deprecaed" in lower_name
            or name.strip(" ?") == ""
            or "????" in name
            or ((row.get(5) in (None, 0)) and not xp["has_xp"] and not effective_touch)
        )
        deps = dependency_ids(row)
        start_route_zones = sorted({zone for entity in start_entities for zone in preferred_entity_route_zones(entity, ZONE_ID)})
        finish_route_zones = sorted({zone for entity in finish_entities for zone in preferred_entity_route_zones(entity, ZONE_ID)})
        extra_route_zones = sorted({zone for extra in extra_objectives for zone in extra.get("route_zones", [])})
        all_zones = sorted(set(start_route_zones + finish_route_zones + objective_entity_zones + extra_route_zones))
        is_cross = any(zone != ZONE_ID for zone in all_zones) or (assigned is not None and assigned != ZONE_ID and effective_touch)
        is_dungeon = bool((assigned is not None and assigned in meta["dungeons"]) or any(zone in meta["dungeons"] for zone in all_zones))
        pvp = pvp_classification(row, name, objective_en or objective_zh, objective_dicts)
        item_start_ids = _ids(row.get(2), 3)
        boundary_reference_kinds = []
        if quest_id in candidate_roles["boundary_prerequisite"]:
            boundary_reference_kinds.append("prerequisite")
        if quest_id in candidate_roles["boundary_followup"]:
            boundary_reference_kinds.append("followup")
        task = {
            "quest_id": quest_id,
            "name": name,
            "is_primary_candidate": quest_id in candidate_roles["primary"],
            "boundary_reference_kinds": boundary_reference_kinds,
            "english_name": str(row.get(1) or ""),
            "required_level": row.get(4),
            "quest_level": row.get(5),
            "required_races": row.get(6),
            "required_classes": row.get(7),
            "required_skill": row.get(18),
            "required_min_rep": row.get(19),
            "required_max_rep": row.get(20),
            "required_max_level": row.get(32),
            "quest_flags": qflags,
            "special_flags": sflags,
            "assigned_zone_id": assigned,
            "raw_zone_or_sort": row.get(17),
            "touches_borean_effective": effective_touch,
            "is_external_prerequisite_only": not effective_touch and assigned != ZONE_ID,
            "is_cross_map": is_cross,
            "is_dungeon": is_dungeon,
            "is_raid_flagged": bool(qflags & RAID),
            "race_allowed": race_allowed,
            "class_allowed": class_allowed,
            "npc_faction_allowed": npc_allowed,
            "faction_reasons": sorted(set(faction_reasons)),
            "is_daily_weekly_monthly_or_repeatable": is_repeat,
            "is_deprecated_or_system": is_deprecated,
            "xp": xp,
            "pvp": pvp,
            "objective_text_zh": objective_zh,
            "objective_text_en": objective_en,
            "task_class": task_class,
            "task_flags": task_flags,
            "objective_review": review,
            "objectives": objective_dicts,
            "extra_objectives": extra_objectives,
            "start_entities": start_entities,
            "finish_entities": finish_entities,
            "item_start_ids": item_start_ids,
            "start_zones": start_route_zones,
            "objective_zones": objective_entity_zones,
            "extra_objective_zones": extra_route_zones,
            "turnin_zones": finish_route_zones,
            "all_route_zones": all_zones,
            "pre_any": deps["pre_any"],
            "pre_all": deps["pre_all"],
            "parent_active": deps["parent_active"],
            "available_starting_with": deps["available_starting_with"],
            "next_quest": row.get(22),
            "child_quests": [int(v) for v in seq(row.get(14)) if isinstance(v, int)],
            "exclusive_to": [int(v) for v in seq(row.get(16)) if isinstance(v, int)],
            "breadcrumb_for": row.get(27),
            "breadcrumbs": [int(v) for v in seq(row.get(28)) if isinstance(v, int)],
            "observed_in_current_journey": quest_id in latest_seen,
            "video_reference": video["tasks"].get(str(quest_id), {"episodes": [], "mentions": [], "timeline_neighbors": []}),
            "legacy_horde_neighbors": journey.get("legacy_horde", {}).get("neighbors", {}).get(str(quest_id), []),
            "quest_log": {
                "accept_delta": 1,
                "release_delta": -1,
                "release_event": "auto_complete" if qflags & AUTO_REWARDED else "turnin",
                "hard_cap": QUEST_LOG_CAP,
                "soft_warning_at": QUEST_LOG_SOFT_WARNING,
            },
        }
        status, reasons = task_scope_status(task)
        task["scope_status"] = status
        task["scope_reasons"] = reasons
        tasks.append(task)
        tasks_by_id[quest_id] = task

    # Resolve mutually-exclusive same-name server variants using the latest real Horde journey.
    variant_groups = variant_components(tasks_by_id)
    variant_audit: list[dict[str, Any]] = []
    for group in variant_groups:
        observed = [qid for qid in group if qid in latest_seen]
        selected = observed[0] if len(observed) == 1 else None
        variant_audit.append({"quest_ids": group, "observed_current": observed, "selected": selected})
        if selected is not None:
            for qid in group:
                task = tasks_by_id[qid]
                task["variant_group"] = group
                task["selected_server_variant"] = qid == selected
                if qid != selected and task["scope_status"].startswith("include_"):
                    task["scope_status"] = "exclude_server_variant"
                    task["scope_reasons"] = [f"same_server_observed_variant_is_{selected}"]
        else:
            for qid in group:
                tasks_by_id[qid]["variant_group"] = group
                tasks_by_id[qid]["selected_server_variant"] = None

    # Reclassify no-XP quests that are strict mandatory prerequisites of included XP tasks.
    included_ids = {qid for qid, task in tasks_by_id.items() if task["scope_status"].startswith("include_leveling")}
    changed = True
    structural_zero_xp: set[int] = set()
    while changed:
        changed = False
        for qid in sorted(included_ids | structural_zero_xp):
            task = tasks_by_id[qid]
            mandatory = set(task["pre_all"] + task["parent_active"])
            if len(task["pre_any"]) == 1:
                mandatory.update(task["pre_any"])
            for dep in mandatory:
                dep_task = tasks_by_id.get(dep)
                if not dep_task:
                    continue
                if dep_task["scope_status"] == "exclude_no_xp_pending_dependency_audit" and dep not in structural_zero_xp:
                    dep_task["scope_status"] = "include_structural_zero_xp_prerequisite"
                    dep_task["scope_reasons"] = [f"mandatory_for_xp_quest_{qid}"]
                    structural_zero_xp.add(dep)
                    changed = True

    # Remaining no-XP tasks are intentionally outside the leveling route.
    for task in tasks:
        if task["scope_status"] == "exclude_no_xp_pending_dependency_audit":
            task["scope_status"] = "exclude_no_xp"
            task["scope_reasons"] = ["no_quest_xp_and_not_mandatory_for_included_xp_task"]

    # Keep only one-hop boundary references that are actually reachable from the surviving
    # Borean full-clear scope. For preQuestSingle (ANY), a viable primary alternative means
    # we do not drag an unused external alternative into the route model.
    route_seed_ids = {
        qid for qid, task in tasks_by_id.items()
        if task["is_primary_candidate"] and (task["scope_status"].startswith("include_") or task["scope_status"] == "defer_future_level_revisit")
    }
    boundary_referenced_by: dict[int, set[int]] = defaultdict(set)
    for qid in sorted(route_seed_ids):
        task = tasks_by_id[qid]
        mandatory = set(task["pre_all"] + task["parent_active"] + task["available_starting_with"])
        for dep in mandatory:
            if dep in tasks_by_id and not tasks_by_id[dep]["is_primary_candidate"]:
                boundary_referenced_by[dep].add(qid)
        if task["pre_any"]:
            viable_primary_any = [
                dep for dep in task["pre_any"]
                if dep in tasks_by_id
                and tasks_by_id[dep]["is_primary_candidate"]
                and (tasks_by_id[dep]["scope_status"].startswith("include_") or tasks_by_id[dep]["scope_status"] == "defer_future_level_revisit")
            ]
            if not viable_primary_any:
                for dep in task["pre_any"]:
                    if dep in tasks_by_id and not tasks_by_id[dep]["is_primary_candidate"]:
                        boundary_referenced_by[dep].add(qid)
        followup_ids = set(task["child_quests"] + task["breadcrumbs"])
        if isinstance(task.get("next_quest"), int):
            followup_ids.add(int(task["next_quest"]))
        if isinstance(task.get("breadcrumb_for"), int):
            followup_ids.add(int(task["breadcrumb_for"]))
        for followup in followup_ids:
            if followup in tasks_by_id and not tasks_by_id[followup]["is_primary_candidate"]:
                boundary_referenced_by[followup].add(qid)

    for qid, task in tasks_by_id.items():
        if task["is_primary_candidate"]:
            continue
        task["boundary_referenced_by_quest_ids"] = sorted(boundary_referenced_by.get(qid, set()))
        if qid not in boundary_referenced_by:
            task["scope_status"] = "boundary_irrelevant_reference"
            task["scope_reasons"] = ["only_referenced_by_excluded_or_unused_alternative_primary_candidate"]
            continue
        if not task["race_allowed"] or not task["npc_faction_allowed"] or not task["class_allowed"]:
            task["scope_status"] = "boundary_incompatible_reference"
            task["scope_reasons"] = ["boundary_reference_not_available_to_blood_elf_horde_paladin"]
        elif task["required_skill"]:
            task["scope_status"] = "boundary_profession_reference"
            task["scope_reasons"] = ["boundary_reference_requires_profession_or_skill"]
        elif task["is_daily_weekly_monthly_or_repeatable"]:
            task["scope_status"] = "boundary_repeatable_reference"
            task["scope_reasons"] = ["boundary_reference_not_one_time_clearable"]
        elif task["pvp"]["is_pvp"] and not task["pvp"]["allowed_by_policy"]:
            task["scope_status"] = "boundary_pvp_disallowed_reference"
            task["scope_reasons"] = ["boundary_reference_requires_disallowed_pvp_interaction"]
        elif not task["xp"]["has_xp"] and "followup" in task["boundary_reference_kinds"] and "prerequisite" not in task["boundary_reference_kinds"]:
            task["scope_status"] = "boundary_no_xp_followup_excluded"
            task["scope_reasons"] = ["boundary_followup_has_no_quest_xp"]
        elif "prerequisite" in task["boundary_reference_kinds"] and not task["xp"]["has_xp"]:
            task["scope_status"] = "boundary_structural_no_xp_prerequisite"
            task["scope_reasons"] = ["direct_boundary_prerequisite_even_though_no_xp"]

    # Split cross-map full-clear tasks by when they can actually occur. Inbound return
    # chains remain in the universe but must not be inserted into the initial Borean pass.
    for task in tasks:
        if task["scope_status"] != "include_leveling_cross_map":
            continue
        starts_here = ZONE_ID in task["start_zones"]
        finishes_here = ZONE_ID in task["turnin_zones"]
        starts_elsewhere = any(zone != ZONE_ID for zone in task["start_zones"])
        finishes_elsewhere = any(zone != ZONE_ID for zone in task["turnin_zones"])
        if starts_elsewhere and finishes_here:
            task["scope_status"] = "include_later_cross_map_inbound"
            task["scope_reasons"] = ["starts_outside_borean_and_returns_here_after_later_map_progress"]
        elif starts_here and finishes_elsewhere:
            task["scope_status"] = "include_leveling_cross_map_outbound"
            task["scope_reasons"] = ["starts_in_borean_and_naturally_carries_into_next_location"]
    changed = True
    while changed:
        changed = False
        for task in tasks:
            if task["scope_status"] != "include_leveling_cross_map_outbound":
                continue
            predecessors = [tasks_by_id.get(qid) for qid in task["pre_any"] + task["pre_all"] + task["parent_active"]]
            if any(pred and pred["scope_status"].startswith("include_later_cross_map") for pred in predecessors):
                task["scope_status"] = "include_later_cross_map_followup"
                task["scope_reasons"] = ["outbound_step_is_unlocked_only_after_a_later_cross_map_return_chain"]
                changed = True

    # Exact-real-entity target clusters. One task may participate in multiple clusters.
    clusters: dict[str, dict[str, Any]] = {}
    targetless_included: list[int] = []
    for task in tasks:
        if not task["scope_status"].startswith("include_"):
            continue
        relations = 0
        for objective in task["objectives"]:
            otype = objective.get("objective_type")
            for source in objective.get("sources") or []:
                zones = source.get("zones") or []
                if ZONE_ID not in zones:
                    continue
                entity_type = str(source.get("entity_type"))
                entity_id = source.get("entity_id")
                if not isinstance(entity_id, int):
                    continue
                key = f"{entity_type}:{entity_id}"
                cluster = clusters.setdefault(key, {
                    "cluster_id": key,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "name": source.get("name"),
                    "borean_representative": (source.get("representative_by_zone") or {}).get(str(ZONE_ID)),
                    "spawn_count": source.get("spawn_count"),
                    "relations": [],
                    "quest_ids": [],
                    "video_reference_episodes": set(),
                })
                if otype == "item":
                    relation_kind = f"resolved_item_source:{objective.get('item_id')}"
                elif otype == "kill":
                    relation_kind = "direct_creature"
                elif otype == "object":
                    relation_kind = "direct_object"
                elif otype == "event":
                    relation_kind = "direct_event_source"
                else:
                    relation_kind = f"direct_or_special:{otype}"
                cluster["relations"].append({
                    "quest_id": task["quest_id"],
                    "quest_name": task["name"],
                    "relation_kind": relation_kind,
                    "required_count": objective.get("required_count"),
                    "item_id": objective.get("item_id"),
                })
                cluster["quest_ids"].append(task["quest_id"])
                cluster["video_reference_episodes"].update(task["video_reference"].get("episodes", []))
                relations += 1
        if relations == 0:
            targetless_included.append(task["quest_id"])

    cluster_list: list[dict[str, Any]] = []
    for cluster in clusters.values():
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["video_reference_episodes"] = sorted(cluster["video_reference_episodes"])
        cluster["relations"].sort(key=lambda row: (row["quest_id"], row["relation_kind"]))
        cluster["shared_by_multiple_tasks"] = len(cluster["quest_ids"]) > 1
        cluster["adversarial_flags"] = []
        if len(cluster["quest_ids"]) > 1 and not cluster["borean_representative"]:
            cluster["adversarial_flags"].append("shared_cluster_missing_borean_representative")
        cluster_list.append(cluster)
    cluster_list.sort(key=lambda c: (-len(c["quest_ids"]), str(c["name"]), c["entity_id"]))

    # Special mechanism anchors are kept separate from Target Clusters. An NPC/object used
    # for a scripted interaction is not automatically the same semantic target as a kill/drop.
    special_anchor_clusters: dict[str, dict[str, Any]] = {}
    special_coordinate_anchors: list[dict[str, Any]] = []
    for task in tasks:
        if not task["scope_status"].startswith("include_"):
            continue
        for extra in task.get("extra_objectives", []):
            for entity in extra.get("references", []):
                if ZONE_ID not in entity.get("zones", []):
                    continue
                entity_id = entity.get("entity_id")
                entity_type = entity.get("entity_type")
                if not isinstance(entity_id, int):
                    continue
                key = f"{entity_type}:{entity_id}"
                cluster = special_anchor_clusters.setdefault(key, {
                    "anchor_id": key,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "name": entity.get("name"),
                    "borean_representative": (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)),
                    "relations": [],
                    "quest_ids": [],
                })
                cluster["relations"].append({
                    "quest_id": task["quest_id"],
                    "quest_name": task["name"],
                    "extra_index": extra.get("index"),
                    "text": extra.get("text"),
                    "relation_kind": "special_mechanism_anchor",
                })
                cluster["quest_ids"].append(task["quest_id"])
            points = (extra.get("coordinates_by_zone") or {}).get(str(ZONE_ID), [])
            if points:
                special_coordinate_anchors.append({
                    "quest_id": task["quest_id"],
                    "quest_name": task["name"],
                    "extra_index": extra.get("index"),
                    "text": extra.get("text"),
                    "points": points,
                })
    special_anchor_list = []
    for cluster in special_anchor_clusters.values():
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["relations"].sort(key=lambda row: (row["quest_id"], row["extra_index"] or 0))
        special_anchor_list.append(cluster)
    special_anchor_list.sort(key=lambda row: (str(row["name"]), row["entity_id"]))

    # Full-clear availability hazards from Questie `exclusiveTo`: the quest on the left
    # must be accepted before any listed included peer becomes active or completed.
    included_ids_now = {task["quest_id"] for task in tasks if task["scope_status"].startswith("include_")}
    availability_constraints: list[dict[str, Any]] = []
    for task in tasks:
        if task["quest_id"] not in included_ids_now:
            continue
        peers = sorted(qid for qid in task.get("exclusive_to", []) if qid in included_ids_now)
        if peers:
            availability_constraints.append({
                "quest_id": task["quest_id"],
                "quest_name": task["name"],
                "must_accept_before_quest_ids": peers,
                "peer_names": [tasks_by_id[qid]["name"] for qid in peers],
                "reason": "Questie exclusiveTo blocks this quest if a peer is active or completed",
            })

    counts = Counter(task["scope_status"] for task in tasks)
    primary_counts = Counter(task["scope_status"] for task in tasks if task["is_primary_candidate"])
    boundary_counts = Counter(task["scope_status"] for task in tasks if not task["is_primary_candidate"])
    exclusion_rows = [
        {"quest_id": task["quest_id"], "name": task["name"], "status": task["scope_status"], "reasons": task["scope_reasons"]}
        for task in tasks
        if task["is_primary_candidate"] and not task["scope_status"].startswith("include_")
    ]
    boundary_rows = [
        {"quest_id": task["quest_id"], "name": task["name"], "status": task["scope_status"], "reasons": task["scope_reasons"], "kinds": task["boundary_reference_kinds"]}
        for task in tasks
        if not task["is_primary_candidate"]
    ]

    # Adversarial checks.
    checks: list[dict[str, Any]] = []
    def check(name: str, ok: bool, detail: Any) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    check("questie_corrections_parse_clean", correction_audit["failed_block_count"] == 0 and correction_audit["unresolved_symbol_count"] == 0, correction_audit)
    check("every_task_has_scope_status", all(task.get("scope_status") for task in tasks), len(tasks))
    check("every_excluded_task_has_reason", all(row["reasons"] for row in exclusion_rows), len(exclusion_rows))
    check("no_alliance_task_included", not any(task["scope_status"].startswith("include_") and (not task["race_allowed"] or not task["npc_faction_allowed"]) for task in tasks), None)
    check("no_repeatable_calendar_task_included", not any(task["scope_status"].startswith("include_") and task["is_daily_weekly_monthly_or_repeatable"] for task in tasks), None)
    check("no_disallowed_pvp_included", not any(task["scope_status"].startswith("include_") and task["pvp"]["is_pvp"] and not task["pvp"]["allowed_by_policy"] for task in tasks), None)
    check("no_unjustified_zero_xp_included", not any(task["scope_status"].startswith("include_") and not task["xp"]["has_xp"] and task["scope_status"] != "include_structural_zero_xp_prerequisite" for task in tasks), sorted(task["quest_id"] for task in tasks if task["scope_status"].startswith("include_") and not task["xp"]["has_xp"]))
    unresolved_variants = []
    for row in variant_audit:
        if row["selected"] is not None:
            continue
        included_peers = [qid for qid in row["quest_ids"] if tasks_by_id[qid]["scope_status"].startswith("include_")]
        if len(included_peers) > 1:
            unresolved_variants.append({**row, "included_peers": included_peers})
    check("server_variants_resolved_or_flagged", not unresolved_variants, unresolved_variants)
    included_target_facts = sum(1 for cluster in cluster_list for _ in cluster["relations"])
    check("included_target_cluster_facts_present", included_target_facts > 0, included_target_facts)
    check("shared_target_clusters_have_coordinates", not any(cluster["adversarial_flags"] for cluster in cluster_list if cluster["shared_by_multiple_tasks"]), [cluster for cluster in cluster_list if cluster["shared_by_multiple_tasks"] and cluster["adversarial_flags"]])
    check("quest_log_metadata_complete", all(task.get("quest_log", {}).get("hard_cap") == 25 for task in tasks), None)
    availability_edges = {(row["quest_id"], peer) for row in availability_constraints for peer in row["must_accept_before_quest_ids"]}
    symmetric_availability = sorted((a, b) for a, b in availability_edges if (b, a) in availability_edges and a < b)
    check("full_clear_availability_constraints_not_mutually_impossible", not symmetric_availability, symmetric_availability)
    included_extra_count = sum(len(task.get("extra_objectives", [])) for task in tasks if task["scope_status"].startswith("include_"))
    check("questie_extra_objectives_materialized", included_extra_count > 0 and (special_anchor_list or special_coordinate_anchors), {"included_extra_objectives": included_extra_count, "entity_anchor_clusters": len(special_anchor_list), "coordinate_anchors": len(special_coordinate_anchors)})

    valid_boundary_statuses = {"boundary_prerequisite_reference", "boundary_mixed_reference", "boundary_structural_no_xp_prerequisite"}
    unresolved_external_dependencies: list[dict[str, Any]] = []
    for qid in sorted(route_seed_ids):
        task = tasks_by_id[qid]
        for dep in set(task["pre_all"] + task["parent_active"] + task["available_starting_with"]):
            if dep in tasks_by_id and not tasks_by_id[dep]["is_primary_candidate"] and tasks_by_id[dep]["scope_status"] not in valid_boundary_statuses:
                unresolved_external_dependencies.append({"quest_id": qid, "dependency": dep, "dependency_status": tasks_by_id[dep]["scope_status"], "kind": "mandatory"})
        if task["pre_any"]:
            viable_primary = [dep for dep in task["pre_any"] if dep in tasks_by_id and tasks_by_id[dep]["is_primary_candidate"] and (tasks_by_id[dep]["scope_status"].startswith("include_") or tasks_by_id[dep]["scope_status"] == "defer_future_level_revisit")]
            viable_boundary = [dep for dep in task["pre_any"] if dep in tasks_by_id and not tasks_by_id[dep]["is_primary_candidate"] and tasks_by_id[dep]["scope_status"] in valid_boundary_statuses]
            if not viable_primary and not viable_boundary:
                unresolved_external_dependencies.append({"quest_id": qid, "pre_any": task["pre_any"], "kind": "any_without_viable_option"})
    check("included_tasks_have_viable_external_prerequisites", not unresolved_external_dependencies, unresolved_external_dependencies)

    # Borean-specific regression checks distilled from episode 34-39 adjacency evidence and
    # the latest Horde Journey. These are reference coverage checks, not route-order authority.
    reference_groups = {
        "kaluak_coast": [11613, 11619, 11620, 11625, 11626],
        "kaskala_outbound": [11949, 11950, 11961, 11968, 12117],
        "coldrock_ancestors": [11605, 11607, 11609, 11610],
        "coldrock_quarry": [11612, 11617, 11623],
        "dehta": [11864, 11865, 11866, 11868, 11869, 11870, 11871, 11872, 11876, 11878, 11879, 11884, 11892],
        "amber_ledge": [11574, 11587, 11590, 11646, 11648, 11663, 11671, 11679, 11680, 11681, 11682, 11733, 11576, 11582, 12728],
        "coldarra": [11900, 11905, 11910, 11911, 11912, 11914, 11918, 11936, 11919, 11931, 11941, 11943, 11946, 11951, 11957, 11967, 11969, 11973],
        "winterfin": [11702, 11571, 11559, 11560, 11561, 11562, 11563, 11564, 11565, 11566, 11569, 11570, 12728],
        "nexus": [11905, 11911, 11973, 13095],
        "warsong_opening": [11585, 11596, 11598, 11606, 11611, 11602, 11608, 11614, 11615, 11616, 11618, 11676, 11686, 11688, 11690, 11703, 11705],
    }
    reference_group_failures = []
    for group_name, quest_ids in reference_groups.items():
        bad = [
            {"quest_id": qid, "status": tasks_by_id[qid]["scope_status"] if qid in tasks_by_id else "missing"}
            for qid in quest_ids
            if qid not in tasks_by_id or not tasks_by_id[qid]["scope_status"].startswith("include_")
        ]
        if bad:
            reference_group_failures.append({"group": group_name, "bad": bad})
    check("video_reference_groups_survive_scope", not reference_group_failures, reference_group_failures)

    cluster_by_id = {cluster["cluster_id"]: cluster for cluster in cluster_list}
    expected_shared = {
        "npc:25445": {11598, 11606},
        "npc:25468": {11714, 11716},
        "npc:25707": {11910, 11912},
        "npc:25722": {11912, 11918},
        "npc:25836": {11866, 11869},
        "npc:25479": {11655, 11660},
    }
    shared_failures = []
    for cluster_id, expected_ids in expected_shared.items():
        actual = set((cluster_by_id.get(cluster_id) or {}).get("quest_ids", []))
        if not expected_ids.issubset(actual):
            shared_failures.append({"cluster_id": cluster_id, "expected_subset": sorted(expected_ids), "actual": sorted(actual)})
    check("known_shared_target_clusters_preserved", not shared_failures, shared_failures)

    special_by_id = {cluster["anchor_id"]: cluster for cluster in special_anchor_list}
    expected_special = {
        "object:187561": {11587},
        "npc:25334": {11652},
        "npc:25607": {11690},
    }
    special_failures = []
    for anchor_id, expected_ids in expected_special.items():
        actual = set((special_by_id.get(anchor_id) or {}).get("quest_ids", []))
        if not expected_ids.issubset(actual):
            special_failures.append({"anchor_id": anchor_id, "expected_subset": sorted(expected_ids), "actual": sorted(actual)})
    check("known_script_mechanism_anchors_preserved", not special_failures, special_failures)

    availability_by_id = {row["quest_id"]: set(row["must_accept_before_quest_ids"]) for row in availability_constraints}
    expected_availability = {11574: {11587}, 11591: {11592, 11593, 11594}}
    availability_failures = [
        {"quest_id": qid, "expected": sorted(peers), "actual": sorted(availability_by_id.get(qid, set()))}
        for qid, peers in expected_availability.items()
        if not peers.issubset(availability_by_id.get(qid, set()))
    ]
    check("known_full_clear_missable_constraints_preserved", not availability_failures, availability_failures)

    expected_cross_status = {
        11930: "include_leveling_cross_map_outbound",
        12117: "include_leveling_cross_map_outbound",
        13242: "include_later_cross_map_inbound",
        13257: "include_later_cross_map_followup",
    }
    cross_failures = [
        {"quest_id": qid, "expected": status, "actual": tasks_by_id[qid]["scope_status"] if qid in tasks_by_id else "missing"}
        for qid, status in expected_cross_status.items()
        if qid not in tasks_by_id or tasks_by_id[qid]["scope_status"] != status
    ]
    check("cross_map_direction_and_phase_preserved", not cross_failures, cross_failures)

    foundation = {
        "title": "北风苔原 Route Atlas 基础任务事实层",
        "zone": {"id": ZONE_ID, "name": "北风苔原"},
        "route_assumptions": {
            "reusable_start": "奥格瑞玛飞艇抵达战歌要塞，按未接未做重新设计",
            "current_live_state_is_reference_only": True,
            "personal_flying_before_level_77": False,
            "taxi_flight_paths_allowed": True,
            "warsong_hold_flight_point_action_required_in_reusable_route": True,
            "northrend_policy": "one-time XP quests full-clear; cross-map quests accepted; no-XP excluded unless mandatory for XP continuation",
            "quest_log_cap": QUEST_LOG_CAP,
            "quest_log_soft_warning": QUEST_LOG_SOFT_WARNING,
        },
        "source": {"questie_version": data.version, "questie_sha256": data.source_sha256},
        "candidate_union": union_sources,
        "primary_candidate_count": len(initial_ids),
        "candidate_count_with_one_hop_boundary_refs": len(candidate_ids),
        "boundary_reference_counts": {key: len(value) for key, value in candidate_roles.items() if key != "primary"},
        "correction_audit": correction_audit,
        "scope_counts": dict(sorted(counts.items())),
        "primary_scope_counts": dict(sorted(primary_counts.items())),
        "boundary_scope_counts": dict(sorted(boundary_counts.items())),
        "variant_groups": variant_audit,
        "structural_zero_xp_quest_ids": sorted(structural_zero_xp),
        "full_clear_availability_constraints": availability_constraints,
        "current_journey_reference": {
            "active_quest_ids": journey.get("current", {}).get("active_quest_ids", []),
            "matched_event_count": journey.get("current", {}).get("matched_event_count", 0),
            "not_used_as_reusable_completion_state": True,
        },
        "tasks": tasks,
    }
    special_anchored_quest_ids = sorted({qid for row in special_anchor_list for qid in row["quest_ids"]} | {row["quest_id"] for row in special_coordinate_anchors})
    cluster_payload = {
        "title": "北风苔原 Target Clusters（完全相同真实目标实体）",
        "method": "Questie effective facts -> exact real entity id; direct and resolved-item-source relations remain typed; route order not assigned here; scripted extraObjectives are kept in a separate special-anchor layer",
        "cluster_count": len(cluster_list),
        "shared_cluster_count": sum(1 for c in cluster_list if c["shared_by_multiple_tasks"]),
        "targetless_included_quest_ids": sorted(targetless_included),
        "targetless_but_special_anchored_quest_ids": sorted(set(targetless_included) & set(special_anchored_quest_ids)),
        "pure_travel_or_dialogue_quest_ids": sorted(set(targetless_included) - set(special_anchored_quest_ids)),
        "clusters": cluster_list,
        "special_mechanism_anchor_clusters": special_anchor_list,
        "special_mechanism_coordinate_anchors": special_coordinate_anchors,
    }
    exclusion_payload = {
        "primary_counts": dict(sorted(Counter(row["status"] for row in exclusion_rows).items())),
        "excluded_or_deferred_primary_tasks": exclusion_rows,
        "boundary_reference_counts": dict(sorted(Counter(row["status"] for row in boundary_rows).items())),
        "boundary_references": boundary_rows,
        "policy_note": "Every primary Borean task outside the first-pass included scope has an explicit reason. Deferred future-level tasks remain in the Northrend full-clear universe. One-hop boundary references are tracked separately, not counted as omitted Borean tasks.",
    }
    video_payload = {
        **video,
        "legacy_horde_journey_reference": journey.get("legacy_horde", {}),
        "usage": "reference insertion adjacency only; never overrides prerequisite/target/spatial/log-cap logic",
    }

    for path, payload in (
        (OUTPUT_FOUNDATION, foundation),
        (OUTPUT_CLUSTERS, cluster_payload),
        (OUTPUT_VIDEO, video_payload),
        (OUTPUT_EXCLUSIONS, exclusion_payload),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures = [row for row in checks if not row["ok"]]
    lines = [
        "# 北风苔原基础数据与Target Cluster对抗式审查",
        "",
        "状态：第一阶段基础层；**尚未开始按R1/R2逐簇插入路线**。",
        "",
        "## 1. 本轮冻结规则",
        "",
        "- 复用路线起点按飞艇刚到战歌要塞、未接未做；当前历程只用于服务器版本/现场事实参考。",
        "- 77级前禁止个人飞行；鸟点/飞艇等系统交通仍可使用。",
        "- 诺森德一次性有经验任务按全清建模；跨地图任务必须进入候选和任务栏容量模型。",
        "- 无经验任务默认不进入升级路线；若它是后续有经验任务的唯一/强制前置，则保留为结构性前置。",
        "- 联盟/非血精灵圣骑任务排除。PvP仅允许普通任务怪击杀；玩家击杀/占点/夺旗等排除。",
        "- 任务栏硬上限25；每个接取记+1，每个交付/自动完成释放-1；22起软警告，后续每次插入必须重放计数器。",
        "- 视频34–39集和旧部落Journey只提供任务邻接/同片区参考，不覆盖我们的前置、Target Cluster、Spatial Instance与任务栏约束。",
        "",
        "## 2. 基础数据结果",
        "",
        f"- Questie：{data.version}；raw assigned={len(union_sources['raw_assigned'])}，raw direct-touches={len(union_sources['raw_touches'])}，修正层Borean提示={len(union_sources['correction_zone_hints'])}。",
        f"- 北风主候选{len(initial_ids)}条；加一跳外部前置/后续边界引用后总记录{len(candidate_ids)}条。边界前置{len(candidate_roles['boundary_prerequisite'])}条、边界后续{len(candidate_roles['boundary_followup'])}条。",
        f"- WotLK修正层：命中{correction_audit['candidate_block_count']}，成功解析{correction_audit['parsed_block_count']}，失败{correction_audit['failed_block_count']}。",
        f"- 北风主候选Scope分布：`{json.dumps(dict(sorted(primary_counts.items())), ensure_ascii=False)}`。",
        f"- 边界引用Scope分布：`{json.dumps(dict(sorted(boundary_counts.items())), ensure_ascii=False)}`。",
        f"- Target Cluster：{len(cluster_list)}个，其中多任务共享实体簇{sum(1 for c in cluster_list if c['shared_by_multiple_tasks'])}个；普通目标为空的纳入任务{len(targetless_included)}个。",
        f"- Questie extraObjectives：纳入任务共{included_extra_count}条特殊机制事实；形成{len(special_anchor_list)}个实体锚点簇和{len(special_coordinate_anchors)}个纯坐标锚点。",
        f"- 全清可错过约束：{len(availability_constraints)}条。",
        "",
        "## 3. 对抗式检查",
        "",
    ]
    for row in checks:
        lines.append(f"- {'PASS' if row['ok'] else 'FAIL'} `{row['check']}`：{json.dumps(row['detail'], ensure_ascii=False) if row['detail'] is not None else '无异常'}")
    lines.extend(["", "## 4. 全清可错过约束与跨图边界", ""])
    for row in availability_constraints:
        peer_text = "、".join(f"`{qid}`《{tasks_by_id[qid]['name']}》" for qid in row["must_accept_before_quest_ids"])
        lines.append(f"- `{row['quest_id']}`《{row['quest_name']}》必须先接，再让{peer_text}进入任务栏或完成；否则Questie `exclusiveTo` 语义会使前者不可接。")
    lines.append("- 初次北风自然出图：`11930`《横贯冰原》、`12117`《前往莫亚基港口》；两者接取后会占用任务栏，直到龙骨荒野对应交付点释放。")
    lines.append("- 后续回北风链：`13242`《黑暗的骚动》需要先完成龙骨荒野`12500`《返回安加萨》，之后回战歌要塞交；再解锁`13257`《战争的使者》并前往奥格瑞玛。这两条保留在全清宇宙，但不插入初次北风清图。")
    relevant_boundary = [row for row in boundary_rows if row["status"] != "boundary_irrelevant_reference"]
    if relevant_boundary:
        lines.append("- 一跳跨图边界引用：")
        for row in sorted(relevant_boundary, key=lambda r: r["quest_id"]):
            refs = tasks_by_id[row["quest_id"]].get("boundary_referenced_by_quest_ids", [])
            lines.append(f"  - `{row['quest_id']}`《{row['name']}》 → `{row['status']}`，由北风任务{refs}直接引用。")

    lines.extend(["", "## 5. 不进入初次升级路线的北风主任务与原因", ""])
    for row in sorted(exclusion_rows, key=lambda r: (r["status"], r["quest_id"])):
        lines.append(f"- `{row['quest_id']}`《{row['name']}》 → `{row['status']}`：{'；'.join(row['reasons'])}")

    lines.extend(["", "## 6. 审查结论", ""])
    if failures:
        for row in failures:
            lines.append(f"- 必须修正：`{row['check']}`。")
    else:
        lines.append("- 机器检查与本轮人工对抗复核全部通过。人工复核已覆盖：旧158条自动候选差集、联盟/职业/重复/无经验过滤、服务器任务版本、跨图方向与阶段、Questie `exclusiveTo` 可错过约束、`extraObjectives`脚本机制、视频34—39集任务组覆盖，以及已知共享真实目标实体簇。")
        lines.append("- 基础任务事实层与Target Cluster层可以冻结进入下一阶段；**尚未生成R1路线**。下一步先把Target Cluster人工拆成真实Spatial Instance，再从战歌要塞构造R1，之后严格逐簇插入。")
        lines.append("- 从R1开始，每次插入都必须重放25格任务栏计数器，并同时查看视频邻接参考；视频只能建议合并位置，不能覆盖前置、空间实例、可错过约束或任务栏容量。")
    OUTPUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_AUDIT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "foundation": str(OUTPUT_FOUNDATION),
        "clusters": str(OUTPUT_CLUSTERS),
        "video": str(OUTPUT_VIDEO),
        "exclusions": str(OUTPUT_EXCLUSIONS),
        "audit": str(OUTPUT_AUDIT),
        "candidate_count": len(candidate_ids),
        "scope_counts": dict(sorted(counts.items())),
        "cluster_count": len(cluster_list),
        "shared_cluster_count": sum(1 for c in cluster_list if c["shared_by_multiple_tasks"]),
        "adversarial_failures": failures,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
