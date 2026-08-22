from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_lua import seq
from lib.questie_source import load_questie
from lib.wotlk_quest_rewards import max_level_bonus_money
from lib.world_builder import _ids, _parse_zone_metadata
from scripts import build_borean_tundra_foundation as shared
from scripts.build_35_55_task_foundation import classify_objectives, classify_task, quest_xp_at_level

ZONE_ID = 65
ZONE_NAME = "龙骨荒野"
ZONE_CONSTANT = "DRAGONBLIGHT"
ENTRY_LEVEL = 71
FIRST_PASS_MAX_REQUIRED_LEVEL = 74
BLOOD_ELF_FLAG = 512
PALADIN_FLAG = 2
QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
VIDEO_ROOT = ROOT.parent / ".ai-bridge" / "wow-video-extraction"

OUT_FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT_CLUSTERS = ROOT / "data/route-atlas/dragonblight-target-clusters.json"
OUT_VIDEO = ROOT / "data/route-atlas/dragonblight-video-reference.json"
OUT_MECHANICS = ROOT / "data/route-atlas/dragonblight-special-mechanism-audit.json"
OUT_AUDIT = ROOT / "docs/archive/analysis/2026-08-16-dragonblight-foundation-audit.md"
OVERRIDES_FILE = ROOT / "data/route-atlas/dragonblight-task-overrides.json"

DAILY = 4096
WEEKLY = 32768
MONTHLY = 65536
REPEATABLE = 1
RAID = 64


def configure_shared() -> None:
    shared.ZONE_ID = ZONE_ID
    shared.START_LEVEL = ENTRY_LEVEL
    shared.NATURAL_FIRST_PASS_MAX_REQUIRED_LEVEL = FIRST_PASS_MAX_REQUIRED_LEVEL
    shared.QUESTIE_ZIP = QUESTIE_ZIP


def candidate_union(data: Any, meta: dict[str, Any]) -> tuple[set[int], dict[str, list[int]]]:
    assigned: set[int] = set()
    touching: set[int] = set()
    for quest_id, row in data.quests.items():
        if not isinstance(quest_id, int) or not isinstance(row, dict):
            continue
        if shared.assigned_parent_zone(row, meta["parents"]) == ZONE_ID:
            assigned.add(quest_id)
        if shared.direct_touches_zone(data, row, ZONE_ID):
            touching.add(quest_id)
    corrections = shared.correction_zone_hints(QUESTIE_ZIP, ZONE_CONSTANT)
    return assigned | touching | corrections, {
        "raw_assigned": sorted(assigned),
        "raw_touches": sorted(touching),
        "correction_zone_hints": sorted(corrections),
    }


def xp_facts(data: Any, quest_id: int, row: dict[Any, Any]) -> dict[str, Any]:
    db = data.quest_xp.get(quest_id)
    db_level = db.get(1) if isinstance(db, dict) else None
    db_base = db.get(2) if isinstance(db, dict) else None
    has_xp = isinstance(db_level, int) and db_level > 0 and isinstance(db_base, int) and db_base > 0
    qlevel = row.get(5)
    return {
        "has_xp": has_xp,
        "xp_db_level": db_level,
        "xp_db_base": db_base,
        "server_multiplier": 2,
        "server_xp_at_entry_level": quest_xp_at_level(data, quest_id, ENTRY_LEVEL) if has_xp else 0,
        "full_xp_through_level": int(qlevel) + 5 if isinstance(qlevel, int) and qlevel > 0 else None,
        "max_level_bonus_money": max_level_bonus_money(data, quest_id, row.get(23)),
    }


