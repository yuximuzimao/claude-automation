from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.analysis.question_cluster_silver_assignment import retrieve
from src.analysis.question_cluster_silver_assignment_apply import apply_routing
from src.analysis.question_cluster_silver_routing_registry import build_draft_queue, build_registry, build_remaining_queue
from src.analysis.silver_draft_pair_proposals import retrieve as retrieve_draft_pairs
from src.analysis.silver_draft_consolidation_registry import build_registry as build_draft_consolidation_registry
from src.analysis.silver_draft_materialization import materialize as materialize_silver_drafts


def cluster(qid: str, question: str, cards: list[str], *, entity: str = "对象") -> dict:
    return {
        "question_id": qid,
        "canonical_question": question,
        "members": [f"AC-{qid}"],
        "source_cards": cards,
        "entities": [entity],
        "inclusion_examples": [{"claim_id": f"AC-{qid}", "statement": question}],
    }


def unit(
    kid: str,
    question: str,
    cards: list[tuple[str, str | None]],
    *,
    subject: str = "对象",
) -> dict:
    refs = []
    for card_id, coverage in cards:
        ref = {"card_id": card_id, "role": "support"}
        if coverage is not None:
            ref["coverage"] = coverage
        refs.append(ref)
    return {
        "knowledge_id": kid,
        "subject": subject,
        "question": question,
        "kind": "mechanism",
        "canonical_facts": [question],
        "search_terms": [subject],
        "evidence_refs": refs,
        "initial_state": "queue",
    }


