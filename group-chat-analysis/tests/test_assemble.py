"""Regression tests for capture-page assembly into normalized records."""

from __future__ import annotations

import unittest

from src.normalize.assemble import BatchAssemblyError, assemble_capture_pages


def block(index: int, text: str, y: float, height: float, *, x: float = 0.04, width: float = 0.12) -> dict:
    return {
        "block_index": index,
        "text": text,
        "bbox": {"x": x, "y": y, "width": width, "height": height},
        "confidence": 1.0,
    }


def capture_page(index: int, lines: list[tuple[str, float, float]], *, group: str = "group-a") -> dict:
    return {
        "schema_version": "1",
        "batch_id": "batch-1",
        "group_key": group,
        "group_display": "测试群",
        "page_index": index,
        "captured_at": f"2026-01-01T00:00:0{index}Z",
        "source": "qq_history_window_ocr",
        "window": {
            "title": "测试群",
            "frame_points": {"x": 0, "y": 0, "width": 1000, "height": 700},
            "capture_size_pixels": {"width": 1000, "height": 700},
        },
        "content_region": {"x": 0, "y": 0.10, "width": 0.92, "height": 0.75},
        "blocks": [
            block(block_index, text, y, height)
            for block_index, (text, y, height) in enumerate(lines)
        ],
    }


def message_lines(sender: str, time: str, body: str, header_y: float, body_y: float) -> list[tuple[str, float, float]]:
    return [
        (f"{sender} {time}", header_y, 0.014),
        (body, body_y, 0.022),
    ]


class BatchAssemblyTests(unittest.TestCase):
    def test_reverses_pages_and_removes_two_message_overlap(self) -> None:
        newest = capture_page(
            0,
            message_lines("甲", "09:03", "C", 0.78, 0.74)
            + message_lines("乙", "09:02", "B-long-anchor", 0.60, 0.56)
            + message_lines("丙", "09:01", "A-long-anchor", 0.42, 0.38),
        )
        older = capture_page(
            1,
            message_lines("乙", "09:02", "B-long-anchor", 0.78, 0.74)
            + message_lines("丙", "09:01", "A-long-anchor", 0.60, 0.56)
            + message_lines("丁", "09:00", "X", 0.42, 0.38),
        )

        result = assemble_capture_pages([newest, older])

        self.assertEqual(
            [record["content_text"] for record in result.records],
            ["X", "A-long-anchor", "B-long-anchor", "C"],
        )
        self.assertEqual([record["sequence"] for record in result.records], [0, 1, 2, 3])
        self.assertEqual(result.overlap_count, 2)

    def test_structured_bottom_fragment_can_anchor_overlap_without_being_lost(self) -> None:
        newest = capture_page(
            0,
            message_lines("甲", "09:03", "C", 0.78, 0.74)
            + message_lines("乙", "09:02", "B-long-anchor", 0.46, 0.42)
            + message_lines("丙", "09:01", "A-long-anchor", 0.15, 0.105),
        )
        older = capture_page(
            1,
            message_lines("乙", "09:02", "B-long-anchor", 0.78, 0.74)
            + message_lines("丙", "09:01", "A-long-anchor", 0.60, 0.56)
            + message_lines("丁", "09:00", "X", 0.42, 0.38),
        )

        result = assemble_capture_pages([newest, older])

        self.assertEqual(
            [record["content_text"] for record in result.records],
            ["X", "A-long-anchor", "B-long-anchor", "C"],
        )
        self.assertEqual(result.overlap_count, 2)

    def test_unresolved_visible_top_fragment_is_preserved_as_text(self) -> None:
        newest = capture_page(
            0,
            [("损坏的头部", 0.81, 0.014), ("仍然可见的正文", 0.77, 0.022)]
            + message_lines("甲", "09:01", "完整消息", 0.60, 0.56),
        )

        result = assemble_capture_pages([newest])

        self.assertEqual(len(result.records), 2)
        self.assertIn("仍然可见的正文", result.records[-1]["content_text"])
        self.assertIsNone(result.records[-1]["sender_display"])

    def test_group_page_indices_may_start_after_zero_but_must_stay_contiguous(self) -> None:
        first = capture_page(3, message_lines("甲", "09:01", "正文A", 0.60, 0.56))
        second = capture_page(4, message_lines("乙", "09:00", "正文B", 0.60, 0.56))
        result = assemble_capture_pages([first, second])
        self.assertTrue(result.records)

        gap = capture_page(5, message_lines("丙", "08:59", "正文C", 0.60, 0.56))
        with self.assertRaises(BatchAssemblyError):
            assemble_capture_pages([first, gap])

    def test_rejects_mixed_groups(self) -> None:
        first = capture_page(0, message_lines("甲", "09:01", "正文A", 0.60, 0.56))
        second = capture_page(1, message_lines("乙", "09:00", "正文B", 0.60, 0.56), group="group-b")
        with self.assertRaises(BatchAssemblyError):
            assemble_capture_pages([first, second])


if __name__ == "__main__":
    unittest.main()
