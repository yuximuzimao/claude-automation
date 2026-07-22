"""Reader for local Codex session JSONL files."""

from __future__ import annotations

import dataclasses
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.models import (
    CodexQuota,
    CodexScanResult,
    CodexSessionResult,
    CodexUsageEvent,
    RateLimitWindow,
    TokenUsage,
)


_PROJECT_PATH_RE = re.compile(r"/claude/([\w][\w-]*)")
_WORKDIR_RE = re.compile(
    r'(?:["\']?workdir["\']?)\s*:\s*["\']([^"\']+)["\']'
)
_WORKTREE_PAIR_RE = re.compile(r"/worktrees/claude/([^/]+)/([^/]+)")
_PROJECT_METADATA_LEGACY_PATH_RE = re.compile(
    r"^项目历史路径[：:]\s*(/[^\r\n]+?)\s*$",
    re.MULTILINE,
)
_TURN_BOUNDARY_SUBTYPE = "user_message"
_USER_PROJECT_SIGNAL_WEIGHT = 20
_TOOL_ARGUMENT_SIGNAL_WEIGHT = 40
_TOOL_WORKDIR_SIGNAL_WEIGHT = 100
_LOCAL_PATH_TOOL_NAMES = frozenset({
    "apply_patch",
    "exec",
    "exec_command",
    "view_image",
})
_NEAT_EXACT_PROMPTS = frozenset({
    "/neat",
    "neat",
    "/sync",
    "同步一下",
    "整理一下",
    "整理文档",
    "收尾",
    "这个阶段做完了",
})


def read_session_file(
    path: Path,
    *,
    inherited_project: str | None = None,
    project_aliases: Mapping[str, str] | None = None,
) -> CodexSessionResult:
    cwd: str | None = None
    last_usage_total = TokenUsage()
    latest_total_usage: TokenUsage | None = None
    latest_quota: CodexQuota | None = None
    usage_events: list[CodexUsageEvent] = []
    token_count_events = 0
    parse_errors = 0
    active_project = (
        inherited_project
        if inherited_project and _project_metadata_exists(inherited_project)
        else None
    )
    turn_votes: dict[str, int] = defaultdict(int)
    turn_usage: list[tuple[str, str | None, TokenUsage]] = []
    turn_is_neat_summary = False
    neat_summary_projects: set[str] = set()
    explicit_turn_projects: set[str] = set()
    neat_backfillable_event_indexes: list[int] = []

    def flush_turn() -> None:
        nonlocal active_project, turn_is_neat_summary
        if turn_votes:
            top_score = max(turn_votes.values())
            winners = [
                project for project, score in turn_votes.items() if score == top_score
            ]
            turn_project = winners[0] if len(winners) == 1 else None
        else:
            turn_project = active_project

        has_explicit_turn_project = bool(turn_votes) and turn_project is not None
        if has_explicit_turn_project:
            explicit_turn_projects.add(turn_project)
        for timestamp, event_cwd, usage in turn_usage:
            event_index = len(usage_events)
            usage_events.append(
                CodexUsageEvent(
                    timestamp=timestamp,
                    cwd=event_cwd,
                    usage=usage,
                    inferred_project=turn_project,
                )
            )
            if not has_explicit_turn_project:
                neat_backfillable_event_indexes.append(event_index)
        if turn_project is not None:
            active_project = turn_project
            if turn_is_neat_summary:
                neat_summary_projects.add(turn_project)
        turn_votes.clear()
        turn_usage.clear()
        turn_is_neat_summary = False

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            if not isinstance(event, dict):
                continue

            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue

            if event.get("type") == "session_meta":
                cwd = _read_cwd(payload) or cwd
                cwd_project = _known_project_from_text(cwd, project_aliases)
                if cwd_project is not None:
                    active_project = cwd_project
                continue

            if payload.get("type") == _TURN_BOUNDARY_SUBTYPE:
                flush_turn()
                turn_is_neat_summary = _is_neat_summary_prompt(
                    payload.get("message")
                )

            for project, weight in _project_evidence(payload, project_aliases):
                turn_votes[project] += weight

            if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue

            token_count_events += 1
            timestamp = event.get("timestamp")
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}

            last_usage = TokenUsage.from_mapping(info.get("last_token_usage"))
            last_usage_total = last_usage_total.plus(last_usage)
            latest_total_usage = TokenUsage.from_mapping(info.get("total_token_usage"))
            if isinstance(timestamp, str):
                turn_usage.append((timestamp, cwd, last_usage))

            quota = _read_quota(payload, timestamp)
            if quota is not None and _quota_has_displayable_percent(quota):
                latest_quota = quota

    flush_turn()

    if (
        len(neat_summary_projects) == 1
        and explicit_turn_projects == neat_summary_projects
    ):
        summary_project = next(iter(neat_summary_projects))
        for event_index in neat_backfillable_event_indexes:
            usage_events[event_index] = dataclasses.replace(
                usage_events[event_index],
                inferred_project=summary_project,
            )

    return CodexSessionResult(
        path=path,
        cwd=cwd,
        last_usage_total=last_usage_total,
        latest_total_usage=latest_total_usage,
        latest_quota=latest_quota,
        usage_events=tuple(usage_events),
        token_count_events=token_count_events,
        parse_errors=parse_errors,
    )


