"""Apply reviewed Question Cluster -> Silver routing decisions.

This does not mutate Silver. It records reviewed mappings and emits a queue for
questions that require new/rebuilt Silver drafts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file


_ALLOWED_RELATIONS = {"same_question", "supporting_evidence", "existing_split"}


def _proposal_map(proposal_doc: dict) -> dict[str, dict]:
    rows = proposal_doc.get("proposals", [])
    result = {}
    for row in rows:
        qid = row.get("question_id")
        if not qid:
            raise ValueError("proposal row missing question_id")
        if qid in result:
            raise ValueError(f"duplicate question proposal: {qid}")
        result[qid] = row
    return result


def _silver_ids(silver: dict) -> set[str]:
    ids = [str(row.get("knowledge_id", "")) for row in silver.get("units", [])]
    if any(not value for value in ids):
        raise ValueError("Silver unit missing knowledge_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Silver knowledge_id")
    return set(ids)


def apply_routing(proposal_doc: dict, silver: dict, decision_doc: dict) -> tuple[dict, dict, dict]:
    proposals = _proposal_map(proposal_doc)
    known_silver = _silver_ids(silver)
    decisions = decision_doc.get("decisions", {})

    scope = decision_doc.get("scope_question_ids")
    if scope is not None:
        if not isinstance(scope, list) or not scope:
            raise ValueError("scope_question_ids must be a non-empty list when provided")
        requested = set(map(str, scope))
        unknown_scope = sorted(requested - set(proposals))
        if unknown_scope:
            raise ValueError(f"unknown questions in routing scope: {unknown_scope}")
        proposals = {qid: proposals[qid] for qid in requested}

    if set(decisions) != set(proposals):
        missing = sorted(set(proposals) - set(decisions))
        extra = sorted(set(decisions) - set(proposals))
        raise ValueError(
            f"routing decisions must cover scoped proposal questions exactly; missing={missing} extra={extra}"
        )

    reviewed_rows = []
    draft_items = []
    counts = {
        "reused_questions": 0,
        "new_draft_questions": 0,
        "needs_review_questions": 0,
        "existing_silver_links": 0,
    }

    for qid in sorted(proposals):
        proposal = proposals[qid]
        decision = decisions[qid]
        value = decision.get("decision")
        reason = str(decision.get("reason", "")).strip()
        if not reason:
            raise ValueError(f"routing decision missing reason: {qid}")

        row = {
            "question_id": qid,
            "canonical_question": proposal.get("canonical_question"),
            "decision": value,
            "reason": reason,
        }

        if value == "reuse_existing":
            targets = decision.get("targets", [])
            if not isinstance(targets, list) or not targets:
                raise ValueError(f"reuse_existing requires non-empty targets: {qid}")
            seen = set()
            normalized_targets = []
            for target in targets:
                kid = str(target.get("knowledge_id", "")).strip()
                relation = str(target.get("relation", "")).strip()
                if kid not in known_silver:
                    raise ValueError(f"unknown Silver target for {qid}: {kid}")
                if relation not in _ALLOWED_RELATIONS:
                    raise ValueError(f"invalid Silver relation for {qid}: {relation}")
                if kid in seen:
                    raise ValueError(f"duplicate Silver target for {qid}: {kid}")
                seen.add(kid)
                normalized_targets.append({
                    "knowledge_id": kid,
                    "relation": relation,
                })
            row["targets"] = normalized_targets
            counts["reused_questions"] += 1
            counts["existing_silver_links"] += len(normalized_targets)

        elif value == "new_draft":
            related = [str(x) for x in decision.get("related_silver_ids", [])]
            unknown = sorted(set(related) - known_silver)
            if unknown:
                raise ValueError(f"unknown related Silver ids for {qid}: {unknown}")
            row["related_silver_ids"] = sorted(set(related))
            draft_items.append({
                "question_id": qid,
                "canonical_question": proposal.get("canonical_question"),
                "entities": proposal.get("entities", []),
                "source_cards": proposal.get("source_cards", []),
                "claim_count": proposal.get("claim_count", 0),
                "related_silver_ids": sorted(set(related)),
                "reason": reason,
            })
            counts["new_draft_questions"] += 1

        elif value == "needs_review":
            counts["needs_review_questions"] += 1

        else:
            raise ValueError(f"invalid routing decision for {qid}: {value}")

        reviewed_rows.append(row)

    routing = {
        "schema_version": 1,
        "status": "reviewed_question_to_silver_routing_not_applied_to_silver",
        "warning": "reviewed mappings do not mutate or overwrite Silver knowledge units",
        "counts": counts,
        "items": reviewed_rows,
    }
    draft_queue = {
        "schema_version": 1,
        "status": "silver_draft_work_queue_not_published",
        "count": len(draft_items),
        "items": draft_items,
    }
    return routing, draft_queue, counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--proposals", type=Path, required=True)
    p.add_argument("--silver", type=Path, default=WORK / "silver-knowledge-v1.json")
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--out", type=Path, default=WORK / "question-cluster-silver-routing-reviewed-v1.json")
    p.add_argument("--draft-out", type=Path, default=WORK / "silver-draft-work-queue-v1.json")
    args = p.parse_args()

    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    silver = json.loads(args.silver.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    routing, draft_queue, counts = apply_routing(proposals, silver, decisions)
    routing["inputs"] = {
        "proposals_sha256": sha256_file(args.proposals),
        "silver_sha256": sha256_file(args.silver),
        "decisions_sha256": sha256_file(args.decisions),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(routing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.draft_out.write_text(
        json.dumps(draft_queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
