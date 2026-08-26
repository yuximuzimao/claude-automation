from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
COLD_AUDIT = ROOT / "data/route-atlas/cold-weather-flying-gate-audit.json"
VIDEO_AUDIT = ROOT / "data/route-atlas/northrend-video-reverse-audit.json"
OVERRIDES = ROOT / "data/route-atlas/sholazar-task-overrides.json"
OUT_SCOPE = ROOT / "data/route-atlas/sholazar-scope-audit.json"
OUT_FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
OUT_CLUSTERS = ROOT / "data/route-atlas/sholazar-target-clusters.json"
OUT_ENTRY = ROOT / "data/route-atlas/sholazar-entry-transition-audit.json"
OUT_REPORT = ROOT / "docs/analysis/2026-08-26-sholazar-foundation-audit.md"

ZONE_ID = 3711
ZONE_NAME = "索拉查盆地"
CURRENT_LEVEL = 80
INBOUND_QUEST_ID = 12521
PREVIOUS_ZONE = "冰冠冰川"
PREVIOUS_PLANNED_ENDPOINT = "奥格瑞姆之锤"
FIRST_LANDING_AREA = "蛮藤谷"
FIRST_CONTACT = "蒙特"


def representative(entity: dict[str, Any]) -> dict[str, float | int | None]:
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
                "representative": representative(source),
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
                "representative": representative(source),
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


