"""Append manually reviewed bootstrap question clusters to the registry."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .atomic_claim_pair_proposals import flatten
from .quality import WORK, sha256_file
from .question_cluster_assignment_apply import _claim_membership, _recount


def apply_bootstrap(registry: dict, claim_doc: dict, gold: dict) -> tuple[dict, dict]:
    claims = flatten(claim_doc)
    by_id = {row["id"]: row for row in claims}
    expected = set(by_id)
    membership = _claim_membership(registry)
    existing_qids = {row["question_id"] for row in registry.get("clusters", [])}

    seen: set[str] = set()
    for cluster in gold.get("clusters", []):
        qid = cluster.get("cluster_id")
        if not qid or qid in existing_qids:
            raise ValueError(f"duplicate or missing bootstrap question id: {qid}")
        members = cluster.get("members", [])
        if not members:
            raise ValueError(f"bootstrap cluster has no members: {qid}")
        for cid in members:
            if cid not in by_id:
                raise ValueError(f"bootstrap member missing from claims: {cid}")
            if cid in seen:
                raise ValueError(f"bootstrap claim appears in multiple clusters: {cid}")
            if cid in membership:
                raise ValueError(f"bootstrap claim already belongs to registry: {cid}")
            seen.add(cid)

    if seen != expected:
        raise ValueError(f"bootstrap gold must cover claims exactly; missing={sorted(expected-seen)} extra={sorted(seen-expected)}")

    negative_pairs: dict[tuple[str, str], str] = {}
    for row in gold.get("must_separate", []):
        a, b = row.get("a"), row.get("b")
        if a not in expected or b not in expected or a == b:
            raise ValueError(f"invalid bootstrap must_separate pair: {a}, {b}")
        negative_pairs[tuple(sorted((a, b)))] = row.get("reason", "")

    new_clusters = []
    for cluster in gold["clusters"]:
        members = sorted(cluster["members"])
        member_rows = [by_id[cid] for cid in members]
        member_set = set(members)
        boundary = []
        for (a, b), reason in negative_pairs.items():
            if (a in member_set) ^ (b in member_set):
                inside = a if a in member_set else b
                outside = b if a in member_set else a
                boundary.append({"inside_claim": inside, "outside_claim": outside, "reason": reason})
        new_clusters.append({
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
                for row in member_rows[:6]
            ],
            "boundary_negatives": sorted(boundary, key=lambda x: (x["outside_claim"], x["inside_claim"])),
        })

    output = json.loads(json.dumps(registry, ensure_ascii=False))
    output["clusters"] = sorted(output.get("clusters", []) + new_clusters, key=lambda row: row["question_id"])
    _recount(output)
    output["status"] = "reviewed_question_cluster_registry_not_silver"
    report = {
        "new_claims": len(expected),
        "new_question_clusters": len(new_clusters),
        "new_multi_claim_clusters": sum(len(row["members"]) > 1 for row in new_clusters),
        "new_boundary_negative_links": sum(len(row["boundary_negatives"]) for row in new_clusters),
    }
    return output, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--claims", type=Path, required=True)
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    updated, report = apply_bootstrap(registry, claims, gold)
    updated["inputs"] = {
        **updated.get("inputs", {}),
        "previous_registry_sha256": sha256_file(args.registry),
        "bootstrap_claims_sha256": sha256_file(args.claims),
        "bootstrap_gold_sha256": sha256_file(args.gold),
    }
    args.out.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "registry_counts": updated["counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
