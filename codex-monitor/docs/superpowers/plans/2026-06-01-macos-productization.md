# Codex Monitor macOS Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Codex Monitor from a tkinter MVP into a local macOS app that can run in the background, start at login, and refresh from file changes without reading credentials or conversation content.

**Architecture:** Keep the existing reader/aggregate/UI layers as the core. Add a small runtime layer for app lifecycle, a watcher layer for debounced JSONL refresh, and a LaunchAgent installer for login startup. Do not implement HTTP quota in this phase; continue using local `payload.rate_limits` and show data freshness.

**Tech Stack:** Python 3.13, tkinter, stdlib `plistlib`, optional `watchdog` for file events, macOS LaunchAgent, `unittest`.

---

## Scope Decision

Implement now:
- `.app` launch wrapper around the current tkinter UI.
- Background-capable app process with hide/show/refresh/quit behavior.
- LaunchAgent install/uninstall commands for login startup.
- Real-time file watching for Codex and Claude JSONL roots with debounced refresh.
- Polling fallback if `watchdog` is unavailable.
- Data freshness display for quota timestamp.
- Watcher-triggered Claude refresh must preserve the user-approved rolling 30-day UI view, using a 30-day `modified_since` bound and the configured `--claude-max-files` cap; watcher callbacks must never trigger an unrestricted `.claude/projects` scan.

Defer:
- HTTP quota. It needs login/session handling and may require reading credentials or browser auth state. The current MVP deliberately avoids that risk.
- Full menu bar app with `rumps`/PyObjC. That is a larger dependency and can follow once the LaunchAgent + app wrapper is stable.
- Index database. If watcher refresh still proves too heavy, add an incremental index in a later phase.

## File Structure

- `app/runtime.py` — owns app refresh loop, watcher callbacks, debounce, modified-since gates, and polling fallback.
- `app/autostart.py` — creates/removes/prints the LaunchAgent plist. No shelling out required for file generation.
- `app/packaging.py` — creates a local `.app` bundle wrapper that launches `python3.13 main.py --ui`.
- `app/ui_tk.py` — minor changes only: expose show/hide/refresh hooks if needed; keep layout changes small.
- `main.py` — add CLI commands:
  - `--install-app`
  - `--install-autostart`
  - `--uninstall-autostart`
  - `--print-launch-agent`
  - `--ui`
- `tests/test_runtime.py` — debounce and polling fallback tests using temporary files.
- `tests/test_autostart.py` — plist content and install/uninstall path tests using temporary directories.
- `tests/test_packaging.py` — `.app` bundle structure and launcher script tests using temporary directories.
- `docs/INDEX.md` — document lifecycle, autostart path, no-credential boundary, and troubleshooting.
- `tasks/todo.md` — mark phase 6 tasks.

## Task 1: Runtime Refresh Controller

**Files:**
- Create: `app/runtime.py`
- Test: `tests/test_runtime.py`

- [x] **Step 1: Write failing tests**

Test required behaviors:
- Multiple file-change events inside a short debounce window produce one refresh.
- Polling fallback detects mtime change and calls refresh.
- Watcher-triggered refresh calls the aggregate loader with the bounded rolling 30-day scope used by the UI, not an unrestricted scan.
- Runtime never reads JSONL contents directly; it calls the existing aggregate loader.

- [x] **Step 2: Run focused tests**

Run: `python3 -m unittest tests.test_runtime -v`
Expected: FAIL because `app.runtime` does not exist.

- [x] **Step 3: Implement minimal runtime**

Implementation shape:
- `DebouncedRefresher(refresh_fn, delay_seconds=0.5)`
- `notify_change(path)`
- `flush_due(now=None)` for testable debounce behavior
- `PollingWatcher(paths, on_change, interval_seconds=5)` with one-step `poll_once()` for tests
- `RefreshRequest(claude_modified_since=None, claude_max_files=None)` or equivalent so watcher refreshes can be incrementally gated while manual refresh can keep the existing `--claude-days` behavior

Do not start background threads in unit tests. Keep thread startup behind explicit runtime methods.

- [x] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_runtime -v`
Expected: PASS.

## Task 2: LaunchAgent Autostart

**Files:**
- Create: `app/autostart.py`
- Test: `tests/test_autostart.py`
- Modify: `main.py`

- [x] **Step 1: Write failing tests**

Test required plist fields:
- `Label`: `com.local.codex-monitor`
- `ProgramArguments`: points to `python3.13`, project `main.py`, and `--ui`
- `RunAtLoad`: true
- `KeepAlive`: false
- `StandardOutPath` and `StandardErrorPath`: under `~/Library/Logs/Codex Monitor/`
- install path defaults to `~/Library/LaunchAgents/com.local.codex-monitor.plist`

- [x] **Step 2: Run focused tests**

Run: `python3 -m unittest tests.test_autostart -v`
Expected: FAIL because `app.autostart` does not exist.

- [x] **Step 3: Implement plist generation and safe file operations**

Use `plistlib.dumps()` and explicit paths. Create parent directories as needed. Do not run `launchctl` automatically from tests.

CLI behavior:
- `--print-launch-agent`: prints plist XML to stdout.
- `--install-autostart`: writes plist and prints the exact `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.codex-monitor.plist` command. It must not execute `launchctl`.
- `--uninstall-autostart`: removes plist if present.

- [x] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_autostart -v`
Expected: PASS.

