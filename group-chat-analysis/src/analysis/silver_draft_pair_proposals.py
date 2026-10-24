"""Retrieve candidate relationships among routed Silver draft questions.

All routes are recall-only. Candidate pairs still require semantic decisions before
any merge, hierarchy, exclusion, or publication action.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .question_cluster_assignment import cosine, normalize, vectorize


def _text(row: dict) -> str:
    return " ".join([
        str(row.get("canonical_question", "")),
        str(row.get("canonical_question", "")),
        " ".join(map(str, row.get("entities", []))),
        str(row.get("reason", "")),
    ])


def _normalized_set(values: list[str]) -> set[str]:
    return {value for value in (normalize(v) for v in values) if value}


def retrieve(doc: dict, *, top_k: int = 8, context_top_k: int = 4) -> dict:
    rows = doc.get("items", [])
    if top_k < 0 or context_top_k < 0:
        raise ValueError("top_k and context_top_k must be >= 0")
    ids = [str(row.get("question_id") or "") for row in rows]
    if any(not value for value in ids):
        raise ValueError("draft queue item missing question_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate draft question_id")

    vectors = vectorize([_text(row) for row in rows]) if rows else []
    scored = []
    by_id: dict[str, list[dict]] = {qid: [] for qid in ids}

    entity_sets = [_normalized_set(row.get("entities", [])) for row in rows]
    source_sets = [set(map(str, row.get("source_cards", []))) for row in rows]
    context_sets = [set(map(str, row.get("related_silver_ids", []))) for row in rows]

    for i, j in itertools.combinations(range(len(rows)), 2):
        pair = {
            "a": ids[i],
            "b": ids[j],
            "score": round(cosine(vectors[i], vectors[j]), 6),
            "shared_entities": sorted(entity_sets[i] & entity_sets[j]),
            "shared_source_cards": sorted(source_sets[i] & source_sets[j]),
            "shared_related_silver_ids": sorted(context_sets[i] & context_sets[j]),
        }
        scored.append(pair)
        by_id[ids[i]].append(pair)
        by_id[ids[j]].append(pair)

    selected: dict[tuple[str, str], dict] = {}

    def add(pair: dict, route: str) -> None:
        key = tuple(sorted((pair["a"], pair["b"])))
        if key not in selected:
            selected[key] = {**pair, "routes": []}
        if route not in selected[key]["routes"]:
            selected[key]["routes"].append(route)
            selected[key]["routes"].sort()

    for qid, pairs in by_id.items():
        for pair in sorted(
            pairs, key=lambda p: (-p["score"], p["a"], p["b"])
        )[:top_k]:
            add(pair, "lexical_topk")

    for pair in scored:
        if pair["shared_source_cards"]:
            add(pair, "same_source_card")
        if pair["shared_entities"]:
            add(pair, "same_entity")

    # Human-reviewed adjacency to the same existing Silver is a useful thematic
    # retrieval signal, but can be very broad. Keep only the nearest few pairs
    # per draft within that context instead of creating a full clique.
    for qid, pairs in by_id.items():
        contextual = [pair for pair in pairs if pair["shared_related_silver_ids"]]
        for pair in sorted(
            contextual, key=lambda p: (-p["score"], p["a"], p["b"])
        )[:context_top_k]:
            add(pair, "shared_silver_context_topk")

    question_map = {
        str(row["question_id"]): row.get("canonical_question")
        for row in rows
    }
    pairs = sorted(
        selected.values(),
        key=lambda p: (
            -len(p["routes"]),
            -p["score"],
            p["a"],
            p["b"],
        ),
    )
    for pair in pairs:
        pair["a_question"] = question_map[pair["a"]]
        pair["b_question"] = question_map[pair["b"]]

    return {
        "schema_version": 1,
        "status": "silver_draft_pair_proposal_only",
        "algorithm": "lexical_topk_plus_same_source_plus_same_entity_plus_shared_silver_context_topk_v1",
        "warning": (
            "all routes are recall-only; candidate pairs require semantic review and "
            "must not be auto-merged"
        ),
        "counts": {
            "draft_questions": len(rows),
            "candidate_pairs": len(pairs),
            "candidate_pairs_by_route": dict(sorted(collections.Counter(
                route for pair in pairs for route in pair.get("routes", [])
            ).items())),
        },
        "pairs": pairs,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--drafts",
        type=Path,
        default=WORK / "silver-draft-work-queue-v1.json",
    )
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--context-top-k", type=int, default=4)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-draft-pair-proposals-v1.json",
    )
    args = p.parse_args()

    doc = json.loads(args.drafts.read_text(encoding="utf-8"))
    result = retrieve(doc, top_k=args.top_k, context_top_k=args.context_top_k)
    result["inputs"] = {
        "drafts_sha256": sha256_file(args.drafts),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
