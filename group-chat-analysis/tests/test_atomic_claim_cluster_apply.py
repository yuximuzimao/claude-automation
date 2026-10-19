from __future__ import annotations

import unittest

from src.analysis.atomic_claim_cluster_apply import build_clusters


def claim(cid, q="问题"):
    return {
        "id": cid, "statement": cid, "entity": "对象", "question": q,
        "kind": "observation", "evidence_type": "player_statement", "certainty": "reported",
    }


def doc(ids):
    return {"items": [{"card": "T1", "claims": [claim(cid) for cid in ids], "refs": []}]}


class AtomicClaimClusterApplyTests(unittest.TestCase):
    def test_two_claim_cluster_requires_explicit_same(self):
        result = build_clusters(doc(["A", "B"]), {
            "decisions": [{"a": "A", "b": "B", "decision": "same_question", "canonical_question": "同一问题"}]
        })
        self.assertEqual(result["counts"]["blocked_clusters"], 0)
        self.assertEqual(result["counts"]["multi_claim_clusters"], 1)

    def test_transitive_chain_is_blocked_without_complete_review(self):
        result = build_clusters(doc(["A", "B", "C"]), {
            "decisions": [
                {"a": "A", "b": "B", "decision": "same_question", "canonical_question": "同一问题"},
                {"a": "B", "b": "C", "decision": "same_question", "canonical_question": "同一问题"},
            ]
        })
        cluster = next(c for c in result["clusters"] if len(c["members"]) == 3)
        self.assertEqual(cluster["status"], "review_required")
        self.assertEqual(cluster["missing_pair_reviews"], [["A", "C"]])

    def test_explicit_different_inside_component_blocks(self):
        result = build_clusters(doc(["A", "B", "C"]), {
            "decisions": [
                {"a": "A", "b": "B", "decision": "same_question", "canonical_question": "同一问题"},
                {"a": "B", "b": "C", "decision": "same_question", "canonical_question": "同一问题"},
                {"a": "A", "b": "C", "decision": "different_question"},
            ]
        })
        self.assertEqual(result["counts"]["blocked_clusters"], 1)

    def test_inconsistent_canonical_question_blocks(self):
        result = build_clusters(doc(["A", "B", "C"]), {
            "decisions": [
                {"a": "A", "b": "B", "decision": "same_question", "canonical_question": "问题一"},
                {"a": "B", "b": "C", "decision": "same_question", "canonical_question": "问题一"},
                {"a": "A", "b": "C", "decision": "same_question", "canonical_question": "问题二"},
            ]
        })
        self.assertEqual(result["counts"]["blocked_clusters"], 1)

    def test_different_pair_does_not_merge(self):
        result = build_clusters(doc(["A", "B"]), {
            "decisions": [{"a": "A", "b": "B", "decision": "different_question"}]
        })
        self.assertEqual(result["counts"]["clusters"], 2)


if __name__ == "__main__":
    unittest.main()
