from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OVERRIDES = ROOT / "data/route-atlas/icecrown-task-overrides.json"
OUT_SCOPE = ROOT / "data/route-atlas/icecrown-scope-audit.json"
OUT_FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT_CLUSTERS = ROOT / "data/route-atlas/icecrown-target-clusters.json"
OUT_ENTRY = ROOT / "data/route-atlas/icecrown-entry-audit.json"
OUT_BACKLOG = ROOT / "data/route-atlas/icecrown-review-backlog.json"
OUT_REPORT = ROOT / "docs/analysis/2026-08-25-icecrown-foundation-audit.md"

ZONE_ID = 210
ZONE_NAME = "冰冠冰川"
CURRENT_LEVEL = 80
ENTRY_QUEST_ID = 12892
PRIMARY_ENTRY_QUEST_ID = 13036
SKIPPED_BREADCRUMB_QUEST_ID = 13227
NATURAL_AIRSHIP_QUEST_ID = 13224
BLOCKED_TRANSPORT_QUEST_ID = 13419
MANUAL_EXCLUDE_IDS = {
    13173: "source_less_non_executable_record",
    13175: "source_less_non_executable_record",
    13176: "source_less_non_executable_record",
    13184: "source_less_non_executable_record",
    13093: "repeatable_followup_of_13092_not_a_second_first_run",
    13481: "phased_mutually_exclusive_alternative_to_13229_default_route_uses_earlier_escort",
    13261: "daily_repeat_of_13239_same_content_not_a_second_first_run",
    13276: "daily_repeat_of_13264_same_content_not_a_second_first_run",
    13281: "daily_repeat_of_13279_same_cauldron_event_not_a_second_first_run",
    13331: "daily_repeat_of_13313_same_sgm3_objective_not_a_second_first_run",
    13353: "daily_repeat_of_13352_same_content_not_a_second_first_run",
    13357: "daily_repeat_of_13356_same_content_not_a_second_first_run",
    13365: "daily_repeat_of_13358_same_content_not_a_second_first_run",
    13368: "daily_repeat_of_13367_same_content_not_a_second_first_run",
    13406: "daily_repeat_of_13373_same_bombardment_area_vehicle_and_target_set_not_a_second_first_run",
    13374: "legacy_unavailable_bomber_quest_current_questie_wotlk_flow_bypasses_13374_from_13373_to_13376",
    13378: "source_less_non_executable_record",
    24808: "internal_ring_flag_not_available_in_game",
    24809: "internal_ring_flag_not_available_in_game",
    24810: "internal_ring_flag_not_available_in_game",
    24811: "internal_ring_flag_not_available_in_game",
    25238: "internal_ring_flag_not_available_in_game",
}
EXTERNAL_ACQUISITION_IDS = {
    24451: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24554: "battered_hilt_requires_external_heroic_frozen_halls_drop_or_purchase",
    24555: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24556: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24558: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24560: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24799: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24800: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
    24801: "quel_delar_chain_requires_external_battered_hilt_and_dungeon_steps",
}
ROUTE_ECONOMICS_SKIP_IDS = {
    13227: "breadcrumb_only_3_24g_per_character_requires_dedicated_moving_airship_detour_before_argent_vanguard",
    13234: "pvp_daily_requires_15_opposing_players_non_deterministic_external_player_dependency",
}
# A map route's dependency closure may cross assigned-zone boundaries. These tasks remain
# attributed to their original zone in the global universe, but are materialized here because
# omitting them would make Icecrown chain coverage falsely appear complete.
CROSS_ZONE_CHAIN_BRIDGE_IDS = {
    13078: "required_dragonblight_bridge_between_icecrown_13077_and_13079",
}


def rep(entity: dict[str, Any]) -> dict[str, float | int | None]:
    row = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
    return {
        "x": row.get("x"),
        "y": row.get("y"),
        "spawn_count": row.get("spawn_count"),
    }


