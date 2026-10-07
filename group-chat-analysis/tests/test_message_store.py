"""Regression tests for crash-safe canonical messages.jsonl persistence."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.store import (
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageStore,
    MessageStoreError,
)


def record(batch: str, sequence: int, content: str, *, group: str = "group-a") -> dict[str, object]:
    return {
        "schema_version": MESSAGE_SCHEMA_VERSION,
        "record_id": f"{batch}:{group}:{sequence}",
        "batch_id": batch,
        "group_key": group,
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


class MessageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.path = Path(self.tempdir.name) / "messages" / "messages.jsonl"
        self.store = MessageStore(self.path)

    def test_commits_and_reloads_valid_batch(self) -> None:
        committed = self.store.commit_batch(
            "batch-1",
            [record("batch-1", 0, "a"), record("batch-1", 1, "b")],
        )

        self.assertEqual([item["content_text"] for item in committed], ["a", "b"])
        self.assertEqual(self.store.records_for_batch("batch-1"), committed)
        self.assertTrue(self.path.exists())

    def test_identical_retry_after_possible_crash_is_idempotent(self) -> None:
        incoming = [record("batch-1", 0, "a"), record("batch-1", 1, "b")]
        first = self.store.commit_batch("batch-1", incoming)
        second = self.store.commit_batch("batch-1", list(reversed(incoming)))

        self.assertEqual(first, second)
        self.assertEqual(len(self.store.load_all()), 2)

    def test_different_retry_for_same_batch_is_rejected(self) -> None:
        self.store.commit_batch(
            "batch-1",
            [record("batch-1", 0, "a"), record("batch-1", 1, "b")],
        )
        changed = [record("batch-1", 0, "a"), record("batch-1", 1, "changed")]

        with self.assertRaises(MessageStoreError):
            self.store.commit_batch("batch-1", changed)

        self.assertEqual(
            [item["content_text"] for item in self.store.records_for_batch("batch-1")],
            ["a", "b"],
        )

    def test_rejects_sequence_gap_before_touching_store(self) -> None:
        with self.assertRaises(MessageStoreError):
            self.store.commit_batch(
                "batch-1",
                [record("batch-1", 0, "a"), record("batch-1", 2, "c")],
            )
        self.assertFalse(self.path.exists())

    def test_preserves_previous_batches_when_appending_new_batch(self) -> None:
        self.store.commit_batch(
            "batch-1",
            [record("batch-1", 0, "a"), record("batch-1", 1, "b")],
        )
        self.store.commit_batch(
            "batch-2",
            [record("batch-2", 0, "c"), record("batch-2", 1, "d")],
        )

        self.assertEqual(
            [(item["batch_id"], item["content_text"]) for item in self.store.load_all()],
            [("batch-1", "a"), ("batch-1", "b"), ("batch-2", "c"), ("batch-2", "d")],
        )


if __name__ == "__main__":
    unittest.main()
