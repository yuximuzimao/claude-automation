from __future__ import annotations

from dataclasses import dataclass
import subprocess


@dataclass(frozen=True)
class ChromeWindowState:
    bounds: tuple[int, int, int, int]
    minimized: bool
    frontmost_process_name: str = ""
    frontmost_process_id: int = 0


@dataclass(frozen=True)
class ChromeActiveTab:
    title: str
    url: str


@dataclass(frozen=True)
class ChromeAccessibilityWindow:
    bounds: tuple[int, int, int, int]
    minimized: bool
    title: str = ""
    subrole: str = ""


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


def parse_accessibility_state(output: str) -> ChromeWindowState | None:
    """把辅助功能的 x、y、宽、高、最小化状态转换成浏览器边界。"""
    text = output.strip()
    if not text or text == "missing":
        return None
    sections = text.split("\x1f")
    parts = [part.strip() for part in sections[0].split(",")]
    if len(parts) != 5 or parts[4] not in {"true", "false"}:
        raise ValueError(f"invalid Chrome accessibility state output: {output!r}")
    x, y, width, height = (int(part) for part in parts[:4])
    frontmost_process_name = sections[1].strip() if len(sections) >= 2 else ""
    try:
        frontmost_process_id = int(sections[2]) if len(sections) >= 3 else 0
    except ValueError:
        frontmost_process_id = 0
    return ChromeWindowState(
        bounds=(x, y, x + width, y + height),
        minimized=parts[4] == "true",
        frontmost_process_name=frontmost_process_name,
        frontmost_process_id=frontmost_process_id,
    )


def select_primary_chrome_window(
    windows: list[ChromeAccessibilityWindow],
) -> ChromeAccessibilityWindow | None:
    """从 Chrome 的辅助功能窗口中排除确认框，选择主浏览器窗口。"""
    viable = [
        window
        for window in windows
        if window.bounds[2] > window.bounds[0]
        and window.bounds[3] > window.bounds[1]
    ]
    if not viable:
        return None
    browser_windows = [
        window
        for window in viable
        if window.title == "Google Chrome"
        or window.title.endswith(" - Google Chrome")
    ]
    candidates = browser_windows or [
        window for window in viable if window.subrole == "AXStandardWindow"
    ]
    if not candidates:
        candidates = viable
    return max(
        candidates,
        key=lambda window: (
            (window.bounds[2] - window.bounds[0])
            * (window.bounds[3] - window.bounds[1])
        ),
    )


def parse_accessibility_window_list(output: str) -> ChromeWindowState | None:
    """解析多个 AX 窗口，并只返回 Chrome 主浏览器窗口状态。"""
    text = output.strip()
    if not text or text == "missing":
        return None
    sections = text.split("\x1f", 2)
    if len(sections) != 3:
        raise ValueError(f"invalid Chrome accessibility window list: {output!r}")
    frontmost_process_name = sections[0].strip()
    try:
        frontmost_process_id = int(sections[1])
    except ValueError:
        frontmost_process_id = 0
    windows: list[ChromeAccessibilityWindow] = []
    for record in sections[2].split("\x1e"):
        if not record:
            continue
        fields = record.split("\x1d", 2)
        state_parts = [part.strip() for part in fields[0].split(",")]
        if len(state_parts) != 5 or state_parts[4] not in {"true", "false"}:
            continue
        x, y, width, height = (int(part) for part in state_parts[:4])
        windows.append(
            ChromeAccessibilityWindow(
                bounds=(x, y, x + width, y + height),
                minimized=state_parts[4] == "true",
                title=fields[1].strip() if len(fields) >= 2 else "",
                subrole=fields[2].strip() if len(fields) >= 3 else "",
            )
        )
    primary = select_primary_chrome_window(windows)
    if primary is None:
        return None
    return ChromeWindowState(
        bounds=primary.bounds,
        minimized=primary.minimized,
        frontmost_process_name=frontmost_process_name,
        frontmost_process_id=frontmost_process_id,
    )


def browser_companion_should_be_visible(
    state: ChromeWindowState,
    *,
    companion_process_id: int,
) -> bool:
    """只在 Chrome 或伴随浮窗自己处于前台时显示浮窗。"""
    if state.minimized:
        return False
    if not state.frontmost_process_name and not state.frontmost_process_id:
        return True
    return (
        state.frontmost_process_name == "Google Chrome"
        or state.frontmost_process_id == companion_process_id
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
        state = parse_applescript_state(completed.stdout)
        if state is not None:
            return state
    except Exception:
        pass
    return _get_chrome_accessibility_window_state()


def _get_chrome_accessibility_window_state() -> ChromeWindowState | None:
    script = """tell application "System Events"
set frontProcess to first application process whose frontmost is true
set frontProcessName to name of frontProcess
set frontProcessId to unix id of frontProcess
set windowRecords to ""
repeat with candidateProcess in (every application process whose name is "Google Chrome")
repeat with candidateWindow in windows of candidateProcess
try
set browserPosition to position of candidateWindow
set browserSize to size of candidateWindow
set browserMinimized to value of attribute "AXMinimized" of candidateWindow
set browserTitle to value of attribute "AXTitle" of candidateWindow
set browserSubrole to value of attribute "AXSubrole" of candidateWindow
set windowRecord to (item 1 of browserPosition as text) & "," & (item 2 of browserPosition as text) & "," & (item 1 of browserSize as text) & "," & (item 2 of browserSize as text) & "," & (browserMinimized as text) & (ASCII character 29) & browserTitle & (ASCII character 29) & browserSubrole
if windowRecords is not "" then set windowRecords to windowRecords & (ASCII character 30)
set windowRecords to windowRecords & windowRecord
end try
end repeat
end repeat
if windowRecords is "" then return "missing"
return frontProcessName & (ASCII character 31) & (frontProcessId as text) & (ASCII character 31) & windowRecords
end tell"""
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return parse_accessibility_window_list(completed.stdout)
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


def get_chrome_front_window_title() -> str:
    """读取 macOS 辅助功能看到的 Chrome 前台窗口标题。

    Chrome 151 的应用脚本接口可能在窗口可见时仍报告 0 个窗口；辅助功能树仍能
    准确返回当前窗口标题，因此只把它作为无法读取活动标签 URL 时的保守回退。
    """
    script = """tell application "System Events"
set browserProcess to missing value
repeat with candidateProcess in (every application process whose name is "Google Chrome")
if (count of windows of candidateProcess) > 0 then
set browserProcess to candidateProcess
exit repeat
end if
end repeat
if browserProcess is missing value then return ""
tell browserProcess
if (count of windows) is 0 then return ""
return value of attribute "AXTitle" of front window
end tell
end tell"""
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return completed.stdout.strip()
    except Exception:
        return ""


def get_chrome_window_bounds() -> tuple[int, int, int, int] | None:
    state = get_chrome_window_state()
    return state.bounds if state is not None else None
