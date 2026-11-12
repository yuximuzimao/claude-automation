"""Bound one farm action and reap its process group before returning."""
from __future__ import annotations

import os
import signal
import subprocess

MANAGED_ENV = "QQ_FARM_MANAGED_ACTION"


class ActionCancelled(RuntimeError):
    pass


class ActionCleanupError(RuntimeError):
    pass


def release_mouse():
    from pathlib import Path
    helper = Path(__file__).resolve().parents[1] / "_sandbox/farm_release_input"
    result = subprocess.run([str(helper), "--release-left"],
                            capture_output=True, text=True, timeout=10)
    if result.returncode or result.stdout.strip() != "left_button_released":
        raise ActionCleanupError("INPUT_RELEASE_FAILED: " + (result.stderr.strip() or result.stdout.strip()))


def run_action(argv, *, timeout, input=None):
    # Nested scripts inherit this process group; they must not detach children.
    env = dict(os.environ, **{MANAGED_ENV: "1"})
    proc = None
    cancelled = None
    previous = {}
    release_needed = True

    def cancel(signum, _frame):
        nonlocal cancelled
        cancelled = signum
        # Never unwind Popen before its process handle has been assigned.
        # If already running, stop the group so communicate wakes promptly.
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, cancel)
        if cancelled is not None:
            raise ActionCancelled(f"ACTION_CANCELLED_SIGNAL_{cancelled}")
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if input is not None else None,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=True, env=env)
        if cancelled is not None:
            raise ActionCancelled(f"ACTION_CANCELLED_SIGNAL_{cancelled}")
        stdout, stderr = proc.communicate(input=input, timeout=timeout)
        if cancelled is not None:
            raise ActionCancelled(f"ACTION_CANCELLED_SIGNAL_{cancelled}")
        release_needed = proc.returncode != 0
        return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
    finally:
        # Ignore repeated cancellation during cleanup. Kill the group even when
        # its leader exited: a timed-out inner script may have left an input helper.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if proc is not None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.communicate()
                if release_needed:
                    try:
                        release_mouse()
                    except (OSError, subprocess.SubprocessError) as exc:
                        raise ActionCleanupError(f"INPUT_RELEASE_FAILED: {exc}") from exc
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def scan_hours(path=None):
    """Read the authoritative constant as text; never import the business server."""
    import re
    from pathlib import Path
    path = path or Path(__file__).resolve().parents[2] / "aftersales-automation/lib/constants.js"
    match = re.search(r"const\s+SCAN_HOURS\s*=\s*\[([\d,\s]+)\]\s*;", path.read_text())
    if not match:
        raise ValueError("SCAN_HOURS_NOT_FOUND")
    hours = [int(v.strip()) for v in match[1].split(",") if v.strip()]
    if not hours or len(set(hours)) != len(hours) or any(not 0 <= h < 24 for h in hours):
        raise ValueError("INVALID_SCAN_HOURS")
    return hours


def allowed_start(moment, hours):
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    if moment.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    local = moment.astimezone(ZoneInfo("Asia/Shanghai"))
    minute = local.replace(second=0, microsecond=0)
    for day in (-1, 0, 1):
        for hour in hours:
            scan = (minute + timedelta(days=day)).replace(hour=hour, minute=0)
            if scan - timedelta(minutes=10) <= minute <= scan + timedelta(hours=1):
                return False
    return True


def next_allowed_start(moment, hours):
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    local = moment.astimezone(ZoneInfo("Asia/Shanghai"))
    target = local.replace(second=0, microsecond=0)
    if local > target:
        target += timedelta(minutes=1)
    for _ in range(24 * 60 + 1):
        if allowed_start(target, hours):
            return target
        target += timedelta(minutes=1)
    raise ValueError("NO_ALLOWED_START_IN_24_HOURS")


if __name__ == "__main__":
    import argparse
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo
    parser = argparse.ArgumentParser(description="Read-only scheduled farm start eligibility")
    parser.add_argument("--at", help="ISO datetime with timezone; default is current computer time")
    args = parser.parse_args()
    try:
        at = datetime.fromisoformat(args.at) if args.at else datetime.now(ZoneInfo("Asia/Shanghai"))
        hours = scan_hours()
        allowed = allowed_start(at, hours)
        print(json.dumps({"allowed_start": allowed, "scan_hours": hours,
                          "local_time": at.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
                          "next_allowed_start": next_allowed_start(at, hours).isoformat()}, ensure_ascii=False))
        raise SystemExit(0 if allowed else 2)
    except (OSError, ValueError) as exc:
        print(json.dumps({"allowed_start": False, "reason": str(exc)}))
        raise SystemExit(2)