def status_for(task: dict[str, Any]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if qid in MANUAL_EXCLUDE_IDS:
        return "exclude_manual_non_executable", [MANUAL_EXCLUDE_IDS[qid]]
    if qid in EXTERNAL_ACQUISITION_IDS:
        return "knowledge_external_acquisition", [EXTERNAL_ACQUISITION_IDS[qid]]
    if qid in ROUTE_ECONOMICS_SKIP_IDS:
        return "exclude_route_economics", [ROUTE_ECONOMICS_SKIP_IDS[qid]]
    if task.get("cold_weather_flying_gate"):
        return "exclude_cold_weather_flying_gate", [
            "current_route_intentionally_does_not_learn_cold_weather_flying"
        ]

    eligibility = task.get("eligibility") or {}
    if eligibility.get("status") == "impossible_or_excluded":
        return "exclude_unavailable_or_policy", list(eligibility.get("reasons") or ["unavailable"])

    required_max = task.get("required_max_level")
    if isinstance(required_max, int) and required_max > 0 and required_max < CURRENT_LEVEL:
        return "exclude_expired_before_level_80", [f"required_max_level_{required_max}"]

    if eligibility.get("status") == "conditional":
        return "include_conditional_route_state", list(eligibility.get("reasons") or ["conditional"])

    if task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly"):
        return "include_first_run_repeatable_or_calendar", [
            "first_run_only_user_rule_compare_real_content_not_calendar_label"
        ]

    return "include_candidate", ["level_80_horde_paladin_outdoor_first_run"]


def objective_sources(task: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    qid = int(task["quest_id"])
    for objective_index, objective in enumerate(task.get("objectives") or [], start=1):
        for source in objective.get("sources") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rows.append(
                {
                    "quest_id": qid,
                    "quest_name": task.get("name"),
                    "objective_index": objective_index,
                    "objective_type": objective.get("objective_type"),
                    "required_count": objective.get("required_count"),
                    "item_id": objective.get("item_id"),
                    "item_name": objective.get("item_name"),
                    "entity_type": source.get("entity_type"),
                    "entity_id": source.get("entity_id"),
                    "entity_name": source.get("name"),
                    "representative": rep(source),
                    "spawn_count": source.get("spawn_count"),
                    "source_kind": "objective",
                }
            )
    for extra in task.get("extra_objectives") or []:
        extra_index = int(extra.get("index") or 0)
        for source in extra.get("references") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rows.append(
                {
                    "quest_id": qid,
                    "quest_name": task.get("name"),
                    "objective_index": extra_index,
                    "objective_type": "extra_objective",
                    "required_count": None,
                    "item_id": None,
                    "item_name": None,
                    "entity_type": source.get("entity_type"),
                    "entity_id": source.get("entity_id"),
                    "entity_name": source.get("name"),
                    "representative": rep(source),
                    "spawn_count": source.get("spawn_count"),
                    "source_kind": "extra_reference",
                    "extra_text": extra.get("text"),
                }
            )
        for coord_index, coord in enumerate(
            (extra.get("coordinates_by_zone") or {}).get(str(ZONE_ID)) or [], start=1
        ):
            if not isinstance(coord, list) or len(coord) < 2:
                continue
            rows.append(
                {
                    "quest_id": qid,
                    "quest_name": task.get("name"),
                    "objective_index": extra_index,
                    "objective_type": "extra_objective",
                    "required_count": None,
                    "item_id": None,
                    "item_name": None,
                    "entity_type": "extra_anchor",
                    "entity_id": f"{qid}:{extra_index}:{coord_index}",
                    "entity_name": extra.get("text") or f"extra objective {extra_index}",
                    "representative": {
                        "x": float(coord[0]),
                        "y": float(coord[1]),
                        "spawn_count": 1,
                    },
                    "spawn_count": 1,
                    "source_kind": "extra_coordinate",
                    "extra_text": extra.get("text"),
                }
            )
    return rows


def start_rows(task: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entity in task.get("start_entities") or []:
        r = rep(entity)
        if r.get("x") is None or r.get("y") is None:
            continue
        result.append(
            {
                "entity_type": entity.get("entity_type"),
                "entity_id": entity.get("entity_id"),
                "name": entity.get("name"),
                **r,
            }
        )
    return result


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    service_overrides = {int(qid): value for qid, value in (overrides.get("manual_service_minutes") or {}).items()}
    direct_money_overrides = {int(qid): value for qid, value in (overrides.get("manual_direct_money_copper") or {}).items()}
    objective_review_resolutions = {int(qid): str(value) for qid, value in (overrides.get("objective_review_resolutions") or {}).items()}
    spatial_resolutions = {int(qid): str(value) for qid, value in (overrides.get("manual_spatial_resolutions") or {}).items()}
    fivebox_resolved = {int(qid): str(value) for qid, value in (overrides.get("fivebox_resolved") or {}).items()}
    evidence_notes = {int(qid): str(value) for qid, value in (overrides.get("evidence_notes") or {}).items()}
    universe_by_id = {int(task["quest_id"]): task for task in universe.get("tasks", [])}
    assigned = [
        dict(task)
        for task in universe.get("tasks", [])
        if int(task.get("assigned_zone_id") or 0) == ZONE_ID
    ]
    touching = [
        dict(task)
        for task in universe.get("tasks", [])
        if ZONE_ID in (task.get("touching_northrend_zone_ids") or [])
    ]
    bridge_tasks = [
        dict(universe_by_id[qid])
        for qid in sorted(CROSS_ZONE_CHAIN_BRIDGE_IDS)
        if qid in universe_by_id
    ]
    assigned_ids = {int(task["quest_id"]) for task in assigned}
    bridge_ids = {int(task["quest_id"]) for task in bridge_tasks}
    scope_ids = assigned_ids | bridge_ids
    touching_ids = {int(task["quest_id"]) for task in touching}

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for task in assigned + bridge_tasks:
        qid = int(task["quest_id"])
        task["scope_origin"] = "cross_zone_chain_bridge" if qid in bridge_ids else "assigned_icecrown"
        if qid in bridge_ids:
            task["scope_bridge_reason"] = CROSS_ZONE_CHAIN_BRIDGE_IDS[qid]
        if qid in service_overrides:
            override = service_overrides[qid]
            task["intrinsic_service_time"] = {
                "status": "estimated",
                "minutes": float(override["minutes"]),
                "basis": f"manual_pre_route:{override['basis']}",
                "range_minutes": [float(x) for x in override.get("range", [])],
            }
        task["objective_review_resolution"] = objective_review_resolutions.get(qid, "")
        task["manual_spatial_resolution"] = spatial_resolutions.get(qid, "")
        task["fivebox_resolved"] = fivebox_resolved.get(qid, "")
        task["manual_evidence_note"] = evidence_notes.get(qid, "")
        status, reasons = status_for(task)
        task["scope_status"] = status
        task["scope_reasons"] = reasons
        bonus = ((task.get("xp") or {}).get("max_level_bonus_money") or {})
        direct_override = direct_money_overrides.get(qid)
        direct_copper = int((direct_override or {}).get("copper") or 0)
        task["level_80_economy"] = {
            "xp_bonus_money_copper": int(bonus.get("bonus_money_from_xp_copper") or 0),
            "xp_bonus_money_gold_decimal": float(bonus.get("bonus_money_from_xp_gold_decimal") or 0.0),
            "xp_bonus_money_display": bonus.get("display"),
            "equipment_reward_count": len((task.get("rewards") or {}).get("equipment_rewards") or []),
            "other_reward_item_count": len((task.get("rewards") or {}).get("other_reward_items") or []),
            "direct_money_copper": direct_copper,
            "direct_money_gold_decimal": direct_copper / 10000.0,
            "direct_money_status": "manual_verified" if direct_override else (task.get("rewards") or {}).get("direct_money_status"),
            "direct_money_basis": (direct_override or {}).get("basis"),
        }
        rows.append(task)
        status_counts[status] += 1

    by_id = {int(task["quest_id"]): task for task in rows}
    route_statuses = {
        "include_candidate",
        "include_conditional_route_state",
        "include_first_run_repeatable_or_calendar",
    }

    # Propagate only hard local dependency blocks. A single pre_any dependency is mandatory; when
    # there are several pre_any alternatives, block only if every listed alternative is an Icecrown
    # task and every one is already excluded from the route pool.
    changed = True
    while changed:
        changed = False
        for task in rows:
            if task.get("scope_status") not in route_statuses:
                continue
            blocked: list[int] = []
            mandatory = set(int(x) for x in (task.get("pre_all") or []))
            mandatory |= set(int(x) for x in (task.get("parent_active") or []))
            pre_any = [int(x) for x in (task.get("pre_any") or [])]
            if len(pre_any) == 1:
                mandatory.add(pre_any[0])
            for dep in sorted(mandatory):
                dep_task = by_id.get(dep)
                if dep_task and dep_task.get("scope_status") not in route_statuses:
                    blocked.append(dep)
            if len(pre_any) > 1 and all(dep in by_id for dep in pre_any):
                if all(by_id[dep].get("scope_status") not in route_statuses for dep in pre_any):
                    blocked.extend(pre_any)
            if blocked:
                task["scope_status"] = "exclude_dependency_on_blocked_task"
                task["scope_reasons"] = [f"blocked_by_{dep}" for dep in sorted(set(blocked))]
                changed = True

    status_counts = Counter(task["scope_status"] for task in rows)
    candidate_ids = {
        int(task["quest_id"])
        for task in rows
        if task.get("scope_status") in route_statuses
    }

    # Zero-XP/zero-item tasks are not automatically deleted because direct quest money is not yet
    # globally materialized in the universe. Flag them for the economic pass instead.
    economy_review: list[dict[str, Any]] = []
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        econ = task["level_80_economy"]
        if (
            econ["xp_bonus_money_copper"] == 0
            and econ["equipment_reward_count"] == 0
            and econ["other_reward_item_count"] == 0
            and econ["direct_money_copper"] == 0
        ):
            economy_review.append(
                {
                    "quest_id": qid,
                    "name": task.get("name"),
                    "reason": "zero_xp_bonus_no_indexed_items_and_no_verified_direct_money",
                }
            )

    dependency_gaps: list[dict[str, Any]] = []
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        mandatory = set(int(x) for x in (task.get("pre_all") or []))
        mandatory |= set(int(x) for x in (task.get("parent_active") or []))
        pre_any = [int(x) for x in (task.get("pre_any") or [])]
        if len(pre_any) == 1:
            mandatory.add(pre_any[0])
        for dep in sorted(mandatory):
            if dep in scope_ids and dep not in candidate_ids:
                dep_task = by_id.get(dep) or {}
                dependency_gaps.append(
                    {
                        "quest_id": qid,
                        "name": task.get("name"),
                        "missing_dependency_id": dep,
                        "missing_dependency_name": dep_task.get("name"),
                        "dependency_status": dep_task.get("scope_status"),
                    }
                )

    unknown_service_tasks: list[dict[str, Any]] = []
    unresolved_objective_review_tasks: list[dict[str, Any]] = []
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        service = task.get("intrinsic_service_time") or {}
        if service.get("status") != "estimated" or not isinstance(service.get("minutes"), (int, float)):
            unknown_service_tasks.append(
                {"quest_id": qid, "name": task.get("name"), "service": service}
            )
        if task.get("objective_review") and not task.get("objective_review_resolution"):
            unresolved_objective_review_tasks.append(
                {
                    "quest_id": qid,
                    "name": task.get("name"),
                    "objective_review": task.get("objective_review"),
                }
            )

    cluster_map: dict[tuple[str, str], dict[str, Any]] = {}
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        for source in objective_sources(task):
            eid = source.get("entity_id")
            if not isinstance(eid, (int, str)):
                continue
            etype = str(source.get("entity_type") or "entity")
            key = (etype, str(eid))
            cluster = cluster_map.setdefault(
                key,
                {
                    "cluster_id": f"{etype}:{eid}",
                    "entity_type": etype,
                    "entity_id": eid,
                    "name": source.get("entity_name"),
                    "representative": source.get("representative") or {},
                    "spawn_count": source.get("spawn_count"),
                    "quest_ids": [],
                    "relations": [],
                    "source_kinds": [],
                },
            )
            cluster["quest_ids"].append(qid)
            cluster["relations"].append(source)
            cluster["source_kinds"].append(source.get("source_kind") or "objective")

    clusters = list(cluster_map.values())
    for cluster in clusters:
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["source_kinds"] = sorted(set(cluster["source_kinds"]))
        cluster["shared_by_multiple_tasks"] = len(cluster["quest_ids"]) > 1
    clusters.sort(
        key=lambda cluster: (
            -len(cluster["quest_ids"]),
            float((cluster.get("representative") or {}).get("y") or 999),
            float((cluster.get("representative") or {}).get("x") or 999),
            str(cluster.get("name") or ""),
        )
    )

    roots: list[dict[str, Any]] = []
    for qid in sorted(candidate_ids):
        task = by_id[qid]
        if task.get("pre_any") or task.get("pre_all") or task.get("parent_active"):
            continue
        roots.append(
            {
                "quest_id": qid,
                "name": task.get("name"),
                "scope_status": task.get("scope_status"),
                "starts": start_rows(task),
                "required_min_rep": task.get("required_min_rep"),
                "available_starting_with": task.get("available_starting_with") or [],
                "level_80_economy": task.get("level_80_economy"),
            }
        )

    entry_task = by_id.get(ENTRY_QUEST_ID) or {}
    primary_entry = by_id.get(PRIMARY_ENTRY_QUEST_ID) or {}
    skipped_breadcrumb = by_id.get(SKIPPED_BREADCRUMB_QUEST_ID) or {}
    natural_airship = by_id.get(NATURAL_AIRSHIP_QUEST_ID) or {}
    blocked_transport = by_id.get(BLOCKED_TRANSPORT_QUEST_ID) or {}
    entry_payload = {
        "status": "primary_entry_frozen_shadow_vault_probe_deferred_to_natural_airship_visit",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "current_level": CURRENT_LEVEL,
        "transport": {
            "cold_weather_flying_learned": False,
            "loaned_wind_rider_available": True,
            "action": "use the loaned wind rider to enter Argent Vanguard first; do not chase the moving airship as the first hub",
        },
        "blocked_transport_quest": {
            "quest_id": BLOCKED_TRANSPORT_QUEST_ID,
            "name": blocked_transport.get("name"),
            "scope_status": blocked_transport.get("scope_status"),
            "cold_weather_flying_gate": blocked_transport.get("cold_weather_flying_gate"),
        },
        "primary_entry": {
            "quest_id": PRIMARY_ENTRY_QUEST_ID,
            "name": primary_entry.get("name"),
            "scope_status": primary_entry.get("scope_status"),
            "starts": start_rows(primary_entry),
            "next_quest": primary_entry.get("next_quest"),
            "reason": "independent Argent Vanguard root; geographically natural first hub and its chain later unlocks the Horde airship breadcrumb 13224",
        },
        "skipped_breadcrumb": {
            "quest_id": SKIPPED_BREADCRUMB_QUEST_ID,
            "name": skipped_breadcrumb.get("name"),
            "xp_bonus_money_gold_decimal": ((skipped_breadcrumb.get("level_80_economy") or {}).get("xp_bonus_money_gold_decimal")),
            "next_quest": skipped_breadcrumb.get("next_quest"),
            "decision": "skip_permanently",
            "reason": "becomes unavailable after starting 13036 and is only 3.24G per character from max-level XP conversion; not worth a dedicated moving-airship detour before Argent Vanguard",
        },
        "natural_airship_entry": {
            "quest_id": NATURAL_AIRSHIP_QUEST_ID,
            "name": natural_airship.get("name"),
            "pre_any": natural_airship.get("pre_any") or [],
            "starts": start_rows(natural_airship),
            "finishes": [
                {
                    "entity_type": entity.get("entity_type"),
                    "entity_id": entity.get("entity_id"),
                    "name": entity.get("name"),
                }
                for entity in (natural_airship.get("finish_entities") or [])
            ],
        },
        "shadow_vault_entry_probe": {
            "quest_id": ENTRY_QUEST_ID,
            "name": entry_task.get("name"),
            "scope_status": entry_task.get("scope_status"),
            "pre_any": entry_task.get("pre_any") or [],
            "pre_all": entry_task.get("pre_all") or [],
            "parent_active": entry_task.get("parent_active") or [],
            "available_starting_with": entry_task.get("available_starting_with") or [],
            "required_spell": entry_task.get("required_spell"),
            "cold_weather_flying_gate": entry_task.get("cold_weather_flying_gate"),
            "starts": start_rows(entry_task),
            "live_check": "when quest 13224 naturally brings the group to Orgrim's Hammer, check whether Koltira Deathweaver offers quest 12892",
            "if_missing": "record the live blocker; do not infer 13419 as a hard prerequisite solely from old public comments",
        },
        "independent_root_count": len(roots),
        "independent_roots": roots,
    }

    total_bonus_copper = sum(
        int(by_id[qid]["level_80_economy"]["xp_bonus_money_copper"])
        for qid in candidate_ids
    )
    foundation = {
        "status": "foundation_scope_started_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "profile": "blood-elf-paladin",
        "current_level": CURRENT_LEVEL,
        "source": universe.get("source"),
        "assigned_task_count": len(assigned),
        "cross_zone_chain_bridge_task_count": len(bridge_tasks),
        "cross_zone_chain_bridge_ids": sorted(bridge_ids),
        "touching_task_count": len(touching),
        "touch_only_ids": sorted(touching_ids - assigned_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "route_candidate_count": len(candidate_ids),
        "route_candidate_ids": sorted(candidate_ids),
        "level_80_xp_bonus_money_candidate_total_copper": total_bonus_copper,
        "level_80_xp_bonus_money_candidate_total_gold_decimal": round(total_bonus_copper / 10000.0, 2),
        "direct_money_note": "Quest direct-money reward is not yet globally materialized; do not use this subtotal as final Icecrown gold.",
        "dependency_hard_gap_count": len(dependency_gaps),
        "dependency_hard_gaps": dependency_gaps,
        "economy_review_count": len(economy_review),
        "economy_review_tasks": economy_review,
        "unknown_service_count": len(unknown_service_tasks),
        "unknown_service_tasks": unknown_service_tasks,
        "unresolved_objective_review_count": len(unresolved_objective_review_tasks),
        "unresolved_objective_review_tasks": unresolved_objective_review_tasks,
        "tasks": sorted(rows, key=lambda task: int(task["quest_id"])),
    }
    scope = {
        "status": "foundation_scope_started_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "current_level": CURRENT_LEVEL,
        "assigned_task_count": len(assigned),
        "cross_zone_chain_bridge_task_count": len(bridge_tasks),
        "cross_zone_chain_bridge_ids": sorted(bridge_ids),
        "touching_task_count": len(touching),
        "touch_only_ids": sorted(touching_ids - assigned_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "route_candidate_count": len(candidate_ids),
        "dependency_hard_gap_count": len(dependency_gaps),
        "economy_review_count": len(economy_review),
    }
    cluster_payload = {
        "status": "foundation_started_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "cluster_type": "objective_and_extra_objective_targets",
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "clusters": clusters,
    }
    backlog_payload = {
        "status": "icecrown_foundation_review_backlog",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "economy_review_tasks": economy_review,
        "unknown_service_tasks": unknown_service_tasks,
        "unresolved_objective_review_tasks": unresolved_objective_review_tasks,
        "independent_roots": roots,
        "argent_tournament_range_rows": [
            {
                "quest_id": int(task["quest_id"]),
                "name": task.get("name"),
                "scope_status": task.get("scope_status"),
                "scope_reasons": task.get("scope_reasons"),
                "eligibility": task.get("eligibility"),
                "is_daily": task.get("is_daily"),
                "is_repeatable": task.get("is_repeatable"),
            }
            for task in rows
            if 13600 <= int(task["quest_id"]) <= 14199
        ],
        "patch_range_rows": [
            {
                "quest_id": int(task["quest_id"]),
                "name": task.get("name"),
                "scope_status": task.get("scope_status"),
                "scope_reasons": task.get("scope_reasons"),
            }
            for task in rows
            if 24400 <= int(task["quest_id"]) <= 25299
        ],
    }

    OUT_FOUNDATION.write_text(json.dumps(foundation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SCOPE.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_CLUSTERS.write_text(json.dumps(cluster_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_ENTRY.write_text(json.dumps(entry_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_BACKLOG.write_text(json.dumps(backlog_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 冰冠冰川基础任务层审计",
        "",
        "- 当前状态：首组已80级并完成风暴峭壁；冰冠从一开始按满级一次性任务金币清理建模。",
        "- 交通：不学习寒冷天气飞行；继续使用K3借用双足飞龙。13419《作战准备》保持排除，不作为冰冠运输入口。",
        f"- effective Northrend universe归属冰冠：{len(assigned)}项；跨图任务链桥接：{len(bridge_tasks)}项（{sorted(bridge_ids)}）；物理touch：{len(touching)}项；touch-only={sorted(touching_ids - assigned_ids)}。",
        f"- 当前首轮路线候选：{len(candidate_ids)}项；状态统计：`{dict(sorted(status_counts.items()))}`。日常/重复只代表首轮一次，不生成第二轮循环。",
        f"- 候选任务80级XP折金小计：约{round(total_bonus_copper / 10000.0, 2)}G/角色；该数尚未包含普通直接金币和装备/物品变现，不能当整图最终金币。",
        f"- 冰冠内部强制依赖缺口：{len(dependency_gaps)}。",
        f"- 经济待核：{len(economy_review)}项（XP折金=0且无已索引奖励物，直接金币尚未全局物化）；服务时间未知={len(unknown_service_tasks)}；objective review={len(unresolved_objective_review_tasks)}。",
        f"- 真实Target Cluster：{len(clusters)}；多任务共享目标簇：{sum(1 for cluster in clusters if cluster['shared_by_multiple_tasks'])}。",
        "",
        "## 入口决策",
        "",
        f"- 13419《{blocked_transport.get('name')}》：{blocked_transport.get('scope_status')}。继续绕过该任务，但借用双足飞龙先去银色前线基地，不追移动飞艇。",
        f"- 首Hub：13036《{primary_entry.get('name')}》，无显式前置，起点={start_rows(primary_entry)}。完成后同区打开13008/13039/13040三任务簇。",
        f"- 13227《{skipped_breadcrumb.get('name')}》：80级XP折金{((skipped_breadcrumb.get('level_80_economy') or {}).get('xp_bonus_money_gold_decimal'))}G/角色；会因先做13036失效。为它专程追飞艇再折回银色前线基地不划算，正式路线永久跳过。",
        f"- 13224《{natural_airship.get('name')}》由pre_any={natural_airship.get('pre_any') or []}自然解锁，届时第一次登上奥格瑞姆之锤。",
        f"- 12892《{entry_task.get('name')}》：Questie effective关系 pre_any={entry_task.get('pre_any') or []} / pre_all={entry_task.get('pre_all') or []} / parent_active={entry_task.get('parent_active') or []} / available_starting_with={entry_task.get('available_starting_with') or []} / required_spell={entry_task.get('required_spell')}。到13224自然登舰时再现场检查库尔迪拉是否给12892；若不给，只记录本服真实阻断，不把公开旧评论直接写成硬前置。",
        "",
        "## 下一步",
        "",
        "- 先清dependency/economy/objective-review待核项，形成可冻结scope。",
        "- 再按真实目标簇、独立任务Hub、前置解锁与地图几何形成整图初始空间序列；随后逐簇插入并重放交通状态。",
        "- 路线成稿前补齐五开共享/个人机制、component timing、semantic-hud-v45和玩家冷启动/几何/依赖门禁。",
    ]
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "assigned": len(assigned),
                "cross_zone_chain_bridges": sorted(bridge_ids),
                "touching": len(touching),
                "candidate": len(candidate_ids),
                "status_counts": dict(sorted(status_counts.items())),
                "dependency_hard_gaps": len(dependency_gaps),
                "economy_review": len(economy_review),
                "unknown_service": len(unknown_service_tasks),
                "objective_review": len(unresolved_objective_review_tasks),
                "target_clusters": len(clusters),
                "shared_target_clusters": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
                "xp_bonus_gold_per_character_subtotal": round(total_bonus_copper / 10000.0, 2),
                "entry_12892": entry_payload["shadow_vault_entry_probe"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
