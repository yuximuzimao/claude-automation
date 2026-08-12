import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_35_55_overlap_blocks.py"
SPEC = importlib.util.spec_from_file_location("overlap_blocks", SCRIPT)
overlap_blocks = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(overlap_blocks)


class OverlapBlockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph, cls.blocks, cls.audit = overlap_blocks.build_outputs()
        cls.candidates = json.loads(
            overlap_blocks.CANDIDATES_PATH.read_text(encoding="utf-8")
        )
        cls.task_by_id = {
            task["quest_id"]: task
            for task in cls.candidates["tasks"]
            if task.get("remaining_35_55_candidate")
        }

    def test_required_edge_types_and_strengths(self):
        self.assertEqual(
            set(overlap_blocks.EDGE_STRENGTH),
            set(self.graph["edge_type_counts"]),
        )
        self.assertTrue(
            all(count >= 0 for count in self.graph["edge_type_counts"].values())
        )
        for edge in self.graph["edges"]:
            self.assertEqual(
                overlap_blocks.EDGE_STRENGTH[edge["edge_type"]], edge["strength"]
            )

    def test_all_remaining_candidate_ids_are_nodes(self):
        self.assertEqual(self.candidates["remaining_candidate_count"], 654)
        self.assertEqual(set(self.task_by_id), {node["quest_id"] for node in self.graph["nodes"]})

    def test_strong_entity_edges_are_directly_recomputable(self):
        features = {
            quest_id: overlap_blocks.task_features(task)
            for quest_id, task in self.task_by_id.items()
        }
        feature_pairs = {
            "same_kill_npc": ("kill_npcs", "kill_npcs"),
            "same_item_source_npc": ("item_source_npcs", "item_source_npcs"),
            "kill_and_item_source_same_npc": ("kill_npcs", "item_source_npcs"),
            "same_world_object": ("world_objects", "world_objects"),
            "same_item_source_object": ("item_source_objects", "item_source_objects"),
        }
        for edge in self.graph["edges"]:
            if edge["edge_type"] not in feature_pairs:
                continue
            left_feature, right_feature = feature_pairs[edge["edge_type"]]
            left_id, right_id = edge["source_quest_id"], edge["target_quest_id"]
            left = set(features[left_id][left_feature])
            right = set(features[right_id][right_feature])
            expected = left & right
            if edge["edge_type"] == "kill_and_item_source_same_npc":
                expected |= set(features[left_id][right_feature]) & set(features[right_id][left_feature])
            evidence = {item["entity_id"] for item in edge["common_entities"]}
            self.assertEqual(expected, evidence)

    def test_blocks_preserve_ids_and_required_task_fields(self):
        required = {
            "quest_id",
            "name",
            "map",
            "current_state",
            "required_level",
            "quest_level",
            "risk_flags",
            "prerequisites",
        }
        for block in self.blocks["blocks"]:
            self.assertGreaterEqual(len(block["task_ids"]), 2)
            self.assertTrue(set(block["task_ids"]).issubset(self.task_by_id))
            self.assertEqual(block["task_ids"], [task["quest_id"] for task in block["tasks"]])
            for task in block["tasks"]:
                self.assertTrue(required.issubset(task))

    def test_repeat_generation_is_stable(self):
        graph_again, blocks_again, audit_again = overlap_blocks.build_outputs()
        self.assertEqual(self.graph, graph_again)
        self.assertEqual(self.blocks, blocks_again)
        self.assertEqual(self.audit, audit_again)

    def test_audit_minimum_examples(self):
        self.assertGreaterEqual(len(self.blocks["obvious_duplicate_combat_blocks"]), 10)
        self.assertGreaterEqual(len(self.blocks["anti_merge_examples"]), 10)
        self.assertEqual(self.blocks["current_processable_count"], 88)

    def test_priority_audit_is_complete_overlay(self):
        priority, markdown = overlap_blocks.build_priority_audit(self.graph, self.blocks)
        self.assertEqual(priority["audited_task_count"], 278)
        required = {
            "quest_id",
            "name",
            "audit_status",
            "objective_counts",
            "mechanic",
            "fivebox_rule",
            "source_selection_rule",
            "drop_reference_summary",
            "fixed_wait_or_script_time",
            "known_overlap_task_ids",
            "risk_flags",
            "correction_reason",
            "evidence",
        }
        self.assertEqual(
            len(priority["records"]),
            len({record["quest_id"] for record in priority["records"]}),
        )
        for record in priority["records"]:
            self.assertTrue(required.issubset(record))
            self.assertIn(
                record["audit_status"], {"confirmed", "corrected", "needs_live_test"}
            )
            self.assertTrue(record["audit_scope_reasons"])
        self.assertIn("按地图审计", markdown)


if __name__ == "__main__":
    unittest.main()
