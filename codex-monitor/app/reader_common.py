"""Shared utilities for session file readers."""

from __future__ import annotations

import re
from typing import TextIO

_PROJECT_PATH_RE = re.compile(r"/claude/([\w][\w-]*)")
_INFERENCE_SKIP = frozenset({"projects", "claude", ".claude"})


def infer_project_from_handle(handle: TextIO, *, max_lines: int = 100) -> str | None:
    """Scan first N lines of an open file for /claude/{project}/ mentions.

    Does NOT seek back — caller must seek(0) to re-read from the start.
    """
    votes: dict[str, int] = {}
    for i, line in enumerate(handle):
        if i >= max_lines:
            break
        for m in _PROJECT_PATH_RE.finditer(line):
            name = m.group(1)
            if name not in _INFERENCE_SKIP:
                votes[name] = votes.get(name, 0) + 1
    if not votes:
        return None
    winner = max(votes, key=lambda k: votes[k])
    return winner if votes[winner] >= 1 else None
