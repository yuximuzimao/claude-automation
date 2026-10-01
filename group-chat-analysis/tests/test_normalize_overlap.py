"""Stage 2-2 prototype for adjacent capture-page overlap removal.

The formal ``src/normalize`` entry is intentionally not created yet; the
current-batch avatar boundary and end-to-end dry-run gate are still open. This
module keeps the
deterministic overlap contract executable and can move into that entry without
changing its behavior once the gate opens.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from difflib import SequenceMatcher
import re
import unicodedata
import unittest


MIN_OVERLAP_COUNT = 2
FUZZY_TEXT_THRESHOLD = 0.90
SHORT_TEXT_LENGTH = 4
SENDER_SUBSTITUTION_COUNT = 1


@dataclass
class Message:
    """The fields needed to compare adjacent normalized messages."""

    content_text: str
    sender_display: str | None = None
    timestamp_text: str | None = None
    message_type: str = "text"
    ocr_confidence: float | None = None
    # Ephemeral current-batch fingerprint of the avatar circle; never persisted.
    avatar_fingerprint: str | None = None


@dataclass(frozen=True)
class AvatarObservation:
    """Current-batch avatar-circle result supplied by capture."""

    fingerprint: str | None = None
    reliable: bool = False

    def usable_fingerprint(self) -> str | None:
        if not self.reliable or not self.fingerprint:
            return None
        fingerprint = self.fingerprint.strip()
        return fingerprint or None


class CurrentBatchAvatarEvidence:
    """Ephemeral capture/normalize boundary for avatar-circle fingerprints."""

    def __init__(self, batch_id: str) -> None:
        if not batch_id:
            raise ValueError("batch_id is required")
        self.batch_id = batch_id
        self._by_observation: dict[str, str | None] = {}
        self._bound_messages: list[Message] = []
        self._closed = False

    def put(
        self,
        batch_id: str,
        observation_id: str,
        observation: AvatarObservation,
    ) -> None:
        self._require_active(batch_id)
        if not observation_id:
            raise ValueError("observation_id is required")
        self._by_observation[observation_id] = observation.usable_fingerprint()

    def lookup(self, batch_id: str, observation_id: str) -> str | None:
        if self._closed or batch_id != self.batch_id:
            return None
        return self._by_observation.get(observation_id)

    def bind(
        self,
        message: Message,
        *,
        batch_id: str,
        observation_id: str,
    ) -> Message:
        self._require_active(batch_id)
        bound = replace(
            message,
            avatar_fingerprint=self.lookup(batch_id, observation_id),
        )
        self._bound_messages.append(bound)
        return bound

    def close(self) -> None:
        for message in self._bound_messages:
            message.avatar_fingerprint = None
        self._bound_messages.clear()
        self._by_observation.clear()
        self._closed = True

    def _require_active(self, batch_id: str) -> None:
        if self._closed or batch_id != self.batch_id:
            raise ValueError("avatar evidence is limited to its active batch")


def persisted_message_fields(message: Message) -> dict[str, object]:
    """Return the message fields allowed past the ephemeral evidence boundary."""

    return {
        "content_text": message.content_text,
        "sender_display": message.sender_display,
        "timestamp_text": message.timestamp_text,
        "message_type": message.message_type,
        "ocr_confidence": message.ocr_confidence,
    }


@dataclass(frozen=True)
class OverlapMatch:
    """A contiguous match from the left page tail into the right page."""

    left_start: int
    right_start: int
    count: int

    @property
    def right_end(self) -> int:
        return self.right_start + self.count


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


def _similar_sender(left: Message, right: Message) -> bool:
    """Match senders exactly or confirm one OCR drift with the avatar circle.

    A missing sender is unknown rather than a positive identity signal. Similar
    names are only accepted when the current-batch avatar fingerprints match;
    no cross-batch nickname alias is inferred here.
    """

    left_key = _text_key(left.sender_display)
    right_key = _text_key(right.sender_display)
    if left_key == right_key and left_key:
        return True
    if not left_key or not right_key:
        return True
    if len(left_key) != len(right_key):
        return False
    if len(left_key) == 1:
        return False
    differences = sum(a != b for a, b in zip(left_key, right_key))
    if differences != SENDER_SUBSTITUTION_COUNT:
        return False
    return (
        bool(left.avatar_fingerprint)
        and bool(right.avatar_fingerprint)
        and left.avatar_fingerprint == right.avatar_fingerprint
    )


def _similar_optional(left: str | None, right: str | None) -> bool:
    """Treat an absent OCR field as unknown, not as evidence of a mismatch."""

    if left is None or right is None:
        return True
    return _similar_text(left, right)


def messages_match(left: Message, right: Message) -> bool:
    """Match one message conservatively, without using a global message key."""

    if left.message_type != right.message_type:
        return False
    return (
        _similar_text(left.content_text, right.content_text)
        and _similar_sender(left, right)
        and _similar_optional(left.timestamp_text, right.timestamp_text)
    )


def _two_message_overlap_is_confirmed(
    left_page: list[Message],
    right_page: list[Message],
    left_start: int,
    right_start: int,
) -> bool:
    """Require a second identity signal for the minimum two-message match."""

    for offset in range(MIN_OVERLAP_COUNT):
        left = left_page[left_start + offset]
        right = right_page[right_start + offset]
        if left.sender_display is not None and right.sender_display is not None:
            return True
        if left.timestamp_text is not None and right.timestamp_text is not None:
            return True
        if (
            _text_key(left.content_text) == _text_key(right.content_text)
            and len(_text_key(left.content_text)) >= 8
        ):
            return True
    return False


def find_overlap(
    left_page: list[Message],
    right_page: list[Message],
    *,
    min_count: int = MIN_OVERLAP_COUNT,
) -> OverlapMatch | None:
    """Find the longest contiguous left-tail/right-page overlap.

    ``right_start`` is allowed to be non-zero because a page can begin with a
    retained edge candidate before the first complete overlap message. Ties
    choose the earliest right-page position. A one-message match is rejected
    by default because it cannot distinguish a repeated short message from a
    page overlap.
    """

    if min_count < 2 or not left_page or not right_page:
        raise ValueError("min_count must be at least 2 and pages must be non-empty")

    max_count = min(len(left_page), len(right_page))
    for count in range(max_count, min_count - 1, -1):
        left_start = len(left_page) - count
        for right_start in range(len(right_page) - count + 1):
            if not all(
                messages_match(left_page[left_start + offset], right_page[right_start + offset])
                for offset in range(count)
            ):
                continue
            if count == MIN_OVERLAP_COUNT and not _two_message_overlap_is_confirmed(
                left_page,
                right_page,
                left_start,
                right_start,
            ):
                continue
            return OverlapMatch(left_start, right_start, count)
    return None


def _canonical_message(left: Message, right: Message) -> Message:
    """Keep the more complete/high-confidence observation for an overlap."""

    if left.ocr_confidence is None and right.ocr_confidence is not None:
        return right
    if right.ocr_confidence is None and left.ocr_confidence is not None:
        return left
    if (right.ocr_confidence or 0) > (left.ocr_confidence or 0):
        return right
    if len(_text_key(right.content_text)) > len(_text_key(left.content_text)):
        return right
    return left


def merge_adjacent_pages(
    left_page: list[Message],
    right_page: list[Message],
    *,
    min_count: int = MIN_OVERLAP_COUNT,
) -> tuple[list[Message], OverlapMatch | None]:
    """Merge two pages in capture order and remove only a confirmed overlap.

    When the overlap starts in the middle of the right page, records before it
    are inserted between the non-overlapping left prefix and the canonical
    overlap. This preserves page order instead of silently dropping records.
    A missing match leaves both pages untouched.
    """

    match = find_overlap(left_page, right_page, min_count=min_count)
    if match is None:
        return list(left_page) + list(right_page), None

    canonical = [
        _canonical_message(
            left_page[match.left_start + offset],
            right_page[match.right_start + offset],
        )
        for offset in range(match.count)
    ]
    merged = (
        list(left_page[: match.left_start])
        + list(right_page[: match.right_start])
        + canonical
        + list(right_page[match.right_end :])
    )
    return merged, match


class AdjacentOverlapTests(unittest.TestCase):
    def test_removes_longest_exact_suffix_prefix_overlap(self) -> None:
        a = Message("a")
        b = Message("b")
        c = Message("c", sender_display="same")
        d = Message("d", sender_display="same")
        e = Message("e")

        merged, match = merge_adjacent_pages([a, b, c, d], [c, d, e])

        self.assertEqual(match, OverlapMatch(left_start=2, right_start=0, count=2))
        self.assertEqual(merged, [a, b, c, d, e])

    def test_requires_a_sequence_not_a_single_repeated_message(self) -> None:
        repeated = Message("好的", sender_display="甲")

        match = find_overlap([Message("older"), repeated], [repeated, Message("newer")])

        self.assertIsNone(match)

    def test_same_text_from_different_senders_is_not_an_overlap(self) -> None:
        left = [
            Message("same", sender_display="甲"),
            Message("tail", sender_display="甲"),
        ]
        right = [
            Message("same", sender_display="乙"),
            Message("tail", sender_display="乙"),
        ]

        self.assertIsNone(find_overlap(left, right))

    def test_allows_controlled_ocr_difference_in_a_long_sequence(self) -> None:
        left = [
            Message(
                "玩家正在测试重叠",
                sender_display="二电六鸟法部落",
                avatar_fingerprint="avatar-a",
            ),
            Message(
                "孩子保住了那个女的大概率就跟定你了",
                sender_display="二电六鸟法部落",
                avatar_fingerprint="avatar-a",
            ),
        ]
        right = [
            Message(
                "玩家正在测试重叠",
                sender_display="二电六乌法部落",
                avatar_fingerprint="avatar-a",
            ),
            Message(
                "孩子保住了那个女的大概率就跟定你了",
                sender_display="二电六乌法部落",
                avatar_fingerprint="avatar-a",
            ),
            Message("newer", sender_display="丙"),
        ]

        match = find_overlap(left, right)

        self.assertEqual(match, OverlapMatch(left_start=0, right_start=0, count=2))

    def test_reliable_current_batch_avatar_evidence_binds_to_message(self) -> None:
        evidence = CurrentBatchAvatarEvidence("batch-1")
        evidence.put(
            "batch-1",
            "observation-1",
            AvatarObservation(" avatar-a ", reliable=True),
        )

        bound = evidence.bind(
            Message("内容", sender_display="甲"),
            batch_id="batch-1",
            observation_id="observation-1",
        )

        self.assertEqual(bound.avatar_fingerprint, "avatar-a")

    def test_unreliable_or_empty_avatar_evidence_stays_unresolved(self) -> None:
        evidence = CurrentBatchAvatarEvidence("batch-1")
        evidence.put(
            "batch-1",
            "unreliable",
            AvatarObservation("avatar-a", reliable=False),
        )
        evidence.put(
            "batch-1",
            "empty",
            AvatarObservation("   ", reliable=True),
        )

        self.assertIsNone(evidence.lookup("batch-1", "unreliable"))
        self.assertIsNone(evidence.lookup("batch-1", "empty"))

    def test_avatar_evidence_cannot_cross_batch_or_survive_close(self) -> None:
        evidence = CurrentBatchAvatarEvidence("batch-1")
        evidence.put(
            "batch-1",
            "observation-1",
            AvatarObservation("avatar-a", reliable=True),
        )

        self.assertIsNone(evidence.lookup("batch-2", "observation-1"))
        with self.assertRaises(ValueError):
            evidence.put(
                "batch-2",
                "observation-2",
                AvatarObservation("avatar-b", reliable=True),
            )

        bound = evidence.bind(
            Message(
                "内容",
                sender_display="二电六鸟法部落",
            ),
            batch_id="batch-1",
            observation_id="observation-1",
        )
        evidence.close()
        self.assertIsNone(evidence.lookup("batch-1", "observation-1"))
        self.assertIsNone(bound.avatar_fingerprint)

    def test_persisted_message_fields_exclude_avatar_evidence(self) -> None:
        message = Message("内容", avatar_fingerprint="avatar-a")

        persisted = persisted_message_fields(message)

        self.assertNotIn("avatar_fingerprint", persisted)
        self.assertEqual(persisted["content_text"], "内容")

    def test_similar_sender_requires_same_avatar(self) -> None:
        left = Message(
            "相似昵称",
            sender_display="二电六鸟法部落",
            avatar_fingerprint="avatar-a",
        )
        right = Message(
            "相似昵称",
            sender_display="二电六乌法部落",
            avatar_fingerprint="avatar-b",
        )

        self.assertFalse(messages_match(left, right))

    def test_similar_sender_without_avatar_stays_unconfirmed(self) -> None:
        left = Message("相似昵称", sender_display="二电六鸟法部落")
        right = Message("相似昵称", sender_display="二电六乌法部落")

        self.assertFalse(messages_match(left, right))

    def test_exact_single_symbol_sender_matches_without_avatar(self) -> None:
        left = Message("单符号昵称", sender_display="、")
        right = Message("单符号昵称", sender_display="、")

        self.assertTrue(messages_match(left, right))

    def test_different_single_symbol_senders_do_not_match_with_same_avatar(self) -> None:
        left = Message(
            "单符号昵称",
            sender_display="、",
            avatar_fingerprint="avatar-a",
        )
        right = Message(
            "单符号昵称",
            sender_display="。",
            avatar_fingerprint="avatar-a",
        )

        self.assertFalse(messages_match(left, right))

    def test_same_avatar_confirms_similar_sender_in_current_batch(self) -> None:
        left = Message(
            "相似昵称",
            sender_display="二电六鸟法部落",
            avatar_fingerprint="avatar-a",
        )
        right = Message(
            "相似昵称",
            sender_display="二电六乌法部落",
            avatar_fingerprint="avatar-a",
        )

        self.assertTrue(messages_match(left, right))

    def test_different_length_or_multiple_edits_are_not_candidates(self) -> None:
        left = Message(
            "相似昵称",
            sender_display="二电六鸟法部落",
            avatar_fingerprint="avatar-a",
        )
        different_length = Message(
            "相似昵称",
            sender_display="二电六乌法部落A",
            avatar_fingerprint="avatar-a",
        )
        multiple_edits = Message(
            "相似昵称",
            sender_display="二电六乌法部洛",
            avatar_fingerprint="avatar-a",
        )

        self.assertFalse(messages_match(left, different_length))
        self.assertFalse(messages_match(left, multiple_edits))

    def test_middle_overlap_preserves_right_page_prefix(self) -> None:
        left = [Message("left-1"), Message("overlap-1"), Message("overlap-2")]
        right = [Message("edge"), Message("overlap-1"), Message("overlap-2"), Message("right")]

        merged, match = merge_adjacent_pages(left, right)

        self.assertEqual(match, OverlapMatch(left_start=1, right_start=1, count=2))
        self.assertEqual(
            [item.content_text for item in merged],
            ["left-1", "edge", "overlap-1", "overlap-2", "right"],
        )

    def test_prefers_higher_confidence_observation(self) -> None:
        left = [
            Message("这是用于测试重叠的完整消息", ocr_confidence=0.5),
            Message("anchor", ocr_confidence=0.5),
        ]
        right = [
            Message("这是用于测试重叠的完整消 息", ocr_confidence=0.9),
            Message("anchor", ocr_confidence=0.9),
        ]

        merged, match = merge_adjacent_pages(left, right)

        self.assertEqual(match, OverlapMatch(left_start=0, right_start=0, count=2))
        self.assertEqual(merged[0], right[0])

    def test_no_match_keeps_both_pages(self) -> None:
        left = [Message("one"), Message("two")]
        right = [Message("three"), Message("four")]

        merged, match = merge_adjacent_pages(left, right)

        self.assertIsNone(match)
        self.assertEqual(merged, left + right)


if __name__ == "__main__":
    unittest.main()
