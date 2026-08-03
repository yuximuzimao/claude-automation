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

    def test_generated_death_knight_world_page_contract(self) -> None:
        path = PROJECT_ROOT / "data/routes/dk-55-80-world-tasks.html"
        rendered = path.read_text(encoding="utf-8")
        self.assertEqual(rendered.count('class="map-tab"'), 42)
        self.assertEqual(rendered.count('class="map-panel"'), 42)
        self.assertEqual(rendered.count('<input type="checkbox"'), 2855)
        self.assertIn("血精灵死亡骑士五开 55—80 全世界任务母版", rendered)
        self.assertIn("打金循环 · 全任务母版", rendered)
        self.assertIn("东瘟疫之地：血色领地", rendered)
        self.assertIn("为巫妖王而战", rendered)
        self.assertIn("东瘟疫之地", rendered)
        self.assertIn("地狱火半岛", rendered)
        self.assertIn("冰冠冰川", rendered)
        self.assertIn("wow-route-death-knight-world-review-55-80-v1-v1", rendered)
        self.assertNotIn("尚未人工整理，暂不提供路线", rendered)


if __name__ == "__main__":
    unittest.main()
