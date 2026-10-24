from __future__ import annotations

import unittest

from src.analysis.page_builder import (
    assign_silver_display_subtopics,
    assign_silver_display_topics,
)


class AnalysisPageTaxonomyTests(unittest.TestCase):
    def test_profession_is_first_level_and_class_is_second_level(self) -> None:
        unit = {
            "subject": "冰DK饰品预算层级",
            "question": "冰DK如何在预算内选择饰品？",
            "topics": ["DK", "饰品", "预算"],
        }
        self.assertEqual(
            assign_silver_display_topics(unit),
            ["职业", "装备机制", "经济 / 打金"],
        )
        self.assertEqual(assign_silver_display_subtopics(unit)["职业"], ["DK"])

    def test_raid_is_first_level_and_instance_is_second_level(self) -> None:
        unit = {
            "subject": "纳克萨玛斯（NAXX）稳定工资与时间成本",
            "question": "NAXX的收益与耗时如何权衡？",
            "topics": ["团本", "NAXX", "G团"],
        }
        self.assertEqual(
            assign_silver_display_topics(unit),
            ["副本攻略", "经济 / 打金"],
        )
        self.assertEqual(assign_silver_display_subtopics(unit)["副本攻略"], ["NAXX"])

    def test_other_topics_do_not_create_new_first_level_labels(self) -> None:
        unit = {
            "subject": "区服人口与服务器生态",
            "question": "如何理解区服人口观察？",
            "topics": ["区服生态", "人口", "阵营"],
        }
        self.assertEqual(assign_silver_display_topics(unit), ["其他"])
        self.assertEqual(assign_silver_display_subtopics(unit), {})

    def test_infinite_is_not_a_normal_first_level_topic(self) -> None:
        unit = {
            "subject": "无限服市场观察",
            "question": "当前市场信号有什么变化？",
            "topics": ["无限服", "经济 / 打金"],
        }
        self.assertEqual(assign_silver_display_topics(unit), ["经济 / 打金"])


if __name__ == "__main__":
    unittest.main()
