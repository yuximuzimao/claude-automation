# Codex Monitor

Local usage monitor for Codex and Claude Code.

The app reads local JSONL session logs, keeps token usage split by source and model, aggregates today / rolling 30-day usage, and presents a small tkinter floating window. It does not read credentials or call internal HTTP quota endpoints.

## Current Capabilities

- Phase 0: project initialization
- Phase 1: Codex local JSONL reader
- Phase 2: Claude Code local JSONL reader
- Phase 3: aggregate today / rolling 30-day totals, quota, and Top projects
- Phase 4: tkinter MVP UI with quota, token totals, Top projects, and cwd tooltip
- Phase 5: window drag, position persistence, manual refresh, collapse/expand
- Phase 6: macOS `.app` wrapper, LaunchAgent plist generation, watchdog/polling refresh

## Run Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall app tests main.py
```

## Smoke Checks

```bash
python3 main.py --smoke-codex
python3 main.py --smoke-claude
python3 main.py --smoke-aggregate
```

The Claude smoke check defaults to a 1-day mtime window and caps reads at 200 files.

## UI

```bash
python3.13 main.py --demo
python3.13 main.py --ui
```

Use `python3.13` for the UI because the current `python3` may not include `_tkinter`.

`python3 main.py --demo` intentionally fails with a clear message when `_tkinter` is unavailable; non-UI smoke checks still work with `python3`.

## macOS App

```bash
python3.13 main.py --install-app --python-executable /Users/chat/miniconda3/bin/python3.13
```

This creates `~/Applications/Codex Monitor.app` by default.

The app wrapper launches `main.py --ui --visible-app` with the selected Python executable. When the login LaunchAgent is already running, the wrapper temporarily unloads `com.local.codex-monitor` so the visible app can acquire the single-instance lock. When the visible app exits, the wrapper restores the LaunchAgent only if it was running before the app was opened.

The wrapper also asks macOS to show `Codex Monitor` with `CodexMonitor.icns`, but the UI is still a Python/Tk app. If macOS ignores the runtime identity update, the Dock may still show Python/Python3 instead of the bundle name; a fully native bundled runtime would be required for a hard guarantee.

## Autostart

```bash
python3.13 main.py --install-autostart
python3.13 main.py --print-launch-agent
python3.13 main.py --uninstall-autostart
```

`--install-autostart` writes `~/Library/LaunchAgents/com.local.codex-monitor.plist` and prints the `launchctl bootstrap` command. It does not execute `launchctl` automatically.

Logs go to:

```text
~/Library/Logs/Codex Monitor/stdout.log
~/Library/Logs/Codex Monitor/stderr.log
```

The LaunchAgent uses hidden floating-widget mode. Double-clicking the `.app` switches to visible app mode; closing it returns to hidden autostart mode when autostart was active before launch.

## Refresh Model

If `watchdog` is installed, the UI listens for local JSONL changes. If it is unavailable, the app falls back to a 5-second mtime poll. File-change detection and aggregate loading run off the tkinter main thread, so the window remains draggable and responsive while data is stale or still loading.

Automatic refreshes are debounced and throttled to at most once every 60 seconds. Manual refresh remains available for on-demand updates. UI refreshes preserve the rolling 30-day view, so watcher-triggered Claude refreshes use the same bounded 30-day scope and `--claude-max-files` cap as the initial UI load; they never trigger an unrestricted scan of `.claude/projects`.

HTTP quota remains intentionally disabled. The app uses local `payload.rate_limits` from Codex logs and does not read `.codex/auth.json`.
