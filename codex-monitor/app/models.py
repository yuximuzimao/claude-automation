"""Shared data models for local usage readers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "TokenUsage":
        data = data or {}
        return cls(
            input_tokens=int(data.get("input_tokens") or 0),
            cached_input_tokens=int(data.get("cached_input_tokens") or 0),
            output_tokens=int(data.get("output_tokens") or 0),
            reasoning_output_tokens=int(data.get("reasoning_output_tokens") or 0),
            total_tokens=int(data.get("total_tokens") or 0),
        )

    def plus(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_output_tokens=self.reasoning_output_tokens
            + other.reasoning_output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    def to_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class RateLimitWindow:
    used_percent: float | None = None
    resets_at: str | int | float | None = None
    window_minutes: int | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "RateLimitWindow | None":
        if not isinstance(data, dict):
            return None
        window_minutes = data.get("window_minutes")
        return cls(
            used_percent=data.get("used_percent"),
            resets_at=data.get("resets_at"),
            window_minutes=int(window_minutes) if window_minutes is not None else None,
        )

    def to_summary(self) -> dict[str, Any]:
        return {
            "used_percent": self.used_percent,
            "resets_at": self.resets_at,
            "window_minutes": self.window_minutes,
        }


@dataclass(frozen=True)
class CodexQuota:
    primary: RateLimitWindow | None
    secondary: RateLimitWindow | None
    timestamp: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "primary": self.primary.to_summary() if self.primary else None,
            "secondary": self.secondary.to_summary() if self.secondary else None,
        }


@dataclass(frozen=True)
class CodexUsageEvent:
    timestamp: str
    cwd: str | None
    usage: TokenUsage
    inferred_project: str | None = None


@dataclass(frozen=True)
class CodexSessionResult:
    path: Path
    cwd: str | None
    last_usage_total: TokenUsage = field(default_factory=TokenUsage)
    latest_total_usage: TokenUsage | None = None
    latest_quota: CodexQuota | None = None
    usage_events: tuple[CodexUsageEvent, ...] = ()
    token_count_events: int = 0
    parse_errors: int = 0

    def to_summary(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "cwd": self.cwd,
            "last_usage_total": self.last_usage_total.to_summary(),
            "latest_total_usage": self.latest_total_usage.to_summary()
            if self.latest_total_usage
            else None,
            "latest_quota": self.latest_quota.to_summary()
            if self.latest_quota
            else None,
            "usage_event_count": len(self.usage_events),
            "token_count_events": self.token_count_events,
            "parse_errors": self.parse_errors,
        }


@dataclass(frozen=True)
class CodexScanResult:
    sessions: tuple[CodexSessionResult, ...]

    @property
    def parse_errors(self) -> int:
        return sum(session.parse_errors for session in self.sessions)

    @property
    def token_count_events(self) -> int:
        return sum(session.token_count_events for session in self.sessions)

    @property
    def last_usage_total(self) -> TokenUsage:
        total = TokenUsage()
        for session in self.sessions:
            total = total.plus(session.last_usage_total)
        return total

    @property
    def usage_events(self) -> tuple[CodexUsageEvent, ...]:
        events: list[CodexUsageEvent] = []
        for session in self.sessions:
            events.extend(session.usage_events)
        return tuple(events)

    def latest_quota(self) -> CodexQuota | None:
        quotas = [
            session.latest_quota
            for session in self.sessions
            if session.latest_quota is not None
        ]
        if not quotas:
            return None
        return max(quotas, key=lambda quota: quota.timestamp)

    def to_summary(self) -> dict[str, Any]:
        latest_quota = self.latest_quota()
        return {
            "session_count": len(self.sessions),
            "token_count_events": self.token_count_events,
            "parse_errors": self.parse_errors,
            "last_usage_total": self.last_usage_total.to_summary(),
            "latest_quota": latest_quota.to_summary() if latest_quota else None,
        }


@dataclass(frozen=True)
class ClaudeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_ephemeral_5m_input_tokens: int = 0
    cache_creation_ephemeral_1h_input_tokens: int = 0

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "ClaudeUsage":
        data = data or {}
        cache_creation = data.get("cache_creation")
        if not isinstance(cache_creation, dict):
            cache_creation = {}
        return cls(
            input_tokens=int(data.get("input_tokens") or 0),
            output_tokens=int(data.get("output_tokens") or 0),
            cache_creation_input_tokens=int(
                data.get("cache_creation_input_tokens") or 0
            ),
            cache_read_input_tokens=int(data.get("cache_read_input_tokens") or 0),
            cache_creation_ephemeral_5m_input_tokens=int(
                cache_creation.get("ephemeral_5m_input_tokens") or 0
            ),
            cache_creation_ephemeral_1h_input_tokens=int(
                cache_creation.get("ephemeral_1h_input_tokens") or 0
            ),
        )

    @property
    def total_estimated_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
        )

    def plus(self, other: "ClaudeUsage") -> "ClaudeUsage":
        return ClaudeUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens
            + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens
            + other.cache_read_input_tokens,
            cache_creation_ephemeral_5m_input_tokens=self.cache_creation_ephemeral_5m_input_tokens
            + other.cache_creation_ephemeral_5m_input_tokens,
            cache_creation_ephemeral_1h_input_tokens=self.cache_creation_ephemeral_1h_input_tokens
            + other.cache_creation_ephemeral_1h_input_tokens,
        )

    def to_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_ephemeral_5m_input_tokens": self.cache_creation_ephemeral_5m_input_tokens,
            "cache_creation_ephemeral_1h_input_tokens": self.cache_creation_ephemeral_1h_input_tokens,
            "total_estimated_tokens": self.total_estimated_tokens,
        }


@dataclass(frozen=True)
class ClaudeUsageEvent:
    timestamp: str
    cwd: str | None
    model: str
    usage: ClaudeUsage
    session_path: str | None = None
    inferred_project: str | None = None


@dataclass(frozen=True)
class ClaudeSessionResult:
    path: Path
    cwd: str | None
    by_model: dict[str, ClaudeUsage] = field(default_factory=dict)
    usage_events: tuple[ClaudeUsageEvent, ...] = ()
    assistant_events: int = 0
    parse_errors: int = 0

    @property
    def total_usage(self) -> ClaudeUsage:
        total = ClaudeUsage()
        for usage in self.by_model.values():
            total = total.plus(usage)
        return total

    def to_summary(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "cwd": self.cwd,
            "assistant_events": self.assistant_events,
            "parse_errors": self.parse_errors,
            "usage_event_count": len(self.usage_events),
            "by_model": {
                model: usage.to_summary()
                for model, usage in sorted(self.by_model.items())
            },
            "total_usage": self.total_usage.to_summary(),
        }


@dataclass(frozen=True)
class ClaudeScanResult:
    sessions: tuple[ClaudeSessionResult, ...]

    @property
    def file_count(self) -> int:
        return len(self.sessions)

    @property
    def assistant_events(self) -> int:
        return sum(session.assistant_events for session in self.sessions)

    @property
    def parse_errors(self) -> int:
        return sum(session.parse_errors for session in self.sessions)

    @property
    def by_model(self) -> dict[str, ClaudeUsage]:
        totals: dict[str, ClaudeUsage] = {}
        for session in self.sessions:
            for model, usage in session.by_model.items():
                totals[model] = totals.get(model, ClaudeUsage()).plus(usage)
        return totals

    @property
    def usage_events(self) -> tuple[ClaudeUsageEvent, ...]:
        events: list[ClaudeUsageEvent] = []
        for session in self.sessions:
            events.extend(session.usage_events)
        return tuple(events)

    @property
    def total_usage(self) -> ClaudeUsage:
        total = ClaudeUsage()
        for usage in self.by_model.values():
            total = total.plus(usage)
        return total

    def to_summary(self) -> dict[str, Any]:
        return {
            "file_count": self.file_count,
            "assistant_events": self.assistant_events,
            "parse_errors": self.parse_errors,
            "by_model": {
                model: usage.to_summary()
                for model, usage in sorted(self.by_model.items())
            },
            "total_usage": self.total_usage.to_summary(),
        }
