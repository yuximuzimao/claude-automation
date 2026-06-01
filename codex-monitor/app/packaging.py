"""Build a minimal macOS .app wrapper for Codex Monitor."""

from __future__ import annotations

import plistlib
import shutil
import stat
from pathlib import Path


BUNDLE_NAME = "Codex Monitor"
BUNDLE_IDENTIFIER = "com.local.codex-monitor"
ICON_NAME = "CodexMonitor"  # .icns, lives in app/resources/
_RESOURCES_SRC = Path(__file__).parent / "resources"


def build_app_bundle(
    *,
    output_dir: Path,
    project_dir: Path,
    python_executable: str,
) -> Path:
    bundle = output_dir / f"{BUNDLE_NAME}.app"
    contents = bundle / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(exist_ok=True)
    _write_info_plist(contents / "Info.plist")
    _copy_icon(resources)
    launcher = macos / BUNDLE_NAME
    _write_launcher(
        launcher,
        project_dir=project_dir,
        python_executable=python_executable,
    )
    return bundle


def _write_info_plist(path: Path) -> None:
    payload = {
        "CFBundleExecutable": BUNDLE_NAME,
        "CFBundleIconFile": ICON_NAME,
        "CFBundleIdentifier": BUNDLE_IDENTIFIER,
        "CFBundleName": BUNDLE_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1.0",
        "LSMinimumSystemVersion": "10.15",
        "LSUIElement": True,            # floating widget — no Dock icon
        "NSHighResolutionCapable": True,  # Retina support
    }
    path.write_bytes(plistlib.dumps(payload, sort_keys=True))


def _copy_icon(resources_dir: Path) -> None:
    src = _RESOURCES_SRC / f"{ICON_NAME}.icns"
    if src.exists():
        shutil.copy2(src, resources_dir / f"{ICON_NAME}.icns")


def _write_launcher(
    path: Path,
    *,
    project_dir: Path,
    python_executable: str,
) -> None:
    script = "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            f"cd {project_dir}",
            f"exec {python_executable} main.py --ui",
            "",
        ]
    )
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def choose_python_executable() -> str:
    for candidate in (
        Path("/opt/homebrew/bin/python3.13"),
        Path("/usr/local/bin/python3.13"),
    ):
        if candidate.exists():
            return str(candidate)
    return "python3.13"
