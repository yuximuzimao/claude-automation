#!/usr/bin/env python3
"""Build first-pass dynamic 35-55 quest-route candidates.

This is deliberately a heuristic stage, not the final route optimizer. It enforces
actual completion-level quest XP, current prerequisite state, the current pending
turn-in, outdoor-only filtering, and placeholder Feralas/Tanaris coverage. It does
not yet remove shared travel/combat costs; Codex C1 task blocks will be merged in a
later stage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data/routes/horde/blood-elf/35-55-optimizer-input.json"
DEFAULT_OUTPUT = ROOT / "data/routes/horde/blood-elf/35-55-route-solutions.json"
DEFAULT_AUDIT = ROOT / "docs/archive/analysis/2026-08-04-35-55-optimizer-audit.md"

CURRENTLY_AVAILABLE_STATES = {
    "available_at_35",
    "available_at_35_conditional_trigger",
    "active",
    "objective_complete_pending_turnin",
}


@dataclass(frozen=True)
class Progress:
    level: int
    xp: int


@dataclass
class ReplayResult:
    valid: bool
    final: Progress
    steps: list[dict[str, Any]]
    zone_counts: Counter[str]
    time_totals: dict[str, float]
    reason: str | None = None


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def advance(progress: Progress, reward: int, xp_to_next: dict[int, int], target: int) -> Progress:
    level, xp = progress.level, progress.xp + max(0, int(reward))
    while level < target:
        needed = xp_to_next[level]
        if xp < needed:
            break
        xp -= needed
        level += 1
    if level >= target:
        return Progress(target, xp)
    return Progress(level, xp)


def task_reward(task: dict[str, Any], level: int) -> int:
    table = task.get("xp_by_completion_level", {})
    if level >= 55:
        return 0
    value = table.get(str(level))
    if value is None:
        value = table.get(str(min(max(level, 35), 54)), 0)
    return int(value or 0)


def scenario_time(task: dict[str, Any], scenario: str) -> float:
    """Return independent task time for one scenario.

    Quest 195 and any future objective-complete task only retain travel,
    interaction, and scripted time. Objective combat is already complete.
    """
    if task.get("candidate_state") == "objective_complete_pending_turnin":
        components = task.get("azerothcore_adjusted_time_components") or task.get(
            "standalone_time_components", {}
        )
        total = 0.0
        for key in ("travel", "interactions", "escort_or_defense"):
            total += float((components.get(key) or {}).get(scenario, 0.0) or 0.0)
        return max(0.2, total)

    adjusted = task.get("azerothcore_adjusted_standalone_time") or {}
    standalone = task.get("standalone_time_at_earliest_level") or {}
    value = adjusted.get(scenario)
    if value is None:
        value = standalone.get(scenario)
    if value is None:
        # Zero-XP chain transitions still need a nonzero operation cost.
        value = 2.0
    return max(0.2, float(value))


def risk_multiplier(task: dict[str, Any], config: dict[str, Any], mode: str) -> float:
    multipliers = config["risk_multipliers"]
    factors: list[float] = []
    flags = set(task.get("route_flags", []))
    review = set(task.get("manual_review_reasons", []))

    if task.get("confidence") == "low_until_manual_review":
        factors.append(float(multipliers["low_confidence"]))
    for flag in ("elite_or_rare_target", "object_respawn_and_multi_click_unknown", "active_item_or_spell_use"):
        if flag in flags:
            factors.append(float(multipliers[flag]))
    if task.get("task_class") == "item_source_not_in_questie" or any(
        str(reason).startswith("item_source_missing") for reason in review
    ):
        factors.append(float(multipliers["item_source_not_in_questie"]))
    if task.get("candidate_state") == "available_at_35_conditional_trigger":
        factors.append(float(multipliers["conditional_trigger"]))

    audit = config.get("_audit_by_quest", {}).get(int(task["quest_id"]))
    if audit:
        if audit.get("audit_status") == "needs_live_test":
            factors.append(float(multipliers["needs_live_test"]))
        if audit.get("route_tendency") in {
            "conditional_candidate_with_stop_loss",
            "defer_until_evidence_or_live_test",
        }:
            factors.append(float(multipliers["conditional_stop_loss"]))

    product = math.prod(factors) if factors else 1.0
    if mode == "risk_averse":
        return product
    # Central profiles retain a modest uncertainty charge without turning the
    # reference-risk model into the pessimistic scenario.
    return product ** 0.35


def adjusted_time(task: dict[str, Any], scenario: str, config: dict[str, Any], mode: str) -> float:
    return scenario_time(task, scenario) * risk_multiplier(task, config, mode)


def transition_time(from_zone: str, to_zone: str, scenario: str, config: dict[str, Any]) -> float:
    transport = config["_transport"]
    if from_zone == to_zone:
        return 0.0
    override = transport.get("known_directed_overrides", {}).get(f"{from_zone}|{to_zone}")
    if override is not None:
        return float(override.get(scenario, 0.0) or 0.0)

    metadata = transport.get("zone_metadata", {})
    left = metadata.get(from_zone)
    right = metadata.get(to_zone)
    defaults = transport["default_transition_minutes"]
    if not left or not right:
        category = "unknown"
    elif left["continent"] != right["continent"]:
        category = "cross_continent"
    elif left["cluster"] == right["cluster"]:
        category = "same_cluster"
    else:
        adjacent = {
            frozenset(pair) for pair in transport.get("adjacent_clusters", [])
        }
        category = (
            "adjacent_cluster"
            if frozenset((left["cluster"], right["cluster"])) in adjacent
            else "same_continent"
        )
    return float(defaults[category][scenario])


def effective_min_level(task: dict[str, Any], profile: dict[str, Any]) -> int:
    minimum = max(
        int(task.get("required_level") or 0),
        int(task.get("earliest_completion_level") or 0),
    )
    # Pure dialogue/turn-in steps do not inherit the surrounding hostile-area
    # quest level. All objective-bearing tasks do, because an object quest can
    # otherwise look safe even when the object sits among much higher-level mobs.
    if task.get("task_class") != "travel_dialogue_or_turnin":
        quest_level = int(task.get("quest_level") or 0)
        max_gap = int(profile.get("max_quest_level_gap", 4))
        minimum = max(minimum, quest_level - max_gap)
    return minimum


def prereqs_met(
    task: dict[str, Any], done: set[int], level: int, profile: dict[str, Any]
) -> bool:
    if task.get("candidate_state") == "objective_complete_pending_turnin":
        return True
    if effective_min_level(task, profile) > level:
        return False
    # The candidate catalog was built from the full Questie completion history.
    # Empty missing-prerequisite fields mean the prerequisites were already met
    # before this optimizer starts, including prerequisites outside this band.
    if not task.get("missing_group_prerequisites") and not task.get("missing_single_prerequisites"):
        return True
    group = [int(value) for value in task.get("pre_group", [])]
    single = [int(value) for value in task.get("pre_single", [])]
    group_ok = all(value in done for value in group)
    single_ok = not single or any(value in done for value in single)
    return group_ok and single_ok


def mandatory_satisfied(zone_counts: Counter[str], config: dict[str, Any]) -> bool:
    return all(
        zone_counts[entry["zone"]] >= int(entry["min_selected_tasks"])
        for entry in config["mandatory_zone_placeholders"]
    )


def build_eligible(
    tasks: list[dict[str, Any]], config: dict[str, Any], include_conditional: bool
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    excluded_ids = {int(value) for value in config["hard_excluded_task_ids"]}
    excluded_flags = set(config["hard_excluded_route_flags"])
    excluded_zones = set(config.get("hard_excluded_zones", []))
    eligible: dict[int, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []

    for task in tasks:
        reasons: list[str] = []
        qid = int(task["quest_id"])
        if not task.get("remaining_35_55_candidate"):
            reasons.append("not_remaining_35_55_candidate")
        if qid in excluded_ids:
            reasons.append("hard_excluded_task_id")
        route_flags = set(task.get("route_flags", []))
        if route_flags & excluded_flags:
            reasons.append("hard_excluded_route_flag")
        if task.get("primary_zone") in excluded_zones:
            reasons.append("hard_excluded_zone")
        if (
            task.get("candidate_state") == "available_at_35_conditional_trigger"
            and not include_conditional
        ):
            reasons.append("conditional_trigger_disabled")
        if int(task.get("required_level") or 0) >= int(config["target_level"]):
            reasons.append("required_level_at_or_above_target")

        audit = config.get("_audit_by_quest", {}).get(qid)
        tendency = audit.get("route_tendency") if audit else None
        if tendency == "exclude_from_current_outdoor_optimizer":
            reasons.append("c2_exclude_from_current_outdoor_optimizer")
        if tendency == "defer_until_evidence_or_live_test" and not include_conditional:
            reasons.append("c2_deferred_without_conditional_profile")

        if reasons:
            excluded.append({"quest_id": qid, "name": task.get("name"), "reasons": reasons})
        else:
            eligible[qid] = task
    return eligible, excluded


def build_children(tasks: dict[int, dict[str, Any]]) -> dict[int, set[int]]:
    children: dict[int, set[int]] = defaultdict(set)
    for qid, task in tasks.items():
        for parent in task.get("pre_group", []):
            children[int(parent)].add(qid)
        for parent in task.get("pre_single", []):
            children[int(parent)].add(qid)
    return children


def mandatory_ancestor_sets(tasks: dict[int, dict[str, Any]], config: dict[str, Any]) -> dict[str, set[int]]:
    by_zone: dict[str, set[int]] = {}
    for entry in config["mandatory_zone_placeholders"]:
        zone = entry["zone"]
        targets = {qid for qid, task in tasks.items() if task.get("primary_zone") == zone}
        ancestors = set(targets)
        frontier = list(targets)
        while frontier:
            qid = frontier.pop()
            task = tasks.get(qid)
            if not task:
                continue
            for parent in list(task.get("pre_group", [])) + list(task.get("pre_single", [])):
                parent = int(parent)
                if parent in tasks and parent not in ancestors:
                    ancestors.add(parent)
                    frontier.append(parent)
        by_zone[zone] = ancestors
    return by_zone


def replay(
    sequence: Iterable[int],
    tasks: dict[int, dict[str, Any]],
    all_tasks: list[dict[str, Any]],
    config: dict[str, Any],
    profile: dict[str, Any],
) -> ReplayResult:
    xp_to_next = {int(key): int(value) for key, value in config["xp_to_next_level"].items()}
    progress = Progress(int(config["start"]["level"]), int(config["start"]["xp_into_level"]))
    target = int(config["target_level"])
    done = {
        int(task["quest_id"])
        for task in all_tasks
        if task.get("candidate_state") == "completed"
    }
    steps: list[dict[str, Any]] = []
    zone_counts: Counter[str] = Counter()
    time_totals = {"optimistic": 0.0, "central": 0.0, "pessimistic": 0.0, "risk_adjusted": 0.0}
    current_zone = str(config["_transport"]["current_state"]["start_zone"])
    route_selected: set[int] = set()

    for order, qid in enumerate(sequence, 1):
        task = tasks.get(int(qid))
        if task is None:
            return ReplayResult(False, progress, steps, zone_counts, time_totals, f"missing_task:{qid}")
        if int(qid) in done:
            return ReplayResult(False, progress, steps, zone_counts, time_totals, f"duplicate_task:{qid}")
        if progress.level >= target:
            return ReplayResult(False, progress, steps, zone_counts, time_totals, "task_after_target")
        if not prereqs_met(task, done, progress.level, profile):
            return ReplayResult(False, progress, steps, zone_counts, time_totals, f"locked_task:{qid}")

        before = progress
        reward = task_reward(task, before.level)
        progress = advance(before, reward, xp_to_next, target)
        zone = str(task.get("primary_zone") or "未知区域")
        from_zone = current_zone
        zone_counts[zone] += 1
        for scenario in ("optimistic", "central", "pessimistic"):
            time_totals[scenario] += scenario_time(task, scenario)
            time_totals[scenario] += transition_time(from_zone, zone, scenario, config)
        profile_scenario = str(profile["scenario"])
        time_totals["risk_adjusted"] += adjusted_time(
            task, profile_scenario, config, str(profile["risk_mode"])
        )
        time_totals["risk_adjusted"] += transition_time(
            from_zone, zone, profile_scenario, config
        )
        current_zone = zone
        done.add(int(qid))
        steps.append(
            {
                "order": order,
                "quest_id": int(qid),
                "name": task.get("name"),
                "zone": zone,
                "travel_from_zone": from_zone,
                "transition_time_optimistic": round(transition_time(from_zone, zone, "optimistic", config), 2),
                "transition_time_central": round(transition_time(from_zone, zone, "central", config), 2),
                "transition_time_pessimistic": round(transition_time(from_zone, zone, "pessimistic", config), 2),
                "candidate_state_at_start": task.get("candidate_state"),
                "required_level": task.get("required_level"),
                "quest_level": task.get("quest_level"),
                "completion_level": before.level,
                "xp_before_turnin": before.xp,
                "quest_xp": reward,
                "level_after_turnin": progress.level,
                "xp_after_turnin": progress.xp,
                "time_optimistic": round(scenario_time(task, "optimistic"), 2),
                "time_central": round(scenario_time(task, "central"), 2),
                "time_pessimistic": round(scenario_time(task, "pessimistic"), 2),
                "time_profile_adjusted": round(
                    adjusted_time(task, str(profile["scenario"]), config, str(profile["risk_mode"])), 2
                ),
                "task_class": task.get("task_class"),
                "route_flags": task.get("route_flags", []),
                "manual_review_reasons": task.get("manual_review_reasons", []),
            }
        )

    valid = progress.level >= target and mandatory_satisfied(zone_counts, config)
    reason = None if valid else "target_or_mandatory_zone_not_reached"
    return ReplayResult(valid, progress, steps, zone_counts, time_totals, reason)


def unlock_value(qid: int, tasks: dict[int, dict[str, Any]], children: dict[int, set[int]], level: int) -> float:
    value = 0.0
    for child_id in children.get(qid, set()):
        child = tasks.get(child_id)
        if not child:
            continue
        child_level = max(level, int(child.get("required_level") or level))
        value += task_reward(child, min(child_level, 54)) / 6.0
    return value


def selected_overlap_matches(
    qid: int, selected_ids: set[int], config: dict[str, Any]
) -> list[dict[str, Any]]:
    matches = [
        edge
        for edge in config.get("_overlap_by_quest", {}).get(qid, [])
        if int(edge["other"]) in selected_ids
    ]
    return sorted(
        matches,
        key=lambda edge: (edge["edge_type"], int(edge["other"]), edge["strength"]),
    )


def selected_overlap_multiplier(
    qid: int, selected_ids: set[int], config: dict[str, Any]
) -> float:
    matches = selected_overlap_matches(qid, selected_ids, config)
    if not matches:
        return 1.0
    configured = config.get("overlap_score_multipliers", {})
    # Use the strongest single supported relation. Multiplying every pair would
    # over-reward dense blocks and would implicitly claim unverified time savings.
    return min(float(configured.get(edge["edge_type"], 1.0)) for edge in matches)


def pick_task(
    available: list[dict[str, Any]],
    progress: Progress,
    current_zone: str,
    selected_ids: set[int],
    zone_counts: Counter[str],
    tasks: dict[int, dict[str, Any]],
    children: dict[int, set[int]],
    mandatory_ancestors: dict[str, set[int]],
    config: dict[str, Any],
    profile: dict[str, Any],
    rng: random.Random,
    deterministic: bool,
) -> int:
    ranked: list[tuple[float, int]] = []
    missing_zones = {
        entry["zone"]
        for entry in config["mandatory_zone_placeholders"]
        if zone_counts[entry["zone"]] < int(entry["min_selected_tasks"])
    }
    sigma = float(config["search"]["random_log_jitter_sigma"])

    for task in available:
        qid = int(task["quest_id"])
        reward = task_reward(task, progress.level)
        unlock = unlock_value(qid, tasks, children, progress.level)
        denominator = max(1.0, float(reward) + unlock)
        profile_scenario = str(profile["scenario"])
        zone = str(task.get("primary_zone") or "未知区域")
        task_minutes = adjusted_time(
            task, profile_scenario, config, str(profile["risk_mode"])
        )
        task_minutes += transition_time(current_zone, zone, profile_scenario, config)
        score = task_minutes / denominator

        if zone in missing_zones:
            score *= 0.08
        elif any(qid in mandatory_ancestors[missing] for missing in missing_zones):
            score *= 0.42
        if task.get("candidate_state") in {"active", "objective_complete_pending_turnin"}:
            score *= 0.70
        if children.get(qid):
            score /= 1.0 + min(0.35, len(children[qid]) * 0.04)
        score *= selected_overlap_multiplier(qid, selected_ids, config)
        if reward <= 0 and unlock <= 0:
            score *= 100.0
        if not deterministic:
            score *= math.exp(rng.gauss(0.0, sigma))
        ranked.append((score, qid))

    ranked.sort(key=lambda item: (item[0], item[1]))
    pool = ranked[: int(config["search"]["top_pool"])]
    if deterministic or len(pool) == 1:
        return pool[0][1]
    weights = [1.0 / ((index + 1) ** 1.6) for index in range(len(pool))]
    return rng.choices([qid for _, qid in pool], weights=weights, k=1)[0]


def cleanup_sequence(
    sequence: list[int],
    tasks: dict[int, dict[str, Any]],
    all_tasks: list[dict[str, Any]],
    config: dict[str, Any],
    profile: dict[str, Any],
) -> list[int]:
    forced = {int(value) for value in config["forced_initial_task_ids"]}
    current = list(sequence)
    changed = True
    while changed:
        changed = False
        for qid in list(reversed(current)):
            if qid in forced:
                continue
            trial = [value for value in current if value != qid]
            result = replay(trial, tasks, all_tasks, config, profile)
            if result.valid:
                current = trial
                changed = True
                break
    return current


def run_iteration(
    tasks: dict[int, dict[str, Any]],
    all_tasks: list[dict[str, Any]],
    config: dict[str, Any],
    profile: dict[str, Any],
    children: dict[int, set[int]],
    mandatory_ancestors: dict[str, set[int]],
    rng: random.Random,
    deterministic: bool,
) -> list[int] | None:
    xp_to_next = {int(key): int(value) for key, value in config["xp_to_next_level"].items()}
    progress = Progress(int(config["start"]["level"]), int(config["start"]["xp_into_level"]))
    target = int(config["target_level"])
    done = {
        int(task["quest_id"])
        for task in all_tasks
        if task.get("candidate_state") == "completed"
    }
    selected: list[int] = []
    zone_counts: Counter[str] = Counter()
    current_zone = str(config["_transport"]["current_state"]["start_zone"])

    for forced_id in config["forced_initial_task_ids"]:
        qid = int(forced_id)
        task = tasks.get(qid)
        if task is None or not prereqs_met(task, done, progress.level, profile):
            return None
        selected.append(qid)
        done.add(qid)
        current_zone = str(task.get("primary_zone") or "未知区域")
        zone_counts[current_zone] += 1
        progress = advance(progress, task_reward(task, progress.level), xp_to_next, target)

    max_tasks = int(config["search"]["max_selected_tasks"])
    while len(selected) < max_tasks:
        if progress.level >= target:
            return selected if mandatory_satisfied(zone_counts, config) else None
        available = [
            task
            for qid, task in tasks.items()
            if qid not in done and prereqs_met(task, done, progress.level, profile)
        ]
        if not available:
            return None
        qid = pick_task(
            available,
            progress,
            current_zone,
            set(selected),
            zone_counts,
            tasks,
            children,
            mandatory_ancestors,
            config,
            profile,
            rng,
            deterministic,
        )
        task = tasks[qid]
        selected.append(qid)
        done.add(qid)
        current_zone = str(task.get("primary_zone") or "未知区域")
        zone_counts[current_zone] += 1
        progress = advance(progress, task_reward(task, progress.level), xp_to_next, target)
    return None


def solution_record(profile: dict[str, Any], replayed: ReplayResult) -> dict[str, Any]:
    return {
        "profile": profile["name"],
        "scenario": profile["scenario"],
        "risk_mode": profile["risk_mode"],
        "includes_conditional_triggers": bool(profile["include_conditional_triggers"]),
        "task_count": len(replayed.steps),
        "final_level": replayed.final.level,
        "final_xp": replayed.final.xp,
        "quest_xp_total": sum(step["quest_xp"] for step in replayed.steps),
        "time_totals_minutes": {key: round(value, 2) for key, value in replayed.time_totals.items()},
        "mandatory_zone_counts": {
            zone: replayed.zone_counts[zone] for zone in ("菲拉斯", "塔纳利斯")
        },
        "zone_task_counts": dict(replayed.zone_counts.most_common()),
        "selected_task_ids": [step["quest_id"] for step in replayed.steps],
        "steps": replayed.steps,
    }


def pareto_front(solutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for candidate in solutions:
        c = candidate["time_totals_minutes"]
        dominated = False
        for other in solutions:
            if other is candidate:
                continue
            o = other["time_totals_minutes"]
            no_worse = (
                o["central"] <= c["central"]
                and o["pessimistic"] <= c["pessimistic"]
                and other["task_count"] <= candidate["task_count"]
            )
            strictly_better = (
                o["central"] < c["central"]
                or o["pessimistic"] < c["pessimistic"]
                or other["task_count"] < candidate["task_count"]
            )
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            result.append(candidate)
    return sorted(
        result,
        key=lambda item: (
            item["time_totals_minutes"]["central"],
            item["time_totals_minutes"]["pessimistic"],
            item["task_count"],
        ),
    )


def write_audit(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# 35—55动态等级优化器首轮审计",
        "",
        "> 本轮产物是独立任务成本下的可行候选，不是最终最快路线。等待Codex C1任务块后，必须用边际成本重新优化。",
        "",
        "## 经验基准校正",
        "",
        f"- 35级425经验到55级的参考任务/击杀总经验缺口：**{payload['input_summary']['exact_reference_gap_from_start']}**。",
        "- 项目旧文档中的1913775少了100经验；本轮按AzerothCore 3.3.5 `player_xp_for_level`表计算为1913875。",
        "- 该表的23级25500、24级27200、35级55000与本项目实测界面记录一致；36—54仍属于参考服数据，最终可由本服升级界面继续校验。",
        "",
        "## 搜索范围",
        "",
        f"- 原候选任务：{payload['input_summary']['all_task_count']}。",
        f"- 户外基础可选任务（条件触发关闭）：{payload['input_summary']['strict_eligible_count']}。",
        f"- 户外基础可选任务（条件触发开启）：{payload['input_summary']['conditional_eligible_count']}。",
        f"- 硬排除的副本目标任务：{payload['input_summary']['dungeon_excluded_count']}。",
        "- 任务196《猎龙》按用户明确决定硬排除；任务195按目标完成、仅剩交付计时。",
        "",
        "## 候选结果",
        "",
    ]
    for profile_name, records in payload["solutions_by_profile"].items():
        lines.append(f"### {profile_name}")
        lines.append("")
        if not records:
            lines.append("未找到满足当前占位约束的可行候选。")
            lines.append("")
            continue
        best = records[0]
        times = best["time_totals_minutes"]
        lines.extend(
            [
                f"- 保留候选：{len(records)}。",
                f"- 当前首位：{best['task_count']}个任务，任务经验{best['quest_xp_total']}。",
                f"- 独立任务成本加临时区际转场：乐观{times['optimistic']:.2f}分钟，中央{times['central']:.2f}分钟，悲观{times['pessimistic']:.2f}分钟。",
                f"- 菲拉斯/塔纳利斯任务数：{best['mandatory_zone_counts']['菲拉斯']}/{best['mandatory_zone_counts']['塔纳利斯']}。",
                "",
            ]
        )

    lines.extend(
        [
            "## 当前不能用于最终结论的原因",
            "",
            "1. 单任务时间仍含重复跑路和重复接交，临时区际转场又叠加在独立跑路之上；当前总分钟只用于约束地图振荡，不是最终路线时间。",
            "2. 同怪击杀、击杀与掉落同源尚未合并，战斗时间会重复计算。",
            "3. 原截图中菲拉斯和塔纳利斯的精确强制任务ID缺失，目前仅使用每区至少一个任务的占位约束。",
            "4. 尚未加入任务互斥、服务器特殊触发和所有世界物体五号交互规则。",
            "5. 尚未计入必然击杀经验，因此任务经验达到55是保守保证；但不能据此推断最终总时间。",
            "6. 公开掉率和AzerothCore时间仍需Codex C2与实跑覆盖层校正。",
            "",
            "## 下一步",
            "",
            "- 读取Codex C1重叠块，把独立时间替换成任务块边际时间。",
            "- 已接入临时区域位置状态；下一轮用实测交通边和Codex任务块替换通用转场估计。",
            "- 对Pareto候选做互斥、任务机制和前置闭包复核，再运行顺路任务增量搜索。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_json(config_path)
    candidate_path = (ROOT / config["source_candidates"]).resolve()
    transport_path = (ROOT / config["source_transport"]).resolve()
    audit_path = (ROOT / config["source_priority_audit"]).resolve()
    overlap_path = (ROOT / config["source_overlap_graph"]).resolve()
    candidate_data = load_json(candidate_path)
    audit_data = load_json(audit_path)
    overlap_data = load_json(overlap_path)
    config["_transport"] = load_json(transport_path)
    config["_audit_by_quest"] = {
        int(record["quest_id"]): record for record in audit_data["records"]
    }
    overlap_by_quest: dict[int, list[dict[str, Any]]] = defaultdict(list)
    supported_overlap_types = set(config.get("overlap_score_multipliers", {}))
    for edge in overlap_data["edges"]:
        if edge["edge_type"] not in supported_overlap_types:
            continue
        left = int(edge["source_quest_id"])
        right = int(edge["target_quest_id"])
        overlap_by_quest[left].append({"other": right, "edge_type": edge["edge_type"], "strength": edge["strength"]})
        overlap_by_quest[right].append({"other": left, "edge_type": edge["edge_type"], "strength": edge["strength"]})
    config["_overlap_by_quest"] = dict(overlap_by_quest)
    all_tasks = candidate_data["tasks"]
    profiles = config["profiles"]
    rng = random.Random(int(config["search"]["seed"]))

    strict_tasks, strict_excluded = build_eligible(all_tasks, config, False)
    conditional_tasks, conditional_excluded = build_eligible(all_tasks, config, True)
    solutions_by_profile: dict[str, list[dict[str, Any]]] = {}
    all_solutions: list[dict[str, Any]] = []

    for profile in profiles:
        tasks = conditional_tasks if profile["include_conditional_triggers"] else strict_tasks
        children = build_children(tasks)
        mandatory_ancestors = mandatory_ancestor_sets(tasks, config)
        raw_unique: dict[tuple[int, ...], dict[str, Any]] = {}
        iterations = int(profile["iterations"])
        for index in range(iterations):
            sequence = run_iteration(
                tasks,
                all_tasks,
                config,
                profile,
                children,
                mandatory_ancestors,
                rng,
                deterministic=index == 0,
            )
            if not sequence:
                continue
            replayed = replay(sequence, tasks, all_tasks, config, profile)
            if not replayed.valid:
                continue
            record = solution_record(profile, replayed)
            key = tuple(record["selected_task_ids"])
            prior = raw_unique.get(key)
            if prior is None or record["time_totals_minutes"]["risk_adjusted"] < prior["time_totals_minutes"]["risk_adjusted"]:
                raw_unique[key] = record

        # Cleanup is substantially more expensive than route generation. Only
        # clean the strongest raw candidates instead of replaying every random
        # route hundreds of times.
        keep = int(config["search"]["keep_per_profile"])
        raw_records = sorted(
            raw_unique.values(),
            key=lambda item: (
                item["time_totals_minutes"]["risk_adjusted"],
                item["time_totals_minutes"]["central"],
                item["task_count"],
            ),
        )[: max(keep * 3, keep)]
        cleaned_unique: dict[tuple[int, ...], dict[str, Any]] = {}
        for raw in raw_records:
            sequence = cleanup_sequence(
                list(raw["selected_task_ids"]), tasks, all_tasks, config, profile
            )
            replayed = replay(sequence, tasks, all_tasks, config, profile)
            if not replayed.valid:
                continue
            record = solution_record(profile, replayed)
            key = tuple(record["selected_task_ids"])
            prior = cleaned_unique.get(key)
            if prior is None or record["time_totals_minutes"]["risk_adjusted"] < prior["time_totals_minutes"]["risk_adjusted"]:
                cleaned_unique[key] = record

        records = sorted(
            cleaned_unique.values(),
            key=lambda item: (
                item["time_totals_minutes"]["risk_adjusted"],
                item["time_totals_minutes"]["central"],
                item["task_count"],
            ),
        )[:keep]
        solutions_by_profile[str(profile["name"])] = records
        all_solutions.extend(records)

    dungeon_excluded = sum(
        1
        for task in all_tasks
        if task.get("remaining_35_55_candidate")
        and "dungeon_objective_source" in set(task.get("route_flags", []))
    )
    payload = {
        "schema_version": 1,
        "status": "heuristic_feasible_candidates_not_final_route",
        "source_hashes": {
            str(config_path.relative_to(ROOT)): sha256(config_path),
            str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
            str(transport_path.relative_to(ROOT)): sha256(transport_path),
            str(audit_path.relative_to(ROOT)): sha256(audit_path),
            str(overlap_path.relative_to(ROOT)): sha256(overlap_path),
        },
        "input_summary": {
            "all_task_count": len(all_tasks),
            "remaining_candidate_count": int(candidate_data["remaining_candidate_count"]),
            "strict_eligible_count": len(strict_tasks),
            "conditional_eligible_count": len(conditional_tasks),
            "strict_excluded_count": len(strict_excluded),
            "conditional_excluded_count": len(conditional_excluded),
            "dungeon_excluded_count": dungeon_excluded,
            "exact_reference_gap_from_start": int(config["exact_reference_gap_from_start"]),
            "start": config["start"],
            "target_level": config["target_level"],
            "mandatory_zone_placeholders": config["mandatory_zone_placeholders"],
            "hard_excluded_zones": config.get("hard_excluded_zones", []),
            "transport_status": config["_transport"].get("status"),
        },
        "search_parameters": config["search"],
        "limitations": config["limitations"],
        "solutions_by_profile": solutions_by_profile,
        "pareto_candidates": pareto_front(all_solutions),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_audit(args.audit, payload)

    print(json.dumps({
        "output": str(args.output.relative_to(ROOT)),
        "audit": str(args.audit.relative_to(ROOT)),
        "profiles": {name: len(records) for name, records in solutions_by_profile.items()},
        "pareto_count": len(payload["pareto_candidates"]),
        "strict_eligible": len(strict_tasks),
        "conditional_eligible": len(conditional_tasks),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
