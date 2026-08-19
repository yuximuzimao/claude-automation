from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie
from lib.wotlk_quest_rewards import base_quest_xp_at_level

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
TIMING = ROOT / "data/route-atlas/route-atlas-timing-estimates.json"
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
BOREAN_FOUNDATION = ROOT / "data/route-atlas/borean-tundra-task-foundation.json"
DRAGON_FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OUT = ROOT / "data/route-atlas/northrend-68-80-time-xp-model.json"
REPORT = ROOT / "docs/analysis/2026-08-18-northrend-68-80-time-xp-model.md"

XP_TO_NEXT = {
    68: 648000,
    69: 717000,
    70: 1523800,
    71: 1539000,
    72: 1555700,
    73: 1571800,
    74: 1587900,
    75: 1604200,
    76: 1620700,
    77: 1637400,
    78: 1653900,
    79: 1670800,
}
SERVER_XP_MULTIPLIER = 2.0
VETERAN_MINUTES = 840.0

# Live calibration: user-reported minimum character at the point where the rebuilt Borean route
# turns in Boiling Point and accepts Motes of the Enraged.
LIVE_LEVEL = 73
LIVE_XP_IN_LEVEL = 21058
LIVE_CHECKPOINT_ACTION_TOKEN = "接《风暴微粒》"

# Current-axis cleanup for the old auto candidate skeletons. These are not speed-pruning deletions:
# they are faction/dungeon/duplicate-repeat/mutually-exclusive alternatives determined by current state.
GRIZZLY_EXCLUDE = {
    11981,  # mutually exclusive with 12074; current Conquest-Hold axis naturally uses 12074
    12434,  # repeatable, zero-XP solvent followup; no second-round generation
    12446,  # Alliance-only counterpart
    12763,  # mutually exclusive with 12789 already carried from Dragonblight
}
ZULDRAK_EXCLUDE = {
    12633, 12638, 12643, 12649,  # branch requires dungeon quest 12238; current outdoor axis uses other branch
    12792, 12793,  # mutually exclusive entry breadcrumbs; current axis already carries 12789
}

# Manual service estimates only for tasks whose Questie objective source is incomplete/scripted.
# Values represent intrinsic task service after arrival at the local objective area; travel between
# areas and NPC accept/turn-in are modeled separately. Ranges are deliberately wider than normal.
MANUAL_SERVICE: dict[int, tuple[float, float, float, str]] = {
    # Grizzly Hills
    11990: (4.0, 6.0, 9.0, "Imbued Vial + Waterweed + 3 Haze Leaves mixed collection"),
    12007: (3.0, 4.5, 7.0, "named mojo + brazier/elixir scripted use"),
    12026: (7.0, 10.0, 15.0, "8 missing journal pages; five-box personal collection risk"),
    12058: (2.0, 3.5, 5.0, "three rune-plate deciphers"),
    12099: (3.0, 4.5, 6.5, "use Runebreaker to free 4 giants"),
    12137: (5.0, 8.0, 12.0, "snow pickup + spirit-particle collection + script"),
    12165: (0.4, 0.7, 1.2, "completed blueprint item handoff; no independent grind"),
    12197: (3.0, 4.5, 6.5, "two named power cells"),
    12241: (2.0, 3.5, 5.5, "burn Vordrassil sapling and recover ashes"),
    12279: (4.0, 7.0, 11.0, "6 Northern Salmon; personal collection risk"),
    # Zul'Drak
    12527: (3.0, 5.0, 8.0, "feed rats to basilisks; collect 5 crystals"),
    12555: (4.0, 5.5, 8.0, "Tangled Skein Thrower destroys 5 plague sprayers"),
    12557: (3.0, 5.0, 8.0, "four laboratory ingredients"),
    12622: (5.0, 7.5, 11.0, "trigger/kill three Jin'Alai leaders and recover treasures"),
    12627: (2.0, 3.5, 5.5, "disturb four cauldrons"),
    12648: (2.0, 3.5, 5.0, "Scourge disguise + purchase Bitter Plasma"),
    12677: (3.0, 5.5, 8.5, "Voltarus disguise package + 5 blight crystals"),
    12729: (3.0, 4.5, 7.0, "two essence items"),
    12919: (8.0, 12.0, 18.0, "Gymer vehicle: 100 Scourge + 3 named targets"),
}

