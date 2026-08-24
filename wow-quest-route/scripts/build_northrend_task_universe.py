from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import effective_quest_rows
from lib.questie_lua import seq
from lib.northrend_execution_review import apply_execution_reviews
from lib.questie_source import load_questie
from lib.wotlk_quest_rewards import base_quest_xp_at_level, max_level_bonus_money
from lib.world_builder import ITEM, QUEST, _ids, _parent_zone, _parse_zone_metadata
from scripts import build_borean_tundra_foundation as shared
from scripts.build_35_55_task_foundation import classify_objectives, classify_task
from scripts.estimate_route_atlas_timing import estimate_foundation_task_service_audit

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
JOURNEY_SOURCE = Path(
    os.environ.get("NORTHREND_JOURNEY_SOURCE", str(ROOT.parent / ".ai-bridge" / "Questie.lua"))
)
OBSERVATIONS = ROOT / "data/observations/fivebox-task-types.json"
OUT = ROOT / "data/route-atlas/northrend-task-universe.json"
EXECUTION_AUDIT_OUT = ROOT / "data/route-atlas/northrend-execution-review.json"
REPORT = ROOT / "docs/analysis/2026-08-18-northrend-task-universe.md"

BLOOD_ELF_FLAG = 512
PALADIN_FLAG = 2
SERVER_XP_MULTIPLIER = 2.0
START_LEVEL = 68
MAX_LEVEL = 80
COLD_WEATHER_FLYING_SPELL_ID = 54197
# Questie explicitly carries requiredSpell=54197 for some Sholazar tasks, but misses several
# WotLK quests whose availability is also gated by having learned Cold Weather Flying.
# Keep those hidden gates as route facts so a no-CWF route can exclude them without confusing
# "can physically reach this with the K3 loaner" with "NPC will actually offer the quest".
COLD_WEATHER_FLYING_HIDDEN_GATE_IDS = {12862, 13060, 13418, 13419}
LEARN_COLD_WEATHER_FLYING = False

KNOWN_REPUTATION_FACTIONS = {
    1104: {"name": "狂心氏族", "branch_group": "sholazar_tribe_choice", "branch_key": "frenzyheart"},
    1105: {"name": "神谕者", "branch_group": "sholazar_tribe_choice", "branch_key": "oracles"},
    1119: {"name": "霍迪尔之子", "branch_group": None, "branch_key": None},
}

KNOWN_PROFILE_VARIANT_OVERRIDES = {
    (12932, 12954): {
        "selected": 12932,
        "variant_kind": "server_current_axis_override",
        "source": "zuldrak_scope_audit_current_axis_uses_12932",
    },
    (24799, 24800, 24801): {
        "selected": 24800,
        "variant_kind": "profile_outcome_variant",
        "source": "blood_elf_paladin_sword_capable_quel_delar_outcome",
    },
}

# Questie variant_components does not catch every normal->daily lifecycle when the localized/title or
# dependency shape differs. These pairs are confirmed as the same first-run content becoming a repeat form.
KNOWN_CALENDAR_LIFECYCLE_GROUPS = [
    (12029, 12038),  # Seared Scourge one-time -> same-location daily burn variant
    (12433, 12434),  # Seeking Solvent -> repeatable Always Seeking Solvent
    (12820, 12833),  # Demolitionist Extraordinaire -> identical Overstock daily mine task
    (12906, 13422),  # Discipline -> identical Maintaining Discipline daily
    (12925, 13425),  # Tradition -> identical Aberrations Must Die daily egg/oil task
    (12971, 13423),  # Taking on All Challengers -> identical Defending Your Title daily
    (12997, 13424),  # Into the Pit -> identical Back to the Pit daily bear combat
    (13420, 13421),  # Everfrost first chip -> repeatable Remember Everfrost turn-in
    (12532, 12702),  # Flown the Coop -> identical Frenzyheart daily Chicken Party
    (12565, 12567),  # The Blessing of Zim'Abwa -> repeatable blessing renewal
    (12572, 12704),  # Gods like Shiny Things -> identical Oracle daily dig-with-companion form
    (11866, 11867),  # Ears of Our Enemies -> repeatable Can't Get Ear-nough turn-in
    (11919, 11940),  # Drake Hunt first capture -> identical daily Drake Hunt
    (12615, 12618),  # The Blessing of Zim'Torga -> repeatable blessing renewal
    (13413, 13414),  # Aces High first training -> identical daily drake combat
    (12655, 12656),  # The Blessing of Zim'Rhuk -> repeatable blessing renewal
    (13092, 13093),  # Reading the Bones: first turn-in -> repeatable turn-in
    (13239, 13261),  # Volatility: one-time -> daily
    (13279, 13281),  # Basic Chemistry -> repeat/daily cauldron version
]

