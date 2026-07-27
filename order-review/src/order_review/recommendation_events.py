from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .case_repository import default_case_path
from .file_lock import exclusive_file_lock
from .order_identity import same_order_signature_key
from .package_plan import SourceSnapshot
from .recommendations import RecommendationCandidate


EVENT_SCHEMA_VERSION = 1


class RecommendationEventType(StrEnum):
    SHOWN = "shown"
    CONFIRMED_DIRECT = "confirmed_direct"
    CONFIRMED_MODIFIED = "confirmed_modified"
    ABANDONED_UNKNOWN = "abandoned_unknown"


@dataclass(frozen=True)
class RecommendationEventKey:
    application_session_id: str
    order_signature: str
    recommendation_id: str


@dataclass(frozen=True)
class RecommendationEvent:
    event_id: str
    occurred_at: str
    event_type: RecommendationEventType
    key: RecommendationEventKey
    rule_id: str
    match_type: str
    algorithm_version: int
    source_case_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": EVENT_SCHEMA_VERSION,
            "eventId": self.event_id,
            "occurredAt": self.occurred_at,
            "eventType": self.event_type.value,
            "applicationSessionId": self.key.application_session_id,
            "orderSignature": self.key.order_signature,
            "recommendationId": self.key.recommendation_id,
            "ruleId": self.rule_id,
            "matchType": self.match_type,
            "algorithmVersion": self.algorithm_version,
            "sourceCaseIds": list(self.source_case_ids),
        }