# Empirical route-structure calibration from the already-reviewed Borean and Dragonblight routes.
# Raw per-task intrinsic service is heavily overlapping. Formal route objective+special time is
# 44.7% of card-sum in Borean and 58.5% in Dragonblight.
OVERLAP_FACTOR = (0.447, 0.516, 0.585)
# Five-box accept/turn-in hub cost derived from reviewed maps: ~0.417-0.433 min per explicit quest op.
HUB_MINUTES_PER_QUEST_OP = (0.36, 0.425, 0.50)
# Old auto skeleton normalized path is compressed by reviewed route ordering. Borean ratio=0.376,
# Dragonblight ratio=0.586. Formal movement costs ~0.0508-0.0521 min per normalized coordinate unit.
PATH_COMPRESSION = (0.376, 0.481, 0.586)
MINUTES_PER_NORMALIZED_UNIT = (0.0508, 0.05145, 0.0521)


def advance(data: Any, level: int, xp: int, qid: int, natural_ratio: float = 0.0) -> tuple[int, int, int]:
    quest_xp = int(base_quest_xp_at_level(data, qid, level) * SERVER_XP_MULTIPLIER)
    gain = int(round(quest_xp * (1.0 + natural_ratio)))
    xp += gain
    while level < 80 and xp >= XP_TO_NEXT[level]:
        xp -= XP_TO_NEXT[level]
        level += 1
    return level, xp, quest_xp


def route_turnins(route_key: str, foundation_path: Path, start_after_token: str | None = None) -> list[tuple[int, str]]:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes[route_key]
    foundation = json.loads(foundation_path.read_text(encoding="utf-8"))["tasks"]
    by_name: dict[str, list[int]] = {}
    for task in foundation:
        if str(task.get("scope_status", "")).startswith("include_") or task.get("scope_status") == "defer_future_level_revisit":
            by_name.setdefault(str(task["name"]), []).append(int(task["quest_id"]))
    seen: set[int] = set()
    active = start_after_token is None
    result: list[tuple[int, str]] = []
    for point in route["points"]:
        action = str(point[3])
        if start_after_token and start_after_token in action:
            active = True
            continue
        if not active:
            continue
        for name in re.findall(r"交《([^》]+)》", action):
            ids = by_name.get(name, [])
            qid = next((value for value in ids if value not in seen), ids[0] if ids else None)
            if qid is not None and qid not in seen:
                seen.add(qid)
                result.append((qid, name))
    return result


def candidate_route(zone_id: int, slug: str) -> dict[str, Any]:
    return json.loads((ROOT / f"data/routes/world-candidate/{zone_id}-{slug}/route.json").read_text(encoding="utf-8"))


def filtered_turnins(route: dict[str, Any], excluded: set[int], data_for_names: Any | None = None) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    seen: set[int] = set()
    for step in route["steps"]:
        if step.get("action") != "交付":
            continue
        names = list(step.get("quest_names") or [])
        for i, raw_qid in enumerate(step.get("quest_ids", [])):
            qid = int(raw_qid)
            if qid in excluded or qid in seen:
                continue
            seen.add(qid)
            if i < len(names):
                name = names[i]
            else:
                row = data_for_names.quests.get(qid) if data_for_names is not None else None
                raw_name = row.get(1) if isinstance(row, dict) else str(qid)
                name = data_for_names.local_name(data_for_names.quest_names, qid, str(raw_name)) if data_for_names is not None else str(qid)
            result.append((qid, name))
    return result


