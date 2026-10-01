"""Deterministic end-to-end dry-run gate for the capture pipeline.

This is intentionally a test-side prototype until the real QQ capture adapter
can supply reliable in-memory avatar-circle evidence. It protects the runtime
contract before the behavior moves into the formal ``src/`` entry points.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import unittest

from tests.test_batch_state import Anchor, BatchStateStore, StateError
from tests.test_normalize_overlap import Message, merge_adjacent_pages


MESSAGE_RECORD_KEYS = {
    "schema_version",
    "record_id",
    "batch_id",
    "group_key",
    "group_display",
    "sequence",
    "sender_display",
    "timestamp",
    "timestamp_text",
    "message_type",
    "content_text",
    "ocr_confidence",
    "observed_at",
    "source",
    "capture_refs",
}
TEXT_MESSAGE_TYPES = {"text", "system"}


@dataclass(frozen=True)
class DryRunMessage:
    """The normalized fields needed by the inbox builder."""

    group_key: str
    group_display: str
    sequence: int
    content_text: str
    sender_display: str | None = None
    timestamp_text: str | None = None
    message_type: str = "text"
    ocr_confidence: float | None = None


def make_record(
    batch_id: str,
    message: DryRunMessage,
    *,
    observed_at: str = "2026-01-01T00:00:00Z",
) -> dict[str, object]:
    """Translate one normalized message into the persisted schema shape."""

    return {
        "schema_version": "1",
        "record_id": f"{batch_id}:{message.group_key}:{message.sequence}",
        "batch_id": batch_id,
        "group_key": message.group_key,
        "group_display": message.group_display,
        "sequence": message.sequence,
        "sender_display": message.sender_display,
        "timestamp": None,
        "timestamp_text": message.timestamp_text,
        "message_type": message.message_type,
        "content_text": message.content_text,
        "ocr_confidence": message.ocr_confidence,
        "observed_at": observed_at,
        "source": "qq_screen_ocr",
        "capture_refs": [],
    }


def validate_record(record: dict[str, object]) -> None:
    """Apply the stable message-record checks needed before inbox generation."""

    if set(record) != MESSAGE_RECORD_KEYS:
        raise StateError("normalized record fields do not match message schema")
    if record["schema_version"] != "1":
        raise StateError("unsupported message schema version")
    if not isinstance(record["record_id"], str) or not record["record_id"]:
        raise StateError("record_id is required")
    if not isinstance(record["batch_id"], str) or not record["batch_id"]:
        raise StateError("batch_id is required")
    if not isinstance(record["group_key"], str) or not record["group_key"]:
        raise StateError("group_key is required")
    if not isinstance(record["sequence"], int) or record["sequence"] < 0:
        raise StateError("sequence must be a non-negative integer")
    if record["message_type"] not in {
        "text",
        "system",
        "image_placeholder",
        "voice_placeholder",
        "file_placeholder",
        "sticker_placeholder",
        "unknown",
    }:
        raise StateError("unsupported message_type")
    if not isinstance(record["content_text"], str):
        raise StateError("content_text must be a string")
    if record["ocr_confidence"] is not None and not (
        isinstance(record["ocr_confidence"], (int, float))
        and 0 <= record["ocr_confidence"] <= 1
    ):
        raise StateError("ocr_confidence must be between 0 and 1")
    if record["source"] != "qq_screen_ocr":
        raise StateError("unsupported message source")


def build_current_inbox(
    store: BatchStateStore,
    batch_id: str,
    records: list[dict[str, object]],
    destination: Path,
) -> str:
    """Build current.md only for a completed or analyzed batch.

    The temporary file is written beside the destination and atomically replaced
    only after every record passes the gate. Placeholder-only records are kept in
    the message store but do not become GPT text input.
    """

    state = store.load()
    if not store.can_build_inbox(batch_id) or state is None:
        raise StateError("current.md requires a completed or analyzed batch")

    allowed_groups = set(state["groups"])
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    group_display: dict[str, str] = {}
    for record in records:
        validate_record(record)
        if record["batch_id"] != batch_id:
            raise StateError("current.md records must belong to the active batch")
        group_key = record["group_key"]
        if group_key not in allowed_groups:
            raise StateError("current.md record group is not part of the active batch")
        if not isinstance(record["group_display"], str):
            raise StateError("group_display must be a string")
        grouped[group_key].append(record)
        group_display[group_key] = record["group_display"] or group_key

    for group_key, messages in grouped.items():
        sequences = sorted(int(item["sequence"]) for item in messages)
        if sequences != list(range(len(sequences))):
            raise StateError(f"{group_key} message sequences must be unique and contiguous")

    lines = [
        "# 群聊分析输入",
        "",
        f"batch_id: {batch_id}",
        f"message_count: {sum(len(items) for items in grouped.values())}",
        "",
    ]
    for group_key in sorted(grouped):
        lines.extend([f"## {group_display[group_key]}", ""])
        messages = sorted(grouped[group_key], key=lambda item: int(item["sequence"]))
        for record in messages:
            if record["message_type"] not in TEXT_MESSAGE_TYPES:
                continue
            timestamp = record["timestamp_text"] or "未知时间"
            sender = record["sender_display"] or "未知成员"
            lines.append(f"[{timestamp}] [{sender}] {record['content_text']}")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    if state["status"] == "analyzed":
        if not destination.exists():
            raise StateError("analyzed batch requires its existing current.md")
        existing = destination.read_text(encoding="utf-8")
        if existing != content:
            raise StateError("analyzed batch cannot replace completed inbox content")
        return existing

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)
    return content


class DryRunGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.store = BatchStateStore(root / "state" / "state.json")
        self.current = root / "inbox" / "current.md"

    def _start_and_capture_two_pages(self) -> None:
        self.store.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a"],
        )
        self.store.record_page(
            "batch-1", "group-a", 0, updated_at="2026-01-01T00:01:00Z"
        )
        self.store.record_page(
            "batch-1", "group-a", 1, updated_at="2026-01-01T00:02:00Z"
        )

    def test_incomplete_batch_cannot_create_or_replace_current(self) -> None:
        self.current.parent.mkdir(parents=True)
        self.current.write_text("previous completed input\n", encoding="utf-8")
        self.store.start_batch(
            "batch-1",
            started_at="2026-01-01T00:00:00Z",
            group_keys=["group-a"],
        )

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [], self.current)

        self.assertEqual(
            self.current.read_text(encoding="utf-8"), "previous completed input\n"
        )

    def test_completed_run_merges_adjacent_pages_and_builds_text_input(self) -> None:
        self._start_and_capture_two_pages()
        overlap_left = [
            Message("旧消息", sender_display="甲"),
            Message("连续锚点一", sender_display="甲"),
            Message("连续锚点二", sender_display="甲"),
        ]
        overlap_right = [
            Message("连续锚点一", sender_display="甲"),
            Message("连续锚点二", sender_display="甲"),
            Message("新消息", sender_display="乙"),
        ]
        merged, match = merge_adjacent_pages(overlap_left, overlap_right)
        self.assertEqual(match.count, 2)
        self.assertEqual([item.content_text for item in merged], ["旧消息", "连续锚点一", "连续锚点二", "新消息"])

        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "连续锚点一"), Anchor(1, "连续锚点二")]},
            completed_at="2026-01-01T00:03:00Z",
        )
        records = [
            make_record(
                "batch-1",
                DryRunMessage(
                    "group-a", "测试群", index, message.content_text, message.sender_display
                ),
            )
            for index, message in enumerate(merged)
        ]

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

    def test_record_from_unknown_group_is_rejected(self) -> None:
        self._start_and_capture_two_pages()
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:03:00Z",
        )
        record = make_record(
            "batch-1",
            DryRunMessage("other-group", "其他群", 0, "越界消息", "甲"),
        )

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [record], self.current)

        self.assertFalse(self.current.exists())

    def test_non_contiguous_sequences_are_rejected(self) -> None:
        self._start_and_capture_two_pages()
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:03:00Z",
        )
        records = [
            make_record("batch-1", DryRunMessage("group-a", "测试群", 0, "a1")),
            make_record("batch-1", DryRunMessage("group-a", "测试群", 2, "a3")),
        ]

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", records, self.current)

    def test_invalid_record_does_not_replace_previous_current(self) -> None:
        self._start_and_capture_two_pages()
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:03:00Z",
        )
        self.current.parent.mkdir(parents=True)
        self.current.write_text("previous completed input\n", encoding="utf-8")
        invalid_record = make_record(
            "batch-1",
            DryRunMessage("group-a", "测试群", 0, "a1", "甲"),
        )
        invalid_record["avatar_fingerprint"] = "must-not-persist"

        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [invalid_record], self.current)

        self.assertEqual(
            self.current.read_text(encoding="utf-8"), "previous completed input\n"
        )

    def test_analyzed_batch_can_rebuild_same_input_without_avatar_or_alias_data(self) -> None:
        self._start_and_capture_two_pages()
        self.store.complete_batch(
            "batch-1",
            anchors={"group-a": [Anchor(0, "a1"), Anchor(1, "a2")]},
            completed_at="2026-01-01T00:03:00Z",
        )
        records = [
            make_record(
                "batch-1",
                DryRunMessage("group-a", "测试群", 0, "a1", "甲"),
            )
        ]

        first = build_current_inbox(self.store, "batch-1", records, self.current)
        self.store.mark_analyzed("batch-1", analyzed_at="2026-01-01T00:04:00Z")
        second = build_current_inbox(self.store, "batch-1", records, self.current)

        self.assertEqual(first, second)
        self.assertNotIn("avatar_fingerprint", second)
        self.assertNotIn("alias", second)

        changed = make_record(
            "batch-1",
            DryRunMessage("group-a", "测试群", 0, "不应覆盖", "甲"),
        )
        with self.assertRaises(StateError):
            build_current_inbox(self.store, "batch-1", [changed], self.current)
        self.assertEqual(self.current.read_text(encoding="utf-8"), first)


if __name__ == "__main__":
    unittest.main()
