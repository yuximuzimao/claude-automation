from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_atlas_geometry import cloud_summary, nearest_point, pair_metrics

DEFAULT_INPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
DEFAULT_OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-geometry-analysis.json"
SAMPLE_QUESTS = (9770, 9747, 9773, 9769, 9895)


def dedupe_points(points: list[list[float]]) -> list[list[float]]:
    seen: set[tuple[float, float]] = set()
    out: list[list[float]] = []
    for point in points:
        if len(point) < 2:
            continue
        key = (round(float(point[0]), 5), round(float(point[1]), 5))
        if key in seen:
            continue
        seen.add(key)
        out.append([float(point[0]), float(point[1])])
    return out


def quest_points(quest: dict[str, Any]) -> list[list[float]]:
    points: list[list[float]] = []
    for target in quest.get("objective_targets") or []:
        points.extend(target.get("spawns") or [])
    return dedupe_points(points)


def is_leveling_quest(quest: dict[str, Any]) -> bool:
    if quest.get("missing"):
        return False
    ql = quest.get("quest_level")
    rl = quest.get("required_level")
    return isinstance(ql, (int, float)) and 58 <= ql <= 68 and isinstance(rl, (int, float)) and rl <= 68


def shared_objective_refs(a: dict[str, Any], b: dict[str, Any]) -> dict[str, list[int]]:
    ar = a.get("objective_refs") or {}
    br = b.get("objective_refs") or {}
    return {
        kind: sorted(set(ar.get(kind) or []) & set(br.get(kind) or []))
        for kind in ("creatures", "objects", "items")
    }


def resolved_target_ids(quest: dict[str, Any]) -> dict[str, set[int]]:
    npcs: set[int] = set()
    objects: set[int] = set()
    for target in quest.get("objective_targets") or []:
        kind = target.get("kind")
        entity_id = target.get("entity_id")
        if not isinstance(entity_id, int):
            continue
        if kind in ("creature", "item_npc"):
            npcs.add(entity_id)
        elif kind in ("object", "item_object"):
            objects.add(entity_id)
    return {"npcs": npcs, "objects": objects}


def resolved_shared_targets(a: dict[str, Any], b: dict[str, Any]) -> dict[str, list[int]]:
    ar = resolved_target_ids(a)
    br = resolved_target_ids(b)
    return {
        "npcs": sorted(ar["npcs"] & br["npcs"]),
        "objects": sorted(ar["objects"] & br["objects"]),
    }


def round_nested(value: Any, digits: int = 3) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [round_nested(v, digits) for v in value]
    if isinstance(value, dict):
        return {k: round_nested(v, digits) for k, v in value.items()}
    return value


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    npcs = {int(npc["id"]): npc for npc in data.get("npcs", [])}
    quests = {int(qid): quest for qid, quest in data.get("quests", {}).items()}

    analyzed: dict[int, dict[str, Any]] = {}
    for quest_id, quest in quests.items():
        if not is_leveling_quest(quest):
            continue
        points = quest_points(quest)
        if not points:
            continue

        start_points: list[list[float]] = []
        start_npc_ids: list[int] = []
        for ref in quest.get("started_by") or []:
            if ref.get("kind") != "npcs":
                continue
            npc_id = int(ref["id"])
            npc = npcs.get(npc_id)
            if not npc:
                continue
            local = npc.get("spawns") or []
            if local:
                start_npc_ids.append(npc_id)
                start_points.extend(local)

        target_kinds: dict[str, int] = {}
        for target in quest.get("objective_targets") or []:
            kind = str(target.get("kind"))
            target_kinds[kind] = target_kinds.get(kind, 0) + 1

        analyzed[quest_id] = {
            "quest_id": quest_id,
            "name": quest.get("name"),
            "quest_level": quest.get("quest_level"),
            "required_level": quest.get("required_level"),
            "target_kinds": target_kinds,
            "geometry": cloud_summary(points),
            "start_npc_ids": sorted(set(start_npc_ids)),
            "entry_from_start": nearest_point(start_points, points),
            "objective_refs": quest.get("objective_refs") or {},
            "points": points,
        }

    pairs: list[dict[str, Any]] = []
    quest_ids = sorted(analyzed)
    for i, a_id in enumerate(quest_ids):
        a = analyzed[a_id]
        for b_id in quest_ids[i + 1 :]:
            b = analyzed[b_id]
            metrics = pair_metrics(a["points"], b["points"])
            if metrics is None:
                continue
            shared = shared_objective_refs(quests[a_id], quests[b_id])
            resolved_shared = resolved_shared_targets(quests[a_id], quests[b_id])
            pairs.append(
                {
                    "a": a_id,
                    "a_name": a["name"],
                    "b": b_id,
                    "b_name": b["name"],
                    "shared": shared,
                    "resolved_shared": resolved_shared,
                    **metrics,
                }
            )

    pairs.sort(key=lambda row: (row["symmetric_nn_p50"], row["centroid_distance"], row["a"], row["b"]))
    return {
        "meta": {
            **(data.get("meta") or {}),
            "analysis": "threshold-free point-cloud geometry; no nearby/overlap classification is hard-coded yet",
            "metric_notes": {
                "centroid_distance": "distance between mean centers in Questie map percentage units",
                "minimum_point_distance": "closest spawn-to-spawn distance",
                "symmetric_nn_p50": "mean of both directed median nearest-neighbor distances; lower means the two clouds interleave more strongly",
                "symmetric_nn_p90": "same idea at p90; lower means most of both clouds remain near each other",
                "bbox_iou": "axis-aligned bounding-box overlap only; diagnostic, not final overlap truth",
                "axis_strength": "PCA anisotropy in [0,1]; higher means the cloud has a clearer elongation direction",
            },
        },
        "quests": {str(qid): round_nested(row) for qid, row in analyzed.items()},
        "pairs": [round_nested(row) for row in pairs],
    }


