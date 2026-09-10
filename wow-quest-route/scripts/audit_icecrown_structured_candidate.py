from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "data/route-atlas/icecrown-route-structured-candidate.json"
DRAFT = ROOT / "data/route-atlas/icecrown-entry-route-draft.json"
COVERAGE = ROOT / "data/route-atlas/icecrown-route-structured-coverage.json"
FOUNDATION = ROOT / "data/route-atlas/icecrown-task-foundation.json"
OUT = ROOT / "data/route-atlas/icecrown-structured-candidate-audit.json"

ROUTE_STATUSES = {
    "include_candidate",
    "include_conditional_route_state",
    "include_first_run_repeatable_or_calendar",
}
CONDITIONAL_TRIGGER_ACCEPT_EXEMPT = {12839}  # 《元帅的计划》由箱子信件条件触发，不伪造必然接取动作。
TASK_ACTION_GROUP = re.compile(r"(接|做|交)((?:《[^》]+》[、，, ]*)+)")
EXTERNAL_PLACES = ("无拘林地", "杉达拉废墟", "月光林地", "雷姆洛斯神殿", "龙眠神殿", "红玉巨龙圣地", "沙塔斯", "达拉然")
SAME_ANCHOR_PREFIXES = (
    "做《", "↳", "五号", "先", "每", "离开条件", "单号", "使用", "接受", "接《", "交《",
    "白骨巨人", "同一片墓地", "继续", "以上", "三项", "两项", "第一具", "第一只", "个人目标",
)
PLACE_TOKEN = re.compile(r"(基地|林地|废墟|墓地|神殿|港口|大教堂|堡垒|营地|村|高地|前线|大厅|矿洞|之峰|之墓|之庭|之门|拱顶|观察站|海姆|雷卡里斯|杜萨|采掘场)")
# These are intentional same-anchor actions even though their prose contains a place-like noun.
SAME_ANCHOR_EXCEPTIONS = {
    (2, 2), (2, 4), (2, 5), (2, 6),
    (23, 4), (23, 5), (24, 2), (24, 3), (38, 6),
}