@dataclass(frozen=True)
class EventAuditIssue:
    line_number: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineNumber": self.line_number,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class EventAuditReport:
    path: str
    exists: bool
    line_count: int
    event_count: int
    issues: tuple[EventAuditIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def invalid_line_count(self) -> int:
        return len({issue.line_number for issue in self.issues if issue.line_number > 0})

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "exists": self.exists,
            "valid": self.valid,
            "lineCount": self.line_count,
            "eventCount": self.event_count,
            "invalidLineCount": self.invalid_line_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def default_event_path(case_path: str | Path | None = None) -> Path:
    source = Path(case_path) if case_path is not None else default_case_path()
    return source.with_name("recommendation-events.jsonl")


class RecommendationEventStore:
    def __init__(
        self,
        path: str | Path | None = None,
        *,
        case_path: str | Path | None = None,
        session_id: str | None = None,
    ) -> None:
        self.path = (
            Path(path)
            if path is not None
            else default_event_path(case_path)
        )
        self.session_id = session_id or f"session-{uuid4()}"
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self._shown: set[RecommendationEventKey] = set()
        self._outcomes: set[RecommendationEventKey] = set()
        self._load_existing()
        self._close_unfinished_previous_sessions()

    def record_shown(
        self,
        source: SourceSnapshot,
        candidate: RecommendationCandidate,
    ) -> RecommendationEventKey | None:
        key = self._key(source, candidate)
        if key not in self._shown:
            self._append(self._event(RecommendationEventType.SHOWN, key, candidate))
            self._shown.add(key)
        return key if key not in self._outcomes else None

    def record_confirmed(
        self,
        source: SourceSnapshot,
        candidate: RecommendationCandidate,
        *,
        modified: bool,
    ) -> bool:
        key = self._key(source, candidate)
        if key in self._outcomes:
            return False
        event_type = (
            RecommendationEventType.CONFIRMED_MODIFIED
            if modified
            else RecommendationEventType.CONFIRMED_DIRECT
        )
        self._append(self._event(event_type, key, candidate))
        self._shown.add(key)
        self._outcomes.add(key)
        return True

    def record_abandoned_unknown(
        self,
        source: SourceSnapshot,
        candidate: RecommendationCandidate,
    ) -> bool:
        key = self._key(source, candidate)
        if key in self._outcomes:
            return False
        self._append(
            self._event(
                RecommendationEventType.ABANDONED_UNKNOWN,
                key,
                candidate,
            )
        )
        self._shown.add(key)
        self._outcomes.add(key)
        return True

    def _key(
        self,
        source: SourceSnapshot,
        candidate: RecommendationCandidate,
    ) -> RecommendationEventKey:
        signature = same_order_signature_key(source) or f"snapshot:{source.snapshot_id}"
        return RecommendationEventKey(
            self.session_id,
            signature,
            candidate.recommendation_id,
        )

    def _event(
        self,
        event_type: RecommendationEventType,
        key: RecommendationEventKey,
        candidate: RecommendationCandidate,
    ) -> RecommendationEvent:
        return RecommendationEvent(
            event_id=f"event-{uuid4()}",
            occurred_at=_utc_now(),
            event_type=event_type,
            key=key,
            rule_id=candidate.rule_id,
            match_type=candidate.match_type,
            algorithm_version=candidate.algorithm_version,
            source_case_ids=candidate.source_case_ids,
        )

    def _append(self, event: RecommendationEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (
            json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        with exclusive_file_lock(self.lock_path):
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            try:
                view = memoryview(encoded)
                while view:
                    written = os.write(descriptor, view)
                    if written == 0:
                        raise OSError("推荐事件写入返回 0 字节")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def _load_existing(self) -> None:
        for value in read_recommendation_events(self.path):
            try:
                key = RecommendationEventKey(
                    str(value["applicationSessionId"]),
                    str(value["orderSignature"]),
                    str(value["recommendationId"]),
                )
                event_type = RecommendationEventType(str(value["eventType"]))
            except (KeyError, ValueError):
                continue
            if event_type is RecommendationEventType.SHOWN:
                self._shown.add(key)
            else:
                self._outcomes.add(key)

    def _close_unfinished_previous_sessions(self) -> None:
        unfinished = [
            key
            for key in self._shown - self._outcomes
            if key.application_session_id != self.session_id
        ]
        if not unfinished:
            return
        lookup = {
            (
                str(value.get("applicationSessionId", "")),
                str(value.get("orderSignature", "")),
                str(value.get("recommendationId", "")),
            ): value
            for value in read_recommendation_events(self.path)
            if value.get("eventType") == RecommendationEventType.SHOWN.value
        }
        for key in unfinished:
            value = lookup.get(
                (
                    key.application_session_id,
                    key.order_signature,
                    key.recommendation_id,
                )
            )
            if value is None:
                continue
            event = RecommendationEvent(
                event_id=f"event-{uuid4()}",
                occurred_at=_utc_now(),
                event_type=RecommendationEventType.ABANDONED_UNKNOWN,
                key=key,
                rule_id=str(value.get("ruleId", "")),
                match_type=str(value.get("matchType", "")),
                algorithm_version=int(value.get("algorithmVersion", 0)),
                source_case_ids=tuple(value.get("sourceCaseIds", [])),
            )
            self._append(event)
            self._outcomes.add(key)


def read_recommendation_events(path: str | Path) -> list[dict[str, Any]]:
    values, _, _ = _parse_recommendation_events(path)
    return values


def audit_recommendation_events(path: str | Path) -> EventAuditReport:
    values, issues, line_count = _parse_recommendation_events(path)
    event_path = Path(path)
    return EventAuditReport(
        path=str(event_path),
        exists=event_path.exists(),
        line_count=line_count,
        event_count=len(values),
        issues=tuple(issues),
    )


def _parse_recommendation_events(
    path: str | Path,
) -> tuple[list[dict[str, Any]], list[EventAuditIssue], int]:
    event_path = Path(path)
    if not event_path.exists():
        return [], [], 0
    try:
        lines = event_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return (
            [],
            [
                EventAuditIssue(
                    0,
                    "event_file_unreadable",
                    f"推荐事件文件无法读取：{exc}",
                )
            ],
            0,
        )
    values: list[dict[str, Any]] = []
    issues: list[EventAuditIssue] = []
    event_ids: set[str] = set()
    required_strings = (
        "eventId",
        "occurredAt",
        "eventType",
        "applicationSessionId",
        "orderSignature",
        "recommendationId",
        "ruleId",
        "matchType",
    )
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(
                EventAuditIssue(
                    line_number,
                    "event_json_invalid",
                    f"事件行不是有效 JSON：{exc.msg}",
                )
            )
            continue
        if not isinstance(value, dict):
            issues.append(
                EventAuditIssue(
                    line_number,
                    "event_not_object",
                    "事件行必须是对象",
                )
            )
            continue
        line_issues: list[EventAuditIssue] = []
        if value.get("schemaVersion") != EVENT_SCHEMA_VERSION:
            line_issues.append(
                EventAuditIssue(
                    line_number,
                    "event_schema_unsupported",
                    f"不支持的 schemaVersion：{value.get('schemaVersion')!r}",
                )
            )
        for field_name in required_strings:
            field_value = value.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                line_issues.append(
                    EventAuditIssue(
                        line_number,
                        "event_field_invalid",
                        f"{field_name} 必须是非空字符串",
                    )
                )
        try:
            RecommendationEventType(str(value.get("eventType", "")))
        except ValueError:
            line_issues.append(
                EventAuditIssue(
                    line_number,
                    "event_type_invalid",
                    f"未知事件类型：{value.get('eventType')!r}",
                )
            )
        algorithm_version = value.get("algorithmVersion")
        if not isinstance(algorithm_version, int) or algorithm_version < 1:
            line_issues.append(
                EventAuditIssue(
                    line_number,
                    "event_algorithm_version_invalid",
                    "algorithmVersion 必须是大于 0 的整数",
                )
            )
        source_case_ids = value.get("sourceCaseIds")
        if not isinstance(source_case_ids, list) or not all(
            isinstance(item, str) and item for item in source_case_ids
        ):
            line_issues.append(
                EventAuditIssue(
                    line_number,
                    "event_source_cases_invalid",
                    "sourceCaseIds 必须是字符串数组",
                )
            )
        event_id = value.get("eventId")
        if isinstance(event_id, str) and event_id in event_ids:
            line_issues.append(
                EventAuditIssue(
                    line_number,
                    "event_id_duplicate",
                    f"eventId 重复：{event_id}",
                )
            )
        if line_issues:
            issues.extend(line_issues)
            continue
        event_ids.add(str(event_id))
        values.append(value)
    return values, issues, len(lines)


def count_event_types(values: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {event_type.value: 0 for event_type in RecommendationEventType}
    for value in values:
        event_type = value.get("eventType")
        if event_type in counts:
            counts[str(event_type)] += 1
    return counts


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
