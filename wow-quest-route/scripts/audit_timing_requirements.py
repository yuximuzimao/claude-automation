from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_task_row(node, task_id: int):
    if isinstance(node, dict):
        if node.get("quest_id") == task_id or node.get("task_id") == task_id:
            return node
        for value in node.values():
            found = _find_task_row(value, task_id)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_task_row(value, task_id)
            if found is not None:
                return found
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Group unresolved Route Timing inputs by step.")
    parser.add_argument("profile_id")
    parser.add_argument("--step", action="append", default=[], help="Only include these step ids.")
    parser.add_argument("--foundation", type=Path, help="Optional legacy/current task-foundation JSON for migration diagnostics.")
    args = parser.parse_args()

    profile_id = args.profile_id
    timing_path = ROOT / "data/generated/route-lifecycle/profiles" / profile_id / "timing.json"
    profile_path = ROOT / "data/route-profiles" / f"{profile_id}.json"
    if not timing_path.exists():
        raise SystemExit(f"Missing Timing artifact: {timing_path}")
    if not profile_path.exists():
        raise SystemExit(f"Missing Route Profile: {profile_path}")

    timing = _load(timing_path)
    profile = _load(profile_path)
    quest_inputs = _load(ROOT / "data/timing/quest-source-inputs.json")
    legacy_types = _load(ROOT / "data/observations/fivebox-task-types.json")
    foundation = _load(args.foundation) if args.foundation else None

    task_cards: dict[str, dict] = {}
    for task_id in profile.get("task_ids") or []:
        path = ROOT / "data/task-cards" / f"{task_id}.json"
        if path.exists():
            task_cards[str(task_id)] = _load(path)

    action_by_id = {str(row["action_id"]): row for row in profile.get("actions") or []}
    issues_by_step: dict[str, list[dict]] = defaultdict(list)
    for issue in timing.get("issues") or []:
        if issue.get("kind") == "timing_range_model_required":
            continue
        if issue.get("resolved_by") == "legacy_step_baseline" or issue.get("severity") in {"requirement", "unknown", "error"}:
            issues_by_step[str(issue.get("step_id") or "__profile__")].append(issue)

    legacy_task_rows = legacy_types.get("tasks") or legacy_types
    quest_task_rows = quest_inputs.get("tasks") or {}

    rows = []
    selected_steps = {str(value) for value in args.step}
    for step in profile.get("step_groups") or []:
        step_id = str(step["step_id"])
        if selected_steps and step_id not in selected_steps:
            continue
        step_issues = issues_by_step.get(step_id, [])
        task_ids = []
        for action_id in step.get("action_ids") or []:
            action = action_by_id.get(str(action_id)) or {}
            if action.get("kind") == "objective" and action.get("task_id") is not None:
                task_id = int(action["task_id"])
                if task_id not in task_ids:
                    task_ids.append(task_id)

        tasks = []
        for task_id in task_ids:
            card = task_cards.get(str(task_id)) or {}
            identity = card.get("identity") or {}
            fivebox = card.get("fivebox") or {}
            legacy = legacy_task_rows.get(str(task_id)) or {}
            quest = quest_task_rows.get(str(task_id)) or {}
            relevant_issues = [
                issue
                for issue in step_issues
                if issue.get("task_id") == task_id
            ]
            foundation_row = _find_task_row(foundation, task_id) if foundation is not None else None
            tasks.append(
                {
                    "task_id": task_id,
                    "name": identity.get("name_zhcn"),
                    "timing_rule_ref": card.get("timing_rule_ref"),
                    "fivebox_status": fivebox.get("status"),
                    "legacy_type": legacy.get("type"),
                    "quest_inputs": quest.get("inputs") or {},
                    "quest_objectives": quest.get("objectives") or [],
                    "quest_issues": quest.get("issues") or [],
                    "foundation": (
                        {
                            "task_class": foundation_row.get("task_class"),
                            "intrinsic_service_time": foundation_row.get("intrinsic_service_time"),
                        }
                        if isinstance(foundation_row, dict)
                        else None
                    ),
                    "issue_kinds": sorted({str(issue.get("kind")) for issue in relevant_issues}),
                }
            )

        non_task_issues = [
            {
                "kind": issue.get("kind"),
                "action_id": issue.get("action_id"),
                "service_id": issue.get("service_id"),
                "operation_kind": issue.get("operation_kind"),
                "severity": issue.get("severity"),
                "resolved_by": issue.get("resolved_by"),
            }
            for issue in step_issues
            if issue.get("task_id") is None
        ]
        timing_step = next((row for row in timing.get("steps") or [] if row.get("step_id") == step_id), {})
        rows.append(
            {
                "step_id": step_id,
                "title": step.get("title"),
                "center_minutes": timing_step.get("center_minutes"),
                "unresolved_component_count": timing_step.get("unresolved_component_count"),
                "tasks": tasks,
                "non_task_issues": non_task_issues,
            }
        )

    payload = {
        "profile_id": profile_id,
        "timing_status": timing.get("status"),
        "timing_center_minutes": timing.get("center_minutes"),
        "timing_complete": timing.get("complete"),
        "steps": rows,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
