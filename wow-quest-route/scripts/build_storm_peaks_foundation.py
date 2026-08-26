from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OUT_SCOPE = ROOT / "data/route-atlas/storm-peaks-scope-audit.json"
OUT_FOUNDATION = ROOT / "data/route-atlas/storm-peaks-task-foundation.json"
OUT_CLUSTERS = ROOT / "data/route-atlas/storm-peaks-target-clusters.json"
OUT_K3 = ROOT / "data/route-atlas/storm-peaks-k3-entry-audit.json"
OUT_REPORT = ROOT / "docs/analysis/2026-08-22-storm-peaks-foundation-audit.md"
OVERRIDES = ROOT / "data/route-atlas/storm-peaks-task-overrides.json"

ZONE_ID = 67
ZONE_NAME = "风暴峭壁"
CURRENT_LEVEL = 77
INBOUND_QUEST_ID = 12853
# 12930 is an outdoor Storm Peaks quest. The global `is_dungeon` proxy is polluted because its
# generic Frostweave Cloth requirement expands to dungeon drop sources; its actual Enchanted Earth
# objective and both quest NPCs are in Storm Peaks.
DUNGEON_FALSE_POSITIVE_IDS = {12930}
# User live run confirmed these calendar quests should be treated like ordinary tasks for the first
# execution when their content is useful on the current route. They remain first-run-only; this does
# not generate a second daily/repeatable loop.
CALENDAR_FIRST_RUN_INCLUDE_IDS = {12981, 12994, 13006, 13046}
# Questie contains two source-less records that are not executable Horde one-time quests in the
# current WotLK route: 13053 is the removed beta Cold Weather Flying test-flight quest; 13417 is a
# source-less duplicate/wrapper of the Alliance Bronzebeard finale rather than a Horde pickup.
MANUAL_EXCLUDE_IDS = {
    13053: "removed_wotlk_cold_weather_flying_test_quest",
    13417: "source_less_alliance_bronzebeard_duplicate_not_horde_route",
}


