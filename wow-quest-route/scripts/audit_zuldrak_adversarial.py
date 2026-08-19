from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
FOUNDATION = ROOT / "data/route-atlas/zuldrak-task-foundation.json"
MECHANISMS = ROOT / "data/route-atlas/zuldrak-special-mechanism-audit.json"
COVERAGE = ROOT / "data/route-atlas/zuldrak-route-coverage.json"
VIDEO = ROOT / "data/route-atlas/northrend-video-reverse-audit.json"
FLIGHT = ROOT / "data/route-atlas/flight-state-audit.json"
OUT_JSON = ROOT / "data/route-atlas/zuldrak-adversarial-audit.json"
OUT_MD = ROOT / "docs/analysis/2026-08-19-zuldrak-adversarial-audit.md"

OP_RE = re.compile(r"(?P<verb>右键接|自动接|接(?:并(?:完成|做|交))?|交)《(?P<name>[^》]+)》")

LONG_EDGE_RESOLUTIONS = {
    ("希姆托加·佐尔玛兹回收", "古达克飞行点"): "required_first_visit: 12721 is accepted only after the Zol'Maz tasks are turned in at Zim'Torga; Gundrak flight point is still unopened, so the first northbound leg must be ground travel.",
    ("哈克娅·诸神的指引", "佐尔赫布召唤圈"): "direct_ground_is_shorter: both Zim'Torga and Gundrak are open, but route-model comparison gives about 1.57 min direct versus 2.27 min via Zim'Torga taxi Gundrak; keep direct ride.",
    ("佐尔玛兹要塞·三任务", "希姆托加·佐尔玛兹回收"): "required_hub_unlock: 12707/12708/12709/12712 must be turned in at Zim'Torga to unlock 12721; cannot continue north before this hub return.",
    ("痛苦之匣·吹号最终", "银色前沿·首次到达"): "direct_ground_is_shorter: Voltarus is already closed locally with Stefan's Horn; direct Pain→Argent is about 1.09 min versus about 2.46 min by backtracking to Ebon then taking taxi.",
    ("哈克娅·奎丝鲁恩收尾", "犸托斯祭坛"): "strict_chain: 12675 turns in at Harkoa and directly unlocks 12684 at Mamtoth; no useful intermediate unlock exists on this edge.",
    ("犸托斯祭坛", "哈克娅·死去神灵回收"): "strict_chain_return: 12684 must return to Harkoa to unlock 12685; this is the mandatory reverse leg of the same deity chain.",
    ("西莱图斯先知·第二趟", "银色前沿·巡逻总回收"): "required_turnin: 12516 and 12596 both close at Argent Stand; no flight point exists at Sseratus and no newly unlocked cluster can replace the hub return.",
    ("药剂喷射器", "希姆埃巴雕像·回程"): "whole-loop_order_checked: the current Sprayer→Zim'Abwa→Argent→Basilisk ordering is about 213 yards shorter than Argent→Zim'Abwa→Basilisk using the same anchors.",
    ("希姆鲁克守卫者", "奎丝鲁恩祭坛典狱官"): "same_quest_two_sources: both are required essence sources for 12729; the long edge connects the two mandatory objectives before the single Harkoa turn-in.",
    ("哈克娅之爪·神圣符印", "奎丝鲁恩之魂"): "strict_chain: turning 12666 at Harkoa unlocks 12667, whose next required endpoint is Quetz'lun; no intermediary task is available to break the edge.",
    ("前线周边·女妖精华", "黑锋入口·硅藻土"): "intentional_cluster_bridge: these are the two material sources for 12914; diatomaceous earth is at the Ebon entrance, so this edge intentionally converts the Gymer material quest into the bridge to the Ebon chain.",
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def formal_tasks() -> dict[int, dict[str, Any]]:
    data = load(FOUNDATION)
    ids = {int(x) for x in data.get("formal_task_ids", [])}
    if not ids:
        ids = {int(t["quest_id"]) for t in data["tasks"]}
    return {int(t["quest_id"]): t for t in data["tasks"] if int(t["quest_id"]) in ids}


def task_names(tasks: dict[int, dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    duplicates: set[str] = set()
    for qid, task in tasks.items():
        name = str(task["name"])
        if name in out and out[name] != qid:
            duplicates.add(name)
        else:
            out[name] = qid
    for name in duplicates:
        out.pop(name, None)
    return out


def simulate_lifecycle(route: dict[str, Any], tasks: dict[int, dict[str, Any]]) -> dict[str, Any]:
    by_name = task_names(tasks)
    accepted: set[int] = set()
    completed: set[int] = set()
    active: set[int] = set()
    prerequisite_violations: list[dict[str, Any]] = []
    duplicate_accepts: list[dict[str, Any]] = []
    turnin_without_accept: list[dict[str, Any]] = []
    max_active = 0
    max_active_point = -1
    active_trace: list[dict[str, Any]] = []

    for index, point in enumerate(route.get("points", [])):
        action = str(point[3])
        for match in OP_RE.finditer(action):
            name = match.group("name")
            qid = by_name.get(name)
            if qid is None:
                continue
            verb = match.group("verb")
            task = tasks[qid]
            if "接" in verb:
                if qid in accepted or qid in completed:
                    duplicate_accepts.append({"point": index, "quest_id": qid, "name": name, "action": action})
                # Only enforce prerequisites that are themselves inside the formal Zul'Drak pool.
                pre_any = [int(x) for x in task.get("pre_any", []) if int(x) in tasks]
                pre_all = [int(x) for x in task.get("pre_all", []) if int(x) in tasks]
                parent_active = [int(x) for x in task.get("parent_active", []) if int(x) in tasks]
                if pre_any and not any(x in completed for x in pre_any):
                    prerequisite_violations.append({"point": index, "quest_id": qid, "name": name, "kind": "pre_any", "required": pre_any})
                missing_all = [x for x in pre_all if x not in completed]
                if missing_all:
                    prerequisite_violations.append({"point": index, "quest_id": qid, "name": name, "kind": "pre_all", "required": missing_all})
                missing_parent = [x for x in parent_active if x not in active]
                if missing_parent:
                    prerequisite_violations.append({"point": index, "quest_id": qid, "name": name, "kind": "parent_active", "required": missing_parent})
                accepted.add(qid)
                active.add(qid)
            else:
                if qid not in active and qid not in accepted:
                    # Inbound/carry tasks may legitimately be first seen at turn-in; keep them visible for review.
                    turnin_without_accept.append({"point": index, "quest_id": qid, "name": name, "action": action})
                active.discard(qid)
                completed.add(qid)
            if len(active) > max_active:
                max_active = len(active)
                max_active_point = index
        active_trace.append({"point": index, "active_count": len(active), "title": point[2]})

    return {
        "max_active": max_active,
        "max_active_point": max_active_point,
        "max_active_title": route["points"][max_active_point][2] if max_active_point >= 0 else None,
        "prerequisite_violations": prerequisite_violations,
        "duplicate_accepts": duplicate_accepts,
        "turnin_without_accept": turnin_without_accept,
        "active_at_end": sorted(active),
        "completed_count": len(completed),
        "active_trace": active_trace,
    }


def long_ride_edges(route: dict[str, Any], threshold: float = 18.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pts = route.get("points", [])
    for idx in range(1, len(pts)):
        b = pts[idx]
        kind = str(b[6] if len(b) > 6 and b[6] else "ride")
        if kind != "ride":
            continue
        a = pts[idx - 1]
        dist = math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))
        if dist >= threshold:
            rows.append({
                "from_point": idx - 1,
                "to_point": idx,
                "from": a[2],
                "to": b[2],
                "map_percent_distance": round(dist, 1),
            })
    rows.sort(key=lambda x: x["map_percent_distance"], reverse=True)
    return rows


def fivebox_coverage(route: dict[str, Any], tasks: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    mech = {int(row["quest_id"]): row for row in load(MECHANISMS).get("rows", [])}
    missing: list[dict[str, Any]] = []
    for qid, row in mech.items():
        checks = row.get("fivebox_checks") or []
        if not checks or qid not in tasks:
            continue
        name = str(tasks[qid]["name"])
        matching = [p for p in route.get("points", []) if f"《{name}》" in str(p[3])]
        if not matching or not any(len(p) > 8 and str(p[8]).strip() for p in matching):
            missing.append({"quest_id": qid, "name": name, "checks": checks})
    return missing


def index_of(route: dict[str, Any], token: str, field: int = 3) -> int | None:
    for idx, point in enumerate(route.get("points", [])):
        if token in str(point[field]):
            return idx
    return None


def main() -> None:
    routes = load(ROUTES)
    route = routes["zuldrak"]
    tasks = formal_tasks()
    coverage = load(COVERAGE)
    video = load(VIDEO)["maps"]["zuldrak"]
    flight = load(FLIGHT)["routes"]["zuldrak"]
    lifecycle = simulate_lifecycle(route, tasks)
    long_edges = long_ride_edges(route)
    for row in long_edges:
        row["manual_resolution"] = LONG_EDGE_RESOLUTIONS.get((str(row["from"]), str(row["to"])))
    unresolved_long_edges = [row for row in long_edges if not row.get("manual_resolution")]
    fivebox_missing = fivebox_coverage(route, tasks)

    breadcrumb_accept = index_of(route, "接《勇士的召唤！》")
    breadcrumb_turnin = index_of(route, "交《勇士的召唤！》")
    arena_accept = index_of(route, "接《痛苦斗兽场：伊戈达斯！》")
    dalaran_detour = index_of(route, "银色前沿·达拉然短往返", field=2)

    voltarus_indices = [i for i, p in enumerate(route.get("points", [])) if str(p[4]) == "voltarus"]
    if voltarus_indices:
        vmin, vmax = min(voltarus_indices), max(voltarus_indices)
        illegal_between = [
            {"point": i, "title": route["points"][i][2], "phase": route["points"][i][4]}
            for i in range(vmin, vmax + 1)
            if str(route["points"][i][4]) not in {"voltarus", "ebon", "forward", "gymer"}
        ]
    else:
        illegal_between = [{"error": "no_voltarus_points"}]

    hard_failures: list[str] = []
    if coverage.get("missing") or coverage.get("unexpected"):
        hard_failures.append("coverage_missing_or_unexpected")
    if int(coverage.get("covered_task_count", 0)) != int(coverage.get("formal_task_count", -1)):
        hard_failures.append("formal_pool_not_fully_covered")
    if coverage.get("intentional_defer"):
        hard_failures.append("formal_task_still_deferred")
    if lifecycle["prerequisite_violations"]:
        hard_failures.append("dependency_order_violation")
    if lifecycle["max_active"] > 25:
        hard_failures.append("quest_log_cap_exceeded")
    if fivebox_missing:
        hard_failures.append("fivebox_check_not_player_visible")
    if flight.get("violation_count") or flight.get("unknown_destination_count"):
        hard_failures.append("flight_state_violation")
    video_unresolved = [row for row in video.get("reversed_video_adjacencies", []) if row.get("manual_review_status") != "resolved"]
    video_pass = int(video.get("critical_video_omission_count", 0)) == 0 and not video_unresolved
    if not video_pass:
        hard_failures.append("video_reverse_review_not_passed")
    if None in {breadcrumb_accept, breadcrumb_turnin, arena_accept, dalaran_detour}:
        hard_failures.append("arena_breadcrumb_sequence_missing")
    elif not (breadcrumb_accept < breadcrumb_turnin <= arena_accept):
        hard_failures.append("arena_breadcrumb_wrong_order")
    if illegal_between:
        hard_failures.append("voltarus_phase_interleaving")
    if unresolved_long_edges:
        hard_failures.append("unresolved_long_ground_edge")

    result = {
        "status": "pass" if not hard_failures else "fail",
        "hard_failures": hard_failures,
        "formal_task_count": coverage.get("formal_task_count"),
        "covered_task_count": coverage.get("covered_task_count"),
        "coverage_missing": coverage.get("missing"),
        "coverage_unexpected": coverage.get("unexpected"),
        "intentional_defer": coverage.get("intentional_defer"),
        "lifecycle": {k: v for k, v in lifecycle.items() if k != "active_trace"},
        "quest_log_safety_margin": 25 - int(lifecycle["max_active"]),
        "flight": {
            "count": flight.get("flight_count"),
            "violations": flight.get("violation_count"),
            "unknown_destinations": flight.get("unknown_destination_count"),
        },
        "video": {
            "status": "pass_whole_map_video_reverse_review" if video_pass else "manual_review_required",
            "common_completion": video.get("common_explicit_completion_count"),
            "critical_omissions": video.get("critical_video_omission_count"),
            "adjacent_reversals": len(video.get("reversed_video_adjacencies", [])),
            "unresolved_reversals": len(video_unresolved),
        },
        "arena_breadcrumb": {
            "dalaran_detour_point": dalaran_detour,
            "accept_point": breadcrumb_accept,
            "turnin_point": breadcrumb_turnin,
            "arena_first_accept_point": arena_accept,
        },
        "fivebox_missing_checks": fivebox_missing,
        "voltarus_illegal_interleaving": illegal_between,
        "long_ride_edges_ge_18pct": long_edges,
        "unresolved_long_ride_edges": unresolved_long_edges,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 祖达克对抗性审查",
        "",
        f"- 结论：**{result['status'].upper()}**。",
        f"- 正式任务：{coverage.get('covered_task_count')}/{coverage.get('formal_task_count')}，missing={coverage.get('missing')}，unexpected={coverage.get('unexpected')}，defer={coverage.get('intentional_defer')}。",
        f"- 任务日志显式生命周期峰值：{lifecycle['max_active']}/25（余量{25-lifecycle['max_active']}）；峰值点：{lifecycle['max_active_title']}。",
        f"- 依赖顺序违规：{len(lifecycle['prerequisite_violations'])}；五开检查未显式落玩家页：{len(fivebox_missing)}。",
        f"- 系统飞行：{flight.get('flight_count')}段，违规{flight.get('violation_count')}，未知目的地{flight.get('unknown_destination_count')}。",
        f"- 视频反审：{'PASS' if video_pass else 'FAIL'}；共同明确完成={video.get('common_explicit_completion_count')}；视频证明漏项={video.get('critical_video_omission_count')}；未解释逆序={len(video_unresolved)}。",
        f"- 12974顺序：达拉然往返点{dalaran_detour} → 接取点{breadcrumb_accept} → 斗兽场交付点{breadcrumb_turnin} / 第一场接取点{arena_accept}。",
        "",
        "## 长骑行边（≥18%地图尺度，人工挑战清单）",
        "",
    ]
    if long_edges:
        for row in long_edges:
            lines.append(f"- {row['from_point']}→{row['to_point']} {row['from']} → {row['to']}：{row['map_percent_distance']}%；{row.get('manual_resolution') or 'UNRESOLVED'}")
    else:
        lines.append("- 无。")
    lines += ["", "## 硬失败", ""]
    if hard_failures:
        lines.extend(f"- {x}" for x in hard_failures)
    else:
        lines.append("- 无。")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "hard_failures": hard_failures,
        "formal": f"{coverage.get('covered_task_count')}/{coverage.get('formal_task_count')}",
        "quest_log_peak": lifecycle["max_active"],
        "dependency_violations": len(lifecycle["prerequisite_violations"]),
        "fivebox_missing": len(fivebox_missing),
        "flight_violations": flight.get("violation_count"),
        "video_status": "pass_whole_map_video_reverse_review" if video_pass else "manual_review_required",
        "long_ride_edges": len(long_edges),
        "unresolved_long_ride_edges": len(unresolved_long_edges),
    }, ensure_ascii=False, indent=2))
    if hard_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
