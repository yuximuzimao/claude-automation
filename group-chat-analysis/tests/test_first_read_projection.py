from __future__ import annotations

import copy
import unittest

from src.analysis.first_read_projection import build_first_read_projection
from src.analysis.semantic_fingerprint import semantic_fingerprint


class FirstReadProjectionTests(unittest.TestCase):
    def base(self) -> dict:
        return {
            "candidates": {
                "candidates": [
                    {"card_id": "T-FULL", "normalized_status": "full", "silver_status": "full"},
                    {"card_id": "T-REUSE", "normalized_status": "unabsorbed", "silver_status": "unabsorbed"},
                    {"card_id": "T-APPEND", "normalized_status": "partial", "silver_status": "partial"},
                    {"card_id": "T-NO", "normalized_status": "unabsorbed", "silver_status": "unabsorbed"},
                ]
            },
            "atomic": {
                "items": [
                    {"card": "T-REUSE", "claims": [{"id": "C-REUSE"}]},
                    {"card": "T-APPEND", "claims": [{"id": "C-APPEND"}]},
                ]
            },
            "no_claim": {
                "cards": [
                    {"card_id": "T-NO", "reason": "重复或没有稳定结论"}
                ]
            },
            "questions": {
                "clusters": [
                    {"question_id": "Q-REUSE", "members": ["C-REUSE"]},
                    {"question_id": "Q-APPEND", "members": ["C-APPEND"]},
                ]
            },
            "routing": {
                "items": [
                    {
                        "question_id": "Q-REUSE",
                        "decision": "reuse_existing",
                        "targets": [{"knowledge_id": "K-OLD"}],
                    },
                    {
                        "question_id": "Q-APPEND",
                        "decision": "new_draft",
                        "targets": [],
                    },
                ]
            },
            "consolidation": {
                "groups": [
                    {"group_id": "G-APPEND", "members": ["Q-APPEND"]}
                ],
                "exclusions": [],
            },
            "publication": {
                "items": [
                    {
                        "group_id": "G-APPEND",
                        "draft_knowledge_id": "K-NEW",
                        "decision": "append_new",
                        "target_knowledge_id": None,
                    }
                ]
            },
            "silver": {
                "units": [
                    {"knowledge_id": "K-OLD", "initial_state": "knowledge"},
                    {"knowledge_id": "K-NEW", "initial_state": "queue"},
                ]
            },
        }

    def build(self, data: dict, reviewed_state: dict | None = None) -> dict:
        return build_first_read_projection(
            data["candidates"],
            data["atomic"],
            data["no_claim"],
            data["questions"],
            data["routing"],
            data["consolidation"],
            data["publication"],
            data["silver"],
            reviewed_state,
        )

    def test_resolved_lineage_removes_partial_and_unabsorbed_raw_cards(self):
        result = self.build(self.base())
        self.assertEqual(result["counts"]["candidate_cards"], 4)
        self.assertEqual(result["counts"]["normalized_component_full"], 1)
        self.assertEqual(result["counts"]["reviewed_claim_lineage_resolved"], 2)
        self.assertEqual(result["counts"]["reviewed_no_claim"], 1)
        self.assertEqual(result["counts"]["raw_card_queue"], 0)
        self.assertEqual(result["counts"]["first_read_silver_units"], 1)
        self.assertEqual(result["counts"]["knowledge_silver_units"], 1)
        self.assertEqual(result["queue"]["silver_knowledge_ids"], ["K-NEW"])
        self.assertEqual(result["queue"]["residual_card_ids"], [])
        self.assertEqual(result["endpoint_counts"]["reuse_existing"], 1)
        self.assertEqual(result["endpoint_counts"]["published_append_new"], 1)
        self.assertEqual(result["endpoint_counts"]["reviewed_no_claim"], 1)

    def test_consolidation_exclusion_is_reviewed_terminal(self):
        data = self.base()
        data["candidates"]["candidates"] = [
            {"card_id": "T-X", "normalized_status": "unabsorbed", "silver_status": "unabsorbed"}
        ]
        data["atomic"]["items"] = [{"card": "T-X", "claims": [{"id": "C-X"}]}]
        data["no_claim"]["cards"] = []
        data["questions"]["clusters"] = [{"question_id": "Q-X", "members": ["C-X"]}]
        data["routing"]["items"] = [{"question_id": "Q-X", "decision": "new_draft", "targets": []}]
        data["consolidation"] = {
            "groups": [],
            "exclusions": [{"question_id": "Q-X", "reason": "只有单次主观样本"}],
        }
        data["publication"]["items"] = []
        data["silver"]["units"] = []
        result = self.build(data)
        self.assertEqual(result["counts"]["raw_card_queue"], 0)
        self.assertEqual(result["endpoint_counts"]["consolidation_excluded"], 1)

    def test_publication_hold_is_reviewed_terminal(self):
        data = self.base()
        data["publication"]["items"][0]["decision"] = "hold"
        data["publication"]["items"][0]["reason"] = "由更完整上位单元覆盖"
        data["silver"]["units"] = [{"knowledge_id": "K-OLD", "initial_state": "knowledge"}]
        result = self.build(data)
        self.assertEqual(result["counts"]["raw_card_queue"], 0)
        self.assertEqual(result["endpoint_counts"]["published_hold"], 1)

    def test_missing_question_assignment_fails_closed(self):
        data = self.base()
        data["questions"]["clusters"] = [
            {"question_id": "Q-APPEND", "members": ["C-APPEND"]}
        ]
        data["routing"]["items"] = [
            {
                "question_id": "Q-APPEND",
                "decision": "new_draft",
                "targets": [],
            }
        ]
        with self.assertRaisesRegex(ValueError, "missing question assignment"):
            self.build(data)

    def test_new_draft_without_consolidation_fails_closed(self):
        data = self.base()
        data["consolidation"] = {"groups": [], "exclusions": []}
        data["publication"] = {"items": []}
        with self.assertRaisesRegex(ValueError, "missing consolidation decision"):
            self.build(data)

    def test_unreviewed_nonfull_candidate_fails_closed(self):
        data = self.base()
        data["candidates"]["candidates"].append({
            "card_id": "T-DANGLING",
            "normalized_status": "unabsorbed",
            "silver_status": "unabsorbed",
        })
        with self.assertRaisesRegex(ValueError, "unresolved raw candidate cards"):
            self.build(data)

    def test_duplicate_claim_membership_fails(self):
        data = self.base()
        data["questions"]["clusters"].append(
            {"question_id": "Q-DUP", "members": ["C-REUSE"]}
        )
        data["routing"]["items"].append(
            {
                "question_id": "Q-DUP",
                "decision": "reuse_existing",
                "targets": [{"knowledge_id": "K-OLD"}],
            }
        )
        with self.assertRaisesRegex(ValueError, "multiple reviewed questions"):
            self.build(data)

    def test_reviewed_state_exact_knowledge_id_closes_queue_unit(self):
        data = self.base()
        reviewed_state = {
            "states": [{
                "decision": "discard",
                "semantic_fingerprint": "sf1:not-needed-for-id-match",
                "aliases": {"knowledge_ids": ["K-NEW"]},
            }]
        }
        result = self.build(data, reviewed_state)
        self.assertEqual(result["counts"]["first_read_silver_units"], 0)
        self.assertEqual(result["counts"]["reviewed_queue_silver_units"], 1)
        self.assertEqual(result["counts"]["reviewed_discard_silver_units"], 1)
        self.assertEqual(result["counts"]["knowledge_silver_units"], 1)
        self.assertEqual(result["queue"]["reviewed_silver_knowledge_ids"], ["K-NEW"])
        self.assertEqual(result["queue"]["reviewed_discard_silver_ids"], ["K-NEW"])

    def test_reviewed_knowledge_moves_queue_unit_into_knowledge_view(self):
        data = self.base()
        reviewed_state = {
            "states": [{
                "decision": "knowledge",
                "semantic_fingerprint": "sf1:not-needed-for-id-match",
                "aliases": {"knowledge_ids": ["K-NEW"]},
            }]
        }
        result = self.build(data, reviewed_state)
        self.assertEqual(result["counts"]["first_read_silver_units"], 0)
        self.assertEqual(result["counts"]["reviewed_knowledge_silver_units"], 1)
        self.assertEqual(result["counts"]["initial_knowledge_silver_units"], 1)
        self.assertEqual(result["counts"]["knowledge_silver_units"], 2)
        self.assertEqual(
            result["knowledge"]["silver_knowledge_ids"],
            ["K-NEW", "K-OLD"],
        )
        self.assertEqual(
            result["queue"]["reviewed_knowledge_silver_ids"],
            ["K-NEW"],
        )

    def test_dossier_absorbed_queue_unit_leaves_first_read(self):
        data = self.base()
        dossier = {
            "silver_routing": {
                "absorbed_knowledge_ids": ["K-NEW"],
                "visible_update_knowledge_ids": [],
            }
        }
        result = build_first_read_projection(
            data["candidates"],
            data["atomic"],
            data["no_claim"],
            data["questions"],
            data["routing"],
            data["consolidation"],
            data["publication"],
            data["silver"],
            None,
            dossier,
        )
        self.assertEqual(result["counts"]["first_read_silver_units"], 0)
        self.assertEqual(result["counts"]["dossier_absorbed_silver_units"], 1)
        self.assertEqual(
            result["queue"]["dossier_absorbed_silver_knowledge_ids"],
            ["K-NEW"],
        )

    def test_reviewed_state_exact_fingerprint_closes_renamed_queue_unit(self):
        data = self.base()
        unit = {
            "knowledge_id": "K-NEW",
            "initial_state": "queue",
            "subject": "冰DK命中阈值",
            "question": "双持冰DK要多少命中？",
            "kind": "mechanism",
            "scope": {"game_variant": "时光服", "class_spec": "冰DK"},
        }
        data["silver"]["units"][1] = unit
        reviewed_state = {
            "states": [{
                "decision": "discard",
                "semantic_fingerprint": semantic_fingerprint(unit),
                "aliases": {"knowledge_ids": []},
            }]
        }
        result = self.build(data, reviewed_state)
        self.assertEqual(result["counts"]["first_read_silver_units"], 0)
        self.assertEqual(result["counts"]["reviewed_queue_silver_units"], 1)

    def test_unsupported_silver_state_fails(self):
        data = self.base()
        data["silver"]["units"].append(
            {"knowledge_id": "K-BAD", "initial_state": "hidden"}
        )
        with self.assertRaisesRegex(ValueError, "unsupported initial_state"):
            self.build(data)


if __name__ == "__main__":
    unittest.main()
