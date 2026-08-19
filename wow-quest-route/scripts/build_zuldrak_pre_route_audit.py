from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ROOT = ROOT.parent / ".ai-bridge" / "wow-video-extraction"
FOUNDATION = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
CLUSTERS = ROOT / "data/route-atlas/zuldrak-target-clusters.json"
OVERRIDES = ROOT / "data/route-atlas/zuldrak-task-overrides.json"
VIDEO_OUT = ROOT / "data/route-atlas/zuldrak-video-reference.json"
MECHANICS_OUT = ROOT / "data/route-atlas/zuldrak-special-mechanism-audit.json"
SPATIAL_OUT = ROOT / "data/route-atlas/zuldrak-spatial-instances.json"
SEQUENCE_OUT = ROOT / "data/route-atlas/zuldrak-target-cluster-sequence.json"
REPORT = ROOT / "docs/analysis/2026-08-19-zuldrak-pre-route-foundation-gate.md"

EPISODES = (52, 53)
SPECIAL_CLASSES = {
    "fixed_object_interaction",
    "world_object_collection",
    "world_object_item_collection",
    "scripted_use_or_event",
    "mixed_with_personal_item",
    "item_source_not_in_questie",
}

# Spatial Instances are reachability constraints, not a second route layer.
# The ordered cluster sequence generated below is the whole-map initial backbone.
INSTANCE_DEFS = [
    {"id": "light_breach_rageclaw", "name": "圣光据点 / 怒爪南部入口", "anchor": [32.2, 76.0], "kind": "surface"},
    {"id": "crusader_forward", "name": "北伐军前线营地", "anchor": [25.3, 64.0], "kind": "surface"},
    {"id": "ebon_watch", "name": "黑锋哨站 / 西南天灾区", "anchor": [16.5, 73.8], "kind": "surface"},
    {"id": "gymer_vehicle", "name": "盖米尔载具段", "anchor": [23.0, 57.0], "kind": "scripted_vehicle"},
    {"id": "voltarus", "name": "沃尔塔鲁斯相位空间", "anchor": [29.0, 46.5], "kind": "phased_transport"},
    {"id": "argent_stand", "name": "银色前沿", "anchor": [40.3, 66.5], "kind": "surface"},
    {"id": "hebvalok_sseratus", "name": "赫布瓦罗 / 西莱图斯祭坛", "anchor": [39.5, 53.5], "kind": "surface"},
    {"id": "draksotra", "name": "达克索塔 / 哈沙尔南部", "anchor": [56.5, 76.0], "kind": "surface"},
    {"id": "amphitheater", "name": "痛苦斗兽场", "anchor": [48.4, 56.4], "kind": "surface"},
    {"id": "zimtorga_jinalai", "name": "希姆托加 / 金亚莱", "anchor": [58.8, 59.5], "kind": "surface"},
    {"id": "harkoa", "name": "哈克娅祭坛", "anchor": [63.0, 71.5], "kind": "surface"},
    {"id": "harkoa_quetzlun_ride", "name": "哈克娅 → 奎丝鲁恩脚本飞行", "anchor": [69.0, 64.0], "kind": "scripted_transport"},
    {"id": "quetzlun", "name": "奎丝鲁恩祭坛", "anchor": [74.0, 59.0], "kind": "surface"},
    {"id": "rhunok_zimrhuk", "name": "伦诺克 / 希姆鲁克", "anchor": [56.5, 43.0], "kind": "surface"},
    {"id": "mamtoth_east_mid", "name": "犸托斯 / 东部中层", "anchor": [73.0, 45.0], "kind": "surface"},
    {"id": "gundrak_dubrajin_north", "name": "古达克 / 杜布拉金北部", "anchor": [72.0, 31.0], "kind": "surface"},
]
INSTANCE_ORDER = [row["id"] for row in INSTANCE_DEFS]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_video(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    docs = {ep: (VIDEO_ROOT / f"episode-{ep}-extraction.md").read_text(encoding="utf-8").splitlines() for ep in EPISODES}
    event_docs = {ep: load(VIDEO_ROOT / f"episode-{ep}-events.json").get("events", []) for ep in EPISODES}
    payload: dict[str, Any] = {
        "policy": "Alliance single-character reference only: route-order/location/action evidence; never proves five-box sharing or five-box timing.",
        "episodes": list(EPISODES),
        "tasks": {},
    }
    for task in tasks:
        qid = int(task["quest_id"])
        name = str(task.get("name") or "")
        matches = []
        events = []
        for ep in EPISODES:
            for line_no, line in enumerate(docs[ep], 1):
                exact = bool(re.search(rf"(?<!\d){qid}(?!\d)", line))
                same_name = bool(name and name in line)
                if exact or same_name:
                    matches.append({"episode": ep, "line": line_no, "match": "exact_id" if exact else "same_name", "text": line.strip()[:360]})
                    if len(matches) >= 10:
                        break
            for event in event_docs[ep]:
                if event.get("quest_id") == qid or (name and event.get("quest_name") == name):
                    events.append({"episode": ep, "time_range": event.get("time_range"), "action": event.get("action"), "quest_id": event.get("quest_id"), "quest_name": event.get("quest_name")})
        payload["tasks"][str(qid)] = {
            "matches": matches[:10],
            "events": events,
            "episodes": sorted({x["episode"] for x in matches + events}),
            "video_evidence_available": bool(matches or events),
            "exact_id_event_available": any(x.get("quest_id") == qid for x in events),
        }
    payload["formal_task_with_video_count"] = sum(1 for row in payload["tasks"].values() if row["video_evidence_available"])
    return payload


def fivebox_checks(task: dict[str, Any]) -> list[str]:
    checks: set[str] = set()
    for obj in task.get("objectives") or []:
        mode = str(obj.get("fivebox_mode") or "")
        if "personal" in mode or "per_character" in mode:
            checks.add("personal_progress_or_pickup_confirm")
        if "unknown" in mode:
            checks.add("sharing_mode_confirm")
    flags = set(task.get("task_flags") or [])
    if "active_item_or_spell_use" in flags:
        checks.add("active_use_shared_vs_per_character")
    if "escort_or_defense_text" in flags:
        checks.add("escort_or_defense_group_completion")
    if task.get("task_class") in {"fixed_object_interaction", "world_object_collection", "world_object_item_collection"}:
        checks.add("fixed_object_shared_vs_personal")
    if task.get("route_mechanism_codes"):
        checks.add("current_server_fivebox_mechanism_confirm")
    return sorted(checks)


def build_mechanics(tasks: list[dict[str, Any]], video: dict[str, Any]) -> dict[str, Any]:
    rows = []
    blocking = []
    decisions = Counter()
    for task in tasks:
        qid = int(task["quest_id"])
        reasons = []
        if task.get("task_flags"):
            reasons += [f"task_flag:{x}" for x in task["task_flags"]]
        if task.get("extra_objectives"):
            reasons.append("questie_extra_objective")
        if task.get("objective_review"):
            reasons += [f"objective_review:{x}" for x in task["objective_review"]]
        if task.get("task_class") in SPECIAL_CLASSES:
            reasons.append(f"special_class:{task.get('task_class')}")
        if task.get("route_mechanism_codes"):
            reasons += [f"mechanism:{x}" for x in task["route_mechanism_codes"]]
        reasons = sorted(set(reasons))
        needs_note = bool(reasons)
        objective_text = str(task.get("objective_text_zh") or "").strip()
        extra_text = [str(x.get("text") or "").strip() for x in task.get("extra_objectives") or [] if x.get("text")]
        sources = []
        for obj in task.get("objectives") or []:
            for source in obj.get("sources") or []:
                rep = (source.get("representative_by_zone") or {}).get("66")
                if rep:
                    sources.append({"name": source.get("name"), "x": rep.get("x"), "y": rep.get("y"), "objective_type": obj.get("objective_type"), "count": obj.get("required_count")})
        unresolved = []
        if needs_note and not objective_text and not extra_text and not task.get("route_mechanism_codes"):
            unresolved.append("missing_player_operation_fact")
        service = task.get("intrinsic_service_time") or {}
        if service.get("status") != "estimated":
            unresolved.append("intrinsic_service_time_unknown")
        row = {
            "quest_id": qid,
            "name": task.get("name"),
            "decision": "must_note" if needs_note else "reviewed_no_extra_note",
            "reasons": reasons,
            "player_operation_fact": objective_text,
            "extra_objective_facts": extra_text,
            "mechanism_codes": task.get("route_mechanism_codes") or [],
            "objective_sources": sources,
            "intrinsic_service_time": service,
            "fivebox_checks": fivebox_checks(task),
            "blocking_unknowns": unresolved,
            "video_reference": video["tasks"].get(str(qid), {}),
        }
        rows.append(row)
        decisions[row["decision"]] += 1
        if unresolved:
            blocking.append({"quest_id": qid, "name": task.get("name"), "blocking_unknowns": unresolved})
    return {
        "status": "per_task_human_executability_screen_before_route_insertion",
        "zone": {"id": 66, "name": "祖达克"},
        "formal_task_count": len(tasks),
        "decision_counts": dict(decisions),
        "must_note_count": decisions["must_note"],
        "blocking_unknown_count": len(blocking),
        "blocking_unknowns": blocking,
        "fivebox_check_task_count": sum(bool(row["fivebox_checks"]) for row in rows),
        "rows": rows,
    }


def coord(cluster: dict[str, Any]) -> tuple[float, float] | None:
    rep = cluster.get("representative") or {}
    x, y = rep.get("x"), rep.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def nearest_instance(x: float, y: float, defs: list[dict[str, Any]]) -> str:
    candidates = [d for d in defs if d["kind"] == "surface"]
    return min(candidates, key=lambda d: math.dist((x, y), tuple(d["anchor"])))["id"]


def build_spatial(clusters: list[dict[str, Any]], overrides: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    special_qids = {name: {int(x) for x in qids} for name, qids in (overrides.get("spatial_overrides") or {}).items()}
    special_to_instance = {
        "voltarus": "voltarus",
        "gymer_vehicle": "gymer_vehicle",
        "harkoa_quetzlun_ride": "harkoa_quetzlun_ride",
        "rhunok_altar_script": "rhunok_zimrhuk",
    }
    assigned: dict[str, str] = {}
    rows = []
    no_coord = []
    for cluster in clusters:
        qids = {int(x) for x in cluster.get("quest_ids") or []}
        forced = None
        forced_reason = None
        for special_name, ids in special_qids.items():
            if qids & ids:
                forced = special_to_instance[special_name]
                forced_reason = special_name
                break
        xy = coord(cluster)
        if forced:
            instance_id = forced
        elif xy:
            instance_id = nearest_instance(xy[0], xy[1], INSTANCE_DEFS)
        else:
            instance_id = "unmapped_no_coordinate"
            no_coord.append(cluster["cluster_id"])
        assigned[cluster["cluster_id"]] = instance_id
        rows.append({
            "cluster_id": cluster["cluster_id"],
            "name": cluster.get("name"),
            "quest_ids": cluster.get("quest_ids") or [],
            "representative": cluster.get("representative"),
            "source_kinds": cluster.get("source_kinds") or [],
            "instance_id": instance_id,
            "assignment_basis": f"special:{forced_reason}" if forced_reason else "nearest_surface_anchor" if xy else "no_coordinate",
        })
    instances = []
    for definition in INSTANCE_DEFS:
        members = [row for row in rows if row["instance_id"] == definition["id"]]
        instances.append({**definition, "cluster_count": len(members), "cluster_ids": [row["cluster_id"] for row in members]})
    return ({
        "status": "spatial_instance_foundation_before_route_insertion",
        "policy": "Spatial Instances constrain real reachability only; they are not macro route blocks.",
        "instances": instances,
        "cluster_assignments": rows,
        "unmapped_no_coordinate_count": len(no_coord),
        "unmapped_no_coordinate_cluster_ids": no_coord,
    }, assigned)


def nearest_neighbor_order(rows: list[dict[str, Any]], start: tuple[float, float]) -> list[dict[str, Any]]:
    remaining = [row for row in rows if coord(row)]
    ordered = []
    current = start
    while remaining:
        nxt = min(remaining, key=lambda row: math.dist(current, coord(row) or current))
        ordered.append(nxt)
        current = coord(nxt) or current
        remaining.remove(nxt)
    return ordered


def build_sequence(clusters: list[dict[str, Any]], assigned: dict[str, str]) -> dict[str, Any]:
    defs = {row["id"]: row for row in INSTANCE_DEFS}
    by_instance: dict[str, list[dict[str, Any]]] = {key: [] for key in INSTANCE_ORDER}
    for cluster in clusters:
        instance = assigned.get(cluster["cluster_id"])
        if instance in by_instance:
            by_instance[instance].append(cluster)
    sequence = []
    prev_xy: tuple[float, float] | None = None
    ordinal = 0
    for instance_id in INSTANCE_ORDER:
        definition = defs[instance_id]
        start = prev_xy or tuple(definition["anchor"])
        ordered = nearest_neighbor_order(by_instance[instance_id], start)
        for cluster in ordered:
            ordinal += 1
            xy = coord(cluster)
            edge = math.dist(prev_xy, xy) if prev_xy and xy else None
            sequence.append({
                "ordinal": ordinal,
                "cluster_id": cluster["cluster_id"],
                "name": cluster.get("name"),
                "quest_ids": cluster.get("quest_ids") or [],
                "representative": cluster.get("representative"),
                "source_kinds": cluster.get("source_kinds") or [],
                "spatial_instance": instance_id,
                "edge_from_previous_map_percent": round(edge, 2) if edge is not None else None,
                "provisional_long_edge": bool(edge is not None and edge >= 18.0),
            })
            if xy:
                prev_xy = xy
    covered = {row["cluster_id"] for row in sequence}
    all_ids = {row["cluster_id"] for row in clusters}
    missing = sorted(all_ids - covered)
    long_edges = [row for row in sequence if row["provisional_long_edge"]]
    return {
        "status": "initial_whole_map_target_cluster_sequence_before_task_insertion",
        "policy": "This ordered Target Cluster sequence is the initial whole-map backbone. Long edges are provisional and should be split naturally by newly available task clusters during insertion; do not preserve artificial macro-block boundaries.",
        "entry_assumption": "Arrive from Grizzly Hills with 12789 carried from Dragonblight and turn it at Light's Breach.",
        "instance_order": INSTANCE_ORDER,
        "cluster_count": len(clusters),
        "ordered_cluster_count": len(sequence),
        "missing_cluster_count": len(missing),
        "missing_cluster_ids": missing,
        "provisional_long_edge_count": len(long_edges),
        "provisional_long_edges": [{k: row[k] for k in ("ordinal", "cluster_id", "name", "spatial_instance", "edge_from_previous_map_percent")} for row in long_edges],
        "sequence": sequence,
    }


def main() -> None:
    foundation = load(FOUNDATION)
    clusters_data = load(CLUSTERS)
    overrides = load(OVERRIDES)
    tasks = foundation["tasks"]
    clusters = clusters_data["clusters"]

    video = parse_video(tasks)
    mechanics = build_mechanics(tasks, video)
    spatial, assigned = build_spatial(clusters, overrides)
    sequence = build_sequence(clusters, assigned)

    VIDEO_OUT.write_text(json.dumps(video, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MECHANICS_OUT.write_text(json.dumps(mechanics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SPATIAL_OUT.write_text(json.dumps(spatial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEQUENCE_OUT.write_text(json.dumps(sequence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 祖达克正式排线前基础门禁",
        "",
        f"- 正式一次性户外任务：{foundation['formal_task_count']}；依赖硬缺口：{foundation['dependency_hard_gap_count']}。",
        f"- Target Cluster：{len(clusters)}（已包含Questie extraObjectives真实锚点）；整图初始序列覆盖：{sequence['ordered_cluster_count']}/{sequence['cluster_count']}，missing={sequence['missing_cluster_count']}。",
        f"- 特殊机制需玩家备注：{mechanics['must_note_count']}；会阻塞排线的机制未知：{mechanics['blocking_unknown_count']}；黄色fivebox实测任务：{mechanics['fivebox_check_task_count']}。",
        f"- 服务时间未知：{len(foundation['unknown_service_tasks'])}。",
        f"- 视频52—53直接/同名证据覆盖正式任务：{video['formal_task_with_video_count']}/{foundation['formal_task_count']}。",
        f"- Spatial Instance未映射簇：{spatial['unmapped_no_coordinate_count']}。",
        f"- 初始簇序列暂时长边：{sequence['provisional_long_edge_count']}；这些是后续逐任务插入优先观察的断边候选，不是固定大块边界。",
        "",
        "## 结论",
        "",
    ]
    passed = foundation["dependency_hard_gap_count"] == 0 and not foundation["unknown_service_tasks"] and mechanics["blocking_unknown_count"] == 0 and spatial["unmapped_no_coordinate_count"] == 0 and sequence["missing_cluster_count"] == 0
    lines.append("- PASS：祖达克已经达到正式逐簇插入前的基础数据标准。下一步才允许从整图Target Cluster序列开始插任务。" if passed else "- NOT PASS：仍有基础层阻塞项，不能开始正式逐簇插入。")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "foundation_gate": "PASS" if passed else "NOT_PASS",
        "formal_tasks": foundation["formal_task_count"],
        "dependency_gaps": foundation["dependency_hard_gap_count"],
        "target_clusters": len(clusters),
        "sequence_covered": sequence["ordered_cluster_count"],
        "sequence_missing": sequence["missing_cluster_count"],
        "unknown_service": len(foundation["unknown_service_tasks"]),
        "mechanism_blocking_unknown": mechanics["blocking_unknown_count"],
        "must_note": mechanics["must_note_count"],
        "fivebox_check_tasks": mechanics["fivebox_check_task_count"],
        "video_tasks": video["formal_task_with_video_count"],
        "spatial_unmapped": spatial["unmapped_no_coordinate_count"],
        "provisional_long_edges": sequence["provisional_long_edge_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
