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
    _distance_band,
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
                            "text": "接取《测试任务》。",
                            "tags": ["五号分别接取"],
                            "quest_ids": [1],
                            "quest_kinds": {"测试任务": "simple"},
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
        self.assertIn('class="quest-name quest-simple"', rendered)
        for term in FORBIDDEN_HTML_TERMS:
            self.assertNotIn(term, rendered)

    def test_validation_rejects_optional_task_inside_public_flow(self) -> None:
        route = {
            "segments": [
                {
                    "id": "zone-a",
                    "name": "测试地图",
                    "steps": [{"text": "完成任务。", "tags": [], "quest_ids": [1]}],
                    "public_steps": [{"text": "完成任务。", "tags": [], "quest_ids": [1]}],
                    "optional_tasks": [{"quest_id": 1, "name": "测试掉落"}],
                    "loot_tasks": [
                        {"quest_id": 1, "name": "测试掉落", "classification": "optional", "reason": "test"}
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "可选任务仍混在主流程中"):
            validate_simple_route(route)

    def test_distance_bands_use_review_thresholds(self) -> None:
        self.assertEqual(_distance_band(2.5), ("same", "同一区域"))
        self.assertEqual(_distance_band(2.51), ("near", "附近"))
        self.assertEqual(_distance_band(5), ("near", "附近"))
        self.assertEqual(_distance_band(5.01), ("separate", "不同任务点"))
        self.assertEqual(_distance_band(8), ("separate", "不同任务点"))
        self.assertEqual(_distance_band(8.01), ("far", "较远"))

    def test_generated_page_contract(self) -> None:
        path = PROJECT_ROOT / "data/routes/simple-leveling-route.html"
        rendered = path.read_text(encoding="utf-8")
        self.assertEqual(rendered.count('class="map-tab"'), 42)
        self.assertEqual(rendered.count('class="map-panel"'), 42)
        self.assertIn("逐日岛", rendered)
        self.assertIn("冰冠冰川", rendered)
        self.assertIn('class="quest-name quest-collect"', rendered)
        self.assertIn('class="quest-name quest-simple"', rendered)
        self.assertEqual(rendered.count('<input type="checkbox"'), 132)
        self.assertIn("尚未人工整理，暂不提供路线", rendered)
        self.assertIn("把炉石绑定在鹰翼广场", rendered)
        self.assertIn('<details class="quest-detail', rendered)
        self.assertIn("补经验任务", rendered)
        self.assertIn("980 经验", rendered)
        self.assertIn("必须先完成：《鱼头......》", rendered)
        self.assertIn("必须先完成：《戴索姆之战》", rendered)
        self.assertIn("必须先完成：《科卡尔首领》", rendered)
        self.assertIn("必须先完成：《野猪人的内战》", rendered)
        self.assertIn('class="detail-prerequisite"', rendered)
        self.assertIn('class="focus-term"', rendered)
        self.assertIn('class="target-focus"', rendered)
        self.assertNotIn("五开判断", rendered)
        self.assertNotIn("无前置任务", rendered)
        self.assertNotIn("任务等级 9 的同级基础经验", rendered)
        self.assertIn("标记过远", rendered)
        self.assertIn("复制过远标记", rendered)
        self.assertIn("同一区域 · 0.3", rendered)

        panels = {
            panel_id: rendered.split(f'id="panel-{panel_id}"', 1)[1].split('</section>', 1)[0]
            for panel_id in (
                "sunstrider-1-6",
                "eversong-6-12",
                "ghostlands-12-20",
                "barrens-20-22",
                "stonetalon-22-24",
            )
        }
        for panel_id in ("sunstrider-1-6", "eversong-6-12", "ghostlands-12-20", "barrens-20-22"):
            self.assertNotIn('class="legacy-step-text"', panels[panel_id])
        self.assertNotIn("尚未人工整理", panels["ghostlands-12-20"])
        self.assertNotIn("尚未人工整理", panels["barrens-20-22"])
        self.assertIn("尚未人工整理", panels["stonetalon-22-24"])
        self.assertIn("达尔坎·德拉希尔", panels["ghostlands-12-20"])
        self.assertIn("曼科里克的妻子", panels["barrens-20-22"])
        self.assertIn("十字路口西侧营地", panels["barrens-20-22"])
        self.assertIn("雷戈萨·死门", panels["barrens-20-22"])

        eversong_main = panels["eversong-6-12"].split('<ol>', 1)[1].split('</ol>', 1)[0]
        self.assertNotIn("鱼头......", eversong_main)
        self.assertNotIn("失落的军备", eversong_main)
        self.assertNotIn("收集豹皮", eversong_main)
        self.assertNotIn("到学徒梅雷多尔集中接取《学徒的欺瞒》", rendered)
        self.assertNotIn("【打怪掉物·必做】", rendered)
        self.assertNotIn("【打怪掉物·可跳】", rendered)
        self.assertNotIn("之后：", rendered)
        self.assertNotIn("Questie", rendered)
        self.assertNotIn("RXP", rendered)
        for term in FORBIDDEN_HTML_TERMS:
            self.assertNotIn(term, rendered)


if __name__ == "__main__":
    unittest.main()
