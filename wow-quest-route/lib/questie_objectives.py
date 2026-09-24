from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .questie_drop_rates import QuestieDropRateDB
from .questie_effective import effective_quest_rows
from .questie_lua import seq
from .questie_source import QuestieData, load_questie

Q_OBJECTIVES = 10
Q_TRIGGER_END = 9
ITEM_NPC_DROPS = 2
ITEM_OBJECT_DROPS = 3

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
}

USABLE_COUNT_CONFIDENCE = {"exact", "exact_text_order", "implicit_single"}


def ordered_numeric_mentions(text: str) -> list[int]:
    """Return objective-like numeric mentions in textual order.

    This is the historical parser used by the route foundation builders. It lives in lib now so
    foundation extraction and Timing's Effective Quest Source Adapter cannot drift into two count
    parsers. It parses Questie's objective source text only; it is never used on Task Card guide,
    presentation notes, route prose or generated HTML.
    """

    mentions: list[tuple[int, int]] = []
    for match in re.finditer(r"(?<![A-Za-z0-9-])\d{1,3}(?![A-Za-z0-9-])", text):
        value = int(match.group(0))
        if 1 <= value <= 100:
            mentions.append((match.start(), value))
    lower = text.lower()
    for word, value in NUMBER_WORDS.items():
        for match in re.finditer(rf"\b{word}\b", lower):
            mentions.append((match.start(), value))
    mentions.sort()
    return [value for _, value in mentions]


def objective_counts(text: str, slot_count: int) -> tuple[list[int | None], str]:
    if slot_count == 0:
        return [], "exact"
    values = ordered_numeric_mentions(text)
    if len(values) == slot_count:
        return values, "exact_text_order"
    if len(values) > slot_count:
        return values[-slot_count:], "ambiguous_extra_numbers"
    if len(values) == 0 and slot_count == 1:
        return [1], "implicit_single"
    return values + [None] * (slot_count - len(values)), "missing_counts"


def localized_objective_text(data: QuestieData, quest_id: int) -> str:
    value = data.quest_names.get(quest_id)
    if not isinstance(value, dict):
        return ""
    objectives = seq(value.get(2))
    return " / ".join(str(value) for value in objectives if isinstance(value, str))


def english_objective_text(row: dict[Any, Any]) -> str:
    return " / ".join(str(value) for value in seq(row.get(8)) if isinstance(value, str))


