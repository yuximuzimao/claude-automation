from __future__ import annotations

import unittest

from src.analysis.reviewed_source_anchor_promotion import build_promoted_anchors


class ReviewedSourceAnchorPromotionTests(unittest.TestCase):
    def test_promotes_reviewed_claim_refs_without_overwriting_existing(self):
        candidates = {
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "source_anchor_confidence": "none"},
                {"card_id": "T2", "date": "2026-09-01", "source_anchor_confidence": "none"},
                {"card_id": "T3", "date": "2026-09-01", "source_anchor_confidence": "high"},
            ]
        }
        verified = {
            "anchors": {
                "T2": {
                    "date": "2026-09-01",
                    "segments": [{"file": "part.md", "start_line": 8, "end_line": 9}],
                }
            }
        }
        atomic = {
            "items": [
                {
                    "card": "T1",
                    "claims": [
                        {
                            "source_refs": [
                                {
                                    "date": "2026-09-01",
                                    "file": "part.md",
                                    "start_line": 1,
                                    "end_line": 2,
                                },
                                {
                                    "date": "2026-09-01",
                                    "file": "part.md",
                                    "start_line": 3,
                                    "end_line": 4,
                                },
                            ]
                        }
                    ],
                },
                {
                    "card": "T2",
                    "claims": [
                        {
                            "source_refs": [
                                {
                                    "date": "2026-09-01",
                                    "file": "part.md",
                                    "start_line": 20,
                                    "end_line": 21,
                                }
                            ]
                        }
                    ],
                },
            ]
        }
        result, audit = build_promoted_anchors(
            candidates, verified, atomic, {"cards": []}
        )
        self.assertEqual(audit["counts"]["promoted_from_reviewed_canonical_refs"], 1)
        self.assertEqual(audit["counts"]["already_verified"], 1)
        self.assertEqual(result["anchors"]["T1"]["segments"], [
            {"file": "part.md", "start_line": 1, "end_line": 4}
        ])
        self.assertEqual(
            result["anchors"]["T2"]["segments"],
            [{"file": "part.md", "start_line": 8, "end_line": 9}],
        )

    def test_promotes_reviewed_no_claim_when_source_refs_exist(self):
        candidates = {
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "source_anchor_confidence": "none"}
            ]
        }
        no_claim = {
            "cards": [{
                "card_id": "T1",
                "source_refs": [{
                    "date": "2026-09-01",
                    "file": "part.md",
                    "start_line": 5,
                    "end_line": 6,
                }],
            }]
        }
        result, audit = build_promoted_anchors(
            candidates, {"anchors": {}}, {"items": []}, no_claim
        )
        self.assertEqual(audit["counts"]["promoted_from_reviewed_canonical_refs"], 1)
        self.assertEqual(
            result["anchors"]["T1"]["verification"]["source"],
            "reviewed_no_claim",
        )

    def test_no_claim_without_source_refs_is_not_fabricated(self):
        candidates = {
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "source_anchor_confidence": "none"}
            ]
        }
        result, audit = build_promoted_anchors(
            candidates,
            {"anchors": {}},
            {"items": []},
            {"cards": [{"card_id": "T1", "source_refs": []}]},
        )
        self.assertNotIn("T1", result["anchors"])
        self.assertEqual(audit["without_source_refs"], ["T1"])

    def test_cross_date_refs_stay_at_claim_level(self):
        candidates = {
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "source_anchor_confidence": "none"}
            ]
        }
        atomic = {
            "items": [{
                "card": "T1",
                "claims": [{
                    "source_refs": [
                        {
                            "date": "2026-09-01",
                            "file": "part.md",
                            "start_line": 1,
                            "end_line": 2,
                        },
                        {
                            "date": "2026-09-02",
                            "file": "part.md",
                            "start_line": 10,
                            "end_line": 11,
                        },
                    ]
                }],
            }]
        }
        result, audit = build_promoted_anchors(
            candidates, {"anchors": {}}, atomic, {"cards": []}
        )
        self.assertEqual(
            result["anchors"]["T1"]["segments"],
            [{"file": "part.md", "start_line": 1, "end_line": 2}],
        )
        self.assertEqual(
            audit["cross_day_supplemental_refs"],
            {"T1": ["2026-09-02"]},
        )

    def test_cross_date_only_refs_do_not_create_card_anchor(self):
        candidates = {
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "source_anchor_confidence": "none"}
            ]
        }
        atomic = {
            "items": [{
                "card": "T1",
                "claims": [{
                    "source_refs": [{
                        "date": "2026-09-02",
                        "file": "part.md",
                        "start_line": 1,
                        "end_line": 2,
                    }]
                }],
            }]
        }
        result, audit = build_promoted_anchors(
            candidates, {"anchors": {}}, atomic, {"cards": []}
        )
        self.assertNotIn("T1", result["anchors"])
        self.assertEqual(audit["without_source_refs"], ["T1"])


if __name__ == "__main__":
    unittest.main()
