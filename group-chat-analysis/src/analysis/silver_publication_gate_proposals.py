"""Build proposal-only publication-gate candidates for authored Silver drafts.

The gate never publishes. It ranks authored drafts against existing formal Silver
and against other authored drafts so human review can decide append/update/hold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .question_cluster_assignment import cosine, vectorize

DEFAULT_AUTHORED = WORK / "silver-draft-authored-registry-v1.json"
DEFAULT_FORMAL = WORK / "silver-knowledge-v1.json"


def _text(unit: dict) -> str:
    return " ".join([
        str(unit.get("subject") or ""),
        str(unit.get("question") or ""),
        str(unit.get("question") or ""),
        " ".join(map(str, unit.get("topics", []))),
        " ".join(map(str, unit.get("canonical_facts", []))),
        " ".join(map(str, unit.get("search_terms", []))),
    ])


def build_proposals(authored: dict, formal: dict, *, top_k: int = 5) -> dict:
    authored_rows = authored.get("items", [])
    formal_rows = formal.get("units", [])
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    authored_units = [row.get("unit") or {} for row in authored_rows]
    if any(not unit.get("knowledge_id") for unit in authored_units):
        raise ValueError("authored draft missing knowledge_id")
    if any(not unit.get("knowledge_id") for unit in formal_rows):
        raise ValueError("formal Silver missing knowledge_id")

    all_texts = [_text(unit) for unit in authored_units] + [_text(unit) for unit in formal_rows]
    vectors = vectorize(all_texts) if all_texts else []
    authored_vecs = vectors[:len(authored_units)]
    formal_vecs = vectors[len(authored_units):]

    authored_by_id = {
        str(unit["knowledge_id"]): unit
        for unit in authored_units
    }
    formal_by_id = {
        str(unit["knowledge_id"]): unit
        for unit in formal_rows
    }
    if len(authored_by_id) != len(authored_units):
        raise ValueError("duplicate authored knowledge_id")
    if len(formal_by_id) != len(formal_rows):
        raise ValueError("duplicate formal knowledge_id")

    authored_ids = list(authored_by_id)
    formal_ids = list(formal_by_id)
    authored_index = {kid: i for i, kid in enumerate(authored_ids)}
    formal_index = {kid: i for i, kid in enumerate(formal_ids)}

    rows = []
    pair_seen: set[tuple[str, str]] = set()
    authored_pair_rows = []

    for source_row in authored_rows:
        unit = source_row["unit"]
        kid = str(unit["knowledge_id"])
        ai = authored_index[kid]
        lineage = source_row.get("lineage") or {}
        related = sorted(set(map(str, lineage.get("related_existing_silver_ids", []))))

        formal_candidates = []
        for formal_id in formal_ids:
            fi = formal_index[formal_id]
            score = cosine(authored_vecs[ai], formal_vecs[fi])
            formal_unit = formal_by_id[formal_id]
            formal_candidates.append({
                "knowledge_id": formal_id,
                "score": round(score, 6),
                "subject": formal_unit.get("subject"),
                "question": formal_unit.get("question"),
                "kind": formal_unit.get("kind"),
                "was_related_context": formal_id in related,
            })
        formal_candidates.sort(key=lambda row: (-row["score"], row["knowledge_id"]))

        authored_candidates = []
        for other_id in authored_ids:
            if other_id == kid:
                continue
            oi = authored_index[other_id]
            score = cosine(authored_vecs[ai], authored_vecs[oi])
            other_unit = authored_by_id[other_id]
            authored_candidates.append({
                "knowledge_id": other_id,
                "score": round(score, 6),
                "subject": other_unit.get("subject"),
                "question": other_unit.get("question"),
                "kind": other_unit.get("kind"),
            })
        authored_candidates.sort(key=lambda row: (-row["score"], row["knowledge_id"]))

        for candidate in authored_candidates[:top_k]:
            key = tuple(sorted((kid, candidate["knowledge_id"])))
            if key in pair_seen:
                continue
            pair_seen.add(key)
            a_id, b_id = key
            a_unit = authored_by_id[a_id]
            b_unit = authored_by_id[b_id]
            authored_pair_rows.append({
                "a": a_id,
                "b": b_id,
                "score": candidate["score"],
                "a_question": a_unit.get("question"),
                "b_question": b_unit.get("question"),
                "a_kind": a_unit.get("kind"),
                "b_kind": b_unit.get("kind"),
            })

        top_formal = formal_candidates[0] if formal_candidates else None
        top_authored = authored_candidates[0] if authored_candidates else None
        risk_score = max(
            float(top_formal["score"]) if top_formal else 0.0,
            float(top_authored["score"]) if top_authored else 0.0,
        )
        rows.append({
            "group_id": lineage.get("group_id"),
            "knowledge_id": kid,
            "subject": unit.get("subject"),
            "question": unit.get("question"),
            "kind": unit.get("kind"),
            "evidence_state": unit.get("evidence_state"),
            "freshness": unit.get("freshness"),
            "related_existing_silver_ids": related,
            "formal_candidates": formal_candidates[:top_k],
            "authored_candidates": authored_candidates[:top_k],
            "top_formal_score": top_formal["score"] if top_formal else 0.0,
            "top_authored_score": top_authored["score"] if top_authored else 0.0,
            "review_priority_score": round(risk_score, 6),
            "status": "publication_review_required",
        })

    rows.sort(key=lambda row: (
        -float(row["review_priority_score"]),
        -float(row["top_formal_score"]),
        -float(row["top_authored_score"]),
        row["knowledge_id"],
    ))
    authored_pair_rows.sort(key=lambda row: (-row["score"], row["a"], row["b"]))

    return {
        "schema_version": 1,
        "status": "silver_publication_gate_proposals_not_applied",
        "contract": {
            "proposal_only": True,
            "no_auto_publish": True,
            "similarity_is_not_merge": True,
            "prior_human_routing_and_consolidation_remain_authoritative_context": True,
        },
        "counts": {
            "authored_drafts": len(authored_units),
            "formal_silver_units": len(formal_rows),
            "drafts_requiring_publication_review": len(rows),
            "authored_pair_candidates": len(authored_pair_rows),
        },
        "items": rows,
        "authored_pair_candidates": authored_pair_rows,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED)
    p.add_argument("--formal", type=Path, default=DEFAULT_FORMAL)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-publication-gate-proposals-v1.json",
    )
    args = p.parse_args()

    authored = json.loads(args.authored.read_text(encoding="utf-8"))
    formal = json.loads(args.formal.read_text(encoding="utf-8"))
    result = build_proposals(authored, formal, top_k=args.top_k)
    result["inputs"] = {
        "authored_sha256": sha256_file(args.authored),
        "formal_sha256": sha256_file(args.formal),
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
