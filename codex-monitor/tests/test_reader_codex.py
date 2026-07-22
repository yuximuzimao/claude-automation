from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.reader_codex import read_codex_sessions, read_session_file


FIXTURES = Path(__file__).parent / "fixtures"


class CodexReaderTests(unittest.TestCase):
    def test_reads_payload_rate_limits_and_five_token_fields(self) -> None:
        result = read_session_file(FIXTURES / "codex_session.jsonl")

        self.assertEqual(result.cwd, "/Users/chat/claude/codex-monitor")
        self.assertEqual(result.token_count_events, 2)
        self.assertEqual(result.latest_quota.primary.used_percent, 13.0)
        self.assertEqual(result.latest_quota.primary.resets_at, 1780258920)
        self.assertEqual(result.latest_quota.secondary.window_minutes, 10080)
        self.assertEqual(result.latest_quota.timestamp, "2026-05-31T10:02:00.000Z")
        self.assertEqual(result.last_usage_total.input_tokens, 150)
        self.assertEqual(result.last_usage_total.cached_input_tokens, 50)
        self.assertEqual(result.last_usage_total.output_tokens, 50)
        self.assertEqual(result.last_usage_total.reasoning_output_tokens, 12)
        self.assertEqual(result.last_usage_total.total_tokens, 200)
        self.assertEqual(result.latest_total_usage.total_tokens, 200)

    def test_missing_rate_limits_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-05-31T11:00:00.000Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "last_token_usage": {"total_tokens": 9},
                                "total_token_usage": {"total_tokens": 9},
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_session_file(path)

        self.assertEqual(result.token_count_events, 1)
        self.assertIsNone(result.latest_quota)
        self.assertEqual(result.last_usage_total.total_tokens, 9)

    def test_incomplete_newer_quota_does_not_replace_displayable_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout-a.jsonl"
            path.write_text(
                _token_count_line(
                    "2026-05-31T11:00:00.000Z",
                    {
                        "primary": {"used_percent": 35.0, "window_minutes": 300},
                        "secondary": {"used_percent": 71.0, "window_minutes": 10080},
                    },
                    total_tokens=9,
                )
                + _token_count_line(
                    "2026-05-31T11:05:00.000Z",
                    {
                        "primary": {"window_minutes": 300},
                        "secondary": {"window_minutes": 10080},
                    },
                    total_tokens=12,
                ),
                encoding="utf-8",
            )

            result = read_session_file(path)

        self.assertIsNotNone(result.latest_quota)
        self.assertEqual(result.latest_quota.timestamp, "2026-05-31T11:00:00.000Z")
        self.assertEqual(result.latest_quota.primary.used_percent, 35.0)
        self.assertEqual(result.latest_quota.secondary.used_percent, 71.0)
        self.assertEqual(result.token_count_events, 2)

    def test_scan_uses_older_displayable_quota_over_newer_empty_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "2026" / "05" / "31"
            session_dir.mkdir(parents=True)
            (session_dir / "rollout-a.jsonl").write_text(
                _token_count_line(
                    "2026-05-31T11:00:00.000Z",
                    {
                        "primary": {"used_percent": 35.0, "window_minutes": 300},
                        "secondary": {"used_percent": 71.0, "window_minutes": 10080},
                    },
                    total_tokens=9,
                ),
                encoding="utf-8",
            )
            (session_dir / "rollout-b.jsonl").write_text(
                _token_count_line(
                    "2026-05-31T11:05:00.000Z",
                    {
                        "primary": {"window_minutes": 300},
                        "secondary": {"window_minutes": 10080},
                    },
                    total_tokens=12,
                ),
                encoding="utf-8",
            )

            result = read_codex_sessions(root)

        latest_quota = result.latest_quota()
        self.assertIsNotNone(latest_quota)
        self.assertEqual(latest_quota.timestamp, "2026-05-31T11:00:00.000Z")
        self.assertEqual(latest_quota.primary.used_percent, 35.0)

    def test_bad_json_line_is_counted_without_exposing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        "{not-json",
                        json.dumps(
                            {
                                "timestamp": "2026-05-31T11:01:00.000Z",
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "last_token_usage": {"total_tokens": 3},
                                        "total_token_usage": {"total_tokens": 3},
                                    },
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = read_session_file(path)

        self.assertEqual(result.parse_errors, 1)
        self.assertEqual(result.last_usage_total.total_tokens, 3)

    def test_scan_root_sums_sessions_and_uses_latest_quota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "2026" / "05" / "31"
            session_dir.mkdir(parents=True)
            fixture_text = (FIXTURES / "codex_session.jsonl").read_text(
                encoding="utf-8"
            )
            (session_dir / "rollout-a.jsonl").write_text(fixture_text, encoding="utf-8")
            (session_dir / "rollout-b.jsonl").write_text(fixture_text, encoding="utf-8")

            result = read_codex_sessions(root)

        self.assertEqual(len(result.sessions), 2)
        self.assertEqual(result.token_count_events, 4)
        self.assertEqual(result.last_usage_total.total_tokens, 400)
        self.assertEqual(result.latest_quota().primary.used_percent, 13.0)

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

    def test_root_session_assigns_each_turn_from_actual_tool_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            lines = [
                _session_meta_line(
                    "parent",
                    cwd="/Users/chat",
                    timestamp="2026-07-22T08:00:00.000Z",
                ),
                _event_line("user_message", "检查售后流程"),
                _token_count_line(
                    "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                ).rstrip("\n"),
                _custom_exec_line(
                    "/Users/chat/.config/superpowers/worktrees/claude/"
                    "aftersales-confidence-safety-v1/aftersales-automation"
                ),
                _token_count_line(
                    "2026-07-22T08:00:02.000Z", {}, total_tokens=20
                ).rstrip("\n"),
                _event_line("user_message", "检查用量统计"),
                _token_count_line(
                    "2026-07-22T08:01:01.000Z", {}, total_tokens=30
                ).rstrip("\n"),
                _custom_exec_line("/Users/chat/claude/codex-monitor"),
                _token_count_line(
                    "2026-07-22T08:01:02.000Z", {}, total_tokens=40
                ).rstrip("\n"),
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project
                in {"aftersales-automation", "codex-monitor"},
            ):
                result = read_session_file(path)

        self.assertEqual(
            [event.inferred_project for event in result.usage_events],
            [
                "aftersales-automation",
                "aftersales-automation",
                "codex-monitor",
                "codex-monitor",
            ],
        )

    def test_nested_exec_uses_unquoted_workdir_as_strong_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "检查统计"),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "custom_tool_call",
                                    "name": "exec",
                                    "input": (
                                        "await tools.exec_command({"
                                        "cmd: 'python3.13 main.py', "
                                        "workdir: '/Users/chat/claude/codex-monitor'"
                                        "})"
                                    ),
                                },
                            }
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "codex-monitor",
            ):
                result = read_session_file(path)

        self.assertEqual(result.usage_events[0].inferred_project, "codex-monitor")

    def test_nested_exec_uses_unique_verified_project_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "检查统计"),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "custom_tool_call",
                                    "name": "exec",
                                    "input": (
                                        "await tools.exec_command({cmd: "
                                        "'sed -n 1,80p "
                                        "/Users/chat/claude/codex-monitor/README.md'})"
                                    ),
                                },
                            }
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "codex-monitor",
            ):
                result = read_session_file(path)

        self.assertEqual(result.usage_events[0].inferred_project, "codex-monitor")

    def test_declared_legacy_path_maps_to_current_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "继续处理语音工具"),
                        _custom_exec_line("/Users/chat/phone-voice-paste"),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "voice-retrieval",
            ):
                result = read_session_file(
                    path,
                    project_aliases={
                        "/Users/chat/phone-voice-paste": "voice-retrieval"
                    },
                )

        self.assertEqual(result.usage_events[0].inferred_project, "voice-retrieval")

    def test_coordination_tool_path_is_not_project_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "安排下一步"),
                        json.dumps(
                            {
                                "type": "event_msg",
                                "payload": {
                                    "type": "function_call",
                                    "name": "update_plan",
                                    "arguments": json.dumps(
                                        {
                                            "note": (
                                                "/Users/chat/claude/codex-monitor"
                                            )
                                        }
                                    ),
                                },
                            }
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "codex-monitor",
            ):
                result = read_session_file(path)

        self.assertIsNone(result.usage_events[0].inferred_project)

    def test_placeholder_project_path_is_not_treated_as_real_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line(
                            "agent_message",
                            "示例：/Users/chat/claude/某项目/src",
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists", return_value=False
            ):
                result = read_session_file(path)

        self.assertIsNone(result.usage_events[0].inferred_project)

    def test_subagent_inherits_confirmed_parent_turn_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / "rollout-parent.jsonl"
            child = root / "rollout-child.jsonl"
            parent.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "处理售后任务"),
                        _custom_exec_line(
                            "/Users/chat/claude/aftersales-automation"
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:02.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            child.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "child",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:03.000Z",
                            thread_source="subagent",
                            parent_thread_id="parent",
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:04.000Z", {}, total_tokens=20
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "aftersales-automation",
            ):
                result = read_codex_sessions(root)

        child_result = next(
            session for session in result.sessions if session.path.name == child.name
        )
        self.assertEqual(
            child_result.usage_events[0].inferred_project,
            "aftersales-automation",
        )

    def test_deleted_worktree_short_path_uses_unique_logged_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "rollout-evidence.jsonl"
            later = root / "rollout-later.jsonl"
            evidence.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "evidence",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "创建隔离任务"),
                        _custom_exec_line(
                            "/Users/chat/.config/superpowers/worktrees/claude/"
                            "aftersales-confidence-safety-v1/aftersales-automation"
                        ),
                        _token_count_line(
                            "2026-07-22T08:00:02.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            later.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "later",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T09:00:00.000Z",
                        ),
                        _event_line(
                            "user_message",
                            "继续处理 /Users/chat/claude/"
                            "aftersales-confidence-safety-v1",
                        ),
                        _token_count_line(
                            "2026-07-22T09:00:01.000Z", {}, total_tokens=20
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "aftersales-automation",
            ):
                result = read_codex_sessions(root)

        later_result = next(
            session for session in result.sessions if session.path.name == later.name
        )
        self.assertEqual(
            later_result.usage_events[0].inferred_project,
            "aftersales-automation",
        )

    def test_neat_turn_backfills_unknown_single_project_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "先讨论实现方案"),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                        _event_line("user_message", "/neat"),
                        _custom_exec_line("/Users/chat/claude/codex-monitor"),
                        _token_count_line(
                            "2026-07-22T09:00:01.000Z", {}, total_tokens=20
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project == "codex-monitor",
            ):
                result = read_session_file(path)

        self.assertEqual(
            [event.inferred_project for event in result.usage_events],
            ["codex-monitor", "codex-monitor"],
        )

    def test_neat_turn_corrects_stale_inherited_project_without_turn_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "child",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                            thread_source="subagent",
                            parent_thread_id="parent",
                        ),
                        _event_line("user_message", "开始处理新任务"),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                        _event_line("user_message", "/neat"),
                        _custom_exec_line("/Users/chat/claude/codex-monitor"),
                        _token_count_line(
                            "2026-07-22T09:00:01.000Z", {}, total_tokens=20
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project
                in {"aftersales-automation", "codex-monitor"},
            ):
                result = read_session_file(
                    path,
                    inherited_project="aftersales-automation",
                )

        self.assertEqual(
            [event.inferred_project for event in result.usage_events],
            ["codex-monitor", "codex-monitor"],
        )

    def test_neat_turn_does_not_overwrite_confirmed_cross_project_turns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rollout.jsonl"
            path.write_text(
                "\n".join(
                    [
                        _session_meta_line(
                            "parent",
                            cwd="/Users/chat",
                            timestamp="2026-07-22T08:00:00.000Z",
                        ),
                        _event_line("user_message", "先讨论"),
                        _token_count_line(
                            "2026-07-22T08:00:01.000Z", {}, total_tokens=5
                        ).rstrip("\n"),
                        _event_line("user_message", "处理售后"),
                        _custom_exec_line(
                            "/Users/chat/claude/aftersales-automation"
                        ),
                        _token_count_line(
                            "2026-07-22T09:00:01.000Z", {}, total_tokens=10
                        ).rstrip("\n"),
                        _event_line("user_message", "/neat"),
                        _custom_exec_line("/Users/chat/claude/codex-monitor"),
                        _token_count_line(
                            "2026-07-22T10:00:01.000Z", {}, total_tokens=20
                        ).rstrip("\n"),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "app.reader_codex._project_metadata_exists",
                side_effect=lambda project: project
                in {"aftersales-automation", "codex-monitor"},
            ):
                result = read_session_file(path)

        self.assertEqual(
            [event.inferred_project for event in result.usage_events],
            [None, "aftersales-automation", "codex-monitor"],
        )


def _token_count_line(
    timestamp: str,
    rate_limits: dict[str, object],
    *,
    total_tokens: int,
) -> str:
    return (
        json.dumps(
            {
                "timestamp": timestamp,
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": rate_limits,
                    "info": {
                        "last_token_usage": {"total_tokens": total_tokens},
                        "total_token_usage": {"total_tokens": total_tokens},
                    },
                },
            }
        )
        + "\n"
    )


def _session_meta_line(
    session_id: str,
    *,
    cwd: str,
    timestamp: str,
    thread_source: str = "user",
    parent_thread_id: str | None = None,
) -> str:
    payload = {
        "id": session_id,
        "session_id": session_id,
        "cwd": cwd,
        "timestamp": timestamp,
        "thread_source": thread_source,
    }
    if parent_thread_id is not None:
        payload["parent_thread_id"] = parent_thread_id
    return json.dumps(
        {"timestamp": timestamp, "type": "session_meta", "payload": payload}
    )


def _event_line(sub_type: str, message: str) -> str:
    return json.dumps(
        {
            "timestamp": "2026-07-22T08:00:00.000Z",
            "type": "event_msg",
            "payload": {"type": sub_type, "message": message},
        }
    )


def _custom_exec_line(workdir: str) -> str:
    return json.dumps(
        {
            "timestamp": "2026-07-22T08:00:01.000Z",
            "type": "event_msg",
            "payload": {
                "type": "custom_tool_call",
                "name": "exec",
                "input": (
                    "await tools.exec_command({"
                    f'\"cmd\":\"rg TODO\",\"workdir\":\"{workdir}\"'
                    "})"
                ),
            },
        }
    )


if __name__ == "__main__":
    unittest.main()
