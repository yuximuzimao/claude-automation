from __future__ import annotations

import unittest

from src.analysis.atomic_claim_queue import classify


def row(cid="T1", status="unabsorbed", confidence="high", normalized_status=None):
    result = {
        "card_id": cid,
        "silver_status": status,
        "source_anchor_confidence": confidence,
    }
    if normalized_status is not None:
        result["normalized_status"] = normalized_status
    return result


class AtomicClaimQueueTests(unittest.TestCase):
    def test_full_is_not_reprocessed(self):
        self.assertEqual(classify(row(status="full"), set()), "already_full_silver")

    def test_dossier_absorbed_source_is_not_reprocessed(self):
        self.assertEqual(
            classify(row(status="unabsorbed", normalized_status="full"), set()),
            "already_normalized",
        )

    def test_semantic_error_overrides_good_anchor(self):
        self.assertEqual(classify(row(cid="BAD", confidence="high"), {"BAD"}), "semantic_rebuild_required")

    def test_reviewed_atomic_claim_does_not_reenter_work_queue(self):
        self.assertEqual(classify(row(cid="DONE", confidence="high"), {"DONE"}, {"DONE"}), "atomic_claim_reviewed")

    def test_no_claim_reviewed_card_does_not_reenter_work_queue(self):
        self.assertEqual(
            classify(row(cid="NOCLAIM", confidence="high"), set(), set(), {"NOCLAIM"}),
            "atomic_claim_no_claim_reviewed",
        )

    def test_high_anchor_is_ready(self):
        self.assertEqual(classify(row(confidence="high"), set()), "ready_from_high_anchor")

    def test_medium_anchor_requires_review(self):
        self.assertEqual(classify(row(confidence="medium"), set()), "needs_anchor_review")

    def test_missing_anchor_routes_to_direct_retrieval(self):
        self.assertEqual(classify(row(confidence="none"), set()), "needs_direct_source_retrieval")


if __name__ == "__main__":
    unittest.main()