def live_natural_xp_lower_bound(data: Any) -> dict[str, Any]:
    all_turns = route_turnins("borean", BOREAN_FOUNDATION)
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    route = routes["borean"]
    foundation = json.loads(BOREAN_FOUNDATION.read_text(encoding="utf-8"))["tasks"]
    by_name: dict[str, list[int]] = {}
    for task in foundation:
        if str(task.get("scope_status", "")).startswith("include_"):
            by_name.setdefault(str(task["name"]), []).append(int(task["quest_id"]))
    level, xp, task_total, turnins = 68, 0, 0, 0
    seen: set[int] = set()
    point_index = None
    for idx, point in enumerate(route["points"], 1):
        action = str(point[3])
        for name in re.findall(r"交《([^》]+)》", action):
            ids = by_name.get(name, [])
            qid = next((q for q in ids if q not in seen), ids[0] if ids else None)
            if qid is None or qid in seen:
                continue
            seen.add(qid)
            level, xp, qxp = advance(data, level, xp, qid, 0.0)
            task_total += qxp
            turnins += 1
        if LIVE_CHECKPOINT_ACTION_TOKEN in action:
            point_index = idx
            break
    actual_total = sum(XP_TO_NEXT[level] for level in range(68, LIVE_LEVEL)) + LIVE_XP_IN_LEVEL
    natural_lower = actual_total - task_total
    return {
        "route_point_index": point_index,
        "turnins_before_checkpoint": turnins,
        "task_only_xp_to_checkpoint": task_total,
        "actual_total_xp_to_checkpoint": actual_total,
        "natural_xp_lower_bound": natural_lower,
        "natural_to_task_ratio_lower_bound": natural_lower / task_total if task_total else 0.0,
        "note": "Task-only simulation keeps the character lower-level and therefore tends to over-credit old quests; the difference is a conservative lower bound on natural kill/exploration XP.",
    }


def quest_service_raw(universe_by_id: dict[int, dict[str, Any]], qids: set[int]) -> tuple[float, float, float, list[int]]:
    low = center = high = 0.0
    unknown: list[int] = []
    for qid in sorted(qids):
        task = universe_by_id.get(qid)
        if qid in MANUAL_SERVICE:
            lo, mid, hi, _ = MANUAL_SERVICE[qid]
            low += lo; center += mid; high += hi
            continue
        if not task:
            unknown.append(qid)
            continue
        service = task.get("intrinsic_service_time") or {}
        minutes = service.get("minutes")
        if service.get("status") == "estimated" and isinstance(minutes, (int, float)):
            minutes = float(minutes)
            low += minutes * 0.8
            center += minutes
            high += minutes * 1.3
        else:
            unknown.append(qid)
    return low, center, high, unknown


