"""Conservative adjacent-page overlap removal for normalized messages.

Capture pages are produced newest-page-first as ``page_index`` increases toward
history.  The raw QQ page itself is visually newest-message-first; the formal
page reconstruction layer must reverse complete candidates to chronological
old-to-new before calling these helpers.  This module therefore accepts only
old-to-new message lists and keeps page-order reversal explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata


MIN_OVERLAP_COUNT = 2
FUZZY_TEXT_THRESHOLD = 0.90
SHORT_TEXT_LENGTH = 4
TWO_MESSAGE_EXACT_TEXT_ANCHOR_LENGTH = 8


@dataclass
class Message:
    """Fields needed to compare adjacent normalized message observations."""

    content_text: str
    sender_display: str | None = None
    timestamp_text: str | None = None
    message_type: str = "text"
    ocr_confidence: float | None = None


def persisted_message_fields(message: Message) -> dict[str, object]:
    """Return message fields that belong in the persistent record."""

    return {
        "content_text": message.content_text,
        "sender_display": message.sender_display,
        "timestamp_text": message.timestamp_text,
        "message_type": message.message_type,
        "ocr_confidence": message.ocr_confidence,
    }


def _text_key(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", "", normalized).casefold()


def _similar_text(left: str, right: str) -> bool:
    left_key = _text_key(left)
    right_key = _text_key(right)
    if left_key == right_key:
        return True
    if min(len(left_key), len(right_key)) < SHORT_TEXT_LENGTH:
        return False
    return SequenceMatcher(None, left_key, right_key).ratio() >= FUZZY_TEXT_THRESHOLD


def _compatible_sender(left: Message, right: Message) -> bool:
    """Match only exact known senders; unknown identity never bridges to known.

    Preserving a duplicate is cheaper than deleting a real message.  Similar
    nicknames therefore do not become the same sender in v1, and a nickname
    missing on only one observation is not enough evidence for destructive
    deduplication.
    """

    left_key = _text_key(left.sender_display)
    right_key = _text_key(right.sender_display)
    if not left_key or not right_key:
        return not left_key and not right_key
    return left_key == right_key


def _compatible_optional(left: str | None, right: str | None) -> bool:
    """A missing non-identity field is unknown; two observed values must agree."""

    if left is None or right is None:
        return True
    return _similar_text(left, right)


def messages_match(left: Message, right: Message) -> bool:
    """Return whether two adjacent observations can safely represent one message."""

    if left.message_type != right.message_type:
        return False
    return (
        _similar_text(left.content_text, right.content_text)
        and _compatible_sender(left, right)
        and _compatible_optional(left.timestamp_text, right.timestamp_text)
    )


@dataclass(frozen=True)
class OverlapMatch:
    """A contiguous match from the older page tail into the newer page."""

    left_start: int
    right_start: int
    count: int

    @property
    def right_end(self) -> int:
        return self.right_start + self.count


def _two_message_overlap_is_confirmed(
    left_page: list[Message],
    right_page: list[Message],
    left_start: int,
    right_start: int,
) -> bool:
    """Require a second strong signal when the overlap has only two messages."""

    for offset in range(MIN_OVERLAP_COUNT):
        left = left_page[left_start + offset]
        right = right_page[right_start + offset]

        left_sender = _text_key(left.sender_display)
        right_sender = _text_key(right.sender_display)
        if left_sender and left_sender == right_sender:
            return True

        left_time = _text_key(left.timestamp_text)
        right_time = _text_key(right.timestamp_text)
        if left_time and left_time == right_time:
            return True

        left_text = _text_key(left.content_text)
        right_text = _text_key(right.content_text)
        if (
            left_text == right_text
            and len(left_text) >= TWO_MESSAGE_EXACT_TEXT_ANCHOR_LENGTH
        ):
            return True

    return False


def find_overlap(
    older_page: list[Message],
    newer_page: list[Message],
    *,
    min_count: int = MIN_OVERLAP_COUNT,
) -> OverlapMatch | None:
    """Find the longest confirmed older-tail/newer-page contiguous overlap."""

    if min_count < MIN_OVERLAP_COUNT:
        raise ValueError("min_count cannot be less than the overlap safety minimum")
    if not older_page or not newer_page:
        return None

    max_count = min(len(older_page), len(newer_page))
    for count in range(max_count, min_count - 1, -1):
        left_start = len(older_page) - count
        for right_start in range(len(newer_page) - count + 1):
            if not all(
                messages_match(
                    older_page[left_start + offset],
                    newer_page[right_start + offset],
                )
                for offset in range(count)
            ):
                continue
            if count == MIN_OVERLAP_COUNT and not _two_message_overlap_is_confirmed(
                older_page,
                newer_page,
                left_start,
                right_start,
            ):
                continue
            return OverlapMatch(left_start, right_start, count)
    return None


def _canonical_message(left: Message, right: Message) -> Message:
    """Prefer completeness before OCR confidence for one confirmed duplicate."""

    left_length = len(_text_key(left.content_text))
    right_length = len(_text_key(right.content_text))
    if right_length != left_length:
        return right if right_length > left_length else left

    left_metadata = int(bool(left.sender_display)) + int(bool(left.timestamp_text))
    right_metadata = int(bool(right.sender_display)) + int(bool(right.timestamp_text))
    if right_metadata != left_metadata:
        return right if right_metadata > left_metadata else left

    left_confidence = left.ocr_confidence if left.ocr_confidence is not None else -1.0
    right_confidence = right.ocr_confidence if right.ocr_confidence is not None else -1.0
    if right_confidence > left_confidence:
        return right
    return left


def merge_adjacent_pages(
    older_page: list[Message],
    newer_page: list[Message],
    *,
    min_count: int = MIN_OVERLAP_COUNT,
) -> tuple[list[Message], OverlapMatch | None]:
    """Merge two old-to-new adjacent pages, deleting only confirmed overlap."""

    match = find_overlap(older_page, newer_page, min_count=min_count)
    if match is None:
        return list(older_page) + list(newer_page), None

    canonical = [
        _canonical_message(
            older_page[match.left_start + offset],
            newer_page[match.right_start + offset],
        )
        for offset in range(match.count)
    ]
    merged = (
        list(older_page[: match.left_start])
        + list(newer_page[: match.right_start])
        + canonical
        + list(newer_page[match.right_end :])
    )
    return merged, match


def merge_capture_order_pages(
    pages: list[list[Message]],
    *,
    min_count: int = MIN_OVERLAP_COUNT,
) -> tuple[list[Message], list[OverlapMatch | None]]:
    """Merge capture pages into chronological order.

    ``pages`` must be ordered by ascending capture ``page_index``: newest page
    first, then progressively older pages.  Each page itself must already be
    old-to-new.  The returned messages are globally old-to-new.
    """

    if not pages:
        return [], []

    chronological_pages = list(reversed(pages))
    merged = list(chronological_pages[0])
    matches: list[OverlapMatch | None] = []
    for newer_page in chronological_pages[1:]:
        merged, match = merge_adjacent_pages(
            merged,
            newer_page,
            min_count=min_count,
        )
        matches.append(match)
    return merged, matches
