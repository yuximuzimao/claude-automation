from __future__ import annotations

import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_drop_rates import QuestieDropRateDB
from lib.questie_source import load_questie
from lib.route_atlas_exact import infer_requirement_count_detail, representative_point
from lib.world_respawn_proxy import WorldRespawnProxy

QUESTIE_ZIP = ROOT / "data" / "sources" / "questie" / "Questie.zip"
INPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
GEOMETRY = ROOT / "data" / "route-atlas" / "zangarmarsh-geometry-analysis.json"
RESPAWN_PROXY = ROOT / "data" / "route-atlas" / "world-respawn-proxy.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"

# Zone dimensions in yards for Zangarmarsh (Map 467 / UI map 102 in legacy map data).
MAP_WIDTH_YARDS = 5027.08349609375
MAP_HEIGHT_YARDS = 3352.083251953125

# v1 first-run cost-model assumptions. They are deliberately simple and replaceable.
# The user wants a five-box operational estimate rather than combat-theory precision:
# one ordinary kill is budgeted as 15 seconds including target acquisition, mount/buff/control overhead.
TRAVEL_SPEED_YARDS_PER_SEC = 14.0
FIVE_BOX_CHARACTERS = 5
FIXED_KILL_SECONDS = 15.0
DEFAULT_OBJECT_RESPAWN_SECONDS = 300.0

# Conclusions already validated/discussed strongly enough to persist as labels.
KNOWN_SCOPE = {
    9747: ("local", "geometry_validated"),
    9773: ("local", "geometry_validated"),
    9895: ("local", "geometry_validated"),
    9769: ("background", "geometry_validated"),
}


def vals(table: Any) -> list[Any]:
    if not isinstance(table, dict):
        return []
    return [table[k] for k in sorted(k for k in table if isinstance(k, int))]


