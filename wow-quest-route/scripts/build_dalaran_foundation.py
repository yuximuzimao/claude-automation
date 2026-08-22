from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import effective_quest_rows
from lib.questie_lua import seq
from lib.questie_source import load_questie
from lib.wotlk_quest_rewards import base_quest_xp_at_level, max_level_bonus_money
from lib.world_builder import QUEST, _ids, _parent_zone, _parse_zone_metadata
from scripts import build_borean_tundra_foundation as shared
from scripts.build_35_55_task_foundation import classify_objectives, classify_task, source_entities_for_item

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
OUT_SCOPE = ROOT / "data/route-atlas/dalaran-scope-audit.json"
OUT_FOUNDATION = ROOT / "data/route-atlas/dalaran-task-foundation.json"
OUT_CLUSTERS = ROOT / "data/route-atlas/dalaran-target-clusters.json"
OUT_REPORT = ROOT / "docs/analysis/2026-08-22-dalaran-foundation-audit.md"

ZONE_ID = 4395
CURRENT_LEVEL = 77
BLOOD_ELF_FLAG = 512
PALADIN_FLAG = 2
DAILY = 4096
WEEKLY = 32768
MONTHLY = 65536
RAID = 64
REPEATABLE = 1
EVENT = 2
SERVER_XP_MULTIPLIER = 2.0
# Canonical remaining Northrend spine after Dalaran. A task physically touching Dalaran but assigned
# outside this set stays in the knowledge layer instead of becoming a current-route breadcrumb.
MAIN_AXIS_ZONE_IDS = {4395, 67, 210, 3711, 66, 394, 495}

# From-zero route state after the current formal Dragonblight route is fully completed.
CARRIED_IN = {12791: "龙骨荒野已接《魔法王国达拉然》并携带进入达拉然"}
# 13419 has requiredLevel=77 in Questie but is additionally gated by learned Cold Weather Flying.
# User live evidence confirmed it is not offered without that skill. The current route intentionally
# does not learn Cold Weather Flying, so keep this transport breadcrumb out of the executable pool;
# Icecrown is entered directly with the K3 loaned wind rider instead.
LIVE_UNAVAILABLE_NOW = {13419: "requires_learned_cold_weather_flying_current_route_uses_k3_loaner_instead"}


def quest_name(data: Any, qid: int, row: dict[Any, Any]) -> str:
    return data.local_name(data.quest_names, qid, str(row.get(1) or f"Quest {qid}"))


def entity_in_zone(entities: list[dict[str, Any]], zone_id: int = ZONE_ID) -> bool:
    return any(zone_id in (entity.get("zones") or []) for entity in entities)


