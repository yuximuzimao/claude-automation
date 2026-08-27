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
TASK_GROUP_TOKEN = r"(?:《[^》]+》)+"
FLOW_ACTION_RE = re.compile(rf"^[^：；;,，0-9]+(?:\s*→\s*(?:接|做|交){TASK_GROUP_TOKEN})+$")
SYSTEM_ACTION_RE = re.compile(r"^(?:开飞行点|炉石绑定|使用炉石)：[^：；;,，0-9]+$")
SYSTEM_FLIGHT_RE = re.compile(r"^系统飞行：[^：；;,，0-9]+\s*→\s*[^：；;,，0-9]+$")


def action_skeleton_ok(text: str) -> bool:
    value = str(text).strip()
    return bool(SYSTEM_ACTION_RE.fullmatch(value) or SYSTEM_FLIGHT_RE.fullmatch(value) or FLOW_ACTION_RE.fullmatch(value))


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

    action_skeleton_violations = [
        {"step": int(step.get("step") or 0), "action": str(action)}
        for step in steps
        for action in (step.get("actions") or [])
        if not action_skeleton_ok(str(action))
    ]
    checks["action_skeleton_violation_count"] = len(action_skeleton_violations)
    if action_skeleton_violations:
        hard.append({"type": "action_skeleton_contract", "rows": action_skeleton_violations})

    if len(formal) != 61:
        hard.append({"type": "formal_task_count", "actual": len(formal), "expected": 61})
    if len(steps) != 16 or len(groups) != 16:
        hard.append({"type": "step_count", "draft": len(steps), "published": len(groups), "expected": 16})
    if str(draft.get("status") or "") != "icecrown_reachable_route_live_entry_confirmed":
        hard.append({"type": "stale_draft_status", "status": draft.get("status")})

    coverage_ok = (
        int(coverage.get("candidate_count", -1)) == len(formal)
        and int(coverage.get("covered_count", -1)) == len(formal)
        and int(coverage.get("uncovered_count", -1)) == 0
        and not coverage.get("uncovered")
    )
    checks["coverage_ok"] = coverage_ok
    if not coverage_ok:
        hard.append({"type": "coverage", "payload": coverage})

    dependency_ok = (
        int(dependency.get("candidate_count", -1)) == len(formal)
        and int(dependency.get("mentioned_candidate_count", -1)) == len(formal)
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
        and route.get("status") == "live_entry_confirmed_current_group_at_12897"
        and int(route.get("order") or -1) == 7
        and int(route.get("defaultGroupIndex") or -1) == 1
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
        and abs(group_center - 289.0) < 1e-6
        and [float(x) for x in route_timing.get("rangeMinutes") or []] == [216.0, 398.0]
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
    invalid_fivebox_format: list[dict] = []
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
                expected_marker = ""
                expected_detail = ""
                if fivebox.startswith("共享："):
                    expected_marker = '<span class="ra-shared">共享：</span>'
                    expected_detail = fivebox[len("共享："):].strip()
                elif fivebox.startswith("不共享："):
                    expected_marker = '<span class="ra-not-shared">不共享：</span>'
                    expected_detail = fivebox[len("不共享："):].strip()
                elif "待实测" in fivebox:
                    expected_marker = '<span class="ra-pending">五开待实测：</span>'
                    expected_detail = re.sub(r"^(?:重点)?待实测[：:]\s*", "", fivebox).strip()
                else:
                    invalid_fivebox_format.append({
                        "quest_id": int(qid),
                        "name": name,
                        "step": step_no,
                        "fivebox": fivebox,
                    })
                if expected_marker:
                    published = name in note_html and expected_marker in note_html
                    if expected_detail:
                        published = published and html.escape(expected_detail) in note_html
                    if not published:
                        missing_fivebox_notes.append({"quest_id": int(qid), "name": name, "step": step_no})
    checks["route_note_cards"] = route_note_cards
    checks["fivebox_cards"] = fivebox_cards
    checks["missing_route_notes"] = len(missing_route_notes)
    checks["missing_fivebox_notes"] = len(missing_fivebox_notes)
    checks["invalid_fivebox_format"] = len(invalid_fivebox_format)
    if missing_route_notes:
        hard.append({"type": "route_note_not_published", "rows": missing_route_notes})
    if missing_fivebox_notes:
        hard.append({"type": "fivebox_note_not_published", "rows": missing_fivebox_notes})
    if invalid_fivebox_format:
        hard.append({"type": "fivebox_format", "rows": invalid_fivebox_format})

    def visible_text(raw: object) -> str:
        return html.unescape(re.sub(r"<[^>]+>", "", str(raw or "")))

    visible_fragments: list[tuple[str, str]] = [
        ("route.title", visible_text(route.get("title"))),
        ("route.sub", visible_text(route.get("sub"))),
        ("route.badge", visible_text(route.get("badge"))),
        ("route.footer", visible_text(route.get("footer"))),
    ]
    for step_no, group in enumerate(groups, start=1):
        visible_fragments.extend([
            (f"step.{step_no}.title", visible_text(group.get("title"))),
            (f"step.{step_no}.summary", visible_text(group.get("summary"))),
            (f"step.{step_no}.actionHtml", visible_text(group.get("actionHtml"))),
            (f"step.{step_no}.noteHtml", visible_text(group.get("noteHtml"))),
        ])

    forbidden_player_terms = (
        "首跑前预算",
        "外部基准",
        "本服首跑实测",
        "共享预期",
        "首跑只需确认",
        "五开：",
    )
    player_text_violations: list[dict] = []
    bare_task_id = re.compile(r"(?<!\d)\d{5}(?!\d)")
    for field, text in visible_fragments:
        terms = [term for term in forbidden_player_terms if term in text]
        ids = sorted(set(bare_task_id.findall(text)))
        if terms or ids:
            player_text_violations.append({
                "field": field,
                "forbidden_terms": terms,
                "bare_task_ids": ids,
                "text": text[:500],
            })
    checks["player_text_violation_count"] = len(player_text_violations)
    if player_text_violations:
        hard.append({"type": "player_text_contract", "rows": player_text_violations})

    blocked_dependency_names = {
        str(task.get("name") or "")
        for task in foundation.get("tasks", [])
        if task.get("scope_status") == "exclude_dependency_on_blocked_task" and task.get("name")
    }
    published_task_names = set()
    task_span_pattern = re.compile(r'<span class="ra-task(?: [^"]+)?">([^<]+)</span>')
    for group in groups:
        published_task_names.update(html.unescape(name) for name in task_span_pattern.findall(str(group.get("actionHtml") or "")))
    blocked_task_leaks = sorted(blocked_dependency_names & published_task_names)
    checks["blocked_dependency_task_count"] = len(blocked_dependency_names)
    checks["blocked_task_leak_count"] = len(blocked_task_leaks)
    if len(blocked_dependency_names) != 102:
        hard.append({"type": "blocked_dependency_count", "actual": len(blocked_dependency_names), "expected": 102})
    if blocked_task_leaks:
        hard.append({"type": "blocked_dependency_task_published", "tasks": blocked_task_leaks})

    action_text = "\n".join(str(point[3]) for point in points)
    task_note_text = "\n".join(
        " ".join(str(card.get(key) or "") for key in ("route_note", "fivebox"))
        for step in steps
        for card in (step.get("task_cards") or {}).values()
    )
    random_trigger_ok = (
        "元帅信件" in task_note_text
        and "当天不重复刷" in task_note_text
    )
    checks["marshal_random_trigger_guard"] = random_trigger_ok
    if not random_trigger_ok:
        hard.append({"type": "marshal_random_trigger_guard_missing"})

    entry_decision = draft.get("entry_decision") or {}
    live_12892_ok = (
        entry_decision.get("live_12892_confirmed") is True
        and entry_decision.get("live_12892_completed") is True
        and "接《乐趣十足》" in action_text
        and entry_decision.get("geographic_entry") == "银色比武场"
        and entry_decision.get("first_quest_hub") == "奥格瑞姆之锤"
    )
    checks["live_12892_confirmed"] = live_12892_ok
    if not live_12892_ok:
        hard.append({"type": "live_12892_state_missing_or_wrong_entry"})

    payload = {
        "status": "PASS" if not hard else "FAIL",
        "hard_issue_count": len(hard),
        "hard_issues": hard,
        "checks": checks,
        "publication_state": "icecrown_first_run_finished_with_valhalas_deferred",
        "next_state": "start_sholazar_live_calibration",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if hard:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