class QuestionClusterSilverAssignmentTests(unittest.TestCase):
    def test_lexical_retrieval_is_proposal_only(self):
        registry = {"clusters": [
            cluster("Q1", "高尚套牌什么时候换伟大？", ["T1"], entity="高尚套牌"),
        ]}
        silver = {"units": [
            unit("K1", "高尚套牌如何兑换伟大？", [], subject="高尚套牌"),
            unit("K2", "防骑仇恨不足怎么办？", [], subject="防骑"),
        ]}
        result = retrieve(registry, silver, top_k=1)
        proposal = result["proposals"][0]
        self.assertEqual(proposal["status"], "semantic_assignment_required")
        self.assertEqual(proposal["candidates"][0]["knowledge_id"], "K1")
        self.assertEqual(proposal["candidates"][0]["routes"], ["lexical_topk"])

    def test_source_overlap_is_included_even_outside_lexical_topk(self):
        registry = {"clusters": [
            cluster("Q1", "治疗驱散怎么处理？", ["T-SHARED"], entity="奶萨"),
        ]}
        silver = {"units": [
            unit("K-LEX", "治疗驱散有哪些职责？", [], subject="奶萨"),
            unit("K-OVERLAP", "完全不同的历史问题？", [("T-SHARED", "partial")], subject="其它"),
        ]}
        result = retrieve(registry, silver, top_k=1)
        candidates = {row["knowledge_id"]: row for row in result["proposals"][0]["candidates"]}
        self.assertIn("K-LEX", candidates)
        self.assertIn("K-OVERLAP", candidates)
        self.assertIn("source_card_overlap", candidates["K-OVERLAP"]["routes"])
        self.assertEqual(candidates["K-OVERLAP"]["overlap_coverage"]["partial"], 1)

    def test_legacy_missing_coverage_is_preserved_not_promoted_to_full(self):
        registry = {"clusters": [cluster("Q1", "问题？", ["T1"])]}
        silver = {"units": [unit("K1", "别的问题？", [("T1", None)])]}
        result = retrieve(registry, silver, top_k=0)
        candidate = result["proposals"][0]["candidates"][0]
        self.assertEqual(candidate["overlap_coverage"], {
            "full": 0,
            "partial": 0,
            "legacy_missing": 1,
        })
        self.assertEqual(candidate["routes"], ["source_card_overlap"])

    def test_every_question_appears_exactly_once_and_inputs_are_not_mutated(self):
        registry = {"clusters": [
            cluster("Q1", "甲问题？", ["T1"], entity="甲"),
            cluster("Q2", "乙问题？", ["T2"], entity="乙"),
        ]}
        silver = {"units": [unit("K1", "甲问题？", [("T1", "full")], subject="甲")]}
        registry_before = repr(registry)
        silver_before = repr(silver)
        result = retrieve(registry, silver, top_k=1)
        self.assertEqual([row["question_id"] for row in result["proposals"]], ["Q1", "Q2"])
        self.assertEqual(len({row["question_id"] for row in result["proposals"]}), 2)
        self.assertEqual(repr(registry), registry_before)
        self.assertEqual(repr(silver), silver_before)

    def test_empty_silver_still_emits_assignment_rows(self):
        registry = {"clusters": [cluster("Q1", "甲问题？", ["T1"])]}
        result = retrieve(registry, {"units": []}, top_k=5)
        self.assertEqual(result["counts"]["reviewed_questions"], 1)
        self.assertEqual(result["proposals"][0]["candidates"], [])
        self.assertEqual(result["proposals"][0]["status"], "semantic_assignment_required")

    def test_negative_top_k_rejected(self):
        with self.assertRaises(ValueError):
            retrieve({"clusters": []}, {"units": []}, top_k=-1)

    def test_apply_routing_supports_multiple_existing_targets(self):
        proposals = {
            "proposals": [{
                "question_id": "Q1",
                "canonical_question": "奥杜尔为什么又难又久？",
                "entities": ["奥杜尔"],
                "source_cards": ["T1"],
                "claim_count": 2,
            }]
        }
        silver = {"units": [
            unit("K-DIFF", "为什么削弱后仍会灭团？", []),
            unit("K-TIME", "为什么时长不能固定？", []),
        ]}
        decisions = {"decisions": {
            "Q1": {
                "decision": "reuse_existing",
                "targets": [
                    {"knowledge_id": "K-DIFF", "relation": "existing_split"},
                    {"knowledge_id": "K-TIME", "relation": "existing_split"},
                ],
                "reason": "一个reviewed question已被两条更窄Silver共同覆盖",
            }
        }}
        routing, drafts, counts = apply_routing(proposals, silver, decisions)
        self.assertEqual(counts["reused_questions"], 1)
        self.assertEqual(counts["existing_silver_links"], 2)
        self.assertEqual(drafts["count"], 0)
        self.assertEqual(len(routing["items"][0]["targets"]), 2)

    def test_apply_routing_new_draft_keeps_related_silver_without_mutating_it(self):
        proposals = {
            "proposals": [{
                "question_id": "Q1",
                "canonical_question": "新问题？",
                "entities": ["甲"],
                "source_cards": ["T1"],
                "claim_count": 3,
            }]
        }
        silver = {"units": [unit("K1", "相关旧问题？", [])]}
        before = repr(silver)
        decisions = {"decisions": {
            "Q1": {
                "decision": "new_draft",
                "related_silver_ids": ["K1"],
                "reason": "旧Silver只部分相关，需要新草稿",
            }
        }}
        routing, drafts, counts = apply_routing(proposals, silver, decisions)
        self.assertEqual(counts["new_draft_questions"], 1)
        self.assertEqual(drafts["items"][0]["related_silver_ids"], ["K1"])
        self.assertEqual(repr(silver), before)
        self.assertEqual(routing["status"], "reviewed_question_to_silver_routing_not_applied_to_silver")

    def test_apply_routing_requires_exact_question_coverage(self):
        proposals = {
            "proposals": [
                {"question_id": "Q1", "canonical_question": "甲？"},
                {"question_id": "Q2", "canonical_question": "乙？"},
            ]
        }
        silver = {"units": [unit("K1", "甲？", [])]}
        decisions = {"decisions": {
            "Q1": {
                "decision": "reuse_existing",
                "targets": [{"knowledge_id": "K1", "relation": "same_question"}],
                "reason": "同题",
            }
        }}
        with self.assertRaises(ValueError):
            apply_routing(proposals, silver, decisions)

    def test_apply_routing_rejects_unknown_target_and_invalid_relation(self):
        proposals = {"proposals": [{"question_id": "Q1", "canonical_question": "甲？"}]}
        silver = {"units": [unit("K1", "甲？", [])]}
        unknown = {"decisions": {
            "Q1": {
                "decision": "reuse_existing",
                "targets": [{"knowledge_id": "NOPE", "relation": "same_question"}],
                "reason": "测试",
            }
        }}
        with self.assertRaises(ValueError):
            apply_routing(proposals, silver, unknown)
        invalid = {"decisions": {
            "Q1": {
                "decision": "reuse_existing",
                "targets": [{"knowledge_id": "K1", "relation": "automatic_merge"}],
                "reason": "测试",
            }
        }}
        with self.assertRaises(ValueError):
            apply_routing(proposals, silver, invalid)

    def test_apply_routing_allows_explicit_batch_scope(self):
        proposals = {
            "proposals": [
                {"question_id": "Q1", "canonical_question": "甲？"},
                {"question_id": "Q2", "canonical_question": "乙？"},
            ]
        }
        silver = {"units": [unit("K1", "甲？", [])]}
        decisions = {
            "scope_question_ids": ["Q1"],
            "decisions": {
                "Q1": {
                    "decision": "reuse_existing",
                    "targets": [{"knowledge_id": "K1", "relation": "same_question"}],
                    "reason": "本批只审核Q1",
                }
            },
        }
        routing, drafts, counts = apply_routing(proposals, silver, decisions)
        self.assertEqual([row["question_id"] for row in routing["items"]], ["Q1"])
        self.assertEqual(counts["reused_questions"], 1)
        self.assertEqual(drafts["count"], 0)

    def test_routing_registry_aggregates_batches_and_rejects_duplicate_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.json"
            b = root / "b.json"
            a.write_text(json.dumps({
                "status": "reviewed_question_to_silver_routing_not_applied_to_silver",
                "items": [{
                    "question_id": "Q1",
                    "canonical_question": "甲？",
                    "decision": "reuse_existing",
                    "reason": "同题",
                    "targets": [{"knowledge_id": "K1", "relation": "same_question"}],
                }],
            }, ensure_ascii=False), encoding="utf-8")
            b.write_text(json.dumps({
                "status": "reviewed_question_to_silver_routing_not_applied_to_silver",
                "items": [{
                    "question_id": "Q2",
                    "canonical_question": "乙？",
                    "decision": "new_draft",
                    "reason": "缺口",
                    "related_silver_ids": ["K2"],
                }],
            }, ensure_ascii=False), encoding="utf-8")
            registry = build_registry([("a", a), ("b", b)])
            self.assertEqual(registry["counts"]["reviewed_questions"], 2)
            self.assertEqual(registry["counts"]["reused_questions"], 1)
            self.assertEqual(registry["counts"]["new_draft_questions"], 1)
            self.assertEqual(registry["counts"]["existing_silver_links"], 1)

            b.write_text(json.dumps({
                "status": "reviewed_question_to_silver_routing_not_applied_to_silver",
                "items": [{
                    "question_id": "Q1",
                    "canonical_question": "重复？",
                    "decision": "needs_review",
                    "reason": "重复测试",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_registry([("a", a), ("b", b)])

    def test_remaining_queue_excludes_reviewed_and_prioritizes_source_overlap(self):
        proposals = {
            "proposals": [
                {
                    "question_id": "Q-REVIEWED",
                    "canonical_question": "已审？",
                    "claim_count": 1,
                    "candidates": [{"knowledge_id": "K1", "score": 0.9, "routes": ["lexical_topk"]}],
                },
                {
                    "question_id": "Q-LEX",
                    "canonical_question": "纯语义？",
                    "claim_count": 8,
                    "candidates": [{"knowledge_id": "K2", "score": 0.8, "routes": ["lexical_topk"]}],
                },
                {
                    "question_id": "Q-OVERLAP",
                    "canonical_question": "共享来源？",
                    "claim_count": 1,
                    "candidates": [{"knowledge_id": "K3", "score": 0.1, "routes": ["source_card_overlap"]}],
                },
            ]
        }
        registry = {"items": [{"question_id": "Q-REVIEWED"}]}
        queue = build_remaining_queue(proposals, registry)
        self.assertEqual(queue["counts"], {
            "total_questions": 3,
            "reviewed_questions": 1,
            "active_work_items": 2,
            "remaining_with_source_overlap": 1,
            "remaining_semantic_only": 1,
        })
        self.assertEqual([row["question_id"] for row in queue["items"]], ["Q-OVERLAP", "Q-LEX"])

    def test_draft_queue_contains_only_new_drafts_with_proposal_metadata(self):
        proposals = {
            "proposals": [
                {
                    "question_id": "Q-NEW",
                    "canonical_question": "新草稿？",
                    "entities": ["甲"],
                    "source_cards": ["T1", "T2"],
                    "claim_count": 3,
                },
                {
                    "question_id": "Q-REUSE",
                    "canonical_question": "旧Silver？",
                    "entities": ["乙"],
                    "source_cards": ["T3"],
                    "claim_count": 1,
                },
            ]
        }
        registry = {
            "items": [
                {
                    "question_id": "Q-NEW",
                    "canonical_question": "新草稿？",
                    "decision": "new_draft",
                    "related_silver_ids": ["K1"],
                    "reason": "现有Silver未完整覆盖",
                    "review_origin": "b1",
                },
                {
                    "question_id": "Q-REUSE",
                    "canonical_question": "旧Silver？",
                    "decision": "reuse_existing",
                    "targets": [{"knowledge_id": "K2", "relation": "same_question"}],
                    "reason": "同题",
                    "review_origin": "b1",
                },
            ]
        }
        queue = build_draft_queue(proposals, registry)
        self.assertEqual(queue["counts"], {
            "draft_questions": 1,
            "questions_with_existing_silver_context": 1,
            "questions_without_existing_silver_context": 0,
        })
        self.assertEqual(queue["items"][0]["question_id"], "Q-NEW")
        self.assertEqual(queue["items"][0]["claim_count"], 3)
        self.assertEqual(queue["items"][0]["source_cards"], ["T1", "T2"])
        self.assertEqual(queue["items"][0]["related_silver_ids"], ["K1"])

    def test_draft_pair_retrieval_uses_source_and_context_without_auto_merge(self):
        drafts = {
            "items": [
                {
                    "question_id": "Q1",
                    "canonical_question": "冰DK双持怎么配装？",
                    "entities": ["冰DK"],
                    "source_cards": ["T-SHARED"],
                    "related_silver_ids": ["K-DK"],
                    "reason": "需要新草稿",
                },
                {
                    "question_id": "Q2",
                    "canonical_question": "冰DK双手怎么配装？",
                    "entities": ["冰DK"],
                    "source_cards": ["T2"],
                    "related_silver_ids": ["K-DK"],
                    "reason": "需要新草稿",
                },
                {
                    "question_id": "Q3",
                    "canonical_question": "完全不同的问题？",
                    "entities": ["其它"],
                    "source_cards": ["T-SHARED"],
                    "related_silver_ids": [],
                    "reason": "需要新草稿",
                },
            ]
        }
        result = retrieve_draft_pairs(drafts, top_k=0, context_top_k=1)
        pairs = {tuple(sorted((row["a"], row["b"]))): row for row in result["pairs"]}
        self.assertIn(("Q1", "Q2"), pairs)
        self.assertIn("same_entity", pairs[("Q1", "Q2")]["routes"])
        self.assertIn("shared_silver_context_topk", pairs[("Q1", "Q2")]["routes"])
        self.assertIn(("Q1", "Q3"), pairs)
        self.assertIn("same_source_card", pairs[("Q1", "Q3")]["routes"])
        self.assertEqual(result["status"], "silver_draft_pair_proposal_only")

    def test_draft_pair_context_route_is_bounded_per_question(self):
        drafts = {
            "items": [
                {
                    "question_id": qid,
                    "canonical_question": question,
                    "entities": [],
                    "source_cards": [],
                    "related_silver_ids": ["K-CONTEXT"],
                    "reason": "",
                }
                for qid, question in [
                    ("Q1", "法师急速怎么配？"),
                    ("Q2", "法师急速阈值？"),
                    ("Q3", "法师装备预算？"),
                    ("Q4", "法师练级路线？"),
                ]
            ]
        }
        result = retrieve_draft_pairs(drafts, top_k=0, context_top_k=1)
        context_pairs = [
            row for row in result["pairs"]
            if "shared_silver_context_topk" in row["routes"]
        ]
        self.assertLessEqual(len(context_pairs), 4)
        self.assertGreaterEqual(len(context_pairs), 2)

    def test_draft_consolidation_registry_groups_excludes_and_keeps_queue(self):
        drafts = {
            "items": [
                {"question_id": "Q1", "canonical_question": "甲？", "source_cards": ["T1"], "claim_count": 2},
                {"question_id": "Q2", "canonical_question": "乙？", "source_cards": ["T2"], "claim_count": 1},
                {"question_id": "Q3", "canonical_question": "丙？", "source_cards": ["T3"], "claim_count": 4},
                {"question_id": "Q4", "canonical_question": "丁？", "source_cards": ["T4"], "claim_count": 3},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b1.json"
            path.write_text(json.dumps({
                "status": "reviewed_silver_draft_consolidation",
                "groups": [{
                    "group_id": "SG1",
                    "canonical_question": "甲乙如何统一？",
                    "members": ["Q1", "Q2"],
                    "reason": "同一最终知识单元",
                }],
                "exclusions": [{"question_id": "Q3", "reason": "超出项目范围"}],
                "separations": [{"a": "Q1", "b": "Q4", "reason": "不同问题"}],
            }, ensure_ascii=False), encoding="utf-8")
            registry, queue = build_draft_consolidation_registry(drafts, [("b1", path)])
        self.assertEqual(registry["counts"]["assigned_questions"], 2)
        self.assertEqual(registry["counts"]["excluded_questions"], 1)
        self.assertEqual(registry["counts"]["active_work_items"], 1)
        self.assertEqual(registry["counts"]["provisional_groups"], 1)
        self.assertEqual(registry["counts"]["separation_boundaries"], 1)
        self.assertEqual(queue["items"][0]["question_id"], "Q4")

    def test_draft_consolidation_registry_rejects_double_assignment(self):
        drafts = {"items": [
            {"question_id": "Q1", "canonical_question": "甲？", "source_cards": [], "claim_count": 1},
            {"question_id": "Q2", "canonical_question": "乙？", "source_cards": [], "claim_count": 1},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b1.json"
            path.write_text(json.dumps({
                "status": "reviewed_silver_draft_consolidation",
                "groups": [
                    {"group_id": "SG1", "canonical_question": "一？", "members": ["Q1"], "reason": "一"},
                    {"group_id": "SG2", "canonical_question": "二？", "members": ["Q1", "Q2"], "reason": "二"},
                ],
            }, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_draft_consolidation_registry(drafts, [("b1", path)])

    def test_materialize_silver_drafts_preserves_claims_sources_and_coverage(self):
        groups = {
            "status": "reviewed_silver_draft_consolidation_registry_not_published",
            "counts": {"assigned_questions": 2},
            "groups": [{
                "group_id": "SG1",
                "canonical_question": "甲乙如何统一？",
                "members": ["Q1", "Q2"],
                "claim_count": 2,
                "reasons": ["同题"],
                "review_origins": ["b1"],
            }],
        }
        questions = {"clusters": [
            {
                "question_id": "Q1",
                "canonical_question": "甲？",
                "members": ["C1"],
                "entities": ["甲"],
                "kinds": ["mechanism"],
                "certainties": ["reported"],
            },
            {
                "question_id": "Q2",
                "canonical_question": "乙？",
                "members": ["C2"],
                "entities": ["乙"],
                "kinds": ["sample"],
                "certainties": ["direct_sample"],
            },
        ]}
        atomic = {"items": [
            {
                "card": "T1",
                "review_origin": "a1",
                "review_source_file": "a1.json",
                "claims": [
                    {
                        "id": "C1",
                        "statement": "甲事实",
                        "entity": "甲",
                        "question": "甲？",
                        "kind": "mechanism",
                        "evidence_type": "player_explanation",
                        "certainty": "reported",
                        "source_refs": [{"date": "2026-09-01", "file": "part.md", "start_line": 1, "end_line": 2}],
                    },
                    {
                        "id": "C-OTHER",
                        "statement": "另一个事实",
                        "entity": "其它",
                        "question": "其它？",
                        "kind": "mechanism",
                        "evidence_type": "player_report",
                        "certainty": "reported",
                        "source_refs": [{"date": "2026-09-01", "file": "part.md", "start_line": 3, "end_line": 4}],
                    },
                ],
            },
            {
                "card": "T2",
                "review_origin": "a2",
                "review_source_file": "a2.json",
                "claims": [{
                    "id": "C2",
                    "statement": "乙样本",
                    "entity": "乙",
                    "question": "乙？",
                    "kind": "sample",
                    "evidence_type": "player_report",
                    "certainty": "direct_sample",
                    "source_refs": [{"date": "2026-09-02", "file": "part.md", "start_line": 5, "end_line": 6}],
                }],
            },
        ]}
        drafts = {"items": [
            {"question_id": "Q1", "related_silver_ids": ["K1"]},
            {"question_id": "Q2", "related_silver_ids": ["K1", "K2"]},
        ]}
        result = materialize_silver_drafts(groups, questions, atomic, drafts)
        self.assertEqual(result["counts"]["provisional_groups"], 1)
        self.assertEqual(result["counts"]["materialized_questions"], 2)
        self.assertEqual(result["counts"]["materialized_claims"], 2)
        item = result["items"][0]
        self.assertEqual(item["related_existing_silver_ids"], ["K1", "K2"])
        refs = {row["card_id"]: row for row in item["evidence_refs_proposed"]}
        self.assertEqual(refs["T1"]["coverage"], "partial")
        self.assertEqual(refs["T2"]["coverage"], "full")
        self.assertEqual(refs["T1"]["role"], "review_required")
        self.assertEqual(item["claims"][0]["source_card_id"], "T1")
        self.assertEqual(item["canonical_source_refs"][0]["card_id"], "T1")

    def test_materialize_silver_drafts_rejects_missing_claim_and_count_mismatch(self):
        groups = {
            "status": "reviewed_silver_draft_consolidation_registry_not_published",
            "counts": {"assigned_questions": 1},
            "groups": [{
                "group_id": "SG1",
                "canonical_question": "甲？",
                "members": ["Q1"],
                "claim_count": 1,
            }],
        }
        questions = {"clusters": [{
            "question_id": "Q1",
            "canonical_question": "甲？",
            "members": ["MISSING"],
            "entities": [],
            "kinds": [],
            "certainties": [],
        }]}
        drafts = {"items": [{"question_id": "Q1", "related_silver_ids": []}]}
        with self.assertRaises(ValueError):
            materialize_silver_drafts(groups, questions, {"items": []}, drafts)

        questions["clusters"][0]["members"] = ["C1"]
        atomic = {"items": [{
            "card": "T1",
            "claims": [{
                "id": "C1",
                "statement": "甲",
                "entity": "甲",
                "question": "甲？",
                "kind": "mechanism",
                "evidence_type": "player_report",
                "certainty": "reported",
                "source_refs": [],
            }],
        }]}
        groups["groups"][0]["claim_count"] = 2
        with self.assertRaises(ValueError):
            materialize_silver_drafts(groups, questions, atomic, drafts)


if __name__ == "__main__":
    unittest.main()
