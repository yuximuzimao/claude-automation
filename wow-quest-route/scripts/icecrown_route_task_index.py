from __future__ import annotations

from collections import Counter


def step_text(step: dict) -> str:
    parts = [str(step.get("title") or ""), str(step.get("exit") or "")]
    parts.extend(str(value) for value in (step.get("actions") or []))
    for card in (step.get("task_cards") or {}).values():
        if not isinstance(card, dict):
            continue
        parts.extend(
            str(card.get(key) or "")
            for key in ("name", "objective", "route_note", "fivebox")
        )
    return "\n".join(parts)


def build_route_task_index(tasks: list[dict], route: dict) -> dict:
    by_id = {int(task["quest_id"]): task for task in tasks}
    name_counts = Counter(str(task.get("name") or "") for task in tasks)
    steps = route.get("steps", [])
    text_by_step = {int(step["step"]): step_text(step) for step in steps}
    first_step: dict[int, int] = {}
    mention_steps: dict[int, list[int]] = {}

    for qid, task in by_id.items():
        name = str(task.get("name") or "")
        explicit_card_steps = [
            int(step["step"])
            for step in steps
            if str(qid) in (step.get("task_cards") or {})
        ]
        named_steps = []
        if name and name_counts[name] == 1:
            token = f"《{name}》"
            named_steps = [step_no for step_no, text in text_by_step.items() if token in text]
        all_steps = sorted(set(explicit_card_steps + named_steps))
        mention_steps[qid] = all_steps
        if all_steps:
            first_step[qid] = all_steps[0]

    missing_mentions = [
        {"quest_id": qid, "name": by_id[qid].get("name")}
        for qid in sorted(by_id)
        if qid not in first_step
    ]
    return {
        "first_step": first_step,
        "mention_steps": mention_steps,
        "missing_mentions": missing_mentions,
    }
