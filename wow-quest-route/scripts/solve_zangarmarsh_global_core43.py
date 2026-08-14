from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_atlas_cpsat import RouteAtlasCpSatSolver, build_instance_from_materialized_data
from lib.route_atlas_initial_solution import build_greedy_feasible_order

ATLAS = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
AUDIT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-solver-input-audit.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-core43-checkpoint.json"
HISTORY = ROOT / "data" / "route-atlas" / "zangarmarsh-global-core43-history.json"
REPORT = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-global-core43-checkpoint.md"

CORE43 = [
    9697, 9701, 9702, 9708, 9709, 9716, 9718, 9720, 9728, 9730, 9731,
    9747, 9769, 9770, 9771, 9772, 9773, 9774, 9775, 9778, 9788, 9814,
    9816, 9817, 9820, 9822, 9823, 9828, 9841, 9842, 9845, 9846, 9847,
    9894, 9895, 9898, 9899, 9903, 9904, 9911, 10096, 10117, 10118,
]
START_XY = (78.40, 62.02)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint() -> str:
    h = hashlib.sha256()
    model_files = (
        ATLAS,
        PROFILES,
        AUDIT,
        ROOT / "lib" / "route_atlas_cpsat.py",
        ROOT / "lib" / "route_atlas_initial_solution.py",
    )
    for path in model_files:
        h.update(str(path.relative_to(ROOT)).encode())
        h.update(path.read_bytes())
    h.update(json.dumps(CORE43).encode())
    h.update(json.dumps(START_XY).encode())
    return h.hexdigest()


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    value = int(round(seconds))
    return f"{value // 60}分{value % 60:02d}秒"


