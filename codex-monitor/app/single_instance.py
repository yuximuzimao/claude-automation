"""Single-instance guard for the Codex Monitor UI."""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path
from types import TracebackType


def default_lock_path(*, home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / "Library" / "Application Support" / "Codex Monitor" / "codex-monitor.lock"


class SingleInstance:
    def __init__(
        self,
        path: Path | None = None,
        *,
        wait_seconds: float = 0.0,
        poll_interval: float = 0.05,
    ) -> None:
        self.path = path or default_lock_path()
        self.wait_seconds = max(0.0, float(wait_seconds))
        self.poll_interval = max(0.001, float(poll_interval))
        self.acquired = False
        self._file = None

    def __enter__(self) -> "SingleInstance":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+", encoding="utf-8")
        deadline = time.monotonic() + self.wait_seconds
        while True:
            if self._try_acquire():
                return self
            if time.monotonic() >= deadline:
                self.acquired = False
                return self
            time.sleep(min(self.poll_interval, max(0.0, deadline - time.monotonic())))

    def _try_acquire(self) -> bool:
        if self._file is None:
            return False
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.acquired = False
            return False
        self.acquired = True
        self._file.seek(0)
        self._file.truncate()
        self._file.write(f"{os.getpid()}\n")
        self._file.flush()
        return True

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        if self._file is None:
            return
        try:
            if self.acquired:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
            self.acquired = False
