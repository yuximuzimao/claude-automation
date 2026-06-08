# Text Correction Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small evaluation script that tests whether text can correct YOLO dense-count misses without overriding concrete visual flavor/spec recognition.

**Architecture:** Add `scripts/ocr_verify.py` as an evaluation-only module. It reuses `scripts.nms_sweep` for ERP standard names, expected parsing, YOLO counting, and metrics, then adds text parsing and a YOLO-first merge policy.

**Tech Stack:** Python 3.10/3.14 compatible stdlib, `collections.Counter`, existing `ultralytics` only when running YOLO inference in the conda `yolov8` environment.

---

### Task 1: Lock Text-Correction Semantics

**Files:**
- Create: `tests/test_ocr_verify.py`
- Create: `scripts/ocr_verify.py`

- [ ] **Step 1: Write failing tests**

Create tests for three behaviors:
- `玉米片 10` plus YOLO detecting two concrete corn-chip flavors becomes each flavor 5.
- `玉米片 10` without concrete YOLO flavor evidence produces no concrete ERP item.
- Exact text such as `腰围卡尺 1` maps directly to the ERP standard name.

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -m unittest tests.test_ocr_verify -v`
Expected: FAIL because `scripts.ocr_verify` does not exist yet.

- [ ] **Step 3: Implement minimal parser and merge policy**

Create `scripts/ocr_verify.py` with:
- `parse_text_counts(text)`
- `merge_text_corrections(yolo_counts, text_counts)`
- group rules for ambiguous categories such as `玉米片`.

- [ ] **Step 4: Run tests and verify pass**

Run: `python3 -m unittest tests.test_ocr_verify -v`
Expected: PASS.

### Task 2: Add Gift13 Evaluation CLI

**Files:**
- Modify: `scripts/ocr_verify.py`

- [ ] **Step 1: Add CLI tests if report rendering has non-trivial branching**

Keep CLI thin if possible; unit-test functions instead of subprocess output.

- [ ] **Step 2: Implement `--model`, `--text-report`, `--output` CLI**

Use train7 by default and output `docs/text-correction-gift13-report.md`.

- [ ] **Step 3: Run gift13 evaluation**

Run:
`/Users/chat/miniconda3/envs/yolov8/bin/python scripts/ocr_verify.py --model runs/kgos_yolov8s_train7/weights/best.pt`

Expected: markdown report with YOLO-only, text-only, and YOLO+text metrics.

### Task 3: Document Result

**Files:**
- Modify: `tasks/todo.md`
- Optionally create: `docs/text-correction-gift13-report.md`

- [ ] **Step 1: Record whether text correction improved dense-count recall**
- [ ] **Step 2: Keep production ONNX untouched**
- [ ] **Step 3: Run targeted tests**

Run:
`python3 -m unittest tests.test_ocr_verify tests.test_nms_sweep -v`