def item_start_sources(data: Any, row: dict[Any, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item_id in _ids(row.get(2), 3):
        npcs, objects = source_entities_for_item(data, int(item_id))
        for entity in [*npcs, *objects]:
            payload = asdict(entity)
            payload["starter_item_id"] = int(item_id)
            result.append(payload)
    return result


def parentize(zones: list[int], parents: dict[int, int]) -> list[int]:
    return sorted({_parent_zone(int(zone), parents) for zone in zones if isinstance(zone, int) and zone > 0})


def current_scope_status(task: dict[str, Any]) -> tuple[str, list[str]]:
    qid = int(task["quest_id"])
    if not task["race_allowed"] or not task["npc_faction_allowed"]:
        return "exclude_faction", list(task.get("faction_reasons") or ["not_horde_blood_elf"])
    if not task["class_allowed"]:
        return "exclude_class", ["not_paladin"]
    if task.get("required_skill"):
        return "knowledge_profession", ["requires_profession_or_skill"]
    if task.get("is_deprecated_or_system"):
        return "exclude_deprecated", ["deprecated_or_system"]
    if task.get("is_dungeon") or task.get("is_raid_flagged"):
        return "knowledge_dungeon_or_raid", ["outdoor_mainline_policy"]
    if task.get("pvp", {}).get("is_pvp") and not task.get("pvp", {}).get("allowed_by_policy"):
        return "knowledge_pvp", ["non_mob_pvp_not_in_outdoor_mainline"]
    if task.get("is_event"):
        return "knowledge_calendar_event", ["event_not_part_of_reusable_baseline"]
    if task.get("is_daily") or task.get("is_weekly") or task.get("is_monthly") or task.get("is_repeatable"):
        return "knowledge_repeatable_or_calendar", ["not_one_time_baseline"]
    # Questie shares some holiday/city NPC spawns with Dalaran. Negative quest level/sort records are
    # retained as knowledge, but they are not part of the reusable Northrend map route.
    quest_level = task.get("quest_level")
    raw_sort = task.get("raw_zone_or_sort")
    if (isinstance(quest_level, int) and quest_level < 0) or (isinstance(raw_sort, int) and raw_sort < 0):
        return "knowledge_event_or_legacy_sort", ["negative_quest_level_or_sort_not_northrend_map_baseline"]
    required_level = task.get("required_level")
    if isinstance(required_level, int) and required_level > 80:
        return "exclude_above_80", [f"required_level_{required_level}"]
    if isinstance(required_level, int) and required_level > CURRENT_LEVEL:
        return "future_level", [f"requires_level_{required_level}"]
    if qid in LIVE_UNAVAILABLE_NOW:
        return "defer_live_unavailable", [LIVE_UNAVAILABLE_NOW[qid]]
    if qid in CARRIED_IN:
        return "include_carried_in_now", [CARRIED_IN[qid]]
    if task.get("start_in_dalaran"):
        assigned = task.get("assigned_zone_id")
        if isinstance(assigned, int) and assigned > 0 and assigned not in MAIN_AXIS_ZONE_IDS:
            return "knowledge_off_axis_outbound", [f"assigned_zone_{assigned}_outside_current_northrend_spine"]
        if task.get("finish_in_dalaran"):
            return "include_local_now", ["one_time_current_level_local"]
        return "include_outbound_breadcrumb_now", ["one_time_current_level_starts_in_dalaran_on_main_axis"]
    if task.get("item_start_in_dalaran"):
        return "conditional_item_trigger", ["requires_item_trigger_from_dalaran_source"]
    if task.get("finish_in_dalaran"):
        return "boundary_turnin_only", ["starts_outside_current_dalaran_route"]
    return "knowledge_touch_only", ["touches_dalaran_but_not_current_start_or_turnin"]


def main() -> None:
    data = load_questie(QUESTIE_ZIP)
    meta = _parse_zone_metadata(QUESTIE_ZIP)

    assigned_ids: set[int] = set()
    touching_ids: set[int] = set()
    for qid, raw_row in data.quests.items():
        if not isinstance(qid, int) or not isinstance(raw_row, dict):
            continue
        if shared.assigned_parent_zone(raw_row, meta["parents"]) == ZONE_ID:
            assigned_ids.add(qid)
        if shared.direct_touches_zone(data, raw_row, ZONE_ID):
            touching_ids.add(qid)
    correction_ids = shared.correction_zone_hints(QUESTIE_ZIP, "DALARAN")
    candidate_ids = assigned_ids | touching_ids | correction_ids
    effective_rows, correction_audit = effective_quest_rows(data, QUESTIE_ZIP, candidate_ids)

    tasks: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()

    for qid in sorted(candidate_ids):
        row = effective_rows.get(qid) or data.quests.get(qid)
        if not isinstance(row, dict):
            continue
        name = quest_name(data, qid, row)
        assigned = shared.assigned_parent_zone(row, meta["parents"])
        objective_zh = shared.localized_objective(data, qid)
        objective_en = shared.english_objective(row)
        preferred_zone = ZONE_ID if shared.direct_touches_zone(data, row, ZONE_ID) else (assigned or ZONE_ID)
        classified, objective_review = classify_objectives(data, row, preferred_zone, objective_zh or objective_en)
        objectives = [asdict(obj) for obj in classified]
        task_class, task_flags = classify_task(classified, objective_en or objective_zh)
        start_entities = shared.entity_group(data, row.get(2))
        finish_entities = shared.entity_group(data, row.get(3))
        item_sources = item_start_sources(data, row)
        extra = shared.extract_extra_objectives(data, row, preferred_zone)

        start_zones = parentize(shared.entity_zones(start_entities), meta["parents"])
        finish_zones = parentize(shared.entity_zones(finish_entities), meta["parents"])
        objective_zones = parentize(shared.objective_route_zones(objectives, preferred_zone), meta["parents"])
        extra_zones = parentize(sorted({int(zone) for item in extra for zone in item.get("route_zones", []) if isinstance(zone, int)}), meta["parents"])
        item_start_zones = parentize(shared.entity_zones(item_sources), meta["parents"])
        all_route_zones = sorted(set(start_zones + finish_zones + objective_zones + extra_zones + item_start_zones + ([assigned] if assigned else [])))

        race_allowed = shared.bit_allows(row.get(6), BLOOD_ELF_FLAG)
        class_allowed = shared.bit_allows(row.get(7), PALADIN_FLAG)
        npc_allowed, faction_reasons = shared.npc_faction_eligibility(data, row)
        qflags = int(row.get(23) or 0)
        sflags = int(row.get(24) or 0)
        is_repeatable = bool(sflags & REPEATABLE)
        is_event = bool(sflags & EVENT)
        is_daily = bool(qflags & DAILY)
        is_weekly = bool(qflags & WEEKLY)
        is_monthly = bool(qflags & MONTHLY)
        lower_name = name.lower()
        is_deprecated = "deprecated" in lower_name or "deprecaed" in lower_name or "????" in name or name.strip(" ?") == ""
        is_dungeon = any(zone in meta["dungeons"] for zone in all_route_zones)
        pvp = shared.pvp_classification(row, name, objective_en or objective_zh, objectives)
        deps = shared.dependency_ids(row)

        required_level = row.get(4)
        qlevel = row.get(5)
        current_xp = base_quest_xp_at_level(data, qid, CURRENT_LEVEL) * SERVER_XP_MULTIPLIER
        task: dict[str, Any] = {
            "quest_id": qid,
            "name": name,
            "english_name": str(row.get(1) or ""),
            "assigned_zone_id": assigned,
            "raw_zone_or_sort": row.get(17),
            "required_level": required_level,
            "quest_level": qlevel,
            "required_races": row.get(6),
            "required_classes": row.get(7),
            "required_skill": row.get(18),
            "quest_flags": qflags,
            "special_flags": sflags,
            "race_allowed": race_allowed,
            "class_allowed": class_allowed,
            "npc_faction_allowed": npc_allowed,
            "faction_reasons": faction_reasons,
            "is_repeatable": is_repeatable,
            "is_event": is_event,
            "is_daily": is_daily,
            "is_weekly": is_weekly,
            "is_monthly": is_monthly,
            "is_raid_flagged": bool(qflags & RAID),
            "is_deprecated_or_system": is_deprecated,
            "is_dungeon": is_dungeon,
            "pvp": pvp,
            "start_entities": start_entities,
            "finish_entities": finish_entities,
            "item_start_sources": item_sources,
            "start_zones": start_zones,
            "turnin_zones": finish_zones,
            "objective_zones": objective_zones,
            "extra_objective_zones": extra_zones,
            "item_start_zones": item_start_zones,
            "all_route_zones": all_route_zones,
            "assigned_to_dalaran": assigned == ZONE_ID,
            "start_in_dalaran": entity_in_zone(start_entities),
            "finish_in_dalaran": entity_in_zone(finish_entities),
            "item_start_in_dalaran": entity_in_zone(item_sources),
            "objective_in_dalaran": ZONE_ID in objective_zones or ZONE_ID in extra_zones,
            "correction_hint": qid in correction_ids,
            "objective_text_zh": objective_zh,
            "objective_text_en": objective_en,
            "objectives": objectives,
            "extra_objectives": extra,
            "objective_review": objective_review,
            "task_class": task_class,
            "task_flags": task_flags,
            "pre_any": deps["pre_any"],
            "pre_all": deps["pre_all"],
            "parent_active": deps["parent_active"],
            "next_quest": row.get(22),
            "child_quests": [int(x) for x in seq(row.get(14)) if isinstance(x, int)],
            "breadcrumb_for": row.get(27),
            "breadcrumbs": [int(x) for x in seq(row.get(28)) if isinstance(x, int)],
            "xp": {
                "server_xp_at_level_77": int(current_xp),
                "max_level_bonus_money": max_level_bonus_money(data, qid, qflags),
            },
        }
        status, reasons = current_scope_status(task)
        task["scope_status"] = status
        task["scope_reasons"] = reasons
        tasks.append(task)
        status_counts[status] += 1
        level_counts[str(required_level)] += 1

    current_ids = sorted(int(t["quest_id"]) for t in tasks if t["scope_status"].startswith("include_"))
    local_ids = sorted(int(t["quest_id"]) for t in tasks if t["scope_status"] in {"include_carried_in_now", "include_local_now"})
    outbound_ids = sorted(int(t["quest_id"]) for t in tasks if t["scope_status"] == "include_outbound_breadcrumb_now")

    # Dalaran route clusters are NPC/service clusters, not outdoor kill-density clusters.
    clusters: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for task in tasks:
        if int(task["quest_id"]) not in current_ids:
            continue
        for role, entities in (("start", task["start_entities"]), ("finish", task["finish_entities"])):
            for entity in entities:
                if ZONE_ID not in (entity.get("zones") or []):
                    continue
                eid = entity.get("entity_id")
                etype = str(entity.get("entity_type") or "entity")
                if not isinstance(eid, int):
                    continue
                key = (etype, eid)
                rep = (entity.get("representative_by_zone") or {}).get(str(ZONE_ID)) or {}
                existing = next((c for c in clusters if (c["entity_type"], c["entity_id"]) == key), None)
                relation = {"quest_id": int(task["quest_id"]), "name": task["name"], "role": role}
                if existing:
                    existing["relations"].append(relation)
                    existing["quest_ids"] = sorted(set(existing["quest_ids"] + [int(task["quest_id"])]))
                else:
                    clusters.append({
                        "entity_type": etype,
                        "entity_id": eid,
                        "name": entity.get("name"),
                        "representative": {"x": rep.get("x"), "y": rep.get("y")},
                        "quest_ids": [int(task["quest_id"])],
                        "relations": [relation],
                    })
                seen.add(key)
    clusters.sort(key=lambda c: (float(c["representative"].get("x") or 999), float(c["representative"].get("y") or 999), c["name"] or ""))

    scope_payload = {
        "status": "foundation_scope_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": "达拉然"},
        "profile": "blood-elf-paladin",
        "current_level": CURRENT_LEVEL,
        "from_zero_entry_state": {
            "previous_zone": "龙骨荒野",
            "dragonblight_complete": True,
            "carried_in_quest_ids": sorted(CARRIED_IN),
        },
        "source": {"questie_version": data.version, "source_sha256": data.source_sha256},
        "candidate_recall": {
            "assigned_count": len(assigned_ids),
            "direct_touch_count": len(touching_ids),
            "correction_hint_count": len(correction_ids),
            "union_count": len(candidate_ids),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "current_formal_ids": current_ids,
        "local_close_now_ids": local_ids,
        "outbound_breadcrumb_now_ids": outbound_ids,
        "rows": [
            {
                "quest_id": int(t["quest_id"]),
                "name": t["name"],
                "required_level": t["required_level"],
                "quest_level": t["quest_level"],
                "scope_status": t["scope_status"],
                "scope_reasons": t["scope_reasons"],
                "assigned_to_dalaran": t["assigned_to_dalaran"],
                "start_in_dalaran": t["start_in_dalaran"],
                "finish_in_dalaran": t["finish_in_dalaran"],
                "item_start_in_dalaran": t["item_start_in_dalaran"],
                "objective_in_dalaran": t["objective_in_dalaran"],
                "correction_hint": t["correction_hint"],
            }
            for t in tasks
        ],
    }
    foundation_payload = {
        "status": "foundation_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": "达拉然"},
        "profile": "blood-elf-paladin",
        "current_level": CURRENT_LEVEL,
        "source": {"questie_version": data.version, "source_sha256": data.source_sha256},
        "correction_audit": correction_audit,
        "current_formal_task_count": len(current_ids),
        "current_formal_task_ids": current_ids,
        "local_close_now_ids": local_ids,
        "outbound_breadcrumb_now_ids": outbound_ids,
        "knowledge_task_count": len(tasks),
        "tasks": tasks,
    }
    cluster_payload = {
        "status": "foundation_complete_route_not_yet_frozen",
        "zone": {"id": ZONE_ID, "name": "达拉然"},
        "cluster_count": len(clusters),
        "clusters": clusters,
    }

    OUT_SCOPE.write_text(json.dumps(scope_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_FOUNDATION.write_text(json.dumps(foundation_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_CLUSTERS.write_text(json.dumps(cluster_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_status: dict[str, list[dict[str, Any]]] = {}
    for task in tasks:
        by_status.setdefault(task["scope_status"], []).append(task)
    lines = [
        "# 达拉然基础任务层审计（77级血精灵圣骑士）",
        "",
        "- 入口状态：从零路线按龙骨荒野整图完成后进入达拉然；12791《魔法王国达拉然》已携带。",
        f"- Questie：{data.version} / {data.source_sha256}",
        f"- 旧式assigned-to-Dalaran仅{len(assigned_ids)}项；物理触碰达拉然召回{len(touching_ids)}项；修正层提示{len(correction_ids)}项；并集{len(candidate_ids)}项。",
        f"- 当前77级一次性正式池：{len(current_ids)}项；本地可闭合：{len(local_ids)}项；达拉然起点跨图面包屑：{len(outbound_ids)}项。",
        f"- scope状态：`{dict(sorted(status_counts.items()))}`。",
        "",
        "## 当前正式池",
        "",
    ]
    for task in tasks:
        if int(task["quest_id"]) in current_ids:
            lines.append(
                f"- {task['quest_id']}《{task['name']}》｜Lv{task['required_level']}｜{task['scope_status']}｜"
                f"startD={task['start_in_dalaran']} finishD={task['finish_in_dalaran']}｜next={task['next_quest']}"
            )
    lines.extend(["", "## 其它分类计数", ""])
    for status, rows in sorted(by_status.items()):
        if status.startswith("include_"):
            continue
        lines.append(f"- {status}: {len(rows)}")
    lines.extend([
        "",
        "## 发布前仍需完成",
        "",
        "- 对6项当前正式池逐项核对NPC、触发动作、跨图目的地、是否立即执行/提前接取、任务日志成本。",
        "- 单独审计三个物品触发达拉然交付任务的来源；没有触发物时不得让玩家主动在达拉然寻找接取NPC。",
        "- 对80级后达拉然/冰冠链保留知识，不进入77级玩家路线。",
        "- 完成Dalaran Hub几何顺序、预计时间、任务日志峰值、玩家冷启动和对抗式复审后，才能写入正式Route Atlas。",
    ])
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "candidate_union": len(candidate_ids),
        "status_counts": dict(sorted(status_counts.items())),
        "current_formal_ids": current_ids,
        "local_close_now_ids": local_ids,
        "outbound_breadcrumb_now_ids": outbound_ids,
        "cluster_count": len(clusters),
        "outputs": [str(p.relative_to(ROOT)) for p in (OUT_SCOPE, OUT_FOUNDATION, OUT_CLUSTERS, OUT_REPORT)],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
