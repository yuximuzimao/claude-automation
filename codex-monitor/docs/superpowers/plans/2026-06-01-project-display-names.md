# Project Display Names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Codex Monitor read Chinese project names from each project's own `CLAUDE.md`, and make that declaration part of new project initialization.

**Architecture:** Keep project identity owned by the project directory. The monitor derives the project slug from `cwd`, reads a small `项目中文名：...` declaration from the nearest project `CLAUDE.md`, and groups undeclared projects into `其他`.

**Tech Stack:** Python 3 standard library, `unittest`, tkinter UI view model, Markdown docs.

---

### Task 1: Project-Owned Display Names

**Files:**
- Modify: `app/aggregate.py`
- Test: `tests/test_aggregate.py`

- [x] **Step 1: Write failing tests**

Add tests that create temporary project directories with `CLAUDE.md`, verify known projects use `项目中文名`, and verify undeclared paths merge into `other` / `其他`.

- [x] **Step 2: Run focused test**

Run: `python3 -m unittest tests.test_aggregate -v`
Expected: FAIL because `aggregate_usage()` does not yet load project metadata from `CLAUDE.md`.

- [x] **Step 3: Implement minimal aggregation support**

Add helpers in `app/aggregate.py` to:
- derive `ProjectIdentity(project, display_name)` from `cwd`
- read `项目中文名：<name>` or `项目中文名: <name>` from `<project>/CLAUDE.md`
- use `other` / `其他` for missing or undeclared projects
- keep at most 3 sample cwd values for tooltips

- [x] **Step 4: Run focused test**

Run: `python3 -m unittest tests.test_aggregate -v`
Expected: PASS.

### Task 2: Remove Deprecated Event Type Surface

**Files:**
- Modify: `app/aggregate.py`
- Modify: `app/ui_tk.py`
- Modify: `main.py`
- Test: `tests/test_ui_tk.py`

- [x] **Step 1: Update tests**

Assert the UI view model no longer exposes `event_types`.

- [x] **Step 2: Run UI tests**

Run: `python3 -m unittest tests.test_ui_tk -v`
Expected: FAIL until UI code stops building/rendering the deprecated section.

- [x] **Step 3: Remove event type model/rendering**

Delete `EventTypeTotal`, `UsageAggregate.event_types`, `infer_event_type()`, `_event_type_view()`, and `_event_types()` rendering.

- [x] **Step 4: Run aggregate and UI tests**

Run: `python3 -m unittest tests.test_aggregate tests.test_ui_tk -v`
Expected: PASS.

### Task 3: UI Cleanup From Claude Feedback

**Files:**
- Modify: `app/ui_tk.py`
- Modify: `tests/test_ui_tk.py`

- [x] **Step 1: Write view-model/UI tests**

Assert quota values include `已用`, and project summary totals remain available in the view model without the old summary card rendering.

- [x] **Step 2: Run UI tests**

Run: `python3 -m unittest tests.test_ui_tk -v`
Expected: FAIL until quota labels and UI structure are adjusted.

- [x] **Step 3: Adjust UI**

Remove the `余额限额` title, enlarge the two quota boxes visually, and remove the `项目消耗` summary card from `_build()`.

- [x] **Step 4: Run UI tests**

Run: `python3 -m unittest tests.test_ui_tk -v`
Expected: PASS.

### Task 4: Initialization Docs

**Files:**
- Modify: `../docs/new-project-template.md`
- Modify: `docs/INDEX.md`
- Modify: current project `CLAUDE.md` files that should have explicit display names

- [x] **Step 1: Update project initialization template**

Add `项目中文名：<中文名>` directly under the top-level project title in the required `CLAUDE.md` template.

- [x] **Step 2: Update Codex Monitor rules**

Document that Chinese names are owned by project `CLAUDE.md`; monitor-side mappings are not the primary path.

- [x] **Step 3: Add current project declarations**

Add `项目中文名：...` near the top of relevant project `CLAUDE.md` files so the monitor can display useful names immediately.

### Task 5: Verification

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