def main() -> None:
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    formal_tasks = {
        int(task["quest_id"]): task
        for task in foundation.get("tasks", [])
        if task.get("scope_status") in ROUTE_STATUSES
    }
    formal_by_name = {str(task.get("name")): qid for qid, task in formal_tasks.items()}
    hard: list[dict] = []
    classified: list[dict] = []

    points = route.get("points") or []
    groups = route.get("stepGroups") or []
    for idx, point in enumerate(points):
        if len(point) < 9 or not (0 <= float(point[0]) <= 100 and 0 <= float(point[1]) <= 100):
            hard.append({"type": "invalid_point", "index": idx, "point": point})

    expected_start = 0
    for step, group in enumerate(groups, start=1):
        if int(group["start"]) != expected_start or int(group["end"]) < int(group["start"]):
            hard.append({"type": "non_contiguous_group", "step": step, "group": group})
        expected_start = int(group["end"]) + 1
    if expected_start != len(points):
        hard.append({"type": "group_point_coverage_mismatch", "covered_until": expected_start, "points": len(points)})

    fallbacks = ((route.get("geometryAudit") or {}).get("fallbackActions") or [])
    for row in fallbacks:
        step = int(row["step"])
        action = int(row["action"])
        text = str(row["text"])
        prefix = text.split("→", 1)[0].split("↳", 1)[0].strip()
        key = (step, action)
        if any(place in prefix for place in EXTERNAL_PLACES):
            status = "crossmap_not_drawn_on_icecrown_map"
        elif key in SAME_ANCHOR_EXCEPTIONS or prefix.startswith(SAME_ANCHOR_PREFIXES):
            status = "same_anchor_action"
        elif not PLACE_TOKEN.search(prefix):
            status = "same_hub_npc_or_instruction"
        else:
            status = "hard_unresolved_location"
            hard.append({"type": status, **row, "prefix": prefix})
        classified.append({**row, "classification": status})

    large_segments: list[dict] = []
    for idx in range(1, len(points)):
        distance = math.hypot(float(points[idx][0]) - float(points[idx - 1][0]), float(points[idx][1]) - float(points[idx - 1][1]))
        if distance >= 35:
            large_segments.append({
                "fromIndex": idx - 1,
                "toIndex": idx,
                "distance": round(distance, 2),
                "movement": points[idx][6],
                "from": points[idx - 1][2],
                "to": points[idx][2],
            })
        if distance > 60 and points[idx][6] not in {"script", "crossmap", "hearth"}:
            hard.append({"type": "implausible_single_map_segment", "index": idx, "distance": round(distance, 2)})

    action_text = "\n".join(str(point[3]) for point in points)

    # Cleaning rich planning prose must never delete a real task action. Audit the final player
    # skeleton itself: objective-bearing quests require 做, every formal quest requires 交, and
    # ordinary quests require 接. Conditional item-triggered quests are explicitly exempted.
    seen_actions: dict[int, set[str]] = {qid: set() for qid in formal_tasks}
    for verb, group_text in TASK_ACTION_GROUP.findall(action_text):
        for task_name in re.findall(r"《([^》]+)》", group_text):
            qid = formal_by_name.get(task_name)
            if qid is not None:
                seen_actions[qid].add(verb)
    for qid, task in formal_tasks.items():
        seen = seen_actions[qid]
        name = str(task.get("name") or qid)
        if task.get("objectives") and "做" not in seen:
            hard.append({"type": "task_action_missing_do", "quest_id": qid, "name": name, "seen": sorted(seen)})
        if "交" not in seen:
            hard.append({"type": "task_action_missing_turnin", "quest_id": qid, "name": name, "seen": sorted(seen)})
        if qid not in CONDITIONAL_TRIGGER_ACCEPT_EXEMPT and "接" not in seen:
            hard.append({"type": "task_action_missing_accept", "quest_id": qid, "name": name, "seen": sorted(seen)})

    expected_system_actions = {
        "开飞行点：银色比武场",
        "开飞行点：银色前线基地",
        "开飞行点：北伐军之峰",
        "开飞行点：暗影拱顶",
        "炉石绑定：暗影拱顶",
        "开飞行点：死亡高地",
    }
    actual_system_actions = {
        line for line in action_text.splitlines()
        if line.startswith("开飞行点：") or line.startswith("炉石绑定：")
    }
    if actual_system_actions != expected_system_actions:
        hard.append({
            "type": "transport_state_action_mismatch",
            "expected": sorted(expected_system_actions),
            "actual": sorted(actual_system_actions),
        })

    center_sum = sum(float(group["timing"]["centerMinutes"]) for group in groups)
    route_center = float((route.get("timing") or {}).get("centerMinutes", -1))
    if round(center_sum, 6) != round(route_center, 6):
        hard.append({"type": "timing_center_mismatch", "groups": center_sum, "route": route_center})

    if coverage.get("missing") or coverage.get("unexpected") or int(coverage.get("coveredTaskCount") or 0) != int(coverage.get("formalTaskCount") or -1):
        hard.append({"type": "coverage_not_closed", "coverage": coverage})

    # Preserve the useful publication-integrity checks from the retired all-in-one audit,
    # but apply them to the current structured candidate without historical task/step constants.
    draft_steps = draft.get("steps") or []
    if len(draft_steps) != len(groups):
        hard.append({"type": "draft_group_count_mismatch", "draft": len(draft_steps), "groups": len(groups)})

    missing_route_notes: list[dict] = []
    missing_fivebox_notes: list[dict] = []
    invalid_fivebox_format: list[dict] = []
    for step_no, (step, group) in enumerate(zip(draft_steps, groups), start=1):
        note_html = str(group.get("noteHtml") or "")
        for raw_qid, card in (step.get("task_cards") or {}).items():
            card = card or {}
            name = str(card.get("name") or "")
            route_note = str(card.get("route_note") or "").strip()
            fivebox = str(card.get("fivebox") or "").strip()
            if route_note and (name not in note_html or html.escape(route_note) not in note_html):
                missing_route_notes.append({"quest_id": int(raw_qid), "name": name, "step": step_no})
            if fivebox:
                if fivebox.startswith("共享："):
                    marker = '<span class="ra-shared">共享：</span>'
                    detail = fivebox[len("共享："):].strip()
                elif fivebox.startswith("不共享："):
                    marker = '<span class="ra-not-shared">不共享：</span>'
                    detail = fivebox[len("不共享："):].strip()
                elif "待实测" in fivebox:
                    marker = '<span class="ra-pending">五开待实测：</span>'
                    detail = re.sub(r"^(?:重点)?待实测[：:]\s*", "", fivebox).strip()
                else:
                    invalid_fivebox_format.append({"quest_id": int(raw_qid), "name": name, "step": step_no, "fivebox": fivebox})
                    continue
                published = name in note_html and marker in note_html
                if detail:
                    published = published and html.escape(detail) in note_html
                if not published:
                    missing_fivebox_notes.append({"quest_id": int(raw_qid), "name": name, "step": step_no})
    if missing_route_notes:
        hard.append({"type": "route_note_not_published", "rows": missing_route_notes})
    if missing_fivebox_notes:
        hard.append({"type": "fivebox_note_not_published", "rows": missing_fivebox_notes})
    if invalid_fivebox_format:
        hard.append({"type": "fivebox_format", "rows": invalid_fivebox_format})

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
    if peak_active > 25:
        hard.append({"type": "quest_log_capacity", "peak_active": peak_active, "peak_step": peak_step, "peak_tasks": peak_tasks})

    blocked_dependency_names = {
        str(task.get("name") or "")
        for task in foundation.get("tasks", [])
        if task.get("scope_status") == "exclude_dependency_on_blocked_task" and task.get("name")
    }
    published_task_names: set[str] = set()
    task_span_pattern = re.compile(r'<span class="ra-task(?: [^"]+)?">([^<]+)</span>')
    for group in groups:
        published_task_names.update(html.unescape(name) for name in task_span_pattern.findall(str(group.get("actionHtml") or "")))
    blocked_task_leaks = sorted(blocked_dependency_names & published_task_names)
    if blocked_task_leaks:
        hard.append({"type": "blocked_dependency_task_published", "tasks": blocked_task_leaks})

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
    forbidden_player_terms = ("首跑前预算", "外部基准", "本服首跑实测", "共享预期", "首跑只需确认", "五开：")
    bare_task_id = re.compile(r"(?<!\d)\d{5}(?!\d)")
    player_text_violations: list[dict] = []
    for field, text in visible_fragments:
        terms = [term for term in forbidden_player_terms if term in text]
        ids = sorted(set(bare_task_id.findall(text)))
        if terms or ids:
            player_text_violations.append({"field": field, "forbidden_terms": terms, "bare_task_ids": ids, "text": text[:500]})
    if player_text_violations:
        hard.append({"type": "player_text_contract", "rows": player_text_violations})

    payload = {
        "status": "PASS" if not hard else "FAIL",
        "hardIssueCount": len(hard),
        "hardIssues": hard,
        "pointCount": len(points),
        "stepGroupCount": len(groups),
        "geometryFallbackCount": len(fallbacks),
        "geometryFallbackClassifications": classified,
        "largeSegmentReview": large_segments,
        "transportStateActions": sorted(actual_system_actions),
        "timingCenterMinutes": center_sum,
        "publicationIntegrity": {
            "missingRouteNotes": missing_route_notes,
            "missingFiveboxNotes": missing_fivebox_notes,
            "invalidFiveboxFormat": invalid_fivebox_format,
            "questLogPeakActive": peak_active,
            "questLogPeakStep": peak_step,
            "questLogPeakTasks": peak_tasks,
            "questLogFinalActive": final_active,
            "blockedDependencyTaskCount": len(blocked_dependency_names),
            "blockedTaskLeaks": blocked_task_leaks,
            "playerTextViolations": player_text_violations,
        },
        "coverage": {
            "formal": coverage.get("formalTaskCount"),
            "covered": coverage.get("coveredTaskCount"),
            "missing": coverage.get("missing"),
            "unexpected": coverage.get("unexpected"),
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": payload["status"], "hard": len(hard), "points": len(points), "groups": len(groups),
        "fallbacks": len(fallbacks), "large_segments_for_review": len(large_segments), "timing_center": center_sum,
    }, ensure_ascii=False, indent=2))
    if hard:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
