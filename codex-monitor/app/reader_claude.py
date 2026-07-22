"""Reader for local Claude Code project JSONL files."""

from __future__ import annotations

import dataclasses
import json
import re
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
        inferred_project = infer_project_from_handle(
            handle,
            early_candidate_is_valid=_project_metadata_exists,
        )
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
                tool_project = _tool_input_project(message)
                usage_events.append(
                    ClaudeUsageEvent(
                        timestamp=timestamp,
                        cwd=_read_cwd(event),
                        model=model,
                        usage=usage,
                        session_path=str(path),
                        inferred_project=tool_project or inferred_project,
                    )
                )

    usage_events = _backfill_workspace_root_events(usage_events)

    return ClaudeSessionResult(
        path=path,
        cwd=cwd,
        by_model=by_model,
        usage_events=tuple(usage_events),
        assistant_events=assistant_events,
        parse_errors=parse_errors,
    )


_PROJECT_PATH_RE = re.compile(r"/claude/([\w][\w-]*)")
_LOCAL_FILE_TOOL_NAMES = frozenset({
    "Bash",
    "Edit",
    "Glob",
    "Grep",
    "NotebookEdit",
    "Read",
    "Write",
})


def _tool_input_project(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if not isinstance(content, list):
        return None
    projects: set[str] = set()
    for block in content:
        if (
            not isinstance(block, dict)
            or block.get("type") != "tool_use"
            or block.get("name") not in _LOCAL_FILE_TOOL_NAMES
        ):
            continue
        try:
            value = json.dumps(block.get("input"), ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        for project in _PROJECT_PATH_RE.findall(value):
            if _project_metadata_exists(project):
                projects.add(project)
    return next(iter(projects)) if len(projects) == 1 else None


def _backfill_workspace_root_events(
    events: list[ClaudeUsageEvent],
) -> list[ClaudeUsageEvent]:
    confirmed: list[tuple[int, str]] = []
    for index, event in enumerate(events):
        project = _project_from_cwd(event.cwd)
        if project is not None:
            confirmed.append((index, project))
    projects = {project for _, project in confirmed}
    if len(projects) != 1:
        return events

    project = next(iter(projects))
    first_index = confirmed[0][0]
    last_index = confirmed[-1][0]
    for index in range(first_index, last_index + 1):
        event = events[index]
        if (
            _is_workspace_root(event.cwd)
            and not _project_metadata_exists(event.inferred_project)
        ):
            events[index] = dataclasses.replace(event, inferred_project=project)
    return events


def _project_from_cwd(cwd: str | None) -> str | None:
    if not isinstance(cwd, str):
        return None
    root = Path.home() / "claude"
    try:
        relative = Path(cwd).relative_to(root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    project = relative.parts[0]
    return project if _project_metadata_exists(project) else None


def _is_workspace_root(cwd: str | None) -> bool:
    return cwd in {str(Path.home()), str(Path.home() / "claude")}


def _project_metadata_exists(project: object) -> bool:
    return isinstance(project, str) and (
        Path.home() / "claude" / project / "CLAUDE.md"
    ).is_file()


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
