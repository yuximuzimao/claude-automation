from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analysis import atomic_claim_quality as mod


class AtomicClaimQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        day = self.root / "2026-09-01"
        day.mkdir(parents=True)
        (day / "part-01.md").write_text("a\nb\nc\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def doc(self):
        return {
            "status": "calibration_rebuilt_from_canonical",
            "source_cards_rebuilt": 1,
            "atomic_claim_count": 1,
            "items": [{
                "card": "T1",
                "claims": [{
                    "id": "AC1",
                    "statement": "事实",
                    "entity": "对象",
                    "question": "问题",
                    "kind": "observation",
                    "evidence_type": "player_statement",
                    "certainty": "reported",
                    "source_refs": [{"date": "2026-09-01", "file": "part-01.md", "start_line": 1, "end_line": 2}],
                }],
                "rejected": ["不支持的推断"],
                "refs": [{"date": "2026-09-01", "file": "part-01.md", "start_line": 1, "end_line": 2}],
            }],
        }

    def test_valid_calibration_passes(self):
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(self.doc())
        self.assertEqual(result["result"], "PASS")

    def test_invalid_source_range_fails(self):
        doc = self.doc()
        doc["items"][0]["refs"][0]["end_line"] = 9
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(doc)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("source_range_invalid", result["quality"]["by_code"])

    def test_missing_hard_negative_fails(self):
        doc = self.doc()
        doc["items"][0]["rejected"] = []
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(doc)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("no_hard_negative", result["quality"]["by_code"])

    def test_production_does_not_require_artificial_hard_negative(self):
        doc = self.doc()
        doc["status"] = "production_reviewed_from_canonical"
        doc["items"][0]["rejected"] = []
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(doc)
        self.assertEqual(result["result"], "PASS")

    def test_claim_level_source_ref_is_mandatory(self):
        doc = self.doc()
        doc["items"][0]["claims"][0].pop("source_refs")
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(doc)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("claim_missing_source_refs", result["quality"]["by_code"])

    def test_duplicate_claim_id_fails(self):
        doc = self.doc()
        second = dict(doc["items"][0]["claims"][0])
        doc["items"][0]["claims"].append(second)
        doc["atomic_claim_count"] = 2
        with patch.object(mod, "SOURCE_DIR", self.root):
            result = mod.assess(doc)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("duplicate_claim_id", result["quality"]["by_code"])


if __name__ == "__main__":
    unittest.main()
