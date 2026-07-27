from __future__ import annotations

from pathlib import Path

from .case_repository import default_case_path
from .file_lock import FileLock, FileLockError


class AlreadyRunningError(RuntimeError):
    """审单悬浮窗已有实例运行。"""


def default_instance_lock_path() -> Path:
    return instance_lock_path_for_case(default_case_path())


def instance_lock_path_for_case(case_path: str | Path) -> Path:
    return Path(case_path).with_name("order-review.instance.lock")


class SingleInstanceGuard:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_instance_lock_path()
        self._lock = FileLock(self.path, timeout=0)

    def __enter__(self) -> SingleInstanceGuard:
        try:
            self._lock.acquire()
        except FileLockError as exc:
            raise AlreadyRunningError("审单悬浮窗已经在运行，本次启动已退出。") from exc
        return self

    def __exit__(self, *_args: object) -> None:
        self._lock.release()
