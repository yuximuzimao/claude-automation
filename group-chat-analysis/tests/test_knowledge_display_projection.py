from __future__ import annotations

import unittest

from src.analysis import page_builder


class KnowledgeDisplayProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.units = [{
            "knowledge_id": "K-TEST-001",
            "subject": "测试主题",
            "question": "原始问题",
            "canonical_facts": ["事实一", "事实二"],
            "evidence_refs": [{"card_id": "T1", "coverage": "full"}],
        }]

    def _apply(self, projection: dict) -> list[dict]:
        fn = getattr(page_builder, "apply_knowledge_display_projection", None)
        self.assertIsNotNone(fn, "page_builder must expose display projection application")
        return fn(self.units, projection)

    def test_multiple_qas_get_stable_fingerprints(self) -> None:
        projected = self._apply({
            "schema_version": 1,
            "status": "reviewed_knowledge_display_projection",
            "items": [{
                "knowledge_id": "K-TEST-001",
                "display_status": "visible",
                "qas": [
                    {
                        "qa_id": "K-TEST-001::q01",
                        "question": "问题一？",
                        "answer": "结论一。",
                        "confidence": "high",
                        "lifecycle": "durable",
                        "time_context": "",
                        "verification_note": "",
                        "evidence_refs": ["T1"],
                    },
                    {
                        "qa_id": "K-TEST-001::q02",
                        "question": "问题二？",
                        "answer": "结论二。",
                        "confidence": "medium",
                        "lifecycle": "time_bound",
                        "time_context": "P6首周 · 2026-10-08..2026-10-18",
                        "verification_note": "需要后续实况核验",
                        "evidence_refs": ["T1"],
                    },
                ],
            }],
        })
        self.assertEqual(len(projected[0]["display_qas"]), 2)
        self.assertEqual(projected[0]["display_qas"][0]["confidence"], "high")
        self.assertRegex(projected[0]["display_qas"][0]["qa_fingerprint"], r"^[a-f0-9]{64}$")
        self.assertNotEqual(
            projected[0]["display_qas"][0]["qa_fingerprint"],
            projected[0]["display_qas"][1]["qa_fingerprint"],
        )

    def test_confidence_change_does_not_change_qa_fingerprint(self) -> None:
        base = {
            "schema_version": 1,
            "status": "reviewed_knowledge_display_projection",
            "items": [{
                "knowledge_id": "K-TEST-001",
                "display_status": "visible",
                "qas": [{
                    "qa_id": "K-TEST-001::q01",
                    "question": "问题？",
                    "answer": "同一结论。",
                    "confidence": "medium",
                    "lifecycle": "durable",
                    "time_context": "",
                    "verification_note": "",
                    "evidence_refs": ["T1"],
                }],
            }],
        }
        before = self._apply(base)[0]["display_qas"][0]["qa_fingerprint"]
        base["items"][0]["qas"][0]["confidence"] = "high"
        after = self._apply(base)[0]["display_qas"][0]["qa_fingerprint"]
        self.assertEqual(before, after)

    def test_answer_change_does_change_qa_fingerprint(self) -> None:
        base = {
            "schema_version": 1,
            "status": "reviewed_knowledge_display_projection",
            "items": [{
                "knowledge_id": "K-TEST-001",
                "display_status": "visible",
                "qas": [{
                    "qa_id": "K-TEST-001::q01",
                    "question": "问题？",
                    "answer": "结论一。",
                    "confidence": "medium",
                    "lifecycle": "durable",
                    "time_context": "",
                    "verification_note": "",
                    "evidence_refs": ["T1"],
                }],
            }],
        }
        before = self._apply(base)[0]["display_qas"][0]["qa_fingerprint"]
        base["items"][0]["qas"][0]["answer"] = "结论二。"
        after = self._apply(base)[0]["display_qas"][0]["qa_fingerprint"]
        self.assertNotEqual(before, after)

    def test_time_bound_requires_time_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "time_context"):
            self._apply({
                "schema_version": 1,
                "status": "reviewed_knowledge_display_projection",
                "items": [{
                    "knowledge_id": "K-TEST-001",
                    "display_status": "visible",
                    "qas": [{
                        "qa_id": "K-TEST-001::q01",
                        "question": "问题？",
                        "answer": "结论。",
                        "confidence": "low",
                        "lifecycle": "time_bound",
                        "time_context": "",
                        "verification_note": "",
                        "evidence_refs": ["T1"],
                    }],
                }],
            })

    def test_duplicate_qa_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate qa_id"):
            self._apply({
                "schema_version": 1,
                "status": "reviewed_knowledge_display_projection",
                "items": [{
                    "knowledge_id": "K-TEST-001",
                    "display_status": "visible",
                    "qas": [
                        {
                            "qa_id": "K-TEST-001::q01",
                            "question": "问题一？",
                            "answer": "结论一。",
                            "confidence": "high",
                            "lifecycle": "durable",
                            "time_context": "",
                            "verification_note": "",
                            "evidence_refs": ["T1"],
                        },
                        {
                            "qa_id": "K-TEST-001::q01",
                            "question": "问题二？",
                            "answer": "结论二。",
                            "confidence": "high",
                            "lifecycle": "durable",
                            "time_context": "",
                            "verification_note": "",
                            "evidence_refs": ["T1"],
                        },
                    ],
                }],
            })

    def test_projection_must_cover_every_silver_unit(self) -> None:
        units = self.units + [{
            "knowledge_id": "K-TEST-002",
            "subject": "第二主题",
            "question": "第二问题",
            "canonical_facts": ["第二事实"],
            "evidence_refs": [{"card_id": "T2", "coverage": "full"}],
        }]
        fn = getattr(page_builder, "apply_knowledge_display_projection", None)
        with self.assertRaisesRegex(ValueError, "missing knowledge_id"):
            fn(units, {
                "schema_version": 1,
                "status": "reviewed_knowledge_display_projection",
                "items": [{
                    "knowledge_id": "K-TEST-001",
                    "display_status": "visible",
                    "qas": [{
                        "qa_id": "K-TEST-001::q01",
                        "question": "问题？",
                        "answer": "结论。",
                        "confidence": "medium",
                        "lifecycle": "durable",
                        "time_context": "",
                        "verification_note": "",
                        "evidence_refs": ["T1"],
                    }],
                }],
            })

    def test_unknown_silver_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown knowledge_id"):
            self._apply({
                "schema_version": 1,
                "status": "reviewed_knowledge_display_projection",
                "items": [{
                    "knowledge_id": "K-NOT-THERE",
                    "display_status": "hidden_no_value",
                    "reason": "无展示价值",
                    "qas": [],
                }],
            })


if __name__ == "__main__":
    unittest.main()
