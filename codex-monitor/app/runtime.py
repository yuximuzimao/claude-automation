"""Runtime refresh helpers for Codex Monitor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class RefreshRequest:
    reason: str
    claude_modified_since: float | None = None
    claude_max_files: int | None = None

    @classmethod
    def manual(cls) -> "RefreshRequest":
        return cls(reason="manual")


class DebouncedRefresher:
    def __init__(
        self,
        refresh_fn: Callable[[RefreshRequest], object],
        *,
        delay_seconds: float = 0.5,
        incremental_window_seconds: float = 300.0,
        claude_max_files: int = 50,
    ) -> None:
        self.refresh_fn = refresh_fn
        self.delay_seconds = delay_seconds
        self.incremental_window_seconds = incremental_window_seconds
        self.claude_max_files = claude_max_files
        self._pending_due_at: float | None = None

    def notify_change(self, _path: Path, *, now: float) -> None:
        self._pending_due_at = now + self.delay_seconds

    def flush_due(self, *, now: float) -> bool:
        if self._pending_due_at is None or now < self._pending_due_at:
            return False
        self._pending_due_at = None
        self.refresh_fn(
            RefreshRequest(
                reason="watcher",
                claude_modified_since=now - self.incremental_window_seconds,
                claude_max_files=self.claude_max_files,
            )
        )
        return True


class PollingWatcher:
    def __init__(
        self,
        paths: Iterable[Path],
        on_change: Callable[[Path], object],
    ) -> None:
        self.paths = tuple(paths)
        self.on_change = on_change
        self._mtimes: dict[Path, float | None] = {}

    def poll_once(self) -> None:
        for path in self.paths:
            mtime = _latest_mtime(path)
            previous = self._mtimes.get(path)
            self._mtimes[path] = mtime
            if previous is not None and mtime is not None and mtime != previous:
                self.on_change(path)


def _latest_mtime(path: Path) -> float | None:
    try:
        if path.is_file():
            return path.stat().st_mtime
        if path.is_dir():
            mtimes = [child.stat().st_mtime for child in path.rglob("*.jsonl")]
            return max(mtimes, default=path.stat().st_mtime)
        return None
    except OSError:
        return None


def start_watchdog_observer(
    paths: Iterable[Path],
    on_change: Callable[[Path], object],
) -> Any | None:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        return None

    class JsonlChangeHandler(FileSystemEventHandler):
        def on_created(self, event: Any) -> None:
            self._handle(event)

        def on_modified(self, event: Any) -> None:
            self._handle(event)

        def _handle(self, event: Any) -> None:
            if getattr(event, "is_directory", False):
                return
            path = Path(event.src_path)
            if path.suffix == ".jsonl":
                on_change(path)

    observer = Observer()
    handler = JsonlChangeHandler()
    scheduled = False
    for path in paths:
        if path.exists():
            observer.schedule(handler, str(path), recursive=path.is_dir())
            scheduled = True
    if not scheduled:
        return None
    observer.start()
    return observer
