"""Build authored Silver draft units from materialized evidence groups.

The authored specification supplies only semantic writing fields. Evidence refs,
coverage, and lineage are inherited from the reviewed materialization layer.
Output is reviewable draft data and never mutates the published Silver registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import KINDS, WORK, sha256_file


DEFAULT_MATERIALIZED = WORK / "silver-draft-materialized-work-queue-v1.json"


UNCERTAINTY_CERTAINTIES = {
    "conflicting_reports",
    "contested",
    "uncertain",
    "unverified",
    "speculative",
    "estimated",
}


def _materialized_map(doc: dict) -> dict[str, dict]:
    result = {}
    for row in doc.get("items", []):
        gid = str(row.get("group_id") or "").strip()
        if not gid:
            raise ValueError("materialized item missing group_id")
        if gid in result:
            raise ValueError(f"duplicate materialized group_id: {gid}")
        result[gid] = row
    return result


def _role_for_card(group: dict, card_id: str) -> str:
    selected = [
        claim for claim in group.get("claims", [])
        if claim.get("source_card_id") == card_id
    ]
    certainties = {str(claim.get("certainty") or "") for claim in selected}
    if certainties & UNCERTAINTY_CERTAINTIES:
        if certainties - UNCERTAINTY_CERTAINTIES:
            return "mixed_evidence_and_uncertainty"
        return "conflict_or_uncertainty"
    return "support"


def _validate_structured_shape(kind: str, structured: dict, group_id: str) -> None:
    if kind == "comparison":
        variants = structured.get("variants")
        if not isinstance(variants, list) or not variants:
            raise ValueError(f"comparison draft requires non-empty structured.variants: {group_id}")
    elif kind == "ordered_route":
        stages = structured.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError(f"ordered_route draft requires non-empty structured.stages: {group_id}")
    elif kind == "mechanism":
        renderable = ("conditions", "mechanism", "action", "outcome", "concrete_samples")
        if not any(structured.get(key) for key in renderable):
            raise ValueError(
                f"mechanism draft requires at least one renderable structured field: {group_id}"
            )


def build_drafts(materialized: dict, spec: dict) -> dict:
    groups = _materialized_map(materialized)
    rows = spec.get("items", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("Silver draft spec must contain items")

    seen_group_ids: set[str] = set()
    seen_knowledge_ids: set[str] = set()
    result = []

    for row in rows:
        gid = str(row.get("group_id") or "").strip()
        kid = str(row.get("knowledge_id") or "").strip()
        subject = str(row.get("subject") or "").strip()
        question = str(row.get("question") or "").strip()
        kind = str(row.get("kind") or "").strip()
        scope = row.get("scope")
        facts = row.get("canonical_facts")
        structured = row.get("structured")
        search_terms = row.get("search_terms")
        evidence_state = str(row.get("evidence_state") or "").strip()
        freshness = str(row.get("freshness") or "").strip()

        if gid not in groups:
            raise ValueError(f"unknown materialized group: {gid}")
        if gid in seen_group_ids:
            raise ValueError(f"duplicate authored group: {gid}")
        if not kid or kid in seen_knowledge_ids:
            raise ValueError(f"missing or duplicate knowledge_id: {kid}")
        if not subject or not question:
            raise ValueError(f"draft requires subject and question: {gid}")
        if kind not in KINDS:
            raise ValueError(f"invalid Silver kind for {gid}: {kind}")
        if not isinstance(scope, dict) or not scope:
            raise ValueError(f"draft requires non-empty scope: {gid}")
        if not evidence_state:
            raise ValueError(f"draft requires evidence_state: {gid}")
        if not freshness:
            raise ValueError(f"draft requires freshness: {gid}")
        if not isinstance(facts, list) or not facts or any(not str(x).strip() for x in facts):
            raise ValueError(f"draft requires non-empty canonical_facts: {gid}")
        if not isinstance(structured, dict) or not structured:
            raise ValueError(f"draft requires structured fields: {gid}")
        _validate_structured_shape(kind, structured, gid)
        if not isinstance(search_terms, list) or not search_terms:
            raise ValueError(f"draft requires search_terms: {gid}")

        source = groups[gid]
        evidence_refs = []
        for ref in source.get("evidence_refs_proposed", []):
            evidence_refs.append({
                "card_id": ref["card_id"],
                "role": _role_for_card(source, ref["card_id"]),
                "coverage": ref["coverage"],
            })

        unit = {
            "knowledge_id": kid,
            "subject": subject,
            "question": question,
            "kind": kind,
            "scope": scope,
            "canonical_facts": facts,
            "structured": structured,
            "search_terms": search_terms,
            "evidence_refs": evidence_refs,
            "evidence_state": evidence_state,
            "freshness": freshness,
            "topics": row.get("topics", []),
            "initial_state": row.get("initial_state", "queue"),
        }
        lineage = {
            "group_id": gid,
            "member_question_ids": source.get("member_question_ids", []),
            "claim_ids": source.get("claim_ids", []),
            "claim_count": source.get("claim_count", 0),
            "dates": source.get("dates", []),
            "related_existing_silver_ids": source.get("related_existing_silver_ids", []),
            "canonical_source_refs": source.get("canonical_source_refs", []),
            "certainties": source.get("certainties", []),
            "evidence_types": source.get("evidence_types", []),
            "consolidation_reasons": source.get("consolidation_reasons", []),
        }
        result.append({"unit": unit, "lineage": lineage})
        seen_group_ids.add(gid)
        seen_knowledge_ids.add(kid)

    return {
        "schema_version": 1,
        "status": "authored_silver_drafts_not_published",
        "contract": {
            "formal_silver_is_not_mutated": True,
            "unit_uses_formal_silver_schema": True,
            "lineage_is_review_metadata": True,
            "evidence_coverage_is_inherited_from_materialization": True,
            "evidence_roles_are_conservative": True,
        },
        "counts": {
            "draft_units": len(result),
            "evidence_links": sum(len(row["unit"]["evidence_refs"]) for row in result),
            "partial_evidence_links": sum(
                ref["coverage"] == "partial"
                for row in result
                for ref in row["unit"]["evidence_refs"]
            ),
            "uncertainty_evidence_links": sum(
                ref["role"] != "support"
                for row in result
                for ref in row["unit"]["evidence_refs"]
            ),
        },
        "items": result,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--materialized", type=Path, default=DEFAULT_MATERIALIZED)
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    result = build_drafts(
        json.loads(args.materialized.read_text(encoding="utf-8")),
        json.loads(args.spec.read_text(encoding="utf-8")),
    )
    result["inputs"] = {
        "materialized_sha256": sha256_file(args.materialized),
        "spec_sha256": sha256_file(args.spec),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
