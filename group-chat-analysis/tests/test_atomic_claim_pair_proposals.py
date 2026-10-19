from __future__ import annotations

import unittest

from src.analysis.atomic_claim_pair_proposals import flatten, retrieve


def claim(cid, entity, question, statement, refs=None):
    return {
        "id": cid,
        "entity": entity,
        "question": question,
        "statement": statement,
        "kind": "observation",
        "evidence_type": "player_statement",
        "certainty": "reported",
        "source_refs": refs or [],
    }


class AtomicClaimPairProposalTests(unittest.TestCase):
    def test_claim_level_source_refs_are_preserved(self):
        claim_refs = [{"date": "2026-09-01", "file": "a.md", "start_line": 2, "end_line": 3}]
        item_refs = [{"date": "2026-09-01", "file": "a.md", "start_line": 1, "end_line": 9}]
        doc = {"items": [{"card": "T1", "refs": item_refs, "claims": [
            claim("A", "甲", "甲问题", "甲事实", claim_refs),
        ]}]}
        rows = flatten(doc)
        self.assertEqual(rows[0]["source_refs"], claim_refs)

    def test_same_source_card_adds_recall_even_when_not_lexical_topk(self):
        rows = flatten({"items": [
            {"card": "T1", "claims": [
                claim("A", "祖尔法拉克", "祖尔法拉克流程为什么长？", "要看剧情"),
                claim("B", "玛拉顿", "玛拉顿旧攻略路线有什么摩擦？", "旧攻略前置不同"),
            ]},
            {"card": "T2", "claims": [
                claim("C", "祖尔法拉克", "祖尔法拉克为什么又臭又长？", "流程很长"),
            ]},
        ]})
        pairs = retrieve(rows, top_k=1)
        pair = next(p for p in pairs if {p["a"], p["b"]} == {"A", "B"})
        self.assertIn("same_source_card", pair["routes"])

    def test_exact_entity_is_recall_only_route(self):
        rows = flatten({"items": [
            {"card": "T1", "claims": [claim("A", "奶骑", "奶骑数量？", "奶骑少")]},
            {"card": "T2", "claims": [claim("B", "奶骑", "奶骑责任？", "倒T背锅")]},
        ]})
        pair = retrieve(rows, top_k=1)[0]
        self.assertTrue(pair["same_entity"])
        self.assertIn("same_entity", pair["routes"])


if __name__ == "__main__":
    unittest.main()
