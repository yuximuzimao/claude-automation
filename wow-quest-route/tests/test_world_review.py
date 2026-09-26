from __future__ import annotations

import unittest
from pathlib import Path

from lib.world_review import _review_level


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WorldReviewTests(unittest.TestCase):
    def test_review_level_uses_highest_relevant_level(self) -> None:
        self.assertEqual(_review_level({"required_level": 1, "quest_level": 80}), 80)
        self.assertEqual(_review_level({"required_level": 55, "quest_level": 55}), 55)
        self.assertEqual(_review_level({}), 1)


if __name__ == "__main__":
    unittest.main()