def route_prefix_metrics(
    route: dict[str, Any],
    excluded: set[int],
    universe_by_id: dict[int, dict[str, Any]],
    max_turnins: int | None = None,
) -> dict[str, Any]:
    selected_qids = {int(q) for step in route["steps"] for q in step.get("quest_ids", []) if int(q) not in excluded}
    kept_steps: list[dict[str, Any]] = []
    turn_seen: set[int] = set()
    completed_turn_count = 0
    for step in route["steps"]:
        step_qids = [int(q) for q in step.get("quest_ids", []) if int(q) in selected_qids]
        if not step_qids:
            continue
        kept_steps.append(step)
        if step.get("action") == "交付":
            for qid in step_qids:
                if qid not in turn_seen:
                    turn_seen.add(qid)
                    completed_turn_count += 1
                    if max_turnins is not None and completed_turn_count >= max_turnins:
                        break
        if max_turnins is not None and completed_turn_count >= max_turnins:
            break

    objective_qids: set[int] = set()
    accept_ops = turn_ops = 0
    points: list[tuple[float, float]] = []
    for step in kept_steps:
        qids = [int(q) for q in step.get("quest_ids", []) if int(q) in selected_qids]
        if step.get("action") == "完成目标":
            objective_qids.update(qids)
        elif step.get("action") == "接取":
            accept_ops += len(set(qids))
        elif step.get("action") == "交付":
            turn_ops += len(set(qids))
        rep = (step.get("anchor_details") or {}).get("representative")
        if isinstance(rep, dict) and isinstance(rep.get("x"), (int, float)) and isinstance(rep.get("y"), (int, float)):
            points.append((float(rep["x"]), float(rep["y"])))

    raw_distance = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
    service_raw = quest_service_raw(universe_by_id, objective_qids)
    raw_low, raw_center, raw_high, unknown = service_raw
    service = {
        "low": raw_low * OVERLAP_FACTOR[0],
        "center": raw_center * OVERLAP_FACTOR[1],
        "high": raw_high * OVERLAP_FACTOR[2],
    }
    hub_ops = accept_ops + turn_ops
    hub = {
        "low": hub_ops * HUB_MINUTES_PER_QUEST_OP[0],
        "center": hub_ops * HUB_MINUTES_PER_QUEST_OP[1],
        "high": hub_ops * HUB_MINUTES_PER_QUEST_OP[2],
    }
    movement = {
        "low": raw_distance * PATH_COMPRESSION[0] * MINUTES_PER_NORMALIZED_UNIT[0],
        "center": raw_distance * PATH_COMPRESSION[1] * MINUTES_PER_NORMALIZED_UNIT[1],
        "high": raw_distance * PATH_COMPRESSION[2] * MINUTES_PER_NORMALIZED_UNIT[2],
    }
    total = {key: service[key] + hub[key] + movement[key] for key in ("low", "center", "high")}
    return {
        "selected_route_task_count": len(selected_qids),
        "turnins_in_prefix": completed_turn_count,
        "objective_task_count_in_prefix": len(objective_qids),
        "accept_ops": accept_ops,
        "turnin_ops": turn_ops,
        "raw_normalized_path_distance": raw_distance,
        "raw_task_service_minutes": {"low": raw_low, "center": raw_center, "high": raw_high},
        "overlapped_task_service_minutes": service,
        "hub_minutes": hub,
        "movement_minutes": movement,
        "total_minutes": total,
        "unknown_service_qids": unknown,
    }


def predict_reach_80(data: Any, natural_ratio: float, grizzly: dict[str, Any], zuldrak: dict[str, Any]) -> dict[str, Any]:
    level, xp = LIVE_LEVEL, LIVE_XP_IN_LEVEL
    stages: list[tuple[str, list[tuple[int, str]]]] = [
        ("北风剩余", route_turnins("borean", BOREAN_FOUNDATION, LIVE_CHECKPOINT_ACTION_TOKEN)),
        ("龙骨荒野", route_turnins("dragonblight", DRAGON_FOUNDATION)),
        ("灰熊丘陵", filtered_turnins(grizzly, GRIZZLY_EXCLUDE, data)),
        ("祖达克", filtered_turnins(zuldrak, ZULDRAK_EXCLUDE, data)),
    ]
    stage_counts: dict[str, int] = {}
    for stage_name, turns in stages:
        stage_counts[stage_name] = 0
        for qid, name in turns:
            level, xp, _ = advance(data, level, xp, qid, natural_ratio)
            stage_counts[stage_name] += 1
            if level >= 80:
                return {
                    "natural_ratio": natural_ratio,
                    "reach_zone": stage_name,
                    "turnin_index_in_zone": stage_counts[stage_name],
                    "quest_id": qid,
                    "quest_name": name,
                    "xp_into_80": xp,
                    "stage_counts": stage_counts,
                }
    return {"natural_ratio": natural_ratio, "reach_zone": None, "stage_counts": stage_counts, "exit_state": [level, xp]}


