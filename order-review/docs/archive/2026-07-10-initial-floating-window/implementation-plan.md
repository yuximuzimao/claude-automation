# Order Review Floating Window Implementation Plan

> Archived on 2026-07-10. This plan has been completed and is kept only as implementation history. Current direction and operating notes live in `../../2026-07-22-approximate-recommendation-direction.md`, `../../../README.md`, and `../../../AGENTS.md`; the completed package-plan requirements are archived at `../2026-07-22-package-plan/requirements.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first read-only desktop floating window for ERP order review, showing the expanded details of the current row whose sequence is `1`.

**Architecture:** Keep ERP reading, domain parsing, simple rule evaluation, and Tkinter UI separate. The reader returns raw DOM text/attributes, the model parser normalizes product rows, rules produce one short judgment line, and UI only renders structured data.

**Tech Stack:** Python 3.13, stdlib `tkinter`, stdlib `urllib`/`socket`/`json` for direct Chrome DevTools access on port `9222`, `pytest` for tests. The CDP shape follows `/Users/chat/claude/aftersales-automation/lib/cdp.js`: list tabs from Chrome HTTP API, execute page JS through `Runtime.evaluate`, and parse JSON return values.

---

### Task 1: Project Skeleton

**Files:**
- Create: `README.md`
- Create: `pyproject.toml`
- Create: `src/order_review/__init__.py`
- Move: `docs/2026-07-09-order-review-floating-window-design.md`

- [x] **Step 1: Create project directories**

Run:

```bash
mkdir -p order-review/docs/superpowers/plans order-review/src/order_review order-review/tests order-review/data
```

Expected: directories exist.

- [x] **Step 2: Move design record into project**

Run:

```bash
mv docs/superpowers/specs/2026-07-09-order-review-floating-window-design.md order-review/docs/2026-07-09-order-review-floating-window-design.md
```

Expected: project owns the design document.

### Task 2: Domain Parser

**Files:**
- Create: `src/order_review/models.py`
- Create: `src/order_review/parser.py`
- Test: `tests/test_parser.py`

- [x] **Step 1: Write failing parser tests**

Create tests covering:

```python
def test_parse_product_title_splits_last_parentheses():
    name, short = split_product_title("KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21（KGOS黑茶 茉莉味）")
    assert name == "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）1g*21"
    assert short == "KGOS黑茶 茉莉味"

def test_parse_platform_ids_distinguishes_spu_and_sku():
    assert parse_platform_ids("平台ID（skuId）： kgoshcml-cx （130292082）") == ("kgoshcml-cx", "130292082")

def test_parse_product_lines_ignores_invalid_fields_and_keeps_quantity():
    product = parse_order_product(SAMPLE_PRODUCT_LINES, {"numiid": "kgoshcml-cx"})
    assert product.short_name == "KGOS黑茶 茉莉味"
    assert product.quantity == 7
    assert product.spu_id == "kgoshcml-cx"
    assert product.sku_id == "130292082"
    assert product.merchant_code == "6979499760044"
```

- [x] **Step 2: Run parser tests and verify they fail**

Run:

```bash
python3.13 -m pytest tests/test_parser.py -v
```

Expected: import errors or missing function failures.

- [x] **Step 3: Implement parser and models**

Implement `Product`, `OrderSnapshot`, `split_product_title`, `parse_platform_ids`, and `parse_order_product`.

- [x] **Step 4: Run parser tests**

Run:

```bash
python3.13 -m pytest tests/test_parser.py -v
```

Expected: tests pass.

### Task 3: Judgment Rules

**Files:**
- Create: `src/order_review/rules.py`
- Test: `tests/test_rules.py`

- [x] **Step 1: Write failing rules tests**

Create tests covering:

```python
def test_unexpanded_order_blocks_reading():
    assert judge(is_expanded=False, products=[]).message == "判断：请先展开订单"

def test_suite_detail_blocks_review():
    product = Product(title="【套件】咖啡", standard_name="咖啡", short_name="咖啡", quantity=1)
    assert judge(is_expanded=True, products=[product], has_suite_action=True).message == "判断：请先套件转单品"

