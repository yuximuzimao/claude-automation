"""Source-anchor review promotion tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analysis import source_anchor_apply as mod


class SourceAnchorApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        day = self.root / "2026-09-21"
        day.mkdir(parents=True)
        (day / "part-01.md").write_text("a\nb\nc\nd\ne\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _proposal(self):
        return {
            "proposals": [{
                "card_id": "T1", "date": "2026-09-21",
                "candidates": [{
                    "score": .08, "margin_from_second": .01,
                    "segments": [{"file": "part-01.md", "start_line": 1, "end_line": 2}],
                }],
            }]
        }

    def test_verified_promotes_top1(self):
        decisions = {"review_batch": "R1", "decisions": {"T1": {"status": "verified", "reviewer": "AI"}}}
        with patch.object(mod, "SOURCE_DIR", self.root):
            out, added = mod.apply_reviews(self._proposal(), decisions, {"schema_version": 1, "anchors": {}})
        self.assertEqual(added, 1)
        self.assertEqual(out["anchors"]["T1"]["segments"][0]["start_line"], 1)

    def test_review_override_replaces_retrieval_window(self):
        decisions = {
            "review_batch": "R1",
            "decisions": {"T1": {
                "status": "verified", "reviewer": "AI",
                "segments_override": [{"file": "part-01.md", "start_line": 4, "end_line": 5}],
            }}
        }
        with patch.object(mod, "SOURCE_DIR", self.root):
            out, _ = mod.apply_reviews(self._proposal(), decisions, {"schema_version": 1, "anchors": {}})
        self.assertEqual(out["anchors"]["T1"]["segments"], [{"file": "part-01.md", "start_line": 4, "end_line": 5}])

    def test_non_verified_is_not_promoted(self):
        decisions = {"decisions": {"T1": {"status": "needs_more_context"}}}
        with patch.object(mod, "SOURCE_DIR", self.root):
            out, added = mod.apply_reviews(self._proposal(), decisions, {"schema_version": 1, "anchors": {}})
        self.assertEqual(added, 0)
        self.assertEqual(out["anchors"], {})

    def test_direct_canonical_review_without_proposal_is_allowed_when_explicit(self):
        decisions = {
            "review_batch": "R-direct",
            "decisions": {
                "T2": {
                    "status": "verified",
                    "reviewer": "AI",
                    "date": "2026-09-21",
                    "segments_override": [
                        {"file": "part-01.md", "start_line": 2, "end_line": 3}
                    ],
                }
            },
        }
        with patch.object(mod, "SOURCE_DIR", self.root):
            out, added = mod.apply_reviews(
                {"proposals": []},
                decisions,
                {"schema_version": 1, "anchors": {}},
            )
        self.assertEqual(added, 1)
        self.assertEqual(out["anchors"]["T2"]["date"], "2026-09-21")
        self.assertEqual(
            out["anchors"]["T2"]["verification"]["source"],
            "direct_canonical_review",
        )
        self.assertIsNone(out["anchors"]["T2"]["verification"]["retrieval_score"])

    def test_direct_canonical_review_requires_date_and_segments(self):
        decisions = {
            "decisions": {
                "T2": {
                    "status": "verified",
                    "segments_override": [
                        {"file": "part-01.md", "start_line": 2, "end_line": 3}
                    ],
                }
            }
        }
        with patch.object(mod, "SOURCE_DIR", self.root):
            with self.assertRaisesRegex(ValueError, "explicit date"):
                mod.apply_reviews(
                    {"proposals": []},
                    decisions,
                    {"schema_version": 1, "anchors": {}},
                )

    def test_refuses_conflicting_verified_anchor(self):
        decisions = {"decisions": {"T1": {"status": "verified"}}}
        existing = {"schema_version": 1, "anchors": {"T1": {
            "date": "2026-09-21",
            "segments": [{"file": "part-01.md", "start_line": 3, "end_line": 3}],
        }}}
        with patch.object(mod, "SOURCE_DIR", self.root):
            with self.assertRaises(ValueError):
                mod.apply_reviews(self._proposal(), decisions, existing)

    def test_invalid_override_is_rejected(self):
        decisions = {"decisions": {"T1": {
            "status": "verified",
            "segments_override": [{"file": "part-01.md", "start_line": 5, "end_line": 7}],
        }}}
        with patch.object(mod, "SOURCE_DIR", self.root):
            with self.assertRaises(ValueError):
                mod.apply_reviews(self._proposal(), decisions, {"schema_version": 1, "anchors": {}})


if __name__ == "__main__":
    unittest.main()
