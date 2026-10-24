from __future__ import annotations

import copy
import unittest

from src.analysis.semantic_fingerprint import (
    build_fingerprint_registry,
    semantic_fingerprint,
    semantic_identity,
)


class SemanticFingerprintTests(unittest.TestCase):
    def unit(self):
        return {
            "knowledge_id": "K1",
            "subject": " 冰DK　命中阈值 ",
            "question": "双持冰DK 要多少命中？",
            "kind": "mechanism",
            "scope": {
                "game_variant": "时光服",
                "class_spec": "双持冰DK",
                "phase_context": "P5",
                "time_window": "2026-10-01..2026-10-18",
                "time_sensitive": True,
            },
            "canonical_facts": ["事实A"],
            "evidence_refs": [{"card_id": "T1"}],
            "evidence_state": "single",
            "freshness": "phase_sensitive",
            "search_terms": ["冰DK"],
            "initial_state": "queue",
        }

    def test_evidence_and_freshness_changes_do_not_change_fingerprint(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["canonical_facts"] = ["事实A", "新增重复支持"]
        b["evidence_refs"].append({"card_id": "T2"})
        b["evidence_state"] = "repeated_support"
        b["freshness"] = "newer"
        b["search_terms"].append("命中")
        b["scope"]["time_window"] = "2026-10-01..2026-10-23"
        b["scope"]["time_sensitive"] = False
        self.assertEqual(semantic_fingerprint(a), semantic_fingerprint(b))

    def test_unicode_and_whitespace_normalize(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["subject"] = "冰DK 命中阈值"
        b["question"] = "  双持冰DK   要多少命中？  "
        self.assertEqual(semantic_fingerprint(a), semantic_fingerprint(b))

    def test_question_change_changes_fingerprint(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["question"] = "双持冰DK 要多少精准？"
        self.assertNotEqual(semantic_fingerprint(a), semantic_fingerprint(b))

    def test_stable_scope_boundary_changes_fingerprint(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["scope"]["phase_context"] = "P6"
        self.assertNotEqual(semantic_fingerprint(a), semantic_fingerprint(b))

    def test_unknown_scope_metadata_does_not_silently_enter_identity(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["scope"]["random_internal_note"] = "new evidence batch"
        self.assertEqual(semantic_fingerprint(a), semantic_fingerprint(b))

    def test_identity_has_only_stable_scope(self):
        identity = semantic_identity(self.unit())
        self.assertEqual(
            identity["scope"],
            {
                "class_spec": "双持冰dk",
                "game_variant": "时光服",
                "phase_context": "p5",
            },
        )

    def test_registry_rejects_exact_semantic_collision(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["knowledge_id"] = "K2"
        with self.assertRaisesRegex(ValueError, "share an exact semantic fingerprint"):
            build_fingerprint_registry({"units": [a, b]})

    def test_registry_allows_same_subject_with_different_question(self):
        a = self.unit()
        b = copy.deepcopy(a)
        b["knowledge_id"] = "K2"
        b["question"] = "双持冰DK 要多少精准？"
        result = build_fingerprint_registry({"units": [a, b]})
        self.assertEqual(result["counts"]["fingerprints"], 2)


if __name__ == "__main__":
    unittest.main()
