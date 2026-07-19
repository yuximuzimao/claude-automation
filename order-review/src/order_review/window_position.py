from __future__ import annotations

import subprocess


def parse_applescript_bounds(output: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in output.strip().split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid bounds output: {output!r}")
    return parts[0], parts[1], parts[2], parts[3]


def panel_geometry_from_browser_bounds(
    bounds: tuple[int, int, int, int],
    *,
    panel_width: int,
    panel_height: int,
    gap: int = 8,
) -> str:
    left, top, _right, _bottom = bounds
    x = max(0, left - panel_width - gap)
    y = max(0, top)
    return f"{panel_width}x{panel_height}+{x}+{y}"


def get_chrome_window_bounds() -> tuple[int, int, int, int] | None:
    script = 'tell application "Google Chrome" to get bounds of front window'
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return None
    try:
        return parse_applescript_bounds(completed.stdout)
    except ValueError:
        return None
