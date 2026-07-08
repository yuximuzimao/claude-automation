"""Reader for local Claude Code project JSONL files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.reader_common import infer_project_from_handle

from app.models import (
    ClaudeScanResult,
    ClaudeSessionResult,
    ClaudeUsage,
    ClaudeUsageEvent,
)


def read_claude_session_file(path: Path) -> ClaudeSessionResult:
    cwd: str | None = None
    by_model: dict[str, ClaudeUsage] = {}
    usage_events: list[ClaudeUsageEvent] = []
    seen_message_ids: set[str] = set()
    assistant_events = 0
    parse_errors = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        inferred_project = infer_project_from_handle(handle)
        handle.seek(0)
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            if not isinstance(event, dict) or event.get("type") != "assistant":
                continue

            message = event.get("message")
            if not isinstance(message, dict):
                continue

            usage_data = message.get("usage")
            if not isinstance(usage_data, dict):
                continue

            message_id = _read_message_id(message)
            if message_id is not None:
                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)

            assistant_events += 1
            cwd = _read_cwd(event) or cwd
            model = _read_model(message)
            usage = ClaudeUsage.from_mapping(usage_data)
            by_model[model] = by_model.get(model, ClaudeUsage()).plus(usage)
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str):
                usage_events.append(
                    ClaudeUsageEvent(
                        timestamp=timestamp,
                        cwd=_read_cwd(event),
                        model=model,
                        usage=usage,
                        session_path=str(path),
                        inferred_project=inferred_project,
                    )
                )

    return ClaudeSessionResult(
        path=path,
        cwd=cwd,
        by_model=by_model,
        usage_events=tuple(usage_events),
        assistant_events=assistant_events,
        parse_errors=parse_errors,
    )


def read_claude_projects(
    root: Path,
    *,
    modified_since: float | int | None = None,
    max_files: int | None = None,
) -> ClaudeScanResult:
    files = list(_iter_claude_files(root, modified_since=modified_since))
    if max_files is not None:
        files = files[:max_files]
    return ClaudeScanResult(
        sessions=tuple(read_claude_session_file(path) for path in files)
    )


_SKIP_PROJECT_DIR_PATTERNS = (
    "observer-sessions",   # claude-mem observer generates thousands of system sessions
)


def _iter_claude_files(
    root: Path,
    *,
    modified_since: float | int | None = None,
) -> Iterable[Path]:
    if root.is_file():
        if _mtime_matches(root, modified_since):
            yield root
        return
    if not root.exists():
        return
    # Collect with mtime so we can sort most-recent-first.
    # This ensures the max_files budget covers recently-active projects
    # rather than alphabetically-first project directories.
    matching: list[tuple[float, Path]] = []
    for path in root.glob("**/*.jsonl"):
        if any(pat in part for part in path.parts for pat in _SKIP_PROJECT_DIR_PATTERNS):
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if modified_since is None or mtime >= modified_since:
            matching.append((mtime, path))
    matching.sort(reverse=True)
    for _, path in matching:
        yield path


def _mtime_matches(path: Path, modified_since: float | int | None) -> bool:
    if modified_since is None:
        return True
    return path.stat().st_mtime >= modified_since


def _read_cwd(event: dict[str, Any]) -> str | None:
    cwd = event.get("cwd")
    return cwd if isinstance(cwd, str) else None


def _read_model(message: dict[str, Any]) -> str:
    model = message.get("model")
    return model if isinstance(model, str) and model else "<missing>"


def _read_message_id(message: dict[str, Any]) -> str | None:
    message_id = message.get("id")
    return message_id if isinstance(message_id, str) and message_id else None
