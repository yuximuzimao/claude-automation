"""Aggregate reviewed Question Cluster -> Silver routing and emit remaining queue."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_MANIFEST = WORK / "question-cluster-silver-routing-reviewed-manifest-v1.json"
DEFAULT_PROPOSALS = WORK / "question-cluster-silver-assignment-proposals-v1.json"


def inputs_from_manifest(path: Path) -> list[tuple[str, Path]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("datasets", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("routing manifest must contain datasets")
    result: list[tuple[str, Path]] = []
    seen_roles: set[str] = set()
    seen_files: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip()
        filename = str(row.get("file") or "").strip()
        if not role or not filename:
            raise ValueError("routing manifest rows require role and file")
        if role in seen_roles or filename in seen_files:
            raise ValueError(f"duplicate routing manifest entry: {role} / {filename}")
        seen_roles.add(role)
        seen_files.add(filename)
        path_obj = WORK / filename
        if not path_obj.exists():
            raise ValueError(f"routing dataset missing: {path_obj}")
        result.append((role, path_obj))
    return result


def build_registry(inputs: list[tuple[str, Path]]) -> dict:
    reviewed: dict[str, dict] = {}
    datasets = []
    counts = {
        "reviewed_questions": 0,
        "reused_questions": 0,
        "new_draft_questions": 0,
        "needs_review_questions": 0,
        "existing_silver_links": 0,
        "input_datasets": 0,
    }

    for role, path in inputs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("status") != "reviewed_question_to_silver_routing_not_applied_to_silver":
            raise ValueError(f"unexpected routing dataset status: {path}: {doc.get('status')}")
        items = doc.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"routing dataset items must be a list: {path}")
        datasets.append({
            "role": role,
            "file": path.name,
            "sha256": sha256_file(path),
            "questions": len(items),
        })
        for item in items:
            qid = str(item.get("question_id") or "").strip()
            if not qid:
                raise ValueError(f"routing item missing question_id: {path}")
            if qid in reviewed:
                raise ValueError(f"duplicate reviewed routing question: {qid}")
            copied = json.loads(json.dumps(item, ensure_ascii=False))
            copied["review_origin"] = role
            copied["review_source_file"] = path.name
            reviewed[qid] = copied

            decision = item.get("decision")
            if decision == "reuse_existing":
                counts["reused_questions"] += 1
                counts["existing_silver_links"] += len(item.get("targets", []))
            elif decision == "new_draft":
                counts["new_draft_questions"] += 1
            elif decision == "needs_review":
                counts["needs_review_questions"] += 1
            else:
                raise ValueError(f"invalid routing decision in reviewed dataset: {qid}: {decision}")

    counts["reviewed_questions"] = len(reviewed)
    counts["input_datasets"] = len(datasets)
    return {
        "schema_version": 1,
        "status": "reviewed_question_to_silver_routing_registry_not_applied_to_silver",
        "contract": {
            "silver_is_not_mutated": True,
            "retrieval_is_not_merge": True,
            "one_question_may_map_to_multiple_existing_silver_units": True,
        },
        "counts": counts,
        "datasets": datasets,
        "items": [reviewed[qid] for qid in sorted(reviewed)],
    }


def build_draft_queue(proposals: dict, registry: dict) -> dict:
    proposal_map = {
        str(row.get("question_id") or ""): row
        for row in proposals.get("proposals", [])
        if row.get("question_id")
    }
    rows = []
    for reviewed in registry.get("items", []):
        if reviewed.get("decision") != "new_draft":
            continue
        qid = str(reviewed["question_id"])
        proposal = proposal_map.get(qid)
        if proposal is None:
            raise ValueError(f"reviewed draft missing proposal metadata: {qid}")
        rows.append({
            "question_id": qid,
            "canonical_question": reviewed.get("canonical_question"),
            "entities": proposal.get("entities", []),
            "source_cards": proposal.get("source_cards", []),
            "claim_count": proposal.get("claim_count", 0),
            "related_silver_ids": reviewed.get("related_silver_ids", []),
            "reason": reviewed.get("reason"),
            "review_origin": reviewed.get("review_origin"),
            "status": "draft_consolidation_required",
        })
    rows.sort(key=lambda row: (-int(row["claim_count"] or 0), row["question_id"]))
    return {
        "schema_version": 1,
        "status": "reviewed_silver_draft_consolidation_work_queue",
        "warning": (
            "one routed question is not one final Silver unit; merge/split/exclude decisions "
            "still require semantic review before publication"
        ),
        "counts": {
            "draft_questions": len(rows),
            "questions_with_existing_silver_context": sum(
                bool(row["related_silver_ids"]) for row in rows
            ),
            "questions_without_existing_silver_context": sum(
                not row["related_silver_ids"] for row in rows
            ),
        },
        "items": rows,
    }


def build_remaining_queue(proposals: dict, registry: dict) -> dict:
    reviewed = {str(item["question_id"]) for item in registry.get("items", [])}
    rows = []
    for proposal in proposals.get("proposals", []):
        qid = str(proposal.get("question_id") or "")
        if not qid or qid in reviewed:
            continue
        candidates = proposal.get("candidates", [])
        source_overlap_count = sum(
            1 for c in candidates if "source_card_overlap" in c.get("routes", [])
        )
        top_score = max((float(c.get("score", 0.0)) for c in candidates), default=0.0)
        top_candidate = candidates[0] if candidates else {}
        rows.append({
            "question_id": qid,
            "canonical_question": proposal.get("canonical_question"),
            "entities": proposal.get("entities", []),
            "source_cards": proposal.get("source_cards", []),
            "claim_count": proposal.get("claim_count", 0),
            "source_overlap_candidate_count": source_overlap_count,
            "top_score": round(top_score, 6),
            "top_candidate": {
                "knowledge_id": top_candidate.get("knowledge_id"),
                "question": top_candidate.get("question"),
                "score": top_candidate.get("score"),
                "routes": top_candidate.get("routes", []),
            } if top_candidate else None,
            "status": "semantic_routing_required",
        })

    rows.sort(
        key=lambda row: (
            0 if row["source_overlap_candidate_count"] else 1,
            -row["source_overlap_candidate_count"],
            -row["top_score"],
            -int(row["claim_count"] or 0),
            row["question_id"],
        )
    )
    return {
        "schema_version": 1,
        "status": "question_to_silver_routing_work_queue",
        "counts": {
            "total_questions": len(proposals.get("proposals", [])),
            "reviewed_questions": len(reviewed),
            "active_work_items": len(rows),
            "remaining_with_source_overlap": sum(
                bool(row["source_overlap_candidate_count"]) for row in rows
            ),
            "remaining_semantic_only": sum(
                not row["source_overlap_candidate_count"] for row in rows
            ),
        },
        "items": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "question-cluster-silver-routing-reviewed-v1.json",
    )
    p.add_argument(
        "--queue-out",
        type=Path,
        default=WORK / "question-cluster-silver-routing-work-queue-v1.json",
    )
    p.add_argument(
        "--draft-out",
        type=Path,
        default=WORK / "silver-draft-work-queue-v1.json",
    )
    args = p.parse_args()

    registry = build_registry(inputs_from_manifest(args.manifest))
    registry["manifest"] = {
        "file": args.manifest.name,
        "sha256": sha256_file(args.manifest),
    }
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    queue = build_remaining_queue(proposals, registry)
    draft_queue = build_draft_queue(proposals, registry)
    queue["inputs"] = {
        "proposals_sha256": sha256_file(args.proposals),
        "reviewed_routing_registry_sha256": None,
    }
    draft_queue["inputs"] = {
        "proposals_sha256": sha256_file(args.proposals),
        "reviewed_routing_registry_sha256": None,
    }

    args.out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    registry_sha = sha256_file(args.out)
    queue["inputs"]["reviewed_routing_registry_sha256"] = registry_sha
    draft_queue["inputs"]["reviewed_routing_registry_sha256"] = registry_sha
    args.queue_out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.draft_out.write_text(
        json.dumps(draft_queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "registry": registry["counts"],
        "queue": queue["counts"],
        "draft_queue": draft_queue["counts"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
