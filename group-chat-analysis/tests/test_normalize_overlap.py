"""Regression tests for the formal conservative overlap implementation."""

from __future__ import annotations

import unittest

from src.normalize import (
    Message,
    OverlapMatch,
    find_overlap,
    merge_adjacent_pages,
    merge_capture_order_pages,
    messages_match,
)


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
        left = [Message("same", sender_display="甲"), Message("tail", sender_display="甲")]
        right = [Message("same", sender_display="乙"), Message("tail", sender_display="乙")]
        self.assertIsNone(find_overlap(left, right))

    def test_similar_nicknames_are_not_merged_without_exact_identity(self) -> None:
        left = Message("相似昵称", sender_display="二电六鸟法部落")
        right = Message("相似昵称", sender_display="二电六乌法部落")
        self.assertFalse(messages_match(left, right))

    def test_one_missing_sender_is_not_destructively_deduplicated(self) -> None:
        left = Message("同一段正文", sender_display="甲")
        right = Message("同一段正文", sender_display=None)
        self.assertFalse(messages_match(left, right))

    def test_both_missing_senders_can_match_on_other_evidence(self) -> None:
        left = Message("这是足够长的完全相同正文", timestamp_text="12:30")
        right = Message("这是足够长的完全相同正文", timestamp_text="12:30")
        self.assertTrue(messages_match(left, right))

    def test_message_type_must_match(self) -> None:
        left = Message("相同内容", sender_display="甲", message_type="text")
        right = Message("相同内容", sender_display="甲", message_type="system")
        self.assertFalse(messages_match(left, right))

    def test_two_observed_timestamps_must_be_compatible(self) -> None:
        left = Message("相同内容", sender_display="甲", timestamp_text="12:30")
        right = Message("相同内容", sender_display="甲", timestamp_text="12:31")
        self.assertFalse(messages_match(left, right))

    def test_missing_timestamp_remains_unknown(self) -> None:
        left = Message("相同内容", sender_display="甲", timestamp_text="12:30")
        right = Message("相同内容", sender_display="甲", timestamp_text=None)
        self.assertTrue(messages_match(left, right))

    def test_controlled_body_ocr_difference_can_match_with_exact_sender(self) -> None:
        left = [
            Message("玩家正在测试连续消息重叠", sender_display="甲"),
            Message("孩子保住了那个女的大概率就跟定你了", sender_display="甲"),
        ]
        right = [
            Message("玩家正在测试连续消息重叠。", sender_display="甲"),
            Message("孩子保住了那个女的大概率就跟定你了", sender_display="甲"),
            Message("newer", sender_display="乙"),
        ]
        self.assertEqual(find_overlap(left, right), OverlapMatch(0, 0, 2))

    def test_two_short_anonymous_messages_are_not_enough_evidence(self) -> None:
        left = [Message("abcd"), Message("efgh")]
        right = [Message("abcd"), Message("efgh")]
        self.assertIsNone(find_overlap(left, right))

    def test_two_long_exact_anonymous_messages_can_confirm_overlap(self) -> None:
        left = [Message("12345678"), Message("abcdefgh")]
        right = [Message("12345678"), Message("abcdefgh")]
        self.assertEqual(find_overlap(left, right), OverlapMatch(0, 0, 2))

    def test_middle_overlap_preserves_newer_page_prefix(self) -> None:
        older = [
            Message("left-1"),
            Message("overlap-1", sender_display="甲"),
            Message("overlap-2", sender_display="甲"),
        ]
        newer = [
            Message("edge"),
            Message("overlap-1", sender_display="甲"),
            Message("overlap-2", sender_display="甲"),
            Message("right"),
        ]

        merged, match = merge_adjacent_pages(older, newer)

        self.assertEqual(match, OverlapMatch(left_start=1, right_start=1, count=2))
        self.assertEqual(
            [item.content_text for item in merged],
            ["left-1", "edge", "overlap-1", "overlap-2", "right"],
        )

    def test_more_complete_text_beats_higher_ocr_confidence(self) -> None:
        older = [
            Message(
                "这是用于测试重叠的一条非常完整消息内容",
                sender_display="甲",
                ocr_confidence=0.60,
            ),
            Message("锚点消息", sender_display="甲", ocr_confidence=0.60),
        ]
        newer = [
            Message(
                "这是用于测试重叠的一条非常完整消息内",
                sender_display="甲",
                ocr_confidence=0.95,
            ),
            Message("锚点消息", sender_display="甲", ocr_confidence=0.95),
        ]

        merged, match = merge_adjacent_pages(older, newer)

        self.assertEqual(match, OverlapMatch(0, 0, 2))
        self.assertEqual(merged[0].content_text, "这是用于测试重叠的一条非常完整消息内容")

    def test_equal_length_observation_prefers_higher_confidence(self) -> None:
        older = [
            Message("这是用于测试的一条足够长完整消息A", sender_display="甲", ocr_confidence=0.5),
            Message("锚点消息", sender_display="甲", ocr_confidence=0.5),
        ]
        newer = [
            Message("这是用于测试的一条足够长完整消息B", sender_display="甲", ocr_confidence=0.9),
            Message("锚点消息", sender_display="甲", ocr_confidence=0.9),
        ]

        merged, match = merge_adjacent_pages(older, newer)

        self.assertEqual(match, OverlapMatch(0, 0, 2))
        self.assertEqual(merged[0], newer[0])

    def test_capture_page_order_is_reversed_before_global_merge(self) -> None:
        newest_page = [
            Message("A", sender_display="甲"),
            Message("B", sender_display="甲"),
            Message("C", sender_display="乙"),
        ]
        older_page = [
            Message("X", sender_display="丙"),
            Message("A", sender_display="甲"),
            Message("B", sender_display="甲"),
        ]

        merged, matches = merge_capture_order_pages([newest_page, older_page])

        self.assertEqual(matches, [OverlapMatch(left_start=1, right_start=0, count=2)])
        self.assertEqual([item.content_text for item in merged], ["X", "A", "B", "C"])

    def test_no_match_keeps_both_pages(self) -> None:
        older = [Message("one"), Message("two")]
        newer = [Message("three"), Message("four")]
        merged, match = merge_adjacent_pages(older, newer)
        self.assertIsNone(match)
        self.assertEqual(merged, older + newer)


if __name__ == "__main__":
    unittest.main()
