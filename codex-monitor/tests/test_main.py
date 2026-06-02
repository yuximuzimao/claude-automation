from __future__ import annotations

import io
import plistlib
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import main
from app.models import ClaudeScanResult, CodexScanResult
from app.runtime import RefreshRequest


class MainCliTests(unittest.TestCase):
    def test_parser_accepts_productization_commands(self) -> None:
        parser = main.build_parser()

        args = parser.parse_args(["--install-app"])
        self.assertTrue(args.install_app)
        args = parser.parse_args(["--install-autostart"])
        self.assertTrue(args.install_autostart)
        args = parser.parse_args(["--uninstall-autostart"])
        self.assertTrue(args.uninstall_autostart)
        args = parser.parse_args(["--print-launch-agent"])
        self.assertTrue(args.print_launch_agent)

    def test_print_launch_agent_outputs_valid_plist(self) -> None:
        with patch(
            "sys.argv",
            [
                "main.py",
                "--print-launch-agent",
                "--python-executable",
                "python3.13",
            ],
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main.main(), 0)

        plist = plistlib.loads(output.getvalue().encode("utf-8"))
        self.assertEqual(plist["Label"], "com.local.codex-monitor")

    def test_install_app_builds_bundle_under_requested_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "sys.argv",
                [
                    "main.py",
                    "--install-app",
                    "--app-output-dir",
                    tmpdir,
                    "--python-executable",
                    "python3.13",
                ],
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main.main(), 0)

            self.assertTrue((Path(tmpdir) / "Codex Monitor.app").exists())

    def test_load_aggregate_uses_incremental_gate_for_watcher_refresh(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            [
                "--sessions-root",
                "/tmp/codex",
                "--claude-projects-root",
                "/tmp/claude",
                "--claude-days",
                "2",
                "--claude-max-files",
                "200",
            ]
        )

        with (
            patch("main.read_codex_sessions", return_value=CodexScanResult(sessions=())),
            patch("main.read_claude_projects", return_value=ClaudeScanResult(sessions=())) as read_claude,
        ):
            main._load_aggregate(
                args,
                request=RefreshRequest(
                    reason="watcher",
                    claude_modified_since=123.0,
                    claude_max_files=50,
                ),
            )

        read_claude.assert_called_once()
        self.assertEqual(read_claude.call_args.kwargs["modified_since"], 123.0)
        self.assertEqual(read_claude.call_args.kwargs["max_files"], 50)


if __name__ == "__main__":
    unittest.main()
