from __future__ import annotations

import json
import unittest
from pathlib import Path

from lib.questie_lua import LuaTableParser, parse_embedded_table_text, seq


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LuaTableParserTests(unittest.TestCase):
    def test_parses_mixed_lua_table(self) -> None:
        parsed = LuaTableParser('return {[8325]={"任务",{{15278}}},nilValue=nil,flag=true}').parse()
        self.assertEqual(parsed[8325][1], "任务")
        self.assertEqual(seq(parsed[8325][2])[0][1], 15278)
        self.assertIsNone(parsed["nilValue"])
        self.assertTrue(parsed["flag"])

    def test_parses_questie_embedded_table(self) -> None:
        text = 'QuestieDB.questData = [[return {[1]={"A"},[2]={"B"}}]]'
        parsed = parse_embedded_table_text(text)
        self.assertEqual(parsed[1][1], "A")
        self.assertEqual(parsed[2][1], "B")

    def test_route_spec_steps_are_sequential(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "data/route-specs/sunstrider-isle.json").read_text(encoding="utf-8")
        )
        steps = [step["step"] for step in spec["steps"]]
        self.assertEqual(steps, list(range(1, len(steps) + 1)))
        self.assertEqual(spec["map_area_id"], 3430)
        self.assertEqual(spec["quest_zone_or_sort"], 3431)


if __name__ == "__main__":
    unittest.main()
