from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_atlas_cpsat import RouteAtlasCpSatSolver, build_instance_from_materialized_data
from lib.route_atlas_region_planner import build_region_first_feasible_order

ATLAS = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
AUDIT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-solver-input-audit.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-first-run-v1.json"
REPORT = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-first-run-v1.md"
START_XY = (78.40, 62.02)


def fingerprint(paths: list[Path], quest_ids: list[int]) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(str(path.relative_to(ROOT)).encode())
        h.update(path.read_bytes())
    h.update(json.dumps(quest_ids).encode())
    h.update(json.dumps(START_XY).encode())
    return h.hexdigest()


def action_order(route: list[dict]) -> list[str]:
    return [str(row["action_id"]) for row in route if row.get("action_id")]


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    value = int(round(seconds))
    return f"{value // 60}分{value % 60:02d}秒"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    solver_ready_ids = sorted(int(qid) for qid, row in audit["quests"].items() if not row.get("hard_blocker"))
    opportunistic_ids = sorted(
        qid
        for qid in solver_ready_ids
        if str(profiles["quests"][str(qid)].get("classification", {}).get("effective_primary") or "").startswith("item_start_")
    )
    quest_ids = [qid for qid in solver_ready_ids if qid not in set(opportunistic_ids)]
    fp = fingerprint(
        [ATLAS, PROFILES, AUDIT, ROOT / "lib" / "route_atlas_cpsat.py", ROOT / "lib" / "route_atlas_region_planner.py"],
        quest_ids,
    )

    instance = build_instance_from_materialized_data(
        atlas,
        profiles,
        audit,
        quest_ids,
        start_xy=START_XY,
        instance_name="zangarmarsh-first-run-v1",
        assume_external_prerequisites_satisfied=True,
    )
    baseline = build_region_first_feasible_order(instance)
    if baseline.status != "FEASIBLE_REGION_HEURISTIC":
        raise RuntimeError(f"baseline failed: {baseline.status}")

    incumbent = {
        "source": "HEURISTIC_BASELINE",
        "objective_seconds": baseline.total_seconds,
        "travel_seconds": baseline.travel_seconds,
        "service_seconds": baseline.service_seconds,
        "action_order": baseline.action_order,
        "route": baseline.steps,
    }
    if OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if previous.get("meta", {}).get("fingerprint") == fp:
            old = previous.get("incumbent") or {}
            if isinstance(old.get("objective_seconds"), (int, float)) and old["objective_seconds"] < incumbent["objective_seconds"]:
                incumbent = old

    result = RouteAtlasCpSatSolver(instance).solve(
        max_time_seconds=args.seconds,
        num_workers=args.workers,
        initial_action_order=list(incumbent["action_order"]),
        objective_upper_bound_seconds=float(incumbent["objective_seconds"]) + 0.01,
    )
    if result.objective_seconds is not None and result.objective_seconds < float(incumbent["objective_seconds"]) - 1e-6:
        incumbent = {
            "source": result.status,
            "objective_seconds": result.objective_seconds,
            "travel_seconds": result.travel_seconds,
            "service_seconds": result.service_seconds,
            "action_order": action_order(result.route),
            "route": result.route,
        }

    payload = {
        "meta": {
            "version": "first-run-v1",
            "fingerprint": fp,
            "quest_ids": quest_ids,
            "quest_count": len(quest_ids),
            "opportunistic_item_start_quest_ids": opportunistic_ids,
            "start_xy": list(START_XY),
            "purpose": "First-run validation route: prioritize a good complete zone order, not an optimality proof.",
            "availability_policy": "Local reputation/external-prerequisite quests stay in the plan; if Questie does not show one at runtime, skip it.",
        },
        "instance": {
            "actions": len(instance.actions),
            "requirements": len(instance.requirement_actions),
        },
        "baseline": {
            "objective_seconds": baseline.total_seconds,
            "travel_seconds": baseline.travel_seconds,
            "service_seconds": baseline.service_seconds,
        },
        "last_run": {
            "seconds_limit": args.seconds,
            "status": result.status,
            "objective_seconds": result.objective_seconds,
            "travel_seconds": result.travel_seconds,
            "service_seconds": result.service_seconds,
            "best_bound_seconds": result.best_bound_seconds,
            "relative_gap": result.relative_gap,
        },
        "incumbent": incumbent,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 赞加沼泽第一版实跑路线",
        "",
        f"- 任务数：{len(quest_ids)}",
        f"- 基线：{fmt(baseline.total_seconds)}（移动 {fmt(baseline.travel_seconds)} / 任务执行 {fmt(baseline.service_seconds)}）",
        f"- 当前最好：{fmt(incumbent['objective_seconds'])}（移动 {fmt(incumbent.get('travel_seconds'))} / 任务执行 {fmt(incumbent.get('service_seconds'))}）",
        "- 这是一条用于实跑验证的当前最好完整路线，不宣称数学全局最优。",
        "- 本地声望/地图外前置任务保留为运行时可用项：Questie显示就做，不显示就跳过。",
        "",
        "## 动作序列",
        "",
    ]
    for i, row in enumerate(incumbent["route"], 1):
        if not row.get("action_id"):
            continue
        name = row.get("name") or row.get("action_id")
        qids = ",".join(str(v) for v in row.get("quest_ids") or [])
        lines.append(f"{i}. {row.get('type')} | {name} | Q:{qids} | move {row.get('travel_seconds', 0):.1f}s | work {row.get('service_seconds', 0):.1f}s")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "quest_count": len(quest_ids),
        "baseline_seconds": baseline.total_seconds,
        "incumbent_seconds": incumbent["objective_seconds"],
        "travel_seconds": incumbent.get("travel_seconds"),
        "service_seconds": incumbent.get("service_seconds"),
        "last_run_status": result.status,
        "output": str(OUTPUT),
        "report": str(REPORT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
