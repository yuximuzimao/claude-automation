"""Retrieve candidate reviewed question clusters for new atomic claims.

Retrieval never mutates the registry. Assignment requires a separate semantic decision.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re
from pathlib import Path

from .atomic_claim_pair_proposals import flatten
from .quality import WORK, sha256_file


def normalize(value: str) -> str:
    return re.sub(r"[^\u3400-\u9fff0-9a-z%]+", "", str(value).lower())


def grams(value: str) -> collections.Counter[str]:
    text = normalize(value)
    result: collections.Counter[str] = collections.Counter()
    for size in (2, 3, 4):
        for i in range(max(0, len(text) - size + 1)):
            result[text[i:i + size]] += 1
    return result


def vectorize(texts: list[str]) -> list[dict[str, float]]:
    counters = [grams(text) for text in texts]
    df: collections.Counter[str] = collections.Counter()
    for counter in counters:
        df.update(counter.keys())
    total = len(counters)
    out = []
    for counter in counters:
        values = {
            key: (1 + math.log(count)) * (1 + math.log((total + 1) / (df[key] + 1)))
            for key, count in counter.items()
        }
        norm = math.sqrt(sum(value * value for value in values.values())) or 1.0
        out.append({key: value / norm for key, value in values.items()})
    return out


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def retrieve(new_claim_doc: dict, registry: dict, top_k: int = 5) -> dict:
    claims = flatten(new_claim_doc)
    clusters = registry.get("clusters", [])
    claim_texts = [
        f"{row['question']} {row['question']} {row['entity']} {row['statement']}"
        for row in claims
    ]
    cluster_texts = []
    for cluster in clusters:
        examples = " ".join(item["statement"] for item in cluster.get("inclusion_examples", []))
        cluster_texts.append(
            f"{cluster['canonical_question']} {cluster['canonical_question']} "
            f"{' '.join(cluster.get('entities', []))} {examples}"
        )
    vectors = vectorize(claim_texts + cluster_texts)
    claim_vectors = vectors[:len(claims)]
    cluster_vectors = vectors[len(claims):]

    proposals = []
    for i, claim in enumerate(claims):
        ranked = sorted(
            (
                (j, round(cosine(claim_vectors[i], cluster_vectors[j]), 6))
                for j in range(len(clusters))
            ),
            key=lambda item: (-item[1], clusters[item[0]]["question_id"]),
        )[:top_k]
        proposals.append({
            "claim_id": claim["id"],
            "source_card": claim["source_card"],
            "question": claim["question"],
            "entity": claim["entity"],
            "status": "semantic_assignment_required",
            "candidates": [
                {
                    "rank": rank,
                    "question_id": clusters[j]["question_id"],
                    "canonical_question": clusters[j]["canonical_question"],
                    "score": score,
                    "entities": clusters[j].get("entities", []),
                    "boundary_negative_count": len(clusters[j].get("boundary_negatives", [])),
                }
                for rank, (j, score) in enumerate(ranked, start=1)
            ],
        })

    return {
        "schema_version": 1,
        "status": "cluster_assignment_proposal_only",
        "warning": "similarity is retrieval only; no claim is attached without semantic review",
        "counts": {
            "new_claims": len(claims),
            "reviewed_clusters": len(clusters),
            "candidate_links": sum(len(row["candidates"]) for row in proposals),
        },
        "proposals": proposals,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=Path, required=True)
    p.add_argument("--registry", type=Path, default=WORK / "question-cluster-registry-v14.json")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--out", type=Path, default=WORK / "question-cluster-assignment-proposals-v1.json")
    args = p.parse_args()
    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    result = retrieve(claims, registry, args.top_k)
    result["inputs"] = {
        "claims_sha256": sha256_file(args.claims),
        "registry_sha256": sha256_file(args.registry),
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
