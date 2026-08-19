from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import effective_quest_rows
from lib.questie_lua import seq
from lib.questie_source import load_questie
from lib.wotlk_quest_rewards import base_quest_xp_at_level, max_level_bonus_money
from lib.world_builder import ITEM, QUEST, _ids, _parent_zone, _parse_zone_metadata
from scripts import build_borean_tundra_foundation as shared
from scripts.build_35_55_task_foundation import classify_objectives, classify_task
from scripts.estimate_route_atlas_timing import estimate_foundation_task_service_audit

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
OBSERVATIONS = ROOT / "data/observations/fivebox-task-types.json"
OUT = ROOT / "data/route-atlas/northrend-task-universe.json"
REPORT = ROOT / "docs/analysis/2026-08-18-northrend-task-universe.md"

BLOOD_ELF_FLAG = 512
PALADIN_FLAG = 2
SERVER_XP_MULTIPLIER = 2.0
START_LEVEL = 68
MAX_LEVEL = 80

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
}


def northrend_outdoor_zone_ids(meta: dict[str, Any]) -> set[int]:
    return set(NORTHREND_OUTDOOR_ZONE_IDS)


def quest_name(data: Any, quest_id: int, row: dict[Any, Any]) -> str:
    return data.local_name(data.quest_names, quest_id, str(row.get(1) or f"Quest {quest_id}"))


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
            "required_min_rep": row.get(19),
            "required_max_rep": row.get(20),
            "required_spell": row.get(30),
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
        task["intrinsic_service_time"] = estimate_foundation_task_service_audit(task, observations)

        tasks.append(task)
        status_counts[status] += 1
        zone_counts[str(task["assigned_zone_name"] or "跨区/未知")] += 1
        if isinstance(required_level, int):
            level_counts[required_level] += 1

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
            "route_mechanism_notes": ROUTE_MECHANISM_NOTES,
            "max_level_gold": "Quest::XPValue(80) * 6 copper; base WotLK XP, no 2x leveling multiplier",
        },
        "correction_audit": correction_audit,
        "summary": {
            "task_card_count": len(tasks),
            "eligibility_counts": dict(status_counts),
            "assigned_zone_counts": dict(sorted(zone_counts.items())),
            "required_level_counts": {str(k): v for k, v in sorted(level_counts.items())},
            "task_service_estimated_count": sum(1 for t in tasks if t["intrinsic_service_time"]["status"] == "estimated"),
            "task_service_unknown_count": sum(1 for t in tasks if t["intrinsic_service_time"]["status"] != "estimated"),
        },
        "tasks": tasks,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
        "- 每张卡已固定80级XP折金字段；与练级期直接金币分开。",
        "- 11591《钢腭的车队》是当前唯一用户明确批准可自然消失的单任务例外；不得类推。",
        "",
        "## 区域卡数",
        "",
    ]
    for zone, count in sorted(zone_counts.items(), key=lambda item: item[0]):
        lines.append(f"- {zone}: {count}")
    lines.extend(["", "## 条件任务", ""])
    for task in conditional:
        lines.append(f"- {task['quest_id']}《{task['name']}》 req={task['required_level']}：{', '.join(task['eligibility']['reasons'])}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
