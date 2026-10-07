"""Deterministic, conservative message overlap normalization."""

from .overlap import (
    FUZZY_TEXT_THRESHOLD,
    MIN_OVERLAP_COUNT,
    TWO_MESSAGE_EXACT_TEXT_ANCHOR_LENGTH,
    Message,
    OverlapMatch,
    find_overlap,
    merge_adjacent_pages,
    merge_capture_order_pages,
    messages_match,
    persisted_message_fields,
)

__all__ = [
    "FUZZY_TEXT_THRESHOLD",
    "MIN_OVERLAP_COUNT",
    "TWO_MESSAGE_EXACT_TEXT_ANCHOR_LENGTH",
    "Message",
    "OverlapMatch",
    "find_overlap",
    "merge_adjacent_pages",
    "merge_capture_order_pages",
    "messages_match",
    "persisted_message_fields",
]
