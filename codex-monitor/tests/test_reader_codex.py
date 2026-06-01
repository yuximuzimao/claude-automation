from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