def raw_objective_slots(row: dict[Any, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    raw = row.get(Q_OBJECTIVES)
    if isinstance(raw, dict):
        for key, objective_type in ((1, "kill"), (2, "object"), (3, "item"), (4, "reputation")):
            for entry in seq(raw.get(key)):
                values = seq(entry)
                if values and isinstance(values[0], int):
                    result.append({"objective_type": objective_type, "entity_id": int(values[0])})
        for entry in seq(raw.get(5)):
            values = seq(entry)
            if values:
                first = values[0]
                if isinstance(first, dict):
                    ids = [int(npc_id) for npc_id in seq(first) if isinstance(npc_id, int)]
                    result.append({"objective_type": "event", "entity_ids": ids})
                else:
                    result.append({"objective_type": "event", "entity_ids": []})
    if row.get(Q_TRIGGER_END):
        result.append({"objective_type": "event", "entity_ids": [], "trigger_end": True})
    return result


def objective_atoms(data: QuestieData, quest_id: int, row: dict[Any, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract the small Questie objective facts Timing may consume.

    Counts are promoted as usable only when the inherited historical parser can map the source text
    to objective slots without ambiguity. Ambiguous text remains visible evidence but never becomes a
    machine Timing input.
    """

    slots = raw_objective_slots(row)
    text = localized_objective_text(data, quest_id) or english_objective_text(row)
    counts, confidence = objective_counts(text, len(slots))
    usable = confidence in USABLE_COUNT_CONFIDENCE
    atoms: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    if not usable and slots:
        issues.append(
            {
                "severity": "requirement",
                "kind": "questie_objective_count_review_required",
                "task_id": quest_id,
                "count_confidence": confidence,
                "slot_count": len(slots),
            }
        )

    for index, slot in enumerate(slots):
        row_out = dict(slot)
        raw_count = counts[index] if index < len(counts) else None
        row_out["required_count"] = int(raw_count) if usable and isinstance(raw_count, int) else None
        row_out["source_count_candidate"] = int(raw_count) if isinstance(raw_count, int) else None
        row_out["count_confidence"] = confidence
        if slot["objective_type"] == "item":
            item_id = int(slot["entity_id"])
            item = data.items.get(item_id)
            row_out["item_id"] = item_id
            if isinstance(item, dict):
                row_out["source_npc_ids"] = [
                    int(npc_id) for npc_id in seq(item.get(ITEM_NPC_DROPS)) if isinstance(npc_id, int)
                ]
                row_out["source_object_ids"] = [
                    int(object_id) for object_id in seq(item.get(ITEM_OBJECT_DROPS)) if isinstance(object_id, int)
                ]
            else:
                row_out["source_npc_ids"] = []
                row_out["source_object_ids"] = []
        atoms.append(row_out)
    return atoms, issues


def timing_inputs_from_atoms(
    atoms: list[dict[str, Any]],
    *,
    drop_db: QuestieDropRateDB | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []

    kill_atoms = [row for row in atoms if row["objective_type"] == "kill"]
    if kill_atoms and all(isinstance(row.get("required_count"), int) for row in kill_atoms):
        inputs["kill_count"] = sum(int(row["required_count"]) for row in kill_atoms)

    object_atoms = [row for row in atoms if row["objective_type"] == "object"]
    if len(object_atoms) == 1 and isinstance(object_atoms[0].get("required_count"), int):
        inputs["interaction_count"] = int(object_atoms[0]["required_count"])

    item_atoms = [row for row in atoms if row["objective_type"] == "item"]
    if len(item_atoms) == 1 and isinstance(item_atoms[0].get("required_count"), int):
        item = item_atoms[0]
        inputs["required_count"] = int(item["required_count"])
        inputs["item_id"] = int(item["item_id"])
        npc_ids = list(item.get("source_npc_ids") or [])
        if drop_db is not None and len(npc_ids) == 1:
            rate = drop_db.get(int(item["item_id"]), int(npc_ids[0]))
            if rate is not None:
                inputs["drop_rate"] = float(rate.rate)
                inputs["drop_rate_source"] = rate.source
                inputs["drop_rate_npc_id"] = int(npc_ids[0])
        elif drop_db is not None and len(npc_ids) > 1:
            candidates = []
            for npc_id in npc_ids:
                rate = drop_db.get(int(item["item_id"]), int(npc_id))
                if rate is not None:
                    candidates.append({"npc_id": int(npc_id), "rate": float(rate.rate), "source": rate.source})
            if candidates:
                inputs["drop_rate_candidates"] = candidates
                issues.append(
                    {
                        "severity": "requirement",
                        "kind": "drop_rate_route_source_selection_required",
                        "item_id": int(item["item_id"]),
                        "candidate_npc_ids": [row["npc_id"] for row in candidates],
                    }
                )
    return inputs, issues


def build_effective_timing_source_inputs(
    source: str | Path,
    task_ids: Iterable[int],
) -> dict[str, Any]:
    path = Path(source).expanduser().resolve()
    ids = sorted({int(task_id) for task_id in task_ids})
    if not path.exists():
        return {
            "schema_version": 1,
            "status": "requirements",
            "source": {"path": str(path), "exists": False},
            "tasks": {},
            "issues": [
                {
                    "severity": "requirement",
                    "kind": "questie_timing_source_required",
                    "path": str(path),
                }
            ],
        }

    data = load_questie(path)
    effective_rows, correction_audit = effective_quest_rows(data, path, ids)
    drop_db = QuestieDropRateDB(path) if path.is_file() and path.suffix.lower() == ".zip" else None
    tasks: dict[str, Any] = {}
    issues: list[dict[str, Any]] = []
    for task_id in ids:
        row = effective_rows.get(task_id)
        if not isinstance(row, dict):
            issues.append({"severity": "requirement", "kind": "questie_task_missing", "task_id": task_id})
            continue
        atoms, atom_issues = objective_atoms(data, task_id, row)
        resolved, resolution_issues = timing_inputs_from_atoms(atoms, drop_db=drop_db)
        tasks[str(task_id)] = {
            "inputs": resolved,
            "objectives": atoms,
            "issues": atom_issues + resolution_issues,
        }
        issues.extend(atom_issues)
        issues.extend({"task_id": task_id, **issue} for issue in resolution_issues)

    return {
        "schema_version": 1,
        "status": "requirements" if issues else "pass",
        "source": {
            "path": str(path),
            "exists": True,
            "questie_version": data.version,
            "source_sha256": data.source_sha256,
            "correction_parse_failures": correction_audit.get("parse_failures") or {},
        },
        "tasks": tasks,
        "issues": issues,
    }
