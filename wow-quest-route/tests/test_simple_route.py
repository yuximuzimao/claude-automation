from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lib.questie_source import QuestieData
from lib.simple_route import (
    FORBIDDEN_HTML_TERMS,
    SegmentBuild,
    _build_loot_classifications,
    _close_route_prerequisites,
    parse_rxp_saved_variables,
    render_simple_html,
    validate_simple_route,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SimpleRouteTests(unittest.TestCase):
    def test_rxp_saved_variables_exposes_metadata_but_not_route_body(self) -> None:
        source = '''RXPCData = {
          ["currentGuideGroup"] = "RestedXP 部落 1-30",
          ["currentGuideName"] = "01-06 永歌森林",
          ["guideMetaData"] = {
            ["g"] = { ["name"] = "01-06 永歌森林", ["next"] = "06-10 永歌森林" },
          },
        }'''
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "RXPGuides.lua"
            path.write_text(source, encoding="utf-8")
            info = parse_rxp_saved_variables(path, ["01-06 永歌森林", "06-10 永歌森林"])
        self.assertEqual(info.current_group, "RestedXP 部落 1-30")
        self.assertEqual(info.current_guide, "01-06 永歌森林")
        self.assertEqual(info.matched_chain, ("01-06 永歌森林",))
        self.assertEqual(info.missing_chain, ("06-10 永歌森林",))
        self.assertFalse(info.has_route_body)

    def test_kill_drop_parent_is_must_and_leaf_is_optional(self) -> None:
        data = QuestieData(
            quests={
                1: {10: {3: {1: {1: 100}}}},
                2: {10: {3: {1: {1: 101}}}, 13: {1: 1}},
            },
            npcs={},
            objects={},
            items={
                100: {2: {1: 500}},
                101: {2: {1: 501}},
            },
            quest_names={},
            npc_names={},
            object_names={},
            item_names={},
            version="test",
            source_sha256="test",
        )
        build = SegmentBuild({}, None, {1, 2}, [], {}, [], [])
        result = _build_loot_classifications(data, [build], {}, {1})
        self.assertEqual(result[1], "must")
        self.assertEqual(result[2], "optional")

    def test_pre_single_adds_only_one_available_alternative(self) -> None:
        data = QuestieData(
            quests={1: {}, 2: {}, 3: {13: {1: 1, 2: 2}}},
            npcs={}, objects={}, items={}, quest_names={}, npc_names={}, object_names={}, item_names={},
            version="test", source_sha256="test",
        )
        candidate = {
            "quest_catalog": [
                {"quest_id": 1, "required_level": 1, "quest_level": 1},
                {"quest_id": 2, "required_level": 1, "quest_level": 1},
                {"quest_id": 3, "required_level": 2, "quest_level": 2},
            ],
            "steps": [
                {"quest_ids": [1]},
                {"quest_ids": [2]},
                {"quest_ids": [3]},
            ],
        }
        build = SegmentBuild(
            {"quest_min": 1, "quest_max": 3}, candidate, {3}, [], {}, [], []
        )
        audit = _close_route_prerequisites(data, [build])
        self.assertEqual(audit["unresolved"], [])
        self.assertEqual(len({1, 2} & build.selected_qids), 1)

    def test_pre_group_adds_all_required_parents(self) -> None:
        data = QuestieData(
            quests={1: {}, 2: {}, 3: {12: {1: 1, 2: 2}}},
            npcs={}, objects={}, items={}, quest_names={}, npc_names={}, object_names={}, item_names={},
            version="test", source_sha256="test",
        )
        candidate = {
            "quest_catalog": [
                {"quest_id": 1, "required_level": 1, "quest_level": 1},
                {"quest_id": 2, "required_level": 1, "quest_level": 1},
                {"quest_id": 3, "required_level": 2, "quest_level": 2},
            ],
            "steps": [{"quest_ids": [1]}, {"quest_ids": [2]}, {"quest_ids": [3]}],
        }
        build = SegmentBuild(
            {"quest_min": 1, "quest_max": 3}, candidate, {3}, [], {}, [], []
        )
        audit = _close_route_prerequisites(data, [build])
        self.assertEqual(audit["unresolved"], [])
        self.assertTrue({1, 2, 3}.issubset(build.selected_qids))

    def test_renderer_is_one_large_checklist_without_old_navigation_fields(self) -> None:
        route = {
            "title": "测试路线",
            "segments": [
                {
                    "id": "zone-a",
                    "name": "测试地图",
                    "level_min": 1,
                    "level_max": 2,
                    "steps": [
                        {
                            "text": "接取测试任务；之后：前往目标区域。",
                            "tags": ["五号分别接取"],
                            "quest_ids": [1],
                        }
                    ],
                    "loot_tasks": [],
                }
            ],
        }
        rendered = render_simple_html(route)
        self.assertEqual(rendered.count("<html"), 1)
        self.assertIn('role="tablist"', rendered)
        self.assertIn('type="checkbox"', rendered)
        self.assertIn("localStorage", rendered)
        for term in FORBIDDEN_HTML_TERMS:
            self.assertNotIn(term, rendered)

    def test_validation_requires_visible_loot_label(self) -> None:
        route = {
            "segments": [
                {
                    "id": "zone-a",
                    "name": "测试地图",
                    "steps": [{"text": "完成任务。", "tags": [], "quest_ids": [1]}],
                    "loot_tasks": [
                        {"quest_id": 1, "name": "测试掉落", "classification": "must", "reason": "test"}
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "未在页面步骤中显示标签"):
            validate_simple_route(route)

    def test_generated_page_contract(self) -> None:
        path = PROJECT_ROOT / "data/routes/simple-leveling-route.html"
        rendered = path.read_text(encoding="utf-8")
        self.assertEqual(rendered.count('class="map-tab"'), 42)
        self.assertEqual(rendered.count('class="map-panel"'), 42)
        self.assertIn("逐日岛", rendered)
        self.assertIn("冰冠冰川", rendered)
        self.assertIn("【打怪掉物·必做】", rendered)
        self.assertIn("【打怪掉物·可跳】", rendered)
        self.assertNotIn("Questie", rendered)
        self.assertNotIn("RXP", rendered)
        for term in FORBIDDEN_HTML_TERMS:
            self.assertNotIn(term, rendered)


if __name__ == "__main__":
    unittest.main()
