from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
SCOPE = ROOT / "data/route-atlas/zuldrak-scope-audit.json"
OVERRIDES = ROOT / "data/route-atlas/zuldrak-task-overrides.json"
OUT = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
CLUSTERS = ROOT / "data/route-atlas/zuldrak-target-clusters.json"
REPORT = ROOT / "docs/analysis/2026-08-19-zuldrak-foundation-audit.md"
ZONE_ID = 66
EXTERNAL_DEPENDENCY_FACTS = {12545: "completed_in_dragonblight_before_carried_12789"}


def objective_sources(task: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    qid = int(task["quest_id"])
    for objective in task.get("objectives") or []:
        for source in objective.get("sources") or []:
            if ZONE_ID in (source.get("zones") or []):
                rows.append({"quest_id": qid, "quest_name": task.get("name"), "objective_type": objective.get("objective_type"), "required_count": objective.get("required_count"), "item_id": objective.get("item_id"), "entity_type": source.get("entity_type"), "entity_id": source.get("entity_id"), "entity_name": source.get("name"), "representative": (source.get("representative_by_zone") or {}).get(str(ZONE_ID)), "spawn_count": source.get("spawn_count"), "source_kind": "objective"})

    # Questie extraObjectives often contain the real scripted target that ordinary objective rows miss.
    # They are part of the Target Cluster foundation, not optional route notes.
    for extra in task.get("extra_objectives") or []:
        extra_index = int(extra.get("index") or 0)
        for source in extra.get("references") or []:
            if ZONE_ID not in (source.get("zones") or []):
                continue
            rows.append({"quest_id": qid, "quest_name": task.get("name"), "objective_type": "extra_objective", "required_count": None, "item_id": None, "entity_type": source.get("entity_type"), "entity_id": source.get("entity_id"), "entity_name": source.get("name"), "representative": (source.get("representative_by_zone") or {}).get(str(ZONE_ID)), "spawn_count": source.get("spawn_count"), "source_kind": "extra_reference", "extra_text": extra.get("text")})
        coordinates = (extra.get("coordinates_by_zone") or {}).get(str(ZONE_ID)) or []
        for coord_index, coord in enumerate(coordinates, start=1):
            if not isinstance(coord, list) or len(coord) < 2:
                continue
            rows.append({"quest_id": qid, "quest_name": task.get("name"), "objective_type": "extra_objective", "required_count": None, "item_id": None, "entity_type": "extra_anchor", "entity_id": f"{qid}:{extra_index}:{coord_index}", "entity_name": extra.get("text") or f"extra objective {extra_index}", "representative": {"x": float(coord[0]), "y": float(coord[1]), "spawn_count": 1}, "spawn_count": 1, "source_kind": "extra_coordinate", "extra_text": extra.get("text")})
    return rows


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    service_overrides = {int(qid): value for qid, value in (overrides.get("manual_service_minutes") or {}).items()}
    mechanism_codes = {int(qid): list(value) for qid, value in (overrides.get("mechanism_codes") or {}).items()}
    all_tasks = {int(t["quest_id"]): t for t in universe["tasks"]}
    formal_ids = {int(q) for q in scope["formal_candidate_ids"]}
    tasks = []
    for qid in sorted(formal_ids):
        task = dict(all_tasks[qid])
        task["scope_status"] = "include_current_full_clear"
        task["is_primary_candidate"] = True
        if qid in service_overrides:
            override = service_overrides[qid]
            task["intrinsic_service_time"] = {
                "status": "estimated",
                "minutes": float(override["minutes"]),
                "basis": f"manual_pre_route:{override['basis']}",
                "range_minutes": [float(x) for x in override.get("range", [])],
            }
        task["route_mechanism_codes"] = mechanism_codes.get(qid, [])
        tasks.append(task)

    dep_rows, hard_gaps = [], []
    for task in tasks:
        pre_any = [int(x) for x in task.get("pre_any") or []]
        pre_all = [int(x) for x in task.get("pre_all") or []]
        parent = [int(x) for x in task.get("parent_active") or []]
        mandatory = set(pre_all + parent)
        if len(pre_any) == 1:
            mandatory.add(pre_any[0])
        missing = sorted(x for x in mandatory if x not in formal_ids and x not in EXTERNAL_DEPENDENCY_FACTS)
        reachable_any = not pre_any or any(x in formal_ids or x in EXTERNAL_DEPENDENCY_FACTS for x in pre_any)
        row = {"quest_id": int(task["quest_id"]), "name": task["name"], "pre_any": pre_any, "pre_all": pre_all, "parent_active": parent, "missing_mandatory": missing, "pre_any_has_reachable_branch": reachable_any}
        dep_rows.append(row)
        if missing or not reachable_any:
            hard_gaps.append(row)

    cluster_map: dict[str, dict[str, Any]] = {}
    for task in tasks:
        for src in objective_sources(task):
            eid = src.get("entity_id")
            if not isinstance(eid, (int, str)):
                continue
            key = f"{src.get('entity_type')}:{eid}"
            c = cluster_map.setdefault(key, {"cluster_id": key, "entity_type": src.get("entity_type"), "entity_id": eid, "name": src.get("entity_name"), "representative": src.get("representative"), "spawn_count": src.get("spawn_count"), "quest_ids": [], "relations": [], "source_kinds": []})
            c["source_kinds"].append(src.get("source_kind") or "objective")
            c["quest_ids"].append(int(src["quest_id"])); c["relations"].append(src)
    clusters = []
    for c in cluster_map.values():
        c["quest_ids"] = sorted(set(c["quest_ids"]))
        c["source_kinds"] = sorted(set(c["source_kinds"]))
        c["shared_by_multiple_tasks"] = len(c["quest_ids"]) > 1
        clusters.append(c)
    clusters.sort(key=lambda c: (-len(c["quest_ids"]), str(c.get("name") or "")))

    classes = Counter(str(t.get("task_class")) for t in tasks)
    levels = Counter(t.get("required_level") for t in tasks)
    unknown = [{"quest_id": int(t["quest_id"]), "name": t["name"], "service": t.get("intrinsic_service_time")} for t in tasks if (t.get("intrinsic_service_time") or {}).get("status") != "estimated"]
    payload = {"status": "foundation_only_no_route_order", "zone": {"id": 66, "name": "祖达克"}, "strategy": "first-run continuous outdoor full-clear baseline; structural exclusions only; no pre-run economic pruning", "entry_contract": {"immediate_previous_zone": "灰熊丘陵", "breadcrumb_origin_zone": "龙骨荒野", "carried_in_quest_id": 12789, "carried_in_quest_name": "前往圣光据点！", "first_hub": "圣光据点", "note": "12789 may be carried through Grizzly Hills; do not assume direct Dragonblight-to-Zul'Drak travel."}, "formal_task_count": len(tasks), "formal_task_ids": sorted(formal_ids), "required_level_counts": {str(k): v for k, v in sorted(levels.items())}, "task_class_counts": dict(sorted(classes.items())), "dependency_hard_gap_count": len(hard_gaps), "dependency_rows": dep_rows, "dependency_hard_gaps": hard_gaps, "unknown_service_tasks": unknown, "tasks": tasks}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CLUSTERS.write_text(json.dumps({"status": "foundation_only_no_route_order", "zone": {"id": 66, "name": "祖达克"}, "cluster_count": len(clusters), "shared_cluster_count": sum(c["shared_by_multiple_tasks"] for c in clusters), "clusters": clusters}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 祖达克基础层审计（未排正式路线）", "", f"- 正式候选：{len(tasks)}项；requiredLevel：`{dict(sorted(levels.items()))}`。", f"- 强依赖缺口：{len(hard_gaps)}。", f"- 目标实体簇：{len(clusters)}；多任务共享簇：{sum(c['shared_by_multiple_tasks'] for c in clusters)}。", f"- 服务时间未知/特殊：{len(unknown)}。", "", "## 强依赖缺口", ""]
    lines += [f"- {r['quest_id']}《{r['name']}》 missing={r['missing_mandatory']} pre_any={r['pre_any']}" for r in hard_gaps] or [f"- 无。{len(tasks)}项在当前入口依赖状态下形成闭合依赖池。"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"formal_task_count": len(tasks), "dependency_hard_gap_count": len(hard_gaps), "cluster_count": len(clusters), "shared_cluster_count": sum(c["shared_by_multiple_tasks"] for c in clusters), "unknown_service_count": len(unknown)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
