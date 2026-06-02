"""Reader for local Codex session JSONL files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.reader_common import infer_project_from_handle

from app.models import (
    CodexQuota,
    CodexScanResult,
    CodexSessionResult,
    CodexUsageEvent,
    RateLimitWindow,
    TokenUsage,
)


def read_session_file(path: Path) -> CodexSessionResult:
    cwd: str | None = None
    last_usage_total = TokenUsage()
    latest_total_usage: TokenUsage | None = None
    latest_quota: CodexQuota | None = None
    usage_events: list[CodexUsageEvent] = []
    token_count_events = 0
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

            if not isinstance(event, dict):
                continue

            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue

            if event.get("type") == "session_meta":
                cwd = _read_cwd(payload) or cwd
                continue

            if event.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue

            token_count_events += 1
            timestamp = event.get("timestamp")
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}

            last_usage = TokenUsage.from_mapping(info.get("last_token_usage"))
            last_usage_total = last_usage_total.plus(last_usage)
            latest_total_usage = TokenUsage.from_mapping(info.get("total_token_usage"))
            if isinstance(timestamp, str):
                usage_events.append(
                    CodexUsageEvent(
                        timestamp=timestamp,
                        cwd=cwd,
                        usage=last_usage,
                        inferred_project=inferred_project,
                    )
                )

            quota = _read_quota(payload, timestamp)
            if quota is not None:
                latest_quota = quota

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
    session_results = tuple(read_session_file(path) for path in _iter_session_files(root))
    return CodexScanResult(sessions=session_results)


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
