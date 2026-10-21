"""Build the full atomic-claim extraction work queue.

This is routing metadata only. Topic Card text is a retrieval hint, not source truth.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file


def classify(
    row: dict,
    correction_ids: set[str],
    reviewed_ids: set[str] | None = None,
    no_claim_reviewed_ids: set[str] | None = None,
) -> str:
    cid = row["card_id"]
    reviewed_ids = reviewed_ids or set()
    no_claim_reviewed_ids = no_claim_reviewed_ids or set()
    normalized_status = row.get("normalized_status", row.get("silver_status"))
    if normalized_status == "full":
        return "already_full_silver" if row.get("silver_status") == "full" else "already_normalized"
    if cid in reviewed_ids:
        return "atomic_claim_reviewed"
    if cid in no_claim_reviewed_ids:
        return "atomic_claim_no_claim_reviewed"
    if cid in correction_ids:
        return "semantic_rebuild_required"
    confidence = row.get("source_anchor_confidence", "none")
    if confidence == "high":
        return "ready_from_high_anchor"
    if confidence == "medium":
        return "needs_anchor_review"
    return "needs_direct_source_retrieval"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", type=Path, default=WORK / "silver-candidates-v1.json")
    p.add_argument("--corrections", type=Path, default=WORK / "semantic-correction-queue-v1.json")
    p.add_argument("--reviewed", type=Path, default=WORK / "atomic-claims-reviewed-v1.json")
    p.add_argument("--no-claim-reviewed", type=Path, default=WORK / "atomic-claim-no-claim-reviewed-v1.json")
    p.add_argument("--out", type=Path, default=WORK / "atomic-claim-work-queue-v1.json")
    args = p.parse_args()

    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    corrections = json.loads(args.corrections.read_text(encoding="utf-8")) if args.corrections.exists() else {"issues": []}
    correction_ids = {x["card_id"] for x in corrections.get("issues", []) if x.get("card_id")}
    reviewed_doc = json.loads(args.reviewed.read_text(encoding="utf-8")) if args.reviewed.exists() else {"items": []}
    reviewed_ids = {x["card"] for x in reviewed_doc.get("items", []) if x.get("card")}
    no_claim_doc = (
        json.loads(args.no_claim_reviewed.read_text(encoding="utf-8"))
        if args.no_claim_reviewed.exists()
        else {"cards": []}
    )
    no_claim_reviewed_ids = {
        x["card_id"] for x in no_claim_doc.get("cards", []) if isinstance(x, dict) and x.get("card_id")
    }

    rows = []
    counts: dict[str, int] = {}
    for row in candidates["candidates"]:
        lane = classify(row, correction_ids, reviewed_ids, no_claim_reviewed_ids)
        counts[lane] = counts.get(lane, 0) + 1
        if lane in {
            "already_full_silver",
            "already_normalized",
            "atomic_claim_reviewed",
            "atomic_claim_no_claim_reviewed",
        }:
            continue
        rows.append({
            "card_id": row["card_id"],
            "date": row.get("date"),
            "title_hint": row.get("title", ""),
            "semantic_summary_hint": row.get("semantic_summary", ""),
            "topics": row.get("topics", []),
            "silver_status": row.get("silver_status"),
            "normalized_status": row.get("normalized_status", row.get("silver_status")),
            "source_anchor_confidence": row.get("source_anchor_confidence", "none"),
            "source_anchor_reason": row.get("source_anchor_reason", ""),
            "lane": lane,
            "contract": {
                "topic_card_is_hint_only": True,
                "must_read_canonical_source": True,
                "may_split_into_multiple_atomic_claims": True,
                "must_preserve_uncertainty": True,
                "must_separate_observation_from_inference": True,
            },
        })

    lane_order = {
        "semantic_rebuild_required": 0,
        "ready_from_high_anchor": 1,
        "needs_anchor_review": 2,
        "needs_direct_source_retrieval": 3,
    }
    rows.sort(key=lambda x: (lane_order[x["lane"]], x["date"] or "", x["card_id"]))

    result = {
        "schema_version": 1,
        "status": "work_queue_not_published",
        "source_of_truth": "canonical_messages_and_verified_source_anchors",
        "warning": "Topic Card title/summary are retrieval hints only and must never be copied into atomic claims without canonical source verification.",
        "counts": {
            "candidate_total": len(candidates["candidates"]),
            **dict(sorted(counts.items())),
            "active_work_items": len(rows),
        },
        "inputs": {
            "candidates_sha256": sha256_file(args.candidates),
            "semantic_corrections_sha256": sha256_file(args.corrections) if args.corrections.exists() else None,
            "reviewed_atomic_claims_sha256": sha256_file(args.reviewed) if args.reviewed.exists() else None,
            "no_claim_reviewed_sha256": sha256_file(args.no_claim_reviewed) if args.no_claim_reviewed.exists() else None,
        },
        "items": rows,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
