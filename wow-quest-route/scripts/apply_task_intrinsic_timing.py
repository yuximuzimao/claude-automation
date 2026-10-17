from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_PARAMETER_PATH = ROOT / "data/timing/task-parameters.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_task_row(node: Any, task_id: int) -> dict[str, Any] | None:
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
    parser = argparse.ArgumentParser(
        description="Apply an existing per-task intrinsic-service dataset as fixed Timing inputs for one Profile."
    )
    parser.add_argument("profile_id")
    parser.add_argument("source", type=Path)
    parser.add_argument("--timing-key", default="intrinsic_service_time")
    parser.add_argument("--clear-unavailable", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    profile = _load(ROOT / "data/route-profiles" / f"{args.profile_id}.json")
    source_path = args.source if args.source.is_absolute() else ROOT / args.source
    source = _load(source_path)
    params = _load(TASK_PARAMETER_PATH)
    param_rows = params.setdefault("tasks", {})

    task_ids: list[int] = []
    for action in profile.get("actions") or []:
        if action.get("kind") != "objective" or action.get("task_id") is None:
            continue
        task_id = int(action["task_id"])
        if task_id not in task_ids:
            task_ids.append(task_id)

    results = []
    for task_id in task_ids:
        card_path = ROOT / "data/task-cards" / f"{task_id}.json"
        card = _load(card_path)
        fivebox_status = str(((card.get("fivebox") or {}).get("status") or "")).strip()
        if fivebox_status == "pending":
            results.append({"task_id": task_id, "status": "pending_cleared" if card.get("timing_rule_ref") else "pending"})
            if args.write and card.get("timing_rule_ref") is not None:
                card["timing_rule_ref"] = None
                _write(card_path, card)
            continue

        row = _find_task_row(source, task_id)
        timing = None
        if isinstance(row, dict):
            timing = row.get(args.timing_key)
            if args.timing_key == "timing" and timing is None:
                timing = row.get("timing")
        if not isinstance(timing, dict) or timing.get("status") != "estimated" or not isinstance(timing.get("minutes"), (int, float)):
            results.append({"task_id": task_id, "status": "unavailable"})
            if args.write and args.clear_unavailable and card.get("timing_rule_ref") is not None:
                card["timing_rule_ref"] = None
                _write(card_path, card)
            continue

        results.append({"task_id": task_id, "status": "fixed", "minutes": float(timing["minutes"])})
        if not args.write:
            continue
        card["timing_rule_ref"] = "fixed-service-seconds"
        _write(card_path, card)
        entry = dict(param_rows.get(str(task_id)) or {})
        inputs = dict(entry.get("inputs") or {})
        inputs["fixed_service_seconds"] = float(timing["minutes"]) * 60.0
        entry["inputs"] = inputs
        entry["source_refs"] = [
            f"{source_path.relative_to(ROOT)}#task_id={task_id}; basis={timing.get('basis') or 'unknown'}"
        ]
        if isinstance(timing.get("range_minutes"), list):
            entry["provisional_range_minutes"] = timing["range_minutes"]
        else:
            entry.pop("provisional_range_minutes", None)
        param_rows[str(task_id)] = entry

    if args.write:
        _write(TASK_PARAMETER_PATH, params)
    counts = {status: sum(1 for row in results if row["status"] == status) for status in sorted({row["status"] for row in results})}
    print(json.dumps({"profile_id": args.profile_id, "source": str(source_path.relative_to(ROOT)), "write": args.write, "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
