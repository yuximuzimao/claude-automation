from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from farm_process import run_action, allowed_start, next_allowed_start


def running(pid):
    reply = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='], capture_output=True, text=True)
    return bool(reply.stdout.strip()) and not reply.stdout.strip().startswith('Z')


def wait_stopped(pid):
    for _ in range(50):
        if not running(pid):
            return
        time.sleep(.02)
    raise AssertionError(f'Leaked test descendant {pid}')


def descendant_code(marker):
    return ("import subprocess,sys,time; from pathlib import Path; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            f"Path({str(marker)!r}).write_text(str(p.pid)); time.sleep(60)")


def cleanup_marker(marker):
    if marker.exists():
        pid = int(marker.read_text())
        if running(pid):
            os.kill(pid, signal.SIGKILL)
        wait_stopped(pid)


def test_timeout_kills_descendants(tmp_path, monkeypatch):
    import farm_process
    releases=[]
    monkeypatch.setattr(farm_process, "release_mouse", lambda: releases.append(True))
    marker = tmp_path / 'child.pid'
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            run_action([sys.executable, '-c', descendant_code(marker)], timeout=.5)
        assert marker.exists()
        wait_stopped(int(marker.read_text()))
        assert releases == [True]
    finally:
        cleanup_marker(marker)


def test_cancellation_kills_descendants(tmp_path):
    marker = tmp_path / 'child.pid'
    scripts = str(Path(__file__).resolve().parents[1] / 'scripts')
    code = f"import sys;sys.path.insert(0,{scripts!r});import farm_process;farm_process.release_mouse=lambda:None;farm_process.run_action([sys.executable,'-c',{descendant_code(marker)!r}],timeout=60)"
    parent = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if marker.exists():break
            time.sleep(.02)
        assert marker.exists()
        parent.terminate()
        parent.wait(timeout=5)
        wait_stopped(int(marker.read_text()))
    finally:
        if parent.poll() is None:parent.kill()
        parent.wait(timeout=5)
        cleanup_marker(marker)


@pytest.mark.parametrize('clock,allowed', [('07:49:59',True),('07:50:00',False),('08:00:00',False),('09:00:59',False),('09:01:00',True),('23:49:59',True),('23:50:00',False),('00:30:00',False),('01:00:59',False),('01:01:00',True)])
def test_start_windows(clock, allowed):
    at=datetime.fromisoformat('2026-11-12T'+clock+'+08:00')
    assert allowed_start(at,[0,8,12,16,20]) is allowed


def test_next_allowed_rolls_over_midnight():
    at=datetime.fromisoformat('2026-11-11T23:51:00+08:00')
    assert next_allowed_start(at,[0,8,12,16,20]).isoformat()=='2026-11-12T01:01:00+08:00'