def distance_yards(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = (b[0] - a[0]) / 100.0 * MAP_WIDTH_YARDS
    dy = (b[1] - a[1]) / 100.0 * MAP_HEIGHT_YARDS
    return math.hypot(dx, dy)


def travel_seconds(a: tuple[float, float], b: tuple[float, float]) -> float:
    return distance_yards(a, b) / TRAVEL_SPEED_YARDS_PER_SEC


def calculation_cell(
    formula: str,
    inputs: dict[str, Any],
    result: float | int | None,
    *,
    unit: str,
    source: str,
    quality: str = "estimated",
) -> dict[str, Any]:
    """Persist formula + inputs + current result like a materialized spreadsheet cell."""
    return {
        "formula": formula,
        "inputs": inputs,
        "result": result,
        "unit": unit,
        "source": source,
        "quality": quality,
    }


def movement_cell(a: tuple[float, float], b: tuple[float, float]) -> dict[str, Any]:
    yards = distance_yards(a, b)
    seconds = yards / TRAVEL_SPEED_YARDS_PER_SEC
    return calculation_cell(
        "sqrt(((x2-x1)/100*map_width_yards)^2 + ((y2-y1)/100*map_height_yards)^2) / travel_speed_yards_per_sec",
        {
            "from_xy": list(a),
            "to_xy": list(b),
            "map_width_yards": MAP_WIDTH_YARDS,
            "map_height_yards": MAP_HEIGHT_YARDS,
            "travel_speed_yards_per_sec": TRAVEL_SPEED_YARDS_PER_SEC,
            "distance_yards": yards,
        },
        seconds,
        unit="seconds",
        source="route_atlas_uniform_flat_map_model",
    )


def five_box_collect_wait_seconds(
    per_character_count: int,
    unique_points: int,
    respawn_seconds: float,
    *,
    characters: int = FIVE_BOX_CHARACTERS,
) -> tuple[int | None, int | None, float | None]:
    """Return (rounds, wait_rounds, seconds). First pickup round requires no respawn wait."""
    if unique_points <= 0:
        return None, None, None
    total_required = int(per_character_count) * int(characters)
    rounds = math.ceil(total_required / unique_points) if total_required > 0 else 0
    wait_rounds = max(0, rounds - 1)
    return rounds, wait_rounds, wait_rounds * float(respawn_seconds)


def unique_spawn_points(targets: list[dict[str, Any]]) -> list[tuple[float, float]]:
    points: set[tuple[float, float]] = set()
    for target in targets:
        for p in target.get("spawns") or []:
            points.add((round(float(p[0]), 4), round(float(p[1]), 4)))
    return sorted(points)


def object_respawn_input(targets: list[dict[str, Any]], respawn_proxy: WorldRespawnProxy) -> dict[str, Any]:
    entry_ids = sorted({int(t["entity_id"]) for t in targets if t.get("entity_id") is not None})
    aggregate = respawn_proxy.gameobjects(entry_ids) if entry_ids else None
    if aggregate and aggregate.median_seconds is not None:
        quality = "proxy_uniform"
        if aggregate.random_range_rows:
            quality = "proxy_random_range_midpoint"
        elif not aggregate.uniform:
            quality = "proxy_mixed_fixed_spawn_median"
        return {
            "respawn_seconds": aggregate.median_seconds,
            "respawn_seconds_lower": aggregate.lower_median_seconds,
            "respawn_seconds_upper": aggregate.upper_median_seconds,
            "respawn_seconds_source": "cmangos_wotlk_spawn_proxy",
            "respawn_point_estimate_policy": "per-spawn (min+max)/2, then median across matching spawn rows",
            "respawn_evidence": aggregate.as_dict(),
            "respawn_quality": quality,
        }
    return {
        "respawn_seconds": DEFAULT_OBJECT_RESPAWN_SECONDS,
        "respawn_seconds_lower": DEFAULT_OBJECT_RESPAWN_SECONDS,
        "respawn_seconds_upper": DEFAULT_OBJECT_RESPAWN_SECONDS,
        "respawn_seconds_source": "temporary_uniform_assumption_pending_server_db_import",
        "respawn_point_estimate_policy": "fixed temporary assumption",
        "respawn_evidence": None,
        "respawn_quality": "temporary_assumption",
    }


def npc_mid_health(raw: dict[Any, Any] | None) -> float | None:
    if not raw:
        return None
    low, high = raw.get(2), raw.get(3)
    numbers = [float(v) for v in (low, high) if isinstance(v, (int, float)) and v > 0]
    return sum(numbers) / len(numbers) if numbers else None


def kill_seconds(raw: dict[Any, Any] | None) -> float:
    # First-run five-box operational constant. NPC health remains available as reference data,
    # but it no longer drives the baseline time estimate.
    return FIXED_KILL_SECONDS


def first_npc_point(refs: list[dict[str, Any]], npc_by_id: dict[int, dict[str, Any]]) -> tuple[float, float] | None:
    for ref in refs:
        if ref.get("kind") != "npcs":
            continue
        row = npc_by_id.get(int(ref["id"]))
        if not row:
            continue
        point = representative_point(row.get("spawns") or [])
        if point is not None:
            return point
    return None


def shortest_component_path(
    start: tuple[float, float],
    end: tuple[float, float],
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    """Exact Held-Karp path through one chosen representative point per component."""
    if not components:
        sec = travel_seconds(start, end)
        return {
            "order": [],
            "travel_to_work_seconds": sec,
            "work_internal_travel_seconds": 0.0,
            "work_to_turnin_seconds": 0.0,
            "total_travel_seconds": sec,
        }
    points = [tuple(c["baseline_point"]) for c in components]
    n = len(points)
    if n == 1:
        a = travel_seconds(start, points[0])
        b = travel_seconds(points[0], end)
        return {
            "order": [components[0]["id"]],
            "travel_to_work_seconds": a,
            "work_internal_travel_seconds": 0.0,
            "work_to_turnin_seconds": b,
            "total_travel_seconds": a + b,
        }

    # dp[(mask,last)] = (seconds, predecessor)
    dp: dict[tuple[int, int], tuple[float, int | None]] = {}
    for i, p in enumerate(points):
        dp[(1 << i, i)] = (travel_seconds(start, p), None)
    for mask_size in range(2, n + 1):
        for combo in itertools.combinations(range(n), mask_size):
            mask = sum(1 << i for i in combo)
            for last in combo:
                prev_mask = mask ^ (1 << last)
                best: tuple[float, int | None] | None = None
                for prev in combo:
                    if prev == last:
                        continue
                    row = dp.get((prev_mask, prev))
                    if row is None:
                        continue
                    cand = row[0] + travel_seconds(points[prev], points[last])
                    if best is None or cand < best[0]:
                        best = (cand, prev)
                if best is not None:
                    dp[(mask, last)] = best
    full = (1 << n) - 1
    last = min(range(n), key=lambda i: dp[(full, i)][0] + travel_seconds(points[i], end))
    total = dp[(full, last)][0] + travel_seconds(points[last], end)
    order_idx: list[int] = []
    mask = full
    cursor: int | None = last
    while cursor is not None:
        order_idx.append(cursor)
        _, prev = dp[(mask, cursor)]
        mask ^= 1 << cursor
        cursor = prev
    order_idx.reverse()
    to_work = travel_seconds(start, points[order_idx[0]])
    internal = sum(travel_seconds(points[a], points[b]) for a, b in zip(order_idx, order_idx[1:]))
    to_turnin = travel_seconds(points[order_idx[-1]], end)
    return {
        "order": [components[i]["id"] for i in order_idx],
        "travel_to_work_seconds": to_work,
        "work_internal_travel_seconds": internal,
        "work_to_turnin_seconds": to_turnin,
        "total_travel_seconds": total,
    }


def objective_raw_kinds(raw: dict[Any, Any] | None) -> dict[str, int]:
    out = {"creature": 0, "object": 0, "item": 0, "reputation": 0, "kill_credit": 0, "spell": 0}
    objectives = raw.get(10) if raw else None
    if not isinstance(objectives, dict):
        return out
    keys = ["creature", "object", "item", "reputation", "kill_credit", "spell"]
    for slot, key in enumerate(keys, 1):
        out[key] = len(vals(objectives.get(slot)))
    return out


def quest_flags(raw: dict[Any, Any] | None) -> int:
    value = raw.get(23) if raw else 0
    return int(value) if isinstance(value, (int, float)) else 0


def classify_task(quest: dict[str, Any], components: list[dict[str, Any]], raw: dict[Any, Any] | None) -> dict[str, Any]:
    text = str(quest.get("objective") or "")
    lower = text.lower()
    escort_signal = "护送" in text or "escort" in lower
    raw_kinds = objective_raw_kinds(raw)
    trigger_end = bool(raw and raw.get(9))
    exploration_flag = bool(quest_flags(raw) & 4)

    families = [c["family"] for c in components]
    unique = sorted(set(families))
    if escort_signal:
        primary = "escort"
    elif not components and not trigger_end and not any(raw_kinds.values()):
        primary = "handoff"
    elif trigger_end or exploration_flag:
        unique.append("explore_trigger")
        primary = unique[0] if len(set(unique)) == 1 else "mixed"
    elif len(unique) == 1:
        primary = unique[0]
    elif not unique and raw_kinds["spell"]:
        primary = "spell_use"
    elif not unique and raw_kinds["reputation"]:
        primary = "reputation"
    else:
        primary = "mixed" if unique else "other"

    labels = [f"task_type:{primary}"]
    for family in sorted(set(unique)):
        labels.append(f"component:{family}")
    return {
        "primary": primary,
        "components": sorted(set(unique)),
        "escort_signal": escort_signal,
        "trigger_end": trigger_end,
        "exploration_flag": exploration_flag,
        "raw_objective_kinds": raw_kinds,
        "labels": labels,
    }


def main() -> None:
    atlas = json.loads(INPUT.read_text(encoding="utf-8"))
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8")) if GEOMETRY.exists() else {"quests": {}}
    questie = load_questie(QUESTIE_ZIP)
    drops = QuestieDropRateDB(QUESTIE_ZIP)
    respawn_proxy = WorldRespawnProxy(RESPAWN_PROXY)
    npc_by_id = {int(n["id"]): n for n in atlas["npcs"]}

    profiles: dict[str, Any] = {}
    type_counts: dict[str, int] = {}
    drop_task_count = 0
    drop_pair_count = 0

    for qid_text, quest in atlas["quests"].items():
        qid = int(qid_text)
        raw = questie.quests.get(qid)
        start = first_npc_point(quest.get("started_by") or [], npc_by_id)
        end = first_npc_point(quest.get("finished_by") or [], npc_by_id)

        groups: list[tuple[str, list[dict[str, Any]]]] = []
        item_groups: dict[int, list[dict[str, Any]]] = {}
        for target in quest.get("objective_targets") or []:
            if target.get("kind") in ("item_npc", "item_object") and target.get("source_item_id") is not None:
                item_groups.setdefault(int(target["source_item_id"]), []).append(target)
            else:
                groups.append((f"entity:{target.get('kind')}:{target.get('entity_id')}", [target]))
        groups.extend((f"item:{item_id}", rows) for item_id, rows in sorted(item_groups.items()))

        components: list[dict[str, Any]] = []
        for index, (group_key, targets) in enumerate(groups, 1):
            count_detail = infer_requirement_count_detail(quest, targets)
            count = int(count_detail["value"])
            cid = f"q{qid}:c{index}"
            is_item_group = group_key.startswith("item:")
            npc_sources = [t for t in targets if t.get("kind") == "item_npc"]
            object_sources = [t for t in targets if t.get("kind") == "item_object"]
            direct_creature = [t for t in targets if t.get("kind") == "creature"]
            direct_object = [t for t in targets if t.get("kind") == "object"]
            direct_trigger = [t for t in targets if t.get("kind") == "trigger"]

            family = "other"
            sources: list[dict[str, Any]] = []
            baseline_source: dict[str, Any] | None = None
            objective_seconds: float | None = 0.0
            objective_seconds_lower: float | None = None
            objective_seconds_upper: float | None = None
            object_collect_inputs: dict[str, Any] | None = None

            if is_item_group and npc_sources:
                family = "mob_drop"
                item_id = int(targets[0]["source_item_id"])
                total_required_count = count * FIVE_BOX_CHARACTERS
                for target in npc_sources:
                    npc_id = int(target["entity_id"])
                    raw_npc = questie.npcs.get(npc_id)
                    rate = drops.get(item_id, npc_id)
                    spawns = target.get("spawns") or []
                    point = representative_point(spawns)
                    per_kill = kill_seconds(raw_npc)
                    expected_kills = total_required_count / (rate.rate / 100.0) if rate and rate.rate > 0 else None
                    service = expected_kills * per_kill if expected_kills is not None else None
                    expected_kills_cell = calculation_cell(
                        "five_box_required_count / (drop_rate_percent / 100)",
                        {
                            "per_character_required_count": count,
                            "characters": FIVE_BOX_CHARACTERS,
                            "five_box_required_count": total_required_count,
                            "drop_rate_percent": rate.rate if rate else None,
                        },
                        expected_kills,
                        unit="kills",
                        source=f"questie_drop_rate:{rate.source}" if rate else "questie_drop_rate:missing",
                        quality="estimated" if rate else "missing_input",
                    )
                    service_cell = calculation_cell(
                        "expected_kills * single_kill_seconds",
                        {"expected_kills": expected_kills, "single_kill_seconds": per_kill},
                        service,
                        unit="seconds",
                        source="questie_drop_rate + questie_npc_health + route_atlas_dps_assumption",
                        quality="estimated" if service is not None else "missing_input",
                    )
                    sources.append({
                        "kind": "npc",
                        "entity_id": npc_id,
                        "name": target.get("name"),
                        "spawn_count": len(spawns),
                        "representative_point": list(point) if point else None,
                        "drop_rate_percent": rate.rate if rate else None,
                        "drop_rate_source": rate.source if rate else None,
                        "expected_kills": expected_kills,
                        "single_kill_seconds": per_kill,
                        "expected_service_seconds": service,
                        "calculations": {
                            "expected_kills": expected_kills_cell,
                            "expected_service_time": service_cell,
                        },
                        "low_density_shortcut": len(spawns) <= 1 and len(npc_sources) > 1,
                    })
                    if rate:
                        drop_pair_count += 1
                drop_task_count += 1
                usable = [s for s in sources if s["representative_point"] and s["expected_service_seconds"] is not None]
                ordinary = [s for s in usable if not s["low_density_shortcut"]]
                candidates = ordinary or usable
                if candidates:
                    # Baseline = normal source with lowest standalone service time; route optimizer may choose differently later.
                    baseline_source = min(candidates, key=lambda s: (s["expected_service_seconds"], -s["spawn_count"]))
                    objective_seconds = float(baseline_source["expected_service_seconds"])
                    objective_seconds_lower = objective_seconds
                    objective_seconds_upper = objective_seconds
                else:
                    objective_seconds = None
                    objective_seconds_lower = None
                    objective_seconds_upper = None
            elif is_item_group and object_sources:
                raw_point_rows = sum(len(t.get("spawns") or []) for t in object_sources)
                unique_points = unique_spawn_points(object_sources)
                total_points = len(unique_points)
                respawn = object_respawn_input(object_sources, respawn_proxy)
                respawn_seconds = float(respawn["respawn_seconds"])
                respawn_seconds_lower = float(respawn["respawn_seconds_lower"])
                respawn_seconds_upper = float(respawn["respawn_seconds_upper"])
                family = "object_interact_single" if count <= 1 else "object_collect_multi"
                target = max(object_sources, key=lambda t: len(t.get("spawns") or []))
                point = representative_point(target.get("spawns") or [])
                baseline_source = {
                    "kind": "object",
                    "entity_id": int(target["entity_id"]),
                    "name": target.get("name"),
                    "spawn_count": len(target.get("spawns") or []),
                    "representative_point": list(point) if point else None,
                }
                if count <= 1:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds = 1 if count else 0
                    wait_rounds = 0
                    objective_seconds = 0.0
                    objective_seconds_lower = 0.0
                    objective_seconds_upper = 0.0
                elif total_points > 0:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds, wait_rounds, objective_seconds = five_box_collect_wait_seconds(count, total_points, respawn_seconds)
                    objective_seconds_lower = wait_rounds * respawn_seconds_lower
                    objective_seconds_upper = wait_rounds * respawn_seconds_upper
                else:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds = None
                    wait_rounds = None
                    objective_seconds = None
                    objective_seconds_lower = None
                    objective_seconds_upper = None
                sources = [{
                    "kind": "object",
                    "entity_id": int(t["entity_id"]),
                    "name": t.get("name"),
                    "spawn_count": len(t.get("spawns") or []),
                    "representative_point": list(representative_point(t.get("spawns") or [])) if representative_point(t.get("spawns") or []) else None,
                } for t in object_sources]
                object_collect_inputs = {
                    "per_character_required_count": count,
                    "characters": FIVE_BOX_CHARACTERS,
                    "five_box_required_count": total_required_count,
                    "raw_spawn_rows": raw_point_rows,
                    "unique_spawn_points": total_points,
                    "respawn_seconds": respawn_seconds,
                    "respawn_seconds_lower": respawn_seconds_lower,
                    "respawn_seconds_upper": respawn_seconds_upper,
                    "respawn_seconds_source": respawn["respawn_seconds_source"],
                    "respawn_point_estimate_policy": respawn["respawn_point_estimate_policy"],
                    "respawn_quality": respawn["respawn_quality"],
                    "respawn_evidence": respawn["respawn_evidence"],
                    "rounds": rounds,
                    "wait_rounds": wait_rounds,
                }
            elif direct_trigger:
                family = "explore_trigger"
                target = direct_trigger[0]
                point = representative_point(target.get("spawns") or [])
                count = 1
                count_detail = {
                    "value": 1,
                    "source": "questie_trigger_end",
                    "confidence": "high",
                    "matched_alias": None,
                    "matches": [],
                    "tried": [],
                }
                objective_seconds = 0.0
                objective_seconds_lower = 0.0
                objective_seconds_upper = 0.0
                baseline_source = {
                    "kind": "trigger",
                    "entity_id": int(target["entity_id"]),
                    "name": target.get("name"),
                    "spawn_count": len(target.get("spawns") or []),
                    "representative_point": list(point) if point else None,
                }
                sources = [baseline_source]
            elif direct_creature:
                family = "kill"
                target = direct_creature[0]
                npc_id = int(target["entity_id"])
                raw_npc = questie.npcs.get(npc_id)
                point = representative_point(target.get("spawns") or [])
                per_kill = kill_seconds(raw_npc)
                objective_seconds = count * per_kill
                objective_seconds_lower = objective_seconds
                objective_seconds_upper = objective_seconds
                baseline_source = {
                    "kind": "npc",
                    "entity_id": npc_id,
                    "name": target.get("name"),
                    "spawn_count": len(target.get("spawns") or []),
                    "representative_point": list(point) if point else None,
                    "npc_mid_health": npc_mid_health(raw_npc),
                    "single_kill_seconds": per_kill,
                    "single_kill_calculation": calculation_cell(
                        "fixed_five_box_operational_seconds_per_kill",
                        {"fixed_kill_seconds": FIXED_KILL_SECONDS},
                        per_kill,
                        unit="seconds",
                        source="user_five_box_operational_assumption",
                    ),
                }
                sources = [baseline_source]
            elif direct_object:
                raw_point_rows = sum(len(t.get("spawns") or []) for t in direct_object)
                unique_points = unique_spawn_points(direct_object)
                total_points = len(unique_points)
                respawn = object_respawn_input(direct_object, respawn_proxy)
                respawn_seconds = float(respawn["respawn_seconds"])
                respawn_seconds_lower = float(respawn["respawn_seconds_lower"])
                respawn_seconds_upper = float(respawn["respawn_seconds_upper"])
                family = "object_interact_single" if count <= 1 else "object_collect_multi"
                target = max(direct_object, key=lambda t: len(t.get("spawns") or []))
                point = representative_point(target.get("spawns") or [])
                baseline_source = {
                    "kind": "object",
                    "entity_id": int(target["entity_id"]),
                    "name": target.get("name"),
                    "spawn_count": len(target.get("spawns") or []),
                    "representative_point": list(point) if point else None,
                }
                if count <= 1:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds = 1 if count else 0
                    wait_rounds = 0
                    objective_seconds = 0.0
                    objective_seconds_lower = 0.0
                    objective_seconds_upper = 0.0
                elif total_points:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds, wait_rounds, objective_seconds = five_box_collect_wait_seconds(count, total_points, respawn_seconds)
                    objective_seconds_lower = wait_rounds * respawn_seconds_lower
                    objective_seconds_upper = wait_rounds * respawn_seconds_upper
                else:
                    total_required_count = count * FIVE_BOX_CHARACTERS
                    rounds = None
                    wait_rounds = None
                    objective_seconds = None
                    objective_seconds_lower = None
                    objective_seconds_upper = None
                object_collect_inputs = {
                    "per_character_required_count": count,
                    "characters": FIVE_BOX_CHARACTERS,
                    "five_box_required_count": total_required_count,
                    "raw_spawn_rows": raw_point_rows,
                    "unique_spawn_points": total_points,
                    "respawn_seconds": respawn_seconds,
                    "respawn_seconds_lower": respawn_seconds_lower,
                    "respawn_seconds_upper": respawn_seconds_upper,
                    "respawn_seconds_source": respawn["respawn_seconds_source"],
                    "respawn_point_estimate_policy": respawn["respawn_point_estimate_policy"],
                    "respawn_quality": respawn["respawn_quality"],
                    "respawn_evidence": respawn["respawn_evidence"],
                    "rounds": rounds,
                }
                sources = [baseline_source]

            if family == "mob_drop":
                objective_calculation = calculation_cell(
                    "baseline_source.expected_kills * baseline_source.single_kill_seconds",
                    {
                        "baseline_entity_id": baseline_source.get("entity_id") if baseline_source else None,
                        "expected_kills": baseline_source.get("expected_kills") if baseline_source else None,
                        "single_kill_seconds": baseline_source.get("single_kill_seconds") if baseline_source else None,
                    },
                    objective_seconds,
                    unit="seconds",
                    source="materialized_from_selected_ordinary_drop_source",
                    quality="estimated" if objective_seconds is not None else "missing_input",
                )
            elif family == "kill":
                objective_calculation = calculation_cell(
                    "required_count * fixed_five_box_operational_seconds_per_kill",
                    {
                        "required_count": count,
                        "fixed_kill_seconds": FIXED_KILL_SECONDS,
                    },
                    objective_seconds,
                    unit="seconds",
                    source="user_five_box_operational_assumption",
                )
            elif family == "object_collect_multi":
                respawn_quality = (object_collect_inputs or {}).get("respawn_quality")
                objective_calculation = calculation_cell(
                    "max(0, ceil(five_box_required_count / unique_spawn_points) - 1) * respawn_seconds",
                    object_collect_inputs or {"per_character_required_count": count, "characters": FIVE_BOX_CHARACTERS},
                    objective_seconds,
                    unit="seconds",
                    source="route_atlas_object_respawn_model",
                    quality=respawn_quality or ("estimated" if objective_seconds is not None else "missing_input"),
                )
                objective_calculation["result_range_seconds"] = {
                    "lower": objective_seconds_lower,
                    "estimate": objective_seconds,
                    "upper": objective_seconds_upper,
                }
            elif family == "object_interact_single":
                objective_calculation = calculation_cell(
                    "0",
                    {"interaction_count": count},
                    objective_seconds,
                    unit="seconds",
                    source="route_atlas_zero_interaction_time_rule",
                )
            elif family == "explore_trigger":
                objective_calculation = calculation_cell(
                    "0",
                    {"trigger_points": len(direct_trigger[0].get("spawns") or []) if direct_trigger else 0},
                    objective_seconds,
                    unit="seconds",
                    source="questie_trigger_end_zero_service_rule",
                    quality="structural",
                )
            else:
                objective_calculation = calculation_cell(
                    "unmodeled",
                    {},
                    objective_seconds,
                    unit="seconds",
                    source="unmodeled",
                    quality="unmodeled",
                )

            component = {
                "id": cid,
                "requirement_key": group_key,
                "family": family,
                "needed_count": count,
                "count_inference": count_detail,
                "label": (targets[0].get("source_item_name") or targets[0].get("name") or group_key),
                "sources": sources,
                "baseline_source": baseline_source,
                "estimated_objective_seconds": objective_seconds,
                "estimated_objective_seconds_lower": objective_seconds_lower,
                "estimated_objective_seconds_upper": objective_seconds_upper,
                "calculation": objective_calculation,
                "time_model": (
                    "expected_drops_x_kill_time" if family == "mob_drop" else
                    "count_x_kill_time" if family == "kill" else
                    "ceil(count/spawn_points)_x_respawn" if family == "object_collect_multi" else
                    "zero_interaction_time" if family == "object_interact_single" else
                    "zero_service_at_questie_trigger_end" if family == "explore_trigger" else
                    "unmodeled"
                ),
            }
            if baseline_source and baseline_source.get("representative_point"):
                component["baseline_point"] = baseline_source["representative_point"]
            components.append(component)

        classification = classify_task(quest, components, raw)
        type_counts[classification["primary"]] = type_counts.get(classification["primary"], 0) + 1

        known_scope = KNOWN_SCOPE.get(qid)
        scope = {
            "class": known_scope[0] if known_scope else None,
            "source": known_scope[1] if known_scope else None,
        }
        geom = geometry.get("quests", {}).get(str(qid))
        if geom:
            scope["geometry"] = geom.get("geometry")
            scope["entry_from_start"] = geom.get("entry_from_start")

        routed_components = [c for c in components if c.get("baseline_point")]
        route_estimate = None
        known_component_times = [c.get("estimated_objective_seconds") for c in components]
        known_component_times_lower = [c.get("estimated_objective_seconds_lower") for c in components]
        known_component_times_upper = [c.get("estimated_objective_seconds_upper") for c in components]
        objective_total = None if any(v is None for v in known_component_times) else sum(float(v) for v in known_component_times)
        objective_total_lower = None if any(v is None for v in known_component_times_lower) else sum(float(v) for v in known_component_times_lower)
        objective_total_upper = None if any(v is None for v in known_component_times_upper) else sum(float(v) for v in known_component_times_upper)
        if start and end:
            if routed_components:
                route_estimate = shortest_component_path(start, end, routed_components)
            elif classification["primary"] == "handoff":
                sec = travel_seconds(start, end)
                route_estimate = {
                    "order": [],
                    "travel_to_work_seconds": sec,
                    "work_internal_travel_seconds": 0.0,
                    "work_to_turnin_seconds": 0.0,
                    "total_travel_seconds": sec,
                }
            if route_estimate is not None:
                route_estimate["objective_seconds"] = objective_total
                route_estimate["objective_seconds_lower"] = objective_total_lower
                route_estimate["objective_seconds_upper"] = objective_total_upper
                route_estimate["estimated_total_seconds"] = (
                    route_estimate["total_travel_seconds"] + objective_total if objective_total is not None else None
                )
                route_estimate["estimated_total_seconds_lower"] = (
                    route_estimate["total_travel_seconds"] + objective_total_lower if objective_total_lower is not None else None
                )
                route_estimate["estimated_total_seconds_upper"] = (
                    route_estimate["total_travel_seconds"] + objective_total_upper if objective_total_upper is not None else None
                )
                route_estimate["calculations"] = {
                    "travel_total": calculation_cell(
                        "travel_to_work_seconds + work_internal_travel_seconds + work_to_turnin_seconds",
                        {
                            "travel_to_work_seconds": route_estimate.get("travel_to_work_seconds"),
                            "work_internal_travel_seconds": route_estimate.get("work_internal_travel_seconds"),
                            "work_to_turnin_seconds": route_estimate.get("work_to_turnin_seconds"),
                        },
                        route_estimate.get("total_travel_seconds"),
                        unit="seconds",
                        source="materialized_route_geometry",
                    ),
                    "objective_total": calculation_cell(
                        "sum(component.estimated_objective_seconds)",
                        {"component_seconds": known_component_times},
                        objective_total,
                        unit="seconds",
                        source="materialized_task_components",
                        quality="estimated" if objective_total is not None else "missing_input",
                    ),
                    "quest_total": calculation_cell(
                        "total_travel_seconds + objective_seconds",
                        {
                            "total_travel_seconds": route_estimate.get("total_travel_seconds"),
                            "objective_seconds": objective_total,
                        },
                        route_estimate.get("estimated_total_seconds"),
                        unit="seconds",
                        source="materialized_task_profile",
                        quality="estimated" if route_estimate.get("estimated_total_seconds") is not None else "missing_input",
                    ),
                }
                route_estimate["calculations"]["objective_total"]["result_range_seconds"] = {
                    "lower": objective_total_lower,
                    "estimate": objective_total,
                    "upper": objective_total_upper,
                }
                route_estimate["calculations"]["quest_total"]["result_range_seconds"] = {
                    "lower": route_estimate.get("estimated_total_seconds_lower"),
                    "estimate": route_estimate.get("estimated_total_seconds"),
                    "upper": route_estimate.get("estimated_total_seconds_upper"),
                }

        labels = list(classification["labels"])
        if scope["class"]:
            labels.append(f"scope:{scope['class']}")
        if any(c["family"] == "mob_drop" for c in components):
            labels.append("requires:drop_rate")
        if any(any(s.get("low_density_shortcut") for s in c.get("sources", [])) for c in components):
            labels.append("strategy:shortcut_source_available")

        quest_level = quest.get("quest_level")
        last_full_xp_level = int(quest_level) + 5 if isinstance(quest_level, (int, float)) else None
        raw_quest = questie.quests.get(qid, {})
        special_flags = int(raw_quest.get(24) or 0) if isinstance(raw_quest, dict) else 0
        repeatable = bool(special_flags & 1)
        quest_xp_row = questie.quest_xp.get(qid)
        quest_xp_base = int(quest_xp_row.get(2)) if isinstance(quest_xp_row, dict) and isinstance(quest_xp_row.get(2), (int, float)) else None
        profiles[qid_text] = {
            "quest_id": qid,
            "name": quest.get("name"),
            "quest_level": quest_level,
            "last_full_xp_level": last_full_xp_level,
            "quest_xp_base": quest_xp_base,
            "quest_xp_source": "questie_xpdb_wotlk" if quest_xp_base is not None else None,
            "required_level": quest.get("required_level"),
            "special_flags": special_flags,
            "repeatable": repeatable,
            "classification": classification,
            "scope": scope,
            "labels": sorted(set(labels)),
            "components": components,
            "solo_time_estimate": route_estimate,
            "time_model_quality": "v1_uniform_assumptions",
        }

    payload = {
        "meta": {
            "zone_id": atlas["meta"]["zone_id"],
            "zone_name": atlas["meta"]["zone_name"],
            "questie_version": atlas["meta"]["questie_version"],
            "questie_sha256": atlas["meta"]["questie_sha256"],
            "map_width_yards": MAP_WIDTH_YARDS,
            "map_height_yards": MAP_HEIGHT_YARDS,
            "travel_speed_yards_per_sec_assumption": TRAVEL_SPEED_YARDS_PER_SEC,
            "five_box_characters": FIVE_BOX_CHARACTERS,
            "fixed_kill_seconds": FIXED_KILL_SECONDS,
            "default_object_respawn_seconds": DEFAULT_OBJECT_RESPAWN_SECONDS,
            "respawn_proxy_available": respawn_proxy.available,
            "respawn_proxy_path": str(RESPAWN_PROXY.relative_to(ROOT)),
            "respawn_proxy_meta": respawn_proxy.meta,
            "travel_model": "straight-line Questie coordinates scaled to Zangarmarsh yard dimensions; terrain ignored uniformly",
            "kill_model": "fixed 15 seconds per ordinary kill including five-box operational overhead",
            "drop_model": "Questie effective GetItemDroprate precedence; expected kills = five_box_required_count / p; each expected kill costs fixed 15s",
            "object_collect_model": "max(0, ceil(five_box_required_count / unique_spawn_points) - 1) * respawn_seconds; first round has no respawn wait", 
            "important": "All time assumptions are explicit and replaceable by observations; labels/facts are persisted separately from route optimization.",
        },
        "summary": {
            "quests": len(profiles),
            "task_type_counts": type_counts,
            "mob_drop_tasks": drop_task_count,
            "drop_rate_pairs_resolved": drop_pair_count,
        },
        "quests": profiles,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(OUTPUT)


if __name__ == "__main__":
    main()