## Task 3: `.app` Bundle Wrapper

**Files:**
- Create: `app/packaging.py`
- Test: `tests/test_packaging.py`
- Modify: `main.py`

- [x] **Step 1: Write failing tests**

Test that `build_app_bundle()` creates:
- `Codex Monitor.app/Contents/Info.plist`
- `Codex Monitor.app/Contents/MacOS/Codex Monitor`
- executable launcher script
- bundle identifier `com.local.codex-monitor`

- [x] **Step 2: Run focused tests**

Run: `python3 -m unittest tests.test_packaging -v`
Expected: FAIL because `app.packaging` does not exist.

- [x] **Step 3: Implement minimal bundle**

Launcher script should execute:
```bash
cd /Users/chat/claude/codex-monitor
exec /opt/homebrew/bin/python3.13 main.py --ui
```

If `/opt/homebrew/bin/python3.13` does not exist, fall back to `/usr/local/bin/python3.13`, then `python3.13` from PATH.

- [x] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_packaging -v`
Expected: PASS.

## Task 4: Wire Runtime Into UI

**Files:**
- Modify: `main.py`
- Modify: `app/ui_tk.py`
- Test: `tests/test_ui_tk.py`

- [x] **Step 1: Add tests around refresh plumbing**

Existing `test_refresh_updates_last_updated_label` should remain green. Add a test that refresh function can be called from runtime without rebuilding the root window.

- [x] **Step 2: Implement runtime-backed UI launch**

`main.py --ui` should:
- load initial aggregate
- create runtime controller
- register Codex sessions root and Claude projects root
- on debounced changes, refresh the current UI model using the user-approved rolling 30-day scope and the configured `--claude-max-files` cap
- on manual refresh, keep the existing explicit `--claude-days` / `--claude-max-files` behavior rather than silently widening scope

Threading rule:
- watcher thread may detect changes
- tkinter update must happen on main thread via `root.after(...)`

- [x] **Step 3: Run UI tests**

Run: `python3 -m unittest tests.test_ui_tk tests.test_runtime -v`
Expected: PASS.

## Task 5: Documentation And Safety Boundary

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `README.md`
- Modify: `tasks/todo.md`

- [x] **Step 1: Update docs**

Document:
- `python3.13 main.py --install-app`
- `python3.13 main.py --install-autostart`
- `python3.13 main.py --uninstall-autostart`
- LaunchAgent path
- Logs path: `~/Library/Logs/Codex Monitor/stdout.log` and `~/Library/Logs/Codex Monitor/stderr.log`
- No `.codex/auth.json`
- No HTTP quota in this phase
- Watchdog fallback behavior
- `--install-autostart` writes plist only and never runs `launchctl`
- Watcher refresh preserves the rolling 30-day UI view and must not perform an unrestricted `.claude/projects` scan

- [x] **Step 2: Read back docs**

Run: `rg -n "install-app|install-autostart|HTTP quota|auth.json|LaunchAgent|watchdog" docs README.md tasks`
Expected: docs mention all required boundaries.

## Task 6: Verification

**Files:**
- No code changes.

- [x] **Step 1: Run all unit tests**

Run: `python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [x] **Step 2: Compile**

Run: `python3 -m compileall app tests`
Expected: compile succeeds.

- [x] **Step 3: Smoke aggregate**

Run: `python3 main.py --smoke-aggregate`
Expected: JSON summary prints without conversation content.

- [x] **Step 4: Build app smoke**

Run: `python3.13 main.py --install-app`
Expected: `.app` bundle is created and launcher points to this project.

- [x] **Step 5: Autostart plist smoke**

Run: `python3.13 main.py --print-launch-agent`
Expected: plist prints valid XML and includes `com.local.codex-monitor`.

## Open Review Questions For Claude

1. Is LaunchAgent the right first autostart mechanism, or should this phase use a proper Login Item API despite higher complexity?
2. Should the `.app` wrapper launch `main.py --ui` directly, or should it launch a separate background/runtime command to separate daemon and UI concerns?
3. Is polling fallback acceptable at 5 seconds, or should the default be slower to reduce laptop wakeups?
4. Claude answered: logs must go under `~/Library/Logs/Codex Monitor/`, not `data/logs/`.
5. Any security concern with reading only `CLAUDE.md` project metadata and local JSONL token fields while continuing to avoid `.codex/auth.json` and HTTP quota?