def initial_scope(task: dict[str, Any]) -> tuple[str, list[str]]:
    if not task["is_primary_candidate"]:
        kinds = task["boundary_reference_kinds"]
        if kinds == ["prerequisite"]:
            return "boundary_prerequisite_reference", ["one_hop_dependency"]
        if kinds == ["followup"]:
            return "boundary_followup_reference", ["one_hop_followup"]
        return "boundary_mixed_reference", ["one_hop_boundary"]
    if not task["race_allowed"] or not task["npc_faction_allowed"]:
        return "exclude_alliance_or_other_faction", task["faction_reasons"] or ["horde_blood_elf_not_allowed"]
    if not task["class_allowed"]:
        return "exclude_other_class", ["paladin_not_allowed"]
    if task["required_skill"]:
        return "exclude_profession", ["requires_skill_or_profession"]
    if task["is_deprecated_or_system"]:
        return "exclude_deprecated_or_system", ["deprecated_placeholder_or_system"]
    if task["is_repeatable"]:
        return "exclude_repeatable_calendar", ["not_one_time_clearable"]
    if task["pvp"]["is_pvp"] and not task["pvp"]["allowed_by_policy"]:
        return "exclude_pvp_non_mob", ["requires_pvp_interaction"]
    required_level = task["required_level"]
    if isinstance(required_level, int) and required_level > FIRST_PASS_MAX_REQUIRED_LEVEL:
        return "defer_future_level_revisit", [f"required_level_{required_level}_above_first_pass_window"]
    if not task["xp"]["has_xp"]:
        return "exclude_no_xp_pending_dependency_audit", ["no_quest_xp"]
    if task["is_dungeon"]:
        return "include_leveling_dungeon", ["one_time_xp_dungeon_task_separate_block"]
    if task["is_cross_map"]:
        return "include_leveling_cross_map", ["cross_map_touch"]
    return "include_leveling_local", ["one_time_xp_horde_paladin_task"]