def main() -> None:
    data = load_questie(QUESTIE_ZIP)
    timing = json.loads(TIMING.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    universe_by_id = {int(task["quest_id"]): task for task in universe["tasks"]}
    grizzly = candidate_route(394, "grizzly-hills")
    zuldrak = candidate_route(66, "zul-drak")

    live_cal = live_natural_xp_lower_bound(data)
    calibrated_ratio = float(live_cal["natural_to_task_ratio_lower_bound"])
    ratio_cases = [0.0, 0.10, calibrated_ratio, 0.20]
    reach_cases = [predict_reach_80(data, ratio, grizzly, zuldrak) for ratio in ratio_cases]
    center_case = reach_cases[2]
    if center_case.get("reach_zone") != "祖达克":
        raise RuntimeError(f"expected calibrated case to reach 80 in Zul'Drak, got {center_case}")

    grizzly_metrics = route_prefix_metrics(grizzly, GRIZZLY_EXCLUDE, universe_by_id)
    zul_center_metrics = route_prefix_metrics(
        zuldrak,
        ZULDRAK_EXCLUDE,
        universe_by_id,
        max_turnins=int(center_case["turnin_index_in_zone"]),
    )
    # Timing envelope for the level-80 point uses XP-position uncertainty too: 20% natural XP is the
    # optimistic task-progress case; 10% is the conservative clean-route case. Zero-natural is retained
    # as a hard task-only location ceiling but is too pessimistic for a time envelope after live evidence.
    zul_conservative_k = int(reach_cases[1]["turnin_index_in_zone"])
    zul_optimistic_k = int(reach_cases[3]["turnin_index_in_zone"])
    zul_conservative_metrics = route_prefix_metrics(zuldrak, ZULDRAK_EXCLUDE, universe_by_id, zul_conservative_k)
    zul_optimistic_metrics = route_prefix_metrics(zuldrak, ZULDRAK_EXCLUDE, universe_by_id, zul_optimistic_k)

    borean = timing["borean"]
    dragon = timing["dragonblight"]
    total_center = float(borean["centerMinutes"]) + float(dragon["centerMinutes"]) + grizzly_metrics["total_minutes"]["center"] + zul_center_metrics["total_minutes"]["center"]
    total_low = float(borean["rangeMinutes"][0]) + float(dragon["rangeMinutes"][0]) + grizzly_metrics["total_minutes"]["low"] + zul_optimistic_metrics["total_minutes"]["low"]
    total_high = float(borean["rangeMinutes"][1]) + float(dragon["rangeMinutes"][1]) + grizzly_metrics["total_minutes"]["high"] + zul_conservative_metrics["total_minutes"]["high"]

    payload = {
        "schema_version": 1,
        "status": "TASK_BASED_68_80_MODEL_V1",
        "method": {
            "xp": "formal Borean/Dragon turn-in order + cleaned Grizzly/Zul'Drak candidate turn-in order; exact WotLK level-dependent quest XP; live natural-XP calibration only locates level-80 point",
            "time": "reviewed Borean/Dragon component model + task-card service / hub-operation / coordinate movement model for later maps; overlap and path-compression factors calibrated from reviewed maps",
            "not_used": ["XP per hour extrapolation", "raw Journey discussion time", "unopened future flight points", "task-count times average-minutes shortcut"],
        },
        "live_natural_xp_calibration": live_cal,
        "reach_80_cases": reach_cases,
        "cleaned_candidate_counts": {
            "grizzly_auto_qids": len({int(q) for step in grizzly["steps"] for q in step.get("quest_ids", [])}),
            "grizzly_selected_qids": grizzly_metrics["selected_route_task_count"],
            "grizzly_excluded_qids": sorted(GRIZZLY_EXCLUDE),
            "zuldrak_auto_qids": len({int(q) for step in zuldrak["steps"] for q in step.get("quest_ids", [])}),
            "zuldrak_selected_qids": route_prefix_metrics(zuldrak, ZULDRAK_EXCLUDE, universe_by_id)["selected_route_task_count"],
            "zuldrak_excluded_qids": sorted(ZULDRAK_EXCLUDE),
        },
        "map_time_minutes": {
            "borean_full": {"low": borean["rangeMinutes"][0], "center": borean["centerMinutes"], "high": borean["rangeMinutes"][1]},
            "dragonblight_full": {"low": dragon["rangeMinutes"][0], "center": dragon["centerMinutes"], "high": dragon["rangeMinutes"][1]},
            "grizzly_full": grizzly_metrics,
            "zuldrak_to_80_center": zul_center_metrics,
            "zuldrak_to_80_optimistic_20pct_natural": zul_optimistic_metrics,
            "zuldrak_to_80_conservative_10pct_natural": zul_conservative_metrics,
        },
        "total_68_80": {
            "low_minutes": total_low,
            "center_minutes": total_center,
            "high_minutes": total_high,
            "low_hours": total_low / 60.0,
            "center_hours": total_center / 60.0,
            "high_hours": total_high / 60.0,
            "veteran_benchmark_minutes": VETERAN_MINUTES,
            "center_gap_minutes": total_center - VETERAN_MINUTES,
            "center_gap_hours": (total_center - VETERAN_MINUTES) / 60.0,
            "center_slower_percent": (total_center / VETERAN_MINUTES - 1.0) * 100.0,
        },
        "manual_special_task_service": {
            str(qid): {"low": v[0], "center": v[1], "high": v[2], "basis": v[3]}
            for qid, v in sorted(MANUAL_SERVICE.items())
        },
        "calibration_constants": {
            "overlap_factor": OVERLAP_FACTOR,
            "hub_minutes_per_quest_op": HUB_MINUTES_PER_QUEST_OP,
            "path_compression": PATH_COMPRESSION,
            "minutes_per_normalized_unit": MINUTES_PER_NORMALIZED_UNIT,
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = payload["total_68_80"]
    lines = [
        "# 诺森德68→80任务级时间/经验模型 V1",
        "",
        "## 结论",
        "",
        f"- 80级位置：中心模型在祖达克第{center_case['turnin_index_in_zone']}个有效交付附近，任务为{center_case['quest_id']}《{center_case['quest_name']}》。",
        f"- 严格上界（以后完全没有自然经验）：祖达克第{reach_cases[0]['turnin_index_in_zone']}个交付；10%自然经验：第{reach_cases[1]['turnin_index_in_zone']}个；当前北风实跑已证明的保守自然经验比率{calibrated_ratio:.1%}：第{center_case['turnin_index_in_zone']}个；20%：第{reach_cases[3]['turnin_index_in_zone']}个。",
        f"- clean component中心：{total['center_hours']:.2f}小时；模型区间：{total['low_hours']:.2f}–{total['high_hours']:.2f}小时。",
        f"- 对老手14小时基准：中心慢{total['center_gap_hours']:.2f}小时（{total['center_slower_percent']:.1f}%）。",
        "- 该时间不包含用户与AI讨论、改路线、暂停；也不使用这些污染墙钟反校准。",
        "",
        "## 分段中心时间",
        "",
        f"- 北风全图：{borean['centerMinutes']/60:.2f}小时。",
        f"- 龙骨全图：{dragon['centerMinutes']/60:.2f}小时。",
        f"- 灰熊全图：{grizzly_metrics['total_minutes']['center']/60:.2f}小时。",
        f"- 祖达克开图→中心80节点：{zul_center_metrics['total_minutes']['center']/60:.2f}小时。",
        "",
        "## 经验校准",
        "",
        f"- 北风到《风暴微粒》接取点：纯任务模拟{live_cal['task_only_xp_to_checkpoint']:,} XP；最低号实际{live_cal['actual_total_xp_to_checkpoint']:,} XP。",
        f"- 因此至少{live_cal['natural_xp_lower_bound']:,} XP来自必经击杀/探索等自然经验，约为同期任务经验的{calibrated_ratio:.1%}。",
        "- 该比例只用于确定80级出现在哪个祖达克任务附近，不用于按XP/h估时间。",
        "",
        "## 当前边界",
        "",
        "- 灰熊/祖达克仍是基于Questie任务卡 + 自动坐标骨架的任务级模型，还不是像北风/龙骨一样完成用户实跑复审的正式路线。因此模型区间刻意保留较宽。",
        "- 任务卡80级折金已独立于练级2倍经验倍率；它只是经济收益组件，不自动推出任务保留。11591《钢腭的车队》按可选面包屑事实在当前基线中不做。", 
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"reach80": center_case, "total": payload["total_68_80"], "grizzly_center": grizzly_metrics["total_minutes"]["center"], "zul_center": zul_center_metrics["total_minutes"]["center"], "unknown_grizzly": grizzly_metrics["unknown_service_qids"], "unknown_zul": zul_center_metrics["unknown_service_qids"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
