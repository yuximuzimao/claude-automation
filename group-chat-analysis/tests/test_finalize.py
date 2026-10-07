"""Recovery tests for canonical messages -> completed state -> current.md ordering."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.store import (
    Anchor,
    BatchStateStore,
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageStore,
    MessageStoreError,
)
from src.store.finalize import finalize_batch


def records(batch: str = "batch-1") -> list[dict[str, object]]:
    result = []
    for sequence, content in enumerate(("older", "newer")):
        result.append(
            {
                "schema_version": MESSAGE_SCHEMA_VERSION,
                "record_id": f"{batch}:group-a:{sequence}",
                "batch_id": batch,
                "group_key": "group-a",
                "group_display": "测试群",
                "sequence": sequence,
                "sender_display": "甲",
                "timestamp": None,
                "timestamp_text": f"09:0{sequence}",
                "message_type": "text",
                "content_text": content,
                "ocr_confidence": 1.0,
                "observed_at": "2026-01-01T00:00:00Z",
                "source": MESSAGE_SOURCE,
                "capture_refs": [],
            }
        )
    return result


class FinalizeBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.state = BatchStateStore(root / "state" / "state.json")
        self.messages = MessageStore(root / "messages" / "messages.jsonl")
        self.current = root / "inbox" / "current.md"
        self.state.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a"],
        )
        self.state.begin_capture(
            "batch-1",
            "group-a",
            0,
            mode="current",
            started_at="2026-01-01T00:01:00Z",
        )
        self.state.record_page(
            "batch-1",
            "group-a",
            0,
            updated_at="2026-01-01T00:01:00Z",
        )

    def test_finalize_persists_messages_before_completed_state_and_builds_inbox(self) -> None:
        content = finalize_batch(
            state_store=self.state,
            message_store=self.messages,
            batch_id="batch-1",
            records=records(),
            completed_at="2026-01-01T00:02:00Z",
            current_destination=self.current,
        )

        self.assertEqual(self.state.load()["status"], "completed")
        self.assertEqual(len(self.messages.records_for_batch("batch-1")), 2)
        self.assertTrue(self.current.exists())
        self.assertLess(content.index("older"), content.index("newer"))

    def test_retry_after_messages_commit_before_state_completion_rolls_forward(self) -> None:
        self.messages.commit_batch("batch-1", records())
        self.assertEqual(self.state.load()["status"], "incomplete")

        finalize_batch(
            state_store=self.state,
            message_store=self.messages,
            batch_id="batch-1",
            records=records(),
            completed_at="2026-01-01T00:02:00Z",
            current_destination=self.current,
        )

        self.assertEqual(self.state.load()["status"], "completed")
        self.assertTrue(self.current.exists())

    def test_retry_after_state_completion_before_current_rebuilds_current(self) -> None:
        committed = self.messages.commit_batch("batch-1", records())
        self.state.complete_batch(
            "batch-1",
            anchors={
                "group-a": [
                    Anchor(0, "older", "甲", "09:00"),
                    Anchor(1, "newer", "甲", "09:01"),
                ]
            },
            completed_at="2026-01-01T00:02:00Z",
        )
        self.assertFalse(self.current.exists())

        finalize_batch(
            state_store=self.state,
            message_store=self.messages,
            batch_id="batch-1",
            records=committed,
            completed_at="2026-01-01T00:03:00Z",
            current_destination=self.current,
        )

        self.assertTrue(self.current.exists())
        self.assertEqual(self.state.load()["status"], "completed")

    def test_completed_state_without_canonical_messages_is_not_silently_repaired(self) -> None:
        self.state.complete_batch(
            "batch-1",
            anchors={
                "group-a": [
                    Anchor(0, "older", "甲", "09:00"),
                    Anchor(1, "newer", "甲", "09:01"),
                ]
            },
            completed_at="2026-01-01T00:02:00Z",
        )

        with self.assertRaises(MessageStoreError):
            finalize_batch(
                state_store=self.state,
                message_store=self.messages,
                batch_id="batch-1",
                records=records(),
                completed_at="2026-01-01T00:03:00Z",
                current_destination=self.current,
            )

        self.assertFalse(self.messages.path.exists())
        self.assertFalse(self.current.exists())

    def test_failed_message_validation_leaves_state_incomplete(self) -> None:
        invalid = records()
        invalid[1]["sequence"] = 3

        with self.assertRaises(Exception):
            finalize_batch(
                state_store=self.state,
                message_store=self.messages,
                batch_id="batch-1",
                records=invalid,
                completed_at="2026-01-01T00:02:00Z",
                current_destination=self.current,
            )

        self.assertEqual(self.state.load()["status"], "incomplete")
        self.assertFalse(self.messages.path.exists())
        self.assertFalse(self.current.exists())


if __name__ == "__main__":
    unittest.main()
