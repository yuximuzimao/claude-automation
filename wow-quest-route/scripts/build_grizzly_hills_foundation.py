from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
SCOPE = ROOT / "data/route-atlas/grizzly-hills-scope-audit.json"
OUT = ROOT / "data/route-atlas/grizzly-hills-task-foundation.json"
CLUSTERS = ROOT / "data/route-atlas/grizzly-hills-target-clusters.json"
REPORT = ROOT / "docs/analysis/2026-08-18-grizzly-hills-foundation-audit.md"
ZONE_ID = 394

# Dependencies satisfied outside the Grizzly formal pool by the route entry state or an alternate branch.
# Keep this explicit so an apparent dependency gap cannot silently pass.
EXTERNAL_DEPENDENCY_FACTS = {
    12487: "carried_in_from_dragonblight_and_turned_in_at_conquest_hold_entry",
}


def objective_sources_in_zone(task: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for objective in task.get("objectives") or []:
        for source in objective.get("sources") or []:
            if ZONE_ID in (source.get("zones") or []):
                result.append({
                    "quest_id": int(task["quest_id"]),
                    "quest_name": task.get("name"),
                    "objective_type": objective.get("objective_type"),
                    "required_count": objective.get("required_count"),
                    "item_id": objective.get("item_id"),
                    "entity_type": source.get("entity_type"),
                    "entity_id": source.get("entity_id"),
                    "entity_name": source.get("name"),
                    "representative": (source.get("representative_by_zone") or {}).get(str(ZONE_ID)),
                    "spawn_count": source.get("spawn_count"),
                })
    return result


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    all_tasks = {int(task["quest_id"]): task for task in universe.get("tasks", [])}
    formal_ids = {int(qid) for qid in scope.get("formal_candidate_ids", [])}
    tasks = []
    for qid in sorted(formal_ids):
        if qid not in all_tasks:
            continue
        task = dict(all_tasks[qid])
        task["scope_status"] = "include_current_full_clear"
        task["is_primary_candidate"] = True
        tasks.append(task)

    dependency_rows: list[dict[str, Any]] = []
    hard_gaps: list[dict[str, Any]] = []
    for task in tasks:
        qid = int(task["quest_id"])
        pre_any = [int(x) for x in (task.get("pre_any") or [])]
        pre_all = [int(x) for x in (task.get("pre_all") or [])]
        parent = [int(x) for x in (task.get("parent_active") or [])]
        mandatory = set(pre_all + parent)
        if len(pre_any) == 1:
            mandatory.add(pre_any[0])

        missing_mandatory = sorted(dep for dep in mandatory if dep not in formal_ids and dep not in EXTERNAL_DEPENDENCY_FACTS)
        pre_any_formal = sorted(dep for dep in pre_any if dep in formal_ids)
        pre_any_external = sorted(dep for dep in pre_any if dep in EXTERNAL_DEPENDENCY_FACTS)
        pre_any_outside = sorted(dep for dep in pre_any if dep not in formal_ids and dep not in EXTERNAL_DEPENDENCY_FACTS)
        alternative_ok = not pre_any or bool(pre_any_formal or pre_any_external)

        row = {
            "quest_id": qid,
            "name": task.get("name"),
            "pre_any": pre_any,
            "pre_all": pre_all,
            "parent_active": parent,
            "missing_mandatory": missing_mandatory,
            "pre_any_formal": pre_any_formal,
            "pre_any_external": pre_any_external,
            "pre_any_outside": pre_any_outside,
            "pre_any_has_reachable_branch": alternative_ok,
        }
        dependency_rows.append(row)
        if missing_mandatory or not alternative_ok:
            hard_gaps.append(row)

    cluster_map: dict[str, dict[str, Any]] = {}
    for task in tasks:
        for source in objective_sources_in_zone(task):
            entity_id = source.get("entity_id")
            if not isinstance(entity_id, int):
                continue
            key = f"{source.get('entity_type')}:{entity_id}"
            cluster = cluster_map.setdefault(key, {
                "cluster_id": key,
                "entity_type": source.get("entity_type"),
                "entity_id": entity_id,
                "name": source.get("entity_name"),
                "representative": source.get("representative"),
                "spawn_count": source.get("spawn_count"),
                "quest_ids": [],
                "relations": [],
            })
            cluster["quest_ids"].append(int(source["quest_id"]))
            cluster["relations"].append(source)
    clusters = []
    for cluster in cluster_map.values():
        cluster["quest_ids"] = sorted(set(cluster["quest_ids"]))
        cluster["shared_by_multiple_tasks"] = len(cluster["quest_ids"]) > 1
        clusters.append(cluster)
    clusters.sort(key=lambda row: (-len(row["quest_ids"]), str(row.get("name") or ""), row["entity_id"]))

    task_classes = Counter(str(task.get("task_class")) for task in tasks)
    required_levels = Counter(task.get("required_level") for task in tasks)
    route_mechanism_notes = [
        {"quest_id": int(task["quest_id"]), "name": task.get("name"), "note": task.get("route_mechanism_note")}
        for task in tasks if task.get("route_mechanism_note")
    ]
    unknown_service = [
        {"quest_id": int(task["quest_id"]), "name": task.get("name"), "service": task.get("intrinsic_service_time")}
        for task in tasks if (task.get("intrinsic_service_time") or {}).get("status") != "estimated"
    ]

    payload = {
        "status": "foundation_only_no_route_order",
        "zone": {"id": ZONE_ID, "name": "灰熊丘陵"},
        "strategy": "first-run continuous outdoor full-clear baseline; structural exclusions only; no pre-run economic pruning",
        "entry_contract": {
            "from_zone": "龙骨荒野",
            "carried_in_quest_id": 12487,
            "carried_in_quest_name": "前往征服堡，自求多福吧！",
            "carried_through_quest_ids": [12789, 13242],
            "first_hub": "征服堡",
        },
        "formal_task_count": len(tasks),
        "formal_task_ids": sorted(formal_ids),
        "required_level_counts": {str(k): v for k, v in sorted(required_levels.items(), key=lambda item: (item[0] is None, item[0] or 0))},
        "task_class_counts": dict(sorted(task_classes.items())),
        "dependency_hard_gap_count": len(hard_gaps),
        "dependency_rows": dependency_rows,
        "dependency_hard_gaps": hard_gaps,
        "route_mechanism_notes": route_mechanism_notes,
        "unknown_service_tasks": unknown_service,
        "tasks": tasks,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CLUSTERS.write_text(json.dumps({
        "status": "foundation_only_no_route_order",
        "zone": {"id": ZONE_ID, "name": "灰熊丘陵"},
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "clusters": clusters,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 灰熊丘陵基础层审计（未排正式路线）",
        "",
        "- 当前只建立首组户外全清任务事实层、依赖闭包和真实目标簇；没有做逐任务经济删留。",
        f"- 正式候选：{len(tasks)}项；requiredLevel：`{dict(sorted(required_levels.items(), key=lambda item: (item[0] is None, item[0] or 0)))}`。",
        f"- task class：`{dict(sorted(task_classes.items()))}`。",
        f"- 精确目标簇：{len(clusters)}；被多个任务共享的实体簇：{sum(1 for cluster in clusters if cluster['shared_by_multiple_tasks'])}。",
        f"- 强依赖缺口：{len(hard_gaps)}。",
        f"- 服务时间仍未知：{len(unknown_service)}。",
        "",
        "## 强依赖缺口",
        "",
    ]
    if hard_gaps:
        for row in hard_gaps:
            lines.append(f"- {row['quest_id']}《{row['name']}》：missing={row['missing_mandatory']}；pre_any={row['pre_any']}；reachable={row['pre_any_has_reachable_branch']}")
    else:
        lines.append("- 无。83项正式候选在当前入口合同下可以形成闭合依赖池。")
    lines.extend(["", "## 服务时间仍未知/需特殊机制核验", ""])
    if unknown_service:
        for row in unknown_service:
            lines.append(f"- {row['quest_id']}《{row['name']}》：{row['service']}")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 已确认的特殊路线机制", ""])
    if route_mechanism_notes:
        for row in route_mechanism_notes:
            lines.append(f"- {row['quest_id']}《{row['name']}》：{row['note']}")
    else:
        lines.append("- 暂无已写入任务宇宙的特殊路线机制。")
    lines.extend(["", "## 下一步", "", "- 只在这个闭合任务池上排征服堡→西南/沃达希尔→欧尼瓦→东北任务中心的正式Hub顺序；完成整图后再做动态飞行点、炉石、玩家视角冷启动复审。"])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "formal_task_count": len(tasks),
        "dependency_hard_gap_count": len(hard_gaps),
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "unknown_service_count": len(unknown_service),
        "foundation": str(OUT.relative_to(ROOT)),
        "clusters": str(CLUSTERS.relative_to(ROOT)),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
