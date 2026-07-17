"""Shared utilities for session file readers."""

from __future__ import annotations

import json
import re
from typing import Callable, Iterable, TextIO

_PROJECT_PATH_RE = re.compile(r"/claude/([\w][\w-]*)")
_INFERENCE_SKIP = frozenset({
    "projects",
    "claude",
    ".claude",
    "docs",
    "scripts",
    "reviews",
    "_sandbox",
    "_exports",
})
_DEFAULT_SCAN_LINES = 200
_EXTENDED_SCAN_LINES = 1000

# Codex event subtypes (payload.type) that carry no project signal —
# tool call arguments and outputs often reference many unrelated paths.
_CODEX_NOISE_SUBTYPES = frozenset({
    "function_call_output",  # directory listings, file contents, search results
    "function_call",         # tool invocation parameters
    "token_count",           # billing metadata, no content
})

# Codex subtypes that represent the user's actual task intent.
_CODEX_HIGH_SIGNAL_SUBTYPES = frozenset({"user_message"})

# Claude Code event types that represent user messages.
_CLAUDE_HIGH_SIGNAL_TYPES = frozenset({"user"})


def _line_weight(line: str) -> int:
    """Return vote weight for a JSONL line based on event type.

    Codex format: top-level 'payload' is a dict (may contain 'type').
    Claude Code format: no 'payload' key; top-level 'type' is the event type.
    """
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(obj, dict):
        return 0

    payload = obj.get("payload")
    if isinstance(payload, dict):
        # Codex format
        sub_type = payload.get("type", "")
        if sub_type in _CODEX_NOISE_SUBTYPES:
            return 0
        if sub_type in _CODEX_HIGH_SIGNAL_SUBTYPES:
            return 5
        return 1

    # Claude Code format
    event_type = obj.get("type", "")
    if event_type in _CLAUDE_HIGH_SIGNAL_TYPES:
        return 5 if _claude_has_human_text(obj) else 0
    if event_type == "assistant":
        return 1 if _claude_has_human_text(obj) else 0
    return 0


def _line_project_signals(line: str) -> Iterable[tuple[str, int]]:
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return ()
    if not isinstance(obj, dict):
        return ()

    payload = obj.get("payload")
    if isinstance(payload, dict):
        sub_type = payload.get("type", "")
        if sub_type in _CODEX_NOISE_SUBTYPES:
            return ()
        weight = 5 if sub_type in _CODEX_HIGH_SIGNAL_SUBTYPES else 1
        return ((line, weight),)

    event_type = obj.get("type", "")
    if event_type == "user":
        return tuple((text, 5) for text in _claude_text_parts(obj))
    if event_type == "assistant":
        return tuple((text, 1) for text in _claude_text_parts(obj))
    return ()


def _claude_has_human_text(obj: dict[str, object]) -> bool:
    return any(True for _ in _claude_text_parts(obj))


def _claude_text_parts(obj: dict[str, object]) -> Iterable[str]:
    message = obj.get("message")
    if not isinstance(message, dict):
        return ()
    content = message.get("content")
    if isinstance(content, str):
        return (content,)
    if not isinstance(content, list):
        return ()

    texts: list[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str):
            texts.append(text)
    return tuple(texts)


def infer_project_from_handle(
    handle: TextIO,
    *,
    max_lines: int | None = None,
    early_candidate_is_valid: Callable[[str], bool] | None = None,
) -> str | None:
    """Infer a project from weighted /claude/{project}/ mentions.

    The default path first scans 200 lines for speed. If that window has no
    unique project signal, it continues up to 1000 lines so long planning
    sessions can still be attributed when the real project is created later.
    Callers may reject an invalid early candidate so the scan continues to
    1000 lines. Passing ``max_lines`` keeps a strict one-window limit for
    tests/callers.

    Does NOT seek back — caller must seek(0) to re-read from the start.
    """
    scan_limit = max_lines if max_lines is not None else _EXTENDED_SCAN_LINES
    initial_limit = scan_limit if max_lines is not None else _DEFAULT_SCAN_LINES
    votes: dict[str, int] = {}

    for i, line in enumerate(handle):
        if i >= scan_limit:
            break
        for text, weight in _line_project_signals(line):
            if weight <= 0:
                continue
            for match in _PROJECT_PATH_RE.finditer(text):
                name = match.group(1)
                if name not in _INFERENCE_SKIP:
                    votes[name] = votes.get(name, 0) + weight

        if max_lines is None and i + 1 == initial_limit:
            winner = _unique_project_winner(votes)
            if winner is not None and (
                early_candidate_is_valid is None
                or early_candidate_is_valid(winner)
            ):
                return winner

    return _unique_project_winner(votes)


def _unique_project_winner(votes: dict[str, int]) -> str | None:
    if not votes:
        return None
    top_score = max(votes.values())
    winners = [name for name, score in votes.items() if score == top_score]
    return winners[0] if len(winners) == 1 else None
