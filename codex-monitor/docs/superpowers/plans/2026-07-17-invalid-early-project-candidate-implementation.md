# Invalid Early Project Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 当 Codex 会话前 200 行只命中不存在的任务名时继续扫描到 1000 行，把主要售后用量归回真实项目，同时保持有效项目的现有快速路径。

**Architecture:** 在共享推断函数中增加可选的早期候选校验回调，默认行为保持兼容；Codex reader 提供基于 `~/claude/<project>/CLAUDE.md` 的校验。聚合层和 JSONL 数据源不变，无法验证的最终候选仍由现有逻辑归入“其他”。

**Tech Stack:** Python 3.13、`unittest`、`unittest.mock`、本地 JSONL reader。

---

### Task 1: 用失败测试固定无效早期候选行为

**Files:**
- Modify: `tests/test_reader_common.py`
- Modify: `tests/test_reader_codex.py`

- [ ] **Step 1: 为共享推断函数添加失败测试**

在 `TestInferProjectSignalWeighting` 中新增：

```python
def test_invalid_early_candidate_extends_to_late_valid_project(self) -> None:
    lines = [
        _codex_line(
            "message",
            "/Users/me/claude/aftersales-confidence-safety-v1/task.md",
        ),
        *[
            _codex_line("function_call_output", "no project signal")
            for _ in range(199)
        ],
        _codex_line(
            "user_message",
            "/Users/me/claude/aftersales-automation/CLAUDE.md",
        ),
    ]
    handle = io.StringIO("\n".join(lines) + "\n")

    result = infer_project_from_handle(
        handle,
        early_candidate_is_valid=lambda project: project == "aftersales-automation",
    )

    self.assertEqual(result, "aftersales-automation")
```

- [ ] **Step 2: 为 Codex reader 的校验接线添加失败测试**

在 `tests/test_reader_codex.py` 顶部导入 `patch`：

```python
from unittest.mock import patch
```

在 `CodexReaderTests` 中新增：

```python
def test_invalid_early_candidate_uses_late_known_project(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rollout.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-07-17T08:00:00.000Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "message",
                        "message": "/Users/me/claude/temporary-task/task.md",
                    },
                }
            ),
            *[
                json.dumps(
                    {
                        "timestamp": "2026-07-17T08:00:00.000Z",
                        "type": "event_msg",
                        "payload": {"type": "function_call_output"},
                    }
                )
                for _ in range(199)
            ],
            json.dumps(
                {
                    "timestamp": "2026-07-17T08:01:00.000Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "user_message",
                        "message": "/Users/me/claude/aftersales-automation/CLAUDE.md",
                    },
                }
            ),
            _token_count_line(
                "2026-07-17T08:02:00.000Z",
                {},
                total_tokens=9,
            ).rstrip("\n"),
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with patch(
            "app.reader_codex._project_metadata_exists",
            side_effect=lambda project: project == "aftersales-automation",
        ):
            result = read_session_file(path)

    self.assertEqual(
        result.usage_events[0].inferred_project,
        "aftersales-automation",
    )
```

- [ ] **Step 3: 运行定向测试并确认按预期失败**

Run:

```bash
python3.13 -m unittest \
  tests.test_reader_common.TestInferProjectSignalWeighting.test_invalid_early_candidate_extends_to_late_valid_project \
  tests.test_reader_codex.CodexReaderTests.test_invalid_early_candidate_uses_late_known_project -v
```

Expected: FAIL/ERROR，原因分别是 `infer_project_from_handle()` 尚不接受 `early_candidate_is_valid`，以及 `app.reader_codex` 尚无 `_project_metadata_exists`。

### Task 2: 实现最小候选校验

**Files:**
- Modify: `app/reader_common.py:5,118-152`
- Modify: `app/reader_codex.py:20-28`

- [ ] **Step 1: 给共享推断函数增加可选回调**

在 `app/reader_common.py` 中导入：

```python
from typing import Callable, Iterable, TextIO
```

将函数签名改为：

```python
def infer_project_from_handle(
    handle: TextIO,
    *,
    max_lines: int | None = None,
    early_candidate_is_valid: Callable[[str], bool] | None = None,
) -> str | None:
```

将 200 行早返回判断改为：

```python
if max_lines is None and i + 1 == initial_limit:
    winner = _unique_project_winner(votes)
    if winner is not None and (
        early_candidate_is_valid is None
        or early_candidate_is_valid(winner)
    ):
        return winner
```

更新 docstring：默认仍分两段扫描；调用方可拒绝无效的 200 行候选，让扫描继续到 1000 行。

- [ ] **Step 2: Codex reader 使用项目说明文件校验候选**

在 `app/reader_codex.py` 中将调用改为：

```python
inferred_project = infer_project_from_handle(
    handle,
    early_candidate_is_valid=_project_metadata_exists,
)
```

在 `_iter_session_files()` 前新增：

```python
def _project_metadata_exists(project: str) -> bool:
    return (Path.home() / "claude" / project / "CLAUDE.md").is_file()
```

- [ ] **Step 3: 运行定向测试并确认通过**

Run:

```bash
python3.13 -m unittest \
  tests.test_reader_common.TestInferProjectSignalWeighting.test_invalid_early_candidate_extends_to_late_valid_project \
  tests.test_reader_codex.CodexReaderTests.test_invalid_early_candidate_uses_late_known_project -v
```

Expected: 2 tests，全部 `ok`。

- [ ] **Step 4: 提交代码和测试**

```bash
git add codex-monitor/app/reader_common.py \
  codex-monitor/app/reader_codex.py \
  codex-monitor/tests/test_reader_common.py \
  codex-monitor/tests/test_reader_codex.py
git commit -m "fix(monitor): reject invalid early project candidates"
```

### Task 3: 同步口径文档并验证真实数据

**Files:**
- Modify: `docs/INDEX.md:78,92`
- Modify: `tasks/todo.md:12-14`

- [ ] **Step 1: 更新稳定口径说明**

在 `docs/INDEX.md` 的项目身份规则中补充：

```markdown
前 200 行的唯一候选只有在对应项目 `CLAUDE.md` 存在时才提前返回；任务名等无效候选必须继续扫描到 1000 行。
```

在已知坑位中记录本次真实案例：无效任务名可在 200 行窗口内形成唯一候选，不能因此阻止后续真实项目信号参与投票。

在 `tasks/todo.md` 的统计准确性观察项中记录该问题已经修复，子代理父会话继承仍不在本次范围。

- [ ] **Step 2: 运行完整验证**

Run:

```bash
python3.13 -m unittest discover -s tests -v
python3.13 -m compileall app tests main.py
python3.13 main.py --smoke-aggregate
```

Expected:

- 全部单元测试通过。
- `compileall` 退出码为 0。
- 真实聚合中主要长会话归入 `aftersales-automation`；总 token 与修复前同一时点相比只允许增加新产生的事件，不允许因归因修复减少。
- `other.today_tokens` 明显下降，剩余子代理会话仍可位于“其他”。

- [ ] **Step 3: 重启常驻 App 并读回运行状态**

先读取单实例锁中的 PID，用 `ps -p <pid>` 确认它属于 Codex Monitor；再停止旧进程并按现有 LaunchAgent 配置启动。重新运行 `--smoke-aggregate`，确认后台进程已加载新代码。

- [ ] **Step 4: 提交文档同步**

```bash
git add codex-monitor/docs/INDEX.md codex-monitor/tasks/todo.md
git commit -m "docs(monitor): record early candidate validation"
```
