from __future__ import annotations

import unittest

from src.analysis.page_builder import (
    assign_silver_display_subtopics,
    assign_silver_display_topics,
    annotate_silver_display_numbers,
    annotate_silver_display_copy,
)
from src.analysis.page_renderer import build_page_v3


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

    def test_thunder_upgrade_has_clear_display_copy(self) -> None:
        unit = {"knowledge_id": "K-THUNDER-UPGRADE-MATERIAL-CLAIM-001"}
        annotate_silver_display_copy([unit])
        self.assertEqual(unit["display_subject"], "雷霆 → 惊雷（锻造武器升级）")
        self.assertEqual(unit["display_question"], "雷霆升级成惊雷需要多少升级材料？")

    def test_thunder_upgrade_maps_to_gear(self) -> None:
        unit = {
            "subject": "雷霆升级惊雷的材料数量口径",
            "question": "雷霆升级惊雷需要多少材料？",
            "topics": ["雷霆", "惊雷", "升级材料"],
        }
        self.assertEqual(assign_silver_display_topics(unit), ["装备机制"])

    def test_other_topics_do_not_create_new_first_level_labels(self) -> None:
        unit = {
            "subject": "区服人口与服务器生态",
            "question": "如何理解区服人口观察？",
            "topics": ["区服生态", "人口", "阵营"],
        }
        self.assertEqual(assign_silver_display_topics(unit), ["其他"])
        self.assertEqual(assign_silver_display_subtopics(unit), {})


    def test_display_numbers_are_baseline_stable(self) -> None:
        units = [
            {"knowledge_id": "K-A"},
            {"knowledge_id": "K-B"},
            {"knowledge_id": "K-C"},
        ]
        annotate_silver_display_numbers(units)
        self.assertEqual([u["display_number"] for u in units], [1, 2, 3])
        # Review/filter flags must not renumber the baseline identifiers.
        units[0]["v3_first_read_queue"] = False
        units[1]["v3_first_read_queue"] = True
        self.assertEqual([u["display_number"] for u in units], [1, 2, 3])

    def test_infinite_is_not_a_normal_first_level_topic(self) -> None:
        unit = {
            "subject": "无限服市场观察",
            "question": "当前市场信号有什么变化？",
            "topics": ["无限服", "经济 / 打金"],
        }
        self.assertEqual(assign_silver_display_topics(unit), ["经济 / 打金"])

    def test_silver_renderer_keeps_all_facts_and_hides_empty_comparison_table(self) -> None:
        html = build_page_v3([], [], {}, [{
            "knowledge_id": "K-TEST",
            "kind": "comparison",
            "canonical_facts": ["事实一", "事实二"],
            "structured": {"left": "A", "right": "B"},
        }])
        self.assertIn("const facts=(u.canonical_facts||[]).filter(Boolean);", html)
        self.assertIn("facts.map", html)
        self.assertIn("if(!variants.length)return '';", html)
        self.assertIn("filter(x=>x.display!==false)", html)


if __name__ == "__main__":
    unittest.main()
