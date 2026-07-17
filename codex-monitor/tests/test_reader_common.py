"""Regression tests for infer_project_from_handle() in reader_common."""

from __future__ import annotations

import io
import json
import unittest

from app.reader_common import infer_project_from_handle


def _codex_line(sub_type: str, text: str = "") -> str:
    """Build a minimal Codex JSONL line with the given payload.type and embedded text."""
    return json.dumps({
        "timestamp": "2026-06-04T00:00:00.000Z",
        "type": "event_msg",
        "payload": {"type": sub_type, "message": text},
    })


def _codex_session_meta(cwd: str) -> str:
    return json.dumps({
        "timestamp": "2026-06-04T00:00:00.000Z",
        "type": "session_meta",
        "payload": {"cwd": cwd},
    })


def _claude_line(event_type: str, text: str = "") -> str:
    """Build a minimal Claude Code JSONL line with the given type."""
    return json.dumps({"type": event_type, "message": {"content": text}})


def _claude_tool_result_line(text: str) -> str:
    return json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": text,
                }
            ],
        },
    })


def _claude_hook_line(text: str) -> str:
    return json.dumps({
        "attachment": {
            "type": "hook_system_message",
            "content": text,
        }
    })


class TestInferProjectNoisePollution(unittest.TestCase):
    """Core regression: Codex tool outputs must not override real signal."""

    def test_function_call_output_does_not_win_over_message_signal(self) -> None:
        """59 aftersales paths in function_call_output must not beat 1 message path."""
        aftersales_path = "/Users/chat/claude/aftersales-automation/data"
        monitor_path = "/Users/chat/claude/codex-monitor/app"

        lines = [
            # Real signal: 1 mention in a model message
            _codex_line("message", f"Reading {monitor_path}/reader_common.py"),
            # Noise: 59 mentions in tool output
            _codex_line("function_call_output", " ".join([aftersales_path] * 59)),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_function_call_output_skipped_entirely(self) -> None:
        """function_call_output lines contribute zero votes."""
        lines = [
            _codex_line("function_call_output", "/Users/me/claude/aftersales-automation/x"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)

    def test_function_call_skipped_entirely(self) -> None:
        """function_call (tool invocation) lines contribute zero votes."""
        lines = [
            _codex_line("function_call", "/Users/me/claude/product-mapping/foo"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)

    def test_token_count_skipped_entirely(self) -> None:
        """token_count lines contribute zero votes."""
        lines = [
            _codex_line("token_count", "/Users/me/claude/aftersales-automation/billing"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)


class TestInferProjectSignalWeighting(unittest.TestCase):
    """user_message/user events should win over generic signal lines."""

    def test_user_message_outweighs_multiple_message_lines(self) -> None:
        """1 user_message (5x) should beat 4 plain message lines (1x each) for a different project."""
        lines = [
            # 4 message lines for aftersales → 4 votes
            _codex_line("message", "/Users/me/claude/aftersales-automation/x"),
            _codex_line("message", "/Users/me/claude/aftersales-automation/y"),
            _codex_line("message", "/Users/me/claude/aftersales-automation/z"),
            _codex_line("message", "/Users/me/claude/aftersales-automation/w"),
            # 1 user_message for codex-monitor → 5 votes
            _codex_line("user_message", "check /Users/me/claude/codex-monitor status"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_session_meta_counts_as_signal(self) -> None:
        """session_meta lines (weight 1) contribute to voting."""
        lines = [
            _codex_session_meta("/Users/me/claude/codex-monitor"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_tied_weak_project_signals_return_none(self) -> None:
        """Tied generic mentions should not arbitrarily pick the first project."""
        lines = [
            _codex_line("message", "/Users/me/claude/product-detect/train.py"),
            _codex_line("message", "/Users/me/claude/codex-monitor/app/ui_tk.py"),
            _codex_line("agent_message", "/Users/me/claude/product-detect/runs"),
            _codex_line("agent_message", "/Users/me/claude/codex-monitor/tests"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)

    def test_shared_workspace_dirs_do_not_count_as_projects(self) -> None:
        lines = [
            _codex_line("user_message", "/Users/me/claude/docs/codex-handoff/plan.md"),
            _codex_line("message", "/Users/me/claude/scripts/helper.py"),
            _codex_line("message", "/Users/me/claude/reviews/weekly/2026-W28.md"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")

        self.assertIsNone(infer_project_from_handle(handle))

    def test_default_scan_extends_for_late_project_signal(self) -> None:
        lines = [
            _codex_line("function_call_output", "no project signal")
            for _ in range(473)
        ]
        lines.append(
            _codex_line("user_message", "/Users/me/claude/order-review/src/order_review/app.py")
        )
        handle = io.StringIO("\n".join(lines) + "\n")

        self.assertEqual(infer_project_from_handle(handle), "order-review")

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


class TestInferProjectClaudeCodeFormat(unittest.TestCase):
    """Claude Code JSONL (no payload dict) should work correctly."""

    def test_claude_user_event_gets_5x_weight(self) -> None:
        """Claude Code 'user' events should win over 4 'assistant' events for a different project."""
        lines = [
            # 4 assistant lines for aftersales → 4 votes
            _claude_line("assistant", "/Users/me/claude/aftersales-automation/a"),
            _claude_line("assistant", "/Users/me/claude/aftersales-automation/b"),
            _claude_line("assistant", "/Users/me/claude/aftersales-automation/c"),
            _claude_line("assistant", "/Users/me/claude/aftersales-automation/d"),
            # 1 user line for codex-monitor → 5 votes
            _claude_line("user", "let's fix /Users/me/claude/codex-monitor/app/reader_common.py"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_claude_assistant_events_participate_normally(self) -> None:
        """Claude Code 'assistant' events should count at weight 1."""
        lines = [
            _claude_line("assistant", "Reading /Users/me/claude/codex-monitor/app/aggregate.py"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_claude_tool_results_do_not_count_as_user_intent(self) -> None:
        """Claude Code tool_result payloads are tool output, not human project intent."""
        lines = [
            _claude_tool_result_line(
                "/Users/me/claude/douyin-workout/CLAUDE.md "
                "/Users/me/claude/douyin-workout/SKILL.md"
            ),
            _claude_line("user", "检查 /Users/me/claude/codex-monitor 的统计逻辑"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_claude_session_hooks_do_not_count_as_project_signal(self) -> None:
        """SessionStart hook context can mention many projects and should not drive attribution."""
        lines = [
            _claude_hook_line("/Users/me/claude/douyin-workout/CLAUDE.md " * 20),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)

    def test_inference_skip_set_excludes_projects(self) -> None:
        """'projects' is in _INFERENCE_SKIP and is never returned as a project name."""
        # /claude/projects matches the regex but is skipped; codex-monitor also present
        lines = [
            _claude_line("user", "/Users/me/claude/projects/old and /Users/me/claude/codex-monitor/app"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")


class TestInferProjectEdgeCases(unittest.TestCase):
    def test_empty_file_returns_none(self) -> None:
        result = infer_project_from_handle(io.StringIO(""))
        self.assertIsNone(result)

    def test_all_noise_returns_none(self) -> None:
        """If every line is noise, result is None (falls through to 'other')."""
        lines = [
            _codex_line("function_call_output", "/Users/me/claude/aftersales-automation/x " * 20),
            _codex_line("function_call", "/Users/me/claude/product-mapping/y " * 10),
            _codex_line("token_count", "/Users/me/claude/transfer/z " * 5),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertIsNone(result)

    def test_invalid_json_lines_are_skipped(self) -> None:
        """Malformed JSON lines don't crash and don't vote."""
        lines = [
            "{not-json",
            _codex_line("message", "/Users/me/claude/codex-monitor/ok"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle)
        self.assertEqual(result, "codex-monitor")

    def test_max_lines_limit_respected(self) -> None:
        """Lines beyond max_lines are not scanned."""
        # First 3 lines: noise pointing at aftersales
        # Line 4 (index 3): real signal for codex-monitor — should be ignored with max_lines=3
        lines = [
            _codex_line("function_call_output", "/Users/me/claude/aftersales-automation/x"),
            _codex_line("function_call_output", "/Users/me/claude/aftersales-automation/y"),
            _codex_line("function_call_output", "/Users/me/claude/aftersales-automation/z"),
            _codex_line("message", "/Users/me/claude/codex-monitor/app"),
        ]
        handle = io.StringIO("\n".join(lines) + "\n")
        result = infer_project_from_handle(handle, max_lines=3)
        # All 3 scanned lines are noise → None
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
