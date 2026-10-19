from __future__ import annotations

import unittest

from src.analysis.cluster_proposals import grams, neighbors, proposals, vectors


def row(cid, topic="法师", status="unabsorbed", title=None, normalized_status=None):
    result = {
        "card_id": cid, "title": title or cid, "semantic_summary": title or cid,
        "topics": [topic], "silver_status": status,
    }
    if normalized_status is not None:
        result["normalized_status"] = normalized_status
    return result


class ClusterProposalTests(unittest.TestCase):
    def test_similarity_retrieval_finds_cross_day_rephrasing(self):
        rows = [row("A", title="冰法急速过高会触及GCD下限"),
                row("B", title="冰法急速叠加时GCD和寒冰箭读条出现饱和"),
                row("C", title="公会团团长如何计算工资")]
        self.assertTrue(grams("冰法急速"))
        result = neighbors(rows, vectors(rows), k=2)
        self.assertEqual(result[0][0][0], 1)

    def test_complete_link_does_not_chain_unrelated_claims(self):
        rows = [row("A"), row("B"), row("C")]
        top = [[(1, .9), (2, .1)], [(0, .9), (2, .9)], [(1, .9), (0, .1)]]
        result = proposals(rows, top, threshold=.58)
        self.assertEqual(result["counts"]["groups"], 2)
        self.assertEqual(result["counts"]["grouped_sources"], 2)

    def test_topics_are_retrieval_guard_not_duplicate_navigation(self):
        rows = [row("A", "经济 / 打金"), row("B", "副本攻略")]
        top = [[(1, .96)], [(0, .96)]]
        result = proposals(rows, top)
        self.assertEqual(result["counts"]["groups"], 2)

    def test_full_source_never_returns_to_proposal(self):
        rows = [row("A", status="full"), row("B")]
        result = proposals(rows, [[(1, .99)], [(0, .99)]])
        self.assertEqual(result["counts"]["non_full_candidates"], 1)
        self.assertEqual(result["groups"][0]["members"], ["B"])

    def test_dossier_absorbed_source_never_returns_to_proposal(self):
        rows = [row("A", normalized_status="full"), row("B")]
        result = proposals(rows, [[(1, .99)], [(0, .99)]])
        self.assertEqual(result["counts"]["non_full_candidates"], 1)
        self.assertEqual(result["groups"][0]["members"], ["B"])

    def test_semantic_error_is_quarantined_until_rebuilt(self):
        rows = [row("A"), row("B"), row("C")]
        top = [[(1, .95)], [(0, .95), (2, .95)], [(1, .95)]]
        result = proposals(rows, top, quarantine_ids={"B"})
        self.assertEqual(result["counts"]["quarantined_semantic_errors"], 1)
        self.assertEqual(sorted(c for g in result["groups"] for c in g["members"]), ["A", "C"])

    def test_every_live_source_appears_once_and_id_is_stable(self):
        rows = [row("A"), row("B"), row("C", status="partial")]
        top = [[(1, .8)], [(0, .8)], []]
        a = proposals(rows, top)
        b = proposals(rows, top)
        self.assertEqual(a, b)
        self.assertEqual(sorted(c for g in a["groups"] for c in g["members"]), ["A", "B", "C"])
        self.assertTrue(all(g["status"] == "review_required" for g in a["groups"]))


if __name__ == "__main__":
    unittest.main()
