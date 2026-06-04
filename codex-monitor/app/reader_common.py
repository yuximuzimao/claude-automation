"""Shared utilities for session file readers."""

from __future__ import annotations

import json
import re
from typing import TextIO

_PROJECT_PATH_RE = re.compile(r"/claude/([\w][\w-]*)")
_INFERENCE_SKIP = frozenset({"projects", "claude", ".claude"})

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
        return 5
    return 1


def infer_project_from_handle(handle: TextIO, *, max_lines: int = 200) -> str | None:
    """Scan first N lines of an open file for /claude/{project}/ mentions.

    Lines are weighted by event type: tool outputs are skipped (weight 0),
    user messages count 5x, other events count 1x. This prevents directory
    listings in tool results from swamping the true project signal.

    Does NOT seek back — caller must seek(0) to re-read from the start.
    """
    votes: dict[str, int] = {}
    for i, line in enumerate(handle):
        if i >= max_lines:
            break
        weight = _line_weight(line)
        if weight <= 0:
            continue
        for m in _PROJECT_PATH_RE.finditer(line):
            name = m.group(1)
            if name not in _INFERENCE_SKIP:
                votes[name] = votes.get(name, 0) + weight
    if not votes:
        return None
    return max(votes, key=lambda k: votes[k])
