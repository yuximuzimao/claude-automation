from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from src.analysis.analysis_release import sha256_json
from src.analysis.question_cluster_assignment_apply import _recount
from src.analysis.question_registry_store import (
    QuestionRegistryError,
    QuestionRegistryStore,
    validate_monotonic_update,
)


def registry() -> dict:
    doc = {
        "schema_version": 1,
        "status": "reviewed_question_cluster_registry_not_silver",
        "contract": {},
        "counts": {},
        "clusters": [
            {
                "question_id": "Q1",
                "canonical_question": "问题一？",
                "status": "reviewed",
                "members": ["C1"],
                "source_cards": ["T1"],
                "entities": ["对象A"],
                "kinds": ["mechanism"],
                "certainties": ["observed"],
                "inclusion_examples": [
                    {"claim_id": "C1", "statement": "事实一"}
                ],
                "boundary_negatives": [
                    {
                        "inside_claim": "C1",
                        "outside_claim": "C-X",
                        "reason": "不同问题",
                    }
                ],
            },
            {
                "question_id": "Q2",
                "canonical_question": "问题二？",
                "status": "reviewed",
                "members": ["C2"],
                "source_cards": ["T2"],
                "entities": ["对象B"],
                "kinds": ["strategy"],
                "certainties": ["reported"],
                "inclusion_examples": [
                    {"claim_id": "C2", "statement": "事实二"}
                ],
                "boundary_negatives": [],
            },
        ],
    }
    _recount(doc)
    return doc


class QuestionRegistryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.store = QuestionRegistryStore(
            current_path=self.root / "current.json",
            snapshots_dir=self.root / "snapshots",
            metadata_path=self.root / "current.meta.json",
        )

    def test_bootstrap_and_idempotent_republish(self):
        base = registry()
        first = self.store.publish(base, source_label="v71")
        second = self.store.publish(base, source_label="v71")

        self.assertEqual(first["status"], "published")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(first["current_sha256"], second["current_sha256"])
        snapshots = list((self.root / "snapshots").glob("*.json"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(json.loads((self.root / "current.json").read_text()), base)

    def test_attach_claim_and_add_new_question_are_monotonic(self):
        base = registry()
        self.store.publish(base, source_label="base")
        next_doc = copy.deepcopy(base)
        q1 = next_doc["clusters"][0]
        q1["members"].append("C3")
        q1["source_cards"].append("T3")
        q1["entities"].append("对象C")
        q1["certainties"].append("verified")
        q1["inclusion_examples"].append(
            {"claim_id": "C3", "statement": "补充事实"}
        )
        next_doc["clusters"].append({
            "question_id": "Q3",
            "canonical_question": "问题三？",
            "status": "reviewed",
            "members": ["C4"],
            "source_cards": ["T4"],
            "entities": ["对象D"],
            "kinds": ["sample"],
            "certainties": ["observed"],
            "inclusion_examples": [
                {"claim_id": "C4", "statement": "新事实"}
            ],
            "boundary_negatives": [],
        })
        _recount(next_doc)

        result = self.store.publish(
            next_doc,
            source_label="daily",
            expected_previous_sha256=sha256_json(base),
        )

        self.assertEqual(result["status"], "published")
        self.assertEqual(result["counts"]["reviewed_claims"], 4)
        self.assertEqual(result["counts"]["reviewed_question_clusters"], 3)

    def test_existing_question_cannot_disappear(self):
        base = registry()
        candidate = copy.deepcopy(base)
        candidate["clusters"] = candidate["clusters"][:1]
        _recount(candidate)
        with self.assertRaisesRegex(QuestionRegistryError, "cannot disappear"):
            validate_monotonic_update(base, candidate)

    def test_existing_claim_cannot_move_or_disappear(self):
        base = registry()
        moved = copy.deepcopy(base)
        moved["clusters"][0]["members"] = ["C-NEW"]
        moved["clusters"][0]["inclusion_examples"] = [
            {"claim_id": "C-NEW", "statement": "新成员"}
        ]
        moved["clusters"][1]["members"].append("C1")
        moved["clusters"][1]["source_cards"].append("T1")
        moved["clusters"][1]["entities"].append("对象A")
        moved["clusters"][1]["kinds"].append("mechanism")
        moved["clusters"][1]["certainties"].append("observed")
        _recount(moved)
        with self.assertRaisesRegex(QuestionRegistryError, "cannot move"):
            validate_monotonic_update(base, moved)

        missing = copy.deepcopy(base)
        missing["clusters"][0]["members"] = ["C-NEW"]
        missing["clusters"][0]["inclusion_examples"] = [
            {"claim_id": "C-NEW", "statement": "替换"}
        ]
        _recount(missing)
        with self.assertRaisesRegex(QuestionRegistryError, "cannot disappear"):
            validate_monotonic_update(base, missing)

    def test_scope_fields_and_boundaries_cannot_shrink(self):
        base = registry()
        candidate = copy.deepcopy(base)
        candidate["clusters"][0]["source_cards"] = []
        _recount(candidate)
        with self.assertRaisesRegex(QuestionRegistryError, "shrank source_cards"):
            validate_monotonic_update(base, candidate)

        candidate = copy.deepcopy(base)
        candidate["clusters"][0]["boundary_negatives"] = []
        _recount(candidate)
        with self.assertRaisesRegex(QuestionRegistryError, "lost boundary"):
            validate_monotonic_update(base, candidate)

    def test_canonical_question_change_requires_revision_history(self):
        base = registry()
        candidate = copy.deepcopy(base)
        candidate["clusters"][0]["canonical_question"] = "修订后问题？"
        _recount(candidate)
        with self.assertRaisesRegex(QuestionRegistryError, "revision history"):
            validate_monotonic_update(base, candidate)

        candidate["clusters"][0]["question_revision_history"] = [{
            "from": "问题一？",
            "to": "修订后问题？",
            "reason": "人工确认边界更准确",
            "decision_source": "reviewed_daily_assignment",
        }]
        validate_monotonic_update(base, candidate)

    def test_expected_previous_hash_prevents_stale_publish(self):
        base = registry()
        self.store.publish(base, source_label="base")
        candidate = copy.deepcopy(base)
        candidate["clusters"][0]["entities"].append("对象C")
        _recount(candidate)

        with self.assertRaisesRegex(QuestionRegistryError, "changed since"):
            self.store.publish(
                candidate,
                source_label="daily",
                expected_previous_sha256="0" * 64,
            )

    def test_stale_counts_are_rejected(self):
        bad = registry()
        bad["counts"]["reviewed_claims"] = 999
        with self.assertRaisesRegex(QuestionRegistryError, "counts are stale"):
            self.store.publish(bad, source_label="bad")


if __name__ == "__main__":
    unittest.main()
