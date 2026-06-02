"""LaunchAgent helpers for Codex Monitor autostart."""

from __future__ import annotations

import os
import plistlib
from pathlib import Path


LAUNCH_AGENT_LABEL = "com.local.codex-monitor"
LAUNCH_AGENT_FILENAME = f"{LAUNCH_AGENT_LABEL}.plist"


def launch_agent_path(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / "Library" / "LaunchAgents" / LAUNCH_AGENT_FILENAME


def log_dir(home: Path | None = None) -> Path:
    home = home or Path.home()
    return home / "Library" / "Logs" / "Codex Monitor"


def build_launch_agent_plist(
    *,
    home: Path | None = None,
    project_dir: Path,
    python_executable: str,
) -> bytes:
    logs = log_dir(home)
    payload = {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": [
            python_executable,
            str(project_dir / "main.py"),
            "--ui",
        ],
        "RunAtLoad": True,
        "KeepAlive": False,
        "WorkingDirectory": str(project_dir),
        "StandardOutPath": str(logs / "stdout.log"),
        "StandardErrorPath": str(logs / "stderr.log"),
    }
    return plistlib.dumps(payload, sort_keys=True)


def install_launch_agent(
    *,
    home: Path | None = None,
    project_dir: Path,
    python_executable: str,
) -> Path:
    path = launch_agent_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    log_dir(home).mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        build_launch_agent_plist(
            home=home,
            project_dir=project_dir,
            python_executable=python_executable,
        )
    )
    return path


def uninstall_launch_agent(*, home: Path | None = None) -> bool:
    path = launch_agent_path(home)
    if not path.exists():
        return False
    path.unlink()
    return True


def launchctl_bootstrap_command(path: Path, *, uid: int | None = None) -> str:
    uid = uid if uid is not None else os.getuid()
    return f"launchctl bootstrap gui/{uid} {path}"
