from __future__ import annotations

from typing import Any

STATUS_TO_BADGE = {
    "shared": "shared",
    "not_shared": "not_shared",
    "sequential_loot": "sequential_loot",
    "pending": None,
}


class TaskPresentationError(ValueError):
    """Raised when Task Presentation metadata is internally inconsistent."""


def _scope_matches(scope: str, profile_id: str | None) -> bool:
    if scope == "all":
        return True
    if profile_id is None:
        return False
    if scope.startswith("route_profile:"):
        return scope.split(":", 1)[1] == profile_id
    return False


def _scoped_override(
    value: Any,
    *,
    profile_id: str | None,
    kind: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise TaskPresentationError(f"presentation.{kind} must be an object or null")
    scope = str(value.get("scope", ""))
    return value if _scope_matches(scope, profile_id) else None


def project_task_presentation(
    card: dict[str, Any],
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Project a validated Task Card into minimal player-facing task metadata.

    Machine facts come only from structured Task Card fields. Human guide text is never parsed to
    infer a badge or mechanic. User-confirmed note overrides affect player notes only.
    """

    presentation = card.get("presentation", {})

    fivebox_status = card.get("fivebox", {}).get("status")
    if fivebox_status not in STATUS_TO_BADGE:
        raise TaskPresentationError(f"unsupported fivebox.status: {fivebox_status!r}")
    badge = STATUS_TO_BADGE[fivebox_status]

    note_override = _scoped_override(
        presentation.get("note_override"),
        profile_id=profile_id,
        kind="note_override",
    )
    note = None if note_override is None else str(note_override.get("text", ""))

    pending_questions = [
        question
        for question in card.get("verification", {}).get("open_questions", [])
        if isinstance(question, dict) and question.get("status") in {"unknown", "expected"}
    ]
    pending = fivebox_status == "pending"

    return {
        "task_id": card.get("task_id"),
        "name": card.get("identity", {}).get("name_zhcn"),
        "badge": badge,
        "note": note,
        "note_override_applied": note_override is not None,
        "pending": pending,
        "pending_questions": pending_questions,
    }