def parse_video(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    documents: dict[int, list[str]] = {}
    for episode in (40, 41, 42):
        path = VIDEO_ROOT / f"episode-{episode}-extraction.md"
        if path.exists():
            documents[episode] = path.read_text(encoding="utf-8").splitlines()
    payload: dict[str, Any] = {
        "policy": "Alliance single-character evidence: location/mechanism only; never proves Horde ID, fivebox sharing, or fivebox timing.",
        "episodes": {str(ep): str((VIDEO_ROOT / f"episode-{ep}-extraction.md").relative_to(ROOT.parent)) for ep in documents},
        "tasks": {},
    }
    for task in tasks:
        qid = task["quest_id"]
        name = str(task["name"] or "").strip()
        matches: list[dict[str, Any]] = []
        for episode, lines in documents.items():
            for line_no, line in enumerate(lines, start=1):
                exact_id = bool(re.search(rf"(?<!\d){qid}(?!\d)", line))
                same_name = bool(name and len(name) >= 3 and name in line)
                if exact_id or same_name:
                    matches.append({
                        "episode": episode,
                        "line": line_no,
                        "match": "exact_id" if exact_id else "same_localized_name",
                        "text": line.strip()[:320],
                    })
                    if len(matches) >= 8:
                        break
            if len(matches) >= 8:
                break
        payload["tasks"][str(qid)] = {
            "matches": matches,
            "episodes": sorted({m["episode"] for m in matches}),
            "has_exact_id_evidence": any(m["match"] == "exact_id" for m in matches),
            "has_same_name_counterpart_evidence": any(m["match"] == "same_localized_name" for m in matches),
        }
    return payload


def empty_note(decision: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "decision": decision,
        "reasons": reasons,
        "verification_needed": [],
        "video_evidence_available": False,
        "unresolved_after_local_evidence": [],
    }


def note_audit(task: dict[str, Any], video: dict[str, Any]) -> dict[str, Any]:
    status = task["scope_status"]
    if not status.startswith("include_") and status != "defer_future_level_revisit":
        return empty_note("not_route_candidate", [status])
    if task["is_dungeon"]:
        return empty_note("not_route_candidate", ["dungeon_block_kept_outside_world_route"])

    reasons: list[str] = []
    verification: list[str] = []
    if task["item_start_ids"]:
        reasons.append("item_trigger_source_must_be_explained")
        verification.append("trigger_drop_source_and_fivebox_loot_mode")
    if task["extra_objectives"]:
        reasons.append("questie_extra_objective_or_script_anchor")
        verification.append("scripted_action_and_exact_player_input")
    if any(obj.get("objective_type") == "event" for obj in task["objectives"]):
        reasons.append("scripted_event_or_area_trigger")
        verification.append("trigger_location_and_completion_condition")
    if "active_item_or_spell_use" in task["task_flags"]:
        reasons.append("active_item_or_spell_use")
        verification.append("which_item_or_spell_and_target")
    if "escort_or_defense_text" in task["task_flags"]:
        reasons.append("escort_or_defense")
        verification.append("escort_start_failure_and_group_completion")
    if task["task_class"] == "scripted_use_or_event":
        reasons.append("scripted_use_or_event")
    if task["task_class"] in {"fixed_object_interaction", "world_object_collection", "world_object_item_collection"}:
        reasons.append("fixed_world_object_interaction")
        verification.append("fivebox_shared_vs_personal_object_state")
    if task["special_flags"] & 2 and task["task_class"] == "travel_dialogue_or_turnin":
        reasons.append("scripted_or_auto_complete_dialogue_without_normal_objective")
        verification.append("actual_script_vehicle_dialogue_sequence")
    if task["objective_review"]:
        reasons.extend(f"objective_review:{value}" for value in task["objective_review"])
        verification.append("objective_semantics")
    if task["task_class"] in {"single_named_drop", "single_creature_drop", "multi_creature_personal_drop", "mixed_with_personal_item"}:
        verification.append("fivebox_loot_mode_and_drop_variance")
    if task["is_cross_map"]:
        verification.append("transport_and_natural_handoff")

    reasons = sorted(set(reasons))
    verification = sorted(set(verification))
    decision = "must_note" if reasons else "review_before_route" if verification else "no_extra_note"
    vref = video["tasks"].get(str(task["quest_id"]), {})
    has_video = bool(vref.get("matches"))
    unresolved = list(verification)
    # Single-character video can resolve ordinary scripted location/action shape, but never fivebox sharing/loot/failure semantics.
    if has_video:
        unresolved = [
            item for item in unresolved
            if item.startswith("fivebox_") or "shared" in item or "group_completion" in item or "loot_mode" in item
        ]
    return {
        "decision": decision,
        "reasons": reasons,
        "verification_needed": verification,
        "video_evidence_available": has_video,
        "unresolved_after_local_evidence": sorted(set(unresolved)),
    }


def final_note_review(task: dict[str, Any], auto: dict[str, Any], manual_notes: dict[int, dict[str, Any]]) -> dict[str, Any]:
    status = task["scope_status"]
    if not status.startswith("include_") or task["is_dungeon"]:
        return {
            "decision": "not_route_candidate",
            "facts": [],
            "verification": [],
            "background_verification": [],
            "review_basis": "scope_filter",
        }
    manual = manual_notes.get(task["quest_id"])
    if manual:
        return {
            "decision": manual.get("decision", "manual_review_pending"),
            "facts": list(manual.get("facts") or []),
            "verification": list(manual.get("verification") or []),
            "background_verification": sorted(set(auto.get("unresolved_after_local_evidence") or [])),
            "review_basis": "manual_override_after_questie_and_reference_review",
        }
    if auto["decision"] == "must_note":
        return {
            "decision": "manual_review_pending",
            "facts": [],
            "verification": list(auto.get("unresolved_after_local_evidence") or []),
            "background_verification": [],
            "review_basis": "automatic_screen_flag_not_yet_manually_resolved",
        }
    return {
        "decision": "reviewed_no_extra_note",
        "facts": [],
        "verification": [],
        "background_verification": sorted(set(auto.get("unresolved_after_local_evidence") or [])),
        "review_basis": "manual_objective_read_straightforward_player_action",
    }


def main() -> None:
    configure_shared()
    data = load_questie(QUESTIE_ZIP)
    meta = _parse_zone_metadata(QUESTIE_ZIP)
    overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    manual_unavailable = {int(qid): reason for qid, reason in (overrides.get("manual_unavailable") or {}).items()}
    manual_defer_to_80 = {int(qid): reason for qid, reason in (overrides.get("manual_defer_to_80") or {}).items()}
    entry_axis_relevance = {int(qid): value for qid, value in (overrides.get("entry_axis_relevance") or {}).items()}
    manual_notes = {int(qid): value for qid, value in (overrides.get("notes") or {}).items()}
    for qid in overrides.get("manual_no_extra_note_ids") or []:
        manual_notes.setdefault(int(qid), {"decision": "reviewed_no_extra_note", "facts": [], "verification": []})
    initial_ids, union_sources = candidate_union(data, meta)
    candidate_ids, rows, correction_audit, roles = shared.effective_with_boundary_refs(data, initial_ids)

    tasks: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}
    for quest_id in sorted(candidate_ids):
        row = rows.get(quest_id)
        if not isinstance(row, dict):
            continue
        name = shared.localized_name(data, quest_id, row)
        objective_zh = shared.localized_objective(data, quest_id)
        objective_en = shared.english_objective(row)
        classified, review = classify_objectives(data, row, ZONE_ID, objective_zh or objective_en)
        objectives = [asdict(obj) for obj in classified]
        extra = shared.extract_extra_objectives(data, row, ZONE_ID)
        task_class, task_flags = classify_task(classified, objective_en or objective_zh)
        starts = shared.entity_group(data, row.get(2))
        finishes = shared.entity_group(data, row.get(3))
        objective_zones = shared.objective_route_zones(objectives, ZONE_ID)
        assigned = shared.assigned_parent_zone(row, meta["parents"])
        touches = shared.direct_touches_zone(data, row, ZONE_ID)
        race_allowed = shared.bit_allows(row.get(6), BLOOD_ELF_FLAG)
        class_allowed = shared.bit_allows(row.get(7), PALADIN_FLAG)
        npc_allowed, npc_reasons = shared.npc_faction_eligibility(data, row)
        faction_reasons = list(npc_reasons)
        if not race_allowed:
            faction_reasons.append("required_races_excludes_blood_elf")
        qflags = int(row.get(23) or 0)
        sflags = int(row.get(24) or 0)
        deps = shared.dependency_ids(row)
        start_zones = sorted({z for entity in starts for z in shared.preferred_entity_route_zones(entity, ZONE_ID)})
        finish_zones = sorted({z for entity in finishes for z in shared.preferred_entity_route_zones(entity, ZONE_ID)})
        extra_zones = sorted({z for item in extra for z in item.get("route_zones", [])})
        all_zones = sorted(set(start_zones + finish_zones + objective_zones + extra_zones))
        is_cross = any(z != ZONE_ID for z in all_zones) or (assigned is not None and assigned != ZONE_ID and touches)
        is_dungeon = bool((assigned is not None and assigned in meta["dungeons"]) or any(z in meta["dungeons"] for z in all_zones))
        pvp = shared.pvp_classification(row, name, objective_en or objective_zh, objectives)
        boundary_kinds: list[str] = []
        if quest_id in roles["boundary_prerequisite"]:
            boundary_kinds.append("prerequisite")
        if quest_id in roles["boundary_followup"]:
            boundary_kinds.append("followup")
        lower_name = name.lower()
        task = {
            "quest_id": quest_id,
            "name": name,
            "english_name": str(row.get(1) or ""),
            "is_primary_candidate": quest_id in roles["primary"],
            "boundary_reference_kinds": boundary_kinds,
            "required_level": row.get(4),
            "quest_level": row.get(5),
            "required_races": row.get(6),
            "required_classes": row.get(7),
            "required_skill": row.get(18),
            "required_min_rep": row.get(19),
            "required_max_rep": row.get(20),
            "quest_flags": qflags,
            "special_flags": sflags,
            "assigned_zone_id": assigned,
            "touches_dragonblight_effective": touches,
            "is_cross_map": is_cross,
            "is_dungeon": is_dungeon,
            "is_raid_flagged": bool(qflags & RAID),
            "race_allowed": race_allowed,
            "class_allowed": class_allowed,
            "npc_faction_allowed": npc_allowed,
            "faction_reasons": sorted(set(faction_reasons)),
            "is_repeatable": bool(sflags & REPEATABLE or qflags & (DAILY | WEEKLY | MONTHLY)),
            "is_deprecated_or_system": "zzold" in lower_name or "deprecated" in lower_name or "????" in name,
            "xp": xp_facts(data, quest_id, row),
            "pvp": pvp,
            "objective_text_zh": objective_zh,
            "objective_text_en": objective_en,
            "task_class": task_class,
            "task_flags": task_flags,
            "objective_review": review,
            "objectives": objectives,
            "extra_objectives": extra,
            "start_entities": starts,
            "finish_entities": finishes,
            "item_start_ids": _ids(row.get(2), 3),
            "start_zones": start_zones,
            "objective_zones": objective_zones,
            "extra_objective_zones": extra_zones,
            "turnin_zones": finish_zones,
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
        }
        task["scope_status"], task["scope_reasons"] = initial_scope(task)
        task["entry_axis_relevance"] = entry_axis_relevance.get(quest_id, "current_axis_or_local")
        if quest_id in manual_unavailable:
            task["scope_status"] = "exclude_removed_or_unavailable"
            task["scope_reasons"] = [manual_unavailable[quest_id]]
        elif quest_id in manual_defer_to_80:
            task["scope_status"] = "defer_to_80_after_live_failure"
            task["scope_reasons"] = [manual_defer_to_80[quest_id]]
        elif "not_current_axis" in task["entry_axis_relevance"]:
            task["scope_status"] = "exclude_current_entry_axis_alternate"
            task["scope_reasons"] = [task["entry_axis_relevance"]]
        tasks.append(task)
        by_id[quest_id] = task

    # Promote mandatory zero-XP structural prerequisites only.
    changed = True
    while changed:
        changed = False
        included_ids = {qid for qid, task in by_id.items() if task["scope_status"].startswith("include_")}
        for qid in sorted(included_ids):
            task = by_id[qid]
            mandatory = set(task["pre_all"] + task["parent_active"])
            if len(task["pre_any"]) == 1:
                mandatory.update(task["pre_any"])
            for dep in mandatory:
                pred = by_id.get(dep)
                if pred and pred["scope_status"] == "exclude_no_xp_pending_dependency_audit":
                    pred["scope_status"] = "include_structural_zero_xp_prerequisite"
                    pred["scope_reasons"] = [f"mandatory_for_xp_quest_{qid}"]
                    changed = True
    for task in tasks:
        if task["scope_status"] == "exclude_no_xp_pending_dependency_audit":
            task["scope_status"] = "exclude_no_xp"
            task["scope_reasons"] = ["no_quest_xp_and_not_mandatory_for_included_xp_task"]

    # Classify cross-map direction. No ordering decision is made.
    for task in tasks:
        if task["scope_status"] != "include_leveling_cross_map":
            continue
        starts_here = ZONE_ID in task["start_zones"]
        finishes_here = ZONE_ID in task["turnin_zones"]
        starts_elsewhere = any(z != ZONE_ID for z in task["start_zones"])
        finishes_elsewhere = any(z != ZONE_ID for z in task["turnin_zones"])
        if starts_elsewhere and finishes_here:
            task["scope_status"] = "include_cross_map_inbound"
            task["scope_reasons"] = ["starts_outside_dragonblight_and_finishes_here"]
        elif starts_here and finishes_elsewhere:
            task["scope_status"] = "include_cross_map_outbound"
            task["scope_reasons"] = ["starts_in_dragonblight_and_finishes_elsewhere"]

    video = parse_video(tasks)
    mechanics_rows: list[dict[str, Any]] = []
    for task in tasks:
        auto_audit = note_audit(task, video)
        final_review = final_note_review(task, auto_audit, manual_notes)
        task["auto_note_screen"] = auto_audit
        task["final_note_review"] = final_review
        if task["is_primary_candidate"]:
            mechanics_rows.append({
                "quest_id": task["quest_id"],
                "name": task["name"],
                "scope_status": task["scope_status"],
                "entry_axis_relevance": task["entry_axis_relevance"],
                "task_class": task["task_class"],
                "task_flags": task["task_flags"],
                "auto_screen": auto_audit,
                "final_review": final_review,
                "video_reference": video["tasks"].get(str(task["quest_id"]), {}),
            })

    clusters: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not task["scope_status"].startswith("include_") or task["is_dungeon"]:
            continue
        for objective in task["objectives"]:
            for source in objective.get("sources") or []:
                if ZONE_ID not in (source.get("zones") or []):
                    continue
                entity_id = source.get("entity_id")
                if not isinstance(entity_id, int):
                    continue
                key = f"{source.get('entity_type')}:{entity_id}"
                cluster = clusters.setdefault(key, {
                    "cluster_id": key,
                    "entity_type": source.get("entity_type"),
                    "entity_id": entity_id,
                    "name": source.get("name"),
                    "dragonblight_representative": (source.get("representative_by_zone") or {}).get(str(ZONE_ID)),
                    "spawn_count": source.get("spawn_count"),
                    "quest_ids": [],
                    "relations": [],
                })
                otype = objective.get("objective_type")
                relation = "direct_creature" if otype == "kill" else "direct_object" if otype == "object" else f"resolved_{otype}"
                cluster["quest_ids"].append(task["quest_id"])
                cluster["relations"].append({
                    "quest_id": task["quest_id"],
                    "quest_name": task["name"],
                    "relation_kind": relation,
                    "required_count": objective.get("required_count"),
                    "item_id": objective.get("item_id"),
                })
    cluster_list: list[dict[str, Any]] = []
    for cluster in clusters.values():
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["relations"].sort(key=lambda row: (row["quest_id"], row["relation_kind"]))
        cluster["shared_by_multiple_tasks"] = len(cluster["quest_ids"]) > 1
        cluster_list.append(cluster)
    cluster_list.sort(key=lambda row: (-len(row["quest_ids"]), str(row["name"]), row["entity_id"]))

    included = {task["quest_id"] for task in tasks if task["scope_status"].startswith("include_")}
    availability = []
    for task in tasks:
        if task["quest_id"] not in included:
            continue
        peers = sorted(qid for qid in task["exclusive_to"] if qid in included)
        if peers:
            availability.append({
                "quest_id": task["quest_id"],
                "quest_name": task["name"],
                "must_accept_before_quest_ids": peers,
                "peer_names": [by_id[qid]["name"] for qid in peers if qid in by_id],
            })

    primary_tasks = [task for task in tasks if task["is_primary_candidate"]]
    scope_counts = Counter(task["scope_status"] for task in primary_tasks)
    note_counts = Counter(row["final_review"]["decision"] for row in mechanics_rows)
    unresolved = [
        row for row in mechanics_rows
        if row["scope_status"].startswith("include_")
        and (row["final_review"]["verification"] or row["final_review"]["background_verification"])
    ]
    pending_manual = [row for row in mechanics_rows if row["final_review"]["decision"] == "manual_review_pending"]

    foundation = {
        "status": "foundation_only_no_route_order",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "entry_contract": {
            "from_borean_quest_id": 11930,
            "from_borean_quest_name": "横贯冰原",
            "carried_cross_map_quest_id": 12117,
            "carried_cross_map_quest_name": "前往莫亚基港口",
            "route_insertion_started": False,
        },
        "assumptions": {
            "profile": "blood_elf_horde_paladin_fivebox",
            "entry_level_floor": ENTRY_LEVEL,
            "first_pass_max_required_level": FIRST_PASS_MAX_REQUIRED_LEVEL,
            "questie_version": data.version,
            "note": "This artifact contains no task ordering, hearth optimization, route insertion, or HTML work.",
        },
        "candidate_union": union_sources,
        "correction_audit": correction_audit,
        "scope_counts": dict(sorted(scope_counts.items())),
        "manual_review_pending_count": len(pending_manual),
        "availability_constraints": availability,
        "tasks": tasks,
    }
    cluster_payload = {
        "status": "foundation_only_no_route_order",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "cluster_count": len(cluster_list),
        "shared_cluster_count": sum(1 for row in cluster_list if row["shared_by_multiple_tasks"]),
        "clusters": cluster_list,
    }
    mechanics_payload = {
        "status": "per_task_human_executability_screen_before_route_insertion",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "decision_counts": dict(sorted(note_counts.items())),
        "manual_review_pending_count": len(pending_manual),
        "rows": mechanics_rows,
        "unresolved_included_tasks": unresolved,
    }

    for path, payload in ((OUT_FOUNDATION, foundation), (OUT_CLUSTERS, cluster_payload), (OUT_VIDEO, video), (OUT_MECHANICS, mechanics_payload)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    must_note = [row for row in mechanics_rows if row["scope_status"].startswith("include_") and row["final_review"]["decision"] == "must_note"]
    review = [row for row in mechanics_rows if row["scope_status"].startswith("include_") and row["final_review"]["decision"] == "review_before_route"]
    no_note = [row for row in mechanics_rows if row["scope_status"].startswith("include_") and row["final_review"]["decision"] == "reviewed_no_extra_note"]
    lines = [
        "# 龙骨荒野任务基础与攻略备注预审（未开始插路线）",
        "",
        "## 边界",
        "",
        "- 本轮只建立任务事实、前置边界、目标簇、特殊机制与攻略备注判定；未做任务插入、路线排序、炉石优化或HTML改动。",
        "- 北风自然入口为11930《横贯冰原》；12117《前往莫亚基港口》跨图携带，到莫亚基港口自然交。",
        f"- Questie {data.version} effective facts；入口等级下限按{ENTRY_LEVEL}，第一遍纳入requiredLevel≤{FIRST_PASS_MAX_REQUIRED_LEVEL}，更高等级门槛保留后续回访候选。",
        "- 视频40—42集只作为单号地点/任务机制证据；视频角色为联盟，不能直接证明部落ID、五开共享或五开耗时。",
        "",
        "## 基础统计",
        "",
        f"- primary候选：{len(primary_tasks)}；连同一跳前置/后续边界：{len(tasks)}。",
        f"- scope：`{dict(sorted(scope_counts.items()))}`。",
        f"- 精确目标簇：{len(cluster_list)}；多任务共享目标簇：{sum(1 for row in cluster_list if row['shared_by_multiple_tasks'])}。",
        f"- 最终攻略备注判定：`{dict(sorted(note_counts.items()))}`。",
        f"- 当前纳入范围 must_note={len(must_note)}，review_before_route={len(review)}，reviewed_no_extra_note={len(no_note)}，manual_review_pending={len(pending_manual)}。",
        f"- 仍需首组五开实测或交通核验的后台机制项={len(unresolved)}；这些不等于都要显示在玩家攻略里。",
        "",
        "## 必须写攻略备注的任务",
        "",
    ]
    for row in must_note:
        final = row["final_review"]
        facts = "；".join(final["facts"]) or "特殊机制已人工确认需要玩家备注"
        pending = ", ".join(final["verification"]) or "无额外未决项"
        lines.append(f"- {row['quest_id']}《{row['name']}》：{facts}；首组待核验：{pending}。")
    lines.extend(["", "## 插入前仍需交通/条件复核但不先写死攻略", ""])
    for row in review:
        final = row["final_review"]
        facts = "；".join(final["facts"]) or "当前只保留为插入阶段条件检查"
        lines.append(f"- {row['quest_id']}《{row['name']}》：{facts}；待核验：{', '.join(final['verification'])}。")
    if pending_manual:
        lines.extend(["", "## 尚未完成人工判定（基础层未通过）", ""])
        for row in pending_manual:
            lines.append(f"- {row['quest_id']}《{row['name']}》：自动筛查仍标记为特殊机制，必须补人工判定后才能开始插入。")
    lines.extend([
        "",
        "## 停止点",
        "",
        "- 到这里为止只完成基础层。等用户明确通知后，才从第一个Target Cluster开始逐任务插入。",
        "- 插入时不得重新把当前首组状态裁进Route Atlas；首组状态只用于CURRENT恢复与实跑反馈。",
        "- 龙骨荒野仍加入统一Route Atlas工作台，不创建独立HTML。",
    ])
    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AUDIT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "foundation": str(OUT_FOUNDATION.relative_to(ROOT)),
        "clusters": str(OUT_CLUSTERS.relative_to(ROOT)),
        "video": str(OUT_VIDEO.relative_to(ROOT)),
        "mechanics": str(OUT_MECHANICS.relative_to(ROOT)),
        "audit": str(OUT_AUDIT.relative_to(ROOT)),
        "primary_count": len(primary_tasks),
        "scope_counts": dict(sorted(scope_counts.items())),
        "note_counts": dict(sorted(note_counts.items())),
        "manual_review_pending": len(pending_manual),
        "unresolved_included": len(unresolved),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
