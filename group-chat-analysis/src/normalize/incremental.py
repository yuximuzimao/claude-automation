"""Conservative helpers for incremental anchor detection and trimming."""

from __future__ import annotations

from collections.abc import Iterable

from src.store import validate_message_record

from .overlap import Message, messages_match


class IncrementalAnchorError(ValueError):
    """Raised when a previous completed anchor cannot be used safely."""


def _message_from_record(record: dict[str, object]) -> Message:
    validate_message_record(record)
    return Message(
        content_text=str(record["content_text"]),
        sender_display=record.get("sender_display"),
        timestamp_text=record.get("timestamp_text"),
        message_type=str(record["message_type"]),
        ocr_confidence=(
            float(record["ocr_confidence"])
            if record.get("ocr_confidence") is not None
            else None
        ),
    )


def _anchor_matches_record(anchor: dict[str, object], record: dict[str, object]) -> bool:
    candidate = _message_from_record(record)
    anchor_message = Message(
        content_text=str(anchor["content_text"]),
        sender_display=anchor.get("sender_display"),
        timestamp_text=anchor.get("timestamp_text"),
        # Anchor state intentionally stores only identity-bearing text metadata.
        # Reuse the observed candidate type so anchor matching neither invents
        # nor weakens a message-type identity signal that is not persisted.
        message_type=candidate.message_type,
    )
    return messages_match(anchor_message, candidate)


def find_anchor_end(
    records: Iterable[dict[str, object]],
    anchors: Iterable[dict[str, object]],
) -> int | None:
    """Return the index immediately after the earliest confirmed anchor sequence.

    Records must be chronological old-to-new. Choosing the earliest confirmed
    occurrence intentionally biases toward preserving duplicates rather than
    risking loss if an identical short sequence later appears again.
    """

    items = [dict(record) for record in records]
    anchor_items = [dict(anchor) for anchor in anchors]
    if len(anchor_items) < 2:
        raise IncrementalAnchorError("incremental capture requires at least two previous anchor messages")
    if len(items) < len(anchor_items):
        return None

    limit = len(items) - len(anchor_items) + 1
    for start in range(limit):
        if all(
            _anchor_matches_record(anchor_items[offset], items[start + offset])
            for offset in range(len(anchor_items))
        ):
            return start + len(anchor_items)
    return None


def reindex_new_records_after_anchor(
    records: Iterable[dict[str, object]],
    anchors: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    """Trim anchor-and-older records, then resequence only truly new messages."""

    items = [dict(record) for record in records]
    end = find_anchor_end(items, anchors)
    if end is None:
        raise IncrementalAnchorError("previous completed anchor was not found in captured records")

    trimmed = items[end:]
    result: list[dict[str, object]] = []
    for sequence, record in enumerate(trimmed):
        updated = dict(record)
        updated["sequence"] = sequence
        updated["record_id"] = f"{record['batch_id']}:{record['group_key']}:{sequence}"
        validate_message_record(updated)
        result.append(updated)
    return result
