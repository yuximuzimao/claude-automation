from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import threading
import time
from typing import Iterator, TextIO


class FileLockError(RuntimeError):
    """跨进程文件锁获取失败。"""


_registry_guard = threading.Lock()
_thread_locks: dict[str, threading.RLock] = {}


def _thread_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _registry_guard:
        return _thread_locks.setdefault(key, threading.RLock())


class FileLock:
    """同时覆盖当前进程线程和其他进程的独占文件锁。"""

    def __init__(self, path: str | Path, *, timeout: float = 5.0) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._thread_lock = _thread_lock(self.path)
        self._handle: TextIO | None = None
        self._thread_acquired = False

    def acquire(self) -> None:
        deadline = time.monotonic() + max(self.timeout, 0.0)
        if not self._thread_lock.acquire(timeout=max(self.timeout, 0.0)):
            raise FileLockError(f"等待本地文件锁超时：{self.path}")
        self._thread_acquired = True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("a+", encoding="utf-8")
            while True:
                try:
                    fcntl.flock(
                        self._handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                    self._write_owner()
                    return
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise FileLockError(f"等待跨进程文件锁超时：{self.path}") from exc
                    time.sleep(0.05)
        except Exception:
            self.release()
            raise

    def _write_owner(self) -> None:
        if self._handle is None:
            return
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(f"{os.getpid()}\n")
        self._handle.flush()

    def release(self) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
        if self._thread_acquired:
            self._thread_acquired = False
            self._thread_lock.release()

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


@contextmanager
def exclusive_file_lock(
    path: str | Path,
    *,
    timeout: float = 5.0,
) -> Iterator[None]:
    with FileLock(path, timeout=timeout):
        yield