def read_codex_sessions(root: Path) -> CodexScanResult:
    paths = tuple(_iter_session_files(root))
    project_aliases = _collect_project_aliases(paths)
    base_results = {
        path: read_session_file(path, project_aliases=project_aliases) for path in paths
    }
    metadata = {path: _read_session_metadata(path) for path in paths}
    path_by_id = {
        str(meta["id"]): path
        for path, meta in metadata.items()
        if isinstance(meta.get("id"), str)
    }
    resolved: dict[Path, CodexSessionResult] = {}

    def resolve(path: Path, resolving: frozenset[Path] = frozenset()) -> CodexSessionResult:
        if path in resolved:
            return resolved[path]
        if path in resolving:
            return base_results[path]

        meta = metadata[path]
        parent_id = meta.get("parent_thread_id")
        parent_path = path_by_id.get(parent_id) if isinstance(parent_id, str) else None
        inherited_project = None
        if parent_path is not None:
            parent = resolve(parent_path, resolving | {path})
            inherited_project = _project_at_timestamp(parent, meta.get("timestamp"))

        result = (
            read_session_file(
                path,
                inherited_project=inherited_project,
                project_aliases=project_aliases,
            )
            if inherited_project is not None
            else base_results[path]
        )
        resolved[path] = result
        return result

    return CodexScanResult(sessions=tuple(resolve(path) for path in paths))


def _project_evidence(
    payload: dict[str, Any],
    project_aliases: Mapping[str, str] | None,
) -> tuple[tuple[str, int], ...]:
    subtype = payload.get("type")
    if subtype == "user_message":
        return tuple(
            (project, _USER_PROJECT_SIGNAL_WEIGHT)
            for project in _known_projects_from_value(
                payload.get("message"), project_aliases
            )
        )

    if subtype not in {"function_call", "custom_tool_call"}:
        return ()

    evidence: list[tuple[str, int]] = []
    for workdir in _tool_workdirs(payload):
        project = _known_project_from_workdir(workdir, project_aliases)
        if project is not None:
            evidence.append((project, _TOOL_WORKDIR_SIGNAL_WEIGHT))
    tool_name = payload.get("name") or payload.get("tool_name")
    if tool_name in _LOCAL_PATH_TOOL_NAMES:
        for project in _tool_argument_projects(payload, project_aliases):
            evidence.append((project, _TOOL_ARGUMENT_SIGNAL_WEIGHT))
    return tuple(evidence)


