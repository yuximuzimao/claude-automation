"""Apply reviewed claim-to-question assignments without auto-creating new questions."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .atomic_claim_pair_proposals import flatten
from .quality import WORK, sha256_file


def _claim_membership(registry: dict) -> dict[str, str]:
    result = {}
    for cluster in registry.get("clusters", []):
        for claim_id in cluster.get("members", []):
            if claim_id in result and result[claim_id] != cluster["question_id"]:
                raise ValueError(f"claim in multiple registry clusters: {claim_id}")
            result[claim_id] = cluster["question_id"]
    return result


def _recount(registry: dict) -> None:
    clusters = registry.get("clusters", [])
    registry["counts"] = {
        "reviewed_claims": sum(len(c.get("members", [])) for c in clusters),
        "reviewed_question_clusters": len(clusters),
        "multi_claim_clusters": sum(len(c.get("members", [])) > 1 for c in clusters),
        "boundary_negative_links": sum(len(c.get("boundary_negatives", [])) for c in clusters),
    }


def apply_assignments(registry: dict, claim_doc: dict, decision_doc: dict) -> tuple[dict, dict, dict]:
    claims = flatten(claim_doc)
    by_id = {row["id"]: row for row in claims}
    clusters = {row["question_id"]: row for row in registry.get("clusters", [])}
    membership = _claim_membership(registry)

    decisions = decision_doc.get("decisions", {})
    if set(decisions) != set(by_id):
        missing = sorted(set(by_id) - set(decisions))
        extra = sorted(set(decisions) - set(by_id))
        raise ValueError(f"assignment decisions must cover input claims exactly; missing={missing} extra={extra}")

    new_question_ids: list[str] = []
    needs_review_ids: list[str] = []
    attached = 0
    renamed = 0

    for claim_id, decision in decisions.items():
        value = decision.get("decision")
        if value == "attach":
            qid = decision.get("question_id")
            if qid not in clusters:
                raise ValueError(f"unknown target question cluster: {qid}")
            existing = membership.get(claim_id)
            if existing and existing != qid:
                raise ValueError(f"claim already belongs to different cluster: {claim_id} -> {existing}")
            cluster = clusters[qid]
            if not existing:
                claim = by_id[claim_id]
                cluster.setdefault("members", []).append(claim_id)
                cluster["members"] = sorted(set(cluster["members"]))
                cluster["source_cards"] = sorted(set(cluster.get("source_cards", [])) | {claim["source_card"]})
                cluster["entities"] = sorted(set(cluster.get("entities", [])) | {claim["entity"]})
                cluster["kinds"] = sorted(set(cluster.get("kinds", [])) | {claim["kind"]})
                cluster["certainties"] = sorted(set(cluster.get("certainties", [])) | {claim["certainty"]})
                examples = cluster.setdefault("inclusion_examples", [])
                if claim_id not in {x.get("claim_id") for x in examples}:
                    examples.append({"claim_id": claim_id, "statement": claim["statement"]})
                    cluster["inclusion_examples"] = examples[:6]
                attached += 1
            override = str(decision.get("canonical_question_override") or "").strip()
            if override and override != cluster.get("canonical_question"):
                cluster.setdefault("question_revision_history", []).append({
                    "from": cluster.get("canonical_question", ""),
                    "to": override,
                    "reason": decision.get("reason", ""),
                    "decision_source": decision_doc.get("status", ""),
                })
                cluster["canonical_question"] = override
                renamed += 1
        elif value == "new_question":
            if claim_id in membership:
                raise ValueError(f"reviewed registry claim cannot be routed to new_question: {claim_id}")
            new_question_ids.append(claim_id)
        elif value == "needs_review":
            needs_review_ids.append(claim_id)
        else:
            raise ValueError(f"invalid assignment decision for {claim_id}: {value}")

    output = json.loads(json.dumps(registry, ensure_ascii=False))
    output["clusters"] = sorted(clusters.values(), key=lambda row: row["question_id"])
    output["status"] = "reviewed_question_cluster_registry_not_silver"
    _recount(output)

    grouped: dict[str, list[dict]] = collections.defaultdict(list)
    for cid in new_question_ids:
        grouped[by_id[cid]["source_card"]].append(by_id[cid])
    bootstrap_items = []
    for card_id in sorted(grouped):
        group = grouped[card_id]
        refs = []
        seen_refs = set()
        for claim in group:
            for ref in claim.get("source_refs", []):
                key = json.dumps(ref, ensure_ascii=False, sort_keys=True)
                if key not in seen_refs:
                    seen_refs.add(key)
                    refs.append(ref)
        bootstrap_items.append({
            "card": card_id,
            "claims": [
                {k: v for k, v in claim.items() if k not in {"source_card"}}
                for claim in group
            ],
            "refs": refs,
            "rejected": [],
        })

    bootstrap = {
        "schema_version": 1,
        "status": "new_question_bootstrap_reviewed_claims",
        "source_cards_rebuilt": len(bootstrap_items),
        "atomic_claim_count": sum(len(item["claims"]) for item in bootstrap_items),
        "items": bootstrap_items,
    }
    report = {
        "attached": attached,
        "canonical_questions_revised": renamed,
        "new_question_claims": len(new_question_ids),
        "needs_review_claims": len(needs_review_ids),
        "needs_review_ids": sorted(needs_review_ids),
    }
    return output, bootstrap, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, default=WORK / "question-cluster-registry-v2.json")
    p.add_argument("--claims", type=Path, required=True)
    p.add_argument("--decisions", type=Path, required=True)
    p.add_argument("--out", type=Path, default=WORK / "question-cluster-registry-next.json")
    p.add_argument("--bootstrap-out", type=Path, default=WORK / "new-question-bootstrap-next.json")
    args = p.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    updated, bootstrap, report = apply_assignments(registry, claims, decisions)
    updated["inputs"] = {
        **updated.get("inputs", {}),
        "previous_registry_sha256": sha256_file(args.registry),
        "assignment_claims_sha256": sha256_file(args.claims),
        "assignment_decisions_sha256": sha256_file(args.decisions),
    }
    args.out.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.bootstrap_out.write_text(json.dumps(bootstrap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "registry_counts": updated["counts"], "bootstrap_claims": bootstrap["atomic_claim_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