def print_summary(result: dict[str, Any]) -> None:
    quests = result["quests"]
    print(f"quests_with_local_point_cloud={len(quests)} pairs={len(result['pairs'])}")
    print("\nSAMPLES")
    for quest_id in SAMPLE_QUESTS:
        row = quests.get(str(quest_id))
        if not row:
            continue
        g = row["geometry"]
        axis = g["principal_axis"]
        entry = row.get("entry_from_start")
        entry_text = "无本图接取点"
        if entry:
            entry_text = f"{entry['direction']} {entry['distance']:.2f} → {entry['target']}"
        bbox = g["bbox"]
        print(
            f"{quest_id} {row['name']} | 点{g['point_count']} | 中心({g['centroid'][0]:.2f},{g['centroid'][1]:.2f}) "
            f"| 范围x {bbox['left']:.2f}..{bbox['right']:.2f} y {bbox['top']:.2f}..{bbox['bottom']:.2f} "
            f"| 主轴{axis['direction']} 强度{axis['axis_strength']:.2f} | 从接取点最近切入: {entry_text}"
        )

    print("\nTOP RESOLVED SAME-ENTITY PAIRS")
    shown = 0
    for row in result["pairs"]:
        resolved = row.get("resolved_shared") or {}
        if not ((resolved.get("npcs") or []) or (resolved.get("objects") or [])):
            continue
        print(
            f"{row['a']} {row['a_name']}  <->  {row['b']} {row['b_name']} "
            f"| sharedNPC={resolved.get('npcs') or []} sharedObject={resolved.get('objects') or []} "
            f"| nn50={row['symmetric_nn_p50']:.2f}"
        )
        shown += 1
        if shown >= 10:
            break

    print("\nTOP PURE-SPATIAL NEARBY PAIRS (excluding direct/resolved shared entities)")
    shown = 0
    for row in result["pairs"]:
        shared = row["shared"]
        resolved = row.get("resolved_shared") or {}
        if any(shared[kind] for kind in ("creatures", "objects", "items")):
            continue
        if (resolved.get("npcs") or []) or (resolved.get("objects") or []):
            continue
        print(
            f"{row['a']} {row['a_name']}  <->  {row['b']} {row['b_name']} "
            f"| nn50={row['symmetric_nn_p50']:.2f} nn90={row['symmetric_nn_p90']:.2f} "
            f"center={row['centroid_distance']:.2f} min={row['minimum_point_distance']:.2f} bboxIoU={row['bbox_iou']:.2f}"
        )
        shown += 1
        if shown >= 15:
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute threshold-free Route Atlas point-cloud geometry for one zone.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print_summary(result)
    print(f"\noutput={args.output}")
