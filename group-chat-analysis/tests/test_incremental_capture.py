"""End-to-end deterministic tests for two-group incremental capture."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.app.full_capture import FullCaptureConfig, GroupTarget
from src.app.incremental_capture import IncrementalCaptureRunner
from src.app.run_capture import CaptureNoChange, RecoveryRequired
from src.store import Anchor, BatchStateStore, MessageStore


def raw_page(
    batch: str,
    group: str,
    page_index: int,
    messages_old_to_new: list[tuple[str, str, str]],
) -> dict:
    blocks: list[dict] = []
    start_y = 0.24
    step_y = 0.14
    for index, (sender, time_text, text) in enumerate(messages_old_to_new):
        header_y = start_y + index * step_y
        blocks.extend(
            [
                {
                    "block_index": len(blocks),
                    "text": f"{sender} {time_text}",
                    "bbox": {"x": 0.04, "y": header_y, "width": 0.12, "height": 0.014},
                    "confidence": 1.0,
                },
                {
                    "block_index": len(blocks) + 1,
                    "text": text,
                    "bbox": {"x": 0.04, "y": header_y - 0.04, "width": 0.16, "height": 0.022},
                    "confidence": 1.0,
                },
            ]
        )
    return {
        "schema_version": "2",
        "visual_fingerprint": "dhash512:" + f"{page_index + 1:0128x}",
        "batch_id": batch,
        "group_key": group,
        "group_display": group,
        "page_index": page_index,
        "captured_at": f"2026-01-02T00:{page_index:02d}:00Z",
        "source": "qq_history_window_ocr",
        "window": {
            "title": group,
            "frame_points": {"x": 0, "y": 0, "width": 1000, "height": 700},
            "capture_size_pixels": {"width": 1000, "height": 700},
        },
        "content_region": {"x": 0, "y": 0.10, "width": 0.92, "height": 0.75},
        "blocks": blocks,
    }


class IncrementalCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.runtime = self.root / "runtime"
        self.groups = (
            GroupTarget("group-a", "A", "群A", "group-a"),
            GroupTarget("group-b", "B", "群B", "group-b"),
        )
        self.clock_index = 0

    def now(self) -> str:
        self.clock_index += 1
        return f"2026-01-02T00:10:{self.clock_index:02d}Z"

    @staticmethod
    def anchors(group: str) -> list[Anchor]:
        return [
            Anchor(10, f"{group}-anchor-1", f"{group}-old-1", "09:00"),
            Anchor(11, f"{group}-anchor-2", f"{group}-old-2", "09:01"),
        ]

    def make_baseline(self, group_keys: tuple[str, ...] | None = None) -> None:
        keys = group_keys or tuple(target.group_key for target in self.groups)
        store = BatchStateStore(self.runtime / "state/batch-state.json")
        store.start_batch(
            "baseline-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=list(keys),
        )
        for page_index, group_key in enumerate(keys):
            store.begin_capture(
                "baseline-1",
                group_key,
                page_index,
                mode="current",
                started_at="2026-01-01T00:01:00Z",
            )
            store.record_page(
                "baseline-1",
                group_key,
                page_index,
                updated_at="2026-01-01T00:01:10Z",
            )
            store.mark_group_capture_complete(
                "baseline-1",
                group_key,
                completed_at="2026-01-01T00:01:20Z",
            )
        store.complete_batch(
            "baseline-1",
            anchors={group_key: self.anchors(group_key) for group_key in keys},
            completed_at="2026-01-01T00:02:00Z",
        )

    def config(self, *, batch_id: str = "inc-1", max_pages: int = 20, groups=None) -> FullCaptureConfig:
        targets = tuple(groups or self.groups)
        return FullCaptureConfig(
            batch_id=batch_id,
            groups=targets,
            window_x=10,
            window_y=20,
            window_width=1000,
            window_height=700,
            runtime_root=self.runtime,
            max_new_pages_per_run=max_pages,
        )

    def write_anchor_and_new(self, config, mode, page_index, output: Path, _previous) -> None:
        self.assertEqual(mode, "current")
        group = config.group_key
        messages = [
            (f"{group}-old-1", "09:00", f"{group}-anchor-1"),
            (f"{group}-old-2", "09:01", f"{group}-anchor-2"),
            (f"{group}-new-1", "09:02", f"{group}-new-text-1"),
            (f"{group}-new-2", "09:03", f"{group}-new-text-2"),
        ]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(raw_page("inc-1", group, page_index, messages), ensure_ascii=False),
            encoding="utf-8",
        )

    def test_two_groups_reopen_once_and_commit_only_messages_after_anchor(self) -> None:
        self.make_baseline()
        opened: list[str] = []
        result = IncrementalCaptureRunner(
            self.root,
            self.config(),
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=self.write_anchor_and_new,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.messages, 4)
        self.assertEqual(opened, ["group-a", "group-b"])

        records = MessageStore(self.runtime / "messages/messages.jsonl").records_for_batch("inc-1")
        self.assertEqual(len(records), 4)
        self.assertTrue(all("anchor" not in str(item["content_text"]) for item in records))
        self.assertEqual(
            [item["content_text"] for item in records if item["group_key"] == "group-a"],
            ["group-a-new-text-1", "group-a-new-text-2"],
        )
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertEqual(state["batch_kind"], "incremental")
        self.assertEqual(
            [item["content_text"] for item in state["groups"]["group-a"]["start_anchor"]],
            ["group-a-anchor-1", "group-a-anchor-2"],
        )
        self.assertEqual(
            [item["content_text"] for item in state["groups"]["group-a"]["last_completed_anchor"]],
            ["group-a-new-text-1", "group-a-new-text-2"],
        )
        current = result.current_path.read_text(encoding="utf-8")
        self.assertIn("group-a-new-text-1", current)
        self.assertNotIn("group-a-anchor-1", current)

        def must_not_touch_qq(*_args) -> None:
            raise AssertionError("completed incremental rebuild must not touch QQ")

        rebuilt = IncrementalCaptureRunner(
            self.root,
            self.config(),
            history_opener=must_not_touch_qq,
            step_executor=must_not_touch_qq,
            now=self.now,
        ).run()
        self.assertEqual(rebuilt.status, "completed")
        self.assertEqual(rebuilt.messages, 4)

    def test_zero_new_messages_completes_without_writing_old_anchor_records(self) -> None:
        one_group = (self.groups[0],)
        self.make_baseline(("group-a",))
        opened: list[str] = []

        def write_anchor_only(config, mode, page_index, output: Path, _previous) -> None:
            self.assertEqual(mode, "current")
            messages = [
                ("group-a-old-1", "09:00", "group-a-anchor-1"),
                ("group-a-old-2", "09:01", "group-a-anchor-2"),
            ]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(raw_page("inc-1", "group-a", page_index, messages), ensure_ascii=False),
                encoding="utf-8",
            )

        result = IncrementalCaptureRunner(
            self.root,
            self.config(groups=one_group),
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=write_anchor_only,
            now=self.now,
        ).run()

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.messages, 0)
        self.assertEqual(opened, ["group-a"])
        self.assertEqual(
            MessageStore(self.runtime / "messages/messages.jsonl").records_for_batch("inc-1"),
            [],
        )
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertEqual(
            [item["content_text"] for item in state["groups"]["group-a"]["last_completed_anchor"]],
            ["group-a-anchor-1", "group-a-anchor-2"],
        )
        self.assertIn("message_count: 0", result.current_path.read_text(encoding="utf-8"))

        result.current_path.unlink()
        rebuilt = IncrementalCaptureRunner(
            self.root,
            self.config(groups=one_group),
            history_opener=lambda _target: (_ for _ in ()).throw(AssertionError("must not open QQ")),
            step_executor=lambda *_args: (_ for _ in ()).throw(AssertionError("must not capture")),
            now=self.now,
        ).run()
        self.assertEqual(rebuilt.status, "completed")
        self.assertEqual(rebuilt.messages, 0)
        self.assertIn("message_count: 0", rebuilt.current_path.read_text(encoding="utf-8"))

    def test_one_new_message_rolls_anchor_forward_without_repeating_old_records(self) -> None:
        one_group = (self.groups[0],)
        self.make_baseline(("group-a",))

        def write_one_new(config, mode, page_index, output: Path, _previous) -> None:
            messages = [
                ("group-a-old-1", "09:00", "group-a-anchor-1"),
                ("group-a-old-2", "09:01", "group-a-anchor-2"),
                ("group-a-new-1", "09:02", "group-a-new-text-1"),
            ]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(raw_page("inc-1", "group-a", page_index, messages), ensure_ascii=False),
                encoding="utf-8",
            )

        result = IncrementalCaptureRunner(
            self.root,
            self.config(groups=one_group),
            history_opener=lambda _target: None,
            step_executor=write_one_new,
            now=self.now,
        ).run()

        self.assertEqual(result.messages, 1)
        records = MessageStore(self.runtime / "messages/messages.jsonl").records_for_batch("inc-1")
        self.assertEqual([item["content_text"] for item in records], ["group-a-new-text-1"])
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertEqual(
            [item["content_text"] for item in state["groups"]["group-a"]["last_completed_anchor"]],
            ["group-a-anchor-2", "group-a-new-text-1"],
        )

    def test_chunk_resume_does_not_reopen_same_history_window(self) -> None:
        one_group = (self.groups[0],)
        self.make_baseline(("group-a",))
        opened: list[str] = []

        def step(config, mode, page_index, output: Path, _previous) -> None:
            if page_index == 0:
                messages = [
                    ("group-a-new-1", "09:02", "group-a-new-text-1"),
                    ("group-a-new-2", "09:03", "group-a-new-text-2"),
                    ("group-a-new-3", "09:04", "group-a-new-text-3"),
                    ("group-a-new-4", "09:05", "group-a-new-text-4"),
                ]
            else:
                self.assertEqual(mode, "scroll")
                messages = [
                    ("group-a-old-1", "09:00", "group-a-anchor-1"),
                    ("group-a-old-2", "09:01", "group-a-anchor-2"),
                    ("group-a-new-1", "09:02", "group-a-new-text-1"),
                    ("group-a-new-2", "09:03", "group-a-new-text-2"),
                ]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(raw_page("inc-1", "group-a", page_index, messages), ensure_ascii=False),
                encoding="utf-8",
            )

        first = IncrementalCaptureRunner(
            self.root,
            self.config(max_pages=1, groups=one_group),
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=step,
            now=self.now,
        ).run()
        self.assertEqual(first.status, "incomplete")
        self.assertEqual(opened, ["group-a"])

        second = IncrementalCaptureRunner(
            self.root,
            self.config(max_pages=1, groups=one_group),
            history_opener=lambda target: opened.append(target.group_key),
            step_executor=step,
            now=self.now,
        ).run()
        self.assertEqual(second.status, "completed")
        self.assertEqual(opened, ["group-a"])
        self.assertEqual(second.messages, 4)

    def test_history_boundary_before_anchor_is_a_hard_failure(self) -> None:
        one_group = (self.groups[0],)
        self.make_baseline(("group-a",))
        scroll_attempts = 0

        def step(config, mode, page_index, output: Path, _previous) -> None:
            nonlocal scroll_attempts
            if mode == "current":
                messages = [
                    ("new-a", "09:10", "not-the-anchor-1"),
                    ("new-b", "09:11", "not-the-anchor-2"),
                ]
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(raw_page("inc-1", "group-a", page_index, messages), ensure_ascii=False),
                    encoding="utf-8",
                )
                return
            scroll_attempts += 1
            raise CaptureNoChange("boundary")

        with self.assertRaises(RecoveryRequired):
            IncrementalCaptureRunner(
                self.root,
                self.config(groups=one_group),
                history_opener=lambda _target: None,
                step_executor=step,
                now=self.now,
            ).run()
        self.assertEqual(scroll_attempts, 2)
        state = BatchStateStore(self.runtime / "state/batch-state.json").load()
        self.assertFalse(state["groups"]["group-a"]["capture_complete"])
        self.assertIsNone(state["pending_capture"])

    def test_missing_baseline_stops_before_opening_qq(self) -> None:
        opened: list[str] = []
        with self.assertRaises(RecoveryRequired):
            IncrementalCaptureRunner(
                self.root,
                self.config(),
                history_opener=lambda target: opened.append(target.group_key),
                step_executor=self.write_anchor_and_new,
                now=self.now,
            ).run()
        self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main()
