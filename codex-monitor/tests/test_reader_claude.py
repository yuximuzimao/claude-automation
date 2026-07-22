from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.reader_claude import read_claude_projects, read_claude_session_file


FIXTURES = Path(__file__).parent / "fixtures"


class ClaudeReaderTests(unittest.TestCase):
    def test_reads_usage_by_dynamic_model_and_preserves_cache_breakdown(self) -> None:
        result = read_claude_session_file(FIXTURES / "claude_session.jsonl")

        self.assertEqual(result.assistant_events, 3)
        self.assertEqual(result.cwd, "/Users/chat/claude/codex-monitor")
        self.assertEqual(result.by_model["claude-sonnet-4-6"].input_tokens, 1000)
        self.assertEqual(
            result.by_model["claude-sonnet-4-6"].cache_creation_input_tokens,
            300,
        )
        self.assertEqual(
            result.by_model["claude-sonnet-4-6"].cache_read_input_tokens,
            400,
        )
        self.assertEqual(
            result.by_model["claude-sonnet-4-6"].cache_creation_ephemeral_5m_input_tokens,
            120,
        )
        self.assertEqual(
            result.by_model["claude-sonnet-4-6"].cache_creation_ephemeral_1h_input_tokens,
            180,
        )
        self.assertEqual(result.by_model["deepseek-v4-flash"].total_estimated_tokens, 550)
        self.assertEqual(result.by_model["<synthetic>"].total_estimated_tokens, 22)

    def test_missing_model_uses_missing_bucket_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-31T09:20:00.000Z",
                        "type": "assistant",
                        "cwd": "/Users/chat/claude/unknown",
                        "message": {
                            "usage": {
                                "input_tokens": 7,
                                "output_tokens": 3,
                            }
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_claude_session_file(path)

        self.assertEqual(result.by_model["<missing>"].input_tokens, 7)
        self.assertEqual(result.by_model["<missing>"].output_tokens, 3)

    def test_tool_result_project_list_does_not_infer_workspace_root_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "message": {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "toolu_1",
                                    "content": (
                                        "/Users/chat/claude/douyin-workout/CLAUDE.md\n"
                                        "/Users/chat/claude/douyin-workout/SKILL.md"
                                    ),
                                }
                            ],
                        },
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-07-07T12:11:18.975Z",
                        "type": "assistant",
                        "cwd": "/Users/chat/claude",
                        "message": {
                            "model": "claude-sonnet-4-6",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_claude_session_file(path)

        self.assertIsNone(result.usage_events[0].inferred_project)

    def test_local_tool_input_assigns_root_event_to_unique_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-22T08:00:00.000Z",
                        "type": "assistant",
                        "cwd": "/Users/chat/claude",
                        "message": {
                            "model": "claude-sonnet-4-6",
                            "usage": {"input_tokens": 10, "output_tokens": 5},
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {
                                        "file_path": (
                                            "/Users/chat/claude/codex-monitor/"
                                            "README.md"
                                        )
                                    },
                                }
                            ],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_claude._project_metadata_exists",
                side_effect=lambda project: project == "codex-monitor",
            ):
                result = read_claude_session_file(path)

        self.assertEqual(result.usage_events[0].inferred_project, "codex-monitor")

    def test_workspace_root_events_between_one_project_are_backfilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            rows = []
            for index, cwd in enumerate(
                [
                    "/Users/chat/claude",
                    "/Users/chat/claude/aftersales-automation",
                    "/Users/chat/claude",
                    "/Users/chat/claude/aftersales-automation",
                    "/Users/chat/claude",
                ]
            ):
                rows.append(
                    json.dumps(
                        {
                            "timestamp": f"2026-07-22T08:00:0{index}.000Z",
                            "type": "assistant",
                            "cwd": cwd,
                            "message": {
                                "id": f"msg-{index}",
                                "model": "claude-sonnet-4-6",
                                "usage": {"input_tokens": 10, "output_tokens": 5},
                            },
                        }
                    )
                )
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")

            with patch(
                "app.reader_claude._project_metadata_exists",
                side_effect=lambda project: project == "aftersales-automation",
            ):
                result = read_claude_session_file(path)

        self.assertEqual(
            [event.inferred_project for event in result.usage_events],
            [None, None, "aftersales-automation", None, None],
        )

    def test_workspace_root_events_are_not_backfilled_across_two_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            rows = []
            for index, cwd in enumerate(
                [
                    "/Users/chat/claude/aftersales-automation",
                    "/Users/chat/claude",
                    "/Users/chat/claude/codex-monitor",
                ]
            ):
                rows.append(
                    json.dumps(
                        {
                            "timestamp": f"2026-07-22T08:00:0{index}.000Z",
                            "type": "assistant",
                            "cwd": cwd,
                            "message": {
                                "id": f"msg-{index}",
                                "model": "claude-sonnet-4-6",
                                "usage": {"input_tokens": 10, "output_tokens": 5},
                            },
                        }
                    )
                )
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")

            with patch(
                "app.reader_claude._project_metadata_exists",
                side_effect=lambda project: project
                in {"aftersales-automation", "codex-monitor"},
            ):
                result = read_claude_session_file(path)

        self.assertIsNone(result.usage_events[1].inferred_project)

    def test_duplicate_assistant_message_id_counts_usage_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            message = {
                "id": "msg-1",
                "model": "claude-sonnet-4-6",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-07T12:11:18.975Z",
                        "type": "assistant",
                        "cwd": "/Users/chat/claude/codex-monitor",
                        "message": message,
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "timestamp": "2026-07-07T12:11:19.330Z",
                        "type": "assistant",
                        "cwd": "/Users/chat/claude/codex-monitor",
                        "message": message,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_claude_session_file(path)

        self.assertEqual(result.assistant_events, 1)
        self.assertEqual(result.by_model["claude-sonnet-4-6"].total_estimated_tokens, 15)
        self.assertEqual(len(result.usage_events), 1)

    def test_bad_json_line_is_counted_without_exposing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.jsonl"
            path.write_text(
                "{bad-json\n"
                + json.dumps(
                    {
                        "type": "assistant",
                        "cwd": "/Users/chat/claude/codex-monitor",
                        "message": {
                            "model": "mimo-v2.5-pro",
                            "usage": {"input_tokens": 1, "output_tokens": 2},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_claude_session_file(path)

        self.assertEqual(result.parse_errors, 1)
        self.assertEqual(result.by_model["mimo-v2.5-pro"].total_estimated_tokens, 3)

    def test_scan_root_includes_subagents_and_filters_by_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "-Users-chat-claude" / "session-uuid"
            subagent_dir = session_dir / "subagents"
            subagent_dir.mkdir(parents=True)
            fixture_text = (FIXTURES / "claude_session.jsonl").read_text(
                encoding="utf-8"
            )
            main_file = session_dir / "main.jsonl"
            subagent_file = subagent_dir / "agent-a.jsonl"
            old_file = root / "-Users-chat-old" / "old.jsonl"
            old_file.parent.mkdir(parents=True)
            main_file.write_text(fixture_text, encoding="utf-8")
            subagent_file.write_text(fixture_text, encoding="utf-8")
            old_file.write_text(fixture_text, encoding="utf-8")
            os.utime(old_file, (1000, 1000))

            result = read_claude_projects(root, modified_since=2000)

        self.assertEqual(result.file_count, 2)
        self.assertEqual(result.assistant_events, 6)
        self.assertEqual(result.by_model["<synthetic>"].total_estimated_tokens, 44)
        self.assertEqual(result.by_model["claude-sonnet-4-6"].input_tokens, 2000)


if __name__ == "__main__":
    unittest.main()