# Current-server/profile facts that cannot be inferred safely from flat Questie rows alone.
MANUAL_LEGACY_TASK_IDS = {
    11189: "removed_howling_fjord_ghost_escort_no_longer_in_game",
    11622: "borean_beta_secrets_of_riplash_removed_before_wrath_live",
    12015: "internal_test_quest_for_craig_not_player_content",
    12021: "dragonblight_manual_foundation_obsolete_beta_row",
    12023: "dragonblight_manual_foundation_obsolete_beta_row",
    12051: "dragonblight_legacy_partial_harpy_row_live_quest_is_12052",
    12490: "borean_beta_quest_never_released_live",
    12601: "legacy_alchemist_apprentice_row_live_troll_patrol_uses_12541",
    12602: "legacy_alchemist_apprentice_row_live_troll_patrol_uses_12541",
    12780: "deprecated_quest_typo_in_source_no_start_or_finish_entity",
    13052: "obsolete_duplicate_aerial_surveillance_live_quest_is_12696",
    13053: "removed_wrath_beta_test_flight_cold_weather_flying_quest",
    13173: "datamined_or_incomplete_legacy_row_no_live_entities_or_xp",
    13175: "datamined_or_incomplete_legacy_row_no_live_entities_or_xp",
    13176: "datamined_or_incomplete_legacy_row_no_live_entities_or_xp",
    13184: "datamined_or_incomplete_legacy_row_no_live_entities_or_xp",
    13481: "legacy_father_kamaros_escort_replaced_by_live_13229",
    24808: "internal_ring_flag_no_player_quest",
    24809: "internal_ring_flag_no_player_quest",
    24810: "internal_ring_flag_no_player_quest",
    24811: "internal_ring_flag_no_player_quest",
    25238: "internal_ring_flag_no_player_quest",
}
MANUAL_ROUTE_POLICY_EXCLUSIONS = {
    11997: "alliance_westfall_brigade_breadcrumb_missing_faction_metadata",
    13234: "requires_killing_alliance_players",
    13417: "alliance_frosthold_bronzebeard_branch_missing_faction_metadata",
    14203: "alliance_waterlogged_recipe_variant_for_current_horde_profile",
}
EXTERNAL_START_CONDITIONS = {
    13372: "focusing_iris_key_must_be_acquired_from_sapphiron_in_naxxramas",
    13375: "heroic_focusing_iris_key_must_be_acquired_from_sapphiron_in_naxxramas",
    13845: "sealed_vial_of_poison_must_come_from_fishing_daily_reward_or_trade",
    24431: "horde_waterlogged_recipe_must_come_from_fishing_daily_reward_or_trade",
    24442: "kvaldir_attack_plans_must_drop_from_hrothgar_kvaldir_before_quest_can_start",
    24554: "battered_hilt_must_be_acquired_from_frozen_halls_or_trade_before_outdoor_chain",
}
SERVER_VERSION_REVIEW_IDS = {
    13374: "bombardment_variant_conflicts_between_current_questie_and_public_wotlk_sources",
}

# Cross-zone continuations can fall outside the Northrend candidate universe. Preserve verified dependency
# edges here so route-policy closure does not incorrectly reopen a later Northrend quest after the chain
# temporarily passes through another continent.
VERIFIED_DEPENDENCY_OVERRIDES = {
    12797: {12548},  # 12548 -> 12547 (Un'Goro) -> 12797; 12547 is outside this universe.
}

DAILY = 4096
WEEKLY = 32768
MONTHLY = 65536
RAID = 64
REPEATABLE = 1

# The Scarlet Enclave is physically on the Northrend map metadata in this client but is the DK start phase,
# not part of a Blood Elf Paladin's Northrend questing universe.
EXCLUDED_OUTDOOR_ZONE_IDS = {4298}
# Stable top-level outdoor task-assignment universe for Northrend. Dalaran/Wintergrasp/Hrothgar
# are retained as Northrend outdoor/reference zones; PvP eligibility is handled per task later.
NORTHREND_OUTDOOR_ZONE_IDS = {495, 3537, 65, 394, 3711, 66, 4395, 210, 67, 4197, 4742}

# Known route-mechanism fact. This is not a global permission exception: the breadcrumb can disappear
# after the Steeljaw battle trio is accepted/completed, so route economics must evaluate it accordingly.
ROUTE_MECHANISM_NOTES = {
    11591: "《钢腭的车队》是可选面包屑；11592/11593/11594可直接接做，之后11591会失去可接资格。当前基线路线不做11591。",
    12177: "《休尼克的掩饰》需要1份煤块和5份面粉；两者都可在征服堡内向商人购买。Questie物品来源展开会把煤块的全世界掉落源带入route_zones，不能因此误判为副本任务。",
}

# Item-source expansion can pollute route zones for vendor/common items. Keep explicit overrides only when
# the quest's real player objective has been independently verified and the generic source expansion is wrong.
DUNGEON_CLASSIFICATION_OVERRIDES = {
    12177: False,
    12930: False,  # Rare Earth is the outdoor Bouldercrag's Refuge chain; generic source expansion falsely marks it dungeon.
    24560: True,  # Tempering the Blade requires the Crucible of Souls inside Forge of Souls.
}


def northrend_outdoor_zone_ids(meta: dict[str, Any]) -> set[int]:
    return set(NORTHREND_OUTDOOR_ZONE_IDS)


def quest_name(data: Any, quest_id: int, row: dict[Any, Any]) -> str:
    return data.local_name(data.quest_names, quest_id, str(row.get(1) or f"Quest {quest_id}"))


