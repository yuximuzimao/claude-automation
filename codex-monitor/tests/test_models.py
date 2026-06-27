from __future__ import annotations

import unittest

from app.models import RateLimitWindow


class ModelTests(unittest.TestCase):
    def test_rate_limit_window_accepts_numeric_string_percent(self) -> None:
        window = RateLimitWindow.from_mapping({"used_percent": "42.5"})

        self.assertIsNotNone(window)
        self.assertEqual(window.used_percent, 42.5)

    def test_rate_limit_window_rejects_invalid_percent_values(self) -> None:
        for value in ("", "not-a-number", "NaN", float("inf"), object()):
            with self.subTest(value=value):
                window = RateLimitWindow.from_mapping({"used_percent": value})

                self.assertIsNotNone(window)
                self.assertIsNone(window.used_percent)


if __name__ == "__main__":
    unittest.main()