def scope_status(task: dict[str, Any], cold_blocked_ids: set[int]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if qid in cold_blocked_ids:
        return "exclude_cold_weather_flying_chain", ["current_route_does_not_learn_cold_weather_flying"]
    if not task.get("race_allowed") or not task.get("npc_faction_allowed"):
        return "exclude_faction", list(task.get("faction_reasons") or ["not_horde_blood_elf"])
    if not task.get("class_allowed"):
        return "exclude_class", ["not_paladin"]
    if task.get("required_skill"):
        return "knowledge_profession", ["requires_profession_or_skill"]
    if task.get("is_deprecated_or_system"):
        return "exclude_deprecated", ["deprecated_or_system"]
    if task.get("is_dungeon") or task.get("is_raid_flagged"):
        return "knowledge_dungeon_or_raid", ["outdoor_route_scope"]
    if task.get("pvp", {}).get("is_pvp") and not task.get("pvp", {}).get("allowed_by_policy"):
        return "knowledge_pvp", ["non_mob_pvp"]
    if task.get("is_repeatable") or task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly"):
        return "knowledge_repeatable_or_calendar", ["one_time_route_default"]
    if task.get("eligibility", {}).get("status") == "conditional":
        return "include_conditional_route_state", list(task.get("eligibility", {}).get("reasons") or ["availability_requires_route_state"])
    if not task.get("xp", {}).get("has_xp"):
        return "include_zero_xp_economic_review", ["one_time_outdoor_zero_xp_not_auto_pruned_at_level_80"]
    return "include_candidate", ["one_time_outdoor_horde_paladin"]


def mandatory_dependencies(task: dict[str, Any]) -> set[int]:
    mandatory = {int(x) for x in (task.get("pre_all") or [])}
    mandatory.update(int(x) for x in (task.get("parent_active") or []))
    pre_any = [int(x) for x in (task.get("pre_any") or [])]
    if len(pre_any) == 1:
        mandatory.add(pre_any[0])
    return mandatory


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    cold = json.loads(COLD_AUDIT.read_text(encoding="utf-8"))
    video = json.loads(VIDEO_AUDIT.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))

    all_tasks = {int(t["quest_id"]): t for t in universe.get("tasks", [])}
    assigned = [dict(t) for t in universe.get("tasks", []) if t.get("assigned_zone_id") == ZONE_ID]
    assigned_ids = {int(t["quest_id"]) for t in assigned}
    touching = [dict(t) for t in universe.get("tasks", []) if ZONE_ID in (t.get("touching_northrend_zone_ids") or [])]
    touch_only_ids = sorted({int(t["quest_id"]) for t in touching} - assigned_ids)

    cold_blocked_ids = {
        int(row["quest_id"])
        for section in ("direct_gates", "dependency_blocked")
        for row in cold.get(section, [])
        if int(row.get("zone_id") or 0) == ZONE_ID
    }
    direct_cold_ids = {
        int(row["quest_id"])
        for row in cold.get("direct_gates", [])
        if int(row.get("zone_id") or 0) == ZONE_ID
    }

    dependency_overrides = {int(qid): dict(value) for qid, value in (overrides.get("dependency_overrides") or {}).items()}
    scope_overrides = {int(qid): dict(value) for qid, value in (overrides.get("scope_overrides") or {}).items()}
    service_overrides = {int(qid): value for qid, value in (overrides.get("manual_service_minutes") or {}).items()}
    objective_required_counts = {int(qid): [int(x) for x in value] for qid, value in (overrides.get("objective_required_counts") or {}).items()}
    mechanism_codes = {int(qid): list(value) for qid, value in (overrides.get("mechanism_codes") or {}).items()}
    mechanism_notes = {int(qid): str(value) for qid, value in (overrides.get("mechanism_notes") or {}).items()}
    review_resolutions = {int(qid): str(value) for qid, value in (overrides.get("objective_review_resolutions") or {}).items()}
    fivebox_resolved = {int(qid): str(value) for qid, value in (overrides.get("fivebox_resolved") or {}).items()}
    fivebox_checks = {int(qid): str(value) for qid, value in (overrides.get("fivebox_checks") or {}).items()}

    rows: list[dict[str, Any]] = []
    for raw in assigned:
        task = dict(raw)
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
                raise RuntimeError(f"objective count override mismatch for {qid}")
            for objective, required_count in zip(objectives, counts):
                objective["required_count"] = required_count
                objective["count_confidence"] = "manual_verified_override"
        if qid in service_overrides:
            value = service_overrides[qid]
            task["intrinsic_service_time"] = {
                "status": "estimated",
                "minutes": float(value["minutes"]),
                "basis": f"manual_pre_route:{value['basis']}",
                "range_minutes": [float(x) for x in value.get("range", [])],
            }
        task["route_mechanism_codes"] = mechanism_codes.get(qid, [])
        task["route_mechanism_note"] = mechanism_notes.get(qid)
        task["objective_review_resolution"] = review_resolutions.get(qid)
        task["fivebox_resolved"] = fivebox_resolved.get(qid, "")
        task["fivebox_check"] = fivebox_checks.get(qid, "")
        status, reasons = scope_status(task, cold_blocked_ids)
        if qid in scope_overrides:
            override = scope_overrides[qid]
            status = str(override["status"])
            reasons = [str(override.get("reason") or "manual_scope_override")]
        task["scope_status"] = status
        task["scope_reasons"] = reasons
        rows.append(task)

    by_id = {int(t["quest_id"]): t for t in rows}
    include_statuses = {"include_candidate", "include_conditional_route_state", "include_zero_xp_economic_review"}
    formal_ids = {int(t["quest_id"]) for t in rows if t["scope_status"] in include_statuses}

    # A repeatable/calendar quest can enter the first-run route only when it is a mandatory
    # structural prerequisite of an already included one-time quest.
    changed = True
    repeatable_promotions: list[dict[str, Any]] = []
    while changed:
        changed = False
        for qid in sorted(formal_ids):
            task = by_id[qid]
            for dep in sorted(mandatory_dependencies(task)):
                dep_task = by_id.get(dep)
                if not dep_task:
                    continue
                if dep_task.get("scope_status") == "knowledge_repeatable_or_calendar":
                    dep_task["scope_status"] = "include_structural_repeatable_first_run"
                    dep_task["scope_reasons"] = [f"mandatory_for_{qid}"]
                    formal_ids.add(dep)
                    repeatable_promotions.append({"quest_id": dep, "name": dep_task.get("name"), "mandatory_for": qid})
                    changed = True
    include_statuses.add("include_structural_repeatable_first_run")

    internal_dependency_gaps: list[dict[str, Any]] = []
    external_dependencies: list[dict[str, Any]] = []
    for qid in sorted(formal_ids):
        task = by_id[qid]
        pre_any = [int(x) for x in (task.get("pre_any") or [])]
        mandatory = mandatory_dependencies(task)
        for dep in sorted(mandatory):
            if dep in assigned_ids:
                if dep not in formal_ids:
                    dep_task = by_id.get(dep) or {}
                    internal_dependency_gaps.append({
                        "quest_id": qid,
                        "name": task.get("name"),
                        "missing_dependency_id": dep,
                        "missing_dependency_name": dep_task.get("name"),
                        "dependency_status": dep_task.get("scope_status"),
                    })
            else:
                dep_task = all_tasks.get(dep) or {}
                external_dependencies.append({
                    "quest_id": qid,
                    "name": task.get("name"),
                    "dependency_id": dep,
                    "dependency_name": dep_task.get("name"),
                    "dependency_zone_id": dep_task.get("assigned_zone_id"),
                    "dependency_zone_name": dep_task.get("assigned_zone_name"),
                    "kind": "mandatory",
                })
        if len(pre_any) > 1 and not any(dep in formal_ids for dep in pre_any if dep in assigned_ids):
            external_reachable = [dep for dep in pre_any if dep not in assigned_ids]
            if external_reachable:
                for dep in external_reachable:
                    dep_task = all_tasks.get(dep) or {}
                    external_dependencies.append({
                        "quest_id": qid,
                        "name": task.get("name"),
                        "dependency_id": dep,
                        "dependency_name": dep_task.get("name"),
                        "dependency_zone_id": dep_task.get("assigned_zone_id"),
                        "dependency_zone_name": dep_task.get("assigned_zone_name"),
                        "kind": "pre_any_external_branch",
                    })

    unknown_service_tasks: list[dict[str, Any]] = []
    unresolved_objective_review_tasks: list[dict[str, Any]] = []
    for qid in sorted(formal_ids):
        task = by_id[qid]
        service = task.get("intrinsic_service_time") or {}
        if not (service.get("status") == "estimated" and isinstance(service.get("minutes"), (int, float))):
            unknown_service_tasks.append({"quest_id": qid, "name": task.get("name"), "service": service})
        review_flags = list(task.get("objective_review") or [])
        if review_flags and not task.get("objective_review_resolution"):
            unresolved_objective_review_tasks.append({"quest_id": qid, "name": task.get("name"), "objective_review": review_flags})

    cluster_map: dict[tuple[str, str], dict[str, Any]] = {}
    for qid in sorted(formal_ids):
        task = by_id[qid]
        for source in objective_sources(task):
            eid = source.get("entity_id")
            if not isinstance(eid, (int, str)):
                continue
            key = (str(source.get("entity_type") or "entity"), str(eid))
            cluster = cluster_map.setdefault(key, {
                "cluster_id": f"{key[0]}:{key[1]}",
                "entity_type": key[0],
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

    inbound = all_tasks.get(INBOUND_QUEST_ID) or {}
    video_maps = video.get("maps") or {}
    video_status = "video_index_contains_sholazar" if any(
        key.lower() == "sholazar" or str(value.get("map") or "") == ZONE_NAME
        for key, value in video_maps.items()
    ) else "no_sholazar_video_in_current_index"

    entry_transition = {
        "status": "pass_current_planned_icecrown_endpoint_revalidate_if_endpoint_changes",
        "validator": "map_transition_contract",
        "previous_zone": PREVIOUS_ZONE,
        "previous_planned_endpoint": PREVIOUS_PLANNED_ENDPOINT,
        "previous_endpoint_state": "current_formal_icecrown_planned_endpoint_but_live_run_not_finished",
        "transport_chain": [
            {
                "from": "奥格瑞姆之锤",
                "to": "银色比武场",
                "action": "K3借用双足飞龙自主飞行",
                "proof": "loaner mount is valid in Icecrown; Icecrown step 1 already opens Argent Tournament Grounds flight point",
            },
            {
                "from": "银色比武场",
                "to": "达拉然",
                "action": "系统飞行",
                "proof": "Argent Tournament Grounds has a WotLK flight-path connection to Dalaran and is already opened in the current Icecrown route",
            },
            {
                "from": "达拉然·大法师伯塔鲁斯",
                "to": "索拉查盆地·蛮藤谷",
                "action": "12521任务脚本运输",
                "proof": "12521 objective text explicitly instructs talking to Pentarus to leave for Sholazar and then speaking with Monte in Wildgrowth Mangal",
            },
        ],
        "inbound_bridge_task": {
            "quest_id": INBOUND_QUEST_ID,
            "name": inbound.get("name"),
            "assigned_zone_id": inbound.get("assigned_zone_id"),
            "assigned_zone_name": inbound.get("assigned_zone_name"),
            "expected_state": "already_accepted_and_carried_from_dalaran",
            "objective_text_zh": inbound.get("objective_text_zh"),
            "extra_objectives": inbound.get("extra_objectives") or [],
        },
        "known_sholazar_entry": {
            "origin_npc": "大法师伯塔鲁斯",
            "origin_zone": "达拉然",
            "transport": "12521任务脚本运输",
            "landing_area": FIRST_LANDING_AREA,
            "first_contact": FIRST_CONTACT,
            "basis": "12521 objective text: talk to Pentarus when ready; after arrival speak with Monte in Wildgrowth Mangal",
        },
        "revalidation_condition": "if the final Icecrown live-run endpoint changes from Orgrim's Hammer, revalidate only the first leg before freezing Sholazar publication",
    }

    status_counts = Counter(str(t.get("scope_status")) for t in rows)
    foundation = {
        "status": "foundation_complete_route_order_not_started",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "profile": "blood-elf-paladin",
        "current_level": CURRENT_LEVEL,
        "strategy": "level-80 outdoor one-time task-gold clear; no cold-weather-flying; structural exclusions only before route optimization",
        "source": universe.get("source"),
        "assigned_task_count": len(assigned),
        "touching_task_count": len(touching),
        "touch_only_ids": touch_only_ids,
        "status_counts": dict(sorted(status_counts.items())),
        "formal_task_count": len(formal_ids),
        "formal_task_ids": sorted(formal_ids),
        "cold_weather_flying_direct_ids": sorted(direct_cold_ids),
        "cold_weather_flying_blocked_ids": sorted(cold_blocked_ids),
        "dependency_hard_gap_count": len(internal_dependency_gaps),
        "dependency_hard_gaps": internal_dependency_gaps,
        "external_dependencies": external_dependencies,
        "repeatable_first_run_promotions": repeatable_promotions,
        "unknown_service_tasks": unknown_service_tasks,
        "unresolved_objective_review_tasks": unresolved_objective_review_tasks,
        "video_status": video_status,
        "entry_transition_status": entry_transition["status"],
        "tasks": sorted(rows, key=lambda t: int(t["quest_id"])),
    }
    scope = {
        "status": "scope_complete_route_order_not_started",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "strategy": foundation["strategy"],
        "assigned_task_count": len(assigned),
        "touching_task_count": len(touching),
        "touch_only_ids": touch_only_ids,
        "status_counts": dict(sorted(status_counts.items())),
        "formal_task_count": len(formal_ids),
        "formal_task_ids": sorted(formal_ids),
        "cold_weather_flying_direct_ids": sorted(direct_cold_ids),
        "cold_weather_flying_blocked_ids": sorted(cold_blocked_ids),
        "dependency_hard_gap_count": len(internal_dependency_gaps),
        "video_status": video_status,
        "entry_transition_status": entry_transition["status"],
    }
    cluster_payload = {
        "status": "foundation_complete_route_order_not_started",
        "zone": {"id": ZONE_ID, "name": ZONE_NAME},
        "cluster_type": "objective_and_extra_objective_targets",
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for c in clusters if c["shared_by_multiple_tasks"]),
        "clusters": clusters,
    }

    OUT_FOUNDATION.write_text(json.dumps(foundation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_SCOPE.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_CLUSTERS.write_text(json.dumps(cluster_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_ENTRY.write_text(json.dumps(entry_transition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 索拉查盆地基础任务层与跨地图入口审计",
        "",
        f"- 当前阶段：80级一次性户外任务金币清理；不学习寒冷天气飞行。",
        f"- effective Northrend universe归属索拉查：{len(assigned)}项；物理touch：{len(touching)}项。",
        f"- 当前正式候选池：{len(formal_ids)}项；状态统计：`{dict(sorted(status_counts.items()))}`。",
        f"- 寒冷天气飞行直接门槛：{sorted(direct_cold_ids)}；连同独占后续递归阻断共{len(cold_blocked_ids)}项：{sorted(cold_blocked_ids)}。",
        f"- 索拉查内部强依赖缺口：{len(internal_dependency_gaps)}；跨图依赖记录：{len(external_dependencies)}。",
        f"- 目标实体簇：{len(clusters)}；多任务共享簇：{sum(1 for c in clusters if c['shared_by_multiple_tasks'])}。",
        f"- 服务时间尚未估计：{len(unknown_service_tasks)}；objective review待人工解析：{len(unresolved_objective_review_tasks)}。这些是后续任务卡建设项，不在foundation阶段伪造为已完成。",
        f"- 视频：`{video_status}`；现有项目视频索引中没有索拉查整图素材，因此本图不安排视频反向审查，除非后续新增素材。",
        "",
        "## 跨地图转场合同",
        "",
        f"- 上一地图：{PREVIOUS_ZONE}；当前正式路线计划终点：{PREVIOUS_PLANNED_ENDPOINT}（冰冠仍在实跑，若最终点改变只重验第一段）。",
        "- 当前计划终点下转场合同已闭合：奥格瑞姆之锤 → K3借用双足飞龙自主飞回已开的银色比武场 → 系统飞行到达拉然 → 大法师伯塔鲁斯执行12521脚本运输 → 索拉查蛮藤谷。",
        f"- 已携带跨图引导：{INBOUND_QUEST_ID}《{inbound.get('name')}》。达拉然阶段只接走，没有触发离城；任务文本明确到达索拉查后在{FIRST_LANDING_AREA}找{FIRST_CONTACT}。",
        "- `map_transition_contract=PASS(current planned Icecrown endpoint)`；正式发布索拉查前若冰冠实跑最终点不再是奥格瑞姆之锤，重新计算上一图出口即可，索拉查脚本落点不变。",
        "",
        "## 强依赖缺口",
        "",
    ]
    lines += [
        f"- {r['quest_id']}《{r['name']}》缺{r['missing_dependency_id']}《{r['missing_dependency_name']}》 status={r['dependency_status']}"
        for r in internal_dependency_gaps
    ] or ["- 无。当前正式候选在索拉查内部没有被scope排除的强制前置缺口。"]
    lines += [
        "",
        "## 跨图依赖",
        "",
    ]
    lines += [
        f"- {r['quest_id']}《{r['name']}》依赖{r['dependency_id']}《{r['dependency_name']}》｜{r['dependency_zone_name']}｜{r['kind']}"
        for r in external_dependencies
    ] or ["- 无。"]
    lines += [
        "",
        "## 重复任务结构提升",
        "",
    ]
    lines += [
        f"- {r['quest_id']}《{r['name']}》被{r['mandatory_for']}作为强制前置引用；这里只标记待人工核对，不代表已确认必须纳入。"
        for r in repeatable_promotions
    ] or ["- 无。"]
    lines += [
        "",
        "## 待补任务卡事实",
        "",
        "### 服务时间未知",
        "",
    ]
    lines += [f"- {r['quest_id']}《{r['name']}》" for r in unknown_service_tasks] or ["- 无。"]
    lines += [
        "",
        "### objective review待人工解析",
        "",
    ]
    lines += [
        f"- {r['quest_id']}《{r['name']}》｜{r['objective_review']}"
        for r in unresolved_objective_review_tasks
    ] or ["- 无。"]
    lines += [
        "",
        "## 下一步",
        "",
        "- 狂心氏族 / 神谕者最终阵营二选一已由用户选择神谕者；狂心最终分支从正式池排除，神谕者结构前置保留。",
        "- 下一步解析当前正式候选的任务卡特殊机制和Target Cluster空间序列；入口合同已PASS，可以开始排索拉查整图顺序。",
    ]
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "assigned": len(assigned),
        "touching": len(touching),
        "formal": len(formal_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "cold_direct": sorted(direct_cold_ids),
        "cold_blocked": sorted(cold_blocked_ids),
        "dependency_hard_gaps": len(internal_dependency_gaps),
        "external_dependencies": len(external_dependencies),
        "repeatable_promotions": repeatable_promotions,
        "unknown_service": len(unknown_service_tasks),
        "unresolved_objective_review": len(unresolved_objective_review_tasks),
        "target_clusters": len(clusters),
        "shared_target_clusters": sum(1 for c in clusters if c["shared_by_multiple_tasks"]),
        "video_status": video_status,
        "entry_transition_status": entry_transition["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
