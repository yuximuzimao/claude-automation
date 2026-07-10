---
name: codex-monitor
description: Work on the local Codex/Claude usage monitor. Use when changing JSONL readers, token aggregation, quota display, UI behavior, or project docs for /Users/chat/claude/codex-monitor.
---

# Codex Monitor Skill

## Scope

This project builds a local monitor for Codex and Claude Code usage from local JSONL logs.

## Required Context

Read these first:

1. `tasks/todo.md`
2. `docs/INDEX.md`
3. `docs/FUTURE.md` only when discussing native macOS UI or material migration
4. Relevant handoff files in `../docs/codex-handoff/` when changing approved scope

## Hard Rules

- Do not read `.codex/auth.json` for MVP work.
- Do not call `chatgpt.com/backend-api/wham/usage` for MVP work.
- Do not output conversation content from JSONL files.
- Do not scan all of `/Users/chat/.claude/projects` from the UI thread.
- Do not run JSONL reading, aggregation, or recursive mtime scans on the tkinter main thread.
- Keep automatic UI refreshes debounced, coalesced, and throttled; prefer stale data over a frozen window or sustained CPU burn.
- Preserve token breakdown fields even when UI displays only totals.

## Verification

Run before reporting completion:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall app tests main.py
python3 main.py --smoke-aggregate
```

Use `python3.13 main.py --demo` or `python3.13 main.py --ui` for manual UI verification.
