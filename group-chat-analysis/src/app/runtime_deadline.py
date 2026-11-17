"""Absolute execution window and bounded process-group lifetime for one night job."""
from __future__ import annotations
import datetime as dt
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Callable

class DeadlineExceeded(RuntimeError):
    pass

class Deadline:
    def __init__(self, end: str, *, now: Callable[[], float] = time.time, monotonic: Callable[[], float] = time.monotonic):
        value = dt.datetime.fromisoformat(end.replace('Z', '+00:00'))
        if value.tzinfo is None:
            raise ValueError('deadline must have timezone')
        self.end = value.timestamp()
        self.now = now
        self.monotonic = monotonic
        self.monotonic_end = monotonic() + max(0.0, self.end - now())

    def remaining(self) -> float:
        return max(0.0, min(self.end-self.now(), self.monotonic_end-self.monotonic()))

    def check(self, reserve: float = 0) -> None:
        if self.remaining() <= reserve:
            raise DeadlineExceeded('absolute night deadline reached or insufficient reserved time')

    @classmethod
    def from_environment(cls) -> 'Deadline | None':
        value = os.environ.get('GCA_DEADLINE_UTC')
        return cls(value) if value else None


def check_environment_deadline(reserve: float = 0) -> None:
    deadline = Deadline.from_environment()
    if deadline:
        deadline.check(reserve)


def run_bounded(argv: list[str], *, deadline: Deadline, cwd: Path, log: Path,
                stdin: str | None = None, timeout: float | None = None,
                preflight: Callable[[int | None], None] | None = None) -> float:
    """Kill the whole child session at the bound; never clear capture pending."""
    deadline.check()
    if preflight:
        preflight(None)
    limit = min(deadline.remaining(), timeout if timeout is not None else deadline.remaining())
    started = time.monotonic()
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GCA_DEADLINE_UTC=dt.datetime.fromtimestamp(deadline.end, dt.timezone.utc).isoformat())
    with log.open('ab') as output:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            # Input can be large; communicate drains/writes without pipe deadlock.
            first = True
            while True:
                deadline.check()
                remaining = min(deadline.remaining(), limit-(time.monotonic()-started))
                if remaining <= 0:
                    raise DeadlineExceeded('child stage exceeded its time budget')
                if preflight:
                    preflight(process.pid)
                try:
                    process.communicate(input=(stdin.encode() if stdin is not None else None) if first else None,
                                        timeout=min(1.0, remaining))
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    continue
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        if process.returncode:
            raise RuntimeError(f'child failed ({process.returncode}); see {log}')
    deadline.check()
    return time.monotonic()-started
