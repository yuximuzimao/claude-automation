from __future__ import annotations

import copy
import unittest

from src.analysis.legacy_knowledge_migration import (
    apply_legacy_knowledge_migration,
)


class LegacyKnowledgeMigrationTests(unittest.TestCase):
    def base_unit(self):
        return {
            "knowledge_id": "K-NEW",
            "subject": "测试知识",
            "question": "这个测试结论是什么？",
            "kind": "mechanism",
            "topics": ["测试"],
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["测试事实。"],
            "structured": {"mechanism": "测试。"},
            "evidence_refs": [
                {"card_id": "T-OLD", "role": "core", "coverage": "full"}
            ],
            "search_terms": ["测试"],
            "evidence_state": "user_confirmed_legacy_migration",
            "freshness": "stable",
            "initial_state": "knowledge",
            "legacy_aliases": {"card_ids": ["T-OLD"]},
        }

    def review(self, unit=None):
        return {
            "status": "reviewed_legacy_knowledge_silver_migration",
            "units": [unit or self.base_unit()],
        }

    def test_migrates_verified_user_confirmed_knowledge(self):
        silver = {
            "units": [{
                "knowledge_id": "K-OLD",
                "subject": "已有知识",
                "question": "已有问题？",
                "kind": "mechanism",
                "scope": {},
                "canonical_facts": ["已有。"],
                "structured": {},
                "evidence_refs": [{"card_id": "T-X", "coverage": "full"}],
                "initial_state": "queue",
            }]
        }
        anchors = {"anchors": {"T-OLD": {}, "T-X": {}}}
        result, audit = apply_legacy_knowledge_migration(
            silver, self.review(), anchors
        )
        self.assertEqual(len(result["units"]), 2)
        self.assertEqual(audit["counts"]["migrated_units"], 1)
        self.assertEqual(audit["counts"]["knowledge_after"], 1)
        self.assertEqual(audit["counts"]["queue_after"], 1)

    def test_requires_verified_source_anchor(self):
        with self.assertRaisesRegex(ValueError, "lacks verified source anchor"):
            apply_legacy_knowledge_migration(
                {"units": []},
                self.review(),
                {"anchors": {}},
            )

    def test_refuses_existing_knowledge_id(self):
        existing = copy.deepcopy(self.base_unit())
        with self.assertRaisesRegex(ValueError, "already exists"):
            apply_legacy_knowledge_migration(
                {"units": [existing]},
                self.review(),
                {"anchors": {"T-OLD": {}}},
            )

    def test_refuses_card_already_owned_by_silver(self):
        existing = copy.deepcopy(self.base_unit())
        existing["knowledge_id"] = "K-EXISTING"
        existing["subject"] = "别的知识"
        existing["question"] = "别的问题？"
        with self.assertRaisesRegex(ValueError, "already owned"):
            apply_legacy_knowledge_migration(
                {"units": [existing]},
                self.review(),
                {"anchors": {"T-OLD": {}}},
            )

    def test_requires_knowledge_state(self):
        unit = self.base_unit()
        unit["initial_state"] = "queue"
        with self.assertRaisesRegex(ValueError, "must be knowledge"):
            apply_legacy_knowledge_migration(
                {"units": []},
                self.review(unit),
                {"anchors": {"T-OLD": {}}},
            )

    def test_rejects_exact_semantic_collision_with_existing_silver(self):
        unit = self.base_unit()
        existing = copy.deepcopy(unit)
        existing["knowledge_id"] = "K-EXISTING"
        existing["evidence_refs"] = [
            {"card_id": "T-X", "coverage": "full"}
        ]
        existing["legacy_aliases"] = {"card_ids": ["T-X"]}
        with self.assertRaisesRegex(ValueError, "share an exact semantic fingerprint"):
            apply_legacy_knowledge_migration(
                {"units": [existing]},
                self.review(unit),
                {"anchors": {"T-OLD": {}, "T-X": {}}},
            )


if __name__ == "__main__":
    unittest.main()
