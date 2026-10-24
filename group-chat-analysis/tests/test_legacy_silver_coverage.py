from __future__ import annotations

import unittest

from src.analysis.legacy_silver_coverage import apply_reviewed_legacy_coverage


class LegacySilverCoverageTests(unittest.TestCase):
    def base(self):
        return {
            "units": [{
                "knowledge_id": "K1",
                "evidence_refs": [
                    {"card_id": "T1", "role": "core"},
                    {"card_id": "T2", "role": "support", "coverage": "partial"},
                ],
            }]
        }

    def test_applies_only_missing_coverage(self):
        review = {
            "status": "reviewed_legacy_silver_coverage",
            "items": [{
                "knowledge_id": "K1",
                "card_id": "T1",
                "coverage": "full",
                "reason": "reviewed",
            }],
        }
        result, audit = apply_reviewed_legacy_coverage(self.base(), review)
        refs = result["units"][0]["evidence_refs"]
        self.assertEqual(refs[0]["coverage"], "full")
        self.assertEqual(refs[1]["coverage"], "partial")
        self.assertEqual(audit["counts"]["applied"], 1)
        self.assertEqual(audit["counts"]["legacy_refs_after"], 0)

    def test_missing_decision_fails_closed(self):
        review = {
            "status": "reviewed_legacy_silver_coverage",
            "items": [],
        }
        with self.assertRaisesRegex(ValueError, "missing reviewed decisions"):
            apply_reviewed_legacy_coverage(self.base(), review)

    def test_stale_decision_fails_closed(self):
        review = {
            "status": "reviewed_legacy_silver_coverage",
            "items": [
                {"knowledge_id": "K1", "card_id": "T1", "coverage": "full"},
                {"knowledge_id": "K1", "card_id": "T2", "coverage": "full"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "not legacy-missing coverage"):
            apply_reviewed_legacy_coverage(self.base(), review)

    def test_rejects_invalid_coverage(self):
        review = {
            "status": "reviewed_legacy_silver_coverage",
            "items": [{
                "knowledge_id": "K1",
                "card_id": "T1",
                "coverage": "all",
            }],
        }
        with self.assertRaisesRegex(ValueError, "invalid legacy coverage decision"):
            apply_reviewed_legacy_coverage(self.base(), review)


if __name__ == "__main__":
    unittest.main()
