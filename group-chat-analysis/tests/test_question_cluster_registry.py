from __future__ import annotations

import unittest

from src.analysis.question_cluster_assignment import retrieve
from src.analysis.question_cluster_assignment_apply import apply_assignments
from src.analysis.question_cluster_bootstrap_apply import apply_bootstrap
from src.analysis.question_cluster_registry import build_registry


def claim(cid, entity, question, statement):
    return {
        "id": cid, "entity": entity, "question": question, "statement": statement,
        "kind": "observation", "evidence_type": "player_statement", "certainty": "reported",
        "source_refs": [{"date": "2026-09-01", "file": "part-01.md", "start_line": 1, "end_line": 1}],
    }


class QuestionClusterRegistryTests(unittest.TestCase):
    def test_registry_requires_complete_cluster_input(self):
        claims = {"items": [{"card": "T1", "claims": [claim("A", "甲", "甲问题？", "甲事实")]}]}
        clusters = {"publication_ready": False, "clusters": []}
        with self.assertRaises(ValueError):
            build_registry(claims, clusters, {"decisions": []})

    def test_registry_preserves_boundary_negative(self):
        claims = {"items": [
            {"card": "T1", "claims": [claim("A", "鞋", "鞋定位？", "这是BIS鞋")]},
            {"card": "T2", "claims": [claim("B", "治疗", "治疗进组？", "治疗不好进组")]},
        ]}
        clusters = {
            "publication_ready": True,
            "clusters": [
                {"cluster_id": "Q-A", "status": "reviewed_complete", "canonical_question": "鞋定位？", "members": ["A"]},
                {"cluster_id": "Q-B", "status": "reviewed_complete", "canonical_question": "治疗进组？", "members": ["B"]},
            ],
        }
        decisions = {"decisions": [{"a": "A", "b": "B", "decision": "different_question", "reason": "不同问题"}]}
        result = build_registry(claims, clusters, decisions)
        a = next(x for x in result["clusters"] if x["question_id"] == "Q-A")
        self.assertEqual(a["boundary_negatives"][0]["outside_claim"], "B")

    def test_assignment_apply_attaches_only_reviewed_target(self):
        registry = {
            "clusters": [{
                "question_id": "Q1", "canonical_question": "旧问题？", "members": ["A"],
                "source_cards": ["T1"], "entities": ["甲"], "kinds": ["observation"],
                "certainties": ["reported"], "inclusion_examples": [{"claim_id": "A", "statement": "甲事实"}],
                "boundary_negatives": [],
            }]
        }
        claims = {"items": [{"card": "T2", "claims": [claim("B", "甲", "新问题？", "新事实")]}]}
        decisions = {"status": "reviewed", "decisions": {
            "B": {"decision": "attach", "question_id": "Q1", "reason": "同一问题"}
        }}
        updated, bootstrap, report = apply_assignments(registry, claims, decisions)
        self.assertEqual(report["attached"], 1)
        self.assertIn("B", updated["clusters"][0]["members"])
        self.assertEqual(bootstrap["atomic_claim_count"], 0)

    def test_assignment_apply_records_question_revision(self):
        registry = {
            "clusters": [{
                "question_id": "Q1", "canonical_question": "2026-09-14当天三区是否开放？", "members": ["A"],
                "source_cards": ["T1"], "entities": ["三区建号"], "kinds": ["dynamic_signal"],
                "certainties": ["reported"], "inclusion_examples": [{"claim_id": "A", "statement": "旧状态"}],
                "boundary_negatives": [],
            }]
        }
        claims = {"items": [{"card": "T2", "claims": [claim("B", "三区建号", "不同时间状态？", "新状态")]}]}
        decisions = {"status": "reviewed", "decisions": {
            "B": {
                "decision": "attach", "question_id": "Q1",
                "canonical_question_override": "三区建号在不同时间点是什么状态？",
                "reason": "新增跨日证据",
            }
        }}
        updated, _, report = apply_assignments(registry, claims, decisions)
        q = updated["clusters"][0]
        self.assertEqual(report["canonical_questions_revised"], 1)
        self.assertEqual(q["canonical_question"], "三区建号在不同时间点是什么状态？")
        self.assertEqual(q["question_revision_history"][0]["from"], "2026-09-14当天三区是否开放？")

    def test_new_question_is_bootstrapped_not_auto_created(self):
        registry = {
            "clusters": [{
                "question_id": "Q1", "canonical_question": "旧问题？", "members": ["A"],
                "source_cards": ["T1"], "entities": ["甲"], "kinds": ["observation"],
                "certainties": ["reported"], "inclusion_examples": [{"claim_id": "A", "statement": "甲事实"}],
                "boundary_negatives": [],
            }]
        }
        claims = {"items": [{"card": "T2", "claims": [claim("B", "乙", "乙问题？", "乙事实")]}]}
        decisions = {"decisions": {"B": {"decision": "new_question", "reason": "无已有问题"}}}
        updated, bootstrap, report = apply_assignments(registry, claims, decisions)
        self.assertEqual(len(updated["clusters"]), 1)
        self.assertEqual(report["new_question_claims"], 1)
        self.assertEqual(bootstrap["atomic_claim_count"], 1)

    def test_bootstrap_requires_exact_claim_coverage(self):
        registry = {"clusters": []}
        claims = {"items": [{"card": "T1", "claims": [
            claim("A", "甲", "甲问题？", "甲事实"),
            claim("B", "乙", "乙问题？", "乙事实"),
        ]}]}
        gold = {"clusters": [{"cluster_id": "Q-A", "canonical_question": "甲问题？", "members": ["A"]}], "must_separate": []}
        with self.assertRaises(ValueError):
            apply_bootstrap(registry, claims, gold)

    def test_bootstrap_appends_reviewed_clusters_and_boundaries(self):
        registry = {"clusters": []}
        claims = {"items": [{"card": "T1", "claims": [
            claim("A", "甲", "共同问题？", "甲事实"),
            claim("B", "甲", "共同问题？", "乙事实"),
            claim("C", "丙", "另一个问题？", "丙事实"),
        ]}]}
        gold = {
            "clusters": [
                {"cluster_id": "Q-AB", "canonical_question": "共同问题？", "members": ["A", "B"]},
                {"cluster_id": "Q-C", "canonical_question": "另一个问题？", "members": ["C"]},
            ],
            "must_separate": [{"a": "A", "b": "C", "reason": "不同问题"}],
        }
        updated, report = apply_bootstrap(registry, claims, gold)
        self.assertEqual(report["new_question_clusters"], 2)
        self.assertEqual(updated["counts"]["reviewed_claims"], 3)
        ab = next(x for x in updated["clusters"] if x["question_id"] == "Q-AB")
        self.assertEqual(ab["members"], ["A", "B"])
        self.assertEqual(ab["boundary_negatives"][0]["outside_claim"], "C")

    def test_assignment_retrieves_cluster_but_does_not_attach(self):
        registry = {
            "clusters": [
                {"question_id": "Q1", "canonical_question": "高尚套牌如何换伟大？", "entities": ["高尚套牌"], "inclusion_examples": [{"statement": "等暗月马戏团交任务"}], "boundary_negatives": []},
                {"question_id": "Q2", "canonical_question": "防骑怎么处理OT？", "entities": ["防骑"], "inclusion_examples": [{"statement": "OT后嘲讽"}], "boundary_negatives": []},
            ]
        }
        new_doc = {"items": [{"card": "T3", "claims": [claim("C", "高尚套牌", "套牌什么时候换伟大？", "等马戏团开放")]}]}
        result = retrieve(new_doc, registry, top_k=1)
        self.assertEqual(result["proposals"][0]["candidates"][0]["question_id"], "Q1")
        self.assertEqual(result["proposals"][0]["status"], "semantic_assignment_required")


if __name__ == "__main__":
    unittest.main()
