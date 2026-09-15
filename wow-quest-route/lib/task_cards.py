from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
TASK_CARDS_DIR = ROOT / "data/task-cards"
TASK_CARD_SCHEMA = TASK_CARDS_DIR / "schema.json"

# Route decisions must never become intrinsic task facts, even inside flexible explanatory objects.
FORBIDDEN_ROUTE_KEYS = {
    "profile_id",
    "step_id",
    "step_number",
    "route_order",
    "route_note",
    "selection_decision",
    "must_do",
    "skip",
    "current_route_minutes",
    "predicted_turnin_level",
    "template_type",
}


class TaskCardError(ValueError):
    """Raised when a Task Card violates the project contract."""


def task_card_path(task_id: int) -> Path:
    return TASK_CARDS_DIR / f"{int(task_id)}.json"


def load_task_card_schema() -> dict[str, Any]:
    return json.loads(TASK_CARD_SCHEMA.read_text(encoding="utf-8"))


def _schema_validator() -> Draft202012Validator:
    schema = load_task_card_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_schema(card: Any) -> None:
    errors = sorted(_schema_validator().iter_errors(card), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    rendered: list[str] = []
    for error in errors[:8]:
        path = "$"
        for part in error.absolute_path:
            path += f"[{part}]" if isinstance(part, int) else f".{part}"
        rendered.append(f"{path}: {error.message}")
    if len(errors) > 8:
        rendered.append(f"... and {len(errors) - 8} more schema errors")
    raise TaskCardError("Task Card JSON Schema validation failed: " + "; ".join(rendered))


def _duplicates(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield key, child_path
            yield from _walk_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def validate_task_card(card: dict[str, Any], *, expected_task_id: int | None = None) -> None:
    """Validate one Task Card.

    JSON Schema is the sole shape/type/enum contract.  The checks below are only semantic invariants
    that JSON Schema cannot express cleanly: filename identity, cross references, duplicate logical
    IDs, and the prohibition on route decisions leaking into a Task Card.
    """

    _validate_schema(card)

    task_id = card["task_id"]
    if expected_task_id is not None and task_id != expected_task_id:
        raise TaskCardError(f"task_id {task_id} does not match filename/id {expected_task_id}")

    forbidden_hits = [(key, path) for key, path in _walk_keys(card) if key in FORBIDDEN_ROUTE_KEYS]
    if forbidden_hits:
        rendered = ", ".join(f"{key}@{path}" for key, path in forbidden_hits)
        raise TaskCardError(f"route/derived fields are forbidden in Task Card: {rendered}")

    objectives = card["objectives"]
    objective_ids = [objective["objective_id"] for objective in objectives]
    duplicate_objectives = _duplicates(objective_ids)
    if duplicate_objectives:
        raise TaskCardError(f"duplicate objective_id values: {duplicate_objectives}")

    mechanics = card["mechanics"]
    mechanic_ids = set(mechanics)
    for objective in objectives:
        missing_refs = sorted(set(objective.get("mechanic_refs", [])) - mechanic_ids)
        if missing_refs:
            raise TaskCardError(
                f"objective {objective['objective_id']} references missing mechanics: {missing_refs}"
            )

    stages = card["fivebox"]["stages"]
    stage_ids = [stage["stage_id"] for stage in stages]
    duplicate_stages = _duplicates(stage_ids)
    if duplicate_stages:
        raise TaskCardError(f"duplicate fivebox stage_id values: {duplicate_stages}")

    objective_id_set = set(objective_ids)
    for stage in stages:
        objective_id = stage["objective_id"]
        if objective_id is not None and objective_id not in objective_id_set:
            raise TaskCardError(
                f"fivebox stage {stage['stage_id']} references unknown objective {objective_id!r}"
            )

    evidence_ids = [item["evidence_id"] for item in card["evidence"]]
    duplicate_evidence = _duplicates(evidence_ids)
    if duplicate_evidence:
        raise TaskCardError(f"duplicate evidence_id values: {duplicate_evidence}")

    coverage = card["coverage"]
    if coverage["fivebox"] == "verified" and not stages:
        raise TaskCardError("coverage.fivebox=verified requires at least one structured fivebox stage")
    if coverage["fivebox"] == "not_applicable" and stages:
        raise TaskCardError("coverage.fivebox=not_applicable cannot contain fivebox stages")


def load_task_card(task_id: int, *, validate: bool = True) -> dict[str, Any]:
    path = task_card_path(task_id)
    if not path.exists():
        raise FileNotFoundError(path)
    card = json.loads(path.read_text(encoding="utf-8"))
    if validate:
        validate_task_card(card, expected_task_id=int(task_id))
    return card


def load_all_task_cards(*, validate: bool = True) -> dict[int, dict[str, Any]]:
    cards: dict[int, dict[str, Any]] = {}
    for path in sorted(TASK_CARDS_DIR.glob("*.json")):
        if path.name == "schema.json":
            continue
        try:
            task_id = int(path.stem)
        except ValueError as exc:
            raise TaskCardError(f"Task Card filename must be numeric: {path.name}") from exc
        card = json.loads(path.read_text(encoding="utf-8"))
        if validate:
            validate_task_card(card, expected_task_id=task_id)
        if task_id in cards:
            raise TaskCardError(f"duplicate Task Card id: {task_id}")
        cards[task_id] = card
    return cards


def build_task_dependents_index(
    cards: dict[int, dict[str, Any]] | None = None,
) -> dict[int, list[int]]:
    """Derive predecessor -> dependent Task Card relations from the authoritative forward fields.

    Task Cards never persist `direct_followups`; reverse relations are rebuilt mechanically.
    """

    if cards is None:
        cards = load_all_task_cards()
    index: dict[int, set[int]] = {}
    for task_id, card in cards.items():
        availability = card["availability"]
        predecessors = {
            *availability.get("pre_any", []),
            *availability.get("pre_all", []),
            *availability.get("parent_active", []),
        }
        for predecessor in predecessors:
            index.setdefault(int(predecessor), set()).add(int(task_id))
    return {
        predecessor: sorted(dependents)
        for predecessor, dependents in sorted(index.items())
    }
