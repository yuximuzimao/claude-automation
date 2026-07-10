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
        args = parser.parse_args(["--ui", "--visible-app"])
        self.assertTrue(args.ui)
        self.assertTrue(args.visible_app)
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

    def test_run_ui_keeps_launch_agent_hidden_by_default(self) -> None:
        aggregate = main._demo_aggregate()
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "monitor.lock"
            with patch("main.run_ui") as run_ui:
                self.assertEqual(main._run_ui(aggregate, single_instance_path=lock_path), 0)

        run_ui.assert_called_once()
        self.assertTrue(run_ui.call_args.kwargs["hide_dock_icon"])

    def test_run_ui_can_show_dock_icon_for_app_launches(self) -> None:
        aggregate = main._demo_aggregate()
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "monitor.lock"
            instances: list[main.SingleInstance] = []

            class CapturingSingleInstance(main.SingleInstance):
                def __init__(self, *args: object, **kwargs: object) -> None:
                    super().__init__(*args, **kwargs)
                    instances.append(self)

            with (
                patch("main.run_ui") as run_ui,
                patch("main.SingleInstance", CapturingSingleInstance),
            ):
                self.assertEqual(
                    main._run_ui(
                        aggregate,
                        visible_app=True,
                        single_instance_path=lock_path,
                    ),
                    0,
                )

        run_ui.assert_called_once()
        self.assertFalse(run_ui.call_args.kwargs["hide_dock_icon"])
        self.assertEqual(instances[0].wait_seconds, 5.0)

    def test_ui_uses_single_instance_lock(self) -> None:
        aggregate = main._demo_aggregate()
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "monitor.lock"
            with main.SingleInstance(lock_path) as first:
                self.assertTrue(first.acquired)
                with patch("main.run_ui") as run_ui:
                    self.assertEqual(
                        main._run_ui(
                            aggregate,
                            single_instance_path=lock_path,
                        ),
                        0,
                    )

        run_ui.assert_not_called()

    def test_ui_initial_aggregate_uses_rolling_30_day_window(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(["--ui"])
        codex = CodexScanResult(sessions=())
        claude = ClaudeScanResult(sessions=())
        aggregate = main._demo_aggregate()
        rolling_start = main._month_start()

        with (
            patch("sys.argv", ["main.py", "--ui"]),
            patch("main._read_local_data", return_value=(codex, claude)),
            patch("main._month_start", return_value=rolling_start),
            patch("main.aggregate_usage", return_value=aggregate) as aggregate_usage,
            patch("main._run_ui", return_value=0),
        ):
            self.assertEqual(main.main(), 0)

        aggregate_usage.assert_called_once_with(
            codex,
            claude,
            month_start=rolling_start,
        )

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

    def test_runtime_factory_uses_window_async_refresh_for_watcher(self) -> None:
        parser = main.build_parser()
        args = parser.parse_args(
            [
                "--sessions-root",
                "/tmp/codex",
                "--claude-projects-root",
                "/tmp/claude",
                "--claude-max-files",
                "200",
            ]
        )

        after_calls: list[tuple[int, object]] = []

        class FakeRoot:
            def after(self, delay_ms: int, callback: object) -> None:
                after_calls.append((delay_ms, callback))

            def protocol(self, _name: str, _callback: object) -> None:
                return None

        class FakeWindow:
            def __init__(self) -> None:
                self.requests: list[RefreshRequest] = []

            def refresh_async(self, request: RefreshRequest) -> None:
                self.requests.append(request)

            def _on_close(self) -> None:
                return None

        captured_on_change = None

        def fake_start_watchdog(_paths: object, on_change: object) -> object:
            nonlocal captured_on_change
            captured_on_change = on_change
            return object()

        root = FakeRoot()
        window = FakeWindow()
        factory = main._build_runtime_factory(args)
        with (
            patch("main.start_watchdog_observer", side_effect=fake_start_watchdog),
            patch("main.time.time", side_effect=[100.0, 100.6]),
        ):
            factory(root, window)
            assert captured_on_change is not None
            captured_on_change(Path("changed.jsonl"))
            flush_loop = after_calls[0][1]
            flush_loop()

        self.assertEqual(len(window.requests), 1)
        self.assertEqual(window.requests[0].reason, "watcher")
        self.assertEqual(window.requests[0].claude_max_files, 200)
        self.assertFalse(
            any(delay == 0 for delay, _ in after_calls),
            "watcher refresh must not schedule main-thread aggregate loading",
        )


if __name__ == "__main__":
    unittest.main()