def _is_neat_summary_prompt(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    if normalized in _NEAT_EXACT_PROMPTS:
        return True
    return normalized.startswith(("/neat ", "/sync "))


def _known_projects_from_value(
    value: Any,
    project_aliases: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    projects: list[str] = []
    for candidate in _PROJECT_PATH_RE.findall(value):
        project = candidate if _project_metadata_exists(candidate) else None
        if project is None and project_aliases is not None:
            project = project_aliases.get(candidate)
        if project is not None and project not in projects:
            projects.append(project)
    if project_aliases is not None:
        for alias, project in project_aliases.items():
            if "/" not in alias or project in projects:
                continue
            if _contains_path(value, alias):
                projects.append(project)
    return tuple(projects)


def _known_project_from_text(
    value: str | None,
    project_aliases: Mapping[str, str] | None = None,
) -> str | None:
    projects = _known_projects_from_value(value, project_aliases)
    return projects[0] if len(projects) == 1 else None


def _known_project_from_workdir(
    value: str,
    project_aliases: Mapping[str, str] | None = None,
) -> str | None:
    direct_project = _known_project_from_text(value, project_aliases)
    if direct_project is not None:
        return direct_project

    if project_aliases is not None:
        normalized = value.rstrip("/")
        for alias, project in project_aliases.items():
            if "/" not in alias:
                continue
            alias_root = alias.rstrip("/")
            if normalized == alias_root or normalized.startswith(alias_root + "/"):
                return project

    # Superpowers/CodexPro worktrees keep the stable project slug below the
    # temporary task directory:
    # .../worktrees/claude/<temporary-task>/<real-project>/...
    parts = Path(value).parts
    for index in range(len(parts) - 1):
        if parts[index : index + 2] != ("worktrees", "claude"):
            continue
        for candidate in reversed(parts[index + 2 :]):
            if _project_metadata_exists(candidate):
                return candidate
    return None


def _tool_workdirs(payload: dict[str, Any]) -> tuple[str, ...]:
    workdirs: list[str] = []
    arguments = payload.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (json.JSONDecodeError, ValueError):
            arguments = None
    if isinstance(arguments, dict):
        workdir = arguments.get("workdir")
        if isinstance(workdir, str):
            workdirs.append(workdir)

    tool_input = payload.get("input")
    if isinstance(tool_input, str):
        workdirs.extend(_WORKDIR_RE.findall(tool_input))
    return tuple(workdirs)


def _tool_argument_projects(
    payload: dict[str, Any],
    project_aliases: Mapping[str, str] | None,
) -> tuple[str, ...]:
    projects: list[str] = []
    for field in ("arguments", "input"):
        value = payload.get(field)
        if not isinstance(value, str):
            try:
                value = json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                continue
        for project in _known_projects_from_value(value, project_aliases):
            if project not in projects:
                projects.append(project)
    return tuple(projects)


def _collect_project_aliases(paths: Iterable[Path]) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for alias, project in _declared_project_aliases().items():
        candidates[alias].add(project)
    for path in paths:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    payload = event.get("payload")
                    if not isinstance(payload, dict):
                        continue
                    for workdir in _tool_workdirs(payload):
                        match = _WORKTREE_PAIR_RE.search(workdir)
                        if match is None:
                            continue
                        alias, project = match.groups()
                        if _project_metadata_exists(project):
                            candidates[alias].add(project)
        except OSError:
            continue
    return {
        alias: next(iter(projects))
        for alias, projects in candidates.items()
        if len(projects) == 1
    }


def _declared_project_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    projects_root = Path.home() / "claude"
    for metadata_path in projects_root.glob("*/CLAUDE.md"):
        project = metadata_path.parent.name
        try:
            text = metadata_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _PROJECT_METADATA_LEGACY_PATH_RE.finditer(text):
            alias = match.group(1).strip().rstrip("/")
            existing = aliases.get(alias)
            if existing is None:
                aliases[alias] = project
            elif existing != project:
                aliases.pop(alias, None)
    return aliases


def _contains_path(value: str, path: str) -> bool:
    pattern = re.compile(
        rf"(?<![\w.-]){re.escape(path.rstrip('/'))}(?=$|[/\s\"'`,;:)\]])"
    )
    return pattern.search(value) is not None


def _read_session_metadata(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("type") != "session_meta":
                    continue
                payload = event.get("payload")
                return payload if isinstance(payload, dict) else {}
    except OSError:
        pass
    return {}


def _project_at_timestamp(
    session: CodexSessionResult,
    timestamp: Any,
) -> str | None:
    cutoff = _parse_timestamp(timestamp)
    candidates: list[tuple[datetime, str]] = []
    for event in session.usage_events:
        if event.inferred_project is None:
            continue
        event_time = _parse_timestamp(event.timestamp)
        if event_time is None:
            continue
        if cutoff is None or event_time <= cutoff:
            candidates.append((event_time, event.inferred_project))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _project_metadata_exists(project: str) -> bool:
    return (Path.home() / "claude" / project / "CLAUDE.md").is_file()


def _iter_session_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    if not root.exists():
        return
    yield from sorted(root.glob("**/rollout-*.jsonl"))


def _read_cwd(payload: dict[str, Any]) -> str | None:
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else None


def _read_quota(payload: dict[str, Any], timestamp: Any) -> CodexQuota | None:
    rate_limits = payload.get("rate_limits")
    if not isinstance(rate_limits, dict) or not isinstance(timestamp, str):
        return None
    return CodexQuota(
        primary=RateLimitWindow.from_mapping(rate_limits.get("primary")),
        secondary=RateLimitWindow.from_mapping(rate_limits.get("secondary")),
        timestamp=timestamp,
    )


def _quota_has_displayable_percent(quota: CodexQuota) -> bool:
    return _window_has_percent(quota.primary) or _window_has_percent(quota.secondary)


def _window_has_percent(window: RateLimitWindow | None) -> bool:
    return window is not None and window.used_percent is not None
