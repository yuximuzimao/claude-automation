"""Deterministic tests for bbox-to-message reconstruction."""

from __future__ import annotations

import unittest

from src.normalize.page_reconstruct import (
    PageReconstructionError,
    reconstruct_page,
)


def raw_block(index: int, text: str, x: float, y: float, width: float, height: float, confidence: float = 1.0) -> dict:
    return {
        "block_index": index,
        "text": text,
        "bbox": {"x": x, "y": y, "width": width, "height": height},
        "confidence": confidence,
    }


def page(blocks: list[dict], *, region_y: float = 0.10, region_height: float = 0.75) -> dict:
    return {
        "schema_version": "2",
        "visual_fingerprint": "dhash512:" + "0" * 128,
        "batch_id": "batch-1",
        "group_key": "group-a",
        "group_display": "测试群",
        "page_index": 0,
        "captured_at": "2026-01-01T00:00:00Z",
        "source": "qq_history_window_ocr",
        "window": {
            "title": "测试群",
            "frame_points": {"x": 0, "y": 0, "width": 1000, "height": 700},
            "capture_size_pixels": {"width": 1000, "height": 700},
        },
        "content_region": {"x": 0, "y": region_y, "width": 0.92, "height": region_height},
        "blocks": blocks,
    }


class PageReconstructTests(unittest.TestCase):
    def test_reconstructs_headers_bodies_and_edge_fragments(self) -> None:
        blocks = [
            raw_block(0, "2026/01/01", 0.01, 0.82, 0.06, 0.014),
            raw_block(1, "页顶残片", 0.04, 0.79, 0.08, 0.022),
            raw_block(2, "玩家甲 09:10", 0.04, 0.74, 0.09, 0.015),
            raw_block(3, "第一条正文", 0.04, 0.70, 0.10, 0.022),
            raw_block(4, "玩家乙 09:09", 0.04, 0.61, 0.09, 0.015),
            raw_block(5, "第二条正文", 0.04, 0.57, 0.10, 0.022),
            raw_block(6, "玩家丙 09:08", 0.04, 0.17, 0.09, 0.015),
            raw_block(7, "页底正文", 0.04, 0.125, 0.10, 0.022),
        ]

        result = reconstruct_page(page(blocks))

        self.assertEqual([item.sender_display for item in result.messages], ["玩家乙", "玩家甲"])
        self.assertEqual([item.content_text for item in result.messages], ["第二条正文", "第一条正文"])
        self.assertEqual([item.kind for item in result.fragments], ["top", "bottom"])
        self.assertEqual(result.fragments[0].text, "页顶残片")
        self.assertIn("页底正文", result.fragments[1].text)

    def test_visual_blocks_on_same_line_are_joined_before_header_parse(self) -> None:
        blocks = [
            raw_block(0, "玩家甲", 0.04, 0.70, 0.05, 0.015),
            raw_block(1, "09:10", 0.10, 0.701, 0.04, 0.015),
            raw_block(2, "一段", 0.04, 0.66, 0.04, 0.022),
            raw_block(3, "正文", 0.081, 0.661, 0.04, 0.022),
            raw_block(4, "玩家乙 09:09", 0.04, 0.45, 0.09, 0.015),
            raw_block(5, "下一条", 0.04, 0.41, 0.08, 0.022),
        ]

        result = reconstruct_page(page(blocks, region_y=0.20, region_height=0.60))

        message = next(item for item in result.messages if item.sender_display == "玩家甲")
        self.assertEqual(message.timestamp_text, "09:10")
        self.assertEqual(message.content_text, "一段正文")

    def test_header_nearly_same_height_as_body_is_still_recognized(self) -> None:
        blocks = [
            raw_block(0, "玩家甲 09:10", 0.04, 0.70, 0.09, 0.0190),
            raw_block(1, "第一条正文", 0.04, 0.66, 0.10, 0.0188),
            raw_block(2, "玩家乙 09:09", 0.04, 0.48, 0.09, 0.0150),
            raw_block(3, "第二条正文", 0.04, 0.44, 0.10, 0.0188),
        ]

        result = reconstruct_page(page(blocks, region_y=0.20, region_height=0.60))

        by_sender = {item.sender_display: item for item in result.messages}
        self.assertEqual(by_sender["玩家甲"].timestamp_text, "09:10")
        self.assertEqual(by_sender["玩家甲"].content_text, "第一条正文")

    def test_time_only_header_keeps_sender_unknown(self) -> None:
        blocks = [
            raw_block(0, ".09:10", 0.04, 0.65, 0.05, 0.014),
            raw_block(1, "正文", 0.04, 0.61, 0.08, 0.022),
            raw_block(2, "玩家乙 09:09", 0.04, 0.45, 0.09, 0.014),
            raw_block(3, "下一条", 0.04, 0.41, 0.08, 0.022),
        ]

        result = reconstruct_page(page(blocks, region_y=0.20, region_height=0.55))

        message = next(item for item in result.messages if item.timestamp_text == "09:10")
        self.assertIsNone(message.sender_display)

    def test_large_unexplained_gap_does_not_merge_into_previous_message(self) -> None:
        blocks = [
            raw_block(0, "玩家甲 09:10", 0.04, 0.75, 0.09, 0.014),
            raw_block(1, "第一行", 0.04, 0.71, 0.08, 0.022),
            raw_block(2, "疑似漏头部后的文字", 0.04, 0.60, 0.16, 0.022),
            raw_block(3, "玩家乙 09:09", 0.04, 0.45, 0.09, 0.014),
            raw_block(4, "下一条", 0.04, 0.41, 0.08, 0.022),
        ]

        result = reconstruct_page(page(blocks, region_y=0.20, region_height=0.65))

        message = next(item for item in result.messages if item.sender_display == "玩家甲")
        self.assertEqual(message.content_text, "第一行")
        self.assertTrue(any(fragment.kind == "orphan" and "疑似漏头部" in fragment.text for fragment in result.fragments))

    def test_header_only_page_is_preserved_as_fragments(self) -> None:
        blocks = [
            raw_block(0, "2026/10/08", 0.01, 0.82, 0.06, 0.014),
            raw_block(1, "玩家甲 13:27", 0.04, 0.64, 0.09, 0.015),
            raw_block(2, "玩家乙 13:26", 0.04, 0.43, 0.09, 0.014),
            raw_block(3, "玩家丙 13:21", 0.04, 0.10, 0.09, 0.016),
        ]

        result = reconstruct_page(page(blocks, region_y=0.02, region_height=0.85))

        self.assertEqual(result.messages, ())
        self.assertEqual([item.kind for item in result.fragments], ["header_only"] * 3)
        self.assertEqual(
            [item.sender_display for item in result.fragments],
            ["玩家甲", "玩家乙", "玩家丙"],
        )

    def test_dense_small_ocr_under_one_header_is_degraded_to_unknown_media(self) -> None:
        blocks = [
            raw_block(0, "玩家甲 09:10", 0.04, 0.78, 0.09, 0.014),
            raw_block(1, "图片内第一行", 0.05, 0.74, 0.12, 0.014),
            raw_block(2, "图片内第二行", 0.05, 0.72, 0.12, 0.014),
            raw_block(3, "图片内第三行", 0.05, 0.70, 0.12, 0.014),
            raw_block(4, "图片内第四行", 0.05, 0.68, 0.12, 0.014),
            raw_block(5, "玩家乙 09:09", 0.04, 0.55, 0.09, 0.014),
            raw_block(6, "正常正文", 0.04, 0.51, 0.08, 0.022),
        ]

        result = reconstruct_page(page(blocks, region_y=0.20, region_height=0.65))
        media = next(item for item in result.messages if item.sender_display == "玩家甲")

        self.assertEqual(media.message_type, "unknown")
        self.assertEqual(media.content_text, "非文字内容（图片/表情等，未解析）")

    def test_rejects_unknown_capture_fields(self) -> None:
        raw = page([raw_block(0, "玩家甲 09:10", 0.04, 0.7, 0.09, 0.014)])
        raw["window_id"] = 123
        with self.assertRaises(PageReconstructionError):
            reconstruct_page(raw)


if __name__ == "__main__":
    unittest.main()
