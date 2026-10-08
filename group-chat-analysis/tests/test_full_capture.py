"""Deterministic tests for two-group full-capture orchestration."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.app.full_capture import FullCaptureConfig, FullCaptureRunner, GroupTarget
from src.app.run_capture import CaptureNoChange, RecoveryRequired
from src.store import BatchStateStore


def raw_page(batch: str, group: str, page_index: int) -> dict:
    return {
        "schema_version": "2",
        "visual_fingerprint": "dhash512:" + f"{page_index + 1:0128x}",
        "batch_id": batch,
        "group_key": group,
        "group_display": group,
        "page_index": page_index,
        "captured_at": f"2026-01-01T00:00:{page_index:02d}Z",
        "source": "qq_history_window_ocr",
        "window": {
            "title": group,
            "frame_points": {"x": 0, "y": 0, "width": 1000, "height": 700},
            "capture_size_pixels": {"width": 1000, "height": 700},
        },
        "content_region": {"x": 0, "y": 0.10, "width": 0.92, "height": 0.75},
        "blocks": [
            {
                "block_index": 0,
                "text": f"新{group} 09:02",
                "bbox": {"x": 0.04, "y": 0.70, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 1,
                "text": f"正文新{group}",
                "bbox": {"x": 0.04, "y": 0.66, "width": 0.10, "height": 0.022},
                "confidence": 1.0,
            },
            {
                "block_index": 2,
                "text": f"旧{group} 09:01",
                "bbox": {"x": 0.04, "y": 0.50, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 3,
                "text": f"正文旧{group}",
                "bbox": {"x": 0.04, "y": 0.46, "width": 0.10, "height": 0.022},
                "confidence": 1.0,
            },
        ],
    }


class FullCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.runtime = self.root / "runtime"
        self.groups = (
            GroupTarget("group-a", "A", "群A", "group-a"),
            GroupTarget("group-b", "B", "群B", "group-b"),
        )
        self.config = FullCaptureConfig(
            batch_id="batch-1",
            groups=self.groups,
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

    def write_current_then_boundary(self, config, mode, page_index, output: Path, _previous) -> None:
        if mode == "scroll":
            raise CaptureNoChange("boundary")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(raw_page("batch-1", config.group_key, page_index), ensure_ascii=False),
            encoding="utf-8",
        )

    def test_two_groups_open_once_each_and_finalize_one_batch(self) -> None:
        opened = []
        runner = FullCaptureRunner(
            self.root,
            self.config,
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        )

        result = runner.run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.messages, 4)
        self.assertEqual(opened, ["group-a", "group-b"])
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertEqual(state["groups"]["group-a"]["last_page_index"], 0)
        self.assertEqual(state["groups"]["group-b"]["last_page_index"], 1)

    def test_existing_durable_page_is_resumed_without_reopening_history(self) -> None:
        state_store = BatchStateStore(self.runtime / "state/batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a", "group-b"]
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )
        raw_path = self.runtime / "raw/batch-1/group-a/page-000000.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw_page("batch-1", "group-a", 0)), encoding="utf-8")
        state_store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:00:00Z"
        )

        opened = []
        result = FullCaptureRunner(
            self.root,
            self.config,
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(opened, ["group-b"])

    def test_page_budget_returns_safely_without_switching_or_marking_boundary(self) -> None:
        config = FullCaptureConfig(
            **{**self.config.__dict__, "max_new_pages_per_run": 1}
        )
        opened = []
        result = FullCaptureRunner(
            self.root,
            config,
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.pages, 1)
        self.assertEqual(opened, ["group-a"])
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertFalse(state["groups"]["group-a"]["capture_complete"])
        self.assertFalse(state["groups"]["group-b"]["capture_complete"])
        self.assertIsNone(state["pending_capture"])
        self.assertEqual(state["next_page_index"], 1)

    def test_other_incomplete_batch_stops_before_any_ui_action(self) -> None:
        state_store = BatchStateStore(self.runtime / "state/batch-state.json")
        state_store.start_batch(
            "other-batch", started_at=self.now(), group_keys=["group-a", "group-b"]
        )
        opened = []
        with self.assertRaises(RecoveryRequired):
            FullCaptureRunner(
                self.root,
                self.config,
                history_opener=lambda target: opened.append(target.group_key),
                step_executor=self.write_current_then_boundary,
                now=self.now,
            ).run()
        self.assertEqual(opened, [])

    def test_pending_scroll_without_raw_stops_before_any_ui_action(self) -> None:
        state_store = BatchStateStore(self.runtime / "state/batch-state.json")
        state_store.start_batch(
            "batch-1", started_at=self.now(), group_keys=["group-a", "group-b"]
        )
        state_store.begin_capture(
            "batch-1", "group-a", 0, mode="current", started_at=self.now()
        )
        raw_path = self.runtime / "raw/batch-1/group-a/page-000000.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(raw_page("batch-1", "group-a", 0)), encoding="utf-8")
        state_store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:00:00Z"
        )
        state_store.begin_capture(
            "batch-1", "group-a", 1, mode="scroll", started_at=self.now()
        )

        opened = []
        with self.assertRaises(RecoveryRequired):
            FullCaptureRunner(
                self.root,
                self.config,
                history_opener=lambda target: opened.append(target.group_key),
                step_executor=self.write_current_then_boundary,
                now=self.now,
            ).run()
        self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main()
