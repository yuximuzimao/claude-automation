# macOS Blur Window Implementation Plan

> **归档状态（2026-07-10）：** 该计划已被后续实现吸收，不再作为待执行清单。当前稳定规则以 `docs/INDEX.md` 为准；原生 macOS 材质迁移只作为 `docs/FUTURE.md` 中的长期方向。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Codex Monitor's rectangular translucent background with a macOS native rounded blur window and simplify expanded controls.

**Architecture:** Keep tkinter for all content and use a small AppKit bridge for the window background only. UI choices that can be tested without a display stay in pure helper functions; the AppKit bridge fails closed so the monitor still opens on unsupported Tk/macOS combinations.

**Tech Stack:** Python 3.13, tkinter, ctypes Objective-C calls into AppKit, unittest.

---

### Task 1: Lock Visual Decisions In Tests

**Files:**
- Modify: `tests/test_ui_tk.py`
- Modify: `app/ui_tk.py`

- [ ] Add tests for native blur config, unified toolbar symbols, no collapsed panel layer, and no footer text buttons.
- [ ] Run `python3.13 -m unittest tests.test_ui_tk -v` and confirm the new tests fail before implementation.

### Task 2: Add macOS Native Blur Bridge

**Files:**
- Modify: `app/ui_tk.py`

- [ ] Add `_macos_blur_config()` and `_install_macos_blur(root, radius)` helpers.
- [ ] Call the bridge after geometry is built and on rebuilds.
- [ ] Keep fallback behavior when AppKit access fails.

### Task 3: Simplify Expanded And Collapsed Chrome

**Files:**
- Modify: `app/ui_tk.py`
- Modify: `tests/test_ui_tk.py`

- [ ] Make the outer container transparent in both modes.
- [ ] Remove the collapsed white rounded panel layer.
- [ ] Move refresh and collapse controls to the top-left toolbar.
- [ ] Use `><` as the expanded-state collapse symbol.
- [ ] Remove the footer text buttons.

### Task 4: Verify

**Files:**
- Modify: runtime state only as needed for manual screenshots.

- [ ] Run `python3.13 -m unittest discover -s tests -v`.
- [ ] Run `python3.13 -m compileall app tests`.
- [ ] Restart `com.local.codex-monitor`.
- [ ] Capture screenshots for expanded and collapsed states and inspect rounded blur, toolbar positions, and text readability.
