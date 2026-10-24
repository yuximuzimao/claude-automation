from __future__ import annotations

import copy
import unittest

from src.analysis.reviewed_semantic_state import build_reviewed_semantic_state


def unit(kid="K1", state="queue", question="问题？"):
    return {
        "knowledge_id": kid,
        "subject": "测试",
        "question": question,
        "kind": "mechanism",
        "scope": {"game_variant": "时光服"},
        "canonical_facts": ["事实"],
        "structured": {},
        "evidence_refs": [{"card_id": "T1", "coverage": "full"}],
        "initial_state": state,
    }


class ReviewedSemanticStateTests(unittest.TestCase):
    def test_only_knowledge_silver_is_seeded_as_reviewed(self):
        result = build_reviewed_semantic_state({
            "units": [unit("KQ", "queue"), unit("KK", "knowledge", "另一个问题？")]
        })
        self.assertEqual(result["counts"]["states"], 1)
        self.assertEqual(result["counts"]["knowledge_states"], 1)
        self.assertEqual(result["states"][0]["aliases"]["knowledge_ids"], ["KK"])

    def test_explicit_discard_card_state_is_not_knowledge(self):
        decisions = {
            "status": "reviewed_user_semantic_decisions",
            "items": [{
                "decision": "discard",
                "decision_source": "user",
                "semantic_identity": {
                    "subject": "低价值样本",
                    "question": "这个弱样本是否值得再次展示？",
                    "kind": "sample",
                    "scope": {"game_variant": "时光服"},
                },
                "aliases": {"card_ids": ["T-DISCARD"]},
                "reason": "用户明确判为无用",
            }],
        }
        result = build_reviewed_semantic_state({"units": []}, decisions)
        self.assertEqual(result["counts"]["discard_states"], 1)
        self.assertEqual(result["counts"]["knowledge_states"], 0)

    def test_system_filter_cannot_enter_user_state(self):
        decisions = {
            "status": "reviewed_user_semantic_decisions",
            "items": [{
                "decision": "discard",
                "decision_source": "system",
                "semantic_identity": {
                    "subject": "过滤项",
                    "question": "是否显示？",
                    "kind": "sample",
                    "scope": {},
                },
                "aliases": {"card_ids": ["T1"]},
            }],
        }
        with self.assertRaisesRegex(ValueError, "explicit user decisions"):
            build_reviewed_semantic_state({"units": []}, decisions)

    def test_explicit_decision_can_reference_formal_knowledge_id(self):
        q = unit("KQ", "queue")
        decisions = {
            "status": "reviewed_user_semantic_decisions",
            "items": [{
                "decision": "discard",
                "decision_source": "user",
                "knowledge_id": "KQ",
                "reason": "用户点没用",
            }],
        }
        result = build_reviewed_semantic_state({"units": [q]}, decisions)
        self.assertEqual(result["counts"]["discard_states"], 1)
        self.assertEqual(
            result["states"][0]["aliases"]["knowledge_ids"],
            ["KQ"],
        )

    def test_conflicting_decision_for_existing_knowledge_fails(self):
        k = unit("KK", "knowledge")
        decisions = {
            "status": "reviewed_user_semantic_decisions",
            "items": [{
                "decision": "discard",
                "decision_source": "user",
                "knowledge_id": "KK",
                "reason": "冲突",
            }],
        }
        with self.assertRaisesRegex(ValueError, "conflicting user decisions"):
            build_reviewed_semantic_state({"units": [k]}, decisions)

    def test_evidence_change_does_not_create_second_state(self):
        k = unit("KK", "knowledge")
        decisions = {
            "status": "reviewed_user_semantic_decisions",
            "items": [{
                "decision": "knowledge",
                "decision_source": "user",
                "semantic_identity": {
                    "subject": "测试",
                    "question": "问题？",
                    "kind": "mechanism",
                    "scope": {"game_variant": "时光服"},
                },
                "aliases": {"card_ids": ["T2"]},
                "source_refs": [{"card_id": "T2", "coverage": "full"}],
                "reason": "同一语义新增证据",
            }],
        }
        result = build_reviewed_semantic_state({"units": [k]}, decisions)
        self.assertEqual(result["counts"]["states"], 1)
        self.assertEqual(
            result["states"][0]["aliases"]["card_ids"],
            ["T2"],
        )


if __name__ == "__main__":
    unittest.main()
