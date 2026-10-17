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
                "text": "2026/01/01",
                "bbox": {"x": 0.01, "y": 0.82, "width": 0.06, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 1,
                "text": f"新{group} 09:02",
                "bbox": {"x": 0.04, "y": 0.70, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 2,
                "text": f"正文新{group}",
                "bbox": {"x": 0.04, "y": 0.66, "width": 0.10, "height": 0.022},
                "confidence": 1.0,
            },
            {
                "block_index": 3,
                "text": f"旧{group} 09:01",
                "bbox": {"x": 0.04, "y": 0.50, "width": 0.10, "height": 0.014},
                "confidence": 1.0,
            },
            {
                "block_index": 4,
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

    def test_history_date_mode_refreshes_history_then_selects_date(self) -> None:
        config = FullCaptureConfig(
            **{**self.config.__dict__, "groups": (self.groups[0],), "history_date": "2026-01-01"}
        )
        opened = []
        selected = []

        result = FullCaptureRunner(
            self.root,
            config,
            history_opener=lambda target: opened.append(target.group_key),
            history_date_selector=lambda target, value: selected.append((target.group_key, value)),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 1)
        self.assertEqual(opened, ["group-a"])
        self.assertEqual(selected, [("group-a", "2026-01-01")])

    def test_history_date_resume_with_durable_page_does_not_reselect_date(self) -> None:
        config = FullCaptureConfig(
            **{
                **self.config.__dict__,
                "groups": (self.groups[0],),
                "history_date": "2026-01-01",
                "max_new_pages_per_run": 1,
            }
        )
        opened = []
        selected = []
        first = FullCaptureRunner(
            self.root,
            config,
            history_opener=lambda target: opened.append(target.group_key),
            history_date_selector=lambda target, value: selected.append((target.group_key, value)),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        ).run()
        self.assertEqual(first.status, "incomplete")
        self.assertEqual(selected, [("group-a", "2026-01-01")])

        second = FullCaptureRunner(
            self.root,
            config,
            history_opener=lambda target: opened.append(target.group_key),
            history_date_selector=lambda target, value: selected.append((target.group_key, value)),
            step_executor=self.write_current_then_boundary,
            now=self.now,
        ).run()
        self.assertEqual(second.status, "completed")
        self.assertEqual(opened, ["group-a"])
        self.assertEqual(selected, [("group-a", "2026-01-01")])

    def test_history_date_pending_scroll_auto_reanchors_without_reselecting_or_reopening(self) -> None:
        config = FullCaptureConfig(
            **{**self.config.__dict__, "groups": (self.groups[0],), "history_date": "2026-01-01"}
        )

        def recovery_page(page_index: int) -> dict:
            value = raw_page("batch-1", "group-a", page_index)
            for block in value["blocks"][1:]:
                block["text"] = f"{block['text']} p{page_index}"
            return value

        state_store = BatchStateStore(self.runtime / "state/batch-state.json")
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
            raw_path = self.runtime / f"raw/batch-1/group-a/page-{page_index:06d}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                json.dumps(recovery_page(page_index)),
                encoding="utf-8",
            )
            state_store.record_page(
                "batch-1",
                "group-a",
                page_index,
                updated_at=f"2026-01-01T00:00:0{page_index}Z",
            )
        state_store.begin_capture(
            "batch-1", "group-a", 3, mode="scroll", started_at=self.now()
        )
        opened = []
        selected = []
        modes = []

        def recover_then_finish(step_config, mode, page_index, output, previous) -> None:
            modes.append((mode, page_index, previous.name if previous else None))
            if mode == "scroll" and page_index == 4:
                raise CaptureNoChange("boundary")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(recovery_page(page_index)),
                encoding="utf-8",
            )

        result = FullCaptureRunner(
            self.root,
            config,
            history_opener=lambda target: opened.append(target.group_key),
            history_date_selector=lambda target, value: selected.append((target.group_key, value)),
            step_executor=recover_then_finish,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 4)
        self.assertEqual(opened, [])
        self.assertEqual(selected, [])
        self.assertEqual(
            modes[:5],
            [
                ("current", 3, None),
                ("rewind", 2, "probe-current-000003.json"),
                ("rewind", 1, "probe-rewind-01-000002.json"),
                ("scroll", 2, "page-000001.json"),
                ("current", 2, None),
            ],
        )
        self.assertEqual(modes[5:], [("scroll", 3, "page-000002.json"), ("scroll", 4, "page-000003.json"), ("scroll", 4, "page-000003.json")])

    def test_history_date_mode_rejects_out_of_day_canonical_messages(self) -> None:
        config = FullCaptureConfig(
            **{**self.config.__dict__, "groups": (self.groups[0],), "history_date": "2026-01-02"}
        )
        with self.assertRaises(RecoveryRequired):
            FullCaptureRunner(
                self.root,
                config,
                history_opener=lambda _target: None,
                history_date_selector=lambda _target, _value: None,
                step_executor=self.write_current_then_boundary,
                now=self.now,
            ).run()
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertNotEqual(state["status"], "completed")

    def test_history_date_mode_rejects_multiple_groups(self) -> None:
        config = FullCaptureConfig(
            **{**self.config.__dict__, "history_date": "2026-09-25"}
        )
        with self.assertRaises(RecoveryRequired):
            FullCaptureRunner(
                self.root,
                config,
                step_executor=self.write_current_then_boundary,
                now=self.now,
            ).run()

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
