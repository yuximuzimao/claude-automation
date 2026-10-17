"""Fault-injection tests for the single formal capture runtime entry."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.app.run_capture import (
    CaptureNoChange,
    CapturePreScrollRejected,
    CaptureRunConfig,
    CaptureRunError,
    CaptureRunner,
    RecoveryRequired,
    history_background_command,
    history_background_paths,
    parse_args,
    start_history_background,
)
from src.store import BatchStateStore


def raw_page(batch: str, group: str, page_index: int) -> dict:
    return {
        "schema_version": "2",
        "visual_fingerprint": "dhash512:" + f"{page_index + 1:0128x}",
        "batch_id": batch,
        "group_key": group,
        "group_display": "测试群",
        "page_index": page_index,
        "captured_at": f"2026-01-01T00:00:{page_index:02d}Z",
        "source": "qq_history_window_ocr",
        "window": {
            "title": "测试群",
            "frame_points": {"x": 0, "y": 0, "width": 1000, "height": 700},
            "capture_size_pixels": {"width": 1000, "height": 700},
        },
        "content_region": {"x": 0, "y": 0.10, "width": 0.92, "height": 0.75},
        "blocks": [
            {
                "block_index": 0,
                "text": f"较新{page_index} 09:02",
                "bbox": {"x": 0.04, "y": 0.70, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 1,
                "text": f"正文新{page_index}",
                "bbox": {"x": 0.04, "y": 0.66, "width": 0.10, "height": 0.022},
                "confidence": 1.0,
            },
            {
                "block_index": 2,
                "text": f"较旧{page_index} 09:01",
                "bbox": {"x": 0.04, "y": 0.50, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 3,
                "text": f"正文旧{page_index}",
                "bbox": {"x": 0.04, "y": 0.46, "width": 0.10, "height": 0.022},
                "confidence": 1.0,
            },
        ],
    }


class InjectedCrash(RuntimeError):
    pass


class RuntimeRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.runtime = self.root / "runtime"
        self.config = CaptureRunConfig(
            batch_id="batch-1",
            group_key="group-a",
            expected_title="测试群",
            page_count=1,
            window_x=10,
            window_y=20,
            window_width=1000,
            window_height=700,
            runtime_root=self.runtime,
        )
        self.clock_index = 0

    def now(self) -> str:
        self.clock_index += 1
        return f"2026-01-01T00:10:{self.clock_index:02d}Z"

    def write_page(self, _config, _mode, page_index, output: Path, _previous) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(raw_page("batch-1", "group-a", page_index), ensure_ascii=False),
            encoding="utf-8",
        )

    def runner(self, executor=None, *, page_count: int | None = None) -> CaptureRunner:
        config = self.config
        if page_count is not None:
            config = CaptureRunConfig(
                **{**config.__dict__, "page_count": page_count}
            )
        return CaptureRunner(
            self.root,
            config,
            step_executor=executor or self.write_page,
            now=self.now,
        )

    def test_history_date_cli_derives_stable_batch_runtime_and_long_page_budget(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_capture",
                "--history-date",
                "2026-09-24",
                "--group-key",
                "wow-infinite-time",
            ],
        ):
            args = parse_args()
        self.assertTrue(args.full)
        self.assertFalse(args.incremental)
        self.assertEqual(args.batch_id, "history-20260924-full")
        self.assertEqual(args.runtime_root, Path("runtime/history-days/2026-09-24"))
        self.assertEqual(args.max_new_pages, 1000)

    def test_background_is_rejected_outside_history_date_mode(self) -> None:
        with patch("sys.argv", ["run_capture", "--batch-id", "batch-1", "--full", "--background"]):
            with self.assertRaises(SystemExit):
                parse_args()

    def test_history_date_background_reuses_same_formal_runner(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_capture",
                "--history-date",
                "2026-09-24",
                "--group-key",
                "wow-infinite-time",
                "--background",
            ],
        ):
            args = parse_args()
        self.assertTrue(args.background)
        command = history_background_command(args)
        self.assertIn("src.app.run_capture", command)
        self.assertIn("--history-date", command)
        self.assertNotIn("--background", command)
        log_path, pid_path = history_background_paths(self.root, "2026-09-24")
        self.assertEqual(log_path, self.root / "runtime/diagnostics/history-20260924-background.log")
        self.assertEqual(pid_path, self.root / "runtime/diagnostics/history-background.pid")

    def test_history_background_launcher_writes_pid_and_uses_detached_same_runner(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_capture",
                "--history-date",
                "2026-09-24",
                "--group-key",
                "wow-infinite-time",
                "--background",
            ],
        ):
            args = parse_args()
        with patch("src.app.run_capture.subprocess.Popen") as popen:
            popen.return_value.pid = 9876
            pid, log_path = start_history_background(self.root, args)
        self.assertEqual(pid, 9876)
        self.assertTrue(log_path.exists())
        _log, pid_path = history_background_paths(self.root, "2026-09-24")
        self.assertEqual(pid_path.read_text(encoding="utf-8"), "9876")
        call = popen.call_args
        self.assertTrue(call.kwargs["start_new_session"])
        self.assertNotIn("--background", call.args[0])

    def test_history_background_global_lock_refuses_second_capture(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_capture",
                "--history-date",
                "2026-09-24",
                "--group-key",
                "wow-infinite-time",
                "--background",
            ],
        ):
            args = parse_args()
        _log_path, pid_path = history_background_paths(self.root, "2026-09-24")
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text("43210", encoding="utf-8")
        with patch("src.app.run_capture.os.kill", return_value=None):
            with self.assertRaises(CaptureRunError):
                start_history_background(self.root, args)

    def test_single_entry_completes_and_builds_current(self) -> None:
        result = self.runner().run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 1)
        self.assertEqual(result.messages, 2)
        self.assertTrue(result.current_path.exists())
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")

    def test_raw_written_before_state_record_is_reconciled_without_recapture(self) -> None:
        def crash_after_write(config, mode, page_index, output, previous) -> None:
            self.write_page(config, mode, page_index, output, previous)
            raise InjectedCrash("after raw write")

        with self.assertRaises(InjectedCrash):
            self.runner(crash_after_write).run()

        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state = state_store.load()
        self.assertEqual(state["pending_capture"]["mode"], "current")
        self.assertTrue(
            (self.runtime / "raw/batch-1/group-a/page-000000.json").exists()
        )

        calls = []

        def must_not_capture(*args) -> None:
            calls.append(args)
            raise AssertionError("recovery should promote durable raw without recapture")

        result = self.runner(must_not_capture).run()
        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [])

    def test_pending_current_without_raw_retries_same_page_safely(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )

        calls = []

        def capture_current(config, mode, page_index, output, previous) -> None:
            calls.append((mode, page_index, previous))
            self.write_page(config, mode, page_index, output, previous)

        result = self.runner(capture_current).run()
        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [("current", 0, None)])

    def test_stray_next_raw_without_pending_is_rejected(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        stray = self.runtime / "raw/batch-1/group-a/page-000005.json"
        self.write_page(self.config, "current", 5, stray, None)

        with self.assertRaises(RecoveryRequired):
            self.runner().run()
        self.assertEqual(state_store.load()["next_page_index"], 0)

    def test_recorded_page_with_no_next_raw_is_safe_to_continue(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1",
            started_at=self.now(),
            group_keys=["group-a"],
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )
        first_path = self.runtime / "raw/batch-1/group-a/page-000000.json"
        self.write_page(self.config, "current", 0, first_path, None)
        state_store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:00:00Z"
        )

        modes = []

        def capture_second(config, mode, page_index, output, previous) -> None:
            modes.append((mode, page_index, previous.name if previous else None))
            self.write_page(config, mode, page_index, output, previous)

        result = self.runner(capture_second, page_count=2).run()
        self.assertEqual(result.status, "completed")
        self.assertEqual(modes, [("scroll", 1, "page-000000.json")])

    def test_pending_scroll_without_raw_stops_instead_of_scrolling_again(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )
        first_path = self.runtime / "raw/batch-1/group-a/page-000000.json"
        self.write_page(self.config, "current", 0, first_path, None)
        state_store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:00:00Z"
        )
        state_store.begin_capture(
            "batch-1", "group-a", 1, mode="scroll", started_at=self.now()
        )

        with self.assertRaises(RecoveryRequired):
            self.runner(page_count=2).run()
        state = state_store.load()
        self.assertEqual(state["pending_capture"]["page_index"], 1)
        self.assertFalse(
            (self.runtime / "raw/batch-1/group-a/page-000001.json").exists()
        )

    def test_pending_scroll_recovery_rewinds_reanchors_and_clears_pending(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        for page_index in range(3):
            state_store.begin_capture(
                "batch-1",
                "group-a",
                page_index,
                mode="current" if page_index == 0 else "scroll",
                started_at=self.now(),
            )
            path = self.runtime / f"raw/batch-1/group-a/page-{page_index:06d}.json"
            self.write_page(self.config, "current", page_index, path, None)
            state_store.record_page(
                "batch-1",
                "group-a",
                page_index,
                updated_at=f"2026-01-01T00:00:0{page_index}Z",
            )
        state_store.begin_capture(
            "batch-1", "group-a", 3, mode="scroll", started_at=self.now()
        )

        calls = []

        def recovery_step(config, mode, page_index, output, previous) -> None:
            calls.append((mode, page_index, previous.name if previous else None))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(raw_page("batch-1", "group-a", page_index), ensure_ascii=False),
                encoding="utf-8",
            )

        state = self.runner(recovery_step, page_count=4).recover_pending_scroll_by_reanchor()

        self.assertIsNone(state["pending_capture"])
        self.assertEqual(state["next_page_index"], 3)
        self.assertEqual(state["groups"]["group-a"]["last_page_index"], 2)
        self.assertEqual(
            calls,
            [
                ("current", 3, None),
                ("rewind", 2, "probe-current-000003.json"),
                ("rewind", 1, "probe-rewind-01-000002.json"),
                ("scroll", 2, "page-000001.json"),
                ("current", 2, None),
            ],
        )
        self.assertFalse(
            (self.runtime / "diagnostics/pending-scroll-recovery").exists()
        )

    def test_pending_scroll_recovery_failure_preserves_original_pending(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        for page_index in range(3):
            state_store.begin_capture(
                "batch-1",
                "group-a",
                page_index,
                mode="current" if page_index == 0 else "scroll",
                started_at=self.now(),
            )
            path = self.runtime / f"raw/batch-1/group-a/page-{page_index:06d}.json"
            self.write_page(self.config, "current", page_index, path, None)
            state_store.record_page(
                "batch-1",
                "group-a",
                page_index,
                updated_at=f"2026-01-01T00:00:0{page_index}Z",
            )
        state_store.begin_capture(
            "batch-1", "group-a", 3, mode="scroll", started_at=self.now()
        )

        def unmatchable_probe(_config, _mode, page_index, output, _previous) -> None:
            value = raw_page("batch-1", "group-a", page_index)
            for block in value["blocks"]:
                block["text"] = f"unknown-{page_index}-{block['block_index']}"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(value), encoding="utf-8")

        with self.assertRaises(RecoveryRequired):
            self.runner(unmatchable_probe, page_count=4).recover_pending_scroll_by_reanchor()

        state = state_store.load()
        self.assertEqual(state["pending_capture"]["page_index"], 3)
        self.assertEqual(state["pending_capture"]["mode"], "scroll")
        self.assertEqual(state["next_page_index"], 3)
        self.assertEqual(state["groups"]["group-a"]["last_page_index"], 2)
        self.assertFalse(
            (self.runtime / "raw/batch-1/group-a/page-000003.json").exists()
        )

    def test_pre_scroll_rejection_clears_pending_without_advancing_page(self) -> None:
        state_store = BatchStateStore(self.runtime / "state" / "batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a"]
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )
        first_path = self.runtime / "raw/batch-1/group-a/page-000000.json"
        self.write_page(self.config, "current", 0, first_path, None)
        state_store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:00:00Z"
        )

        def reject_before_scroll(_config, mode, page_index, _output, _previous) -> None:
            self.assertEqual((mode, page_index), ("scroll", 1))
            raise CapturePreScrollRejected("viewport gate")

        with self.assertRaises(RecoveryRequired):
            self.runner(reject_before_scroll, page_count=2).run()

        state = state_store.load()
        self.assertIsNone(state["pending_capture"])
        self.assertEqual(state["next_page_index"], 1)
        self.assertEqual(state["groups"]["group-a"]["last_page_index"], 0)
        self.assertFalse(
            (self.runtime / "raw/batch-1/group-a/page-000001.json").exists()
        )

        result = self.runner(page_count=2).run()
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 2)

    def test_history_boundary_requires_two_consecutive_no_change_results(self) -> None:
        config = CaptureRunConfig(
            **{**self.config.__dict__, "page_count": None, "boundary_confirmations": 2}
        )
        calls = []
        no_change_attempts = 0

        def capture_until_boundary(config, mode, page_index, output, previous) -> None:
            nonlocal no_change_attempts
            calls.append((mode, page_index))
            if mode == "current":
                self.write_page(config, mode, page_index, output, previous)
                return
            if page_index == 1:
                self.write_page(config, mode, page_index, output, previous)
                return
            no_change_attempts += 1
            raise CaptureNoChange("boundary")

        result = CaptureRunner(
            self.root,
            config,
            step_executor=capture_until_boundary,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [("current", 0), ("scroll", 1), ("scroll", 2), ("scroll", 2)])
        self.assertEqual(no_change_attempts, 2)
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertTrue(state["groups"]["group-a"]["capture_complete"])
        self.assertEqual(state["next_page_index"], 2)

    def test_two_groups_share_one_batch_and_finalize_only_after_both_complete(self) -> None:
        groups = ("group-a", "group-b")

        def write_group_page(config, _mode, page_index, output: Path, _previous) -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(raw_page("batch-1", config.group_key, page_index), ensure_ascii=False),
                encoding="utf-8",
            )

        first_config = CaptureRunConfig(
            **{**self.config.__dict__, "batch_group_keys": groups}
        )
        first = CaptureRunner(
            self.root,
            first_config,
            step_executor=write_group_page,
            now=self.now,
        ).run()
        self.assertEqual(first.status, "incomplete")
        self.assertFalse(first.current_path.exists())

        second_config = CaptureRunConfig(
            **{
                **self.config.__dict__,
                "group_key": "group-b",
                "expected_title": "测试群B",
                "batch_group_keys": groups,
            }
        )
        second = CaptureRunner(
            self.root,
            second_config,
            step_executor=write_group_page,
            now=self.now,
        ).run()

        self.assertEqual(second.status, "completed")
        self.assertEqual(second.pages, 2)
        self.assertEqual(second.messages, 4)
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["groups"]["group-a"]["last_page_index"], 0)
        self.assertEqual(state["groups"]["group-b"]["last_page_index"], 1)
        self.assertTrue(all(item["capture_complete"] for item in state["groups"].values()))

    def test_completed_state_can_rebuild_missing_current_without_capture(self) -> None:
        first = self.runner().run()
        first.current_path.unlink()

        def must_not_capture(*_args) -> None:
            raise AssertionError("completed recovery must not capture again")

        second = self.runner(must_not_capture).run()
        self.assertEqual(second.status, "completed")
        self.assertTrue(second.current_path.exists())


if __name__ == "__main__":
    unittest.main()
