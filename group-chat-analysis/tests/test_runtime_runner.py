"""Fault-injection tests for the single formal capture runtime entry."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.app.run_capture import (
    CaptureRunConfig,
    CaptureRunner,
    RecoveryRequired,
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

    def test_single_entry_completes_and_builds_current(self) -> None:
        result = self.runner().run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 1)
        self.assertEqual(result.messages, 2)
        self.assertTrue(result.current_path.exists())
        state = BatchStateStore(self.runtime / "state" / "batch-state.json").load()
        self.assertEqual(state["status"], "completed")
        self.assertIsNone(state["pending_capture"])

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