def status_for(task: dict[str, Any]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if qid in MANUAL_EXCLUDE_IDS:
        return "exclude_manual_non_executable", [MANUAL_EXCLUDE_IDS[qid]]
    if task.get("cold_weather_flying_gate"):
        return "exclude_cold_weather_flying_gate", ["current_route_intentionally_does_not_learn_cold_weather_flying"]
    if not task.get("race_allowed") or not task.get("npc_faction_allowed"): 
        return "exclude_faction", list(task.get("faction_reasons") or ["not_horde_blood_elf"])
    if not task.get("class_allowed"):
        return "exclude_class", ["not_paladin"]
    if task.get("required_skill"):
        return "knowledge_profession", ["requires_profession_or_skill"]
    if task.get("is_deprecated_or_system"):
        return "exclude_deprecated", ["deprecated_or_system"]
    if (task.get("is_dungeon") and int(task["quest_id"]) not in DUNGEON_FALSE_POSITIVE_IDS) or task.get("is_raid_flagged"):
        return "knowledge_dungeon_or_raid", ["outdoor_mainline_policy"]
    if task.get("pvp", {}).get("is_pvp") and not task.get("pvp", {}).get("allowed_by_policy"):
        return "knowledge_pvp", ["non_mob_pvp"]
    if qid in CALENDAR_FIRST_RUN_INCLUDE_IDS:
        if task.get("eligibility", {}).get("status") == "conditional":
            return "include_verified_calendar_first_run_conditional", list(task.get("eligibility", {}).get("reasons") or ["calendar_first_run_route_state"])
        return "include_verified_calendar_first_run", ["user_verified_same_route_content_first_run_only"]
    if task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly"):
        return "knowledge_repeatable_or_calendar", ["not_yet_verified_for_first_route_run"]
    if task.get("eligibility", {}).get("status") == "conditional":
        return "include_conditional_route_state", list(task.get("eligibility", {}).get("reasons") or ["availability_requires_route_state"])
    if not task.get("xp", {}).get("has_xp"):
        return "exclude_no_xp_pending_dependency", ["no_xp"]
    return "include_candidate", ["one_time_outdoor_horde_paladin_xp"]


def rep(entity: dict[str, Any]) -> dict[str, float | int | None]:
    row = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
    return {"x": row.get("x"), "y": row.get("y"), "spawn_count": row.get("spawn_count")}


def objective_sources(task: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    qid = int(task["quest_id"])
    for objective_index, objective in enumerate(task.get("objectives") or [], start=1):
        for source in objective.get("sources") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rows.append({
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
            })
    for extra in task.get("extra_objectives") or []:
        extra_index = int(extra.get("index") or 0)
        for source in extra.get("references") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rows.append({
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
            })
        for coord_index, coord in enumerate((extra.get("coordinates_by_zone") or {}).get(str(ZONE_ID)) or [], start=1):
            if not isinstance(coord, list) or len(coord) < 2:
                continue
            rows.append({
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
                "representative": {"x": float(coord[0]), "y": float(coord[1]), "spawn_count": 1},
                "spawn_count": 1,
                "source_kind": "extra_coordinate",
                "extra_text": extra.get("text"),
            })
    return rows


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    service_overrides = {int(qid): value for qid, value in (overrides.get("manual_service_minutes") or {}).items()}
    objective_required_counts = {int(qid): [int(x) for x in value] for qid, value in (overrides.get("objective_required_counts") or {}).items()}
    mechanism_codes = {int(qid): list(value) for qid, value in (overrides.get("mechanism_codes") or {}).items()}
    mechanism_notes = {int(qid): str(value) for qid, value in (overrides.get("mechanism_notes") or {}).items()}
    review_resolutions = {int(qid): str(value) for qid, value in (overrides.get("objective_review_resolutions") or {}).items()}
    fivebox_resolved = {int(qid): str(value) for qid, value in (overrides.get("fivebox_resolved") or {}).items()}
    fivebox_checks = {int(qid): str(value) for qid, value in (overrides.get("fivebox_checks") or {}).items()}
    scope_overrides = {int(qid): dict(value) for qid, value in (overrides.get("scope_overrides") or {}).items()}
    dependency_overrides = {int(qid): dict(value) for qid, value in (overrides.get("dependency_overrides") or {}).items()}
    assigned = [dict(t) for t in universe.get("tasks", []) if t.get("assigned_zone_id") == ZONE_ID]
    touching = [dict(t) for t in universe.get("tasks", []) if ZONE_ID in (t.get("touching_northrend_zone_ids") or [])]
    assigned_ids = {int(t["quest_id"]) for t in assigned}
    touching_ids = {int(t["quest_id"]) for t in touching}
    touch_only = sorted(touching_ids - assigned_ids)

    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for task in assigned:
        qid = int(task["quest_id"])
        if qid in dependency_overrides:
            override = dependency_overrides[qid]
            for field in ("pre_any", "pre_all", "parent_active"):
                if field in override:
                    task[field] = [int(x) for x in (override.get(field) or [])]
            task["dependency_override_basis"] = override.get("basis")
        if qid in objective_required_counts:
            counts = objective_required_counts[qid]
            objectives = task.get("objectives") or []
            if len(objectives) != len(counts):
                raise RuntimeError(f"objective count override length mismatch for {qid}: objectives={len(objectives)} override={len(counts)}")
            for objective, required_count in zip(objectives, counts):
                objective["required_count"] = required_count
                objective["count_confidence"] = "manual_verified_override"
        if qid in service_overrides:
            override = service_overrides[qid]
            task["intrinsic_service_time"] = {
                "status": "estimated",
                "minutes": float(override["minutes"]),
                "basis": f"manual_pre_route:{override['basis']}",
                "range_minutes": [float(x) for x in override.get("range", [])],
            }
        task["route_mechanism_codes"] = mechanism_codes.get(qid, [])
        task["route_mechanism_note"] = mechanism_notes.get(qid)
        task["objective_review_resolution"] = review_resolutions.get(qid)
        task["fivebox_resolved"] = fivebox_resolved.get(qid, "")
        task["fivebox_check"] = fivebox_checks.get(qid, "")
        status, reasons = status_for(task)
        if qid in scope_overrides:
            override = scope_overrides[qid]
            status = str(override["status"])
            reasons = [str(override.get("reason") or "user_live_scope_override")]
        task["scope_status"] = status
        task["scope_reasons"] = reasons
        rows.append(task)
        status_counts[status] += 1
    by_id = {int(t["quest_id"]): t for t in rows}

    formal_ids = {
        int(t["quest_id"])
        for t in rows
        if t["scope_status"] in {
            "include_candidate",
            "include_conditional_route_state",
            "include_verified_calendar_first_run",
            "include_verified_calendar_first_run_conditional",
        }
    }

    # Promote zero-XP records only when they are the unique/mandatory dependency of a formal task.
    changed = True
    while changed:
        changed = False
        for qid in sorted(formal_ids):
            task = by_id.get(qid)
            if not task:
                continue
            mandatory = set(task.get("pre_all") or []) | set(task.get("parent_active") or [])
            pre_any = list(task.get("pre_any") or [])
            if len(pre_any) == 1:
                mandatory.add(int(pre_any[0]))
            for dep in mandatory:
                dep_task = by_id.get(int(dep))
                if dep_task and dep_task.get("scope_status") == "exclude_no_xp_pending_dependency":
                    dep_task["scope_status"] = "include_structural_zero_xp_prerequisite"
                    dep_task["scope_reasons"] = [f"mandatory_for_{qid}"]
                    formal_ids.add(int(dep))
                    changed = True
    for task in rows:
        if task.get("scope_status") == "exclude_no_xp_pending_dependency":
            task["scope_status"] = "exclude_no_xp"
            task["scope_reasons"] = ["no_xp_not_mandatory_for_current_formal_pool"]

    # Recount after zero-XP dependency promotion.
    status_counts = Counter(t["scope_status"] for t in rows)

    # Dependency audit: only a missing mandatory dependency that itself belongs to Storm Peaks is hard.
    dependency_gaps: list[dict[str, Any]] = []
    for qid in sorted(formal_ids):
        task = by_id[qid]
        mandatory = set(int(x) for x in (task.get("pre_all") or [])) | set(int(x) for x in (task.get("parent_active") or []))
        pre_any = [int(x) for x in (task.get("pre_any") or [])]
        if len(pre_any) == 1:
            mandatory.add(pre_any[0])
        for dep in sorted(mandatory):
            if dep in assigned_ids and dep not in formal_ids:
                dep_task = by_id.get(dep) or {}
                dependency_gaps.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "missing_dependency_id": dep,
                    "missing_dependency_name": dep_task.get("name"),
                    "dependency_status": dep_task.get("scope_status"),
                })

    unknown_service_tasks: list[dict[str, Any]] = []
    unresolved_objective_review_tasks: list[dict[str, Any]] = []
    for qid in sorted(formal_ids):
        task = by_id[qid]
        service = task.get("intrinsic_service_time") or {}
        service_ready = service.get("status") == "estimated" and isinstance(service.get("minutes"), (int, float))
        review_flags = list(task.get("objective_review") or [])
        review_ready = not review_flags or bool(task.get("objective_review_resolution"))
        task["task_card_status"] = "ready_for_route" if service_ready and review_ready else "needs_manual_review"
        if not service_ready:
            unknown_service_tasks.append({"quest_id": qid, "name": task.get("name"), "service": service})
        if not review_ready:
            unresolved_objective_review_tasks.append({
                "quest_id": qid,
                "name": task.get("name"),
                "objective_review": review_flags,
            })

    # True Target Clusters: objective entities and extra-objective anchors, not accept/turn-in NPCs.
    cluster_map: dict[tuple[str, str], dict[str, Any]] = {}
    for qid in sorted(formal_ids):
        task = by_id[qid]
        for source in objective_sources(task):
            eid = source.get("entity_id")
            if not isinstance(eid, (int, str)):
                continue
            etype = str(source.get("entity_type") or "entity")
            key = (etype, str(eid))
            cluster = cluster_map.setdefault(key, {
                "cluster_id": f"{etype}:{eid}",
                "entity_type": etype,
                "entity_id": eid,
                "name": source.get("entity_name"),
                "representative": source.get("representative") or {},
                "spawn_count": source.get("spawn_count"),
                "quest_ids": [],
                "relations": [],
                "source_kinds": [],
            })
            cluster["quest_ids"].append(qid)
            cluster["relations"].append(source)
            cluster["source_kinds"].append(source.get("source_kind") or "objective")
    clusters = list(cluster_map.values())
    for cluster in clusters:
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["source_kinds"] = sorted(set(cluster["source_kinds"]))
        cluster["shared_by_multiple_tasks"] = len(cluster["quest_ids"]) > 1
    clusters.sort(key=lambda c: (
        -len(c["quest_ids"]),
        float((c.get("representative") or {}).get("y") or 999),
        float((c.get("representative") or {}).get("x") or 999),
        str(c.get("name") or ""),
    ))

    # Canonical first-arrival K3 scan. These are the quests currently offered without Storm prerequisites.
    k3_box = (37.0, 44.0, 82.0, 89.0)
    k3_rows: list[dict[str, Any]] = []
    for qid in sorted(formal_ids):
        task = by_id[qid]
        starts = []
        for entity in task.get("start_entities") or []:
            r = rep(entity)
            x, y = r.get("x"), r.get("y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)) and k3_box[0] <= x <= k3_box[1] and k3_box[2] <= y <= k3_box[3]:
                starts.append({"name": entity.get("name"), "entity_id": entity.get("entity_id"), **r})
        if starts:
            k3_rows.append({
                "quest_id": qid,
                "name": task.get("name"),
                "scope_status": task.get("scope_status"),
                "pre_any": task.get("pre_any") or [],
                "pre_all": task.get("pre_all") or [],
                "parent_active": task.get("parent_active") or [],
                "next_quest": task.get("next_quest"),
                "task_class": task.get("task_class"),
                "starts": starts,
                "objective_text_zh": task.get("objective_text_zh"),
                "objectives": task.get("objectives") or [],
                "xp": task.get("xp"),
            })
    initial_k3 = [
        row for row in k3_rows
        if not row["pre_any"] and not row["pre_all"] and not row["parent_active"]
    ]

    foundation = {
        "status": "foundation_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "profile": "blood-elf-paladin",
        "current_level": CURRENT_LEVEL,
        "source": universe.get("source"),
        "assigned_task_count": len(assigned),
        "touching_task_count": len(touching),
        "touch_only_ids": touch_only,
        "status_counts": dict(sorted(status_counts.items())),
        "formal_task_count": len(formal_ids),
        "formal_task_ids": sorted(formal_ids),
        "dependency_hard_gap_count": len(dependency_gaps),
        "dependency_hard_gaps": dependency_gaps,
        "task_card_ready_count": len(formal_ids) - len({row["quest_id"] for row in unknown_service_tasks} | {row["quest_id"] for row in unresolved_objective_review_tasks}),
        "unknown_service_tasks": unknown_service_tasks,
        "unresolved_objective_review_tasks": unresolved_objective_review_tasks,
        "tasks": sorted(rows, key=lambda t: int(t["quest_id"])),
    }
    scope = {
        "status": "foundation_scope_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "assigned_task_count": len(assigned),
        "touching_task_count": len(touching),
        "touch_only_ids": touch_only,
        "status_counts": dict(sorted(status_counts.items())),
        "formal_task_count": len(formal_ids),
        "dependency_hard_gap_count": len(dependency_gaps),
    }
    cluster_payload = {
        "status": "foundation_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "cluster_type": "objective_and_extra_objective_targets",
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "clusters": clusters,
    }
    k3_payload = {
        "status": "k3_entry_scan_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "inbound_breadcrumb_id": INBOUND_QUEST_ID,
        "hard_transport_action": {
            "npc": "“诚实的”麦克斯",
            "coordinate": [40.6, 84.6],
            "condition": "level >= 77 and no Cold Weather Flying",
            "action": "five characters obtain Loaned Wind Rider Reins before questing",
            "usable_zones": [67, 210, 3711],
        },
        "all_k3_start_rows": k3_rows,
        "initial_no_storm_prereq_rows": initial_k3,
        "initial_no_storm_prereq_ids": [int(row["quest_id"]) for row in initial_k3],
    }

    OUT_FOUNDATION.write_text(json.dumps(foundation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SCOPE.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_CLUSTERS.write_text(json.dumps(cluster_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_K3.write_text(json.dumps(k3_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 风暴峭壁基础任务层审计",
        "",
        "- 从零入口：达拉然完成当前77级清理后，携带12853《豪华的体验！》从晶歌森林地面进入K3。",
        f"- effective Northrend universe归属风暴峭壁：{len(assigned)}项；物理touch：{len(touching)}项；touch-only={touch_only}。",
        f"- 当前户外一次性正式池：{len(formal_ids)}项；状态统计：`{dict(sorted(status_counts.items()))}`。",
        f"- Storm内部强制依赖缺口：{len(dependency_gaps)}。",
        f"- 任务卡门禁：ready={len(formal_ids) - len({row['quest_id'] for row in unknown_service_tasks} | {row['quest_id'] for row in unresolved_objective_review_tasks})}/{len(formal_ids)}；服务时间未知={len(unknown_service_tasks)}；objective review未解析={len(unresolved_objective_review_tasks)}。",
        f"- 真实目标簇：{len(clusters)}；多任务共享目标簇：{sum(1 for cluster in clusters if cluster['shared_by_multiple_tasks'])}。目标簇只使用objective/extraObjective，不再拿接交NPC冒充任务目标。",
        f"- K3范围内正式任务起点：{len(k3_rows)}项；无Storm前置、首到即可接：{[row['quest_id'] for row in initial_k3]}。",
        "- K3入口硬交通动作：五号先找“诚实的”麦克斯领取借用双足飞龙；未取得前不开始大范围Storm目标路线。",
        "- 声望条件任务保留为路线状态解锁；已由首跑确认与当前路线内容等价且顺路的12981/12994/13006/13046按第一轮普通任务处理，只做本轮一次，不生成第二轮日常/重复循环。",
        "",
        "## K3首到即可接",
        "",
    ]
    for row in initial_k3:
        lines.append(f"- {row['quest_id']}《{row['name']}》｜{row['task_class']}｜接：{', '.join(x['name'] for x in row['starts'])}")
    lines.extend([
        "",
        "## 下一步",
        "",
        "- 先设计K3入口小圈：12853交付 → 借用飞行坐骑 → 开K3飞行点 → 首到任务一次接齐。",
        "- 再按Target Cluster构造整图顺序，随后做五开机制/任务日志/时间/玩家冷启动/整图几何对抗审查。",
    ])
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "assigned": len(assigned),
        "touching": len(touching),
        "formal": len(formal_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "dependency_hard_gaps": len(dependency_gaps),
        "task_card_ready": len(formal_ids) - len({row["quest_id"] for row in unknown_service_tasks} | {row["quest_id"] for row in unresolved_objective_review_tasks}),
        "unknown_service": len(unknown_service_tasks),
        "unresolved_objective_review": len(unresolved_objective_review_tasks),
        "target_clusters": len(clusters),
        "shared_target_clusters": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "k3_all": len(k3_rows),
        "k3_initial_ids": [int(row["quest_id"]) for row in initial_k3],
        "outputs": [str(p.relative_to(ROOT)) for p in (OUT_SCOPE, OUT_FOUNDATION, OUT_CLUSTERS, OUT_K3, OUT_REPORT)],
    }, ensure_ascii=False, indent=2))

    if dependency_gaps or unknown_service_tasks or unresolved_objective_review_tasks:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
