from __future__ import annotations

import re
from typing import Any

STATUS_TO_BADGE = {
    "shared": "shared",
    "not_shared": "not_shared",
    "sequential_loot": "sequential_loot",
    "special": "special",
    "pending": None,
}
DEFERRED_NOTE_OPTIMIZATION_MARKER = "【需要单独修正优化】"
PROCESS_PREFIX_RE = re.compile(
    r"^[^：:\n]{0,48}(?:(?:首组|第二组|本轮)?(?:实跑|实测)(?:确认)?|首组确认|已实测|已验证|经审计)(?:[：:]\s*)?"
)
STATUS_PREFIX_RE = re.compile(
    r"^(?:(?:任务|完成)?(?:进度|完成)?\s*)?(?:共享|不共享|依次拾取|特殊|待实测)[：:，,。；;]\s*"
)
REDUNDANT_NOTE_PATTERNS = (
    re.compile(r"^(?:任务|完成)?(?:进度)?(?:共享|不共享)[。！!]*$"),
    re.compile(r"^(?:五号|五个角色)(?:分别|各自)完成[。！!]*$"),
    re.compile(r"^(?:一号|主控)(?:完成|执行)(?:一次)?即可同步(?:五号|全队|队伍)[。！!]*$"),
    re.compile(r"^(?:击杀|完成|任务)?进度共享[。！!]*$"),
)


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


def _clean_player_note(text: str, *, task_name: str, fivebox_status: str) -> str:
    """Normalize migrated note prose without changing Task Card facts/evidence."""

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    raw_lines = [line for line in text.splitlines() if line.strip()]
    has_unmarked_line = any(DEFERRED_NOTE_OPTIMIZATION_MARKER not in line for line in raw_lines)
    cleaned_lines: list[str] = []
    for raw_line in raw_lines:
        if has_unmarked_line and DEFERRED_NOTE_OPTIMIZATION_MARKER in raw_line:
            continue
        line = raw_line.replace(DEFERRED_NOTE_OPTIMIZATION_MARKER, "").strip()
        if not line:
            continue
        self_label = f"《{task_name}》"
        line = re.sub(rf"^\s*{re.escape(self_label)}(?:的)?[：:]?\s*", "", line)
        line = line.replace(self_label, "本任务")
        previous = None
        while line and line != previous:
            previous = line
            line = PROCESS_PREFIX_RE.sub("", line).strip()
            line = STATUS_PREFIX_RE.sub("", line).strip()
        if not line:
            continue
        if any(pattern.fullmatch(line) for pattern in REDUNDANT_NOTE_PATTERNS):
            continue
        if fivebox_status == "shared" and re.fullmatch(r".+只需击杀一次[。！!]*", line):
            continue
        if fivebox_status == "sequential_loot" and re.fullmatch(r"(?:五号|五个角色)依次拾取[。！!]*", line):
            continue
        if line not in cleaned_lines:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


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
    task_name = str(card.get("identity", {}).get("name_zhcn") or "").strip()
    note = (
        None
        if note_override is None
        else _clean_player_note(
            str(note_override.get("text", "")),
            task_name=task_name,
            fivebox_status=str(fivebox_status),
        )
    )

    pending = fivebox_status == "pending"

    return {
        "task_id": card.get("task_id"),
        "name": card.get("identity", {}).get("name_zhcn"),
        "badge": badge,
        "note": note,
        "note_override_applied": note_override is not None,
        "pending": pending,
    }
