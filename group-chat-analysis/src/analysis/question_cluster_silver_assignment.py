"""Retrieve existing Silver candidates for reviewed question clusters.

This module is proposal-only. A shared source card or a high lexical score is a
retrieval signal, never proof that a reviewed question belongs to an existing
Silver knowledge unit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .question_cluster_assignment import cosine, vectorize


def _question_text(cluster: dict) -> str:
    examples = " ".join(
        str(item.get("statement", ""))
        for item in cluster.get("inclusion_examples", [])
    )
    return " ".join([
        str(cluster.get("canonical_question", "")),
        str(cluster.get("canonical_question", "")),
        " ".join(map(str, cluster.get("entities", []))),
        examples,
    ])


def _silver_text(unit: dict) -> str:
    return " ".join([
        str(unit.get("question", "")),
        str(unit.get("question", "")),
        str(unit.get("subject", "")),
        " ".join(map(str, unit.get("canonical_facts", []))),
        " ".join(map(str, unit.get("search_terms", []))),
    ])


def _source_overlap(cluster: dict, unit: dict) -> tuple[list[str], dict[str, int]]:
    source_cards = set(map(str, cluster.get("source_cards", [])))
    coverage = {"full": 0, "partial": 0, "legacy_missing": 0}
    overlap: set[str] = set()
    for ref in unit.get("evidence_refs", []):
        if not isinstance(ref, dict):
            continue
        card_id = ref.get("card_id")
        if not card_id or str(card_id) not in source_cards:
            continue
        card_id = str(card_id)
        overlap.add(card_id)
        value = ref.get("coverage")
        if value == "full":
            coverage["full"] += 1
        elif value == "partial":
            coverage["partial"] += 1
        else:
            coverage["legacy_missing"] += 1
    return sorted(overlap), coverage


def retrieve(question_registry: dict, silver: dict, top_k: int = 5) -> dict:
    clusters = question_registry.get("clusters", [])
    units = silver.get("units", [])
    if top_k < 0:
        raise ValueError("top_k must be >= 0")

    question_texts = [_question_text(cluster) for cluster in clusters]
    silver_texts = [_silver_text(unit) for unit in units]
    vectors = vectorize(question_texts + silver_texts) if question_texts or silver_texts else []
    q_vectors = vectors[:len(clusters)]
    s_vectors = vectors[len(clusters):]

    proposals = []
    overlap_links = 0
    lexical_links = 0

    for i, cluster in enumerate(clusters):
        lexical_ranked = sorted(
            (
                (j, round(cosine(q_vectors[i], s_vectors[j]), 6))
                for j in range(len(units))
            ),
            key=lambda item: (-item[1], str(units[item[0]].get("knowledge_id", ""))),
        )[:top_k]
        lexical_ids = {j for j, _ in lexical_ranked}
        scores = {j: score for j, score in lexical_ranked}

        overlap_by_index: dict[int, tuple[list[str], dict[str, int]]] = {}
        for j, unit in enumerate(units):
            overlap, coverage = _source_overlap(cluster, unit)
            if overlap:
                overlap_by_index[j] = (overlap, coverage)

        candidate_indices = lexical_ids | set(overlap_by_index)
        candidates = []
        for j in candidate_indices:
            overlap, coverage = overlap_by_index.get(
                j, ([], {"full": 0, "partial": 0, "legacy_missing": 0})
            )
            routes = []
            if j in lexical_ids:
                routes.append("lexical_topk")
                lexical_links += 1
            if overlap:
                routes.append("source_card_overlap")
                overlap_links += 1
            score = scores.get(j)
            if score is None:
                score = round(cosine(q_vectors[i], s_vectors[j]), 6)

            unit = units[j]
            candidates.append({
                "knowledge_id": unit.get("knowledge_id"),
                "question": unit.get("question"),
                "subject": unit.get("subject"),
                "kind": unit.get("kind"),
                "initial_state": unit.get("initial_state"),
                "score": score,
                "routes": routes,
                "overlapping_source_cards": overlap,
                "overlap_coverage": coverage,
            })

        candidates.sort(
            key=lambda row: (
                0 if "source_card_overlap" in row["routes"] else 1,
                -len(row["overlapping_source_cards"]),
                -row["score"],
                str(row.get("knowledge_id", "")),
            )
        )
        for rank, row in enumerate(candidates, start=1):
            row["rank"] = rank

        proposals.append({
            "question_id": cluster.get("question_id"),
            "canonical_question": cluster.get("canonical_question"),
            "entities": cluster.get("entities", []),
            "source_cards": cluster.get("source_cards", []),
            "claim_count": len(cluster.get("members", [])),
            "status": "semantic_assignment_required",
            "candidates": candidates,
        })

    return {
        "schema_version": 1,
        "status": "question_to_silver_assignment_proposal_only",
        "warning": (
            "lexical similarity and shared source cards are retrieval signals only; "
            "no reviewed question is attached to Silver without semantic review"
        ),
        "counts": {
            "reviewed_questions": len(clusters),
            "existing_silver_units": len(units),
            "questions_with_candidates": sum(bool(row["candidates"]) for row in proposals),
            "candidate_links": sum(len(row["candidates"]) for row in proposals),
            "lexical_candidate_links": lexical_links,
            "source_overlap_candidate_links": overlap_links,
            "questions_with_source_overlap": sum(
                any("source_card_overlap" in c["routes"] for c in row["candidates"])
                for row in proposals
            ),
        },
        "proposals": proposals,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--registry",
        type=Path,
        default=WORK / "question-cluster-registry-current.json",
    )
    p.add_argument(
        "--silver",
        type=Path,
        default=WORK / "silver-knowledge-v1.json",
    )
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "question-cluster-silver-assignment-proposals-v1.json",
    )
    args = p.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    silver = json.loads(args.silver.read_text(encoding="utf-8"))
    result = retrieve(registry, silver, args.top_k)
    result["inputs"] = {
        "question_registry_sha256": sha256_file(args.registry),
        "silver_sha256": sha256_file(args.silver),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