def action_order_from_route(route: list[dict[str, Any]]) -> list[str]:
    return [str(row["action_id"]) for row in route if row.get("action_id")]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    fp = fingerprint()

    instance = build_instance_from_materialized_data(
        atlas,
        profiles,
        audit,
        CORE43,
        start_xy=START_XY,
        instance_name="zangarmarsh-reputation-independent-local-core43",
    )
    heuristic = build_greedy_feasible_order(instance)
    if heuristic.status != "FEASIBLE_HEURISTIC":
        raise RuntimeError(f"Warm start failed: {heuristic.status}")

    previous: dict[str, Any] | None = None
    if OUTPUT.exists():
        candidate = json.loads(OUTPUT.read_text(encoding="utf-8"))
        candidate_fp = candidate.get("meta", {}).get("input_fingerprint")
        if candidate_fp == fp:
            previous = candidate
        else:
            # Never destroy a checkpoint just because the model/data fingerprint changed.
            # Archive the full prior incumbent/bound under its original fingerprint first.
            history = {"versions": []}
            if HISTORY.exists():
                loaded = json.loads(HISTORY.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and isinstance(loaded.get("versions"), list):
                    history = loaded
            known = {
                row.get("meta", {}).get("input_fingerprint")
                for row in history["versions"]
                if isinstance(row, dict)
            }
            if candidate_fp not in known:
                history["versions"].append(candidate)
                HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    hint_order = heuristic.action_order
    upper = heuristic.total_seconds
    incumbent: dict[str, Any] = {
        "source": "HEURISTIC_ONLY",
        "objective_seconds": heuristic.total_seconds,
        "travel_seconds": heuristic.travel_seconds,
        "service_seconds": heuristic.service_seconds,
        "action_order": heuristic.action_order,
        "route": heuristic.steps,
    }
    accumulated_bound: float | None = None

    if previous:
        old = previous.get("incumbent") or {}
        old_obj = old.get("objective_seconds")
        if isinstance(old_obj, (int, float)) and old_obj < incumbent["objective_seconds"]:
            incumbent = old
            hint_order = list(old.get("action_order") or hint_order)
            upper = float(old_obj)
        old_bound = previous.get("proof", {}).get("best_bound_seconds")
        if isinstance(old_bound, (int, float)):
            accumulated_bound = float(old_bound)

    result = RouteAtlasCpSatSolver(instance).solve(
        max_time_seconds=args.seconds,
        num_workers=args.workers,
        initial_action_order=hint_order,
        objective_upper_bound_seconds=upper + 0.01,
    )

    if result.objective_seconds is not None and result.objective_seconds < float(incumbent["objective_seconds"]) - 1e-6:
        incumbent = {
            "source": result.status,
            "objective_seconds": result.objective_seconds,
            "travel_seconds": result.travel_seconds,
            "service_seconds": result.service_seconds,
            "action_order": action_order_from_route(result.route),
            "route": result.route,
        }

    if result.best_bound_seconds is not None:
        accumulated_bound = max(accumulated_bound or float("-inf"), result.best_bound_seconds)

    objective = float(incumbent["objective_seconds"])
    gap = None
    if accumulated_bound is not None and objective > 0:
        gap = max(0.0, (objective - accumulated_bound) / objective)
    proof_status = "PROVEN_OPTIMAL" if gap is not None and gap <= 1e-6 else "BEST_FOUND_WITH_GAP"

    payload = {
        "meta": {
            "model": "Route Atlas fourth-layer local reputation-independent core",
            "input_fingerprint": fp,
            "atlas_sha256": file_sha(ATLAS),
            "profiles_sha256": file_sha(PROFILES),
            "audit_sha256": file_sha(AUDIT),
            "quest_ids": CORE43,
            "quest_count": len(CORE43),
            "start_xy": list(START_XY),
            "scope": (
                "Zangarmarsh-local quests without reputation-gated availability. Cross-zone, dungeon, "
                "profession/class/seasonal, and conditional-inventory quests are outside this checkpoint."
            ),
            "important": "This checkpoint preserves incumbent/bound across interrupted runs; solver search-tree state itself is not serialized.",
        },
        "instance": {
            "actions": len(instance.actions),
            "requirements": len(instance.requirement_actions),
            "item_start_accepts": len(instance.accept_trigger_actions),
        },
        "heuristic_warm_start": {
            "status": heuristic.status,
            "objective_seconds": heuristic.total_seconds,
            "travel_seconds": heuristic.travel_seconds,
            "service_seconds": heuristic.service_seconds,
        },
        "last_run": {
            "seconds_limit": args.seconds,
            "workers": args.workers,
            "status": result.status,
            "cp_status": result.cp_status,
            "objective_seconds": result.objective_seconds,
            "best_bound_seconds": result.best_bound_seconds,
            "relative_gap": result.relative_gap,
            "wall_time_seconds": result.wall_time_seconds,
            "branches": result.branches,
            "conflicts": result.conflicts,
        },
        "incumbent": incumbent,
        "proof": {
            "status": proof_status,
            "best_bound_seconds": accumulated_bound,
            "relative_gap": gap,
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 赞加沼泽第四层：43任务本地无声望核心 checkpoint",
        "",
        f"- 当前状态：`{proof_status}`",
        f"- 当前最好完整路线：**{fmt(objective)}**（{objective:.3f}秒）",
        f"- 当前理论下界：**{fmt(accumulated_bound)}**" if accumulated_bound is not None else "- 当前理论下界：—",
        f"- 当前 gap：**{gap * 100:.2f}%**" if gap is not None else "- 当前 gap：—",
        f"- 任务：{len(CORE43)}；动作候选：{len(instance.actions)}；逻辑Objective：{len(instance.requirement_actions)}。",
        f"- 本次搜索：{args.seconds:g}秒；`{result.status}`；本次找到 {fmt(result.objective_seconds)}；本次下界 {fmt(result.best_bound_seconds)}。",
        "",
        "## 范围",
        "",
        "这是第四层的第一块：只含赞加本地且不依赖动态声望门槛的任务。Item-start 已建成 `获取起始物 G(Q) → A(Q)`，可以和其他任务共享同一怪物服务流。",
        "",
        "尚未包含声望状态任务、跨区/副本边界任务、专业/职业/节日任务，以及只有实际拿到随机物品时才成立的条件库存任务。",
        "",
        "## 中断恢复",
        "",
        "脚本每次运行先读取同 fingerprint 的旧 checkpoint，把此前最好路线作为新的上界/搜索 hint；同时保留历次搜索中最高的有效 lower bound。中断不会丢已落盘 incumbent/bound，但 CP-SAT 内部搜索树不能跨进程恢复。",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "proof_status": proof_status,
        "incumbent_seconds": objective,
        "best_bound_seconds": accumulated_bound,
        "gap": gap,
        "last_run_status": result.status,
        "output": str(OUTPUT),
        "report": str(REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
