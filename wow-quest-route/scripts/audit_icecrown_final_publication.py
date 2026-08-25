from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
COVERAGE = ROOT / "data/route-atlas/icecrown-route-coverage-audit.json"
DEPENDENCY = ROOT / "data/route-atlas/icecrown-route-dependency-order-audit.json"
STRUCTURED = ROOT / "data/route-atlas/icecrown-structured-candidate-audit.json"
OBJECTIVE_ANCHORS = ROOT / "data/route-atlas/objective-anchor-audit.json"
FLIGHT_STATE = ROOT / "data/route-atlas/flight-state-audit.json"
WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
OUT = ROOT / "data/route-atlas/icecrown-final-publication-audit.json"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}


def main() -> None:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    dependency = json.loads(DEPENDENCY.read_text(encoding="utf-8"))
    structured = json.loads(STRUCTURED.read_text(encoding="utf-8"))
    objective_anchors = json.loads(OBJECTIVE_ANCHORS.read_text(encoding="utf-8"))
    flight_state = json.loads(FLIGHT_STATE.read_text(encoding="utf-8"))
    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    route = routes.get("icecrown") or {}

    hard: list[dict] = []
    checks: dict[str, object] = {}

    formal = [
        task for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    ]
    steps = draft.get("steps") or []
    groups = route.get("stepGroups") or []
    points = route.get("points") or []

    checks["formal_task_count"] = len(formal)
    checks["step_count"] = len(steps)
    checks["point_count"] = len(points)
    if len(formal) != 163:
        hard.append({"type": "formal_task_count", "actual": len(formal), "expected": 163})
    if len(steps) != 40 or len(groups) != 40:
        hard.append({"type": "step_count", "draft": len(steps), "published": len(groups), "expected": 40})
    if not str(draft.get("status") or "").startswith("icecrown_full_zone_route"):
        hard.append({"type": "stale_draft_status", "status": draft.get("status")})

    coverage_ok = (
        int(coverage.get("candidate_count", -1)) == 163
        and int(coverage.get("covered_count", -1)) == 163
        and int(coverage.get("uncovered_count", -1)) == 0
        and not coverage.get("uncovered")
    )
    checks["coverage_ok"] = coverage_ok
    if not coverage_ok:
        hard.append({"type": "coverage", "payload": coverage})

    dependency_ok = (
        int(dependency.get("candidate_count", -1)) == 163
        and int(dependency.get("mentioned_candidate_count", -1)) == 163
        and int(dependency.get("missing_mention_count", -1)) == 0
        and int(dependency.get("dependency_order_violation_count", -1)) == 0
    )
    checks["dependency_ok"] = dependency_ok
    if not dependency_ok:
        hard.append({"type": "dependency", "payload": dependency})

    structured_ok = structured.get("status") == "PASS" and int(structured.get("hardIssueCount") or 0) == 0
    checks["structured_geometry_ok"] = structured_ok
    if not structured_ok:
        hard.append({"type": "structured_geometry", "payload": structured})

    ice_anchor = (objective_anchors.get("routes") or {}).get("icecrown") or {}
    anchor_ok = int(ice_anchor.get("failure_count") or 0) == 0 and int(ice_anchor.get("review_count") or 0) == 0
    checks["objective_anchor_ok"] = anchor_ok
    if not anchor_ok:
        hard.append({"type": "objective_anchor", "payload": ice_anchor})

    ice_flight = (flight_state.get("routes") or {}).get("icecrown") or {}
    flight_ok = int(ice_flight.get("violation_count") or 0) == 0 and int(ice_flight.get("unknown_destination_count") or 0) == 0
    checks["flight_state_ok"] = flight_ok
    if not flight_ok:
        hard.append({"type": "flight_state", "payload": ice_flight})

    publication_ok = (
        route.get("uiStandard") == "semantic-hud-v45"
        and route.get("status") == "formal_pre_live_fivebox_calibration"
        and int(route.get("order") or -1) == 7
    )
    checks["publication_contract_ok"] = publication_ok
    if not publication_ok:
        hard.append({
            "type": "publication_contract",
            "uiStandard": route.get("uiStandard"),
            "status": route.get("status"),
            "order": route.get("order"),
        })

    group_center = sum(float((group.get("timing") or {}).get("centerMinutes") or 0) for group in groups)
    route_timing = route.get("timing") or {}
    timing_ok = (
        abs(group_center - float(route_timing.get("centerMinutes") or -1)) < 1e-6
        and abs(group_center - 725.0) < 1e-6
        and [float(x) for x in route_timing.get("rangeMinutes") or []] == [540.0, 960.0]
    )
    checks["timing_ok"] = timing_ok
    checks["timing_center_minutes"] = group_center
    if not timing_ok:
        hard.append({"type": "timing", "group_center": group_center, "route_timing": route_timing})

    # Audit the actual semantic HUD, not raw prose. Multi-task actions inherit the same
    # accept/turn-in class, so this is the closest representation of what the player sees.
    quest_log_pattern = re.compile(r'<span class="ra-task (ra-accept|ra-turnin)">([^<]+)</span>')
    active: dict[str, int] = {}
    peak_active = 0
    peak_step = 0
    peak_tasks: list[str] = []
    for step_no, group in enumerate(groups, start=1):
        for kind, raw_name in quest_log_pattern.findall(str(group.get("actionHtml") or "")):
            name = html.unescape(raw_name)
            if kind == "ra-accept":
                active[name] = active.get(name, 0) + 1
            elif active.get(name, 0) > 0:
                active[name] -= 1
                if active[name] <= 0:
                    active.pop(name, None)
            active_count = sum(active.values())
            if active_count > peak_active:
                peak_active = active_count
                peak_step = step_no
                peak_tasks = sorted(active)
    final_active = sorted(name for name, count in active.items() for _ in range(count))
    quest_log_ok = peak_active <= 25 and not final_active
    checks["quest_log_ok"] = quest_log_ok
    checks["quest_log_peak_active"] = peak_active
    checks["quest_log_peak_step"] = peak_step
    checks["quest_log_peak_tasks"] = peak_tasks
    checks["quest_log_final_active"] = final_active
    if not quest_log_ok:
        hard.append({
            "type": "quest_log_state",
            "peak_active": peak_active,
            "peak_step": peak_step,
            "peak_tasks": peak_tasks,
            "final_active": final_active,
        })

    missing_route_notes: list[dict] = []
    missing_fivebox_notes: list[dict] = []
    route_note_cards = 0
    fivebox_cards = 0
    for step in steps:
        step_no = int(step["step"])
        if not (1 <= step_no <= len(groups)):
            hard.append({"type": "invalid_step_number", "step": step_no})
            continue
        note_html = str(groups[step_no - 1].get("noteHtml") or "")
        for qid, card in (step.get("task_cards") or {}).items():
            name = str(card.get("name") or "")
            route_note = str(card.get("route_note") or "").strip()
            fivebox = str(card.get("fivebox") or "").strip()
            if route_note:
                route_note_cards += 1
                if name not in note_html or html.escape(route_note) not in note_html:
                    missing_route_notes.append({"quest_id": int(qid), "name": name, "step": step_no})
            if fivebox:
                fivebox_cards += 1
                if name not in note_html or html.escape(fivebox) not in note_html or "五开" not in note_html:
                    missing_fivebox_notes.append({"quest_id": int(qid), "name": name, "step": step_no})
    checks["route_note_cards"] = route_note_cards
    checks["fivebox_cards"] = fivebox_cards
    checks["missing_route_notes"] = len(missing_route_notes)
    checks["missing_fivebox_notes"] = len(missing_fivebox_notes)
    if missing_route_notes:
        hard.append({"type": "route_note_not_published", "rows": missing_route_notes})
    if missing_fivebox_notes:
        hard.append({"type": "fivebox_note_not_published", "rows": missing_fivebox_notes})

    action_text = "\n".join(str(point[3]) for point in points)
    random_trigger_ok = (
        "右键接《元帅的计划》" in action_text
        and "若未掉落，不为它当天重复刷《收集情报》" in action_text
    )
    checks["marshal_random_trigger_guard"] = random_trigger_ok
    if not random_trigger_ok:
        hard.append({"type": "marshal_random_trigger_guard_missing"})

    probe_12892_ok = "12892《乐趣十足》" in str((draft.get("entry_decision") or {}).get("probe_12892") or "")
    checks["probe_12892_present"] = probe_12892_ok
    if not probe_12892_ok:
        hard.append({"type": "probe_12892_missing"})

    payload = {
        "status": "PASS" if not hard else "FAIL",
        "hard_issue_count": len(hard),
        "hard_issues": hard,
        "checks": checks,
        "publication_state": "formal_pre_live_fivebox_calibration",
        "next_state": "first_live_run_calibration",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if hard:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