def faction_rep_requirement(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    faction_id, value = raw.get(1), raw.get(2)
    if not isinstance(faction_id, int) or not isinstance(value, int):
        return None
    parsed = {"faction_id": int(faction_id), "value": int(value)}
    known = KNOWN_REPUTATION_FACTIONS.get(int(faction_id))
    if known:
        parsed.update(known)
    return parsed


def reputation_rewards(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in seq(raw):
        parsed = faction_rep_requirement(row)
        if parsed:
            out.append(parsed)
    return out


def current_journey_quest_ids(candidate_ids: set[int]) -> tuple[set[int], dict[str, Any]]:
    if JOURNEY_SOURCE.exists():
        summary = shared.summarize_journey(JOURNEY_SOURCE, preview=10000)
        candidates = summary.get("candidates") or []
        if candidates:
            current = candidates[0]
            event_ids = {
                int(event["quest_id"])
                for event in current.get("events_preview", [])
                if isinstance(event.get("quest_id"), int) and event["quest_id"] in candidate_ids
            }
            return event_ids, {
                "mode": "latest_account_journey",
                "source_sha256": summary.get("source_sha256"),
                "matched_event_quest_count": len(event_ids),
                "candidate_event_count": current.get("event_count"),
                "candidate_max_level": current.get("max_level"),
            }
    journey = shared.journey_reference(candidate_ids)
    event_ids = set(journey.get("current", {}).get("event_quest_ids", []))
    return event_ids, {
        "mode": "sanitized_journey_fallback" if journey.get("available") else "unavailable",
        "matched_event_quest_count": len(event_ids),
    }


def reward_items_by_quest(data: Any) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item_id, row in data.items.items():
        if not isinstance(item_id, int) or not isinstance(row, dict):
            continue
        for qid in seq(row.get(6)):
            if not isinstance(qid, int):
                continue
            result[int(qid)].append(
                {
                    "item_id": int(item_id),
                    "name": data.local_name(data.item_names, int(item_id), str(row.get(ITEM["name"]) or f"Item {item_id}")),
                    "item_class": row.get(12),
                    "item_subclass": row.get(13),
                    "item_level": row.get(9),
                    "required_level": row.get(10),
                }
            )
    return result


def route_zones_for_task(data: Any, row: dict[Any, Any], preferred_zone: int, meta: dict[str, Any]) -> tuple[list[int], list[int], list[int], list[int]]:
    start_entities = shared.entity_group(data, row.get(2))
    finish_entities = shared.entity_group(data, row.get(3))
    localized = ""
    # Objective classifier produces source entities with their spawn-zone lists.
    objective_zh = ""
    objective_en = shared.english_objective(row)
    classified, _ = classify_objectives(data, row, preferred_zone, objective_zh or objective_en)
    objective_dicts = [asdict(obj) for obj in classified]
    extra = shared.extract_extra_objectives(data, row, preferred_zone)

    def parentize(zones: list[int]) -> list[int]:
        return sorted({_parent_zone(int(zone), meta["parents"]) for zone in zones if isinstance(zone, int) and zone > 0})

    starts = parentize(shared.entity_zones(start_entities))
    finishes = parentize(shared.entity_zones(finish_entities))
    objectives = parentize(shared.objective_route_zones(objective_dicts, preferred_zone))
    extras = parentize(sorted({int(zone) for item in extra for zone in item.get("route_zones", []) if isinstance(zone, int)}))
    return starts, objectives, extras, finishes


def is_calendar_task(task: dict[str, Any]) -> bool:
    return bool(task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly"))


def blocked_dependency_ids(task: dict[str, Any], blocked: set[int]) -> set[int]:
    pre_any = {int(qid) for qid in (task.get("pre_any") or [])}
    pre_all = {int(qid) for qid in (task.get("pre_all") or [])}
    parent = {int(qid) for qid in (task.get("parent_active") or [])}
    verified = VERIFIED_DEPENDENCY_OVERRIDES.get(int(task["quest_id"]), set())
    blockers = (pre_all | parent | verified) & blocked
    if pre_any and pre_any <= blocked:
        blockers |= pre_any
    return blockers


def custom_eligibility(task: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if not task["race_allowed"]:
        reasons.append("required_races_excludes_blood_elf")
    if not task["class_allowed"]:
        reasons.append("required_classes_excludes_paladin")
    if not task["npc_faction_allowed"]:
        reasons.extend(task["faction_reasons"] or ["npc_faction_not_horde_compatible"])
    if task["required_skill"]:
        reasons.append("requires_profession_or_skill")
    if task["is_deprecated_or_system"]:
        reasons.append("deprecated_or_system_placeholder")
    if not task.get("start_entities") and not task.get("finish_entities") and not task.get("xp", {}).get("has_xp"):
        reasons.append("no_live_start_finish_entities_and_no_xp")
    if task.get("manual_legacy_reason"):
        reasons.append("manual_legacy_or_replaced_task")
    if task.get("manual_route_policy_exclusion_reason"):
        reasons.append("manual_route_policy_excluded")
    if task["cold_weather_flying_gate"] and not LEARN_COLD_WEATHER_FLYING:
        reasons.append("cold_weather_flying_excluded_by_route_policy")
    if task["is_dungeon"] or task["is_raid_flagged"]:
        reasons.append("dungeon_or_raid_excluded")
    if task["pvp"]["is_pvp"] and not task["pvp"]["allowed_by_policy"]:
        reasons.append("pvp_non_mob_excluded_by_policy")
    required_max = task.get("required_max_level")
    if isinstance(required_max, int) and required_max > 0 and required_max < START_LEVEL:
        reasons.append(f"expired_before_level_{START_LEVEL}")
    required_level = task.get("required_level")
    if isinstance(required_level, int) and required_level > MAX_LEVEL:
        reasons.append("requires_above_level_80")
    if reasons:
        return "impossible_or_excluded", sorted(set(reasons))

    condition_reasons: list[str] = []
    if task.get("required_min_rep") or task.get("required_max_rep"):
        condition_reasons.append("reputation_condition_needs_route_state")
    if task.get("available_starting_with"):
        condition_reasons.append("available_starting_with_condition")
    if task.get("disabled_by_quest"):
        condition_reasons.append("disabled_by_quest_condition")
    if task.get("required_spell") or task.get("required_specialization") or task.get("required_ranks"):
        condition_reasons.append("special_character_condition")
    if task.get("external_start_condition"):
        condition_reasons.append("external_item_start_required")
    if task.get("server_version_review_reason"):
        condition_reasons.append("server_version_availability_needs_confirmation")
    if condition_reasons:
        return "conditional", condition_reasons
    return "eligible_first_run", []


def main() -> None:
    data = load_questie(QUESTIE_ZIP)
    meta = _parse_zone_metadata(QUESTIE_ZIP)
    outdoor = northrend_outdoor_zone_ids(meta)

    raw_candidate_ids: set[int] = set()
    for qid, row in data.quests.items():
        if not isinstance(qid, int) or not isinstance(row, dict):
            continue
        raw_zone = row.get(QUEST["zone_or_sort"])
        assigned = _parent_zone(raw_zone, meta["parents"]) if isinstance(raw_zone, int) and raw_zone > 0 else None
        if assigned in outdoor:
            raw_candidate_ids.add(qid)

    effective_rows, correction_audit = effective_quest_rows(data, QUESTIE_ZIP, raw_candidate_ids)
    rewards = reward_items_by_quest(data)
    observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8")) if OBSERVATIONS.exists() else {"tasks": {}}
    latest_seen, journey_audit = current_journey_quest_ids(raw_candidate_ids)

    tasks: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    zone_counts: Counter[str] = Counter()
    level_counts: Counter[int] = Counter()

    for qid in sorted(raw_candidate_ids):
        row = effective_rows.get(qid)
        if not isinstance(row, dict):
            row = data.quests.get(qid)
        if not isinstance(row, dict):
            continue
        assigned = shared.assigned_parent_zone(row, meta["parents"])
        touched = [zone_id for zone_id in sorted(outdoor) if shared.direct_touches_zone(data, row, zone_id)]
        if assigned not in outdoor and not touched:
            continue
        preferred_zone = assigned if assigned in outdoor else touched[0]
        name = quest_name(data, qid, row)
        objective_zh = shared.localized_objective(data, qid)
        objective_en = shared.english_objective(row)
        classified, review = classify_objectives(data, row, preferred_zone, objective_zh or objective_en)
        objective_dicts = [asdict(obj) for obj in classified]
        extra_objectives = shared.extract_extra_objectives(data, row, preferred_zone)
        task_class, task_flags = classify_task(classified, objective_en or objective_zh)
        start_entities = shared.entity_group(data, row.get(2))
        finish_entities = shared.entity_group(data, row.get(3))
        starts, objective_zones, extra_zones, finishes = route_zones_for_task(data, row, preferred_zone, meta)
        all_route_zones = sorted(set(starts + objective_zones + extra_zones + finishes + ([assigned] if assigned else [])))

        race_allowed = shared.bit_allows(row.get(6), BLOOD_ELF_FLAG)
        class_allowed = shared.bit_allows(row.get(7), PALADIN_FLAG)
        npc_allowed, faction_reasons = shared.npc_faction_eligibility(data, row)
        qflags = int(row.get(23) or 0)
        sflags = int(row.get(24) or 0)
        is_repeatable = bool(sflags & REPEATABLE)
        is_daily = bool(qflags & DAILY)
        is_weekly = bool(qflags & WEEKLY)
        is_monthly = bool(qflags & MONTHLY)
        lower_name = name.lower()
        xp_row = data.quest_xp.get(qid)
        xp_level = xp_row.get(1) if isinstance(xp_row, dict) else None
        xp_base = xp_row.get(2) if isinstance(xp_row, dict) else None
        has_xp = isinstance(xp_level, int) and xp_level > 0 and isinstance(xp_base, int) and xp_base > 0
        is_deprecated = "deprecated" in lower_name or "deprecaed" in lower_name or "????" in name or name.strip(" ?") == ""
        is_dungeon = bool(any(zone in meta["dungeons"] for zone in all_route_zones))
        if qid in DUNGEON_CLASSIFICATION_OVERRIDES:
            is_dungeon = bool(DUNGEON_CLASSIFICATION_OVERRIDES[qid])
        pvp = shared.pvp_classification(row, name, objective_en or objective_zh, objective_dicts)
        deps = shared.dependency_ids(row)

        reward_rows = rewards.get(qid, [])
        equipment = [item for item in reward_rows if item.get("item_class") in {1, 2, 4, 11}]
        required_level = row.get(4)
        qlevel = row.get(5)
        earliest_level = max(START_LEVEL, int(required_level or START_LEVEL)) if not isinstance(required_level, int) or required_level <= MAX_LEVEL else int(required_level)
        xp_at_earliest = base_quest_xp_at_level(data, qid, earliest_level) * SERVER_XP_MULTIPLIER if earliest_level <= MAX_LEVEL else 0

        cold_weather_flying_gate = (
            row.get(30) == COLD_WEATHER_FLYING_SPELL_ID
            or qid in COLD_WEATHER_FLYING_HIDDEN_GATE_IDS
        )
        task: dict[str, Any] = {
            "quest_id": qid,
            "name": name,
            "english_name": str(row.get(1) or ""),
            "assigned_zone_id": assigned,
            "assigned_zone_name": meta["zh"].get(meta["names"].get(assigned, ""), meta["names"].get(assigned, "")) if assigned else None,
            "touching_northrend_zone_ids": touched,
            "required_level": required_level,
            "quest_level": qlevel,
            "required_max_level": row.get(32),
            "required_races": row.get(6),
            "required_classes": row.get(7),
            "required_skill": row.get(18),
            "required_min_rep": faction_rep_requirement(row.get(19)),
            "required_max_rep": faction_rep_requirement(row.get(20)),
            "reputation_rewards": reputation_rewards(row.get(26)),
            "required_spell": row.get(30),
            "cold_weather_flying_gate": cold_weather_flying_gate,
            "cold_weather_flying_gate_source": (
                "questie_required_spell_54197"
                if row.get(30) == COLD_WEATHER_FLYING_SPELL_ID
                else ("verified_hidden_gate" if qid in COLD_WEATHER_FLYING_HIDDEN_GATE_IDS else None)
            ),
            "required_specialization": row.get(31),
            "required_ranks": row.get(36),
            "available_starting_with": [int(x) for x in seq(row.get(34)) if isinstance(x, int)],
            "disabled_by_quest": [int(x) for x in seq(row.get(35)) if isinstance(x, int)],
            "quest_flags": qflags,
            "special_flags": sflags,
            "race_allowed": race_allowed,
            "class_allowed": class_allowed,
            "npc_faction_allowed": npc_allowed,
            "faction_reasons": faction_reasons,
            "is_repeatable": is_repeatable,
            "is_daily": is_daily,
            "is_weekly": is_weekly,
            "is_monthly": is_monthly,
            "first_run_policy": "include_first_run_only" if (is_repeatable or is_daily or is_weekly or is_monthly) else "one_time",
            "is_deprecated_or_system": is_deprecated,
            "manual_legacy_reason": MANUAL_LEGACY_TASK_IDS.get(qid),
            "manual_route_policy_exclusion_reason": MANUAL_ROUTE_POLICY_EXCLUSIONS.get(qid),
            "external_start_condition": EXTERNAL_START_CONDITIONS.get(qid),
            "server_version_review_reason": SERVER_VERSION_REVIEW_IDS.get(qid),
            "is_dungeon": is_dungeon,
            "is_raid_flagged": bool(qflags & RAID),
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
            "start_zones": starts,
            "objective_zones": objective_zones,
            "extra_objective_zones": extra_zones,
            "turnin_zones": finishes,
            "all_route_zones": all_route_zones,
            "pre_any": deps["pre_any"],
            "pre_all": deps["pre_all"],
            "parent_active": deps["parent_active"],
            "next_quest": row.get(22),
            "child_quests": [int(x) for x in seq(row.get(14)) if isinstance(x, int)],
            "exclusive_to": [int(x) for x in seq(row.get(16)) if isinstance(x, int)],
            "relevant_exclusive_to": [],
            "unresolved_exclusive_to": [],
            "variant_group": [],
            "variant_kind": None,
            "selected_server_variant": None,
            "selected_first_run_variant": None,
            "breadcrumb_for": row.get(27),
            "breadcrumbs": [int(x) for x in seq(row.get(28)) if isinstance(x, int)],
            "xp": {
                "has_xp": has_xp,
                "xp_db_level": xp_level,
                "xp_db_base": xp_base,
                "server_leveling_multiplier": SERVER_XP_MULTIPLIER,
                "server_xp_at_earliest_route_level": int(xp_at_earliest),
                "max_level_bonus_money": max_level_bonus_money(data, qid, qflags),
            },
            "rewards": {
                "equipment_rewards": equipment,
                "other_reward_items": [item for item in reward_rows if item not in equipment],
                "direct_money_status": "not_yet_globally_audited",
            },
            "route_mechanism_note": ROUTE_MECHANISM_NOTES.get(qid),
        }
        status, reasons = custom_eligibility(task)
        task["eligibility"] = {"status": status, "reasons": reasons}
        task["availability_dependency_blockers"] = []
        task["intrinsic_service_time"] = estimate_foundation_task_service_audit(task, observations)

        tasks.append(task)
        status_counts[status] += 1
        zone_counts[str(task["assigned_zone_name"] or "跨区/未知")] += 1
        if isinstance(required_level, int):
            level_counts[required_level] += 1

    policy_blocked = {
        int(task["quest_id"])
        for task in tasks
        if "cold_weather_flying_excluded_by_route_policy" in task["eligibility"]["reasons"]
        and task["race_allowed"]
        and task["class_allowed"]
        and task["npc_faction_allowed"]
    }
    changed = True
    while changed:
        changed = False
        for task in tasks:
            qid = int(task["quest_id"])
            if qid in policy_blocked:
                continue
            if not task["race_allowed"] or not task["class_allowed"] or not task["npc_faction_allowed"]:
                continue
            blockers = blocked_dependency_ids(task, policy_blocked)
            if not blockers:
                continue
            task["availability_dependency_blockers"] = sorted(blockers)
            task["eligibility"] = {
                "status": "impossible_or_excluded",
                "reasons": sorted(set(task["eligibility"]["reasons"] + ["dependency_on_route_policy_excluded_quest"])),
            }
            policy_blocked.add(qid)
            changed = True

    by_id = {int(task["quest_id"]): task for task in tasks}
    variant_groups = shared.variant_components(by_id)
    existing_variant_ids = {qid for group in variant_groups for qid in group}
    for manual_group in KNOWN_CALENDAR_LIFECYCLE_GROUPS:
        if all(qid in by_id for qid in manual_group) and not (set(manual_group) & existing_variant_ids):
            variant_groups.append(list(manual_group))
            existing_variant_ids.update(manual_group)
    variant_audit: list[dict[str, Any]] = []
    for group in variant_groups:
        viable = [qid for qid in group if by_id[qid]["eligibility"]["status"] != "impossible_or_excluded"]
        observed = [qid for qid in viable if qid in latest_seen]
        calendar_viable = [qid for qid in viable if is_calendar_task(by_id[qid])]
        one_time_viable = [qid for qid in viable if not is_calendar_task(by_id[qid])]
        selected_server: int | None = None
        selected_first_run: int | None = None
        selection_source: str | None = None
        group_set = set(group)
        override = next(
            (
                value
                for key, value in KNOWN_PROFILE_VARIANT_OVERRIDES.items()
                if set(key).issubset(group_set) and int(value["selected"]) in group_set
            ),
            None,
        )

        if override and int(override["selected"]) in viable:
            selected_first_run = int(override["selected"])
            variant_kind = str(override["variant_kind"])
            selection_source = str(override["source"])
            if variant_kind == "server_current_axis_override":
                selected_server = selected_first_run
            for qid in viable:
                if qid == selected_first_run:
                    continue
                task = by_id[qid]
                task["eligibility"] = {
                    "status": "impossible_or_excluded",
                    "reasons": sorted(set(task["eligibility"]["reasons"] + [f"profile_variant_selected_{selected_first_run}"])),
                }
        elif len(viable) <= 1:
            variant_kind = "profile_resolved"
            selected_first_run = viable[0] if viable else None
        elif calendar_viable and one_time_viable:
            variant_kind = "normal_calendar_lifecycle"
            observed_one_time = [qid for qid in one_time_viable if qid in latest_seen]
            if len(one_time_viable) == 1:
                selected_first_run = one_time_viable[0]
            elif len(observed_one_time) == 1:
                selected_first_run = observed_one_time[0]
                selected_server = observed_one_time[0]
            for qid in calendar_viable:
                task = by_id[qid]
                task["eligibility"] = {
                    "status": "impossible_or_excluded",
                    "reasons": sorted(set(task["eligibility"]["reasons"] + ["calendar_repeat_form_not_separate_first_run_card"])),
                }
            unresolved_one_time = [qid for qid in one_time_viable if qid != selected_first_run]
            if selected_first_run is not None:
                for qid in unresolved_one_time:
                    task = by_id[qid]
                    task["eligibility"] = {
                        "status": "impossible_or_excluded",
                        "reasons": sorted(set(task["eligibility"]["reasons"] + [f"same_server_observed_variant_is_{selected_first_run}"])),
                    }
            elif len(one_time_viable) > 1:
                for qid in one_time_viable:
                    task = by_id[qid]
                    task["eligibility"] = {
                        "status": "conditional",
                        "reasons": sorted(set(task["eligibility"]["reasons"] + ["server_variant_needs_confirmation"])),
                    }
        elif calendar_viable:
            variant_kind = "calendar_rotation"
            for qid in viable:
                task = by_id[qid]
                task["eligibility"] = {
                    "status": "conditional",
                    "reasons": sorted(set(task["eligibility"]["reasons"] + ["calendar_rotation_condition"])),
                }
        else:
            variant_kind = "server_or_same_title_one_time_variant"
            if len(observed) == 1:
                selected_server = observed[0]
                selected_first_run = observed[0]
                for qid in viable:
                    if qid == selected_server:
                        continue
                    task = by_id[qid]
                    task["eligibility"] = {
                        "status": "impossible_or_excluded",
                        "reasons": sorted(set(task["eligibility"]["reasons"] + [f"same_server_observed_variant_is_{selected_server}"])),
                    }
            else:
                for qid in viable:
                    task = by_id[qid]
                    task["eligibility"] = {
                        "status": "conditional",
                        "reasons": sorted(set(task["eligibility"]["reasons"] + ["server_variant_needs_confirmation"])),
                    }

        for qid in group:
            task = by_id[qid]
            task["variant_group"] = group
            task["variant_kind"] = variant_kind
            task["selected_server_variant"] = (qid == selected_server) if selected_server is not None else None
            task["selected_first_run_variant"] = (qid == selected_first_run) if selected_first_run is not None else None

        variant_audit.append(
            {
                "quest_ids": group,
                "variant_kind": variant_kind,
                "observed_current": observed,
                "profile_viable_before_variant_resolution": viable,
                "calendar_viable": calendar_viable,
                "one_time_viable": one_time_viable,
                "selected_server_variant": selected_server,
                "selected_first_run_variant": selected_first_run,
                "selection_source": selection_source,
            }
        )

    # Calendar lifecycle is orthogonal to faction/server variants. Apply known normal->daily relations
    # even when either quest already belongs to another variant component (e.g. Horde/Alliance mirrors).
    audited_lifecycle_groups = {
        tuple(row["quest_ids"])
        for row in variant_audit
        if row["variant_kind"] == "normal_calendar_lifecycle"
    }
    for lifecycle_group in KNOWN_CALENDAR_LIFECYCLE_GROUPS:
        if not all(qid in by_id for qid in lifecycle_group):
            continue
        first_run = int(lifecycle_group[0])
        repeats = [int(qid) for qid in lifecycle_group[1:]]
        for qid in lifecycle_group:
            task = by_id[int(qid)]
            task["calendar_lifecycle_group"] = list(lifecycle_group)
            task["calendar_lifecycle_first_run"] = int(qid) == first_run
        for qid in repeats:
            task = by_id[qid]
            if task["eligibility"]["status"] != "impossible_or_excluded":
                task["eligibility"] = {
                    "status": "impossible_or_excluded",
                    "reasons": sorted(set(task["eligibility"]["reasons"] + ["calendar_repeat_form_not_separate_first_run_card"])),
                }
        if tuple(lifecycle_group) not in audited_lifecycle_groups:
            variant_audit.append(
                {
                    "quest_ids": list(lifecycle_group),
                    "variant_kind": "normal_calendar_lifecycle",
                    "observed_current": [qid for qid in lifecycle_group if qid in latest_seen],
                    "profile_viable_before_variant_resolution": list(lifecycle_group),
                    "calendar_viable": repeats,
                    "one_time_viable": [first_run],
                    "selected_server_variant": None,
                    "selected_first_run_variant": first_run,
                    "selection_source": "manual_calendar_lifecycle_override",
                }
            )

    hard_blocked = {
        int(task["quest_id"])
        for task in tasks
        if task["eligibility"]["status"] == "impossible_or_excluded"
    }
    changed = True
    while changed:
        changed = False
        for task in tasks:
            qid = int(task["quest_id"])
            if qid in hard_blocked:
                continue
            blockers = blocked_dependency_ids(task, hard_blocked)
            if not blockers:
                continue
            task["availability_dependency_blockers"] = sorted(
                set(task.get("availability_dependency_blockers") or []) | blockers
            )
            task["eligibility"] = {
                "status": "impossible_or_excluded",
                "reasons": sorted(set(task["eligibility"]["reasons"] + ["dependency_on_excluded_quest"])),
            }
            hard_blocked.add(qid)
            changed = True

    for row in variant_audit:
        row["profile_viable_after_dependency_closure"] = [
            qid
            for qid in row["quest_ids"]
            if by_id[qid]["eligibility"]["status"] != "impossible_or_excluded"
        ]

    for task in tasks:
        if task["eligibility"]["status"] == "impossible_or_excluded":
            continue
        raw_exclusive = [int(qid) for qid in task.get("exclusive_to") or []]
        relevant = [
            qid
            for qid in raw_exclusive
            if qid in by_id and by_id[qid]["eligibility"]["status"] != "impossible_or_excluded"
        ]
        unresolved = [qid for qid in raw_exclusive if qid not in by_id]
        task["relevant_exclusive_to"] = sorted(relevant)
        task["unresolved_exclusive_to"] = sorted(unresolved)
        extra_reasons: list[str] = []
        if relevant:
            extra_reasons.append("exclusive_availability_condition")
        if extra_reasons:
            task["eligibility"] = {
                "status": "conditional",
                "reasons": sorted(set(task["eligibility"]["reasons"] + extra_reasons)),
            }

    status_counts = Counter(task["eligibility"]["status"] for task in tasks)
    raw_rows_for_execution_review = {
        int(task["quest_id"]): (
            effective_rows.get(int(task["quest_id"]))
            if isinstance(effective_rows.get(int(task["quest_id"])), dict)
            else data.quests.get(int(task["quest_id"]), {})
        )
        for task in tasks
    }
    execution_review_audit = apply_execution_reviews(ROOT, tasks, raw_rows_for_execution_review)

    payload = {
        "schema_version": 1,
        "status": "NORTHREND_TASK_CARD_UNIVERSE",
        "profile": "blood-elf-paladin",
        "start_level": START_LEVEL,
        "max_level": MAX_LEVEL,
        "questie_version": data.version,
        "source_sha256": data.source_sha256,
        "rules": {
            "dungeon_and_raid": "excluded from outdoor route but retained as excluded task cards",
            "repeatable_daily_weekly_monthly": "first run may be eligible; no second-run generation by default",
            "task_selection_policy": "no level-based all-clear or speed-only deletion; compare do-now / do-later / never-do by impact on this quest-cycle total gold, total wall-clock, and gold-per-hour; do not import raid/daily opportunity cost",
            "cold_weather_flying": {
                "learned_by_route_profile": LEARN_COLD_WEATHER_FLYING,
                "rule": "learned-skill gates and quests exclusively dependent on them are excluded; physical flight alone is not a gate because the K3 loaner can cover travel",
            },
            "route_mechanism_notes": ROUTE_MECHANISM_NOTES,
            "max_level_gold": "Quest::XPValue(80) * 6 copper; base WotLK XP, no 2x leveling multiplier",
        },
        "correction_audit": correction_audit,
        "journey_audit": journey_audit,
        "server_variant_audit": variant_audit,
        "execution_review_summary": {
            key: value
            for key, value in execution_review_audit.items()
            if key != "review_queue"
        },
        "summary": {
            "task_card_count": len(tasks),
            "eligibility_counts": dict(status_counts),
            "assigned_zone_counts": dict(sorted(zone_counts.items())),
            "required_level_counts": {str(k): v for k, v in sorted(level_counts.items())},
            "route_policy_blocked_count": len(policy_blocked),
            "route_policy_blocked_ids": sorted(policy_blocked),
            "same_title_variant_group_count": len(variant_audit),
            "server_variant_selected_group_count": sum(
                1
                for row in variant_audit
                if row["selected_server_variant"] is not None
                and row["selected_server_variant"] in row["profile_viable_after_dependency_closure"]
            ),
            "server_variant_unresolved_profile_group_count": sum(
                1
                for row in variant_audit
                if row["variant_kind"] == "server_or_same_title_one_time_variant"
                and row["selected_server_variant"] is None
                and len(set(row["one_time_viable"]) & set(row["profile_viable_after_dependency_closure"])) > 1
            ),
            "normal_calendar_lifecycle_group_count": sum(
                1 for row in variant_audit if row["variant_kind"] == "normal_calendar_lifecycle"
            ),
            "calendar_rotation_group_count": sum(
                1 for row in variant_audit if row["variant_kind"] == "calendar_rotation"
            ),
            "dependency_blocked_count": sum(
                1 for task in tasks if "dependency_on_excluded_quest" in task["eligibility"]["reasons"]
            ),
            "availability_constraint_counts": {
                "required_reputation": sum(1 for t in tasks if t.get("required_min_rep") or t.get("required_max_rep")),
                "exclusive_to": sum(1 for t in tasks if t.get("exclusive_to")),
                "available_starting_with": sum(1 for t in tasks if t.get("available_starting_with")),
                "disabled_by_quest": sum(1 for t in tasks if t.get("disabled_by_quest")),
                "required_skill": sum(1 for t in tasks if t.get("required_skill")),
                "required_spell_or_specialization": sum(1 for t in tasks if t.get("required_spell") or t.get("required_specialization") or t.get("required_ranks")),
                "repeatable": sum(1 for t in tasks if t.get("is_repeatable")),
                "daily": sum(1 for t in tasks if t.get("is_daily")),
                "weekly": sum(1 for t in tasks if t.get("is_weekly")),
                "monthly": sum(1 for t in tasks if t.get("is_monthly")),
            },
            "task_service_estimated_count": sum(1 for t in tasks if t["intrinsic_service_time"]["status"] == "estimated"),
            "task_service_unknown_count": sum(1 for t in tasks if t["intrinsic_service_time"]["status"] != "estimated"),
            "execution_review_status_counts": execution_review_audit["status_counts"],
            "execution_review_queue_count": execution_review_audit["eligible_review_queue_count"],
            "execution_review_high_signal_count": execution_review_audit["eligible_high_signal_review_count"],
            "execution_review_low_signal_count": execution_review_audit["eligible_low_signal_review_count"],
            "execution_review_queue_by_zone": execution_review_audit["eligible_review_queue_by_zone"],
            "execution_confirmed_nonflat_count": execution_review_audit["spatial_status_counts"].get("confirmed_non_flat_or_special_access", 0),
        },
        "tasks": tasks,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EXECUTION_AUDIT_OUT.write_text(
        json.dumps(execution_review_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    eligible = [t for t in tasks if t["eligibility"]["status"] == "eligible_first_run"]
    conditional = [t for t in tasks if t["eligibility"]["status"] == "conditional"]
    excluded = [t for t in tasks if t["eligibility"]["status"] == "impossible_or_excluded"]
    lines = [
        "# 诺森德全任务卡宇宙（血精灵圣骑士）",
        "",
        f"- Questie：{data.version}",
        f"- 总任务卡：{len(tasks)}",
        f"- 第一轮直接可做：{len(eligible)}",
        f"- 条件待路线状态确认：{len(conditional)}",
        f"- 当前角色/户外规则排除：{len(excluded)}",
        f"- 已有任务自身服务时间：{payload['summary']['task_service_estimated_count']}；仍需专项机制估时：{payload['summary']['task_service_unknown_count']}。",
        f"- 当前不学寒冷天气飞行策略直接/递归阻断：{payload['summary']['route_policy_blocked_count']}张。",
        f"- 同名候选组：{payload['summary']['same_title_variant_group_count']}；Journey已选定服务器一次性版本{payload['summary']['server_variant_selected_group_count']}组；普通→日常生命周期组{payload['summary']['normal_calendar_lifecycle_group_count']}组；日常轮换组{payload['summary']['calendar_rotation_group_count']}组；仍有{payload['summary']['server_variant_unresolved_profile_group_count']}组一次性服务器版本待确认。",
        f"- 人类可执行性/隐藏机制：已明确需要备注{payload['summary']['execution_review_status_counts'].get('reviewed_note_required', 0)}张、已明确无需额外备注{payload['summary']['execution_review_status_counts'].get('reviewed_no_extra_note', 0)}张；当前仍可能入线但待审{payload['summary']['execution_review_queue_count']}张，其中高风险信号{payload['summary']['execution_review_high_signal_count']}张。",
        f"- 已确认存在洞穴/楼层/上下层/水下/悬崖/脚本交通等非平面执行约束：{payload['summary']['execution_confirmed_nonflat_count']}张。所有未完成人工执行审计的任务默认禁止仅凭平面坐标自动判定顺路。",
        "- 每张卡已固定80级XP折金字段；与练级期直接金币分开。",
        "- 11591《钢腭的车队》是当前唯一用户明确批准可自然消失的单任务例外；不得类推。",
        "",
        "## 区域卡数",
        "",
    ]
    for zone, count in sorted(zone_counts.items(), key=lambda item: item[0]):
        lines.append(f"- {zone}: {count}")

    lines.extend(["", "## 人类可执行性 / 空间风险待审", ""])
    lines.append("- `reviewed_note_required`：已查清特殊完成方式，后续玩家任务备注必须复用这些事实。")
    lines.append("- `reviewed_no_extra_note`：已人工审过，任务名 + 正常目标定位足够，不强行写废话备注。")
    lines.append("- `review_required_*`：尚未完成这一层人工审计；无论平面坐标多近，路线层都不得据此自动判定真实顺路。")
    for zone, counts in payload["summary"]["execution_review_queue_by_zone"].items():
        lines.append(
            f"- {zone}：待审{counts.get('total', 0)}；高风险{counts.get('high_signal', 0)}；低信号{counts.get('low_signal', 0)}。"
        )
    lines.append(f"- 完整待审队列：`{EXECUTION_AUDIT_OUT.relative_to(ROOT)}`。")

    lines.extend(["", "## 条件任务", ""])
    for task in conditional:
        details: list[str] = []
        if task.get("required_min_rep"):
            rep = task["required_min_rep"]
            faction = rep.get("name") or rep["faction_id"]
            details.append(f"minRep={faction}:{rep['value']}")
            if rep.get("branch_group"):
                details.append(f"branch={rep['branch_group']}:{rep['branch_key']}")
        if task.get("required_max_rep"):
            rep = task["required_max_rep"]
            faction = rep.get("name") or rep["faction_id"]
            details.append(f"maxRep={faction}:{rep['value']}")
        if task.get("available_starting_with"):
            details.append(f"availableStartingWith={task['available_starting_with']}")
        if task.get("disabled_by_quest"):
            details.append(f"disabledBy={task['disabled_by_quest']}")
        if task.get("relevant_exclusive_to"):
            details.append(f"exclusiveTo={task['relevant_exclusive_to']}")
        if task.get("unresolved_exclusive_to"):
            details.append(f"externalExclusiveTo={task['unresolved_exclusive_to']}")
        if task.get("required_spell"):
            details.append(f"requiredSpell={task['required_spell']}")
        suffix = f"；{'；'.join(details)}" if details else ""
        lines.append(f"- {task['quest_id']}《{task['name']}》 req={task['required_level']}：{', '.join(task['eligibility']['reasons'])}{suffix}")

    lines.extend(["", "## 尚未由当前Journey选定的一次性服务器版本组", ""])
    unresolved_variant_rows = [
        row
        for row in variant_audit
        if row["variant_kind"] == "server_or_same_title_one_time_variant"
        and row["selected_server_variant"] is None
        and len(set(row["one_time_viable"]) & set(row["profile_viable_after_dependency_closure"])) > 1
    ]
    if not unresolved_variant_rows:
        lines.append("- 无。")
    for row in unresolved_variant_rows:
        viable_after = set(row["profile_viable_after_dependency_closure"])
        peers = [by_id[qid] for qid in row["one_time_viable"] if qid in viable_after]
        peer_text = " / ".join(f"{task['quest_id']}《{task['name']}》" for task in peers)
        lines.append(f"- {peer_text}")

    lines.extend(["", "## 普通任务 → 日常/重复生命周期组", ""])
    lifecycle_rows = [row for row in variant_audit if row["variant_kind"] == "normal_calendar_lifecycle"]
    if not lifecycle_rows:
        lines.append("- 无。")
    for row in lifecycle_rows:
        selected = row["selected_first_run_variant"]
        calendar_text = ", ".join(str(qid) for qid in row["calendar_viable"])
        lines.append(f"- 首轮={selected}《{by_id[selected]['name']}》；后续日常/重复ID=[{calendar_text}]")

    lines.extend(["", "## 日常轮换同名组", ""])
    rotation_rows = [row for row in variant_audit if row["variant_kind"] == "calendar_rotation"]
    if not rotation_rows:
        lines.append("- 无。")
    for row in rotation_rows:
        peers = [by_id[qid] for qid in row["calendar_viable"]]
        peer_text = " / ".join(f"{task['quest_id']}《{task['name']}》" for task in peers)
        lines.append(f"- {peer_text}")

    lines.extend(["", "## 技能 / 法术 Availability 门槛", ""])
    skill_spell_tasks = [
        task for task in tasks
        if task.get("required_skill") or task.get("required_spell") or task.get("required_specialization") or task.get("required_ranks")
    ]
    if not skill_spell_tasks:
        lines.append("- 无。")
    for task in skill_spell_tasks:
        lines.append(
            f"- {task['quest_id']}《{task['name']}》：skill={task.get('required_skill')}；"
            f"spell={task.get('required_spell')}；specialization={task.get('required_specialization')}；"
            f"ranks={task.get('required_ranks')}；status={task['eligibility']['status']}；"
            f"reasons={task['eligibility']['reasons']}"
        )

    counts = payload["summary"]["availability_constraint_counts"]
    lines.extend([
        "",
        "## 日常 / 重复版本统计",
        "",
        f"- repeatable={counts['repeatable']}；daily={counts['daily']}；weekly={counts['weekly']}；monthly={counts['monthly']}。",
        "- 宇宙层只生成首轮任务卡，不生成第二轮循环；同名版本由server_variant_audit单独去重/待确认。",
    ])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
