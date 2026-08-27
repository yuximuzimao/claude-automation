from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
SCOPE = ROOT / "data/route-atlas/howling-fjord-scope-audit.json"
OUT = ROOT / "data/route-atlas/howling-fjord-task-foundation.json"
CLUSTERS = ROOT / "data/route-atlas/howling-fjord-target-clusters.json"
REPORT = ROOT / "docs/analysis/2026-08-26-howling-fjord-foundation-audit.md"
ZONE_ID = 495

# No Howling quest is assumed complete on entry. Previous-route transport state is handled by entry_contract.
EXTERNAL_DEPENDENCY_FACTS: dict[int, str] = {}


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
        "zone": {"id": ZONE_ID, "name": "嚎风峡湾"},
        "strategy": "one-time outdoor Horde full-clear baseline; structural exclusions only; no pre-run economic pruning",
        "entry_contract": {
            "from_zone": "灰熊丘陵",
            "previous_route_endpoint": "加弗洛克交《终获解救》后的状态",
            "known_open_transport_from_previous_route": ["欧尼瓦营地飞行点", "征服堡飞行点"],
            "planned_transition": "加弗洛克 → 欧尼瓦营地 → 系统飞行到征服堡 → 陆路越境进入嚎风峡湾西侧药剂师营地",
            "first_hub": "药剂师营地",
            "assumed_howling_flight_points_open": [],
            "carried_in_quest_ids": [],
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
        "zone": {"id": ZONE_ID, "name": "嚎风峡湾"},
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "clusters": clusters,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 嚎风峡湾基础层审计（未排正式路线）",
        "",
        "- 输入直接来自已清洗的诺森德任务宇宙；本步骤只建立嚎风正式scope、依赖闭包和目标簇。",
        f"- 正式候选：{len(tasks)}项；requiredLevel：`{dict(sorted(required_levels.items(), key=lambda item: (item[0] is None, item[0] or 0)))}`。",
        f"- task class：`{dict(sorted(task_classes.items()))}`。",
        f"- 精确目标簇：{len(clusters)}；多个任务共享实体簇：{sum(1 for cluster in clusters if cluster['shared_by_multiple_tasks'])}。",
        f"- 强依赖缺口：{len(hard_gaps)}。",
        f"- 服务时间仍未知：{len(unknown_service)}。",
        "",
        "## 入图合同",
        "",
        "- 灰熊正式设计出口：加弗洛克交《终获解救》。",
        "- 利用灰熊已开的欧尼瓦/征服堡飞行网络：加弗洛克骑到欧尼瓦 → 系统飞行征服堡 → 陆路越境进入嚎风西侧药剂师营地；不假设嚎风任何飞行点已开。",
        "- 第一个正式Hub固定为药剂师营地；其飞行点首次到达时开启，之后才允许使用药剂师营地→征服堡/冬蹄/新阿加曼德/卡玛古等已知航线。",
        "",
        "## 强依赖缺口",
        "",
    ]
    if hard_gaps:
        for row in hard_gaps:
            lines.append(f"- {row['quest_id']}《{row['name']}》：missing={row['missing_mandatory']}；pre_any={row['pre_any']}；reachable={row['pre_any_has_reachable_branch']}")
    else:
        lines.append(f"- 无。{len(tasks)}项正式候选在当前scope内依赖闭合。")
    lines.extend(["", "## 下一步", "", "- 以复仇港东线为第一任务簇，逐簇插入；每插一簇同步检查交后解锁、同NPC、同Spatial Instance和当时交通。海盗湾/慈悲修女号整链作为独立完整任务簇插入，不再沿用旧自动路线漏项结构。"])
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "formal_task_count": len(tasks),
        "dependency_hard_gap_count": len(hard_gaps),
        "cluster_count": len(clusters),
        "shared_cluster_count": sum(1 for cluster in clusters if cluster["shared_by_multiple_tasks"]),
        "unknown_service_count": len(unknown_service),
        "foundation": str(OUT.relative_to(ROOT)),
        "clusters": str(CLUSTERS.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
