#!/usr/bin/env python3
"""生成35—55候选任务的重叠图与任务块候选。

本脚本只读取既有候选与基础数据，不选择最终路线，也不估算合并节省分钟。
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "data/routes/horde/blood-elf/35-55-candidates.json"
FOUNDATION_PATH = ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json"
CONSTRAINTS_PATH = ROOT / "data/route-specs/35-55-speedrun-constraints.json"
GRAPH_PATH = ROOT / "data/routes/horde/blood-elf/35-55-overlap-graph.json"
BLOCKS_PATH = ROOT / "data/routes/horde/blood-elf/35-55-overlap-blocks.json"
AUDIT_PATH = ROOT / "docs/analysis/2026-08-04-35-55-overlap-block-audit.md"
PRIORITY_AUDIT_JSON_PATH = ROOT / "data/routes/horde/blood-elf/35-55-priority-task-audit.json"
PRIORITY_AUDIT_MD_PATH = ROOT / "docs/analysis/2026-08-04-35-55-priority-task-audit.md"

PARAMETERS = {
    "objective_cluster_radius": 2.5,
    "accept_turnin_hub_radius": 1.25,
    "transport_destination_radius": 1.25,
    "coordinate_system": "Questie map percentage points; Euclidean distance within one map only",
    "block_policy": "evidence groups; coordinate relations remain bounded pair candidates",
}

EDGE_STRENGTH = {
    "same_kill_npc": "strong",
    "same_item_source_npc": "strong",
    "kill_and_item_source_same_npc": "strong",
    "same_world_object": "strong",
    "same_item_source_object": "strong",
    "same_accept_npc": "weak",
    "same_turnin_npc": "weak",
    "same_accept_turnin_hub": "medium",
    "nearby_objective_cluster": "medium",
    "direct_chain": "strong",
    "shared_transport_destination": "weak",
}

CURRENT_STATES = {
    "available_at_35",
    "available_at_35_conditional_trigger",
    "active",
    "objective_complete_pending_turnin",
}

COMBAT_EDGE_TYPES = {
    "same_kill_npc",
    "same_item_source_npc",
    "kill_and_item_source_same_npc",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_unique(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    result = []
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def valid_coordinate(record: dict[str, Any]) -> bool:
    x, y = record.get("x"), record.get("y")
    return (
        isinstance(x, (int, float))
        and isinstance(y, (int, float))
        and 0 <= x <= 100
        and 0 <= y <= 100
    )


def entity_points(
    entities: Iterable[dict[str, Any]], role: str
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for entity in entities:
        for zone_id, record in (entity.get("representative_by_zone") or {}).items():
            if not valid_coordinate(record):
                continue
            points.append(
                {
                    "map_id": int(zone_id),
                    "x": round(float(record["x"]), 4),
                    "y": round(float(record["y"]), 4),
                    "role": role,
                    "entity_type": entity.get("entity_type"),
                    "entity_id": entity.get("entity_id"),
                    "entity_name": entity.get("name") or "",
                }
            )
    return sorted(
        stable_unique(points),
        key=lambda item: (
            item["map_id"],
            item["x"],
            item["y"],
            str(item["entity_type"]),
            item["entity_id"] or -1,
        ),
    )


def objective_points(task: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, objective in enumerate(task.get("objectives") or []):
        for point in entity_points(objective.get("sources") or [], "objective"):
            points.append({**point, "objective_index": index})
    return sorted(
        stable_unique(points),
        key=lambda item: (
            item["map_id"],
            item["x"],
            item["y"],
            item.get("objective_index", -1),
            item["entity_id"] or -1,
        ),
    )


def task_features(task: dict[str, Any]) -> dict[str, Any]:
    kill_npcs: dict[int, str] = {}
    item_source_npcs: dict[int, str] = {}
    item_source_objects: dict[int, str] = {}
    world_objects: dict[int, str] = {}

    for objective in task.get("objectives") or []:
        objective_type = objective.get("objective_type")
        sources = objective.get("sources") or []
        if objective_type == "kill":
            for source in sources:
                if source.get("entity_type") == "npc" and source.get("entity_id") is not None:
                    kill_npcs[int(source["entity_id"])] = source.get("name") or ""
            for entity_id in objective.get("entity_ids") or []:
                kill_npcs.setdefault(int(entity_id), "")
        elif objective_type == "item":
            for source in sources:
                entity_id = source.get("entity_id")
                if entity_id is None:
                    continue
                if source.get("entity_type") == "npc":
                    item_source_npcs[int(entity_id)] = source.get("name") or ""
                elif source.get("entity_type") == "object":
                    item_source_objects[int(entity_id)] = source.get("name") or ""
        elif objective_type == "object":
            for source in sources:
                if source.get("entity_type") == "object" and source.get("entity_id") is not None:
                    world_objects[int(source["entity_id"])] = source.get("name") or ""
            for entity_id in objective.get("entity_ids") or []:
                world_objects.setdefault(int(entity_id), "")

    accept_npcs = {
        int(entity["entity_id"]): entity.get("name") or ""
        for entity in task.get("start_entities") or []
        if entity.get("entity_type") == "npc" and entity.get("entity_id") is not None
    }
    turnin_npcs = {
        int(entity["entity_id"]): entity.get("name") or ""
        for entity in task.get("finish_entities") or []
        if entity.get("entity_type") == "npc" and entity.get("entity_id") is not None
    }
    accept_points = entity_points(task.get("start_entities") or [], "accept")
    turnin_points = entity_points(task.get("finish_entities") or [], "turnin")
    start_maps = {point["map_id"] for point in accept_points}
    finish_maps = {point["map_id"] for point in turnin_points}
    cross_zone = (
        "cross_zone_or_multi_zone" in (task.get("route_flags") or [])
        or bool(start_maps and finish_maps and start_maps.isdisjoint(finish_maps))
    )
    return {
        "kill_npcs": kill_npcs,
        "item_source_npcs": item_source_npcs,
        "item_source_objects": item_source_objects,
        "world_objects": world_objects,
        "accept_npcs": accept_npcs,
        "turnin_npcs": turnin_npcs,
        "accept_points": accept_points,
        "turnin_points": turnin_points,
        "hub_points": sorted(accept_points + turnin_points, key=point_sort_key),
        "objective_points": objective_points(task),
        "transport_points": turnin_points if cross_zone else [],
    }


def point_sort_key(point: dict[str, Any]) -> tuple[Any, ...]:
    return (
        point["map_id"],
        point["x"],
        point["y"],
        point.get("role", ""),
        point.get("entity_id") or -1,
    )


def pairwise_task_ids(task_ids: Iterable[int]) -> Iterable[tuple[int, int]]:
    return itertools.combinations(sorted(set(task_ids)), 2)


def closest_points(
    left: Iterable[dict[str, Any]],
    right: Iterable[dict[str, Any]],
    radius: float,
) -> dict[str, Any] | None:
    best: tuple[float, dict[str, Any], dict[str, Any]] | None = None
    for first in left:
        for second in right:
            if first["map_id"] != second["map_id"]:
                continue
            distance = math.hypot(first["x"] - second["x"], first["y"] - second["y"])
            if distance > radius:
                continue
            candidate = (distance, first, second)
            if best is None or (
                round(candidate[0], 8), point_sort_key(candidate[1]), point_sort_key(candidate[2])
            ) < (
                round(best[0], 8), point_sort_key(best[1]), point_sort_key(best[2])
            ):
                best = candidate
    if best is None:
        return None
    distance, first, second = best
    return {
        "map_id": first["map_id"],
        "distance": round(distance, 4),
        "left": first,
        "right": second,
    }


def build_edges(
    tasks: list[dict[str, Any]], features: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    pair_evidence: dict[tuple[int, int, str], dict[str, Any]] = {}

    def add_entity_relation(
        edge_type: str,
        left_index: dict[int, set[int]],
        right_index: dict[int, set[int]] | None,
        names: dict[tuple[str, int], str],
        entity_type: str,
        left_role: str,
        right_role: str,
    ) -> None:
        other = left_index if right_index is None else right_index
        for entity_id in sorted(set(left_index) & set(other)):
            if right_index is None:
                pairs = pairwise_task_ids(left_index[entity_id])
            else:
                pairs = sorted(
                    {
                        tuple(sorted((left_id, right_id)))
                        for left_id in left_index[entity_id]
                        for right_id in other[entity_id]
                        if left_id != right_id
                    }
                )
            for source, target in pairs:
                key = (source, target, edge_type)
                edge = pair_evidence.setdefault(
                    key,
                    {
                        "source_quest_id": source,
                        "target_quest_id": target,
                        "edge_type": edge_type,
                        "strength": EDGE_STRENGTH[edge_type],
                        "common_entities": [],
                        "common_coordinates": [],
                    },
                )
                edge["common_entities"].append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "name": names.get((entity_type, entity_id), ""),
                        "left_role": left_role,
                        "right_role": right_role,
                    }
                )

    indexes: dict[str, dict[int, set[int]]] = {
        name: defaultdict(set)
        for name in (
            "kill_npcs",
            "item_source_npcs",
            "item_source_objects",
            "world_objects",
            "accept_npcs",
            "turnin_npcs",
        )
    }
    names: dict[tuple[str, int], str] = {}
    for task in tasks:
        quest_id = task["quest_id"]
        for feature_name, index in indexes.items():
            for entity_id, name in features[quest_id][feature_name].items():
                index[entity_id].add(quest_id)
                names.setdefault(("object" if "object" in feature_name else "npc", entity_id), name)

    add_entity_relation(
        "same_kill_npc", indexes["kill_npcs"], None, names, "npc", "kill", "kill"
    )
    add_entity_relation(
        "same_item_source_npc",
        indexes["item_source_npcs"],
        None,
        names,
        "npc",
        "item_source",
        "item_source",
    )
    add_entity_relation(
        "kill_and_item_source_same_npc",
        indexes["kill_npcs"],
        indexes["item_source_npcs"],
        names,
        "npc",
        "kill",
        "item_source",
    )
    add_entity_relation(
        "same_world_object",
        indexes["world_objects"],
        None,
        names,
        "object",
        "world_object",
        "world_object",
    )
    add_entity_relation(
        "same_item_source_object",
        indexes["item_source_objects"],
        None,
        names,
        "object",
        "item_source",
        "item_source",
    )
    add_entity_relation(
        "same_accept_npc",
        indexes["accept_npcs"],
        None,
        names,
        "npc",
        "accept",
        "accept",
    )
    add_entity_relation(
        "same_turnin_npc",
        indexes["turnin_npcs"],
        None,
        names,
        "npc",
        "turnin",
        "turnin",
    )

    task_by_id = {task["quest_id"]: task for task in tasks}
    candidate_ids = set(task_by_id)
    chain_pairs: dict[tuple[int, int], set[str]] = defaultdict(set)
    for task in tasks:
        quest_id = task["quest_id"]
        next_quest = task.get("next_quest")
        if next_quest in candidate_ids and next_quest != quest_id:
            chain_pairs[tuple(sorted((quest_id, int(next_quest))))].add("next_quest")
        for predecessor in (task.get("pre_single") or []) + (task.get("pre_group") or []):
            if predecessor in candidate_ids and predecessor != quest_id:
                chain_pairs[tuple(sorted((quest_id, int(predecessor))))].add("predecessor")
    for (source, target), evidence in sorted(chain_pairs.items()):
        pair_evidence[(source, target, "direct_chain")] = {
            "source_quest_id": source,
            "target_quest_id": target,
            "edge_type": "direct_chain",
            "strength": "strong",
            "common_entities": [],
            "common_coordinates": [],
            "chain_evidence": sorted(evidence),
        }

    coordinate_relations = (
        (
            "same_accept_turnin_hub",
            "hub_points",
            PARAMETERS["accept_turnin_hub_radius"],
        ),
        (
            "nearby_objective_cluster",
            "objective_points",
            PARAMETERS["objective_cluster_radius"],
        ),
        (
            "shared_transport_destination",
            "transport_points",
            PARAMETERS["transport_destination_radius"],
        ),
    )
    for left_task, right_task in itertools.combinations(tasks, 2):
        left_id, right_id = left_task["quest_id"], right_task["quest_id"]
        for edge_type, feature_name, radius in coordinate_relations:
            match = closest_points(
                features[left_id][feature_name], features[right_id][feature_name], radius
            )
            if match is None:
                continue
            pair_evidence[(left_id, right_id, edge_type)] = {
                "source_quest_id": left_id,
                "target_quest_id": right_id,
                "edge_type": edge_type,
                "strength": EDGE_STRENGTH[edge_type],
                "common_entities": [],
                "common_coordinates": [match],
                "radius": radius,
            }

    edges = []
    for index, key in enumerate(sorted(pair_evidence), 1):
        edge = pair_evidence[key]
        edge["common_entities"] = sorted(
            stable_unique(edge["common_entities"]),
            key=lambda item: (
                item["entity_type"],
                item["entity_id"],
                item["left_role"],
                item["right_role"],
            ),
        )
        edge["edge_id"] = f"E{index:06d}"
        if edge["edge_type"] == "kill_and_item_source_same_npc":
            edge["reuse_note"] = (
                "同一NPC的必需击杀可同时推进共享击杀与个人掉落；"
                "只记录复用目标，不假定掉落完成或节省分钟。"
            )
        edges.append(edge)
    return edges


def task_risk_flags(task: dict[str, Any]) -> list[str]:
    flags = list(task.get("route_flags") or []) + list(task.get("manual_review_reasons") or [])
    for objective in task.get("objectives") or []:
        flags.extend(objective.get("difficulty_flags") or [])
        if objective.get("count_confidence") not in (None, "exact_text_order"):
            flags.append(f"objective_count:{objective.get('count_confidence')}")
    return sorted(set(flags))


def task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "quest_id": task["quest_id"],
        "name": task.get("name") or "",
        "map": {
            "map_id": task.get("primary_zone_id"),
            "name": task.get("primary_zone") or "",
        },
        "current_state": task.get("candidate_state"),
        "status": task.get("status"),
        "required_level": task.get("required_level"),
        "quest_level": task.get("quest_level"),
        "earliest_completion_level": task.get("earliest_completion_level"),
        "prerequisites": {
            "pre_single": task.get("pre_single") or [],
            "pre_group": task.get("pre_group") or [],
            "next_quest": task.get("next_quest"),
            "missing_single": task.get("missing_single_prerequisites") or [],
            "missing_group": task.get("missing_group_prerequisites") or [],
        },
        "risk_flags": task_risk_flags(task),
    }


def build_blocks(
    tasks: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    task_by_id = {task["quest_id"]: task for task in tasks}
    edge_by_id = {edge["edge_id"]: edge for edge in edges}
    seeds: dict[tuple[Any, ...], set[str]] = defaultdict(set)

    for edge in edges:
        strength = edge["strength"]
        edge_type = edge["edge_type"]
        task_pair = (edge["source_quest_id"], edge["target_quest_id"])
        if edge["common_entities"]:
            for entity in edge["common_entities"]:
                seed_key = (
                    strength,
                    edge_type,
                    entity["entity_type"],
                    entity["entity_id"],
                )
                seeds[seed_key].add(edge["edge_id"])
        else:
            seed_key = (strength, edge_type, "pair", *task_pair)
            seeds[seed_key].add(edge["edge_id"])

    raw_blocks: list[dict[str, Any]] = []
    for seed_key, seed_edge_ids in sorted(seeds.items()):
        selected_edges = [edge_by_id[edge_id] for edge_id in sorted(seed_edge_ids)]
        task_ids = sorted(
            {
                quest_id
                for edge in selected_edges
                for quest_id in (edge["source_quest_id"], edge["target_quest_id"])
            }
        )
        if len(task_ids) < 2:
            continue
        raw_blocks.append(
            {
                "strength": seed_key[0],
                "task_ids": task_ids,
                "edge_ids": sorted(seed_edge_ids),
            }
        )

    merged: dict[tuple[str, tuple[int, ...]], set[str]] = defaultdict(set)
    for block in raw_blocks:
        merged[(block["strength"], tuple(block["task_ids"]))].update(block["edge_ids"])

    strength_order = {"strong": 0, "medium": 1, "weak": 2}
    prepared = []
    for (strength, task_ids), block_edge_ids in merged.items():
        selected_edges = [edge_by_id[edge_id] for edge_id in sorted(block_edge_ids)]
        common_entities = sorted(
            stable_unique(
                entity for edge in selected_edges for entity in edge["common_entities"]
            ),
            key=lambda item: (
                item["entity_type"],
                item["entity_id"],
                item["left_role"],
                item["right_role"],
            ),
        )
        common_coordinates = sorted(
            stable_unique(
                coordinate
                for edge in selected_edges
                for coordinate in edge["common_coordinates"]
            ),
            key=lambda item: (
                item["map_id"],
                item["distance"],
                point_sort_key(item["left"]),
                point_sort_key(item["right"]),
            ),
        )
        maps = sorted(
            stable_unique(task_summary(task_by_id[quest_id])["map"] for quest_id in task_ids),
            key=lambda item: (item["map_id"] or -1, item["name"]),
        )
        combat_edge_count = sum(
            1 for edge in selected_edges if edge["edge_type"] in COMBAT_EDGE_TYPES
        )
        prepared.append(
            {
                "strength": strength,
                "task_ids": list(task_ids),
                "tasks": [task_summary(task_by_id[quest_id]) for quest_id in task_ids],
                "maps": maps,
                "edge_ids": sorted(block_edge_ids),
                "edge_types": sorted({edge["edge_type"] for edge in selected_edges}),
                "common_entities": common_entities,
                "common_coordinates": common_coordinates,
                "combat_reuse_candidate": bool(combat_edge_count),
                "combat_reuse_score": combat_edge_count * 10 + len(task_ids),
                "reuse_boundary": (
                    "只表示目标/动作可共同推进；个人掉落额外击杀、刷新和实际节省分钟仍需后续验证。"
                    if combat_edge_count
                    else "只表示接交、链条或空间邻近关系，不代表战斗成本可以去重。"
                ),
            }
        )

    prepared.sort(
        key=lambda block: (
            strength_order[block["strength"]],
            -block["combat_reuse_score"],
            block["task_ids"],
            block["edge_types"],
        )
    )
    counters = Counter()
    for block in prepared:
        counters[block["strength"]] += 1
        prefix = block["strength"].upper()
        block["block_id"] = f"B-{prefix}-{counters[block['strength']]:04d}"
    return prepared


def build_anti_merge_examples(
    tasks: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    task_by_id = {task["quest_id"]: task for task in tasks}
    pair_types: dict[tuple[int, int], set[str]] = defaultdict(set)
    for edge in edges:
        pair = (edge["source_quest_id"], edge["target_quest_id"])
        pair_types[pair].add(edge["edge_type"])

    examples = []
    weak_npc_types = {"same_accept_npc", "same_turnin_npc"}
    for pair, edge_types in sorted(pair_types.items()):
        if not edge_types & weak_npc_types:
            continue
        if any(EDGE_STRENGTH[edge_type] != "weak" for edge_type in edge_types):
            continue
        examples.append(
            {
                "quest_ids": list(pair),
                "names": [task_by_id[quest_id].get("name") or "" for quest_id in pair],
                "shared_fact": f"仅共享接取/交付NPC（{', '.join(sorted(edge_types))}）",
                "decision": "只保留弱关系，不提升为共同战斗或目标任务块。",
            }
        )
        if len(examples) >= 5:
            break

    by_zone: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        if task.get("primary_zone_id") is not None:
            by_zone[int(task["primary_zone_id"])].append(task)
    for zone_id, zone_tasks in sorted(by_zone.items()):
        for left, right in itertools.combinations(sorted(zone_tasks, key=lambda item: item["quest_id"]), 2):
            pair = (left["quest_id"], right["quest_id"])
            if pair in pair_types:
                continue
            examples.append(
                {
                    "quest_ids": list(pair),
                    "names": [left.get("name") or "", right.get("name") or ""],
                    "shared_fact": f"仅同属{left.get('primary_zone') or zone_id}",
                    "decision": "无共同实体、紧邻坐标或直接链条证据，不生成任务块。",
                }
            )
            break
        if len(examples) >= 10:
            break
    if len(examples) < 10:
        raise ValueError("无法生成至少10个稳定的防误合并反例")
    return examples[:10]


def zone_blocks(
    blocks: list[dict[str, Any]], tasks: list[dict[str, Any]], zone_id: int
) -> list[dict[str, Any]]:
    task_by_id = {task["quest_id"]: task for task in tasks}
    selected = []
    for block in blocks:
        if block["strength"] != "strong":
            continue
        relevant_ids = [
            quest_id
            for quest_id in block["task_ids"]
            if task_by_id[quest_id].get("primary_zone_id") == zone_id
            or zone_id in (task_by_id[quest_id].get("all_route_zones") or [])
        ]
        if len(relevant_ids) < 2:
            continue
        selected.append(
            {
                "block_id": block["block_id"],
                "task_ids": relevant_ids,
                "task_names": [task_by_id[quest_id].get("name") or "" for quest_id in relevant_ids],
                "edge_types": block["edge_types"],
                "combat_reuse_candidate": block["combat_reuse_candidate"],
                "full_block_task_ids": block["task_ids"],
            }
        )
    selected.sort(
        key=lambda item: (
            not item["combat_reuse_candidate"],
            -len(item["task_ids"]),
            item["task_ids"],
        )
    )
    return selected[:15]


def item_source_span(task: dict[str, Any], npc_id: int) -> int | None:
    """返回某NPC在单个物品目标中的最窄来源数，用于抑制超宽世界掉落噪声。"""
    spans = []
    for objective in task.get("objectives") or []:
        if objective.get("objective_type") != "item":
            continue
        npc_sources = {
            int(source["entity_id"])
            for source in objective.get("sources") or []
            if source.get("entity_type") == "npc" and source.get("entity_id") is not None
        }
        if npc_id in npc_sources:
            spans.append(len(npc_sources))
    return min(spans) if spans else None


def combat_specificity_score(
    block: dict[str, Any], task_by_id: dict[int, dict[str, Any]]
) -> tuple[int, int, int]:
    """高分代表共同实体更可能对应真正可去重的必需战斗。"""
    score = 0
    specific_entities = 0
    for entity in block["common_entities"]:
        if entity.get("entity_type") != "npc":
            continue
        npc_id = entity["entity_id"]
        relation = (entity.get("left_role"), entity.get("right_role"))
        spans = [
            span
            for quest_id in block["task_ids"]
            if (span := item_source_span(task_by_id[quest_id], npc_id)) is not None
        ]
        if relation == ("kill", "kill"):
            score += 100
            specific_entities += 1
        elif relation == ("kill", "item_source"):
            if spans and min(spans) <= 10:
                score += 70
                specific_entities += 1
            else:
                score += 2
        elif relation == ("item_source", "item_source"):
            if len(spans) >= 2 and max(spans) <= 10:
                score += 50
                specific_entities += 1
            else:
                score += 1
    current_count = sum(
        task_by_id[quest_id].get("candidate_state") in CURRENT_STATES
        for quest_id in block["task_ids"]
    )
    return score, specific_entities, current_count


def select_obvious_combat_blocks(
    blocks: list[dict[str, Any]], task_by_id: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates = [
        block
        for block in blocks
        if block["strength"] == "strong" and block["combat_reuse_candidate"]
    ]
    candidates.sort(
        key=lambda block: (
            -combat_specificity_score(block, task_by_id)[0],
            -combat_specificity_score(block, task_by_id)[1],
            -combat_specificity_score(block, task_by_id)[2],
            -len(block["task_ids"]),
            block["task_ids"],
        )
    )
    specific = [
        block
        for block in candidates
        if combat_specificity_score(block, task_by_id)[1] > 0
    ]
    if len(specific) < 10:
        raise ValueError("来源明确的重复战斗块不足10个，不能满足审计要求")
    return specific[:10]


def build_outputs() -> tuple[dict[str, Any], dict[str, Any], str]:
    candidates = load_json(CANDIDATES_PATH)
    foundation = load_json(FOUNDATION_PATH)
    constraints = load_json(CONSTRAINTS_PATH)
    tasks = sorted(
        [task for task in candidates["tasks"] if task.get("remaining_35_55_candidate")],
        key=lambda item: item["quest_id"],
    )
    expected_count = candidates.get("remaining_candidate_count")
    if expected_count != len(tasks):
        raise ValueError(f"候选数量不一致：元数据{expected_count}，实际{len(tasks)}")

    features = {task["quest_id"]: task_features(task) for task in tasks}
    edges = build_edges(tasks, features)
    blocks = build_blocks(tasks, edges)
    observed_edge_counts = Counter(edge["edge_type"] for edge in edges)
    edge_counts = {edge_type: observed_edge_counts.get(edge_type, 0) for edge_type in EDGE_STRENGTH}

    task_by_id = {task["quest_id"]: task for task in tasks}
    nodes = []
    for task in tasks:
        summary = task_summary(task)
        summary["task_class"] = task.get("task_class")
        nodes.append(summary)

    strong_blocks = [block for block in blocks if block["strength"] == "strong"]
    strong_task_ids = {quest_id for block in strong_blocks for quest_id in block["task_ids"]}
    current_task_ids = {
        task["quest_id"] for task in tasks if task.get("candidate_state") in CURRENT_STATES
    }
    current_strong_ids = current_task_ids & strong_task_ids
    block_counts = Counter(block["strength"] for block in blocks)
    anti_merge_examples = build_anti_merge_examples(tasks, edges)
    obvious_combat_blocks = select_obvious_combat_blocks(blocks, task_by_id)

    inputs = {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in (CANDIDATES_PATH, FOUNDATION_PATH, CONSTRAINTS_PATH)
    }
    graph = {
        "schema_version": 1,
        "generator": "scripts/build_35_55_overlap_blocks.py",
        "purpose": "候选任务重叠证据图；不是最终路线",
        "parameters": PARAMETERS,
        "input_sha256": inputs,
        "source_metadata": {
            "candidate_schema_version": candidates.get("schema_version"),
            "foundation_schema_version": foundation.get("schema_version"),
            "questie_version": foundation.get("questie_version"),
            "questie_sha256": foundation.get("questie_sha256"),
            "mandatory_map_ids": [
                section.get("map_area_id") for section in constraints.get("mandatory_sections", [])
            ],
        },
        "node_count": len(nodes),
        "edge_count": len(edges),
        "edge_type_counts": edge_counts,
        "nodes": nodes,
        "edges": edges,
    }
    block_output = {
        "schema_version": 1,
        "generator": "scripts/build_35_55_overlap_blocks.py",
        "purpose": "可多重归属的任务块候选；不含最终选择、最终顺序或节省分钟",
        "parameters": PARAMETERS,
        "input_sha256": inputs,
        "candidate_count": len(tasks),
        "current_processable_count": len(current_task_ids),
        "block_count": len(blocks),
        "block_strength_counts": dict(sorted(block_counts.items())),
        "strong_overlap_candidate_count": len(strong_task_ids),
        "current_processable_strong_overlap_count": len(current_strong_ids),
        "feralas_high_value_blocks": zone_blocks(blocks, tasks, 357),
        "tanaris_high_value_blocks": zone_blocks(blocks, tasks, 440),
        "obvious_duplicate_combat_blocks": [
            {
                "block_id": block["block_id"],
                "task_ids": block["task_ids"],
                "task_names": [task_by_id[quest_id].get("name") or "" for quest_id in block["task_ids"]],
                "edge_types": block["edge_types"],
                "boundary": block["reuse_boundary"],
            }
            for block in obvious_combat_blocks
        ],
        "anti_merge_examples": anti_merge_examples,
        "blocks": blocks,
    }
    audit = render_audit(graph, block_output)
    return graph, block_output, audit


def render_audit(graph: dict[str, Any], blocks: dict[str, Any]) -> str:
    lines = [
        "# 35—55任务重叠图与任务块候选审计",
        "",
        "> 本文只审计任务之间可共同执行的证据，不选择最终路线，不计算最终任务数、总时长或节省分钟。",
        "",
        "## 1. 结论",
        "",
        f"- 候选任务：{blocks['candidate_count']}个。",
        f"- 至少进入一个强重叠块：{blocks['strong_overlap_candidate_count']}个（{blocks['strong_overlap_candidate_count'] / blocks['candidate_count']:.1%}）。",
        f"- 当前可处理任务：{blocks['current_processable_count']}个；其中有强重叠：{blocks['current_processable_strong_overlap_count']}个。",
        f"- 重叠边：{graph['edge_count']}条；任务块候选：{blocks['block_count']}个。",
        "- 强边只来自共同战斗/物体实体ID或直接任务链；同NPC只记为弱边，同地图本身不生成边。",
        "",
        "## 2. 生成参数与可追溯性",
        "",
        f"- 目标坐标邻近半径：{graph['parameters']['objective_cluster_radius']}。",
        f"- 接取/交付中心半径：{graph['parameters']['accept_turnin_hub_radius']}。",
        f"- 跨区交通终点半径：{graph['parameters']['transport_destination_radius']}。",
        "- 坐标只在同一地图内比较；无效坐标（例如副本中的-1,-1）不参与邻近判断。",
        "- 输入SHA256：",
    ]
    for path, digest in graph["input_sha256"].items():
        lines.append(f"  - `{path}`：`{digest}`")
    lines.extend(["", "## 3. 各类型重叠边", "", "| 边类型 | 强度 | 数量 |", "| --- | --- | ---: |"])
    for edge_type in EDGE_STRENGTH:
        lines.append(
            f"| `{edge_type}` | {EDGE_STRENGTH[edge_type]} | {graph['edge_type_counts'].get(edge_type, 0)} |"
        )
    lines.extend(["", "## 4. 候选块数量", "", "| 强度 | 数量 |", "| --- | ---: |"])
    for strength in ("strong", "medium", "weak"):
        lines.append(f"| {strength} | {blocks['block_strength_counts'].get(strength, 0)} |")

    def append_zone(title: str, values: list[dict[str, Any]]) -> None:
        lines.extend(["", f"## {title}", ""])
        if not values:
            lines.append("- 未发现有实体ID或直接链条支持的强块；不能因同地图强行合并。")
            return
        for item in values:
            names = "、".join(
                f"《{name}》（{quest_id}）"
                for quest_id, name in zip(item["task_ids"], item["task_names"])
            )
            lines.append(
                f"- `{item['block_id']}`：{names}；依据：{', '.join(item['edge_types'])}；"
                f"战斗复用候选：{'是' if item['combat_reuse_candidate'] else '否'}。"
            )

    append_zone("5. 菲拉斯高价值强重叠块", blocks["feralas_high_value_blocks"])
    append_zone("6. 塔纳利斯高价值强重叠块", blocks["tanaris_high_value_blocks"])

    lines.extend(["", "## 7. 独立计算会重复战斗的明显任务块", ""])
    for index, item in enumerate(blocks["obvious_duplicate_combat_blocks"], 1):
        names = "、".join(
            f"《{name}》（{quest_id}）"
            for quest_id, name in zip(item["task_ids"], item["task_names"])
        )
        lines.append(
            f"{index}. `{item['block_id']}`：{names}；依据：{', '.join(item['edge_types'])}。{item['boundary']}"
        )

    lines.extend(["", "## 8. 防误合并反例", ""])
    for index, item in enumerate(blocks["anti_merge_examples"], 1):
        names = "、".join(
            f"《{name}》（{quest_id}）"
            for quest_id, name in zip(item["quest_ids"], item["names"])
        )
        lines.append(f"{index}. {names}：{item['shared_fact']}；{item['decision']}")

    lines.extend(
        [
            "",
            "## 9. 使用边界",
            "",
            "- 强块表示存在可复算的共同实体或直接链条，不代表任务一定入选。",
            "- 个人掉落与共享击杀同源时，只能先去重必需击杀目标；五号最慢完成者造成的额外击杀仍需单独计算。",
            "- 中块只表示小范围空间重叠，弱块只表示接交或交通协同；两者都不能直接去重战斗。",
            "- 后续优化器可以读取本图计算边际成本，但不得把块数量当成最终任务数。",
            "",
        ]
    )
    return "\n".join(lines)


def priority_scope_reasons(
    task: dict[str, Any], high_value_low_confidence_ids: set[int]
) -> list[str]:
    reasons = []
    if task.get("candidate_state") in CURRENT_STATES:
        reasons.append("current_processable_88")
    if task.get("primary_zone_id") == 357 or 357 in (task.get("all_route_zones") or []):
        reasons.append("feralas_remaining")
    if task.get("primary_zone_id") == 440 or 440 in (task.get("all_route_zones") or []):
        reasons.append("tanaris_remaining")
    manual_reasons = task.get("manual_review_reasons") or []
    if any(str(reason).startswith("objective_count:") for reason in manual_reasons):
        reasons.append("objective_count_review")
    if any(str(reason).startswith("item_source_missing:") for reason in manual_reasons) or any(
        objective.get("mechanic") == "item_source_not_in_questie"
        for objective in task.get("objectives") or []
    ):
        reasons.append("item_source_missing")
    if "scripted_event_mechanic" in manual_reasons or any(
        objective.get("mechanic") == "spell_use_area_trigger_or_scripted_event"
        for objective in task.get("objectives") or []
    ):
        reasons.append("scripted_event_mechanic")
    route_flags = task.get("route_flags") or []
    for flag, scope_reason in (
        ("object_respawn_and_multi_click_unknown", "object_respawn_and_multi_click_unknown"),
        ("dungeon_objective_source", "dungeon_objective_source"),
        ("escort_or_defense_text", "escort_or_defense"),
    ):
        if flag in route_flags:
            reasons.append(scope_reason)
    if task.get("task_class") == "escort_or_defense":
        reasons.append("escort_or_defense")
    if task["quest_id"] in high_value_low_confidence_ids:
        reasons.append("c1_high_value_strong_overlap_low_confidence")
    return sorted(set(reasons))


def objective_count_audit(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "objective_index": index,
            "objective_type": objective.get("objective_type"),
            "required_count": objective.get("required_count"),
            "count_confidence": objective.get("count_confidence"),
            "status": (
                "confirmed_from_structured_input"
                if objective.get("required_count") is not None
                and objective.get("count_confidence") == "exact_text_order"
                else "needs_source_or_live_confirmation"
            ),
        }
        for index, objective in enumerate(task.get("objectives") or [])
    ]


def mechanic_audit(task: dict[str, Any]) -> dict[str, Any]:
    objectives = task.get("objectives") or []
    return {
        "task_class_from_foundation": task.get("task_class"),
        "objective_mechanics": sorted(
            {objective.get("mechanic") for objective in objectives if objective.get("mechanic")}
        )
        or ["travel_dialogue_or_turnin"],
        "objective_types": sorted(
            {objective.get("objective_type") for objective in objectives if objective.get("objective_type")}
        ),
    }


def fivebox_audit(task: dict[str, Any]) -> dict[str, Any]:
    modes = sorted(
        {
            objective.get("fivebox_mode")
            for objective in task.get("objectives") or []
            if objective.get("fivebox_mode")
        }
    )
    if not modes:
        return {
            "modes": ["five_individual_accept_and_turnin"],
            "completion_rule": "五个角色逐号接取/交付，并逐号确认任务从日志消失。",
            "static_confidence": "confirmed_process_rule",
        }
    uncertain = any("expected" in mode or "unknown" in mode for mode in modes)
    if any("event" in mode or "use" in mode for mode in modes):
        completion_rule = "每个角色分别检查触发/使用进度；事件是否组队共享及是否可连续触发必须实测。"
    elif any("personal" in mode or "per_character" in mode for mode in modes):
        completion_rule = "以五个角色中最慢完成者为准；尸体或物体能否供五号连续使用必须实测。"
    elif any("group" in mode for mode in modes):
        completion_rule = "预计共享推进，但必须观察五个任务日志同步变化后才能确认。"
    else:
        completion_rule = "逐号检查任务进度；脚本或区域事件不得静态假定共享。"
    return {
        "modes": modes,
        "completion_rule": completion_rule,
        "static_confidence": "needs_live_test" if uncertain else "confirmed_from_structured_input",
    }


def drop_reference_audit(task: dict[str, Any]) -> dict[str, Any]:
    item_rows = []
    for index, objective in enumerate(task.get("objectives") or []):
        if objective.get("objective_type") != "item":
            continue
        sources = objective.get("sources") or []
        probabilities = []
        representative_sources = []
        for source in sources:
            source_probabilities = sorted(
                {
                    abs(float(evidence["probability_percent"]))
                    for evidence in source.get("loot_evidence") or []
                    if evidence.get("probability_percent") is not None
                }
            )
            probabilities.extend(source_probabilities)
            if len(representative_sources) < 10:
                representative_sources.append(
                    {
                        "entity_type": source.get("entity_type"),
                        "entity_id": source.get("entity_id"),
                        "name": source.get("name") or "",
                        "reference_probability_percent": source_probabilities,
                    }
                )
        unique_probabilities = sorted(set(probabilities))
        item_rows.append(
            {
                "objective_index": index,
                "item_id": objective.get("item_id"),
                "item_name": objective.get("item_name") or "",
                "required_count": objective.get("required_count"),
                "source_count": len(sources),
                "sources_with_reference_probability": sum(
                    bool(
                        [
                            evidence
                            for evidence in source.get("loot_evidence") or []
                            if evidence.get("probability_percent") is not None
                        ]
                    )
                    for source in sources
                ),
                "source_type_counts": dict(
                    sorted(Counter(source.get("entity_type") or "unknown" for source in sources).items())
                ),
                "reference_probability_min_percent": min(unique_probabilities)
                if unique_probabilities
                else None,
                "reference_probability_max_percent": max(unique_probabilities)
                if unique_probabilities
                else None,
                "all_known_sources_are_100_percent": bool(unique_probabilities)
                and min(unique_probabilities) == 100.0
                and max(unique_probabilities) == 100.0,
                "representative_sources": representative_sources,
                "summary_truncated": len(sources) > len(representative_sources),
            }
        )
    if not item_rows:
        status = "not_applicable"
    elif any(row["source_count"] == 0 for row in item_rows):
        status = "one_or_more_item_sources_missing"
    elif any(
        row["sources_with_reference_probability"] < row["source_count"]
        for row in item_rows
    ):
        status = "one_or_more_sources_lack_reference_probability"
    else:
        status = "reference_probabilities_available"
    return {
        "status": status,
        "items": item_rows,
        "reference_boundary": (
            "AzerothCore固定提交只作公开WotLK参考，不证明当前服务器掉率；负掉率已按任务专属概率绝对值解释。"
        ),
    }


def source_selection_rule(drop_summary: dict[str, Any]) -> str:
    if drop_summary["status"] == "not_applicable":
        return "无任务物品来源选择。"
    if drop_summary["status"] == "one_or_more_item_sources_missing":
        return "来源不完整；进入优化器前必须补证据，不能自行选择来源或假定掉率。"
    if any(item["source_count"] > 1 for item in drop_summary["items"]):
        return (
            "多来源不得只选最高参考掉率；先过滤当前等级可命中和户外可达来源，再比较密度、路径、血量与参考概率。"
        )
    return "使用结构化输入中的单一来源；参考概率仍须服从当前服务器实测。"


def fixed_wait_audit(task: dict[str, Any]) -> dict[str, Any]:
    route_flags = set(task.get("route_flags") or [])
    mechanics = {
        objective.get("mechanic") for objective in task.get("objectives") or []
    }
    fixed_component = (task.get("standalone_time_components") or {}).get("escort_or_defense") or {}
    named_respawn_unknown = task.get("task_class") in {
        "single_named_drop",
        "single_named_kill",
        "elite_or_boss_kill",
    }
    uncertain = bool(
        task.get("task_class") == "escort_or_defense"
        or "escort_or_defense_text" in route_flags
        or "spell_use_area_trigger_or_scripted_event" in mechanics
        or "object_respawn_and_multi_click_unknown" in route_flags
        or named_respawn_unknown
    )
    return {
        "status": (
            "named_target_respawn_unknown_requires_live_test"
            if named_respawn_unknown
            else "unknown_requires_live_test"
            if uncertain
            else "none_identified_in_static_input"
        ),
        "input_time_range_minutes": {
            key: fixed_component.get(key) for key in ("optimistic", "central", "pessimistic")
        },
        "boundary": (
            "单命名怪的寻路、清场、刷新等待和尸体规则必须现场计时。"
            if named_respawn_unknown
            else "静态时间组件不是实测脚本时长；护送、防守、物体刷新或事件等待必须现场计时。"
            if uncertain
            else "未发现固定等待机制；命名怪刷新仍需在具体路线审计时单独检查。"
        ),
    }


def audit_decision(
    task: dict[str, Any],
    counts: list[dict[str, Any]],
    fivebox_rule: dict[str, Any],
    drop_summary: dict[str, Any],
    fixed_wait: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons = []
    if any(item["status"] != "confirmed_from_structured_input" for item in counts):
        reasons.append("目标数量未由结构化输入完整确认")
    if fivebox_rule["static_confidence"] == "needs_live_test":
        reasons.append("五开共享/逐号机制只能由当前服务器实测确认")
    if drop_summary["status"] == "one_or_more_item_sources_missing":
        reasons.append("任务物品来源缺失")
    if fixed_wait["status"] != "none_identified_in_static_input":
        reasons.append("固定等待、刷新或脚本时长未知")
    if "scripted_event_mechanic" in (task.get("manual_review_reasons") or []):
        reasons.append("脚本事件机制未静态闭包")
    if reasons:
        return "needs_live_test", sorted(set(reasons))
    return "confirmed", ["基础任务机制、数量与来源结构内部一致；本覆盖层不改原始字段"]


def route_tendency(task: dict[str, Any], audit_status: str) -> str:
    flags = set(task.get("route_flags") or [])
    if "dungeon_objective_source" in flags:
        return "exclude_from_current_outdoor_optimizer"
    if task.get("task_class") in {"escort_or_defense", "item_source_not_in_questie"}:
        return "defer_until_evidence_or_live_test"
    if "scripted_event_mechanic" in (task.get("manual_review_reasons") or []):
        return "defer_until_evidence_or_live_test"
    if audit_status == "needs_live_test":
        return "conditional_candidate_with_stop_loss"
    return "retain_as_structurally_valid_candidate"


def build_priority_audit(
    graph: dict[str, Any], block_output: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    candidates = load_json(CANDIDATES_PATH)
    foundation = load_json(FOUNDATION_PATH)
    tasks = sorted(
        [task for task in candidates["tasks"] if task.get("remaining_35_55_candidate")],
        key=lambda item: item["quest_id"],
    )
    obvious_ids = {
        quest_id
        for block in block_output["obvious_duplicate_combat_blocks"]
        for quest_id in block["task_ids"]
    }
    high_value_low_confidence_ids = {
        task["quest_id"]
        for task in tasks
        if task["quest_id"] in obvious_ids and task.get("confidence") == "low_until_manual_review"
    }
    scope_by_id = {
        task["quest_id"]: priority_scope_reasons(task, high_value_low_confidence_ids)
        for task in tasks
    }
    audited_tasks = [task for task in tasks if scope_by_id[task["quest_id"]]]

    overlap_by_task: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"strong_neighbors": set(), "edge_types": set(), "edge_ids": []}
    )
    for edge in graph["edges"]:
        left, right = edge["source_quest_id"], edge["target_quest_id"]
        for quest_id, neighbor in ((left, right), (right, left)):
            if edge["strength"] == "strong":
                overlap_by_task[quest_id]["strong_neighbors"].add(neighbor)
                overlap_by_task[quest_id]["edge_types"].add(edge["edge_type"])
                overlap_by_task[quest_id]["edge_ids"].append(edge["edge_id"])

    records = []
    for task in audited_tasks:
        quest_id = task["quest_id"]
        counts = objective_count_audit(task)
        mechanic = mechanic_audit(task)
        fivebox_rule = fivebox_audit(task)
        drops = drop_reference_audit(task)
        fixed_wait = fixed_wait_audit(task)
        audit_status, decision_reasons = audit_decision(
            task, counts, fivebox_rule, drops, fixed_wait
        )
        overlap = overlap_by_task[quest_id]
        risks = sorted(
            set(task_risk_flags(task))
            | ({"fivebox_mechanic_unconfirmed"} if fivebox_rule["static_confidence"] == "needs_live_test" else set())
            | ({"fixed_wait_or_respawn_unknown"} if fixed_wait["status"] != "none_identified_in_static_input" else set())
        )
        records.append(
            {
                "quest_id": quest_id,
                "name": task.get("name") or "",
                "primary_map": {
                    "map_id": task.get("primary_zone_id"),
                    "name": task.get("primary_zone") or "",
                },
                "candidate_state": task.get("candidate_state"),
                "audit_scope_reasons": scope_by_id[quest_id],
                "audit_status": audit_status,
                "route_tendency": route_tendency(task, audit_status),
                "objective_counts": counts,
                "mechanic": mechanic,
                "fivebox_rule": fivebox_rule,
                "source_selection_rule": source_selection_rule(drops),
                "drop_reference_summary": drops,
                "fixed_wait_or_script_time": fixed_wait,
                "known_overlap_task_ids": sorted(overlap["strong_neighbors"]),
                "known_overlap_edge_types": sorted(overlap["edge_types"]),
                "risk_flags": risks,
                "correction_reason": "；".join(decision_reasons),
                "overrides": {},
                "evidence": [
                    {
                        "source": str(CANDIDATES_PATH.relative_to(ROOT)),
                        "quest_id": quest_id,
                        "sha256": sha256_file(CANDIDATES_PATH),
                    },
                    {
                        "source": str(GRAPH_PATH.relative_to(ROOT)),
                        "edge_ids": sorted(overlap["edge_ids"]),
                        "input_sha256": graph["input_sha256"],
                    },
                    {
                        "source": "AzerothCore database-wotlk",
                        "commit": foundation["loot_reference"]["commit"],
                        "applies_to": "drop_reference_summary_only",
                    },
                ],
            }
        )

    status_counts = Counter(record["audit_status"] for record in records)
    tendency_counts = Counter(record["route_tendency"] for record in records)
    scope_counts = Counter(reason for record in records for reason in record["audit_scope_reasons"])
    zone_counts = Counter(record["primary_map"]["name"] for record in records)
    mechanism_counts = Counter(
        mechanic
        for record in records
        for mechanic in record["mechanic"]["objective_mechanics"]
    )
    personal_100 = 0
    personal_below_100 = 0
    drop_missing = 0
    for record in records:
        drops = record["drop_reference_summary"]
        if drops["status"] == "one_or_more_item_sources_missing":
            drop_missing += 1
        item_rows = drops["items"]
        if item_rows and all(item["all_known_sources_are_100_percent"] for item in item_rows):
            personal_100 += 1
        if any(
            item["reference_probability_min_percent"] is not None
            and item["reference_probability_min_percent"] < 100
            for item in item_rows
        ):
            personal_below_100 += 1

    output = {
        "schema_version": 1,
        "purpose": "C2高优先任务人工分类覆盖层；不修改基础JSON，不选择最终路线",
        "source_sha256": {
            str(CANDIDATES_PATH.relative_to(ROOT)): sha256_file(CANDIDATES_PATH),
            str(FOUNDATION_PATH.relative_to(ROOT)): sha256_file(FOUNDATION_PATH),
            str(GRAPH_PATH.relative_to(ROOT)): sha256_file(GRAPH_PATH),
            str(BLOCKS_PATH.relative_to(ROOT)): sha256_file(BLOCKS_PATH),
        },
        "scope_definition": [
            "当前88个直接可处理候选",
            "菲拉斯全部剩余候选",
            "塔纳利斯全部剩余候选",
            "目标数量/来源缺失/脚本事件/物体刷新/副本/护送风险任务",
            "C1最明显强战斗重叠块中的低置信度任务",
        ],
        "audited_task_count": len(records),
        "audit_status_counts": dict(sorted(status_counts.items())),
        "route_tendency_counts": dict(sorted(tendency_counts.items())),
        "scope_reason_counts": dict(sorted(scope_counts.items())),
        "zone_counts": dict(sorted(zone_counts.items())),
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "drop_distinction_counts": {
            "all_known_item_sources_100_percent": personal_100,
            "one_or_more_reference_probabilities_below_100_percent": personal_below_100,
            "one_or_more_item_sources_missing": drop_missing,
        },
        "records": records,
    }
    return output, render_priority_audit(output)


def render_priority_audit(output: dict[str, Any]) -> str:
    lines = [
        "# 35—55高优先任务分类审计",
        "",
        "> 本文是覆盖层审计，不改基础任务JSON，不宣布最终路线、最终任务数或总时长。`needs_live_test`表示当前服务器五开机制不能由静态数据库证明。",
        "",
        "## 1. 审计结果",
        "",
        f"- 并集审计任务：{output['audited_task_count']}个。",
        "- 状态："
        + "；".join(f"{key} {value}个" for key, value in output["audit_status_counts"].items())
        + "。",
        "- 倾向："
        + "；".join(f"{key} {value}个" for key, value in output["route_tendency_counts"].items())
        + "。",
        "- 所有修正只保存在本覆盖层；本轮没有用不确定推断覆盖基础事实。",
        "",
        "## 2. 范围覆盖",
        "",
        "| 范围 | 数量 |",
        "| --- | ---: |",
    ]
    for key, value in output["scope_reason_counts"].items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## 3. 关键机制区分",
            "",
            f"- 所有已知物品来源均为100%参考概率：{output['drop_distinction_counts']['all_known_item_sources_100_percent']}个任务；仍不能据此假定同一尸体可供五号分别拾取。",
            f"- 至少一个参考概率低于100%：{output['drop_distinction_counts']['one_or_more_reference_probabilities_below_100_percent']}个任务；必须按五号最慢完成者处理掉落方差。",
            f"- 至少一个物品来源缺失：{output['drop_distinction_counts']['one_or_more_item_sources_missing']}个任务；来源补齐前不进入无条件保留集合。",
            "- 固定物体与怪物掉落分别保留原机制；物体刷新、五号连续交互、护送、防守、限时和区域事件只要静态不可证实，均标记`needs_live_test`。",
            "- `dungeon_objective_source`统一倾向排除出当前户外优化器，但保留数据，不等于永久删除任务。",
            "",
            "## 4. 按地图审计",
            "",
        ]
    )
    records_by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in output["records"]:
        records_by_zone[record["primary_map"]["name"]].append(record)
    for zone in sorted(records_by_zone):
        lines.extend([f"### {zone}", ""])
        for record in records_by_zone[zone]:
            mechanics = ", ".join(record["mechanic"]["objective_mechanics"])
            risks = ", ".join(record["risk_flags"]) or "无新增风险标记"
            overlaps = ", ".join(str(value) for value in record["known_overlap_task_ids"][:12]) or "无强重叠"
            if len(record["known_overlap_task_ids"]) > 12:
                overlaps += "…"
            lines.append(
                f"- 《{record['name']}》（{record['quest_id']}）— `{record['audit_status']}` / `{record['route_tendency']}`；"
                f"机制：{mechanics}；强重叠：{overlaps}；风险：{risks}。"
            )
        lines.append("")
    lines.extend(
        [
            "## 5. 给后续优化器的边界",
            "",
            "- `confirmed`只代表静态字段内部一致，不代表任务已被最终选中。",
            "- `needs_live_test`不得被自动改写成确认；可在路线候选中保留，但必须带止损或先做小样本实测。",
            "- `exclude_from_current_outdoor_optimizer`只处理副本目标与当前户外目标冲突，不删除基础任务。",
            "- 合并任务块时读取`known_overlap_task_ids`，但仍要分别处理个人掉落额外击杀、物体刷新和脚本等待。",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只在内存生成并校验，不写文件",
    )
    parser.add_argument(
        "--build-priority-audit",
        action="store_true",
        help="在C1验收后生成C2高优先任务覆盖层",
    )
    args = parser.parse_args()
    graph, blocks, audit = build_outputs()
    if args.build_priority_audit:
        priority_json, priority_md = build_priority_audit(graph, blocks)
        if not args.check:
            write_json(PRIORITY_AUDIT_JSON_PATH, priority_json)
            PRIORITY_AUDIT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
            PRIORITY_AUDIT_MD_PATH.write_text(priority_md, encoding="utf-8")
        print(
            json.dumps(
                {
                    "audited_task_count": priority_json["audited_task_count"],
                    "audit_status_counts": priority_json["audit_status_counts"],
                    "route_tendency_counts": priority_json["route_tendency_counts"],
                    "written": not args.check,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if not args.check:
        write_json(GRAPH_PATH, graph)
        write_json(BLOCKS_PATH, blocks)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(audit, encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate_count": graph["node_count"],
                "edge_count": graph["edge_count"],
                "edge_type_counts": graph["edge_type_counts"],
                "block_count": blocks["block_count"],
                "block_strength_counts": blocks["block_strength_counts"],
                "strong_overlap_candidate_count": blocks["strong_overlap_candidate_count"],
                "current_processable_strong_overlap_count": blocks[
                    "current_processable_strong_overlap_count"
                ],
                "written": not args.check,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
