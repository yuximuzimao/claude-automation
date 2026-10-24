from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.analysis.review_decision_store import (
    ReviewDecisionError,
    ReviewDecisionStore,
)


def unit(kid: str, state: str, question: str) -> dict:
    return {
        "knowledge_id": kid,
        "subject": "测试对象",
        "question": question,
        "kind": "mechanism",
        "scope": {"game_variant": "时光服"},
        "canonical_facts": ["事实。"],
        "structured": {},
        "evidence_refs": [{"card_id": f"T-{kid}", "coverage": "full"}],
        "initial_state": state,
    }


class ReviewDecisionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.silver = self.root / "silver.json"
        self.decisions = self.root / "decisions.json"
        self.state = self.root / "state.json"
        self.silver.write_text(
            json.dumps({
                "units": [
                    unit("K-Q", "queue", "是否保留？"),
                    unit("K-OLD", "knowledge", "已有知识？"),
                ]
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.times = iter([
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:01Z",
            "2026-01-01T00:00:02Z",
        ])

    def store(self) -> ReviewDecisionStore:
        return ReviewDecisionStore(
            silver_path=self.silver,
            decisions_path=self.decisions,
            state_path=self.state,
            now=lambda: next(self.times),
        )

    def test_knowledge_decision_persists_without_mutating_silver(self):
        before = self.silver.read_bytes()
        result = self.store().apply("K-Q", "knowledge")

        self.assertEqual(result["status"], "updated")
        self.assertEqual(self.silver.read_bytes(), before)
        decisions = json.loads(self.decisions.read_text(encoding="utf-8"))
        self.assertEqual(decisions["items"][0]["knowledge_id"], "K-Q")
        self.assertEqual(decisions["items"][0]["decision"], "knowledge")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        by_id = {
            kid: row["decision"]
            for row in state["states"]
            for kid in row["aliases"]["knowledge_ids"]
        }
        self.assertEqual(by_id["K-Q"], "knowledge")
        self.assertEqual(by_id["K-OLD"], "knowledge")

    def test_same_decision_is_idempotent(self):
        store = self.store()
        first = store.apply("K-Q", "discard")
        first_bytes = self.decisions.read_bytes()
        second = store.apply("K-Q", "discard")

        self.assertEqual(first["status"], "updated")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(self.decisions.read_bytes(), first_bytes)

    def test_changing_decision_replaces_same_knowledge_id(self):
        store = self.store()
        store.apply("K-Q", "discard")
        changed = store.apply("K-Q", "knowledge")

        self.assertEqual(changed["status"], "updated")
        decisions = json.loads(self.decisions.read_text(encoding="utf-8"))
        self.assertEqual(len(decisions["items"]), 1)
        self.assertEqual(decisions["items"][0]["decision"], "knowledge")
        self.assertEqual(decisions["items"][0]["previous_decision"], "discard")

    def test_preserves_historical_card_only_decisions(self):
        self.decisions.write_text(
            json.dumps({
                "schema_version": 1,
                "status": "reviewed_user_semantic_decisions",
                "items": [{
                    "decision": "discard",
                    "decision_source": "user",
                    "semantic_identity": {
                        "subject": "旧弱样本",
                        "question": "旧弱样本是否值得保留？",
                        "kind": "sample",
                        "scope": {"game_variant": "时光服"},
                    },
                    "aliases": {"card_ids": ["T-OLD-CARD"]},
                    "reason": "用户明确排除",
                }],
            }, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        self.store().apply("K-Q", "knowledge")

        decisions = json.loads(self.decisions.read_text(encoding="utf-8"))
        self.assertEqual(len(decisions["items"]), 2)
        self.assertEqual(
            decisions["items"][0]["aliases"]["card_ids"],
            ["T-OLD-CARD"],
        )

    def test_rejects_non_queue_unit(self):
        with self.assertRaisesRegex(ReviewDecisionError, "only target"):
            self.store().apply("K-OLD", "discard")

    def test_rejects_unknown_id_and_invalid_decision(self):
        store = self.store()
        with self.assertRaisesRegex(ReviewDecisionError, "unknown"):
            store.apply("K-MISSING", "discard")
        with self.assertRaisesRegex(ReviewDecisionError, "invalid"):
            store.apply("K-Q", "seen")

    def test_list_formal_decisions_includes_seeded_and_page_decisions(self):
        store = self.store()
        store.apply("K-Q", "discard")
        listed = store.list_formal_decisions()
        rows = {row["knowledge_id"]: row["decision"] for row in listed["items"]}
        self.assertEqual(rows, {"K-OLD": "knowledge", "K-Q": "discard"})


if __name__ == "__main__":
    unittest.main()
