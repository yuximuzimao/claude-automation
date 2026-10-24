from __future__ import annotations

import unittest

from src.analysis.infinite_dossier_routing import apply_infinite_dossier_routing


class InfiniteDossierRoutingTests(unittest.TestCase):
    def dossier(self):
        return {
            "schema_version": 2,
            "sections": [{
                "key": "rules",
                "signals": [{
                    "field": "拾取模式",
                    "state": "未确认",
                    "scope": "测试期",
                    "basis": "冲突口径",
                    "evidence_ids": ["T0"],
                }],
            }],
        }

    def silver(self):
        return {
            "units": [{
                "knowledge_id": "K-INF",
                "initial_state": "queue",
                "topics": ["无限服"],
                "evidence_refs": [{"card_id": "T1", "coverage": "full"}],
            }]
        }

    def test_absorb_existing_signal_adds_silver_lineage_and_evidence(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "baseline_absorb",
                "targets": [{"section_key": "rules", "field": "拾取模式"}],
            }],
        }
        result, audit = apply_infinite_dossier_routing(
            self.dossier(), self.silver(), review
        )
        signal = result["sections"][0]["signals"][0]
        self.assertEqual(signal["silver_ids"], ["K-INF"])
        self.assertEqual(signal["evidence_ids"], ["T0", "T1"])
        self.assertEqual(audit["absorbed_knowledge_ids"], ["K-INF"])

    def test_new_signal_is_created_with_lineage(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "visible_update",
                "new_signals": [{
                    "section_key": "rules",
                    "signal": {
                        "field": "团本锁定",
                        "state": "未确认",
                        "scope": "测试期",
                        "basis": "玩家传闻",
                    },
                }],
            }],
        }
        result, audit = apply_infinite_dossier_routing(
            self.dossier(), self.silver(), review
        )
        signal = result["sections"][0]["signals"][1]
        self.assertEqual(signal["silver_ids"], ["K-INF"])
        self.assertEqual(signal["evidence_ids"], ["T1"])
        self.assertEqual(audit["visible_update_knowledge_ids"], ["K-INF"])

    def test_reapplying_same_new_signal_is_idempotent(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "baseline_absorb",
                "new_signals": [{
                    "section_key": "rules",
                    "signal": {
                        "field": "团本锁定",
                        "state": "未确认",
                        "scope": "测试期",
                        "basis": "玩家传闻",
                    },
                }],
            }],
        }
        first, _ = apply_infinite_dossier_routing(
            self.dossier(), self.silver(), review
        )
        second, audit = apply_infinite_dossier_routing(
            first, self.silver(), review
        )
        signals = second["sections"][0]["signals"]
        self.assertEqual(
            sum(signal["field"] == "团本锁定" for signal in signals),
            1,
        )
        self.assertEqual(audit["counts"]["new_signals"], 1)
        self.assertEqual(audit["counts"]["created_new_signals"], 0)
        self.assertEqual(second, first)

    def test_visible_update_can_change_existing_state_and_records_delta(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "visible_update",
                "targets": [{
                    "section_key": "rules",
                    "field": "拾取模式",
                    "state": "官方已确认个人拾取",
                    "basis": "正式规则原文",
                }],
            }],
        }
        result, audit = apply_infinite_dossier_routing(
            self.dossier(), self.silver(), review
        )
        signal = result["sections"][0]["signals"][0]
        self.assertEqual(signal["state"], "官方已确认个人拾取")
        self.assertEqual(signal["basis"], "正式规则原文")
        self.assertEqual(len(audit["visible_changes"]), 1)
        self.assertEqual(
            audit["visible_changes"][0]["before"]["state"],
            "未确认",
        )

    def test_baseline_absorb_cannot_change_existing_state(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "baseline_absorb",
                "targets": [{
                    "section_key": "rules",
                    "field": "拾取模式",
                    "state": "错误改写",
                }],
            }],
        }
        with self.assertRaisesRegex(ValueError, "only visible_update"):
            apply_infinite_dossier_routing(
                self.dossier(), self.silver(), review
            )

    def test_requires_complete_review_of_infinite_queue(self):
        with self.assertRaisesRegex(ValueError, "missing reviewed routing"):
            apply_infinite_dossier_routing(
                self.dossier(),
                self.silver(),
                {"status": "reviewed_infinite_dossier_routing", "items": []},
            )

    def test_rejects_non_infinite_extra_route(self):
        silver = self.silver()
        silver["units"].append({
            "knowledge_id": "K-OTHER",
            "initial_state": "queue",
            "topics": ["DK"],
            "evidence_refs": [],
        })
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [
                {
                    "knowledge_id": "K-INF",
                    "visibility": "baseline_absorb",
                    "targets": [{"section_key": "rules", "field": "拾取模式"}],
                },
                {
                    "knowledge_id": "K-OTHER",
                    "visibility": "baseline_absorb",
                    "targets": [{"section_key": "rules", "field": "拾取模式"}],
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "non-current Infinite"):
            apply_infinite_dossier_routing(self.dossier(), silver, review)

    def test_requires_target_or_new_signal(self):
        review = {
            "status": "reviewed_infinite_dossier_routing",
            "items": [{
                "knowledge_id": "K-INF",
                "visibility": "baseline_absorb",
            }],
        }
        with self.assertRaisesRegex(ValueError, "no target"):
            apply_infinite_dossier_routing(
                self.dossier(), self.silver(), review
            )


if __name__ == "__main__":
    unittest.main()
