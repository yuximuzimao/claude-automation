"""Build a reviewed Question Cluster Registry from complete atomic-claim clusters."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .atomic_claim_pair_proposals import flatten
from .quality import WORK, sha256_file


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def build_registry(claim_doc: dict, cluster_doc: dict, decision_doc: dict) -> dict:
    if not cluster_doc.get("publication_ready"):
        raise ValueError("question clusters are not review-complete; refuse registry build")

    claims = flatten(claim_doc)
    by_id = {claim["id"]: claim for claim in claims}
    seen: set[str] = set()
    decision_map = {
        pair_key(row["a"], row["b"]): row
        for row in decision_doc.get("decisions", [])
    }

    clusters = []
    for cluster in cluster_doc.get("clusters", []):
        if cluster.get("status") != "reviewed_complete":
            raise ValueError(f"non-complete cluster in registry input: {cluster.get('cluster_id')}")
        members = cluster["members"]
        for cid in members:
            if cid not in by_id:
                raise ValueError(f"cluster member missing from claims: {cid}")
            if cid in seen:
                raise ValueError(f"claim appears in multiple clusters: {cid}")
            seen.add(cid)

        boundary = []
        member_set = set(members)
        for key, row in decision_map.items():
            if row.get("decision") != "different_question":
                continue
            a, b = key
            if (a in member_set) ^ (b in member_set):
                outside = b if a in member_set else a
                inside = a if a in member_set else b
                boundary.append({
                    "inside_claim": inside,
                    "outside_claim": outside,
                    "reason": row.get("reason", ""),
                })

        member_rows = [by_id[cid] for cid in members]
        clusters.append({
            "question_id": cluster["cluster_id"],
            "canonical_question": cluster["canonical_question"],
            "status": "reviewed",
            "members": members,
            "source_cards": sorted({row["source_card"] for row in member_rows}),
            "entities": sorted({row["entity"] for row in member_rows}),
            "kinds": sorted({row["kind"] for row in member_rows}),
            "certainties": sorted({row["certainty"] for row in member_rows}),
            "inclusion_examples": [
                {"claim_id": row["id"], "statement": row["statement"]}
                for row in member_rows[:4]
            ],
            "boundary_negatives": sorted(
                boundary,
                key=lambda x: (x["outside_claim"], x["inside_claim"]),
            ),
        })

    missing = sorted(set(by_id) - seen)
    if missing:
        raise ValueError(f"reviewed claims missing from question registry: {missing}")

    clusters.sort(key=lambda row: row["question_id"])
    return {
        "schema_version": 1,
        "status": "reviewed_question_cluster_registry_not_silver",
        "contract": {
            "assignment_unit": "atomic_claim",
            "canonical_question_is_merge_boundary": True,
            "new_claim_must_be_semantically_reviewed_against_cluster": True,
            "similarity_score_is_retrieval_only": True,
            "boundary_negatives_are_hard_examples": True,
        },
        "counts": {
            "reviewed_claims": len(claims),
            "reviewed_question_clusters": len(clusters),
            "multi_claim_clusters": sum(len(row["members"]) > 1 for row in clusters),
            "boundary_negative_links": sum(len(row["boundary_negatives"]) for row in clusters),
        },
        "clusters": clusters,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=Path, default=WORK / "atomic-claims-combined-holdout-v1.json")
    p.add_argument("--clusters", type=Path, default=WORK / "atomic-claim-question-clusters-holdout-complete-v1.json")
    p.add_argument("--decisions", type=Path, default=WORK / "atomic-claim-pair-decisions-combined-complete-v1.json")
    p.add_argument("--out", type=Path, default=WORK / "question-cluster-registry-v1.json")
    args = p.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    clusters = json.loads(args.clusters.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    result = build_registry(claims, clusters, decisions)
    result["inputs"] = {
        "claims_sha256": sha256_file(args.claims),
        "clusters_sha256": sha256_file(args.clusters),
        "decisions_sha256": sha256_file(args.decisions),
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
