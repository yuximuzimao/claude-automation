"""Deterministic tests for incremental anchor detection and trimming."""

from __future__ import annotations

import unittest

from src.normalize.incremental import (
    IncrementalAnchorError,
    find_anchor_end,
    reindex_new_records_after_anchor,
)


def record(
    batch: str,
    group: str,
    sequence: int,
    text: str,
    sender: str,
    time_text: str,
) -> dict[str, object]:
    return {
        "schema_version": "1",
        "record_id": f"{batch}:{group}:{sequence}",
        "batch_id": batch,
        "group_key": group,
        "group_display": "测试群",
        "sequence": sequence,
        "sender_display": sender,
        "timestamp": None,
        "timestamp_text": time_text,
        "message_type": "text",
        "content_text": text,
        "ocr_confidence": 1.0,
        "observed_at": "2026-01-02T00:00:00Z",
        "source": "qq_screen_ocr",
        "capture_refs": [{"page_index": 0}],
    }


def anchor(sequence: int, text: str, sender: str, time_text: str) -> dict[str, object]:
    return {
        "sequence": sequence,
        "content_text": text,
        "sender_display": sender,
        "timestamp_text": time_text,
    }


class IncrementalAnchorTests(unittest.TestCase):
    def test_finds_contiguous_anchor_and_keeps_only_newer_records(self) -> None:
        records = [
            record("inc-1", "group-a", 0, "更旧", "Old", "08:59"),
            record("inc-1", "group-a", 1, "锚点一", "Alice", "09:00"),
            record("inc-1", "group-a", 2, "锚点二", "Bob", "09:01"),
            record("inc-1", "group-a", 3, "新增一", "Cara", "09:02"),
            record("inc-1", "group-a", 4, "新增二", "Dan", "09:03"),
        ]
        anchors = [
            anchor(100, "锚点一", "Alice", "09:00"),
            anchor(101, "锚点二", "Bob", "09:01"),
        ]

        self.assertEqual(find_anchor_end(records, anchors), 3)
        trimmed = reindex_new_records_after_anchor(records, anchors)
        self.assertEqual([item["content_text"] for item in trimmed], ["新增一", "新增二"])
        self.assertEqual([item["sequence"] for item in trimmed], [0, 1])
        self.assertEqual(
            [item["record_id"] for item in trimmed],
            ["inc-1:group-a:0", "inc-1:group-a:1"],
        )

    def test_uses_earliest_anchor_occurrence_to_bias_against_message_loss(self) -> None:
        records = [
            record("inc-1", "group-a", 0, "锚点一", "Alice", "09:00"),
            record("inc-1", "group-a", 1, "锚点二", "Bob", "09:01"),
            record("inc-1", "group-a", 2, "中间新增", "Cara", "09:02"),
            record("inc-1", "group-a", 3, "锚点一", "Alice", "09:00"),
            record("inc-1", "group-a", 4, "锚点二", "Bob", "09:01"),
            record("inc-1", "group-a", 5, "最新新增", "Dan", "09:03"),
        ]
        anchors = [
            anchor(100, "锚点一", "Alice", "09:00"),
            anchor(101, "锚点二", "Bob", "09:01"),
        ]

        self.assertEqual(find_anchor_end(records, anchors), 2)
        trimmed = reindex_new_records_after_anchor(records, anchors)
        self.assertEqual(
            [item["content_text"] for item in trimmed],
            ["中间新增", "锚点一", "锚点二", "最新新增"],
        )

    def test_zero_new_messages_returns_empty_trimmed_batch(self) -> None:
        records = [
            record("inc-1", "group-a", 0, "锚点一", "Alice", "09:00"),
            record("inc-1", "group-a", 1, "锚点二", "Bob", "09:01"),
        ]
        anchors = [
            anchor(100, "锚点一", "Alice", "09:00"),
            anchor(101, "锚点二", "Bob", "09:01"),
        ]
        self.assertEqual(reindex_new_records_after_anchor(records, anchors), [])

    def test_missing_or_too_short_anchor_stays_unresolved(self) -> None:
        records = [record("inc-1", "group-a", 0, "其它", "Alice", "09:00")]
        with self.assertRaises(IncrementalAnchorError):
            find_anchor_end(records, [anchor(0, "其它", "Alice", "09:00")])
        self.assertIsNone(
            find_anchor_end(
                records,
                [anchor(0, "锚点一", "Alice", "09:00"), anchor(1, "锚点二", "Bob", "09:01")],
            )
        )


if __name__ == "__main__":
    unittest.main()
