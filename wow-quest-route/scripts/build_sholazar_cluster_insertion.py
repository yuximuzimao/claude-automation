from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/sholazar-task-foundation.json"
CLUSTERS = ROOT / "data/route-atlas/sholazar-target-clusters.json"
SKELETON = ROOT / "data/route-atlas/sholazar-route-skeleton.json"
OUT = ROOT / "data/route-atlas/sholazar-cluster-insertion.json"
REPORT = ROOT / "docs/analysis/2026-08-26-sholazar-cluster-insertion.md"

# These quests legitimately touch many unrelated entities and must not create false
# explicit service visits or "same cluster split into many visits" signals.
# 12592 is a broad kill counter; 12624 is explicitly fixed to Swindlegrin's Dig.
NON_EXPLICIT_CLUSTER_QUESTS = {12592, 12624}

# Coarse start anchors only seed within-phase nearest-neighbour ordering. They do not
# override roads, caves, scripts, or manual Spatial Instance decisions.
PHASE_START_ANCHORS: dict[str, tuple[float, float]] = {
    "S01": (39.68, 58.66),   # Wildgrowth Mangal / Monte
    "S02": (27.10, 58.64),   # Nesingwary Base Camp
    "S03": (27.10, 58.64),
    "S04": (27.10, 58.64),
    "S05": (27.10, 58.64),
    "S06": (27.10, 58.64),
    "S07": (54.99, 69.11),   # Frenzyheart Hill
    "S08": (54.99, 69.11),
    "S09": (54.99, 69.11),
    "S10": (42.15, 38.65),   # Mistwhisper Village
    "S11": (54.59, 56.36),   # Rainspeaker Canopy
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def coord(row: dict[str, Any]) -> tuple[float, float] | None:
    rep = row.get("representative") or {}
    x, y = rep.get("x"), rep.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def mandatory_dependencies(task: dict[str, Any]) -> set[int]:
    out = {int(x) for x in (task.get("pre_all") or [])}
    out.update(int(x) for x in (task.get("parent_active") or []))
    pre_any = [int(x) for x in (task.get("pre_any") or [])]
    if len(pre_any) == 1:
        out.add(pre_any[0])
    return out


def nearest_order(rows: list[dict[str, Any]], start: tuple[float, float] | None) -> list[dict[str, Any]]:
    remaining = rows[:]
    ordered: list[dict[str, Any]] = []
    here = start
    while remaining:
        if here is None:
            remaining.sort(key=lambda r: (
                float((r.get("representative") or {}).get("y") or 999),
                float((r.get("representative") or {}).get("x") or 999),
                r.get("cluster_id") or "",
            ))
            nxt = remaining.pop(0)
        else:
            nxt = min(
                remaining,
                key=lambda r: math.dist(here, coord(r)) if coord(r) else 9999.0,
            )
            remaining.remove(nxt)
        ordered.append(nxt)
        if coord(nxt):
            here = coord(nxt)
    return ordered


def main() -> None:
    foundation = load(FOUNDATION)
    cluster_data = load(CLUSTERS)
    skeleton = load(SKELETON)

    formal_ids = {int(x) for x in foundation.get("formal_task_ids", [])}
    tasks = {int(t["quest_id"]): t for t in foundation.get("tasks", [])}
    phases = skeleton.get("phases") or []
    phase_index = {str(p["id"]): i for i, p in enumerate(phases)}
    qphase: dict[int, str] = {}
    for phase in phases:
        pid = str(phase["id"])
        for qid in phase.get("task_ids") or []:
            qid = int(qid)
            if qid in qphase:
                raise RuntimeError(f"quest appears in multiple skeleton phases: {qid}")
            qphase[qid] = pid

    if set(qphase) != formal_ids:
        raise RuntimeError(f"skeleton/formal mismatch missing={sorted(formal_ids-set(qphase))} extra={sorted(set(qphase)-formal_ids)}")

    visits_by_phase: dict[str, list[dict[str, Any]]] = defaultdict(list)
    cross_phase_same_entity: list[dict[str, Any]] = []
    coordinate_rows: list[dict[str, Any]] = []

    for cluster in cluster_data.get("clusters") or []:
        relation_qids = sorted({
            int(r["quest_id"])
            for r in (cluster.get("relations") or [])
            if int(r.get("quest_id") or 0) in formal_ids
        })
        if not relation_qids:
            continue

        explicit_qids = [qid for qid in relation_qids if qid not in NON_EXPLICIT_CLUSTER_QUESTS]
        grouped: dict[str, list[int]] = defaultdict(list)
        for qid in explicit_qids:
            grouped[qphase[qid]].append(qid)

        for pid, qids in grouped.items():
            visits_by_phase[pid].append({
                "cluster_id": cluster.get("cluster_id"),
                "name": cluster.get("name"),
                "entity_type": cluster.get("entity_type"),
                "entity_id": cluster.get("entity_id"),
                "representative": cluster.get("representative") or {},
                "quest_ids": sorted(qids),
                "source_kinds": cluster.get("source_kinds") or [],
            })

        effective = explicit_qids
        effective_phases = sorted({qphase[qid] for qid in effective}, key=lambda p: phase_index[p])
        if len(effective_phases) > 1:
            dependency_between = []
            earliest_i = min(phase_index[p] for p in effective_phases)
            for later_qid in effective:
                later_pid = qphase[later_qid]
                deps = mandatory_dependencies(tasks[later_qid])
                # A later quest cannot be merged into the earliest visit if one of its
                # prerequisites is not completed until a phase after that earliest visit.
                blocking = sorted(
                    dep for dep in deps
                    if dep in qphase and phase_index[qphase[dep]] > earliest_i
                )
                if blocking:
                    dependency_between.append({
                        "quest_id": later_qid,
                        "phase": later_pid,
                        "blocking_dependencies": blocking,
                    })
            cross_phase_same_entity.append({
                "cluster_id": cluster.get("cluster_id"),
                "name": cluster.get("name"),
                "representative": cluster.get("representative") or {},
                "quest_ids": effective,
                "phases": effective_phases,
                "has_dependency_unlock_between": bool(dependency_between),
                "dependency_unlocks": dependency_between,
                "review_priority": "high" if not dependency_between else "normal",
            })

        xy = coord(cluster)
        if xy:
            coordinate_rows.append({
                "cluster_id": cluster.get("cluster_id"),
                "name": cluster.get("name"),
                "xy": xy,
                "quest_ids": effective,
                "phases": sorted({qphase[qid] for qid in effective}, key=lambda p: phase_index[p]),
            })

    # Route-specific explicit service override: the generic loot table for 12624 is
    # intentionally collapsed to one real farming visit at Swindlegrin's Dig.
    visits_by_phase["S02"].append({
        "cluster_id": "manual:12624:swindlegrins_dig",
        "name": "斯温迪格林挖掘场·金色订婚戒指",
        "entity_type": "manual_spatial_service",
        "entity_id": "12624:swindlegrins_dig",
        "representative": {"x": 35.55, "y": 47.42, "spawn_count": None},
        "quest_ids": [12624],
        "source_kinds": ["manual_route_override"],
    })

    # Nearby but non-identical target clusters can still be the same real service area.
    nearby_cross_phase: list[dict[str, Any]] = []
    for i, left in enumerate(coordinate_rows):
        if not left["quest_ids"]:
            continue
        for right in coordinate_rows[i + 1:]:
            if not right["quest_ids"]:
                continue
            if set(left["phases"]) == set(right["phases"]):
                continue
            dist = math.dist(left["xy"], right["xy"])
            if dist > 2.5:
                continue
            if set(left["phases"]) & set(right["phases"]):
                # Still useful, but only report pairs with at least one genuinely different phase.
                if set(left["phases"]) == set(right["phases"]):
                    continue
            nearby_cross_phase.append({
                "distance_map_percent": round(dist, 2),
                "left": {k: left[k] for k in ("cluster_id", "name", "quest_ids", "phases")},
                "right": {k: right[k] for k in ("cluster_id", "name", "quest_ids", "phases")},
            })
    nearby_cross_phase.sort(key=lambda r: (r["distance_map_percent"], r["left"]["cluster_id"], r["right"]["cluster_id"]))

    ordered_phases = []
    visit_count = 0
    for phase in phases:
        pid = str(phase["id"])
        ordered = nearest_order(visits_by_phase.get(pid, []), PHASE_START_ANCHORS.get(pid))
        visit_count += len(ordered)
        ordered_phases.append({
            "phase_id": pid,
            "title": phase.get("title"),
            "task_ids": phase.get("task_ids") or [],
            "cluster_visit_count": len(ordered),
            "ordered_cluster_visits": ordered,
        })

    payload = {
        "status": "task_cluster_insertion_draft_before_whole_map_merge_audit",
        "policy": "Target Cluster visits are inserted into the current whole-map skeleton. Same-entity and nearby cross-phase repeats are explicitly surfaced for the post-insertion merge audit; coordinates never override real terrain or prerequisite state.",
        "formal_task_count": len(formal_ids),
        "phase_count": len(phases),
        "target_cluster_count": len(cluster_data.get("clusters") or []),
        "cluster_visit_count": visit_count,
        "cross_phase_same_entity_count": len(cross_phase_same_entity),
        "cross_phase_same_entity": sorted(cross_phase_same_entity, key=lambda r: (0 if r["review_priority"] == "high" else 1, r["cluster_id"])),
        "nearby_cross_phase_count": len(nearby_cross_phase),
        "nearby_cross_phase": nearby_cross_phase,
        "phases": ordered_phases,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    high = [r for r in cross_phase_same_entity if r["review_priority"] == "high"]
    lines = [
        "# 索拉查盆地任务簇插入草案",
        "",
        f"- 正式任务：{len(formal_ids)}；空间阶段：{len(phases)}；Target Cluster原始数：{len(cluster_data.get('clusters') or [])}；插入后服务访问：{visit_count}。",
        f"- 同一真实实体跨阶段重复：{len(cross_phase_same_entity)}；其中没有显式依赖解锁理由、优先检查能否合并：{len(high)}。",
        f"- 坐标距离≤2.5%且跨阶段的不同簇候选：{len(nearby_cross_phase)}。这只是发现器，必须再看真实道路/地形/任务是否已接。",
        "- 12592《猎人的挑战》和12624《不知所踪！》不参与跨阶段重复判定：前者是合法广域累计；后者已固定为斯温迪格林挖掘场显式服务段。",
        "",
        "## 高优先级同实体跨阶段候选",
        "",
    ]
    if high:
        for row in high:
            lines.append(f"- {row['cluster_id']} {row['name']}｜phases={row['phases']}｜quests={row['quest_ids']}")
    else:
        lines.append("- 无。")
    lines += ["", "## 各阶段插入后的Target Cluster访问", ""]
    for phase in ordered_phases:
        lines.append(f"### {phase['phase_id']}｜{phase['title']}｜{phase['cluster_visit_count']}个服务簇")
        lines.append("")
        for visit in phase["ordered_cluster_visits"]:
            rep = visit.get("representative") or {}
            xy = "?,?"
            if isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
                xy = f"{float(rep['x']):.1f},{float(rep['y']):.1f}"
            lines.append(f"- {xy}｜{visit['name']}｜quests={visit['quest_ids']}｜{visit['cluster_id']}")
        lines.append("")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "formal": len(formal_ids),
        "phases": len(phases),
        "target_clusters": len(cluster_data.get("clusters") or []),
        "cluster_visits": visit_count,
        "cross_phase_same_entity": len(cross_phase_same_entity),
        "high_priority_same_entity": len(high),
        "nearby_cross_phase": len(nearby_cross_phase),
        "output": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