def test_normal_product_can_enter_manual_review():
    product = Product(title="KGOS灵芝金花黑茶固体饮料（KGOS黑茶 茉莉味）", standard_name="KGOS灵芝金花黑茶固体饮料", short_name="KGOS黑茶 茉莉味", quantity=7)
    assert judge(is_expanded=True, products=[product]).message == "判断：可进入人工判断"
```

- [x] **Step 2: Run rules tests and verify they fail**

Run:

```bash
python3.13 -m pytest tests/test_rules.py -v
```

Expected: missing module/function failures.

- [x] **Step 3: Implement minimal rule evaluator**

Implement `Judgment` and `judge`.

- [x] **Step 4: Run rules tests**

Run:

```bash
python3.13 -m pytest tests/test_rules.py -v
```

Expected: tests pass.

### Task 4: ERP Reader

**Files:**
- Create: `src/order_review/cdp.py`
- Create: `src/order_review/erp_reader.py`
- Test: `tests/test_erp_reader.py`

- [x] **Step 1: Write failing tests for generated JavaScript**

Test that the generated JS:

```python
def test_reader_js_targets_sequence_one_and_requires_expanded_row():
    js = build_read_sequence_one_js()
    assert ".module-trade-list-item" in js
    assert "seq(row)==='1'" in js
    assert "module-trade-list-item-open" in js
    assert "tr.order-temp" in js
```

- [x] **Step 2: Run reader JS test and verify it fails**

Run:

```bash
python3.13 -m pytest tests/test_erp_reader.py -v
```

Expected: missing module/function failures.

- [x] **Step 3: Implement CDP target lookup and sequence-one reader**

Implement against Chrome DevTools on `localhost:9222`, matching the售后系统 style:

- `list_targets()`
- `cdp_call()`
- `eval_js()`
- `find_erp_toaudit_target()`
- `build_read_sequence_one_js()`
- `read_sequence_one_order()`

- [x] **Step 4: Run reader tests**

Run:

```bash
python3.13 -m pytest tests/test_erp_reader.py -v
```

Expected: tests pass.

### Task 5: Tkinter UI

**Files:**
- Create: `src/order_review/ui.py`
- Create: `src/order_review/app.py`
- Test: `tests/test_ui_presenter.py`

- [x] **Step 1: Write failing presenter tests**

Test a pure formatting function:

```python
def test_format_sidebar_lines_shows_judgment_and_product_quantity():
    lines = format_sidebar_lines(snapshot)
    assert lines[0] == "判断：可进入人工判断"
    assert "1 种 / 7 件" in lines
    assert "KGOS黑茶 茉莉味 x7" in lines
```

- [x] **Step 2: Run presenter test and verify it fails**

Run:

```bash
python3.13 -m pytest tests/test_ui_presenter.py -v
```

Expected: missing module/function failures.

- [x] **Step 3: Implement presenter and Tk window**

Implement a 320-340px wide always-on-top Tk window with a refresh button and text/list layout.

- [x] **Step 4: Run presenter tests**

Run:

```bash
python3.13 -m pytest tests/test_ui_presenter.py -v
```

Expected: tests pass.

### Task 6: Verification

**Files:**
- All project files.

- [x] **Step 1: Run full tests**

Run:

```bash
python3.13 -m pytest -v
```

Expected: all tests pass.

- [x] **Step 2: Run import smoke**

Run:

```bash
PYTHONPATH=src python3.13 -m order_review.app --help
```

Expected: command prints usage text and exits 0.

- [x] **Step 3: Run real read-only ERP page check**

Run:

```bash
PYTHONPATH=src python3.13 - <<'PY'
from order_review.erp_reader import read_sequence_one_order
from order_review.ui import format_sidebar_lines
snapshot = read_sequence_one_order()
for line in format_sidebar_lines(snapshot):
    print(line)
PY
```

Result on 2026-07-09: direct CDP read succeeded, sequence `1` returned `4 种 / 18 件` and `可合单标记：有`.
