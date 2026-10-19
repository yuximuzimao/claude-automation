"""Apply reviewed atomic-claim pair decisions into complete-link question clusters.

A multi-claim cluster is publishable as a proposal only when every internal pair has an
explicit same_question review. Transitive similarity alone is never sufficient.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path

from .atomic_claim_pair_proposals import flatten, gold_pairs
from .quality import WORK, sha256_file


def pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def build_clusters(claim_doc: dict, decision_doc: dict) -> dict:
    rows = flatten(claim_doc)
    by_id = {row["id"]: row for row in rows}
    decision_map: dict[tuple[str, str], dict] = {}
    issues: list[dict] = []

    for row in decision_doc.get("decisions", []):
        a, b = row.get("a"), row.get("b")
        if a not in by_id or b not in by_id or a == b:
            issues.append({"severity": "error", "code": "invalid_pair_decision", "pair": [a, b]})
            continue
        key = pair_key(a, b)
        if key in decision_map:
            issues.append({"severity": "error", "code": "duplicate_pair_decision", "pair": list(key)})
            continue
        if row.get("decision") not in {"same_question", "different_question"}:
            issues.append({"severity": "error", "code": "invalid_decision_value", "pair": list(key)})
            continue
        decision_map[key] = row

    parent = {cid: cid for cid in by_id}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (a, b), row in decision_map.items():
        if row["decision"] == "same_question":
            union(a, b)

    components: dict[str, list[str]] = collections.defaultdict(list)
    for cid in by_id:
        components[find(cid)].append(cid)

    clusters = []
    blocked = 0
    for members in components.values():
        members = sorted(members)
        missing = []
        conflicts = []
        questions = set()
        if len(members) > 1:
            for a, b in itertools.combinations(members, 2):
                decision = decision_map.get(pair_key(a, b))
                if not decision:
                    missing.append([a, b])
                elif decision["decision"] != "same_question":
                    conflicts.append([a, b])
                elif decision.get("canonical_question"):
                    questions.add(decision["canonical_question"].strip())
        status = "reviewed_complete"
        if missing or conflicts or len(questions) > 1:
            status = "review_required"
            blocked += 1
        canonical_question = (
            next(iter(questions))
            if len(questions) == 1
            else by_id[members[0]]["question"] if len(members) == 1
            else ""
        )
        clusters.append({
            "cluster_id": "Q-" + members[0],
            "status": status,
            "canonical_question": canonical_question,
            "members": members,
            "source_cards": sorted({by_id[cid]["source_card"] for cid in members}),
            "missing_pair_reviews": missing,
            "conflicting_pair_reviews": conflicts,
        })

    clusters.sort(key=lambda c: (-len(c["members"]), c["cluster_id"]))
    return {
        "schema_version": 1,
        "status": "question_cluster_proposal_not_silver",
        "counts": {
            "claims": len(rows),
            "clusters": len(clusters),
            "multi_claim_clusters": sum(len(c["members"]) > 1 for c in clusters),
            "reviewed_complete_clusters": sum(c["status"] == "reviewed_complete" for c in clusters),
            "blocked_clusters": blocked,
        },
        "quality": {
            "errors": sum(i["severity"] == "error" for i in issues),
            "issues": issues,
        },
        "clusters": clusters,
    }


def _pair_metrics(predicted: set[tuple[str, str]], expected: set[tuple[str, str]]) -> dict:
    tp = predicted & expected
    fp = predicted - expected
    fn = expected - predicted
    precision = len(tp) / len(predicted) if predicted else None
    recall = len(tp) / len(expected) if expected else None
    return {
        "expected_positive_pairs": len(expected),
        "predicted_positive_pairs": len(predicted),
        "pairwise_precision": round(precision, 4) if precision is not None else None,
        "pairwise_recall": round(recall, 4) if recall is not None else None,
        "false_positive_pairs": [list(x) for x in sorted(fp)],
        "missed_positive_pairs": [list(x) for x in sorted(fn)],
    }


def evaluate(result: dict, gold: dict) -> dict:
    predicted = set()
    for cluster in result["clusters"]:
        if cluster["status"] != "reviewed_complete":
            continue
        for a, b in itertools.combinations(cluster["members"], 2):
            predicted.add(pair_key(a, b))
    expected = gold_pairs(gold)
    output = {
        "note": "reviewed-cluster pair metrics; only reviewed_complete clusters count as predictions",
        "all": _pair_metrics(predicted, expected),
    }
    holdout = set(gold.get("holdout_claim_ids", []))
    if holdout:
        in_holdout_scope = lambda pair: pair[0] in holdout or pair[1] in holdout
        hold_predicted = {pair for pair in predicted if in_holdout_scope(pair)}
        hold_expected = {pair for pair in expected if in_holdout_scope(pair)}
        output["holdout"] = _pair_metrics(hold_predicted, hold_expected)
        output["holdout"]["claim_count"] = len(holdout)
    return output


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=Path, default=WORK / "atomic-claims-pilot-v1.json")
    p.add_argument("--decisions", type=Path, default=WORK / "atomic-claim-pair-decisions-pilot-v1.json")
    p.add_argument("--gold", type=Path, default=WORK / "atomic-claim-cluster-gold-v1.json")
    p.add_argument("--out", type=Path, default=WORK / "atomic-claim-question-clusters-pilot-v1.json")
    args = p.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    result = build_clusters(claims, decisions)
    if args.gold.exists():
        gold = json.loads(args.gold.read_text(encoding="utf-8"))
        result["evaluation"] = evaluate(result, gold)
    result["inputs"] = {
        "claims_sha256": sha256_file(args.claims),
        "decisions_sha256": sha256_file(args.decisions),
        "gold_sha256": sha256_file(args.gold) if args.gold.exists() else None,
    }
    result["publication_ready"] = not result["quality"]["errors"] and not result["counts"]["blocked_clusters"]
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "quality": result["quality"], "publication_ready": result["publication_ready"], "evaluation": result.get("evaluation")}, ensure_ascii=False))
    return 1 if result["quality"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
