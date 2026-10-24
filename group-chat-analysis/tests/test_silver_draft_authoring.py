from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.analysis.silver_draft_authored_registry import build_registry
from src.analysis.silver_draft_build import build_drafts
from src.analysis.silver_publication_gate_registry import build_registry as build_publication_registry
from src.analysis.silver_publication_apply import build_publication_candidate, merge_update


class SilverDraftAuthoringTests(unittest.TestCase):
    def materialized(self) -> dict:
        return {
            "status": "materialized_silver_draft_inputs_not_published",
            "items": [{
                "group_id": "G1",
                "canonical_question": "问题？",
                "member_question_ids": ["Q1"],
                "claim_ids": ["C1"],
                "claim_count": 1,
                "claims": [{
                    "id": "C1",
                    "source_card_id": "T1",
                    "certainty": "reported",
                }],
                "dates": ["2026-09-01"],
                "related_existing_silver_ids": ["K-OLD"],
                "evidence_types": ["player_report"],
                "evidence_refs_proposed": [{
                    "card_id": "T1",
                    "coverage": "full",
                    "role": "review_required",
                }],
                "canonical_source_refs": [{
                    "card_id": "T1",
                    "coverage": "full",
                    "source_refs": [{
                        "date": "2026-09-01",
                        "file": "part.md",
                        "start_line": 1,
                        "end_line": 2,
                    }],
                }],
                "consolidation_reasons": ["同题"],
            }],
        }

    def test_build_drafts_inherits_evidence_and_lineage(self):
        spec = {"items": [{
            "group_id": "G1",
            "knowledge_id": "K-NEW-001",
            "subject": "对象",
            "question": "问题？",
            "kind": "mechanism",
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["事实。"],
            "evidence_state": "test_evidence",
            "freshness": "structural",
            "structured": {
                "conditions": ["条件"],
                "mechanism": "机制",
                "action": "动作",
                "outcome": "结果",
                "failure_mode": "失败",
            },
            "search_terms": ["对象"],
        }]}
        result = build_drafts(self.materialized(), spec)
        self.assertEqual(result["counts"]["draft_units"], 1)
        row = result["items"][0]
        self.assertEqual(row["unit"]["evidence_refs"], [{
            "card_id": "T1",
            "role": "support",
            "coverage": "full",
        }])
        self.assertEqual(row["lineage"]["group_id"], "G1")
        self.assertEqual(row["lineage"]["claim_ids"], ["C1"])

    def test_build_drafts_marks_uncertainty_conservatively(self):
        materialized = self.materialized()
        materialized["items"][0]["claims"][0]["certainty"] = "uncertain"
        spec = {"items": [{
            "group_id": "G1",
            "knowledge_id": "K-NEW-001",
            "subject": "对象",
            "question": "问题？",
            "kind": "dynamic_signal",
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["当前只有未核验口径。"],
            "evidence_state": "test_uncertainty",
            "freshness": "dynamic_signal",
            "structured": {
                "dimension": "规则",
                "current_state": "未确认",
                "indicators": ["玩家说法"],
                "changed_at": "2026-09-01",
                "unresolved": ["正式规则"],
            },
            "search_terms": ["对象"],
        }]}
        result = build_drafts(materialized, spec)
        self.assertEqual(
            result["items"][0]["unit"]["evidence_refs"][0]["role"],
            "conflict_or_uncertainty",
        )

    def test_authored_registry_tracks_remaining_and_rejects_duplicate_group(self):
        materialized = self.materialized()
        materialized["items"].append({
            "group_id": "G2",
            "claim_count": 3,
            "evidence_refs_proposed": [{"card_id": "T2"}],
        })
        authored = build_drafts(self.materialized(), {"items": [{
            "group_id": "G1",
            "knowledge_id": "K-NEW-001",
            "subject": "对象",
            "question": "问题？",
            "kind": "mechanism",
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["事实。"],
            "structured": {"mechanism": "机制"},
            "search_terms": ["对象"],
            "evidence_state": "test_evidence",
            "freshness": "structural",
        }]})
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "b1.json"
            p1.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")
            registry, queue = build_registry(materialized, [("b1", p1)])
            self.assertEqual(registry["counts"]["authored_groups"], 1)
            self.assertEqual(registry["counts"]["active_work_items"], 1)
            self.assertEqual(queue["items"][0]["group_id"], "G2")

            p2 = Path(tmp) / "b2.json"
            p2.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_registry(materialized, [("b1", p1), ("b2", p2)])

    def test_authored_registry_rejects_formal_silver_id_collision(self):
        authored = build_drafts(self.materialized(), {"items": [{
            "group_id": "G1",
            "knowledge_id": "K-COLLIDE",
            "subject": "对象",
            "question": "问题？",
            "kind": "mechanism",
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["事实。"],
            "structured": {"mechanism": "机制"},
            "search_terms": ["对象"],
            "evidence_state": "test_evidence",
            "freshness": "structural",
        }]})
        formal = {"units": [{"knowledge_id": "K-COLLIDE"}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b1.json"
            path.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_registry(self.materialized(), [("b1", path)], formal)

    def test_publication_registry_tracks_decisions_and_remaining(self):
        proposals = {
            "items": [
                {"group_id": "G1", "knowledge_id": "K-NEW-1", "review_priority_score": 0.9},
                {"group_id": "G2", "knowledge_id": "K-NEW-2", "review_priority_score": 0.8},
                {"group_id": "G3", "knowledge_id": "K-NEW-3", "review_priority_score": 0.7},
            ]
        }
        authored = {
            "items": [
                {"unit": {"knowledge_id": "K-NEW-1"}, "lineage": {"group_id": "G1"}},
                {"unit": {"knowledge_id": "K-NEW-2"}, "lineage": {"group_id": "G2"}},
                {"unit": {"knowledge_id": "K-NEW-3"}, "lineage": {"group_id": "G3"}},
            ]
        }
        formal = {"units": [{"knowledge_id": "K-OLD"}]}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "b1.json"
            p.write_text(json.dumps({
                "status": "reviewed_silver_publication_gate",
                "decisions": [
                    {"group_id": "G1", "decision": "append_new", "reason": "独立新知识"},
                    {
                        "group_id": "G2",
                        "decision": "update_existing",
                        "target_knowledge_id": "K-OLD",
                        "reason": "同一既有知识的增量证据",
                    },
                ],
            }, ensure_ascii=False), encoding="utf-8")
            registry, queue = build_publication_registry(
                proposals, authored, formal, [("b1", p)]
            )
        self.assertEqual(registry["counts"]["reviewed_groups"], 2)
        self.assertEqual(registry["counts"]["append_new"], 1)
        self.assertEqual(registry["counts"]["update_existing"], 1)
        self.assertEqual(registry["counts"]["hold"], 0)
        self.assertEqual(registry["counts"]["active_work_items"], 1)
        self.assertEqual(queue["items"][0]["group_id"], "G3")

    def test_publication_registry_rejects_invalid_update_target(self):
        proposals = {"items": [{"group_id": "G1", "knowledge_id": "K-NEW-1"}]}
        authored = {"items": [{"unit": {"knowledge_id": "K-NEW-1"}, "lineage": {"group_id": "G1"}}]}
        formal = {"units": [{"knowledge_id": "K-OLD"}]}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "b1.json"
            p.write_text(json.dumps({
                "status": "reviewed_silver_publication_gate",
                "decisions": [{
                    "group_id": "G1",
                    "decision": "update_existing",
                    "target_knowledge_id": "K-MISSING",
                    "reason": "测试非法目标",
                }],
            }, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                build_publication_registry(proposals, authored, formal, [("b1", p)])

    def test_publication_apply_appends_updates_holds_and_rebuilds_candidate_index(self):
        formal = {
            "schema_version": 1,
            "source_window": "2026-09-01..2026-09-01",
            "units": [{
                "knowledge_id": "K-OLD",
                "subject": "旧对象",
                "question": "旧问题？",
                "kind": "mechanism",
                "scope": {"game_variant": "时光服"},
                "canonical_facts": ["旧事实。"],
                "structured": {"mechanism": "旧机制"},
                "search_terms": ["旧对象"],
                "evidence_refs": [{"card_id": "T1", "role": "support", "coverage": "full"}],
                "evidence_state": "old",
                "freshness": "structural",
                "topics": ["旧主题"],
                "initial_state": "queue",
            }],
        }
        authored = {
            "items": [
                {
                    "unit": {
                        "knowledge_id": "K-NEW",
                        "subject": "新对象",
                        "question": "新问题？",
                        "kind": "strategy",
                        "scope": {"game_variant": "时光服"},
                        "canonical_facts": ["新增事实。"],
                        "structured": {"action": "新增动作"},
                        "search_terms": ["新对象"],
                        "evidence_refs": [{"card_id": "T2", "role": "support", "coverage": "full"}],
                        "evidence_state": "new",
                        "freshness": "structural",
                        "topics": ["新主题"],
                        "initial_state": "queue",
                    },
                    "lineage": {"group_id": "G-APPEND"},
                },
                {
                    "unit": {
                        "knowledge_id": "K-DRAFT-UPDATE",
                        "subject": "旧对象扩展",
                        "question": "旧问题如何扩展？",
                        "kind": "mechanism",
                        "scope": {"game_variant": "时光服"},
                        "canonical_facts": ["更新事实。"],
                        "structured": {"mechanism": "新机制"},
                        "search_terms": ["更新"],
                        "evidence_refs": [
                            {"card_id": "T1", "role": "support", "coverage": "full"},
                            {"card_id": "T3", "role": "support", "coverage": "partial"},
                        ],
                        "evidence_state": "new",
                        "freshness": "structural",
                        "topics": ["更新主题"],
                        "initial_state": "queue",
                    },
                    "lineage": {"group_id": "G-UPDATE"},
                },
                {
                    "unit": {
                        "knowledge_id": "K-HOLD",
                        "subject": "不发布",
                        "question": "不发布？",
                        "kind": "sample",
                        "scope": {"game_variant": "时光服"},
                        "canonical_facts": ["不发布事实。"],
                        "structured": {"sample": "hold"},
                        "search_terms": ["hold"],
                        "evidence_refs": [{"card_id": "T4", "role": "support", "coverage": "full"}],
                        "evidence_state": "new",
                        "freshness": "structural",
                        "topics": ["hold"],
                        "initial_state": "queue",
                    },
                    "lineage": {"group_id": "G-HOLD"},
                },
            ]
        }
        gate = {
            "status": "reviewed_silver_publication_gate_not_applied",
            "counts": {
                "active_work_items": 0,
                "append_new": 1,
                "update_existing": 1,
                "hold": 1,
            },
            "items": [
                {"group_id": "G-APPEND", "decision": "append_new"},
                {
                    "group_id": "G-UPDATE",
                    "decision": "update_existing",
                    "target_knowledge_id": "K-OLD",
                },
                {"group_id": "G-HOLD", "decision": "hold"},
            ],
        }
        candidates = {
            "schema_version": 1,
            "source_queue_count": 4,
            "candidates": [
                {"card_id": "T1", "date": "2026-09-01", "dossier_refs": []},
                {"card_id": "T2", "date": "2026-09-02", "dossier_refs": []},
                {"card_id": "T3", "date": "2026-09-03", "dossier_refs": []},
                {"card_id": "T4", "date": "2026-09-04", "dossier_refs": []},
            ],
        }
        silver_out, candidates_out, report = build_publication_candidate(
            formal, authored, gate, candidates
        )
        self.assertEqual(report["counts"]["formal_units_after"], 2)
        units = {row["knowledge_id"]: row for row in silver_out["units"]}
        self.assertEqual(set(units), {"K-OLD", "K-NEW"})
        self.assertNotIn("K-DRAFT-UPDATE", units)
        self.assertNotIn("K-HOLD", units)
        self.assertIn("旧事实。", units["K-OLD"]["canonical_facts"])
        self.assertIn("更新事实。", units["K-OLD"]["canonical_facts"])
        self.assertEqual(
            {ref["card_id"] for ref in units["K-OLD"]["evidence_refs"]},
            {"T1", "T3"},
        )
        self.assertEqual(silver_out["source_window"], "2026-09-01..2026-09-03")
        card_map = {row["card_id"]: row for row in candidates_out["candidates"]}
        self.assertEqual(card_map["T1"]["silver_status"], "full")
        self.assertEqual(card_map["T2"]["silver_status"], "full")
        self.assertEqual(card_map["T3"]["silver_status"], "partial")
        self.assertEqual(card_map["T4"]["silver_status"], "unabsorbed")
        self.assertEqual(card_map["T1"]["silver_refs"][0]["knowledge_id"], "K-OLD")

    def test_merge_update_preserves_old_core_for_protected_target(self):
        old = {
            "knowledge_id": "K-ACCOUNT-CONTROL-RISK-001",
            "subject": "账号控制权",
            "question": "旧核心？",
            "kind": "comparison",
            "scope": {"game_variant": "时光服"},
            "canonical_facts": ["旧事实。"],
            "structured": {"variants": ["自己账号"]},
            "search_terms": ["账号"],
            "evidence_refs": [{"card_id": "T1", "role": "support"}],
            "topics": ["账号安全"],
            "initial_state": "queue",
        }
        new = {
            "knowledge_id": "K-DRAFT",
            "subject": "委托风险",
            "question": "新窄问题？",
            "kind": "strategy",
            "scope": {"game_variant": "时光服", "context": "阵营锁"},
            "canonical_facts": ["新事实。"],
            "structured": {"decision_rule": "不交账号"},
            "search_terms": ["代清"],
            "evidence_refs": [{"card_id": "T2", "role": "support", "coverage": "full"}],
            "topics": ["托管"],
            "initial_state": "queue",
        }
        merged = merge_update(old, new)
        self.assertEqual(merged["knowledge_id"], "K-ACCOUNT-CONTROL-RISK-001")
        self.assertEqual(merged["question"], "旧核心？")
        self.assertEqual(merged["structured"], {"variants": ["自己账号"]})
        self.assertEqual(merged["canonical_facts"], ["旧事实。", "新事实。"])
        self.assertEqual(
            {ref["card_id"] for ref in merged["evidence_refs"]},
            {"T1", "T2"},
        )
        self.assertEqual(merged["scope"]["context"], "阵营锁")

    def test_publication_apply_rejects_duplicate_update_target(self):
        formal = {"units": [{
            "knowledge_id": "K-OLD",
            "subject": "旧",
            "question": "旧？",
            "kind": "mechanism",
            "scope": {},
            "canonical_facts": ["旧"],
            "structured": {},
            "search_terms": ["旧"],
            "evidence_refs": [{"card_id": "T1"}],
        }]}
        authored = {"items": [
            {"unit": {"knowledge_id": "K-D1", "canonical_facts": [], "evidence_refs": []}, "lineage": {"group_id": "G1"}},
            {"unit": {"knowledge_id": "K-D2", "canonical_facts": [], "evidence_refs": []}, "lineage": {"group_id": "G2"}},
        ]}
        gate = {
            "status": "reviewed_silver_publication_gate_not_applied",
            "counts": {"active_work_items": 0, "append_new": 0, "update_existing": 2, "hold": 0},
            "items": [
                {"group_id": "G1", "decision": "update_existing", "target_knowledge_id": "K-OLD"},
                {"group_id": "G2", "decision": "update_existing", "target_knowledge_id": "K-OLD"},
            ],
        }
        candidates = {
            "source_queue_count": 1,
            "candidates": [{"card_id": "T1", "date": "2026-09-01", "dossier_refs": []}],
        }
        with self.assertRaises(ValueError):
            build_publication_candidate(formal, authored, gate, candidates)


if __name__ == "__main__":
    unittest.main()
