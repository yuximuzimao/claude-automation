from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
BOREAN_FOUNDATION = ROOT / "data/route-atlas/borean-tundra-task-foundation.json"
TAGS = ROOT / "data/route-atlas/dragonblight-removal-priority-tags.json"
RETENTION = ROOT / "data/route-atlas/dragonblight-retention-overrides.json"
COVERAGE = ROOT / "data/route-atlas/dragonblight-route-coverage.json"
FLIGHT_AUDIT = ROOT / "data/route-atlas/flight-state-audit.json"
OUT_JSON = ROOT / "data/route-atlas/dragonblight-p2-release-audit.json"
OUT_MD = ROOT / "docs/analysis/2026-08-18-dragonblight-p2-release-audit.md"

# WotLK pre-Cataclysm XP-to-next-level table. The level-71 requirement (1,539,000)
# matches the user's current-server observed 71->72 transition range.
XP_TO_NEXT = {
    68: 648_000,
    69: 717_000,
    70: 1_523_800,
    71: 1_539_000,
    72: 1_555_700,
    73: 1_571_800,
    74: 1_587_900,
    75: 1_604_200,
    76: 1_620_700,
    77: 1_637_400,
    78: 1_653_900,
    79: 1_670_800,
}
CURRENT_UNUSABLE = {11979, 12033}
AUDIT_ROOTS = {11978, 12048}
P2_ROOTS = {12048}
FORMAL_REMOVE = {12048}
FORMAL_RETAIN: set[int] = set()
ENTRY_ACTIVE = {12117}
ENTRY_COMPLETED = {11930}


def advance(level: int, xp: int, gain: int) -> tuple[int, int]:
    xp += gain
    while level in XP_TO_NEXT and xp >= XP_TO_NEXT[level]:
        xp -= XP_TO_NEXT[level]
        level += 1
    return level, xp


def route_turnin_xp(route: dict[str, Any], by_name: dict[str, dict[str, Any]], *, stop_title: str | None = None) -> tuple[int, int | None]:
    seen: set[str] = set()
    total = 0
    stop_index = None
    for index, point in enumerate(route["points"], 1):
        if stop_title and stop_title in str(point[2]):
            stop_index = index
            break
        for name in re.findall(r"交《([^》]+)》", str(point[3])):
            if name in seen:
                continue
            seen.add(name)
            task = by_name.get(name) or {}
            xp = task.get("xp") or {}
            total += int(xp.get("server_xp_at_entry_level") or xp.get("server_xp_at_68") or 0)
    return total, stop_index


def included_current(task: dict[str, Any]) -> bool:
    qid = int(task["quest_id"])
    return bool(
        task.get("is_primary_candidate")
        and str(task.get("scope_status") or "").startswith("include_")
        and not task.get("is_dungeon")
        and not task.get("is_raid_flagged")
        and not task.get("is_repeatable")
        and qid not in CURRENT_UNUSABLE
    )


def has_local_start(task: dict[str, Any]) -> bool:
    for entity in task.get("start_entities") or []:
        if (entity.get("representative_by_zone") or {}).get("65"):
            return True
    return bool(task.get("item_start_ids")) or task.get("scope_status") == "include_structural_zero_xp_prerequisite"


def reachable(by_id: dict[int, dict[str, Any]], candidate_ids: set[int], removed: set[int]) -> set[int]:
    available = candidate_ids - removed
    result = set(ENTRY_ACTIVE) & available
    changed = True
    while changed:
        changed = False
        satisfied = result | ENTRY_COMPLETED | ENTRY_ACTIVE
        for qid in sorted(available - result):
            task = by_id[qid]
            pre_all = [int(x) for x in task.get("pre_all") or []]
            pre_any = [int(x) for x in task.get("pre_any") or []]
            parent = [int(x) for x in task.get("parent_active") or []]
            if any(x not in satisfied for x in pre_all + parent):
                continue
            if pre_any and not any(x in satisfied for x in pre_any):
                continue
            if has_local_start(task):
                result.add(qid)
                changed = True
    return result


def quest_log_peak(route: dict[str, Any]) -> dict[str, Any]:
    active = {"横贯冰原", "前往莫亚基港口"}
    peak = len(active)
    peak_rows = []
    violations = []
    for index, point in enumerate(route["points"], 1):
        action = str(point[3])
        for name in re.findall(r"交《([^》]+)》", action):
            active.discard(name)
        for name in re.findall(r"接《([^》]+)》", action):
            active.add(name)
        if len(active) > peak:
            peak = len(active)
            peak_rows = [{"point": index, "title": point[2], "active_count": peak}]
        elif len(active) == peak:
            peak_rows.append({"point": index, "title": point[2], "active_count": peak})
        if len(active) > 25:
            violations.append({"point": index, "title": point[2], "active_count": len(active)})
    return {"peak": peak, "violations": violations, "peak_rows": peak_rows[-5:]}


