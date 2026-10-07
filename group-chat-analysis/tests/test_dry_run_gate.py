"""Synthetic end-to-end gate over the formal normalize/store/inbox modules."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import tempfile
import unittest

from src.inbox import build_current_inbox
from src.normalize import Message, merge_capture_order_pages
from src.store import (
    Anchor,
    BatchStateStore,
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageRecordError,
    StateError,
)


def make_record(
    batch_id: str,
    group_key: str,
    sequence: int,
    content_text: str,
    *,
    group_display: str | None = "测试群",
    sender_display: str | None = None,
    timestamp_text: str | None = None,
    message_type: str = "text",
    ocr_confidence: float | None = None,
) -> dict[str, object]:
    """Test-only factory for a schema-shaped normalized record."""

    return {
        "schema_version": MESSAGE_SCHEMA_VERSION,
        "record_id": f"{batch_id}:{group_key}:{sequence}",
        "batch_id": batch_id,
        "group_key": group_key,
        "group_display": group_display,
        "sequence": sequence,
        "sender_display": sender_display,
        "timestamp": None,
        "timestamp_text": timestamp_text,
        "message_type": message_type,
        "content_text": content_text,
        "ocr_confidence": ocr_confidence,
        "observed_at": "2026-01-01T00:00:00Z",
        "source": MESSAGE_SOURCE,
        "capture_refs": [],
    }


class DryRunGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.store = BatchStateStore(root / "state" / "state.json")
        self.current = root / "inbox" / "current.md"

    def _start_and_capture_two_pages(self) -> None:
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )
        self.store.begin_capture(
            "batch-1",
            "group-a",
            0,
            mode="current",
            started_at="2026-01-01T00:01:00Z",
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self.store.begin_capture(
            "batch-1",
            "group-a",
            1,
            mode="scroll",
            started_at="2026-01-01T00:02:00Z",
        )
        self.store.record_page(
            "batch-1", "group-a", 1, updated_at="2026-01-01T00:02:00Z"
        )

    def _complete_from_records(self, records: list[dict[str, object]]) -> None:
        grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
        for record in records:
            grouped[str(record["group_key"])].append(record)

        anchors: dict[str, list[Anchor]] = {}
        for group_key, group_records in grouped.items():
            ordered = sorted(group_records, key=lambda item: int(item["sequence"]))
            if len(ordered) < 2:
                raise AssertionError("test completion needs at least two records per group")
            selected = ordered[-2:]
            anchors[group_key] = [
                Anchor(
                    int(record["sequence"]),
                    str(record["content_text"]),
                    record.get("sender_display"),
                    record.get("timestamp_text"),
                )
                for record in selected
            ]

        self.store.complete_batch(
            "batch-1",
            anchors=anchors,
            completed_at="2026-01-01T00:03:00Z",
        )

    def test_incomplete_batch_cannot_create_or_replace_current(self) -> None:
        self.current.parent.mkdir(parents=True)
        self.current.write_text("previous completed input\n", encoding="utf-8")
        self.store.start_batch(
            "batch-1", started_at="2026-01-01T00:00:00Z", group_keys=["group-a"]
        )

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [], self.current)

        self.assertEqual(
            self.current.read_text(encoding="utf-8"), "previous completed input\n"
        )

    def test_completed_run_uses_capture_order_and_builds_text_input(self) -> None:
        self._start_and_capture_two_pages()
        newest_page = [
            Message("连续锚点一", sender_display="甲"),
            Message("连续锚点二", sender_display="甲"),
            Message("新消息", sender_display="乙"),
        ]
        older_page = [
            Message("旧消息", sender_display="丙"),
            Message("连续锚点一", sender_display="甲"),
            Message("连续锚点二", sender_display="甲"),
        ]
        merged, matches = merge_capture_order_pages([newest_page, older_page])
        self.assertEqual(matches[0].count, 2)
        self.assertEqual(
            [item.content_text for item in merged],
            ["旧消息", "连续锚点一", "连续锚点二", "新消息"],
        )

        records = [
            make_record(
                "batch-1",
                "group-a",
                index,
                message.content_text,
                sender_display=message.sender_display,
            )
            for index, message in enumerate(merged)
        ]
        self._complete_from_records(records)

        content = build_current_inbox(self.store, "batch-1", records, self.current)

        self.assertEqual(content.count("连续锚点一"), 1)
        self.assertEqual(content.count("连续锚点二"), 1)
        self.assertLess(content.index("旧消息"), content.index("新消息"))
        self.assertTrue(self.current.exists())
        self.assertFalse(self.current.with_name("current.md.tmp").exists())

    def test_completed_batch_rejects_missing_anchor_before_inbox_gate(self) -> None:
        self._start_and_capture_two_pages()
        with self.assertRaises(StateError):
            self.store.complete_batch(
                "batch-1",
                anchors={"group-a": [Anchor(0, "only one anchor")]},
                completed_at="2026-01-01T00:03:00Z",
            )
        self.assertFalse(self.store.can_build_inbox("batch-1"))
        self.assertFalse(self.current.exists())

    def test_completed_state_cannot_build_from_empty_records(self) -> None:
        self._start_and_capture_two_pages()
        records = [
            make_record("batch-1", "group-a", 0, "a1"),
            make_record("batch-1", "group-a", 1, "a2"),
        ]
        self._complete_from_records(records)

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [], self.current)

        self.assertFalse(self.current.exists())

    def test_record_from_unknown_group_is_rejected(self) -> None:
        self._start_and_capture_two_pages()
        valid = [
            make_record("batch-1", "group-a", 0, "a1"),
            make_record("batch-1", "group-a", 1, "a2"),
        ]
        self._complete_from_records(valid)
        invalid = valid + [make_record("batch-1", "other-group", 0, "越界消息")]

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", invalid, self.current)
        self.assertFalse(self.current.exists())

    def test_non_contiguous_sequences_are_rejected(self) -> None:
        self._start_and_capture_two_pages()
        valid = [
            make_record("batch-1", "group-a", 0, "a1"),
            make_record("batch-1", "group-a", 1, "a2"),
        ]
        self._complete_from_records(valid)
        invalid = [
            make_record("batch-1", "group-a", 0, "a1"),
            make_record("batch-1", "group-a", 2, "a3"),
        ]

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", invalid, self.current)

    def test_invalid_record_does_not_replace_previous_current(self) -> None:
        self._start_and_capture_two_pages()
        valid = [
            make_record("batch-1", "group-a", 0, "a1"),
            make_record("batch-1", "group-a", 1, "a2"),
        ]
        self._complete_from_records(valid)
        self.current.parent.mkdir(parents=True)
        self.current.write_text("previous completed input\n", encoding="utf-8")
        invalid = [dict(record) for record in valid]
        invalid[0]["avatar_fingerprint"] = "must-not-persist"

        with self.assertRaises(MessageRecordError):
            build_current_inbox(self.store, "batch-1", invalid, self.current)

        self.assertEqual(
            self.current.read_text(encoding="utf-8"), "previous completed input\n"
        )

    def test_analyzed_batch_can_only_rebuild_same_input(self) -> None:
        self._start_and_capture_two_pages()
        records = [
            make_record("batch-1", "group-a", 0, "a1", sender_display="甲"),
            make_record("batch-1", "group-a", 1, "a2", sender_display="甲"),
        ]
        self._complete_from_records(records)

        first = build_current_inbox(self.store, "batch-1", records, self.current)
        self.store.mark_analyzed("batch-1", analyzed_at="2026-01-01T00:04:00Z")
        second = build_current_inbox(self.store, "batch-1", records, self.current)
        self.assertEqual(first, second)

        changed = [dict(record) for record in records]
        changed[0]["content_text"] = "不应覆盖"
        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", changed, self.current)
        self.assertEqual(self.current.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
