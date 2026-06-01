from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.aggregate import aggregate_usage
from app.models import (
    ClaudeScanResult,
    ClaudeSessionResult,
    ClaudeUsage,
    ClaudeUsageEvent,
    CodexQuota,
    CodexScanResult,
    CodexSessionResult,
    CodexUsageEvent,
    RateLimitWindow,
    TokenUsage,
)


class AggregateTests(unittest.TestCase):
    def test_project_display_name_comes_from_project_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            monitor_dir = root / "codex-monitor"
            monitor_dir.mkdir()
            (monitor_dir / "CLAUDE.md").write_text(
                "# Codex Monitor\n\n项目中文名：用量监控软件\n",
                encoding="utf-8",
            )
            undeclared_dir = root / "undeclared-tool"
            undeclared_dir.mkdir()
            (undeclared_dir / "CLAUDE.md").write_text(
                "# Undeclared Tool\n",
                encoding="utf-8",
            )

            result = aggregate_usage(
                CodexScanResult(
                    sessions=(
                        CodexSessionResult(
                            path=Path("codex-a.jsonl"),
                            cwd=str(monitor_dir),
                            usage_events=(
                                CodexUsageEvent(
                                    timestamp="2026-06-01T01:00:00+08:00",
                                    cwd=str(monitor_dir),
                                    usage=TokenUsage(total_tokens=100),
                                ),
                                CodexUsageEvent(
                                    timestamp="2026-06-01T02:00:00+08:00",
                                    cwd=str(undeclared_dir),
                                    usage=TokenUsage(total_tokens=80),
                                ),
                                CodexUsageEvent(
                                    timestamp="2026-06-01T03:00:00+08:00",
                                    cwd=None,
                                    usage=TokenUsage(total_tokens=20),
                                ),
                            ),
                        ),
                    ),
                ),
                ClaudeScanResult(sessions=()),
                now="2026-06-01T12:00:00+08:00",
            )

        self.assertEqual(result.top_projects[0].project, "codex-monitor")
        self.assertEqual(result.top_projects[0].display_name, "用量监控软件")
        self.assertEqual(result.top_projects[0].total_tokens, 100)
        self.assertEqual(result.top_projects[1].project, "other")
        self.assertEqual(result.top_projects[1].display_name, "其他")
        self.assertEqual(result.top_projects[1].total_tokens, 100)
        self.assertEqual(
            result.top_projects[1].sample_cwds,
            (str(undeclared_dir),),
        )

    def test_aggregates_today_month_and_top_projects_from_usage_events(self) -> None:
        codex = CodexScanResult(
            sessions=(
                CodexSessionResult(
                    path=Path("codex-a.jsonl"),
                    cwd="/Users/chat/claude/codex-monitor",
                    latest_quota=CodexQuota(
                        primary=RateLimitWindow(
                            used_percent=42.0,
                            resets_at=1780259470,
                            window_minutes=300,
                        ),
                        secondary=RateLimitWindow(
                            used_percent=11.0,
                            resets_at=1780846270,
                            window_minutes=10080,
                        ),
                        timestamp="2026-06-01T01:10:00+08:00",
                    ),
                    usage_events=(
                        CodexUsageEvent(
                            timestamp="2026-06-01T01:00:00+08:00",
                            cwd="/Users/chat/claude/codex-monitor",
                            usage=TokenUsage(total_tokens=100),
                        ),
                        CodexUsageEvent(
                            timestamp="2026-05-31T23:00:00+08:00",
                            cwd="/Users/chat/claude/old",
                            usage=TokenUsage(total_tokens=900),
                        ),
                    ),
                ),
                CodexSessionResult(
                    path=Path("codex-b.jsonl"),
                    cwd="/Users/chat/claude/lkwj",
                    usage_events=(
                        CodexUsageEvent(
                            timestamp="2026-06-01T02:00:00+08:00",
                            cwd="/Users/chat/claude/lkwj",
                            usage=TokenUsage(total_tokens=200),
                        ),
                    ),
                ),
            )
        )
        claude = ClaudeScanResult(
            sessions=(
                ClaudeSessionResult(
                    path=Path("claude-a.jsonl"),
                    cwd="/Users/chat/claude/codex-monitor",
                    usage_events=(
                        ClaudeUsageEvent(
                            timestamp="2026-06-01T03:00:00+08:00",
                            cwd="/Users/chat/claude/codex-monitor",
                            model="claude-sonnet-4-6",
                            usage=ClaudeUsage(input_tokens=10, output_tokens=5),
                        ),
                    ),
                ),
                ClaudeSessionResult(
                    path=Path("claude-b.jsonl"),
                    cwd="/Users/chat/claude/lkwj",
                    usage_events=(
                        ClaudeUsageEvent(
                            timestamp="2026-06-01T04:00:00+08:00",
                            cwd="/Users/chat/claude/lkwj",
                            model="deepseek-v4-pro",
                            usage=ClaudeUsage(input_tokens=30, output_tokens=10),
                        ),
                        ClaudeUsageEvent(
                            timestamp="2026-06-01T05:00:00+08:00",
                            cwd="/Users/chat/claude/zero-project",
                            model="<synthetic>",
                            usage=ClaudeUsage(),
                        ),
                        ClaudeUsageEvent(
                            timestamp="2026-06-01T06:00:00+08:00",
                            cwd="/private/tmp/lkwj",
                            model="claude-sonnet-4-6",
                            usage=ClaudeUsage(input_tokens=1),
                        ),
                    ),
                ),
            )
        )

        result = aggregate_usage(
            codex,
            claude,
            now="2026-06-01T12:00:00+08:00",
        )

        self.assertEqual(result.today.codex_tokens, 300)
        self.assertEqual(result.today.claude_tokens, 56)
        self.assertEqual(result.today.total_tokens, 356)
        self.assertEqual(result.month.codex_tokens, 300)
        self.assertEqual(result.month.claude_tokens, 56)
        self.assertEqual(result.month.total_tokens, 356)
        self.assertEqual(result.top_projects[0].project, "lkwj")
        self.assertEqual(result.top_projects[0].display_name, "洛克收集助手")
        self.assertEqual(result.top_projects[0].total_tokens, 240)
        self.assertEqual(result.top_projects[0].today_tokens, 240)
        self.assertEqual(result.top_projects[0].month_percent, 67.4)
        self.assertEqual(
            result.top_projects[0].sample_cwds,
            ("/Users/chat/claude/lkwj",),
        )
        self.assertEqual(
            result.top_projects[0].to_summary()["sample_cwds"],
            ["/Users/chat/claude/lkwj"],
        )
        self.assertEqual(result.top_projects[1].project, "codex-monitor")
        self.assertEqual(result.top_projects[1].display_name, "用量监控软件")
        self.assertEqual(result.top_projects[1].total_tokens, 115)
        self.assertEqual(result.top_projects[2].project, "other")
        self.assertEqual(result.top_projects[2].display_name, "其他")
        self.assertEqual(result.top_projects[2].total_tokens, 1)
        self.assertNotIn(
            "zero-project",
            [project.project for project in result.top_projects],
        )
        self.assertEqual(result.quota.primary.used_percent, 42.0)
        self.assertEqual(result.quota.secondary.used_percent, 11.0)
        self.assertNotIn("event_types", result.to_summary())

    def test_empty_inputs_return_zero_summary(self) -> None:
        result = aggregate_usage(
            CodexScanResult(sessions=()),
            ClaudeScanResult(sessions=()),
            now="2026-06-01T12:00:00+08:00",
        )

        self.assertEqual(result.today.total_tokens, 0)
        self.assertEqual(result.month.total_tokens, 0)
        self.assertEqual(result.top_projects, ())


if __name__ == "__main__":
    unittest.main()
