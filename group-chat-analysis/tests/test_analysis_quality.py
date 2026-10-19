"""Silver 只读质量门禁的确定性合成回归。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.analysis.quality import assess, semantic_coverage_dates


def card(cid, status, refs=None):
    return {
        "card_id": cid, "title": cid, "semantic_summary": "事实", "date": "2026-10-01",
        "silver_status": status, "silver_refs": refs or [],
    }


def unit(uid, refs, state="queue"):
    return {
        "knowledge_id": uid, "subject": "对象", "question": "如何做？",
        "kind": "mechanism", "structured": {}, "canonical_facts": ["事实"],
        "evidence_refs": refs, "initial_state": state,
    }


def item(cid, uid, coverage, role="support"):
    return {"knowledge_id": uid, "coverage": coverage, "role": role}


def scan(candidates, units, ids):
    return assess({"source_queue_count": len(candidates), "candidates": candidates},
                  {"units": units}, set(ids))


class AnalysisQualityTests(unittest.TestCase):
    def test_pass_with_full_and_partial(self):
        u = unit("K1", [{"card_id": "T1", "coverage": "full", "role": "support"},
                        {"card_id": "T2", "coverage": "partial", "role": "support"}])
        r = scan([card("T1", "full", [item("T1", "K1", "full")]),
                  card("T2", "partial", [item("T2", "K1", "partial")]),
                  card("T3", "unabsorbed")], [u], {"T1", "T2", "T3"})
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(r["counts"]["candidate_states"]["unabsorbed"], 1)

    def test_never_hide_partial_card_as_full(self):
        u = unit("K1", [{"card_id": "T1", "coverage": "partial", "role": "support"}])
        r = scan([card("T1", "full", [item("T1", "K1", "partial")])], [u], {"T1"})
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("coverage_state_mismatch", r["quality"]["by_code"])

    def test_dossier_absorption_is_separate_from_silver_status(self):
        x = card("T1", "unabsorbed")
        x["dossier_refs"] = [{"section_key": "rules", "field": "规则"}]
        x["normalized_status"] = "full"
        r = scan([x], [], {"T1"})
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(r["counts"]["candidate_states"]["unabsorbed"], 1)
        self.assertEqual(r["counts"]["normalized_candidate_states"]["full"], 1)

    def test_missing_card_ref_is_hard_error(self):
        u = unit("K1", [{"role": "support"}])
        r = scan([card("T1", "unabsorbed")], [u], {"T1"})
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("missing_source_ref", r["quality"]["by_code"])

    def test_external_reference_without_locator_is_warning_not_card_loss(self):
        u = unit("K1", [{"card_id": "T1", "coverage": "full", "role": "support"},
                        {"external": "官方解释", "role": "object_identity"}])
        r = scan([card("T1", "full", [item("T1", "K1", "full")])], [u], {"T1"})
        self.assertEqual(r["result"], "PASS_WITH_WARNINGS")
        self.assertIn("external_source_no_locator", r["quality"]["by_code"])

    def test_legacy_missing_coverage_reported(self):
        u = unit("K1", [{"card_id": "T1", "role": "support"}])
        r = scan([card("T1", "full", [item("T1", "K1", "full")])], [u], {"T1"})
        self.assertEqual(r["result"], "PASS_WITH_WARNINGS")
        self.assertIn("legacy_implicit_full", r["quality"]["by_code"])

    def test_multi_unit_full_coverage_warning(self):
        u1 = unit("K1", [{"card_id": "T1", "coverage": "full", "role": "support"}])
        u2 = unit("K2", [{"card_id": "T1", "coverage": "full", "role": "support"}])
        r = scan([card("T1", "full", [item("T1", "K1", "full"), item("T1", "K2", "full")])],
                 [u1, u2], {"T1"})
        self.assertIn("multi_unit_full_coverage", r["quality"]["by_code"])

    def test_orphan_source_is_error(self):
        u = unit("K1", [{"card_id": "DOES_NOT_EXIST", "coverage": "full", "role": "support"},
                        {"card_id": "T1", "coverage": "full", "role": "support"}])
        r = scan([card("T1", "full", [item("T1", "K1", "full")])], [u], {"T1"})
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("unknown_source_card", r["quality"]["by_code"])

    def test_missing_direct_source_anchor_is_visible(self):
        x = card("T1", "unabsorbed")
        x["source_anchor_confidence"] = "none"
        r = scan([x], [], {"T1"})
        self.assertIn("source_anchors_need_backfill", r["quality"]["by_code"])
        self.assertEqual(r["counts"]["source_anchor_confidence"]["none"], 1)

    def test_duplicate_candidate_id_is_error(self):
        r = scan([card("T1", "unabsorbed"), card("T1", "unabsorbed")], [], {"T1"})
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("duplicate_candidate_id", r["quality"]["by_code"])

    def test_queue_unit_without_queue_source_is_visible_warning(self):
        r = scan([card("T1", "unabsorbed")],
                 [unit("K1", [{"card_id": "T2", "coverage": "full", "role": "support"}])],
                 {"T1", "T2"})
        self.assertIn("queue_unit_no_current_candidate", r["quality"]["by_code"])

    def test_semantic_coverage_dates_reports_unindexed_bronze_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chunks = root / "chunks"
            topics = root / "topics"
            (chunks / "2026-10-12").mkdir(parents=True)
            (chunks / "2026-10-13").mkdir(parents=True)
            topics.mkdir()
            (topics / "2026-10-12.md").write_text("# x\n", encoding="utf-8")
            result = semantic_coverage_dates(chunks, topics)
        self.assertEqual(result["missing_topic_candidate_dates"], ["2026-10-13"])
        self.assertEqual(result["orphan_topic_candidate_dates"], [])


if __name__ == "__main__":
    unittest.main()
