"""Atomic-claim candidate pair retrieval and gold evaluation.

Lexical similarity is recall-only. It never directly means "same canonical question".
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import re
from pathlib import Path

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


def flatten(doc: dict) -> list[dict]:
    rows = []
    for item in doc.get("items", []):
        for claim in item.get("claims", []):
            row = dict(claim)
            row["source_card"] = item["card"]
            row["source_refs"] = claim.get("source_refs") or item.get("refs", [])
            rows.append(row)
    return rows


def vectors(rows: list[dict]) -> list[dict[str, float]]:
    # canonical question gets the strongest weight; entity helps recall; statement supplies details.
    texts = [
        f"{row['question']} {row['question']} {row['entity']} {row['statement']}"
        for row in rows
    ]
    counters = [grams(text) for text in texts]
    df: collections.Counter[str] = collections.Counter()
    for counter in counters:
        df.update(counter.keys())
    total = len(counters)
    result = []
    for counter in counters:
        values = {
            key: (1 + math.log(count)) * (1 + math.log((total + 1) / (df[key] + 1)))
            for key, count in counter.items()
        }
        norm = math.sqrt(sum(value * value for value in values.values())) or 1.0
        result.append({key: value / norm for key, value in values.items()})
    return result


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(value * b.get(key, 0.0) for key, value in a.items())


def retrieve(rows: list[dict], *, top_k: int = 5) -> list[dict]:
    """Union multiple recall routes; none of them imply same-question membership."""
    vs = vectors(rows)
    scored: list[dict] = []
    by_claim: dict[str, list[dict]] = {row["id"]: [] for row in rows}
    for i, j in itertools.combinations(range(len(rows)), 2):
        score = round(cosine(vs[i], vs[j]), 6)
        left_entity = normalize(rows[i]["entity"])
        right_entity = normalize(rows[j]["entity"])
        pair = {
            "a": rows[i]["id"],
            "b": rows[j]["id"],
            "score": score,
            "same_entity": bool(left_entity) and left_entity == right_entity,
            "same_source_card": rows[i]["source_card"] == rows[j]["source_card"],
        }
        scored.append(pair)
        by_claim[rows[i]["id"]].append(pair)
        by_claim[rows[j]["id"]].append(pair)

    selected: dict[tuple[str, str], dict] = {}

    def add_route(pair: dict, route: str) -> None:
        key = tuple(sorted((pair["a"], pair["b"])))
        if key not in selected:
            selected[key] = {**pair, "routes": []}
        if route not in selected[key]["routes"]:
            selected[key]["routes"].append(route)
            selected[key]["routes"].sort()

    # Route 1: lexical nearest-neighbour recall.
    for claim_id, pairs in by_claim.items():
        ordered = sorted(
            pairs,
            key=lambda p: (-p["score"], p["a"], p["b"]),
        )[:top_k]
        for pair in ordered:
            add_route(pair, "lexical_topk")

    # Route 2: co-claims split from one source card. This recovers cases where a
    # single old card contained multiple semantically related statements whose
    # wording/entities are too different for lexical Top-K.
    for pair in scored:
        if pair["same_source_card"]:
            add_route(pair, "same_source_card")

    # Route 3: exact normalized entity identity. Same entity is recall only;
    # canonical_question still decides whether the pair may merge.
    for pair in scored:
        if pair["same_entity"]:
            add_route(pair, "same_entity")

    return sorted(selected.values(), key=lambda p: (-p["score"], p["a"], p["b"]))


def gold_pairs(gold: dict) -> set[tuple[str, str]]:
    result = set()
    for cluster in gold.get("clusters", []):
        members = cluster["members"]
        for a, b in itertools.combinations(sorted(members), 2):
            result.add((a, b))
    return result


def _metric_slice(retrieved: set[tuple[str, str]], high: set[tuple[str, str]], positive: set[tuple[str, str]]) -> dict:
    hits = retrieved & positive
    high_hits = high & positive
    high_false = high - positive
    return {
        "positive_pairs": len(positive),
        "retrieved_pairs": len(retrieved),
        "positive_recall": round(len(hits) / len(positive), 4) if positive else None,
        "high_score_pairs": len(high),
        "high_score_precision": round(len(high_hits) / len(high), 4) if high else None,
        "high_score_recall": round(len(high_hits) / len(positive), 4) if positive else None,
        "high_score_false_pairs": len(high_false),
    }


def evaluate(pairs: list[dict], gold: dict) -> dict:
    positive = gold_pairs(gold)
    retrieved = {tuple(sorted((pair["a"], pair["b"]))) for pair in pairs}
    must_separate = {
        tuple(sorted((row["a"], row["b"])))
        for row in gold.get("must_separate", [])
    }
    risky = retrieved & must_separate

    # High-score threshold was frozen on pilot. Holdout metrics must not tune it.
    high = {
        tuple(sorted((pair["a"], pair["b"])))
        for pair in pairs if pair["score"] >= 0.075
    }
    result = {
        "note": "retrieval evaluation; score is not same-question probability",
        "high_score_threshold": 0.075,
        "must_separate_retrieved": len(risky),
        "all": _metric_slice(retrieved, high, positive),
    }
    holdout = set(gold.get("holdout_claim_ids", []))
    if holdout:
        in_holdout_scope = lambda pair: pair[0] in holdout or pair[1] in holdout
        hold_positive = {pair for pair in positive if in_holdout_scope(pair)}
        hold_retrieved = {pair for pair in retrieved if in_holdout_scope(pair)}
        hold_high = {pair for pair in high if in_holdout_scope(pair)}
        result["holdout"] = _metric_slice(hold_retrieved, hold_high, hold_positive)
        result["holdout"]["claim_count"] = len(holdout)
        result["holdout"]["note"] = "at least one endpoint is a frozen holdout claim; pilot-tuned threshold unchanged"
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--claims", type=Path, default=WORK / "atomic-claims-pilot-v1.json")
    p.add_argument("--gold", type=Path, default=WORK / "atomic-claim-cluster-gold-v1.json")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--out", type=Path, default=WORK / "atomic-claim-pair-proposals-v1.json")
    args = p.parse_args()

    claims = json.loads(args.claims.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    rows = flatten(claims)
    pairs = retrieve(rows, top_k=args.top_k)
    result = {
        "schema_version": 1,
        "status": "pair_proposal_only_not_clustered",
        "algorithm": "lexical_topk_plus_same_source_plus_same_entity_v2",
        "warning": "all routes are recall only; every pair still requires semantic same-question adjudication",
        "counts": {
            "claims": len(rows),
            "candidate_pairs": len(pairs),
            "candidate_pairs_by_route": dict(sorted(collections.Counter(
                route for pair in pairs for route in pair.get("routes", [])
            ).items())),
        },
        "evaluation": evaluate(pairs, gold),
        "inputs": {
            "claims_sha256": sha256_file(args.claims),
            "gold_sha256": sha256_file(args.gold),
        },
        "pairs": pairs,
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "evaluation": result["evaluation"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
