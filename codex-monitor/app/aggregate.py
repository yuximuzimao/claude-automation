"""Aggregate Codex and Claude reader outputs for UI consumption."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.models import ClaudeScanResult, CodexQuota, CodexScanResult


OTHER_PROJECT = "other"
OTHER_PROJECT_DISPLAY_NAME = "其他"


@dataclass(frozen=True)
class TokenTotals:
    codex_tokens: int = 0
    claude_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.codex_tokens + self.claude_tokens

    def to_summary(self) -> dict[str, int]:
        return {
            "codex_tokens": self.codex_tokens,
            "claude_tokens": self.claude_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ProjectIdentity:
    project: str
    display_name: str


@dataclass(frozen=True)
class ProjectTotal:
    project: str
    display_name: str | None = None
    codex_tokens: int = 0
    claude_tokens: int = 0
    today_codex_tokens: int = 0
    today_claude_tokens: int = 0
    month_percent: float = 0.0
    sample_cwds: tuple[str, ...] = ()

    @property
    def total_tokens(self) -> int:
        return self.codex_tokens + self.claude_tokens

    @property
    def today_tokens(self) -> int:
        return self.today_codex_tokens + self.today_claude_tokens

    def to_summary(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "display_name": self.display_name or project_display_name(self.project),
            "codex_tokens": self.codex_tokens,
            "claude_tokens": self.claude_tokens,
            "total_tokens": self.total_tokens,
            "today_tokens": self.today_tokens,
            "today_codex_tokens": self.today_codex_tokens,
            "today_claude_tokens": self.today_claude_tokens,
            "month_percent": self.month_percent,
            "sample_cwds": list(self.sample_cwds),
        }


@dataclass(frozen=True)
class UsageAggregate:
    today: TokenTotals
    month: TokenTotals
    top_projects: tuple[ProjectTotal, ...]
    quota: CodexQuota | None
    last_updated: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "today": self.today.to_summary(),
            "month": self.month.to_summary(),
            "top_projects": [project.to_summary() for project in self.top_projects],
            "quota": self.quota.to_summary() if self.quota else None,
            "last_updated": self.last_updated,
        }


def aggregate_usage(
    codex: CodexScanResult,
    claude: ClaudeScanResult,
    *,
    now: str | datetime | None = None,
    month_start: str | datetime | None = None,
    timezone: str = "Asia/Shanghai",
    top_n: int = 5,
) -> UsageAggregate:
    tz = ZoneInfo(timezone)
    now_dt = _parse_datetime(now, tz) if now is not None else datetime.now(tz)
    today_key = now_dt.date().isoformat()

    if month_start is not None:
        month_start_dt: datetime | None = _parse_datetime(month_start, tz)
        month_key: str | None = None
    else:
        month_start_dt = None
        month_key = now_dt.strftime("%Y-%m")

    def _in_month(event_dt: datetime) -> bool:
        if month_start_dt is not None:
            return event_dt >= month_start_dt
        return event_dt.strftime("%Y-%m") == month_key

    today = TokenTotals()
    month = TokenTotals()
    by_project: dict[str, ProjectTotal] = {}
    identity_cache: dict[tuple[str | None, str | None, str | None], ProjectIdentity] = {}

    for event in codex.usage_events:
        event_dt = _parse_datetime(event.timestamp, tz)
        tokens = event.usage.total_tokens
        is_today = event_dt.date().isoformat() == today_key
        if is_today:
            today = TokenTotals(
                codex_tokens=today.codex_tokens + tokens,
                claude_tokens=today.claude_tokens,
            )
        if _in_month(event_dt):
            month = TokenTotals(
                codex_tokens=month.codex_tokens + tokens,
                claude_tokens=month.claude_tokens,
            )
            if tokens <= 0:
                continue
            identity = _cached_project_identity(
                event.cwd, identity_cache, inferred_project=event.inferred_project
            )
            by_project[identity.project] = _add_project_tokens(
                by_project.get(identity.project, ProjectTotal(project=identity.project)),
                display_name=identity.display_name,
                codex_tokens=tokens,
                today_codex_tokens=tokens if is_today else 0,
                cwd=event.cwd,
            )

    for event in claude.usage_events:
        event_dt = _parse_datetime(event.timestamp, tz)
        tokens = event.usage.total_estimated_tokens
        is_today = event_dt.date().isoformat() == today_key
        if is_today:
            today = TokenTotals(
                codex_tokens=today.codex_tokens,
                claude_tokens=today.claude_tokens + tokens,
            )
        if _in_month(event_dt):
            month = TokenTotals(
                codex_tokens=month.codex_tokens,
                claude_tokens=month.claude_tokens + tokens,
            )
            if tokens <= 0:
                continue
            identity = _cached_project_identity(
                event.cwd,
                identity_cache,
                session_path=event.session_path,
                inferred_project=event.inferred_project,
            )
            by_project[identity.project] = _add_project_tokens(
                by_project.get(identity.project, ProjectTotal(project=identity.project)),
                display_name=identity.display_name,
                claude_tokens=tokens,
                today_claude_tokens=tokens if is_today else 0,
                cwd=event.cwd,
            )

    top_projects = tuple(
        _with_percent(project, month.total_tokens)
        for project in
        sorted(
            [
                project
                for project in by_project.values()
                if project.total_tokens > 0
            ],
            key=lambda project: (-project.total_tokens, project.project),
        )[:top_n]
    )
    return UsageAggregate(
        today=today,
        month=month,
        top_projects=top_projects,
        quota=codex.latest_quota(),
        last_updated=now_dt.isoformat(),
    )


def _parse_datetime(value: str | datetime, tz: ZoneInfo) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _project_identity(
    cwd: str | None,
    session_path: str | None = None,
    inferred_project: str | None = None,
) -> ProjectIdentity:
    if cwd:
        path = Path(cwd)
        for candidate in (path, *path.parents):
            display_name = _read_project_display_name(candidate / "CLAUDE.md")
            if display_name:
                return ProjectIdentity(candidate.name, display_name)

    # session_path fallback: extract project name from Claude session file path
    if session_path and cwd:
        project_name = _project_from_session_path(session_path, cwd)
        if project_name:
            project_dir = Path(cwd) / project_name
            display_name = _read_project_display_name(project_dir / "CLAUDE.md")
            return ProjectIdentity(project_name, display_name or project_display_name(project_name))

    # inferred_project fallback: derived from /claude/{project}/ path patterns in session content.
    # Require CLAUDE.md to exist — filters out shared dirs like docs/, scripts/, reviews/.
    if inferred_project:
        project_claude_md = Path.home() / "claude" / inferred_project / "CLAUDE.md"
        if project_claude_md.exists():
            display_name = _read_project_display_name(project_claude_md)
            return ProjectIdentity(
                inferred_project, display_name or project_display_name(inferred_project)
            )

    return ProjectIdentity(OTHER_PROJECT, OTHER_PROJECT_DISPLAY_NAME)


def _canonical_cwd(cwd: str) -> str:
    """Normalize cwd to use the real home dir from the password database.

    On some systems $HOME (e.g. /Users/chat) differs from the pwd
    home path (e.g. /Users/chat) that Claude Code uses when encoding session
    directory names.  We try both so the prefix comparison succeeds.
    """
    try:
        import os, pwd as _pwd
        env_home = os.path.expanduser("~")
        pwd_home = _pwd.getpwuid(os.getuid()).pw_dir
        if env_home != pwd_home and cwd.startswith(env_home):
            return pwd_home + cwd[len(env_home):]
    except Exception:
        pass
    return cwd


def _project_from_session_path(session_path: str, cwd: str) -> str | None:
    """Extract project name by decoding the session directory vs cwd.

    Claude stores sessions under ~/.claude/projects/-Users-foo-bar-projectname/
    where the directory name is the working-directory path with / replaced by -.
    """
    try:
        parts = Path(session_path).parts
        for i, part in enumerate(parts):
            if part == "projects" and i > 0 and parts[i - 1] == ".claude" and i + 1 < len(parts):
                encoded_dir = parts[i + 1]
                # Try both raw cwd and canonicalized cwd (handles $HOME alias vs pwd home)
                for candidate_cwd in dict.fromkeys([cwd, _canonical_cwd(cwd)]):
                    cwd_encoded = Path(candidate_cwd).as_posix().replace("/", "-")
                    prefix = cwd_encoded + "-"
                    if encoded_dir.startswith(prefix):
                        project_name = encoded_dir[len(prefix):]
                        if project_name:
                            return project_name
                break
        return None
    except Exception:
        return None


def _cached_project_identity(
    cwd: str | None,
    cache: dict[tuple[str | None, str | None, str | None], ProjectIdentity],
    session_path: str | None = None,
    inferred_project: str | None = None,
) -> ProjectIdentity:
    key = (cwd, session_path, inferred_project)
    if key not in cache:
        cache[key] = _project_identity(cwd, session_path, inferred_project)
    return cache[key]


def _read_project_display_name(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as file:
            lines = [line.rstrip("\n") for _, line in zip(range(20), file)]
    except OSError:
        return None
    for line in lines:
        stripped = line.strip()
        for marker in ("项目中文名：", "项目中文名:"):
            if stripped.startswith(marker):
                name = stripped[len(marker):].strip()
                return name or None
    return None


def _add_project_tokens(
    project: ProjectTotal,
    *,
    display_name: str,
    codex_tokens: int = 0,
    claude_tokens: int = 0,
    today_codex_tokens: int = 0,
    today_claude_tokens: int = 0,
    cwd: str | None = None,
) -> ProjectTotal:
    return ProjectTotal(
        project=project.project,
        display_name=project.display_name or display_name,
        codex_tokens=project.codex_tokens + codex_tokens,
        claude_tokens=project.claude_tokens + claude_tokens,
        today_codex_tokens=project.today_codex_tokens + today_codex_tokens,
        today_claude_tokens=project.today_claude_tokens + today_claude_tokens,
        month_percent=project.month_percent,
        sample_cwds=_add_sample_cwd(project.sample_cwds, cwd),
    )


def _add_sample_cwd(samples: tuple[str, ...], cwd: str | None) -> tuple[str, ...]:
    if not cwd or cwd in samples:
        return samples
    if len(samples) >= 3:
        return samples
    return (*samples, cwd)


def _with_percent(project: ProjectTotal, total_tokens: int) -> ProjectTotal:
    return ProjectTotal(
        project=project.project,
        display_name=project.display_name or project_display_name(project.project),
        codex_tokens=project.codex_tokens,
        claude_tokens=project.claude_tokens,
        today_codex_tokens=project.today_codex_tokens,
        today_claude_tokens=project.today_claude_tokens,
        month_percent=_percent(project.total_tokens, total_tokens),
        sample_cwds=project.sample_cwds,
    )


def _percent(tokens: int, total_tokens: int) -> float:
    if total_tokens <= 0:
        return 0.0
    return round(tokens / total_tokens * 100, 1)


def project_display_name(project: str) -> str:
    if project == OTHER_PROJECT:
        return OTHER_PROJECT_DISPLAY_NAME
    return project
