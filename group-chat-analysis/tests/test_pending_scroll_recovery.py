"""Pure tests for conservative pending-scroll re-anchor matching."""

from __future__ import annotations

import unittest

from src.app.pending_scroll_recovery import raw_pages_same_view, unique_rewind_anchor


def page(fingerprint: int, label: str, *, y_offset: float = 0.0) -> dict:
    return {
        "visual_fingerprint": "dhash512:" + f"{fingerprint:0128x}",
        "content_region": {"x": 0.0, "y": 0.10, "width": 0.92, "height": 0.75},
        "blocks": [
            {
                "text": f"玩家{label} 12:34",
                "bbox": {"x": 0.05, "y": 0.60 + y_offset, "width": 0.10, "height": 0.02},
            },
            {
                "text": f"正文{label}",
                "bbox": {"x": 0.05, "y": 0.55 + y_offset, "width": 0.10, "height": 0.03},
            },
            {
                "text": f"第二行{label}",
                "bbox": {"x": 0.05, "y": 0.50 + y_offset, "width": 0.10, "height": 0.03},
            },
            {
                "text": f"第三行{label}",
                "bbox": {"x": 0.05, "y": 0.45 + y_offset, "width": 0.10, "height": 0.03},
            },
        ],
    }


class PendingScrollRecoveryMatchTests(unittest.TestCase):
    def test_same_view_requires_fingerprint_and_same_position_text(self) -> None:
        durable = page(0b1010, "A")
        recapture = page(0b1011, "A")
        shifted = page(0b1011, "A", y_offset=0.20)

        self.assertTrue(raw_pages_same_view(recapture, durable))
        self.assertFalse(raw_pages_same_view(shifted, durable))

    def test_two_rewind_probes_must_form_one_consecutive_durable_sequence(self) -> None:
        durable = {
            5: page(0b00101, "5"),
            6: page(0b00110, "6"),
            7: page(0b00111, "7"),
        }
        first_probe = page(0b00110, "6")
        second_probe = page(0b00101, "5")

        self.assertEqual(unique_rewind_anchor(first_probe, second_probe, durable), 5)

    def test_nonconsecutive_or_ambiguous_probe_sequence_is_rejected(self) -> None:
        durable = {
            5: page(0b00101, "same"),
            6: page(0b00110, "same"),
            7: page(0b00111, "same"),
        }
        first_probe = page(0b00110, "same")
        second_probe = page(0b00101, "same")

        self.assertIsNone(unique_rewind_anchor(first_probe, second_probe, durable))


if __name__ == "__main__":
    unittest.main()