def main() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    dragon = routes["dragonblight"]
    borean = routes["borean"]
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    borean_foundation = json.loads(BOREAN_FOUNDATION.read_text(encoding="utf-8"))
    tags = json.loads(TAGS.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    flight = json.loads(FLIGHT_AUDIT.read_text(encoding="utf-8"))

    by_id = {int(t["quest_id"]): t for t in foundation["tasks"]}
    by_name = {str(t["name"]): t for t in foundation["tasks"]}
    borean_by_name = {str(t["name"]): t for t in borean_foundation["tasks"]}
    candidate_ids = {qid for qid, task in by_id.items() if included_current(task)}
    protected_ids = {
        int(qid)
        for package in retention.get("packages") or []
        if str(package.get("status") or "").startswith("retained")
        for qid in package.get("protected_quest_ids") or []
    }

    p2_ids = {
        int(row["quest_id"])
        for row in tags.get("priority_candidates") or []
        if int(row.get("priority") or 0) == 2
    }
    if p2_ids != P2_ROOTS:
        raise RuntimeError(f"Expected current P2 roots {sorted(P2_ROOTS)}, got {sorted(p2_ids)}")

    baseline_reachable = reachable(by_id, candidate_ids, set())
    dependency_effects = []
    for root in sorted(AUDIT_ROOTS):
        after = reachable(by_id, candidate_ids, {root})
        lost = sorted((baseline_reachable - after) - {root})
        dependency_effects.append({
            "quest_id": root,
            "name": by_id[root]["name"],
            "decision": "formal_remove" if root in FORMAL_REMOVE else "protected_non_priority_candidate",
            "newly_unreachable_count": len(lost),
            "newly_unreachable": [{"quest_id": qid, "name": by_id[qid]["name"]} for qid in lost],
        })

    route_text = json.dumps(dragon, ensure_ascii=False)
    forbidden_removed_mentions = [qid for qid in FORMAL_REMOVE if by_id[qid]["name"] in route_text]

    borean_task_xp, _ = route_turnin_xp(borean, borean_by_name)
    borean_boundary = advance(68, 0, borean_task_xp)

    checkpoint_specs = [
        ("level73_fallback_pickup", "阿格玛·月影第一轮回收", 73),
        ("grizzly_outbound", "怨毒镇·高级执行官", 73),
        ("zuldrak_level74_gate", "东部北伐军联络点", 74),
    ]
    checkpoints = []
    for key, title, required_level in checkpoint_specs:
        dragon_xp, point = route_turnin_xp(dragon, by_name, stop_title=title)
        state = advance(borean_boundary[0], borean_boundary[1], dragon_xp)
        checkpoints.append({
            "key": key,
            "before_point_title": title,
            "point_index": point,
            "required_level": required_level,
            "task_reward_xp_from_dragon_entry": dragon_xp,
            "task_reward_only_state": {"level": state[0], "xp": state[1]},
            "passes": state[0] >= required_level,
        })

    log = quest_log_peak(dragon)
    coverage_pass = not coverage.get("missing") and not coverage.get("unexpected") and int(coverage.get("covered_task_count") or 0) == 143
    flight_row = flight.get("dragonblight") or {}
    flight_pass = not flight_row.get("violations") and int(flight_row.get("unknown_destination_count") or 0) == 0
    dependency_pass = next(x for x in dependency_effects if x["quest_id"] == 12048)["newly_unreachable_count"] == 0
    retained_chain_pass = next(x for x in dependency_effects if x["quest_id"] == 11978)["newly_unreachable_count"] > 0
    xp_pass = all(row["passes"] for row in checkpoints)
    log_pass = log["peak"] <= 25 and not log["violations"]
    removed_text_pass = not forbidden_removed_mentions
    only_p2_removed_pass = FORMAL_REMOVE == P2_ROOTS and not FORMAL_RETAIN
    retention_override_pass = not (FORMAL_REMOVE & protected_ids) and 11978 in protected_ids and 11978 not in P2_ROOTS

    gates = {
        "only_p2_scope": only_p2_removed_pass,
        "retention_override": retention_override_pass,
        "dependency_closure": dependency_pass and retained_chain_pass,
        "route_coverage": coverage_pass,
        "next_map_level_gates": xp_pass,
        "quest_log_cap": log_pass,
        "flight_state": flight_pass,
        "removed_task_absent_from_player_route": removed_text_pass,
        "geometry": len(dragon["points"]) == 193 and len(dragon["stepGroups"]) == 51,
    }
    passed = all(gates.values())

    result = {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "scope": "Dragonblight P2-only formal removal and release gate before HTML rebuild",
        "p2_roots": sorted(P2_ROOTS),
        "formal_remove": sorted(FORMAL_REMOVE),
        "formal_retain": sorted(FORMAL_RETAIN),
        "dependency_effects": dependency_effects,
        "reward_impact": {
            "12048_task_xp_lost_per_character": int(by_id[12048]["xp"]["server_xp_at_entry_level"]),
            "12048_has_equipment_reward": True,
            "note": "Equipment value is why the task is P2 rather than P1; project rules do not make equipment an automatic retain condition. Route overlap can reduce marginal time, so timing savings are not used as a release gate.",
        },
        "experience": {
            "borean_current_route_task_reward_total": borean_task_xp,
            "task_reward_only_borean_boundary_from_68_0": {"level": borean_boundary[0], "xp": borean_boundary[1]},
            "current_first_group_snapshot": {"minimum_level": 73, "minimum_xp": 21058, "note": "User-reported 2026-08-18; Borean not yet fully finished."},
            "checkpoints": checkpoints,
        },
        "quest_log": log,
        "coverage": coverage,
        "flight": flight_row,
        "gates": gates,
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    p2_11978 = next(x for x in dependency_effects if x["quest_id"] == 11978)
    p2_12048 = next(x for x in dependency_effects if x["quest_id"] == 12048)
    lines = [
        "# 龙骨荒野 P2-only 正式剔除与发布前审查",
        "",
        f"- 总状态：**{'PASS' if passed else 'FAIL'}**。只有全部gate通过才允许重建统一HTML。",
        "- 当前P2候选只剩12048《天灾的装备》；11978《深入密林》已由用户明确改为结构性非剔除任务，退出P1—P4候选排名。P3/P4正式路线不动。",
        f"- 11978《深入密林》：**结构保护、非P候选**。若删除会新增不可达{p2_11978['newly_unreachable_count']}个任务，影响从《部落的血誓》《阿格玛之锤》一路延伸到库卡隆/红龙之翼/《黑暗的骚动》。",
        f"- 12048《天灾的装备》：**P2A删除**。新增不可达任务={p2_12048['newly_unreachable_count']}，即只损失任务本身；完整经验损失40,600/号。",
        "- 12048有装备奖励，这是它从P1降到P2的原因；装备不是强制保留条件。它与冰雾村三钥匙/军旗存在空间重叠，因此不把通用模型的8.32分钟当作真实边际节省，发布判断只依赖依赖闭包、经验门槛、任务栏、交通与覆盖正确性。",
        "",
        "## 经验门槛",
        "",
        f"- 当前北风正式路线从68级0经验只算任务交付：{borean_task_xp:,} XP → 约{borean_boundary[0]}级 {borean_boundary[1]:,} XP。",
    ]
    for row in checkpoints:
        state = row["task_reward_only_state"]
        lines.append(
            f"- {row['before_point_title']}前：龙骨累计任务奖励{row['task_reward_xp_from_dragon_entry']:,} XP → "
            f"约{state['level']}级 {state['xp']:,} XP；要求≥{row['required_level']}级：{'PASS' if row['passes'] else 'FAIL'}。"
        )
    lines.extend([
        "- 用户当前首组最低号已为73级21,058 XP，且北风尚未结束，因此现场门槛比上述从零任务奖励下界更安全。",
        "",
        "## 发布gate",
        "",
    ])
    for key, value in gates.items():
        lines.append(f"- {'PASS' if value else 'FAIL'} `{key}`")
    lines.extend([
        "",
        f"- 任务栏峰值：{log['peak']}/25。",
        f"- 龙骨飞行状态：{flight_row.get('flight_count', 0)}段，违规={flight_row.get('violation_count', 0)}，未知目的地={flight_row.get('unknown_destination_count', 0)}。",
        f"- 正式覆盖：expected={coverage.get('expected_world_task_count')} / covered={coverage.get('covered_task_count')} / missing={len(coverage.get('missing') or [])} / unexpected={len(coverage.get('unexpected') or [])}。",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": result["status"], "gates": gates, "out_json": str(OUT_JSON.relative_to(ROOT)), "out_md": str(OUT_MD.relative_to(ROOT))}, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
