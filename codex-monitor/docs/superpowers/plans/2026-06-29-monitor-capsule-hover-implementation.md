# Monitor Capsule Hover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the large floating monitor window with a dock-height glass capsule and a click-triggered popover showing Project Top 10.

**Architecture:** Keep the current Tkinter UI and native AppKit blur-window layering. The main window becomes a compact capsule canvas; a separate transparent Tk toplevel displays the transient Top10 popover when the capsule is clicked.

**Tech Stack:** Python 3.13, Tkinter, PyObjC/AppKit `NSVisualEffectView`, `unittest`.

---

### Task 1: Test The New Presentation Contract

**Files:**
- Modify: `tests/test_ui_tk.py`
- Modify: `app/ui_tk.py`

- [ ] **Step 1: Add failing tests for constants, time labels, and Top10**

Add tests that assert:

```python
from app.ui_tk import (
    COLLAPSED_H,
    COLLAPSED_W,
    _fmt_compact_duration,
    _project_popover_limit,
)

def test_collapsed_capsule_matches_dock_height_target(self):
    self.assertEqual(COLLAPSED_W, 258)
    self.assertEqual(COLLAPSED_H, 82)

def test_compact_duration_uses_chinese_units(self):
    self.assertEqual(_fmt_compact_duration(172), "2小时52分")
    self.assertEqual(_fmt_compact_duration(9600), "6天16小时")
    self.assertEqual(_fmt_compact_duration(45), "45分")

def test_project_popover_contract(self):
    self.assertEqual(_project_popover_limit(), 10)
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: fail because the new helper functions do not exist and the collapsed constants still use the old round panel size.

- [ ] **Step 3: Implement constants and formatting helpers**

In `app/ui_tk.py`:

```python
COLLAPSED_W = 258
COLLAPSED_H = 82
PROJECT_POPOVER_LIMIT = 10

def _project_popover_limit() -> int:
    return PROJECT_POPOVER_LIMIT

def _fmt_compact_duration(minutes: int | None) -> str:
    if minutes is None:
        return "--"
    minutes = max(0, int(minutes))
    days, rem = divmod(minutes, 1440)
    hours, mins = divmod(rem, 60)
    if days:
        return f"{days}天{hours}小时" if hours else f"{days}天"
    if hours:
        return f"{hours}小时{mins}分" if mins else f"{hours}小时"
    return f"{mins}分"
```

- [ ] **Step 4: Run test to verify GREEN**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: UI tests pass for the new helper behavior.

### Task 2: Build The Dock-Height Capsule

**Files:**
- Modify: `app/ui_tk.py`
- Modify: `tests/test_ui_tk.py`

- [ ] **Step 1: Add failing tests for palette and no collapsed panel layers**

Assert the collapsed panel no longer uses the old double-layer frame and the palette exposes readable dark-glass colors:

```python
from app.ui_tk import (
    COLOR_5H,
    COLOR_WEEK,
    TEXT_ON_GLASS,
    _collapsed_panel_layers,
)

def test_collapsed_panel_uses_no_extra_card_layers(self):
    self.assertEqual(_collapsed_panel_layers(258, 82), [])

def test_dark_glass_palette_uses_light_text_and_status_colors(self):
    self.assertEqual(TEXT_ON_GLASS, "#F7F9FB")
    self.assertEqual(COLOR_5H, "#5FD0C5")
    self.assertEqual(COLOR_WEEK, "#F2B866")
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: fail because `TEXT_ON_GLASS` is not defined and colors still use the previous palette.

- [ ] **Step 3: Implement capsule drawing**

Update the collapsed builder to draw:

- one rounded capsule shell,
- left 5h ring,
- right weekly ring,
- two centered reset-time labels,
- no action buttons,
- no bottom countdown labels.

The ring drawing can keep using `_draw_ring`, with smaller radii and very subtle track color.

- [ ] **Step 4: Run test to verify GREEN**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: UI tests pass.

### Task 3: Add The Click-Triggered Top10 Popover

**Files:**
- Modify: `app/ui_tk.py`
- Modify: `tests/test_ui_tk.py`

- [ ] **Step 1: Add tests for click trigger state**

```python
def test_capsule_click_shows_project_popover_immediately(self):
    # Create a minimal fake window instance via object.__new__.
    # Verify _capsule_click calls _show_project_popover immediately.
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: fail because click popover methods do not exist.

- [ ] **Step 3: Implement click trigger and range tracking**

Add fields:

```python
self._popover_after_id: str | None = None
self._project_popover: Any | None = None
self._popover_pointer_inside = False
self._capsule_pointer_inside = False
```

Add methods:

```python
def _cancel_project_popover_timer(self): ...
def _capsule_enter(self, _event=None): ...
def _capsule_click(self, _event=None): ...
def _capsule_leave(self, _event=None): ...
def _maybe_hide_project_popover(self, _event=None): ...
def _show_project_popover(self): ...
def _hide_project_popover(self): ...
```

Bind capsule `<Button-1>` to immediate show, and `<Enter>` / `<Leave>` to the range tracking and hide logic.

- [ ] **Step 4: Build popover UI**

Use a `tk.Toplevel` with transparent chrome and the same native blur helper. The popover contains only the Project Top10 table:

- title row: `项目 Top 10`,
- totals: `30天 {month_total} · 今日 {today_total}`,
- rows: first 10 projects,
- columns: project, today, 30天, 占比,
- note: `结合 Claude Code 和 Codex 本地日志估算`.

- [ ] **Step 5: Run test to verify GREEN**

Run:

```bash
python3.13 -m unittest tests.test_ui_tk -v
```

Expected: UI tests pass.

### Task 4: Verify Real App Behavior

**Files:**
- Modify: `data/state.json` only if needed to leave app in collapsed state for visual verification.

- [ ] **Step 1: Run full automated checks**

Run:

```bash
python3.13 -m unittest discover -s tests -v
python3.13 -m compileall app tests
```

Expected: all tests pass and compilation exits 0.

- [ ] **Step 2: Restart LaunchAgent**

Run:

```bash
launchctl bootout gui/501/com.local.codex-monitor
launchctl bootstrap gui/501 /Users/chat/Library/LaunchAgents/com.local.codex-monitor.plist
sleep 4
launchctl print gui/501/com.local.codex-monitor
tail -120 '/Users/chat/Library/Logs/Codex Monitor/stderr.log'
```

Expected: service is running and stderr is empty.

- [ ] **Step 3: Screenshot verify**

Run:

```bash
screencapture -x /tmp/codex-monitor-capsule-hover.png
```

Expected: collapsed monitor is a dock-height glass capsule in the bottom-left area. Manual click verification confirms the Top10 popover appears immediately and hides after leaving.
