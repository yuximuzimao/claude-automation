from __future__ import annotations

from dataclasses import dataclass
import subprocess


@dataclass(frozen=True)
class ChromeWindowState:
    bounds: tuple[int, int, int, int]
    minimized: bool


@dataclass(frozen=True)
class ChromeActiveTab:
    title: str
    url: str


def parse_applescript_bounds(output: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in output.strip().split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid bounds output: {output!r}")
    return parts[0], parts[1], parts[2], parts[3]


def parse_applescript_state(output: str) -> ChromeWindowState | None:
    text = output.strip()
    if text == "missing":
        return None
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 5 or parts[4] not in {"true", "false"}:
        raise ValueError(f"invalid Chrome window state output: {output!r}")
    bounds = tuple(int(part) for part in parts[:4])
    return ChromeWindowState(
        bounds=(bounds[0], bounds[1], bounds[2], bounds[3]),
        minimized=parts[4] == "true",
    )


def parse_applescript_active_tab(output: str) -> ChromeActiveTab | None:
    text = output.strip()
    if text == "missing":
        return None
    parts = text.split("\x1f", 1)
    if len(parts) != 2:
        raise ValueError(f"invalid Chrome active tab output: {output!r}")
    return ChromeActiveTab(title=parts[0].strip(), url=parts[1].strip())


def panel_geometry_from_browser_bounds(
    bounds: tuple[int, int, int, int],
    *,
    panel_width: int,
    panel_height: int | None = None,
    gap: int = 8,
) -> str:
    left, top, _right, bottom = bounds
    if panel_height is None:
        panel_height = max(1, bottom - top)
    x = max(0, left - panel_width - gap)
    y = max(0, top)
    return f"{panel_width}x{panel_height}+{x}+{y}"


def get_chrome_window_state() -> ChromeWindowState | None:
    script = """tell application \"Google Chrome\"
if (count of windows) is 0 then return \"missing\"
set browserBounds to bounds of front window
set browserMinimized to minimized of front window
return (item 1 of browserBounds as text) & \",\" & (item 2 of browserBounds as text) & \",\" & (item 3 of browserBounds as text) & \",\" & (item 4 of browserBounds as text) & \",\" & (browserMinimized as text)
end tell"""
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return parse_applescript_state(completed.stdout)
    except Exception:
        return None


def get_chrome_active_tab() -> ChromeActiveTab | None:
    script = """tell application \"Google Chrome\"
if (count of windows) is 0 then return \"missing\"
set activeTitle to title of active tab of front window
set activeUrl to URL of active tab of front window
return activeTitle & (ASCII character 31) & activeUrl
end tell"""
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return parse_applescript_active_tab(completed.stdout)
    except Exception:
        return None


def get_chrome_window_bounds() -> tuple[int, int, int, int] | None:
    state = get_chrome_window_state()
    return state.bounds if state is not None else None
