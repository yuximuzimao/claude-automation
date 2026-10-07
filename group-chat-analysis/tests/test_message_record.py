"""Regression tests for the formal persisted message-record boundary."""

from __future__ import annotations

import unittest

from src.store import (
    MESSAGE_SCHEMA_VERSION,
    MESSAGE_SOURCE,
    MessageRecordError,
    validate_message_record,
)


def valid_record() -> dict[str, object]:
    return {
        "schema_version": MESSAGE_SCHEMA_VERSION,
        "record_id": "batch-1:group-a:0",
        "batch_id": "batch-1",
        "group_key": "group-a",
        "sequence": 0,
        "message_type": "text",
        "content_text": "正文",
        "observed_at": "2026-01-01T00:00:00Z",
        "source": MESSAGE_SOURCE,
    }


class MessageRecordTests(unittest.TestCase):
    def test_accepts_minimal_schema_shaped_record(self) -> None:
        validate_message_record(valid_record())

    def test_rejects_unknown_ephemeral_fields(self) -> None:
        record = valid_record()
        record["avatar_fingerprint"] = "must-not-persist"
        with self.assertRaises(MessageRecordError):
            validate_message_record(record)

    def test_rejects_boolean_sequence(self) -> None:
        record = valid_record()
        record["sequence"] = True
        with self.assertRaises(MessageRecordError):
            validate_message_record(record)

    def test_rejects_date_without_time_or_timezone(self) -> None:
        record = valid_record()
        record["observed_at"] = "2026-01-01"
        with self.assertRaises(MessageRecordError):
            validate_message_record(record)

        record["observed_at"] = "2026-01-01T00:00:00"
        with self.assertRaises(MessageRecordError):
            validate_message_record(record)

    def test_capture_refs_must_be_array_when_present(self) -> None:
        record = valid_record()
        record["capture_refs"] = None
        with self.assertRaises(MessageRecordError):
            validate_message_record(record)

        record["capture_refs"] = [
            {
                "page_index": 0,
                "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
            }
        ]
        validate_message_record(record)


if __name__ == "__main__":
    unittest.main()
