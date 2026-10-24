"""Materialize provisional Silver groups into evidence-complete draft inputs.

This module joins reviewed consolidation groups to Question Clusters and reviewed
Atomic Claims. It does not generate or publish Silver prose. Its job is to make
all evidence, lineage, source coverage, uncertainty, and existing-Silver context
explicit before manual Silver drafting.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from .quality import WORK, sha256_file


DEFAULT_GROUPS = WORK / "silver-draft-consolidation-reviewed-v1.json"
DEFAULT_QUESTIONS = WORK / "question-cluster-registry-current.json"
DEFAULT_ATOMIC = WORK / "atomic-claims-reviewed-v1.json"
DEFAULT_DRAFT_QUEUE = WORK / "silver-draft-work-queue-v1.json"
DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"


def _question_map(doc: dict) -> dict[str, dict]:
    rows = doc.get("clusters", [])
    result: dict[str, dict] = {}
    for row in rows:
        qid = str(row.get("question_id") or "").strip()
        if not qid:
            raise ValueError("question cluster missing question_id")
        if qid in result:
            raise ValueError(f"duplicate question cluster: {qid}")
        result[qid] = row
    return result


def _atomic_maps(doc: dict) -> tuple[dict[str, dict], dict[str, dict], dict[str, list[str]]]:
    claims: dict[str, dict] = {}
    cards: dict[str, dict] = {}
    card_claim_ids: dict[str, list[str]] = {}
    for item in doc.get("items", []):
        card_id = str(item.get("card") or "").strip()
        if not card_id:
            raise ValueError("atomic registry item missing card")
        if card_id in cards:
            raise ValueError(f"duplicate atomic source card: {card_id}")
        cards[card_id] = item
        ids = []
        for claim in item.get("claims", []):
            cid = str(claim.get("id") or "").strip()
            if not cid:
                raise ValueError(f"atomic claim missing id in {card_id}")
            if cid in claims:
                raise ValueError(f"duplicate atomic claim id: {cid}")
            copied = json.loads(json.dumps(claim, ensure_ascii=False))
            copied["source_card_id"] = card_id
            copied["review_origin"] = item.get("review_origin")
            copied["review_source_file"] = item.get("review_source_file")
            claims[cid] = copied
            ids.append(cid)
        card_claim_ids[card_id] = ids
    return claims, cards, card_claim_ids


def _draft_map(doc: dict) -> dict[str, dict]:
    result = {}
    for row in doc.get("items", []):
        qid = str(row.get("question_id") or "").strip()
        if not qid:
            raise ValueError("draft queue item missing question_id")
        if qid in result:
            raise ValueError(f"duplicate draft queue question: {qid}")
        result[qid] = row
    return result


def _source_ref_key(ref: dict) -> tuple:
    return (
        ref.get("date"),
        ref.get("file"),
        ref.get("start_line"),
        ref.get("end_line"),
    )


def materialize(
    groups_doc: dict,
    questions_doc: dict,
    atomic_doc: dict,
    draft_doc: dict,
    silver_doc: dict | None = None,
) -> dict:
    if groups_doc.get("status") != "reviewed_silver_draft_consolidation_registry_not_published":
        raise ValueError(f"unexpected consolidation status: {groups_doc.get('status')}")

    questions = _question_map(questions_doc)
    claims, _cards, card_claim_ids = _atomic_maps(atomic_doc)
    drafts = _draft_map(draft_doc)
    silver_map = {}
    if silver_doc is not None:
        for unit in silver_doc.get("units", []):
            kid = str(unit.get("knowledge_id") or "").strip()
            if not kid:
                raise ValueError("existing Silver unit missing knowledge_id")
            if kid in silver_map:
                raise ValueError(f"duplicate existing Silver id: {kid}")
            silver_map[kid] = unit

    group_rows = []
    seen_questions: set[str] = set()
    seen_group_claims: set[str] = set()

    for group in groups_doc.get("groups", []):
        gid = str(group.get("group_id") or "").strip()
        members = [str(x) for x in group.get("members", [])]
        if not gid or not members:
            raise ValueError(f"invalid provisional group: {gid}")
        if len(members) != len(set(members)):
            raise ValueError(f"duplicate question inside provisional group: {gid}")

        unknown_questions = sorted(set(members) - set(questions))
        if unknown_questions:
            raise ValueError(f"unknown question ids in {gid}: {unknown_questions}")
        unknown_drafts = sorted(set(members) - set(drafts))
        if unknown_drafts:
            raise ValueError(f"group members missing routed draft metadata in {gid}: {unknown_drafts}")

        duplicate_questions = sorted(set(members) & seen_questions)
        if duplicate_questions:
            raise ValueError(f"question assigned to multiple provisional groups: {duplicate_questions}")
        seen_questions.update(members)

        selected_claim_ids = []
        for qid in members:
            selected_claim_ids.extend(map(str, questions[qid].get("members", [])))
        if len(selected_claim_ids) != len(set(selected_claim_ids)):
            dup = [cid for cid, n in collections.Counter(selected_claim_ids).items() if n > 1]
            raise ValueError(f"claim duplicated across group member questions in {gid}: {sorted(dup)}")

        unknown_claims = sorted(set(selected_claim_ids) - set(claims))
        if unknown_claims:
            raise ValueError(f"unknown atomic claims in {gid}: {unknown_claims}")

        overlapping_claims = sorted(set(selected_claim_ids) & seen_group_claims)
        if overlapping_claims:
            raise ValueError(f"atomic claim assigned to multiple provisional groups: {overlapping_claims}")
        seen_group_claims.update(selected_claim_ids)

        selected_set = set(selected_claim_ids)
        claim_rows = [claims[cid] for cid in selected_claim_ids]

        grouped_by_card: dict[str, list[str]] = collections.defaultdict(list)
        for claim in claim_rows:
            grouped_by_card[claim["source_card_id"]].append(claim["id"])

        evidence_refs = []
        source_ref_rows = []
        for card_id in sorted(grouped_by_card):
            group_card_claims = sorted(grouped_by_card[card_id])
            all_card_claims = sorted(card_claim_ids.get(card_id, []))
            if not all_card_claims:
                raise ValueError(f"source card has no reviewed claims: {card_id}")
            coverage = "full" if set(all_card_claims).issubset(selected_set) else "partial"
            evidence_refs.append({
                "card_id": card_id,
                "coverage": coverage,
                "role": "review_required",
                "claim_ids": group_card_claims,
                "card_reviewed_claim_count": len(all_card_claims),
                "selected_claim_count": len(group_card_claims),
            })
            seen_source_refs: set[tuple] = set()
            refs = []
            for cid in group_card_claims:
                for ref in claims[cid].get("source_refs", []):
                    key = _source_ref_key(ref)
                    if key in seen_source_refs:
                        continue
                    seen_source_refs.add(key)
                    refs.append(ref)
            source_ref_rows.append({
                "card_id": card_id,
                "coverage": coverage,
                "source_refs": refs,
            })

        entities = sorted({
            str(claim.get("entity"))
            for claim in claim_rows
            if claim.get("entity")
        })
        kinds = sorted({
            str(claim.get("kind"))
            for claim in claim_rows
            if claim.get("kind")
        })
        certainties = sorted({
            str(claim.get("certainty"))
            for claim in claim_rows
            if claim.get("certainty")
        })
        evidence_types = sorted({
            str(claim.get("evidence_type"))
            for claim in claim_rows
            if claim.get("evidence_type")
        })
        dates = sorted({
            str(ref.get("date"))
            for claim in claim_rows
            for ref in claim.get("source_refs", [])
            if ref.get("date")
        })
        related_silver = sorted({
            str(kid)
            for qid in members
            for kid in drafts[qid].get("related_silver_ids", [])
            if kid
        })
        related_silver_context = []
        if silver_doc is not None:
            unknown_related = sorted(set(related_silver) - set(silver_map))
            if unknown_related:
                raise ValueError(f"unknown related Silver ids in {gid}: {unknown_related}")
            related_silver_context = [{
                "knowledge_id": kid,
                "subject": silver_map[kid].get("subject"),
                "question": silver_map[kid].get("question"),
                "kind": silver_map[kid].get("kind"),
                "scope": silver_map[kid].get("scope"),
                "canonical_facts": silver_map[kid].get("canonical_facts", []),
                "freshness": silver_map[kid].get("freshness"),
                "initial_state": silver_map[kid].get("initial_state"),
            } for kid in related_silver]

        declared_claim_count = int(group.get("claim_count") or 0)
        if declared_claim_count != len(selected_claim_ids):
            raise ValueError(
                f"claim_count mismatch for {gid}: consolidation={declared_claim_count} "
                f"materialized={len(selected_claim_ids)}"
            )

        group_rows.append({
            "group_id": gid,
            "status": "materialized_silver_draft_input_not_published",
            "canonical_question": group.get("canonical_question"),
            "member_question_ids": members,
            "member_questions": [{
                "question_id": qid,
                "canonical_question": questions[qid].get("canonical_question"),
                "entities": questions[qid].get("entities", []),
                "kinds": questions[qid].get("kinds", []),
                "certainties": questions[qid].get("certainties", []),
                "boundary_negatives": questions[qid].get("boundary_negatives", []),
                "question_revision_history": questions[qid].get("question_revision_history", []),
            } for qid in members],
            "claim_count": len(selected_claim_ids),
            "claim_ids": selected_claim_ids,
            "claims": claim_rows,
            "entities": entities,
            "claim_kinds": kinds,
            "certainties": certainties,
            "evidence_types": evidence_types,
            "dates": dates,
            "date_window": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
            "related_existing_silver_ids": related_silver,
            "related_existing_silver": related_silver_context,
            "evidence_refs_proposed": evidence_refs,
            "canonical_source_refs": source_ref_rows,
            "consolidation_reasons": group.get("reasons", []),
            "review_origins": group.get("review_origins", []),
        })

    expected_assigned = int(groups_doc.get("counts", {}).get("assigned_questions") or 0)
    if len(seen_questions) != expected_assigned:
        raise ValueError(
            f"assigned question coverage mismatch: consolidation={expected_assigned} "
            f"materialized={len(seen_questions)}"
        )

    return {
        "schema_version": 1,
        "status": "materialized_silver_draft_inputs_not_published",
        "contract": {
            "provisional_groups_are_not_silver": True,
            "formal_silver_is_not_mutated": True,
            "canonical_source_refs_are_preserved": True,
            "evidence_roles_require_manual_review": True,
            "coverage_is_computed_against_reviewed_claims_per_source_card": True,
        },
        "counts": {
            "provisional_groups": len(group_rows),
            "materialized_questions": len(seen_questions),
            "materialized_claims": len(seen_group_claims),
            "evidence_card_links": sum(len(row["evidence_refs_proposed"]) for row in group_rows),
            "full_coverage_links": sum(
                ref["coverage"] == "full"
                for row in group_rows
                for ref in row["evidence_refs_proposed"]
            ),
            "partial_coverage_links": sum(
                ref["coverage"] == "partial"
                for row in group_rows
                for ref in row["evidence_refs_proposed"]
            ),
            "groups_with_existing_silver_context": sum(
                bool(row["related_existing_silver_ids"]) for row in group_rows
            ),
        },
        "items": group_rows,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--groups", type=Path, default=DEFAULT_GROUPS)
    p.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    p.add_argument("--atomic", type=Path, default=DEFAULT_ATOMIC)
    p.add_argument("--draft-queue", type=Path, default=DEFAULT_DRAFT_QUEUE)
    p.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-draft-materialized-work-queue-v1.json",
    )
    args = p.parse_args()

    result = materialize(
        json.loads(args.groups.read_text(encoding="utf-8")),
        json.loads(args.questions.read_text(encoding="utf-8")),
        json.loads(args.atomic.read_text(encoding="utf-8")),
        json.loads(args.draft_queue.read_text(encoding="utf-8")),
        json.loads(args.silver.read_text(encoding="utf-8")),
    )
    result["inputs"] = {
        "groups_sha256": sha256_file(args.groups),
        "questions_sha256": sha256_file(args.questions),
        "atomic_sha256": sha256_file(args.atomic),
        "draft_queue_sha256": sha256_file(args.draft_queue),
        "silver_sha256": sha256_file(args.silver),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
