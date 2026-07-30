from __future__ import annotations

import unittest

from lib.navigator_renderer import render_navigator_html
from lib.world_builder import _bit_allowed, _segments


class NavigatorAndWorldTests(unittest.TestCase):
    def test_navigator_is_coordinate_direction_ui_not_abstract_map(self) -> None:
        route = {
            "title": "测试路线",
            "segments": [{"id": "A", "title": "测试区", "steps": [1], "goal": "测试"}],
            "steps": [
                {
                    "step": 1,
                    "action": "完成目标",
                    "quests": [{"quest_id": 1, "name": "测试任务", "quest_level": 1, "required_level": 1, "pre_single": [], "pre_group": []}],
                    "instruction": "去目标点",
                    "anchor_details": {
                        "entities": [
                            {
                                "id": 10,
                                "kind": "npc",
                                "name": "测试目标",
                                "coordinates": [{"x": 40.0, "y": 20.0}],
                                "coordinate_summary": {"representative": {"x": 40.0, "y": 20.0}, "spawn_count": 1},
                            }
                        ]
                    },
                }
            ],
            "quest_catalog": [{"quest_id": 1, "name": "测试任务", "quest_level": 1, "required_level": 1, "pre_single": [], "pre_group": []}],
            "fivebox_observations": {"1": {"status": "not_classified"}},
            "output_basename": "test",
        }
        rendered = render_navigator_html(route)
        self.assertIn("当前X", rendered)
        self.assertIn("当前Y", rendered)
        self.assertIn("向东北", rendered)
        self.assertIn("输入游戏地图坐标，只回答", rendered)
        self.assertNotIn("<svg", rendered)

    def test_blood_elf_bitmask(self) -> None:
        blood_elf_flag = 512
        alliance_mask = 1101
        blood_elf_horde_mask = 690
        self.assertFalse(_bit_allowed(alliance_mask, blood_elf_flag))
        self.assertTrue(_bit_allowed(blood_elf_horde_mask, blood_elf_flag))
        self.assertTrue(_bit_allowed(0, blood_elf_flag))

    def test_segments_cover_all_steps_once(self) -> None:
        steps = []
        for index in range(1, 20):
            steps.append(
                {
                    "step": index,
                    "anchor_details": {
                        "representative": {"x": float(index), "y": float(index)},
                        "entities": [{"name": f"目标{index}"}],
                    },
                }
            )
        segments = _segments(steps)
        flattened = [step for segment in segments for step in segment["steps"]]
        self.assertEqual(flattened, list(range(1, 20)))
        self.assertEqual(len(flattened), len(set(flattened)))


if __name__ == "__main__":
    unittest.main()
